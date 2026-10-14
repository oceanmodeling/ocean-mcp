"""Tools: rtofs_get_transect, rtofs_compare_with_observations."""

from __future__ import annotations

from typing import Literal
import asyncio
import json
import math

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import RTOFSClient, handle_rtofs_error, haversine
from ..models import (
    DATASETS,
    PROFILE_VARIABLES,
    SURFACE_VARIABLES,
    THREDDS_BASE,
)
from ..server import mcp


_COMPARE_WINDOW_HOURS = 24


def _get_client(ctx: Context) -> RTOFSClient:
    return ctx.request_context.lifespan_context["rtofs_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def rtofs_get_transect(
    ctx: Context,
    lat_start: float,
    lon_start: float,
    lat_end: float,
    lon_end: float,
    variable: str = "temperature",
    time: str | None = None,
    n_points: int = 10,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get a vertical transect (cross-section) between two points from RTOFS 3D data.

    Queries depth profiles at multiple points along a line between start and end
    coordinates, then combines them into a depth vs. distance cross-section.
    Uses asyncio.gather for parallel THREDDS NCSS queries.

    Args:
        lat_start: Starting latitude.
        lon_start: Starting longitude.
        lat_end: Ending latitude.
        lon_end: Ending longitude.
        variable: One of: temperature, salinity, u, v. Default: 'temperature'.
        time: Time in ISO format. Default: latest ('present').
        n_points: Number of profile points along the transect (2–20). Default: 10.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if variable not in PROFILE_VARIABLES:
            valid = ", ".join(PROFILE_VARIABLES.keys())
            return f"Unknown variable '{variable}'. Valid options: {valid}"

        n_points = max(2, min(20, n_points))

        var_info = PROFILE_VARIABLES[variable]
        dataset_key = var_info["dataset"]
        thredds_var = var_info["thredds_var"]
        unit = var_info["unit"]

        client = _get_client(ctx)

        # Generate transect points
        points = []
        for i in range(n_points):
            frac = i / max(1, n_points - 1)
            lat = lat_start + frac * (lat_end - lat_start)
            lon = lon_start + frac * (lon_end - lon_start)
            points.append((round(lat, 4), round(lon, 4)))

        # Query each profile in parallel
        async def fetch_profile(lat: float, lon: float) -> dict:
            """Fetch a single depth profile."""
            try:
                rows = await client.fetch_point_csv(
                    dataset_key=dataset_key,
                    variable=thredds_var,
                    latitude=lat,
                    longitude=lon,
                    time=time or "present",
                )
                # Filter NaN
                valid = [
                    r
                    for r in rows
                    if r.get(thredds_var) is not None
                    and not (
                        isinstance(r[thredds_var], float) and math.isnan(r[thredds_var])
                    )
                ]
                return {
                    "lat": lat,
                    "lon": lon,
                    "actual_lat": valid[0].get("latitude", lat) if valid else lat,
                    "actual_lon": valid[0].get("longitude", lon) if valid else lon,
                    "levels": [
                        {
                            "depth": r.get("vertCoord", r.get("depth", 0)),
                            "value": r[thredds_var],
                        }
                        for r in valid
                    ],
                }
            except Exception:
                return {
                    "lat": lat,
                    "lon": lon,
                    "actual_lat": lat,
                    "actual_lon": lon,
                    "levels": [],
                }

        results = await asyncio.gather(
            *[fetch_profile(lat, lon) for lat, lon in points]
        )

        # Compute cumulative distances
        distances = [0.0]
        for i in range(1, len(points)):
            d = haversine(
                points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]
            )
            distances.append(distances[-1] + d)

        total_distance = distances[-1] if distances else 0

        if response_format == "json":
            transect = []
            for i, r in enumerate(results):
                transect.append(
                    {
                        "point_index": i,
                        "lat": r["lat"],
                        "lon": r["lon"],
                        "distance_km": round(distances[i], 2),
                        "n_levels": len(r["levels"]),
                        "profile": r["levels"],
                    }
                )
            return json.dumps(
                {
                    "variable": variable,
                    "unit": unit,
                    "start": {"lat": lat_start, "lon": lon_start},
                    "end": {"lat": lat_end, "lon": lon_end},
                    "total_distance_km": round(total_distance, 2),
                    "n_points": n_points,
                    "transect": transect,
                },
                indent=2,
            )

        lines = [
            f"## RTOFS Vertical Transect — {var_info['long_name']}",
            f"**From**: ({lat_start}°, {lon_start}°) **To**: ({lat_end}°, {lon_end}°)",
            f"**Total distance**: {total_distance:.1f} km",
            f"**Points**: {n_points} | **Variable**: {variable} ({unit})",
            "",
        ]

        for i, r in enumerate(results):
            if not r["levels"]:
                lines.append(
                    f"### Point {i + 1} ({r['lat']}°, {r['lon']}°) — "
                    f"{distances[i]:.1f} km: *No data (land?)*"
                )
                continue

            lines.append(
                f"### Point {i + 1} ({r['lat']}°, {r['lon']}°) — {distances[i]:.1f} km"
            )
            lines.append("| Depth (m) | Value |")
            lines.append("| --- | --- |")
            for level in r["levels"]:
                lines.append(f"| {level['depth']:.1f} | {level['value']:.4f} {unit} |")
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
async def rtofs_compare_with_observations(
    ctx: Context,
    latitude: float,
    longitude: float,
    variable: str = "sst",
    time: str | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Compare RTOFS values at the same location over the 24 hours before a time.

    Fetches the 24 h window ending at the reference time and reports the
    value at its start, middle and end, plus the change across the window.

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        variable: Surface variable to compare. Default: 'sst'.
        time: Reference time (end of the window) in ISO format.
              Default: now ('present').
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

        ds_info = DATASETS[dataset_key]
        vert_coord = 0.0 if ds_info["dimensions"] == "3D" else None

        client = _get_client(ctx)

        # Only the window ending at the reference time; the full series is
        # far too slow to extract for three values.
        rows = await client.fetch_point_csv(
            dataset_key=dataset_key,
            variable=thredds_var,
            latitude=latitude,
            longitude=longitude,
            time_end=time or "present",
            time_duration=f"PT{_COMPARE_WINDOW_HOURS}H",
            vert_coord=vert_coord,
        )

        # Filter NaN
        valid_rows = [
            r
            for r in rows
            if r.get(thredds_var) is not None
            and not (isinstance(r[thredds_var], float) and math.isnan(r[thredds_var]))
        ]

        if len(valid_rows) < 2:
            return (
                f"Insufficient data at ({latitude}, {longitude}) for comparison. "
                "Need at least 2 valid time steps."
            )

        first_row = valid_rows[0]
        last_row = valid_rows[-1]
        mid_row = valid_rows[len(valid_rows) // 2]

        first_val = first_row[thredds_var]
        mid_val = mid_row[thredds_var]
        last_val = last_row[thredds_var]

        change = last_val - first_val

        if response_format == "json":
            return json.dumps(
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "variable": variable,
                    "unit": unit,
                    "window_hours": _COMPARE_WINDOW_HOURS,
                    "n_time_steps": len(valid_rows),
                    "earliest": {
                        "time": first_row.get("time", ""),
                        "value": first_val,
                    },
                    "middle": {
                        "time": mid_row.get("time", ""),
                        "value": mid_val,
                    },
                    "latest": {
                        "time": last_row.get("time", ""),
                        "value": last_val,
                    },
                    "change_over_window": round(change, 4),
                },
                indent=2,
            )

        lines = [
            f"## RTOFS {_COMPARE_WINDOW_HOURS} h Change — {var_info['long_name']}",
            f"**Location**: ({latitude:.4f}°, {longitude:.4f}°)",
            f"**Variable**: {variable} ({unit})",
            f"**Time steps**: {len(valid_rows)}",
            "",
            "| Period | Time | Value |",
            "| --- | --- | --- |",
            f"| Earliest | {str(first_row.get('time', '')).replace('T', ' ')[:19]} | {first_val:.4f} {unit} |",
            f"| Middle | {str(mid_row.get('time', '')).replace('T', ' ')[:19]} | {mid_val:.4f} {unit} |",
            f"| Latest | {str(last_row.get('time', '')).replace('T', ' ')[:19]} | {last_val:.4f} {unit} |",
            "",
            f"**Change over the {_COMPARE_WINDOW_HOURS} h window**: {change:+.4f} {unit}",
            "",
            f"*Source: HYCOM THREDDS ({THREDDS_BASE})*",
        ]
        return "\n".join(lines)

    except Exception as e:
        return handle_rtofs_error(e)
