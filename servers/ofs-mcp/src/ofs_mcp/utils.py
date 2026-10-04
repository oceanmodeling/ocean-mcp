"""Parsers, formatters, and helpers for OFS data."""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two lat/lon points."""
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
# NetCDF variable detection
# ---------------------------------------------------------------------------


def _detect_variable(nc, candidates: list[str]) -> str | None:
    """Return the first variable name found in the NetCDF dataset."""
    for name in candidates:
        if name in nc.variables:
            return name
    return None


def _parse_nc_times(nc, time_var_name: str) -> list[str]:
    """Parse time variable from NetCDF into ISO 8601 strings.

    Handles ROMS (ocean_time: seconds/days since ref) and
    FVCOM (time: days since ref, or Times: character array).
    """
    import netCDF4
    import numpy as np

    # FVCOM character array 'Times'
    if time_var_name == "Times":
        raw = nc.variables["Times"][:]
        if hasattr(raw, "data"):
            raw = raw.data
        result = []
        for row in raw:
            try:
                s = (
                    "".join(
                        c.decode("utf-8", errors="replace")
                        if isinstance(c, bytes)
                        else str(c)
                        for c in row
                    )
                    .strip("\x00")
                    .strip()
                )
                # Format: YYYY-MM-DDTHH:MM:SS.SS
                result.append(s[:16].replace("T", " "))
            except Exception:
                result.append("")
        return result

    # Float time variable (ocean_time, time)
    time_var = nc.variables[time_var_name]
    units = getattr(time_var, "units", "seconds since 1970-01-01 00:00:00")
    calendar = getattr(time_var, "calendar", "standard")
    raw = time_var[:]
    if hasattr(raw, "data"):
        raw = np.array(raw.data)

    datetimes = netCDF4.num2date(raw, units=units, calendar=calendar)
    return [dt.strftime("%Y-%m-%d %H:%M") for dt in datetimes]


# ---------------------------------------------------------------------------
# ROMS grid nearest-point finder
# ---------------------------------------------------------------------------


def find_nearest_roms(
    target_lat: float,
    target_lon: float,
    lat_rho,  # numpy 2D array (eta_rho, xi_rho)
    lon_rho,  # numpy 2D array (eta_rho, xi_rho)
    max_distance_km: float = 200.0,
    valid=None,  # optional numpy 2D bool array; only True cells are candidates
) -> tuple[int, int, float] | None:
    """Find nearest (i, j) grid cell on a ROMS structured grid.

    Returns:
        (i, j, distance_km) or None if beyond max_distance_km (or if no
        ``valid`` cell exists).
    """
    import numpy as np

    lat_arr = np.array(lat_rho)
    lon_arr = np.array(lon_rho)

    # Vectorized haversine
    R = 6371.0
    phi1 = math.radians(target_lat)
    phi2 = np.radians(lat_arr)
    dphi = phi2 - phi1
    dlambda = np.radians(lon_arr - target_lon)
    a = np.sin(dphi / 2) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    dist = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    if valid is not None:
        dist = np.where(np.asarray(valid, dtype=bool), dist, np.inf)

    idx = np.unravel_index(np.argmin(dist), dist.shape)
    min_dist = float(dist[idx])

    if min_dist > max_distance_km:
        return None

    return int(idx[0]), int(idx[1]), min_dist


# ---------------------------------------------------------------------------
# FVCOM grid nearest-node finder
# ---------------------------------------------------------------------------


def find_nearest_fvcom(
    target_lat: float,
    target_lon: float,
    lats,  # numpy 1D array (node,)
    lons,  # numpy 1D array (node,)
    max_distance_km: float = 200.0,
) -> tuple[int, float] | None:
    """Find nearest node index on an FVCOM unstructured grid.

    Returns:
        (node_idx, distance_km) or None if beyond max_distance_km.
    """
    import numpy as np

    lat_arr = np.array(lats)
    lon_arr = np.array(lons)

    R = 6371.0
    phi1 = math.radians(target_lat)
    phi2 = np.radians(lat_arr)
    dphi = phi2 - phi1
    dlambda = np.radians(lon_arr - target_lon)
    a = np.sin(dphi / 2) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    dist = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    idx = int(np.argmin(dist))
    min_dist = float(dist[idx])

    if min_dist > max_distance_km:
        return None

    return idx, min_dist


# ---------------------------------------------------------------------------
# OFS point time series extraction
# ---------------------------------------------------------------------------


def _read_point_series(var, index: tuple, chunk: int = 24):
    """Read ``var[:, *index]``, tolerating unreadable stretches of the time axis.

    THREDDS FMRC "best" aggregations list the newest run before all of its
    data can be served, and one bad stretch fails the whole request with
    "NetCDF: DAP failure". On failure, read ``chunk`` steps at a time and
    leave the unreadable chunks as NaN (dropped later as fill). Re-raises if
    nothing at all can be read.
    """
    import numpy as np

    try:
        return np.array(var[(slice(None),) + index], dtype=float)
    except RuntimeError:
        n = var.shape[0]
        out = np.full(n, np.nan)
        read_any = False
        for a in range(0, n, chunk):
            b = min(a + chunk, n)
            try:
                out[a:b] = np.array(var[(slice(a, b),) + index], dtype=float)
                read_any = True
            except RuntimeError:
                continue
        if not read_any:
            raise
        return out


def extract_point_timeseries(
    nc,
    model: str,
    variable: str,
    target_lat: float,
    target_lon: float,
    max_distance_km: float = 200.0,
) -> dict[str, Any]:
    """Extract a surface time series at a lat/lon point from an OFS NetCDF.

    Works for structured (ROMS, POM) and unstructured (FVCOM) grids. The grid
    layout and the time axis are read from the file itself, not from the
    model registry: the same model is served with a different time axis by
    the THREDDS FMRC aggregation ('time') than in its S3 files ('ocean_time'),
    and several models have changed grid type over the years.

    Args:
        nc: Open netCDF4.Dataset (local file or OPeNDAP).
        model: OFS model key (e.g., 'cbofs').
        variable: OFSVariable value — 'water_level', 'temperature', 'salinity'.
        target_lat: Target latitude in decimal degrees.
        target_lon: Target longitude in decimal degrees.
        max_distance_km: Maximum allowed distance to nearest grid point (default 200 km).

    Returns:
        Dict with:
            - 'times': list of 'YYYY-MM-DD HH:MM' strings
            - 'values': list of floats
            - 'lat': actual grid point latitude
            - 'lon': actual grid point longitude
            - 'distance_km': distance from target to nearest point
            - 'variable': variable name used
            - 'units': variable units
            - 'fill_count': number of fill values encountered

    Raises:
        ValueError: If no grid point found within max_distance_km.
        RuntimeError: If required variables are not found.
    """
    import numpy as np
    from .models import OFS_MODELS

    model_info = OFS_MODELS.get(model, {})
    nc_vars = model_info.get("nc_vars", {})

    # --- Detect variable to extract ---
    var_map = {
        "water_level": [nc_vars.get("water_level", ""), "zeta", "ssh", "water_level"],
        "temperature": [
            nc_vars.get("temperature", ""),
            "temp",
            "temperature",
            "water_temp",
        ],
        "salinity": [nc_vars.get("salinity", ""), "salt", "salinity", "sal"],
    }
    var_candidates = [v for v in var_map.get(variable, []) if v]
    nc_var_name = _detect_variable(nc, var_candidates)
    if not nc_var_name:
        raise RuntimeError(
            f"Variable '{variable}' not found in {model.upper()} NetCDF file. "
            f"Checked: {var_candidates}. Available: {list(nc.variables.keys())[:20]}"
        )

    var = nc.variables[nc_var_name]
    var_units = getattr(var, "units", "")
    fill_value = getattr(var, "_FillValue", None)
    ndim = len(var.shape)

    # --- Detect time variable ---
    # The time axis is the variable's own first dimension. The registry name
    # is only a fallback: in the THREDDS FMRC aggregations zeta is on 'time'
    # while 'ocean_time' survives as a length-1 leftover, so trusting the
    # registry paired a full series with a single timestamp.
    time_dim = var.dimensions[0] if var.dimensions else ""
    if time_dim in nc.variables:
        time_var_name = time_dim
    else:
        time_candidates = [nc_vars.get("time", ""), "ocean_time", "time", "Times"]
        time_var_name = _detect_variable(nc, [c for c in time_candidates if c])
    if not time_var_name:
        raise RuntimeError(f"Time variable not found in {model.upper()} NetCDF file.")

    # --- Find nearest grid point ---
    lon_candidates = [nc_vars.get("lon", ""), "lon_rho", "lon", "x", "longitude"]
    lat_candidates = [nc_vars.get("lat", ""), "lat_rho", "lat", "y", "latitude"]
    lon_name = _detect_variable(nc, [c for c in lon_candidates if c])
    lat_name = _detect_variable(nc, [c for c in lat_candidates if c])
    if not lon_name or not lat_name:
        raise RuntimeError(
            f"Coordinate variables not found in {model.upper()} NetCDF file."
        )

    lon_arr = np.array(nc.variables[lon_name][:])
    lat_arr = np.array(nc.variables[lat_name][:])

    # Grid layout from the coordinates themselves: 2-D lon/lat is a structured
    # grid (ROMS rho points, POM); 1-D is an FVCOM node list.
    if lon_arr.ndim == 2:
        # A coastal gauge's nearest grid point is often land, which holds only
        # fill/NaN (or a constant on GOMOFS). Search water cells only: the
        # land mask (ROMS mask_rho, POM mask) and, where bathymetry is given,
        # h > 0 — wetting/drying grids (CIOFS) mark tidal flats as water but
        # give them negative h, and those cells sit dry at a constant level.
        valid = np.ones(lon_arr.shape, dtype=bool)
        for mask_name in ("mask_rho", "mask"):
            if mask_name in nc.variables:
                land_mask = np.array(nc.variables[mask_name][:])
                if land_mask.shape == lon_arr.shape:
                    valid &= land_mask > 0.5
                break
        if "h" in nc.variables:
            depth = np.array(nc.variables["h"][:])
            if depth.shape == lon_arr.shape:
                valid &= depth > 0
        result = find_nearest_roms(
            target_lat, target_lon, lat_arr, lon_arr, max_distance_km, valid
        )
        if result is None:
            raise ValueError(
                f"No {model.upper()} water grid point within {max_distance_km} km of "
                f"({target_lat:.4f}, {target_lon:.4f}). "
                "Use ofs_list_models to check model domains, or increase max_distance_km."
            )
        i, j, dist_km = result
        point_lat = float(lat_arr[i, j])
        point_lon = float(lon_arr[i, j])

        if ndim == 4:
            # (time, level, y, x). ROMS s_rho counts up from the bottom, so the
            # surface is the last level; POM sigma counts down from the surface.
            surface = -1 if var.dimensions[1] in ("s_rho", "s_w") else 0
            raw_vals = _read_point_series(var, (surface, i, j))
        elif ndim == 3:
            # (time, y, x), e.g. zeta
            raw_vals = _read_point_series(var, (i, j))
        else:
            raw_vals = np.array(var[:])

    else:  # unstructured (FVCOM)
        lons = lon_arr.ravel()
        lats = lat_arr.ravel()

        result = find_nearest_fvcom(target_lat, target_lon, lats, lons, max_distance_km)
        if result is None:
            raise ValueError(
                f"No {model.upper()} grid point within {max_distance_km} km of "
                f"({target_lat:.4f}, {target_lon:.4f}). "
                "Use ofs_list_models to check model domains, or increase max_distance_km."
            )
        node_idx, dist_km = result
        point_lat = float(lats[node_idx])
        point_lon = float(lons[node_idx])

        if ndim == 3:
            # (time, siglay, node) — surface = siglay index 0
            raw_vals = _read_point_series(var, (0, node_idx))
        else:
            # (time, node), e.g. zeta
            raw_vals = _read_point_series(var, (node_idx,))

    # --- Parse times ---
    time_strings = _parse_nc_times(nc, time_var_name)
    if len(time_strings) != len(raw_vals):
        # zip() below would silently truncate to the shorter of the two.
        raise RuntimeError(
            f"{model.upper()} time axis '{time_var_name}' has {len(time_strings)} "
            f"steps but '{nc_var_name}' has {len(raw_vals)}; refusing to pair them."
        )

    # --- Mask fill values ---
    # FMRC best series carry NaN where a run is missing; NaN fails the > 1e10
    # test, so check finiteness explicitly.
    raw_vals = raw_vals.astype(float)
    mask = ~np.isfinite(raw_vals) | (np.abs(raw_vals) > 1e10)
    if fill_value is not None:
        mask |= raw_vals == float(fill_value)

    # Build filtered output
    times_out: list[str] = []
    values_out: list[float] = []
    fill_count = 0

    for t_str, v, m in zip(time_strings, raw_vals.tolist(), mask.tolist()):
        if m:
            fill_count += 1
        else:
            times_out.append(t_str)
            values_out.append(round(float(v), 4))

    return {
        "times": times_out,
        "values": values_out,
        "lat": point_lat,
        "lon": point_lon,
        "distance_km": round(dist_km, 2),
        "variable": nc_var_name,
        "units": var_units,
        "fill_count": fill_count,
    }


# ---------------------------------------------------------------------------
# Time series cleanup — dedup, sort, gap detection, contiguous block
# ---------------------------------------------------------------------------


def clean_timeseries(
    times: list[str],
    values: list[float],
    max_gap_hours: float = 6.0,
    min_points: int = 3,
) -> dict[str, list[str] | list[float] | int | bool]:
    """Sort, deduplicate, and extract the longest contiguous block.

    OFS FMRC data can contain duplicate timestamps, out-of-order entries,
    and large time gaps from stitching multiple forecast runs. This function
    cleans the series into a usable contiguous block.

    Args:
        times: Time strings in 'YYYY-MM-DD HH:MM' format.
        values: Corresponding values.
        max_gap_hours: Maximum gap (hours) before splitting into segments.
        min_points: Minimum points for a valid segment.

    Returns:
        Dict with:
            - 'times': cleaned time strings
            - 'values': cleaned values
            - 'n_original': original point count
            - 'n_duplicates_removed': duplicate timestamps removed
            - 'n_segments': number of contiguous segments found
            - 'is_sparse': True if result has fewer than min_points
    """
    if not times or not values:
        return {
            "times": [],
            "values": [],
            "n_original": 0,
            "n_duplicates_removed": 0,
            "n_parse_failures": 0,
            "n_segments": 0,
            "is_sparse": True,
        }

    # Parse times
    n_input = len(times)
    parsed: list[tuple[datetime, float]] = []
    for t_str, v in zip(times, values):
        try:
            dt = datetime.strptime(t_str[:16], "%Y-%m-%d %H:%M")
            parsed.append((dt, v))
        except ValueError:
            continue

    n_parse_failures = n_input - len(parsed)

    # Sort by time
    parsed.sort(key=lambda x: x[0])

    # Deduplicate — keep last value for each timestamp (stable sort preserves
    # original order among entries with the same timestamp)
    seen: dict[datetime, float] = {}
    for dt, v in parsed:
        seen[dt] = v
    deduped = sorted(seen.items(), key=lambda x: x[0])
    n_duplicates = len(parsed) - len(deduped)

    if len(deduped) < min_points:
        return {
            "times": [dt.strftime("%Y-%m-%d %H:%M") for dt, _ in deduped],
            "values": [v for _, v in deduped],
            "n_original": n_input,
            "n_duplicates_removed": n_duplicates,
            "n_parse_failures": n_parse_failures,
            "n_segments": 1 if deduped else 0,
            "is_sparse": True,
        }

    # Split on gaps > max_gap_hours
    gap_threshold = timedelta(hours=max_gap_hours)
    segments: list[list[tuple[datetime, float]]] = [[deduped[0]]]
    for i in range(1, len(deduped)):
        if deduped[i][0] - deduped[i - 1][0] > gap_threshold:
            segments.append([])
        segments[-1].append(deduped[i])

    # Keep longest contiguous segment
    best = max(segments, key=len)

    result_times = [dt.strftime("%Y-%m-%d %H:%M") for dt, _ in best]
    result_values = [v for _, v in best]

    return {
        "times": result_times,
        "values": result_values,
        "n_original": n_input,
        "n_duplicates_removed": n_duplicates,
        "n_parse_failures": n_parse_failures,
        "n_segments": len(segments),
        "is_sparse": len(best) < min_points,
    }


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------


def compute_validation_stats(
    forecast: list[float],
    observed: list[float],
) -> dict[str, float | int | None]:
    """Compute validation metrics for two aligned arrays.

    Returns:
        Dict with: bias, rmse, mae, peak_error, correlation, n.
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


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------


