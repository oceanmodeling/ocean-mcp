"""Tools: rtofs_get_surface_forecast, rtofs_get_profile_forecast, rtofs_get_area_forecast."""

from __future__ import annotations

from typing import Literal
import asyncio
import json
import math
from datetime import datetime, timezone

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import RTOFSClient, handle_rtofs_error
from ..models import (
    DATASETS,
    PROFILE_VARIABLES,
    SURFACE_VARIABLES,
    THREDDS_BASE,
)
from ..server import mcp


def _get_client(ctx: Context) -> RTOFSClient:
    return ctx.request_context.lifespan_context["rtofs_client"]


def _cap_series_json(result: dict, max_points: int = 2000) -> str:
    """Serialize a forecast result to JSON, capping its `data` row series.

    A surface time-series can be a long `data` list; the json path would
    otherwise dump it whole. Keep the first ``max_points``, record
    n_rows/total_rows/truncated, and stamp retrieved_at (per CONVENTIONS.md).
    """
    rows = result.get("data", []) or []
    total = len(rows)
    truncated = total > max_points
    if truncated:
        rows = rows[:max_points]
        result["data"] = rows
    result["n_rows"] = len(rows)
    result["total_rows"] = total
    result["truncated"] = truncated
    result["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if truncated:
        result["hint"] = (
            f"Showing the first {len(rows)} of {total} points "
            "(truncated to limit response size)."
        )
    return json.dumps(result, indent=2)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def rtofs_get_surface_forecast(
    ctx: Context,
    latitude: float,
    longitude: float,
    variable: str = "sst",
    time_start: str | None = None,
    time_end: str | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get RTOFS surface time series at a point (SST, SSS, currents, or SSH).

    Queries HYCOM THREDDS NCSS for the nearest grid cell to the requested
    lat/lon (~8 km resolution). By default returns the window starting now:
    the next 72 h for the 3-hourly sst/sss/currents, the next 24 h for hourly
    ssh. Data spans ~10 days back and ~6 days ahead. HYCOM extracts about one
    time step per second, so keep custom windows to a few days.

    For 3D variables (SST, SSS, currents), surface values (depth=0) are returned.

    Args:
        latitude: Latitude in decimal degrees (-80 to 90).
        longitude: Longitude in decimal degrees (-180 to 180).
        variable: One of: sst, sss, u_current, v_current, ssh. Default: 'sst'.
        time_start: Start time in ISO format (e.g., '2026-03-01T00:00:00Z').
                    Default: now ('present'), or the default window before
                    time_end when only time_end is given.
        time_end: End time in ISO format. Default: the default window
                  (72 h, or 24 h for ssh) after time_start.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if not (-80 <= latitude <= 90):
            return "Latitude must be between -80 and 90 degrees."
        if not (-180 <= longitude <= 180):
            return "Longitude must be between -180 and 180 degrees."

        if variable not in SURFACE_VARIABLES:
            valid = ", ".join(SURFACE_VARIABLES.keys())
            return f"Unknown variable '{variable}'. Valid options: {valid}"

        var_info = SURFACE_VARIABLES[variable]
        dataset_key = var_info["dataset"]
        thredds_var = var_info["thredds_var"]
        unit = var_info["unit"]

        client = _get_client(ctx)

        # For 3D datasets, pin to surface (depth=0)
        ds_info = DATASETS[dataset_key]
        vert_coord = 0.0 if ds_info["dimensions"] == "3D" else None

        rows = await client.fetch_point_csv(
            dataset_key=dataset_key,
            variable=thredds_var,
            latitude=latitude,
            longitude=longitude,
            time_start=time_start,
            time_end=time_end,
            vert_coord=vert_coord,
        )

        if not rows:
            return (
                f"No data returned for ({latitude}, {longitude}). "
                "The point may be over land or outside the RTOFS domain."
            )

        # Filter NaN values
        valid_rows = [
            r
            for r in rows
            if r.get(thredds_var) is not None
            and not (isinstance(r[thredds_var], float) and math.isnan(r[thredds_var]))
        ]

        if not valid_rows:
            return (
                f"All values are NaN at ({latitude}, {longitude}). "
                "This point is likely over land."
            )

        if response_format == "json":
            return _cap_series_json(
                {
                    "variable": variable,
                    "thredds_variable": thredds_var,
                    "unit": unit,
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "actual_lat": valid_rows[0].get("latitude"),
                    "actual_lon": valid_rows[0].get("longitude"),
                    "data": [
                        {"time": r.get("time", ""), "value": r[thredds_var]}
                        for r in valid_rows
                    ],
                }
            )

        # Markdown table
        actual_lat = valid_rows[0].get("latitude", latitude)
        actual_lon = valid_rows[0].get("longitude", longitude)

        lines = [
            f"## RTOFS Surface Forecast — {var_info['long_name']}",
            f"**Location**: ({latitude}°, {longitude}°) → grid ({actual_lat}°, {actual_lon}°)",
            f"**Variable**: {thredds_var} ({unit})",
            f"**Points**: {len(valid_rows)}",
            "",
        ]

        # Subsample display
        max_display = 80
        if len(valid_rows) > max_display:
            step = max(1, len(valid_rows) // max_display)
            display = valid_rows[::step]
            lines.append(
                f"*Showing every {step}th point ({len(display)} of {len(valid_rows)})*"
            )
            lines.append("")
        else:
            display = valid_rows

        lines.append(f"| Time (UTC) | {var_info['long_name']} ({unit}) |")
        lines.append("| --- | --- |")
        for r in display:
            t = str(r.get("time", "")).replace("T", " ").rstrip("Z")[:19]
            v = r[thredds_var]
            lines.append(f"| {t} | {v:.4f} |")

        # Summary stats
        values = [r[thredds_var] for r in valid_rows]
        lines.append("")
        lines.append(
            f"**Min**: {min(values):.4f} {unit} | "
            f"**Max**: {max(values):.4f} {unit} | "
            f"**Mean**: {sum(values) / len(values):.4f} {unit}"
        )

        lines.append("")
        lines.append(f"*Source: HYCOM THREDDS ({THREDDS_BASE})*")
        return "\n".join(lines)

    except Exception as e:
        return handle_rtofs_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def rtofs_get_profile_forecast(
    ctx: Context,
    latitude: float,
    longitude: float,
    variable: str = "temperature",
    time: str | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get RTOFS 3D depth profile at a point (temperature, salinity, or currents vs depth).

    Queries HYCOM THREDDS NCSS for a vertical profile at the nearest grid cell.
    Returns values at all available depth levels for a single time step.

    Args:
        latitude: Latitude in decimal degrees (-80 to 90).
        longitude: Longitude in decimal degrees (-180 to 180).
        variable: One of: temperature, salinity, u, v. Default: 'temperature'.
        time: Time in ISO format (e.g., '2026-03-03T12:00:00Z'). Default: latest.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if not (-80 <= latitude <= 90):
            return "Latitude must be between -80 and 90 degrees."
        if not (-180 <= longitude <= 180):
            return "Longitude must be between -180 and 180 degrees."

        if variable not in PROFILE_VARIABLES:
            valid = ", ".join(PROFILE_VARIABLES.keys())
            return f"Unknown variable '{variable}'. Valid options: {valid}"

        var_info = PROFILE_VARIABLES[variable]
        dataset_key = var_info["dataset"]
        thredds_var = var_info["thredds_var"]
        unit = var_info["unit"]

        client = _get_client(ctx)

        # Use 'present' for latest time if not specified
        rows = await client.fetch_point_csv(
            dataset_key=dataset_key,
            variable=thredds_var,
            latitude=latitude,
            longitude=longitude,
            time=time or "present",
        )

        if not rows:
            return (
                f"No profile data at ({latitude}, {longitude}). "
                "The point may be over land or outside the model domain."
            )

        # Filter NaN values
        valid_rows = [
            r
            for r in rows
            if r.get(thredds_var) is not None
            and not (isinstance(r[thredds_var], float) and math.isnan(r[thredds_var]))
        ]

        if not valid_rows:
            return (
                f"All values are NaN at ({latitude}, {longitude}). "
                "This point is likely over land."
            )

        if response_format == "json":
            return json.dumps(
                {
                    "variable": variable,
                    "thredds_variable": thredds_var,
                    "unit": unit,
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "actual_lat": valid_rows[0].get("latitude"),
                    "actual_lon": valid_rows[0].get("longitude"),
                    "time": valid_rows[0].get("time"),
                    "n_levels": len(valid_rows),
                    "profile": [
                        {
                            "depth": r.get("vertCoord", r.get("depth", 0)),
                            "value": r[thredds_var],
                        }
                        for r in valid_rows
                    ],
                },
                indent=2,
            )

        actual_lat = valid_rows[0].get("latitude", latitude)
        actual_lon = valid_rows[0].get("longitude", longitude)
        time_str = str(valid_rows[0].get("time", "")).replace("T", " ").rstrip("Z")[:19]

        lines = [
            f"## RTOFS Depth Profile — {var_info['long_name']}",
            f"**Location**: ({latitude}°, {longitude}°) → grid ({actual_lat}°, {actual_lon}°)",
            f"**Time**: {time_str}",
            f"**Variable**: {thredds_var} ({unit})",
            f"**Levels**: {len(valid_rows)}",
            "",
            "| Depth (m) | Value |",
            "| --- | --- |",
        ]

        for r in valid_rows:
            depth = r.get("vertCoord", r.get("depth", 0))
            val = r[thredds_var]
            lines.append(f"| {depth:.1f} | {val:.4f} {unit} |")

        lines.append("")
        lines.append(f"*Source: HYCOM THREDDS ({THREDDS_BASE})*")
        return "\n".join(lines)

    except Exception as e:
        return handle_rtofs_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def rtofs_get_area_forecast(
    ctx: Context,
    lat_start: float,
    lat_end: float,
    lon_start: float,
    lon_end: float,
    variable: str = "sst",
    time: str | None = None,
    n_points: int = 10,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get RTOFS surface forecast for a grid of points in a bounding box.

    Queries multiple points in parallel using THREDDS NCSS. The number of
    points per axis is controlled by n_points (total queries = n_points^2).

    For 3D variables (SST, SSS, currents), surface values (depth=0) are returned.

    Args:
        lat_start: Southern latitude bound.
        lat_end: Northern latitude bound.
        lon_start: Western longitude bound.
        lon_end: Eastern longitude bound.
        variable: One of: sst, sss, u_current, v_current, ssh. Default: 'sst'.
        time: Time in ISO format. Default: latest ('present').
        n_points: Number of grid points per axis (2–15). Default: 10. Total = n^2.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if not (-80 <= lat_start <= 90 and -80 <= lat_end <= 90):
            return "Latitudes must be between -80 and 90 degrees."
        if not (-180 <= lon_start <= 180 and -180 <= lon_end <= 180):
            return "Longitudes must be between -180 and 180 degrees."
        if lat_start >= lat_end:
            return "lat_start must be less than lat_end."
        if lon_start >= lon_end:
            return "lon_start must be less than lon_end."

        if variable not in SURFACE_VARIABLES:
            valid = ", ".join(SURFACE_VARIABLES.keys())
            return f"Unknown variable '{variable}'. Valid options: {valid}"

        n_points = max(2, min(15, n_points))

        var_info = SURFACE_VARIABLES[variable]
        dataset_key = var_info["dataset"]
        thredds_var = var_info["thredds_var"]
        unit = var_info["unit"]

        ds_info = DATASETS[dataset_key]
        vert_coord = 0.0 if ds_info["dimensions"] == "3D" else None

        client = _get_client(ctx)

        # Generate grid of query points
        lat_step = (lat_end - lat_start) / max(1, n_points - 1)
        lon_step = (lon_end - lon_start) / max(1, n_points - 1)
        query_points = []
        for i in range(n_points):
            for j in range(n_points):
                lat = lat_start + i * lat_step
                lon = lon_start + j * lon_step
                query_points.append((round(lat, 4), round(lon, 4)))

        # Query all points in parallel
        async def fetch_one(lat: float, lon: float) -> dict | None:
            """Fetch a single point."""
            try:
                rows = await client.fetch_point_csv(
                    dataset_key=dataset_key,
                    variable=thredds_var,
                    latitude=lat,
                    longitude=lon,
                    time=time or "present",
                    vert_coord=vert_coord,
                )
                if rows and rows[0].get(thredds_var) is not None:
                    val = rows[0][thredds_var]
                    if isinstance(val, float) and math.isnan(val):
                        return None
                    return {
                        "lat": rows[0].get("latitude", lat),
                        "lon": rows[0].get("longitude", lon),
                        "time": rows[0].get("time", ""),
                        "value": val,
                    }
            except Exception:
                pass
            return None

        results = await asyncio.gather(
            *[fetch_one(lat, lon) for lat, lon in query_points]
        )

        valid_results = [r for r in results if r is not None]

        if not valid_results:
            return (
                f"No valid data in bounding box "
                f"({lat_start}, {lon_start}) to ({lat_end}, {lon_end}). "
                "The area may be entirely over land."
            )

        if response_format == "json":
            return json.dumps(
                {
                    "variable": variable,
                    "unit": unit,
                    "bbox": {
                        "lat_start": lat_start,
                        "lat_end": lat_end,
                        "lon_start": lon_start,
                        "lon_end": lon_end,
                    },
                    "n_points_per_axis": n_points,
                    "n_valid": len(valid_results),
                    "data": valid_results,
                },
                indent=2,
            )

        lines = [
            f"## RTOFS Area Forecast — {var_info['long_name']}",
            f"**Bounding box**: ({lat_start}°, {lon_start}°) to ({lat_end}°, {lon_end}°)",
            f"**Variable**: {thredds_var} ({unit})",
            f"**Grid**: {n_points} × {n_points} ({len(valid_results)} ocean points)",
            "",
            "| Lat | Lon | Value |",
            "| --- | --- | --- |",
        ]

        for r in valid_results:
            lines.append(
                f"| {r['lat']:.4f} | {r['lon']:.4f} | {r['value']:.4f} {unit} |"
            )

        # Summary
        values = [r["value"] for r in valid_results]
        lines.append("")
        lines.append(
            f"**Min**: {min(values):.4f} {unit} | "
            f"**Max**: {max(values):.4f} {unit} | "
            f"**Mean**: {sum(values) / len(values):.4f} {unit}"
        )
        lines.append("")
        lines.append(f"*Source: HYCOM THREDDS ({THREDDS_BASE})*")
        return "\n".join(lines)

    except Exception as e:
        return handle_rtofs_error(e)
