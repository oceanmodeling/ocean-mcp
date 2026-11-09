"""Parsers, formatters, and helpers for WW3 MCP server."""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    NDBC_HISTORICAL_MISSING_CODES,
    NDBC_HISTORICAL_RENAMES,
    NDBC_STDMET_UNITS,
)


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
# Longitude normalization (user -180..180 <-> GRIB 0..360)
# ---------------------------------------------------------------------------


def normalize_lon(lon: float) -> float:
    """Convert longitude from -180..180 to 0..360 convention."""
    return lon % 360.0


def denormalize_lon(lon: float) -> float:
    """Convert longitude from 0..360 to -180..180 convention."""
    return lon if lon <= 180.0 else lon - 360.0


# ---------------------------------------------------------------------------
# NDBC realtime text parser
# ---------------------------------------------------------------------------


def parse_ndbc_realtime(text: str) -> list[dict[str, Any]]:
    """Parse NDBC realtime2 standard meteorological text into records.

    Handles the fixed-width format with two header rows (column names + units).
    Values of 'MM' (missing) are converted to None.

    Args:
        text: Raw text from NDBC realtime2 .txt file.

    Returns:
        List of dicts with parsed values.
    """
    lines = text.strip().split("\n")
    if len(lines) < 3:
        return []

    # First line is column names (starts with #)
    header_line = lines[0].lstrip("#").strip()
    columns = header_line.split()

    # Second line is units (starts with #), skip it
    # Data starts at line index 2
    records = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < len(columns):
            continue

        record: dict[str, Any] = {}
        for i, col in enumerate(columns):
            val = parts[i] if i < len(parts) else "MM"
            if val == "MM":
                record[col] = None
            else:
                try:
                    record[col] = float(val) if "." in val else int(val)
                except ValueError:
                    record[col] = val

        # Build ISO timestamp from date components
        try:
            yr = record.get("YY", record.get("#YY", 0))
            mo = record.get("MM", 1)
            dd = record.get("DD", 1)
            hh = record.get("hh", 0)
            mm = record.get("mm", 0)
            if yr and mo and dd:
                record["timestamp"] = (
                    f"{int(yr):04d}-{int(mo):02d}-{int(dd):02d} {int(hh):02d}:{int(mm):02d}"
                )
        except (ValueError, TypeError):
            record["timestamp"] = ""

        records.append(record)

    return records


# ---------------------------------------------------------------------------
# NDBC historical (annual) text parser
# ---------------------------------------------------------------------------

# Date/time columns: never checked against missing-value codes.
_DATE_COLUMNS = frozenset({"YY", "MM", "DD", "hh", "mm"})


