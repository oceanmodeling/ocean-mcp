"""Parsers, formatters, and helper utilities for STOFS data."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# NetCDF parsing
# ---------------------------------------------------------------------------


def _detect_variable(nc, candidates: list[str]):
    """Return the first variable name found in the NetCDF dataset."""
    for name in candidates:
        if name in nc.variables:
            return name
    return None


def _decode_station_names(var) -> list[str]:
    """Decode station names from a NetCDF character or byte array variable."""
    import numpy as np

    data = var[:]
    if hasattr(data, "data"):
        data = data.data

    names = []
    # 2D char array: shape (n_stations, str_len)
    if data.ndim == 2:
        for row in data:
            chars = []
            for c in row:
                if isinstance(c, (bytes, np.bytes_)):
                    ch = c.decode("utf-8", errors="replace")
                else:
                    ch = str(c) if c else ""
                chars.append(ch)
            name = "".join(chars).strip("\x00").strip()
            names.append(name)
    # 1D array of bytes or strings
    elif data.ndim == 1:
        for item in data:
            if isinstance(item, (bytes, np.bytes_)):
                name = item.decode("utf-8", errors="replace").strip("\x00").strip()
            else:
                name = str(item).strip("\x00").strip()
            names.append(name)
    return names


def parse_station_netcdf(
    filepath: Path | str,
    station_id: str | None = None,
) -> dict[str, Any]:
    """Open a STOFS station NetCDF file and extract water level time series.

    Args:
        filepath: Path to the downloaded NetCDF file.
        station_id: CO-OPS station ID to extract. If None, returns metadata
                    about all stations without time series data.

    Returns:
        Dict with keys:
            - 'station_names': list of all station ID strings
            - 'lats': list of latitudes
            - 'lons': list of longitudes
            - 'n_stations': total station count
            - 'n_times': total time steps
            - 'datum': datum attribute if available
            If station_id provided, also:
            - 'station_id': the matched station ID
            - 'station_idx': index in the array
            - 'times': list of ISO 8601 datetime strings
            - 'values': list of water level values (m), NaN filtered
            - 'lat': station latitude
            - 'lon': station longitude
            - 'model_start': first time string
            - 'model_end': last time string

    Raises:
        ValueError: If station_id is not found in the file.
        RuntimeError: If required variables are missing.
    """
    import netCDF4
    import numpy as np

    nc = netCDF4.Dataset(str(filepath), "r")
    try:
        # --- Detect variable names ---
        time_var_name = _detect_variable(nc, ["time", "ocean_time"])
        zeta_var_name = _detect_variable(
            nc, ["zeta", "elevation", "water_level", "ssh"]
        )
        sname_var_name = _detect_variable(nc, ["station_name", "station", "stationid"])
        lat_var_name = _detect_variable(nc, ["y", "lat", "latitude"])
        lon_var_name = _detect_variable(nc, ["x", "lon", "longitude"])

        if not time_var_name:
            raise RuntimeError("Could not find time variable in NetCDF file.")
        if not zeta_var_name:
            raise RuntimeError("Could not find water level variable in NetCDF file.")

        # --- Station names ---
        station_names: list[str] = []
        if sname_var_name:
            station_names = _decode_station_names(nc.variables[sname_var_name])

        # --- Coordinates ---
        lats: list[float] = []
        lons: list[float] = []
        if lat_var_name:
            lats = list(
                float(v) for v in np.array(nc.variables[lat_var_name][:]).ravel()
            )
        if lon_var_name:
            lons = list(
                float(v) for v in np.array(nc.variables[lon_var_name][:]).ravel()
            )

        n_stations = len(station_names) or (len(lats) if lats else 0)
        n_times = len(nc.variables[time_var_name])

        # --- Datum attribute ---
        datum = getattr(nc, "datum", getattr(nc, "vertical_datum", ""))

        result: dict[str, Any] = {
            "station_names": station_names,
            "lats": lats,
            "lons": lons,
            "n_stations": n_stations,
            "n_times": n_times,
            "datum": datum,
        }

        if station_id is None:
            return result

        # --- Find station index ---
        station_idx = None
        for i, name in enumerate(station_names):
            if station_id in name or name.strip() == station_id:
                station_idx = i
                break

        if station_idx is None:
            raise ValueError(
                f"Station '{station_id}' not found in this STOFS file. "
                f"Available station IDs (first 20): "
                f"{', '.join(station_names[:20])}"
            )

        # --- Time array ---
        time_var = nc.variables[time_var_name]
        units = getattr(time_var, "units", "seconds since 1970-01-01 00:00:00")
        calendar = getattr(time_var, "calendar", "standard")
        raw_times = time_var[:]
        if hasattr(raw_times, "data"):
            raw_times = raw_times.data

        datetimes = netCDF4.num2date(raw_times, units=units, calendar=calendar)
        time_strings = [dt.strftime("%Y-%m-%d %H:%M") for dt in datetimes]

        # --- Water level time series ---
        zeta = nc.variables[zeta_var_name]
        fill_value = getattr(zeta, "_FillValue", None)

        # zeta shape: (time, station)
        values_raw = np.array(zeta[:, station_idx])

        # Mask fill values
        if fill_value is not None:
            mask = np.abs(values_raw) > 1e10
            mask |= values_raw == fill_value
        else:
            mask = np.abs(values_raw) > 1e10

        # Build filtered lists
        times_out = []
        values_out = []
        for t_str, v, m in zip(time_strings, values_raw.tolist(), mask.tolist()):
            if not m:
                times_out.append(t_str)
                values_out.append(round(float(v), 4))

        station_lat = lats[station_idx] if station_idx < len(lats) else None
        station_lon = lons[station_idx] if station_idx < len(lons) else None

        result.update(
            {
                "station_id": station_id,
                "station_idx": station_idx,
                "times": times_out,
                "values": values_out,
                "lat": station_lat,
                "lon": station_lon,
                "model_start": time_strings[0] if time_strings else "",
                "model_end": time_strings[-1] if time_strings else "",
            }
        )
        return result

    finally:
        nc.close()


# ---------------------------------------------------------------------------
# Nearest station finder
# ---------------------------------------------------------------------------


def find_nearest_station(
    target_lat: float,
    target_lon: float,
    station_lats: list[float],
    station_lons: list[float],
    station_names: list[str],
    max_distance_km: float = 50.0,
) -> tuple[int, str, float] | None:
    """Find the nearest station within max_distance_km.

    Returns:
        (index, station_name, distance_km) or None if none within range.
    """
    best_idx = None
    best_dist = float("inf")

    for i, (lat, lon) in enumerate(zip(station_lats, station_lons)):
        dist = _haversine(target_lat, target_lon, lat, lon)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    if best_idx is None or best_dist > max_distance_km:
        return None

    return best_idx, station_names[best_idx], best_dist


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------


def compute_validation_stats(
    forecast: list[float],
    observed: list[float],
) -> dict[str, float]:
    """Compute bias, RMSE, MAE, peak error, and correlation for aligned arrays.

    Args:
        forecast: List of STOFS forecast values (m).
        observed: List of CO-OPS observed values (m), same length as forecast.

    Returns:
        Dict with keys: bias, rmse, mae, peak_error, correlation, n.
    """
    import numpy as np

    f = np.array(forecast, dtype=float)
    o = np.array(observed, dtype=float)

    if len(f) == 0 or len(f) != len(o):
        return {
            "bias": None,
            "rmse": None,
            "mae": None,
            "peak_error": None,
            "correlation": None,
            "n": 0,
        }

    diff = f - o
    bias = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff**2)))
    mae = float(np.mean(np.abs(diff)))
    peak_error = float(np.max(np.abs(diff)))

    # Correlation
    if np.std(f) > 0 and np.std(o) > 0:
        correlation = float(np.corrcoef(f, o)[0, 1])
    else:
        correlation = float("nan")

    return {
        "bias": round(bias, 4),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "peak_error": round(peak_error, 4),
        "correlation": round(correlation, 4),
        "n": int(len(f)),
    }


def compute_peak_stats(
    times: list[str],
    forecast: list[float],
    observed: list[float],
) -> dict[str, Any]:
    """Compare forecast and observed peaks over the same aligned timestamps.

    Both maxima come from the aligned series, so they cover the same period.
    ``observed_peak_at_series_end`` flags an observed maximum on the last
    aligned point: the water was still rising when the record (or the gauge)
    ended, so the true observed peak may be higher.

    Args:
        times: Aligned timestamps, 'YYYY-MM-DD HH:MM' (UTC).
        forecast: Forecast values (m), same length as times.
        observed: Observed values (m), same length as times.

    Returns:
        Dict with observed/forecast peak value and time, peak_error_m
        (forecast peak minus observed peak) and peak_timing_error_hours
        (positive means the forecast peak came later).
    """
    if not times or not (len(times) == len(forecast) == len(observed)):
        return {
            "observed_peak_m": None,
            "observed_peak_time": None,
            "forecast_peak_m": None,
            "forecast_peak_time": None,
            "peak_error_m": None,
            "peak_timing_error_hours": None,
            "observed_peak_at_series_end": None,
        }

    i_obs = max(range(len(observed)), key=observed.__getitem__)
    i_fc = max(range(len(forecast)), key=forecast.__getitem__)
    t_obs = datetime.strptime(times[i_obs], "%Y-%m-%d %H:%M")
    t_fc = datetime.strptime(times[i_fc], "%Y-%m-%d %H:%M")

    return {
        "observed_peak_m": round(observed[i_obs], 4),
        "observed_peak_time": times[i_obs],
        "forecast_peak_m": round(forecast[i_fc], 4),
        "forecast_peak_time": times[i_fc],
        "peak_error_m": round(forecast[i_fc] - observed[i_obs], 4),
        "peak_timing_error_hours": round((t_fc - t_obs).total_seconds() / 3600, 2),
        "observed_peak_at_series_end": i_obs == len(observed) - 1,
    }


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------


def align_timeseries(
    forecast_times: list[str],
    forecast_values: list[float],
    observed_times: list[str],
    observed_values: list[float],
    tolerance_minutes: int = 3,
) -> tuple[list[str], list[float], list[float]]:
    """Align two time series to common timestamps.

    Matches forecast times to the nearest observed timestamp within
    tolerance_minutes. Returns only matched pairs.

    Args:
        forecast_times: List of 'YYYY-MM-DD HH:MM' strings.
        forecast_values: Corresponding forecast values.
        observed_times: List of 'YYYY-MM-DD HH:MM' strings.
        observed_values: Corresponding observed values.
        tolerance_minutes: Max time difference for a match (default 3).

    Returns:
        (common_times, aligned_forecast, aligned_observed) lists.
    """

    def parse_dt(s: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%m/%d/%Y %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {s!r}")

    tol = tolerance_minutes * 60  # seconds

    obs_dts = [parse_dt(t) for t in observed_times]
    obs_timestamps = [dt.timestamp() for dt in obs_dts]

    common_times = []
    aligned_forecast = []
    aligned_observed = []

    for f_t_str, f_v in zip(forecast_times, forecast_values):
        try:
            f_dt = parse_dt(f_t_str)
        except ValueError:
            continue
        f_ts = f_dt.timestamp()

        # Find nearest observed
        best_i = None
        best_diff = float("inf")
        for i, o_ts in enumerate(obs_timestamps):
            diff = abs(f_ts - o_ts)
            if diff < best_diff:
                best_diff = diff
                best_i = i

        if best_i is not None and best_diff <= tol:
            common_times.append(f_t_str)
            aligned_forecast.append(f_v)
            aligned_observed.append(observed_values[best_i])

    return common_times, aligned_forecast, aligned_observed


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_timeseries_table(
    times: list[str],
    values: list[float],
    title: str = "",
    metadata_lines: list[str] | None = None,
    max_rows: int = 100,
    source: str = "NOAA STOFS",
) -> str:
    """Format a water level time series as a markdown table.

    Subsamples to max_rows if longer. Includes min/max/mean summary.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    total = len(times)
    if total == 0:
        lines.append("*No data available.*")
        return "\n".join(lines)

    # Compute summary
    import numpy as np

    vals = [v for v in values if v is not None]
    if vals:
        v_min = min(vals)
        v_max = max(vals)
        v_mean = float(np.mean(vals))
        lines.append(
            f"**Min**: {v_min:.3f} m | **Max**: {v_max:.3f} m | "
            f"**Mean**: {v_mean:.3f} m | **Total points**: {total}"
        )
        lines.append("")

    # Subsample
    if total > max_rows:
        step = max(1, total // max_rows)
        indices = list(range(0, total, step))
        times_show = [times[i] for i in indices]
        values_show = [values[i] for i in indices]
        lines.append(f"*Showing every {step}th point ({len(indices)} of {total} rows)*")
        lines.append("")
    else:
        times_show = times
        values_show = values

    lines.append("| Time (UTC) | Water Level (m) |")
    lines.append("| --- | --- |")
    for t, v in zip(times_show, values_show):
        lines.append(f"| {t} | {v:.3f} |")

    lines.append("")
    lines.append(f"*Data from {source}.*")
    return "\n".join(lines)


def format_station_table(
    stations: list[dict],
    title: str = "",
    metadata_lines: list[str] | None = None,
    extra_col: tuple[str, str] | None = None,
    source: str = "NOAA STOFS",
) -> str:
    """Format a list of station dicts as a markdown table.

    Args:
        stations: List of station dicts with id, name, state, lat, lon.
        title: Optional heading.
        metadata_lines: Optional lines shown below title.
        extra_col: Optional (key, header) tuple for an extra column.
        source: Attribution string.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    if extra_col:
        key, header = extra_col
        lines.append(f"| Station ID | Name | State | Lat | Lon | {header} |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for s in stations:
            lines.append(
                f"| {s.get('id', '')} | {s.get('name', '')} | {s.get('state', '')} "
                f"| {s.get('lat', '')} | {s.get('lon', '')} | {s.get(key, '')} |"
            )
    else:
        lines.append("| Station ID | Name | State | Lat | Lon |")
        lines.append("| --- | --- | --- | --- | --- |")
        for s in stations:
            lines.append(
                f"| {s.get('id', '')} | {s.get('name', '')} | {s.get('state', '')} "
                f"| {s.get('lat', '')} | {s.get('lon', '')} |"
            )

    lines.append("")
    lines.append(f"*{len(stations)} stations. Data from {source}.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cycle resolution
# ---------------------------------------------------------------------------


async def resolve_latest_cycle(
    client,
    model: str,
    num_days: int = 2,
) -> tuple[str, str] | None:
    """Find the latest available STOFS cycle on AWS S3.

    Checks today and yesterday (or more days), newest cycle first.

    Args:
        client: STOFSClient instance.
        model: '2d_global' or '3d_atlantic'.
        num_days: Number of past days to check.

    Returns:
        (date_str, cycle_str) tuple (e.g., ('20260219', '12')), or None.
    """
    import time
    from datetime import timedelta
    from .models import MODEL_CYCLES

    # Short-TTL cache on the client: resolving sweeps several S3 HEADs and every
    # forecast tool resolves on each call. Cache positive results only.
    cache = getattr(client, "_cycle_cache", None)
    ttl = getattr(client, "_cycle_cache_ttl", 0.0)
    now = time.monotonic()
    if cache is not None:
        hit = cache.get(model)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]

    cycles = MODEL_CYCLES.get(model, ["12"])
    today = datetime.now(timezone.utc)

    for day_offset in range(num_days):
        date = today - timedelta(days=day_offset)
        date_str = date.strftime("%Y%m%d")
        for cycle in cycles:
            url = client.build_station_url(model, date_str, cycle)
            if await client.check_file_exists(url):
                if cache is not None:
                    cache[model] = (now, (date_str, cycle))
                return date_str, cycle

    return None


async def resolve_cycle(
    client,
    model: str,
    cycle_date: str | None,
    cycle_hour: str | None,
) -> tuple[str, str] | None:
    """Resolve a STOFS cycle (date, hour), finding the latest if unspecified.

    Single source of truth shared by every STOFS tool. If only one of
    ``cycle_date`` / ``cycle_hour`` is given, the other defaults sensibly
    (date → today; hour → the model's first configured cycle) **and the
    provided value is honoured**. The validation tool previously had its own
    copy that required *both* and silently fell back to the latest cycle when
    only a date was given — so a historical ``cycle_date`` was ignored and the
    comparison ran against the wrong (latest) cycle with no error. Centralized
    here to keep that from happening again.

    Returns:
        (YYYYMMDD, HH) or None if a provided ``cycle_date`` is unparseable.
    """
    from .models import MODEL_CYCLES

    if cycle_date or cycle_hour:
        if cycle_date:
            date_str: str | None = None
            for fmt in ("%Y-%m-%d", "%Y%m%d"):
                try:
                    date_str = datetime.strptime(cycle_date, fmt).strftime("%Y%m%d")
                    break
                except ValueError:
                    continue
            if date_str is None:
                return None
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

        if cycle_hour:
            hour_str = cycle_hour.zfill(2)
        else:
            # Default to the model's first listed cycle hour.
            hour_str = (MODEL_CYCLES.get(model) or ["12"])[0]
        return date_str, hour_str

    return await resolve_latest_cycle(client, model)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def handle_stofs_error(e: Exception, model: str = "", url: str = "") -> str:
    """Format an exception into a user-friendly STOFS error message.

    Args:
        e: The exception.
        model: Model name for context.
        url: URL that was being accessed.

    Returns:
        User-friendly error string.
    """
    import httpx

    model_label = f" ({model})" if model else ""

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"STOFS file not found{model_label} (HTTP 404). "
                "The cycle may not be available yet or has been archived. "
                "Use stofs_list_cycles to check available forecast cycles."
            )
        if status == 403:
            return (
                f"AWS S3 access denied{model_label} (HTTP 403). "
                "The data may have been archived. Try a more recent date."
            )
        return (
            f"HTTP {status} error{model_label}. "
            "The STOFS S3 bucket may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"Download timed out{model_label}. "
            "STOFS NetCDF files can be 2-10 MB and may be slow. "
            "Try again or use a different cycle."
        )

    if isinstance(e, ValueError):
        return str(e)

    if "NetCDF" in type(e).__name__ or "netCDF" in str(e):
        return (
            f"Error reading STOFS NetCDF file{model_label}. "
            "The file may be corrupted or the format may have changed. "
            "Try a different cycle using stofs_list_cycles."
        )

    return f"Unexpected error{model_label}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# OPeNDAP region selection
# ---------------------------------------------------------------------------


def get_opendap_region(latitude: float, longitude: float) -> str:
    """Return the NOMADS STOFS-2D regional product name for a lat/lon.

    NOMADS serves STOFS as separate per-region datasets. This helper maps
    any lat/lon to the correct region name to use in the OPeNDAP URL.

    Region boundaries are approximate; they are checked in priority order
    (small/specific regions first, broad CONUS regions last).

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees (-180 to 180).

    Returns:
        NOMADS region string: one of 'conus.east', 'conus.west', 'alaska',
        'hawaii', 'puertori', 'guam', 'northpacific'.
    """
    # Guam (positive longitude, western Pacific)
    if 12.0 <= latitude <= 17.0 and 143.0 <= longitude <= 149.0:
        return "guam"

    # Hawaii (~-163W to -153W)
    if 17.5 <= latitude <= 23.5 and -163.0 <= longitude <= -153.0:
        return "hawaii"

    # Puerto Rico / USVI (~-69W to -63W)
    if 16.5 <= latitude <= 20.5 and -69.0 <= longitude <= -63.0:
        return "puertori"

    # Alaska: high latitudes, western hemisphere (west of -130W) or far east Pacific
    if latitude >= 50.0 and (longitude <= -130.0 or longitude >= 150.0):
        return "alaska"

    # CONUS West coast (Pacific): roughly west of -115W
    if 20.0 <= latitude <= 53.0 and -131.0 <= longitude <= -115.0:
        return "conus.west"

    # CONUS East + Gulf: roughly east of -100W (Atlantic + Gulf of Mexico)
    if 20.0 <= latitude <= 53.0 and -100.0 <= longitude <= -60.0:
        return "conus.east"

    # North Pacific / global fallback
    return "northpacific"


# ---------------------------------------------------------------------------
# OPeNDAP point extraction (regular-grid NOMADS datasets)
# ---------------------------------------------------------------------------


def extract_point_from_opendap(
    opendap_url: str,
    latitude: float,
    longitude: float,
    variable: str | None = None,
) -> dict[str, Any]:
    """Extract a time series at a single lat/lon from a NOMADS OPeNDAP dataset.

    Opens the remote dataset with xarray and selects the nearest grid point.
    Only the requested slice is transferred over the network via OPeNDAP —
    the full gridded field is never downloaded.

    **Important**: This function uses blocking I/O (xarray's netCDF4 engine
    for OPeNDAP is synchronous). Always call it via ``asyncio.to_thread()``
    from async tool handlers to avoid blocking the MCP event loop.

    Args:
        opendap_url: Full NOMADS OPeNDAP URL
            (e.g., ``https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/...``).
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        variable: Specific variable name to extract. If None, auto-detects
            the combined water level variable.

    Returns:
        Dict with keys:
            - ``times``: list of 'YYYY-MM-DD HH:MM' strings
            - ``values``: list of water level values (m), NaN filtered
            - ``actual_lat``: float — latitude of nearest grid point
            - ``actual_lon``: float — longitude of nearest grid point
            - ``variable``: str — variable name used
            - ``n_times``: int — number of valid time steps
            - ``grid_resolution_deg``: float — approximate grid spacing (°)

    Raises:
        RuntimeError: If the OPeNDAP endpoint is unreachable.
        ValueError: If no suitable water level variable is found.
    """
    import numpy as np
    import xarray as xr

    try:
        ds = xr.open_dataset(opendap_url, engine="netcdf4")
    except Exception as e:
        raise RuntimeError(
            f"Cannot open OPeNDAP dataset at {opendap_url}. "
            f"NOMADS may be temporarily unavailable. Error: {e}"
        )

    try:
        # --- Auto-detect water level variable if not specified ---
        if variable is None:
            candidates = [
                "etcwlsfc",  # combined water level (NOMADS STOFS OPeNDAP name)
                "etsrgsfc",  # storm surge (NOMADS STOFS OPeNDAP name)
                "etwlswlc",  # alternative name seen in some products
                "etsurgetsrg",  # alternative surge name
                "zeta",  # native NetCDF name (not typical on NOMADS)
                "water_level",
            ]
            for name in candidates:
                if name in ds.data_vars:
                    variable = name
                    break

            if variable is None:
                available = list(ds.data_vars)
                ds.close()
                raise ValueError(
                    f"No known water level variable found in OPeNDAP dataset. "
                    f"Available variables: {available}. "
                    "Specify the variable name explicitly using the 'variable' parameter."
                )

        if variable not in ds.data_vars:
            available = list(ds.data_vars)
            ds.close()
            raise ValueError(
                f"Variable '{variable}' not found in OPeNDAP dataset. "
                f"Available: {available}"
            )

        # --- Resolve longitude convention (NOMADS may use 0-360 instead of -180-180) ---
        lon_vals = ds["lon"].values if "lon" in ds.coords else ds["longitude"].values
        lon_name = "lon" if "lon" in ds.coords else "longitude"
        lat_name = "lat" if "lat" in ds.coords else "latitude"

        query_lon = longitude
        if float(lon_vals.min()) >= 0 and longitude < 0:
            # Dataset uses 0-360, convert target
            query_lon = longitude % 360

        # --- Select nearest grid point ---
        point = ds[variable].sel(
            {lat_name: latitude, lon_name: query_lon},
            method="nearest",
        )

        actual_lat = float(point[lat_name].values)
        actual_lon_raw = float(point[lon_name].values)

        # --- If nearest cell is all NaN (land), find nearest wet ocean cell ---
        # The regular grid has NaN over land; coastal points often snap to a land cell.
        # Load a ±0.5° area at the first time step to find valid ocean cells.
        check_vals = point.values
        time_dim = list(point.dims)[0] if point.dims else "time"
        if np.all(np.isnan(check_vals) | (np.abs(check_vals) > 1e10)):
            search_radius = 0.5
            lat_slice = slice(latitude - search_radius, latitude + search_radius)
            lon_slice = slice(query_lon - search_radius, query_lon + search_radius)
            area = ds[variable].sel({lat_name: lat_slice, lon_name: lon_slice})
            t0_vals = area.isel({time_dim: 0}).values  # (lat, lon)
            lats_area = area[lat_name].values
            lons_area = area[lon_name].values

            valid_mask = ~np.isnan(t0_vals) & (np.abs(t0_vals) < 1e10)
            if valid_mask.sum() > 0:
                lat_grid, lon_grid = np.meshgrid(lats_area, lons_area, indexing="ij")
                dist_grid = (lat_grid - latitude) ** 2 + (lon_grid - query_lon) ** 2
                dist_grid[~valid_mask] = 1e9
                idx = np.unravel_index(np.argmin(dist_grid), dist_grid.shape)
                best_lat = float(lats_area[idx[0]])
                best_lon = float(lons_area[idx[1]])
                # Re-select the full time series at the nearest wet cell
                point = ds[variable].sel(
                    {lat_name: best_lat, lon_name: best_lon}, method="nearest"
                )
                actual_lat = float(point[lat_name].values)
                actual_lon_raw = float(point[lon_name].values)

        # Convert back to -180-180 if needed
        actual_lon = actual_lon_raw if actual_lon_raw <= 180 else actual_lon_raw - 360

        # --- Extract time series ---
        times_raw = point[time_dim].values if time_dim in point.coords else None

        values_raw = point.values  # shape: (time,)

        # Convert numpy datetime64 to strings
        times_out: list[str] = []
        if times_raw is not None:
            for t in times_raw:
                try:
                    if hasattr(t, "isoformat"):
                        times_out.append(t.isoformat()[:16].replace("T", " "))
                    else:
                        # numpy datetime64
                        ts = (
                            t - np.datetime64("1970-01-01T00:00:00")
                        ) / np.timedelta64(1, "s")
                        from datetime import datetime, timezone

                        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                        times_out.append(dt.strftime("%Y-%m-%d %H:%M"))
                except Exception:
                    times_out.append("")

        # Filter NaN / fill values
        times_filtered: list[str] = []
        values_filtered: list[float] = []
        for t_str, v in zip(times_out, values_raw.tolist()):
            try:
                fv = float(v)
                if not (fv is None or (fv != fv) or abs(fv) > 1e10):  # NaN check
                    times_filtered.append(t_str)
                    values_filtered.append(round(fv, 4))
            except (TypeError, ValueError):
                continue

        # Estimate grid resolution
        lat_arr = ds[lat_name].values
        grid_res = abs(float(lat_arr[1] - lat_arr[0])) if len(lat_arr) > 1 else 0.0

        return {
            "times": times_filtered,
            "values": values_filtered,
            "actual_lat": round(actual_lat, 4),
            "actual_lon": round(actual_lon, 4),
            "variable": variable,
            "n_times": len(times_filtered),
            "grid_resolution_deg": round(grid_res, 4),
        }

    finally:
        ds.close()


# ---------------------------------------------------------------------------
# Temp file cleanup
# ---------------------------------------------------------------------------


def cleanup_temp_file(filepath: Path | str | None) -> None:
    """Remove a temporary NetCDF file. Safe to call with None."""
    if filepath is None:
        return
    try:
        os.unlink(str(filepath))
    except OSError:
        pass
