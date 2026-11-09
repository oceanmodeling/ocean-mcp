"""Tools: ww3_get_forecast_at_point, ww3_get_point_snapshot, ww3_get_regional_summary, ww3_compare_forecast_with_buoy."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import WW3Client
from ..models import VARIABLE_INFO, WAVE_GRIDS, WaveGrid
from ..server import mcp
from ..utils import (
    align_timeseries,
    cleanup_temp_file,
    compute_validation_stats,
    denormalize_lon,
    extract_grib_point,
    format_forecast_table,
    handle_ww3_error,
    normalize_lon,
    parse_ndbc_realtime,
    select_recent_window,
)


def _get_client(ctx: Context) -> WW3Client:
    return ctx.request_context.lifespan_context["ww3_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_get_forecast_at_point(
    ctx: Context,
    latitude: float,
    longitude: float,
    grid: WaveGrid = WaveGrid.GLOBAL_0P25,
    variables: list[str] | None = None,
    max_hours: int = 120,
    step_hours: int = 3,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get GFS-Wave forecast time series at a geographic point.

    Downloads subsetted GRIB2 data from NOMADS for multiple forecast hours
    and extracts wave variables at the nearest grid point. This is the
    primary tool for wave forecast data.

    Args:
        latitude: Target latitude in decimal degrees (-90 to 90).
        longitude: Target longitude in decimal degrees (-180 to 180).
        grid: Wave grid to use (default: 'global.0p25').
        variables: List of wave variables to retrieve (e.g., ['HTSGW', 'PERPW', 'DIRPW']).
                   Default: ['HTSGW', 'PERPW', 'DIRPW'].
        max_hours: Maximum forecast hours to retrieve (default 120, max 384).
        step_hours: Hours between forecast steps (default 3, min 1).
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_paths: list[Path] = []
    try:
        client = _get_client(ctx)
        max_hours = max(1, min(384, max_hours))
        step_hours = max(1, min(24, step_hours))

        if variables is None:
            variables = ["HTSGW", "PERPW", "DIRPW"]

        # Resolve latest cycle
        cycle_result = await client.resolve_latest_cycle(grid.value)
        if not cycle_result:
            return (
                "No GFS-Wave cycles found. Use ww3_list_cycles to check availability."
            )

        date_str, cycle_str = cycle_result
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        # Normalize longitude to 0-360 for GFS-Wave
        lon_360 = normalize_lon(longitude)

        # Build lat/lon range for subsetting (small box around point)
        lat_range = (latitude - 1.0, latitude + 1.0)
        lon_range = (lon_360 - 1.0, lon_360 + 1.0)

        # Download and extract for each forecast hour
        fhours = list(range(0, max_hours + 1, step_hours))
        times: list[str] = []
        values: list[dict[str, Any]] = []

        for fhour in fhours:
            tmp_path = None
            try:
                tmp_path = await client.download_grib_subset(
                    grid.value,
                    date_str,
                    cycle_str,
                    fhour,
                    variables=variables,
                    lat_range=lat_range,
                    lon_range=lon_range,
                )
                tmp_paths.append(tmp_path)

                point_data = await asyncio.to_thread(
                    extract_grib_point, tmp_path, latitude, lon_360
                )

                valid_time = point_data.pop("valid_time", f"f{fhour:03d}")
                point_data.pop("latitude", None)
                point_data.pop("longitude", None)

                times.append(valid_time)
                values.append(point_data)

            except Exception:
                # Skip failed forecast hours
                continue

        if not times:
            return (
                f"Could not retrieve any forecast data at "
                f"({latitude:.4f}°N, {longitude:.4f}°E) from {grid.value}. "
                "The NOMADS server may be temporarily unavailable."
            )

        if response_format == "json":
            return json.dumps(
                {
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "grid": grid.value,
                    "cycle": f"{date_fmt} {cycle_str}z",
                    "variables": variables,
                    "n_points": len(times),
                    "times": times,
                    "values": values,
                },
                indent=2,
            )

        grid_info = WAVE_GRIDS.get(grid.value, {})
        return format_forecast_table(
            times=times,
            values=values,
            title=f"GFS-Wave Forecast — {grid_info.get('name', grid.value)}",
            metadata_lines=[
                f"Location: ({latitude:.4f}°N, {longitude:.4f}°E)",
                f"Grid: {grid.value} ({grid_info.get('resolution', '')})",
                f"Cycle: {date_fmt} {cycle_str}z",
                f"Variables: {', '.join(variables)}",
            ],
        )

    except Exception as e:
        return handle_ww3_error(e, grid.value)
    finally:
        for p in tmp_paths:
            cleanup_temp_file(p)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_get_point_snapshot(
    ctx: Context,
    latitude: float,
    longitude: float,
    forecast_hour: int = 0,
    grid: WaveGrid = WaveGrid.GLOBAL_0P25,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get all wave variables at a single point and forecast time.

    Downloads a single GRIB2 file and extracts all available wave variables
    at the nearest grid point. Use this for a quick snapshot of current or
    near-future conditions.

    Args:
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        forecast_hour: Forecast hour (0=analysis, 6, 12, ..., max 384). Default: 0.
        grid: Wave grid to use (default: 'global.0p25').
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_path: Path | None = None
    try:
        client = _get_client(ctx)
        forecast_hour = max(0, min(384, forecast_hour))

        cycle_result = await client.resolve_latest_cycle(grid.value)
        if not cycle_result:
            return (
                "No GFS-Wave cycles found. Use ww3_list_cycles to check availability."
            )

        date_str, cycle_str = cycle_result
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        lon_360 = normalize_lon(longitude)

        lat_range = (latitude - 1.0, latitude + 1.0)
        lon_range = (lon_360 - 1.0, lon_360 + 1.0)

        tmp_path = await client.download_grib_subset(
            grid.value,
            date_str,
            cycle_str,
            forecast_hour,
            lat_range=lat_range,
            lon_range=lon_range,
        )

        point_data = await asyncio.to_thread(
            extract_grib_point, tmp_path, latitude, lon_360
        )

        actual_lat = point_data.pop("latitude", latitude)
        actual_lon = point_data.pop("longitude", lon_360)
        valid_time = point_data.pop("valid_time", "")

        if response_format == "json":
            return json.dumps(
                {
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "nearest_lat": actual_lat,
                    "nearest_lon": denormalize_lon(actual_lon),
                    "grid": grid.value,
                    "cycle": f"{date_fmt} {cycle_str}z",
                    "forecast_hour": forecast_hour,
                    "valid_time": valid_time,
                    "variables": point_data,
                },
                indent=2,
            )

        grid_info = WAVE_GRIDS.get(grid.value, {})
        lines = [
            "## Wave Conditions Snapshot",
            f"**Location**: ({latitude:.4f}°N, {longitude:.4f}°E)",
            f"**Grid**: {grid.value} ({grid_info.get('resolution', '')})",
            f"**Cycle**: {date_fmt} {cycle_str}z | **Forecast hour**: f{forecast_hour:03d}",
            f"**Valid time**: {valid_time}",
            "",
            "| Variable | Value | Description |",
            "| --- | --- | --- |",
        ]

        for var_name, val in sorted(point_data.items()):
            var_info = VARIABLE_INFO.get(var_name.upper(), {})
            desc = var_info.get("name", var_name)
            units = var_info.get("units", "")
            lines.append(f"| `{var_name}` | {val:.2f} {units} | {desc} |")

        lines += [
            "",
            f"*Data from GFS-Wave ({grid_info.get('name', grid.value)}) via NOMADS.*",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ww3_error(e, grid.value)
    finally:
        cleanup_temp_file(tmp_path)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_get_regional_summary(
    ctx: Context,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    forecast_hour: int = 0,
    grid: WaveGrid = WaveGrid.GLOBAL_0P25,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get spatial statistics for wave variables over a bounding box.

    Downloads a single GRIB2 file subsetted to the bounding box and computes
    min, max, mean, and standard deviation for each wave variable.

    Args:
        lat_min: Southern latitude bound.
        lat_max: Northern latitude bound.
        lon_min: Western longitude bound (-180 to 180).
        lon_max: Eastern longitude bound (-180 to 180).
        forecast_hour: Forecast hour (default 0).
        grid: Wave grid to use (default: 'global.0p25').
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_paths: list[Path] = []
    try:
        import numpy as np

        client = _get_client(ctx)
        forecast_hour = max(0, min(384, forecast_hour))

        cycle_result = await client.resolve_latest_cycle(grid.value)
        if not cycle_result:
            return (
                "No GFS-Wave cycles found. Use ww3_list_cycles to check availability."
            )

        date_str, cycle_str = cycle_result
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        lon_min_360 = normalize_lon(lon_min)
        lon_max_360 = normalize_lon(lon_max)

        # A box whose west edge normalizes east of its east edge wraps the
        # 0°/360° seam (Greenwich or the dateline). NOMADS grib-filter cannot
        # express a seam-crossing subregion in one request — it returns an
        # empty body (verified) — so fetch the two pieces [west, 360] and
        # [0, east] and combine. W→E bounds make the split unambiguous, and
        # for a spatial summary the union of valid grid points is exact.
        if lon_min_360 <= lon_max_360:
            lon_ranges = [(lon_min_360, lon_max_360)]
        else:
            lon_ranges = [(lon_min_360, 360.0), (0.0, lon_max_360)]

        import xarray as xr

        combined: dict[str, list] = {}
        for lon_lo, lon_hi in lon_ranges:
            tmp = await client.download_grib_subset(
                grid.value,
                date_str,
                cycle_str,
                forecast_hour,
                lat_range=(lat_min, lat_max),
                lon_range=(lon_lo, lon_hi),
            )
            tmp_paths.append(tmp)
            if tmp.stat().st_size == 0:
                continue  # NOMADS returned an empty slice for this piece
            ds = await asyncio.to_thread(
                lambda p=tmp: xr.open_dataset(str(p), engine="cfgrib")
            )
            try:
                for var_name in ds.data_vars:
                    valid = ds[var_name].values.flatten()
                    valid = valid[~np.isnan(valid)]
                    if len(valid):
                        combined.setdefault(str(var_name), []).append(valid)
            finally:
                ds.close()

        stats: dict[str, dict[str, float]] = {}
        for var_name, arrays in combined.items():
            allv = np.concatenate(arrays)
            stats[var_name] = {
                "min": round(float(np.min(allv)), 4),
                "max": round(float(np.max(allv)), 4),
                "mean": round(float(np.mean(allv)), 4),
                "std": round(float(np.std(allv)), 4),
                "n_points": int(len(allv)),
            }

        if response_format == "json":
            return json.dumps(
                {
                    "bounding_box": {
                        "lat_min": lat_min,
                        "lat_max": lat_max,
                        "lon_min": lon_min,
                        "lon_max": lon_max,
                    },
                    "grid": grid.value,
                    "cycle": f"{date_fmt} {cycle_str}z",
                    "forecast_hour": forecast_hour,
                    "statistics": stats,
                },
                indent=2,
            )

        grid_info = WAVE_GRIDS.get(grid.value, {})
        lines = [
            "## Regional Wave Summary",
            f"**Bounding box**: {lat_min}–{lat_max}°N, {lon_min}–{lon_max}°E",
            f"**Grid**: {grid.value} ({grid_info.get('resolution', '')})",
            f"**Cycle**: {date_fmt} {cycle_str}z | **Forecast hour**: f{forecast_hour:03d}",
            "",
            "| Variable | Min | Max | Mean | Std Dev | Points |",
            "| --- | --- | --- | --- | --- | --- |",
        ]

        for var_name, s in sorted(stats.items()):
            var_info = VARIABLE_INFO.get(var_name.upper(), {})
            units = var_info.get("units", "")
            lines.append(
                f"| `{var_name}` | {s['min']:.2f} {units} | {s['max']:.2f} {units} "
                f"| {s['mean']:.2f} {units} | {s['std']:.2f} | {s['n_points']} |"
            )

        lines += ["", "*Data from GFS-Wave via NOMADS.*"]
        return "\n".join(lines)

    except Exception as e:
        return handle_ww3_error(e, grid.value)
    finally:
        for p in tmp_paths:
            cleanup_temp_file(p)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_compare_forecast_with_buoy(
    ctx: Context,
    station_id: str,
    buoy_lat: float,
    buoy_lon: float,
    grid: WaveGrid = WaveGrid.GLOBAL_0P25,
    hours_to_compare: int = 24,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Compare GFS-Wave forecast with NDBC buoy observations.

    Fetches both the model forecast and buoy observations for wave height,
    aligns the time series, and computes validation statistics (bias, RMSE,
    MAE, peak error, correlation).

    Args:
        station_id: NDBC buoy station ID (e.g., '41025', '46042').
        buoy_lat: Buoy latitude in decimal degrees.
        buoy_lon: Buoy longitude in decimal degrees.
        grid: Wave grid to use (default: 'global.0p25').
        hours_to_compare: Hours of comparison (default 24, max 120). Sets
            both the forecast hours fetched (0 to hours_to_compare, every 3 h)
            and the observation window: the buoy rows within this many hours
            before its latest row, selected by timestamp at whatever interval
            the station reports.
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_paths: list[Path] = []
    try:
        client = _get_client(ctx)
        hours_to_compare = max(1, min(120, hours_to_compare))

        # Step 1: Fetch buoy observations
        raw_text = await client.fetch_ndbc_realtime(station_id)
        obs_records = parse_ndbc_realtime(raw_text)

        if not obs_records:
            return f"No observation data available for NDBC station '{station_id}'."

        # Observation window by timestamp (rows come every 10 min at some
        # stations, 30 or 60 at others); then keep rows with a wave height.
        obs_window_rows, obs_window = select_recent_window(
            obs_records, hours_to_compare
        )
        obs_times = []
        obs_values = []
        for r in obs_window_rows:
            ts = r.get("timestamp", "")
            wvht = r.get("WVHT")
            if ts and wvht is not None:
                obs_times.append(ts)
                obs_values.append(float(wvht))

        if not obs_values:
            return f"No wave height data available from buoy {station_id}."

        # Step 2: Fetch model forecast
        cycle_result = await client.resolve_latest_cycle(grid.value)
        if not cycle_result:
            return "No GFS-Wave cycles found."

        date_str, cycle_str = cycle_result
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        lon_360 = normalize_lon(buoy_lon)

        lat_range = (buoy_lat - 1.0, buoy_lat + 1.0)
        lon_range = (lon_360 - 1.0, lon_360 + 1.0)

        fcst_times = []
        fcst_values = []

        for fhour in range(0, hours_to_compare + 1, 3):
            tmp_path = None
            try:
                tmp_path = await client.download_grib_subset(
                    grid.value,
                    date_str,
                    cycle_str,
                    fhour,
                    variables=["HTSGW"],
                    lat_range=lat_range,
                    lon_range=lon_range,
                )
                tmp_paths.append(tmp_path)

                point_data = await asyncio.to_thread(
                    extract_grib_point, tmp_path, buoy_lat, lon_360
                )

                valid_time = point_data.get("valid_time", "")
                htsgw = None
                for key in ("HTSGW", "swh"):
                    if key in point_data:
                        htsgw = point_data[key]
                        break

                if valid_time and htsgw is not None:
                    fcst_times.append(valid_time)
                    fcst_values.append(float(htsgw))
            except Exception:
                continue

        if not fcst_values:
            return f"Could not retrieve forecast data near buoy {station_id}."

        # Step 3: Align and compute stats
        common_times, aligned_fcst, aligned_obs = align_timeseries(
            fcst_times,
            fcst_values,
            obs_times,
            obs_values,
        )

        stats = compute_validation_stats(aligned_fcst, aligned_obs)
        obs_window["rows_with_wvht"] = len(obs_values)

        if response_format == "json":
            return json.dumps(
                {
                    "station_id": station_id,
                    "buoy_lat": buoy_lat,
                    "buoy_lon": buoy_lon,
                    "grid": grid.value,
                    "cycle": f"{date_fmt} {cycle_str}z",
                    "observation_window": obs_window,
                    "stats": stats,
                    "comparison_times": common_times,
                    "forecast_values": aligned_fcst,
                    "observed_values": aligned_obs,
                },
                indent=2,
            )

        def fmt_stat(v: float | None, suffix: str = " m") -> str:
            if v is None:
                return "N/A"
            return f"{v:+.3f}{suffix}" if suffix == " m" else f"{v:.4f}"

        grid_info = WAVE_GRIDS.get(grid.value, {})
        lines = [
            f"## GFS-Wave vs NDBC Buoy {station_id}",
            f"**Buoy location**: ({buoy_lat:.4f}°N, {buoy_lon:.4f}°E)",
            f"**Grid**: {grid.value} ({grid_info.get('resolution', '')})",
            f"**Cycle**: {date_fmt} {cycle_str}z",
            "**Variable**: Significant Wave Height (HTSGW vs WVHT)",
            f"**Observations**: {len(obs_values)} rows with WVHT among the "
            f"{obs_window['rows_in_window']} buoy rows from "
            f"{obs_window['window_start']} to {obs_window['latest_time']} UTC "
            f"({hours_to_compare} h before the latest row)",
            "",
        ]

        if stats["n"] == 0:
            lines.append(
                "*No overlapping data points found. "
                "Model forecast and buoy observations may not overlap in time.*"
            )
            return "\n".join(lines)

        lines += [
            "### Validation Statistics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Bias (mean error) | {fmt_stat(stats['bias'])} |",
            f"| RMSE | {fmt_stat(stats['rmse'])} |",
            f"| MAE | {fmt_stat(stats['mae'])} |",
            f"| Peak Error | {fmt_stat(stats['peak_error'])} |",
            f"| Correlation (R) | {fmt_stat(stats['correlation'], '')} |",
            f"| Comparison Points | {stats['n']} |",
            "",
        ]

        # Comparison table
        lines += [
            "### Time Series Comparison",
            "",
            "| Time (UTC) | Forecast (m) | Observed (m) | Error (m) |",
            "| --- | --- | --- | --- |",
        ]
        for t, f_v, o_v in zip(common_times, aligned_fcst, aligned_obs):
            err = f_v - o_v
            lines.append(f"| {t} | {f_v:.2f} | {o_v:.2f} | {err:+.2f} |")

        lines += [
            "",
            f"*Model: GFS-Wave ({grid_info.get('name', grid.value)}) via NOMADS. "
            f"Observations: NDBC buoy {station_id}.*",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ww3_error(e, f"buoy {station_id}")
    finally:
        for p in tmp_paths:
            cleanup_temp_file(p)