def parse_ndbc_historical(text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse an NDBC historical annual standard meteorological file.

    Unlike realtime2 files, historical files mark missing values with a
    column-specific 9-filled code (see NDBC_HISTORICAL_MISSING_CODES). Each
    field's text is compared with its column's code before any number
    conversion; a match becomes None and is counted. "MM" is also treated as
    missing. Other fields are converted to numbers as in parse_ndbc_realtime.

    Handles the header variants seen in NDBC's files: one header line
    (``YY``/``YYYY``, ``WD``, ``BAR``, with or without a minute column) or a
    ``#YY`` header followed by a ``#yr`` units line. Columns are renamed to
    the current names (NDBC_HISTORICAL_RENAMES) and two-digit years are
    expanded to 19YY.

    Args:
        text: Raw text of the historical file.

    Returns:
        (records, info). Each record maps column name to value (None when
        missing) plus ``timestamp`` ("YYYY-MM-DD HH:MM", UTC). ``info`` holds
        the detected format, the units, the number of data rows, malformed
        rows skipped, and missing-value counts per column.

    Raises:
        ValueError: if the header lacks the date columns or WVHT, so the file
            is not in a format this parser understands.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header: list[str] = []
    for ln in lines:
        if ln.split()[0].isdigit():
            break
        header.append(ln)
    if not header:
        raise ValueError(
            "Unrecognised NDBC historical file: no header line before the data."
        )

    raw_columns = header[0].lstrip("#").split()
    columns = [NDBC_HISTORICAL_RENAMES.get(c, c) for c in raw_columns]
    required = {"YY", "MM", "DD", "hh", "WVHT"}
    if not required.issubset(columns):
        raise ValueError(
            "Unrecognised NDBC historical file format: header "
            f"{' '.join(raw_columns)!r} lacks {sorted(required - set(columns))}."
        )

    units: dict[str, str] = {}
    units_source = "NDBC units line of current historical files (file has none)"
    if len(header) > 1:
        unit_tokens = header[1].lstrip("#").split()
        if len(unit_tokens) == len(columns):
            units = {
                c: u for c, u in zip(columns, unit_tokens) if c not in _DATE_COLUMNS
            }
            units_source = "the file's units line"
    if not units:
        units = {c: NDBC_STDMET_UNITS[c] for c in columns if c in NDBC_STDMET_UNITS}

    missing = {c: 0 for c in columns if c not in _DATE_COLUMNS}
    malformed = 0
    two_digit_year = False
    records: list[dict[str, Any]] = []
    for ln in lines[len(header) :]:
        parts = ln.split()
        if len(parts) != len(columns):
            malformed += 1
            continue
        record: dict[str, Any] = {}
        row_missing: list[str] = []
        for col, tok in zip(columns, parts):
            if col not in _DATE_COLUMNS and (
                tok == "MM" or NDBC_HISTORICAL_MISSING_CODES.get(col) == tok
            ):
                record[col] = None
                row_missing.append(col)
                continue
            try:
                record[col] = float(tok) if "." in tok else int(tok)
            except ValueError:
                record[col] = tok
        yr = record["YY"]
        if isinstance(yr, int) and yr < 100:
            two_digit_year = True
            yr = record["YY"] = 1900 + yr
        try:
            record["timestamp"] = (
                f"{int(yr):04d}-{int(record['MM']):02d}-{int(record['DD']):02d} "
                f"{int(record['hh']):02d}:{int(record.get('mm', 0)):02d}"
            )
        except (TypeError, ValueError):
            malformed += 1
            continue
        for col in row_missing:  # count only rows that are kept
            missing[col] += 1
        records.append(record)

    info = {
        "header_lines": len(header),
        "columns": columns,
        "renamed": {r: c for r, c in zip(raw_columns, columns) if r != c},
        "two_digit_year": two_digit_year,
        "minute_column": "mm" in columns,
        "units": units,
        "units_source": units_source,
        "data_rows": len(records),
        "malformed_rows_skipped": malformed,
        "missing_counts": missing,
    }
    return records, info


def summarize_values(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Summary statistics of one column over every record with a value.

    Returns the count of valid values, min, max, the time of the first
    maximum, how many rows share the maximum, and the mean (3 decimals).
    Statistics are None when no record has a value.
    """
    vals = [
        (r[key], r.get("timestamp"))
        for r in records
        if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)
    ]
    if not vals:
        return {
            "valid": 0,
            "min": None,
            "max": None,
            "max_time": None,
            "max_count": 0,
            "mean": None,
        }
    numbers = [v for v, _ in vals]
    vmax = max(numbers)
    return {
        "valid": len(numbers),
        "min": min(numbers),
        "max": vmax,
        "max_time": next(t for v, t in vals if v == vmax),
        "max_count": numbers.count(vmax),
        "mean": round(sum(numbers) / len(numbers), 3),
    }


# ---------------------------------------------------------------------------
# NDBC active stations XML parser
# ---------------------------------------------------------------------------


def parse_ndbc_stations_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse NDBC activestations.xml into station dicts.

    Args:
        xml_text: Raw XML from NDBC active stations endpoint.

    Returns:
        List of station dicts with id, lat, lon, name, type, etc.
    """
    stations = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for station in root.iter("station"):
        attrs = station.attrib
        station_id = attrs.get("id", "")
        if not station_id:
            continue

        lat = attrs.get("lat", "")
        lon = attrs.get("lon", "")
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            continue

        stations.append(
            {
                "id": station_id,
                "lat": lat_f,
                "lon": lon_f,
                "name": attrs.get("name", ""),
                "type": attrs.get("type", ""),
                "owner": attrs.get("owner", ""),
                "pgm": attrs.get("pgm", ""),
                "met": attrs.get("met", ""),
                "currents": attrs.get("currents", ""),
            }
        )

    return stations


# ---------------------------------------------------------------------------
# GRIB2 point extraction via cfgrib/xarray
# ---------------------------------------------------------------------------


def extract_grib_point(
    grib_path: str | Path,
    lat: float,
    lon: float,
) -> dict[str, Any]:
    """Extract all wave variables at the nearest point from a GRIB2 file.

    Uses xarray with the cfgrib engine. The longitude should be in 0-360
    convention to match GFS-Wave output.

    Args:
        grib_path: Path to the GRIB2 file.
        lat: Target latitude.
        lon: Target longitude (0-360 convention).

    Returns:
        Dict with variable names as keys and values as floats, plus
        'latitude', 'longitude', 'valid_time' metadata.
    """
    import xarray as xr

    ds = xr.open_dataset(str(grib_path), engine="cfgrib")

    # Select nearest point
    point = ds.sel(latitude=lat, longitude=lon, method="nearest")

    result: dict[str, Any] = {}

    # Extract coordinates
    if "latitude" in point.coords:
        result["latitude"] = float(point.coords["latitude"].values)
    if "longitude" in point.coords:
        result["longitude"] = float(point.coords["longitude"].values)
    if "valid_time" in point.coords:
        vt = point.coords["valid_time"].values
        result["valid_time"] = str(vt)[:16].replace("T", " ")
    elif "time" in point.coords:
        vt = point.coords["time"].values
        result["valid_time"] = str(vt)[:16].replace("T", " ")

    # Extract data variables
    for var_name in ds.data_vars:
        try:
            val = float(point[var_name].values)
            if not math.isnan(val):
                result[str(var_name)] = round(val, 4)
        except (ValueError, TypeError):
            pass

    ds.close()
    return result


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
    tolerance_minutes: int = 30,
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


def format_wave_observation_table(
    records: list[dict[str, Any]],
    station_id: str = "",
    max_rows: int = 100,
    summary_lines: list[str] | None = None,
    footer: str | None = None,
) -> str:
    """Format NDBC buoy observations as a markdown table.

    By default the wave-height summary is computed from ``records``. Pass
    ``summary_lines`` to print a summary computed elsewhere (for example over
    a whole file of which ``records`` is only a part), and ``footer`` for a
    line placed directly under the table.
    """
    lines: list[str] = []

    if station_id:
        lines.append(f"## NDBC Buoy {station_id} — Wave Observations")
        lines.append("")

    if not records:
        lines.append("*No observation data available.*")
        return "\n".join(lines)

    # Collect wave height values for stats
    wvht_vals = [r["WVHT"] for r in records if r.get("WVHT") is not None]
    if summary_lines is not None:
        lines.extend(summary_lines)
        lines.append("")
    elif wvht_vals:
        lines.append(
            f"**Wave Height**: min {min(wvht_vals):.1f} m, "
            f"max {max(wvht_vals):.1f} m, "
            f"mean {sum(wvht_vals) / len(wvht_vals):.1f} m | "
            f"**Records**: {len(records)}"
        )
        lines.append("")

    # Subsample if too many rows
    if len(records) > max_rows:
        step = max(1, len(records) // max_rows)
        show = records[::step]
        lines.append(f"*Showing every {step}th of {len(records)} records*")
        lines.append("")
    else:
        show = records

    lines.append(
        "| Time (UTC) | WVHT (m) | DPD (s) | APD (s) | MWD (deg) | WSPD (m/s) | WDIR (deg) |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")

    for r in show:
        ts = r.get("timestamp", "")
        wvht = f"{r['WVHT']:.1f}" if r.get("WVHT") is not None else "—"
        dpd = f"{r['DPD']:.1f}" if r.get("DPD") is not None else "—"
        apd = f"{r['APD']:.1f}" if r.get("APD") is not None else "—"
        mwd = f"{int(r['MWD'])}" if r.get("MWD") is not None else "—"
        wspd = f"{r['WSPD']:.1f}" if r.get("WSPD") is not None else "—"
        wdir = f"{int(r['WDIR'])}" if r.get("WDIR") is not None else "—"
        lines.append(f"| {ts} | {wvht} | {dpd} | {apd} | {mwd} | {wspd} | {wdir} |")

    lines.append("")
    if footer:
        lines.append(footer)
    lines.append("*Data from NOAA NDBC.*")
    return "\n".join(lines)


def format_forecast_table(
    times: list[str],
    values: list[dict[str, Any]],
    title: str = "",
    metadata_lines: list[str] | None = None,
    max_rows: int = 100,
) -> str:
    """Format wave forecast time series as a markdown table."""
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    total = len(times)
    if total == 0:
        lines.append("*No forecast data available.*")
        return "\n".join(lines)

    # Determine which variables are present
    var_keys = set()
    for v in values:
        var_keys.update(
            k for k in v if k not in ("latitude", "longitude", "valid_time")
        )
    var_keys_sorted = sorted(var_keys)

    if not var_keys_sorted:
        lines.append("*No wave variables found in forecast data.*")
        return "\n".join(lines)

    # Summary stats for wave height if present
    htsgw_vals = [v.get("HTSGW") or v.get("swh") for v in values]
    htsgw_clean = [x for x in htsgw_vals if x is not None]
    if htsgw_clean:
        lines.append(
            f"**Sig. Wave Height**: min {min(htsgw_clean):.2f} m, "
            f"max {max(htsgw_clean):.2f} m, "
            f"mean {sum(htsgw_clean) / len(htsgw_clean):.2f} m | "
            f"**Total points**: {total}"
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

    # Build table header
    header_cols = ["Time (UTC)"] + var_keys_sorted
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(header_cols)) + " |")

    for t, v in zip(times_show, values_show):
        row = [t]
        for k in var_keys_sorted:
            val = v.get(k)
            if val is not None:
                row.append(f"{val:.2f}")
            else:
                row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("*Data from NOAA GFS-Wave via NOMADS.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def handle_ww3_error(e: Exception, context: str = "") -> str:
    """Format an exception into a user-friendly WW3 error message."""
    import httpx

    label = f" ({context})" if context else ""

    # cfgrib/ecCodes is a native dependency (not pip-installable everywhere);
    # surface an actionable setup fix instead of the opaque cfgrib/ecCodes error.
    if "eccodes" in str(e).lower():
        return (
            f"GRIB support unavailable{label}: cfgrib could not load the ecCodes "
            "C library. WW3 forecast tools read GFS-Wave GRIB2 and need ecCodes "
            "installed — via conda (`conda install -c conda-forge eccodes cfgrib`) "
            "or your OS package manager (e.g. `apt-get install libeccodes0` then "
            "`pip install cfgrib`); see the ww3-mcp README. NDBC buoy tools "
            "(ww3_get_buoy_*) work without GRIB."
        )

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"Data not found{label} (HTTP 404). "
                "The forecast cycle may not be available yet. "
                "Use ww3_list_cycles to check available cycles."
            )
        if status == 403:
            return (
                f"Access denied{label} (HTTP 403). "
                "The data may have been archived. Try a more recent date."
            )
        return (
            f"HTTP {status} error{label}. "
            "The data service may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"Download timed out{label}. "
            "GRIB2 files can be large. Try a smaller region or fewer variables."
        )

    if isinstance(e, ValueError):
        return str(e)

    if isinstance(e, RuntimeError):
        return str(e)

    return f"Unexpected error{label}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Temp file cleanup
# ---------------------------------------------------------------------------


def cleanup_temp_file(filepath: Path | str | None) -> None:
    """Remove a temporary file. Safe to call with None."""
    if filepath is None:
        return
    try:
        os.unlink(str(filepath))
    except OSError:
        pass