def align_timeseries(
    forecast_times: list[str],
    forecast_values: list[float],
    observed_times: list[str],
    observed_values: list[float],
    tolerance_minutes: int = 10,
) -> tuple[list[str], list[float], list[float]]:
    """Align two time series to common timestamps within tolerance.

    Returns:
        (common_times, aligned_forecast, aligned_observed)
    """

    def parse_dt(s: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%m/%d/%Y %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {s!r}")

    tol = tolerance_minutes * 60

    obs_dts = []
    for t in observed_times:
        try:
            obs_dts.append(parse_dt(t))
        except ValueError:
            obs_dts.append(None)

    obs_timestamps = [dt.timestamp() if dt else None for dt in obs_dts]

    common_times: list[str] = []
    aligned_forecast: list[float] = []
    aligned_observed: list[float] = []

    for f_t_str, f_v in zip(forecast_times, forecast_values):
        try:
            f_dt = parse_dt(f_t_str)
        except ValueError:
            continue
        f_ts = f_dt.timestamp()

        best_i = None
        best_diff = float("inf")
        for i, o_ts in enumerate(obs_timestamps):
            if o_ts is None:
                continue
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
    units: str = "m",
    source: str = "NOAA OFS",
) -> str:
    """Format a time series as a markdown table with summary statistics."""
    import numpy as np

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

    vals = [v for v in values if v is not None]
    if vals:
        v_min = min(vals)
        v_max = max(vals)
        v_mean = float(np.mean(vals))
        lines.append(
            f"**Min**: {v_min:.3f} {units} | **Max**: {v_max:.3f} {units} | "
            f"**Mean**: {v_mean:.3f} {units} | **Total points**: {total}"
        )
        lines.append("")

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

    lines.append(f"| Time (UTC) | Value ({units}) |")
    lines.append("| --- | --- |")
    for t, v in zip(times_show, values_show):
        lines.append(f"| {t} | {v:.3f} |")

    lines.append("")
    lines.append(f"*Data from {source}.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def handle_ofs_error(e: Exception, model: str = "") -> str:
    """Format an exception into a user-friendly OFS error message."""
    import httpx

    model_label = f" ({model.upper()})" if model else ""

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"OFS file not found{model_label} (HTTP 404). "
                "The cycle may not be available yet. "
                "Use ofs_list_cycles to check available forecast cycles."
            )
        if status == 403:
            return (
                f"S3 access denied{model_label} (HTTP 403). "
                "The data may have been archived. Try a more recent date."
            )
        return (
            f"HTTP {status} error{model_label}. "
            "The OFS data service may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"Download timed out{model_label}. "
            "OFS NetCDF files can be large. Try again or use a different cycle."
        )

    if isinstance(e, ValueError):
        return str(e)

    if isinstance(e, RuntimeError):
        return str(e)

    if "NetCDF" in type(e).__name__ or "netCDF" in str(e).lower():
        return (
            f"Error reading OFS NetCDF file{model_label}. "
            "The file may be corrupted or the format may have changed. "
            "Try a different cycle using ofs_list_cycles."
        )

    return f"Unexpected error{model_label}: {type(e).__name__}: {e}"


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
