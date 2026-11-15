"""Tools: stofs_list_cycles, stofs_get_system_info, stofs_list_stations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import STOFSClient
from ..models import MODEL_CYCLES, Region, STOFSModel
from ..server import mcp
from ..stations import (
    STOFS_STATIONS,
    filter_by_proximity,
    filter_by_region,
    filter_by_state,
)
from ..utils import format_station_table, handle_stofs_error


def _get_client(ctx: Context) -> STOFSClient:
    return ctx.request_context.lifespan_context["stofs_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def stofs_list_cycles(
    ctx: Context,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    date: str | None = None,
    num_days: int = 2,
) -> str:
    """List available STOFS forecast cycles on AWS S3 for a given date range.

    Checks AWS S3 for available station NetCDF files to determine which
    forecast cycles have been published.

    Args:
        model: 'two_global' (4x daily, global) or '3d_atlantic' (1x daily, US East/Gulf).
        date: Specific date in YYYY-MM-DD format. Default: today UTC.
        num_days: Number of past days to check (1–7). Default: 2.
    """
    try:
        client = _get_client(ctx)
        num_days = max(1, min(7, num_days))

        # Determine date range
        if date:
            try:
                end_date = datetime.strptime(date, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return f"Invalid date format '{date}'. Use YYYY-MM-DD."
        else:
            end_date = datetime.now(timezone.utc)

        cycles = MODEL_CYCLES.get(model.value, ["12"])
        model_label = (
            "STOFS-2D-Global" if model.value == "2d_global" else "STOFS-3D-Atlantic"
        )

        results = []
        for day_offset in range(num_days):
            check_date = end_date - timedelta(days=day_offset)
            date_str = check_date.strftime("%Y%m%d")
            date_label = check_date.strftime("%Y-%m-%d")

            for cycle in cycles:
                url = client.build_station_url(model.value, date_str, cycle)
                exists = await client.check_file_exists(url)
                results.append(
                    {
                        "date": date_label,
                        "cycle": f"{cycle}z",
                        "status": "Available" if exists else "Not available",
                        "url": url if exists else "",
                    }
                )

        available = [r for r in results if r["status"] == "Available"]

        lines = [
            f"## STOFS Forecast Cycles — {model_label}",
            f"**Checking**: last {num_days} day(s) | "
            f"**Available**: {len(available)} of {len(results)} cycles",
            "",
            "| Date | Cycle | Status | Station File URL |",
            "| --- | --- | --- | --- |",
        ]
        for r in results:
            url_cell = f"`{r['url']}`" if r["url"] else "—"
            lines.append(f"| {r['date']} | {r['cycle']} | {r['status']} | {url_cell} |")

        lines.append("")
        if available:
            latest = available[0]
            lines.append(
                f"*Latest available: **{latest['date']} {latest['cycle']}**. "
                f"Use stofs_get_station_forecast to retrieve data.*"
            )
        else:
            lines.append(
                "*No cycles found. STOFS-2D products typically arrive ~3 hours after cycle time. "
                "Try again later or check a wider date range.*"
            )

        return "\n".join(lines)

    except Exception as e:
        return handle_stofs_error(e, model.value)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def stofs_get_system_info(
    ctx: Context,
    model: STOFSModel | None = None,
    include_stations: bool = False,
) -> str:
    """Get STOFS system metadata — model specifications, datums, cycle schedule.

    Args:
        model: '2d_global', '3d_atlantic', or None for both. Default: None.
        include_stations: If True, include the full station registry. Default: False.
    """
    try:
        models_to_show = []
        if model is None:
            models_to_show = [STOFSModel.GLOBAL_2D, STOFSModel.ATLANTIC_3D]
        else:
            models_to_show = [model]

        SPECS = {
            "2d_global": {
                "full_name": "STOFS-2D-Global",
                "model_core": "ADCIRC v55+",
                "domain": "Global unstructured mesh",
                "nodes": "~12.8 million",
                "cycles": "4x daily: 00, 06, 12, 18 UTC",
                "forecast_length": "180 hours (7.5 days)",
                "nowcast": "6 hours",
                "station_count": "~385",
                "station_resolution": "6-minute",
                "datum": "LMSL (Local Mean Sea Level), station and gridded output",
                "atmospheric_forcing": "GFS",
                "products": "cwl (combined), htp (tidal), swl (surge)",
                "data_url": "s3://noaa-gestofs-pds/",
                "availability_lag": "~2–3.5 hours after cycle time",
                "opendap": "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/ (regular grid, ~2-day window)",
            },
            "3d_atlantic": {
                "full_name": "STOFS-3D-Atlantic",
                "model_core": "SCHISM",
                "domain": "US East Coast + Gulf of Mexico + Puerto Rico",
                "nodes": "~2.9 million",
                "cycles": "1x daily: 12 UTC",
                "forecast_length": "96 hours (4 days)",
                "nowcast": "24 hours",
                "station_count": "108 (v2.1); 166 (v3.1, from 2026-08-17 12z)",
                "station_resolution": "6-minute",
                "datum": (
                    "Station NetCDF: NAVD88 through the 2026-08-16 cycle (v2.1), "
                    "LMSL from the 2026-08-17 12z cycle (v3.1). "
                    "Gridded GRIB2: xGEOID20b."
                ),
                "atmospheric_forcing": "GFS + HRRR",
                "tidal_forcing": "FES2014",
                "hydrology": "National Water Model (NWM)",
                "products": "cwl only",
                "data_url": "s3://noaa-nos-stofs3d-pds/",
                "availability_lag": "~4–5 hours after 12z",
                "opendap": "https://nomads.ncep.noaa.gov/dods/stofs_3d_atl/ (regular grid, ~2-day window)",
            },
        }

        lines = ["# STOFS System Information"]
        lines.append("")
        per_model = {
            "2d_global": "STOFS-2D-Global station output is LMSL.",
            "3d_atlantic": (
                "STOFS-3D-Atlantic station output is NAVD88 before the v3.1 "
                "upgrade (2026-08-17 12z cycle) and LMSL from it; its gridded "
                "output is xGEOID20b."
            ),
        }
        lines.append(
            "> **Datum note**: "
            + " ".join(per_model[m.value] for m in models_to_show)
            + " The station tools read the datum from each file's metadata and "
            "compare against CO-OPS MSL (for LMSL) or NAVD (CO-OPS's identifier "
            "for NAVD88). No vertical transformation is applied, and matching "
            "labels do not guarantee identical realizations or epochs."
        )

        for m in models_to_show:
            spec = SPECS[m.value]
            lines.append("")
            lines.append(f"## {spec['full_name']}")
            for key, val in spec.items():
                if key == "full_name":
                    continue
                label = key.replace("_", " ").title()
                lines.append(f"- **{label}**: {val}")

        if include_stations:
            lines.append("")
            lines.append("## Station Registry (hardcoded, ~50 key CO-OPS stations)")
            lines.append("")
            lines.append("| Station ID | Name | State | Lat | Lon |")
            lines.append("| --- | --- | --- | --- | --- |")
            for s in STOFS_STATIONS:
                lines.append(
                    f"| {s['id']} | {s['name']} | {s['state']} "
                    f"| {s['lat']} | {s['lon']} |"
                )

        return "\n".join(lines)

    except Exception as e:
        return handle_stofs_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def stofs_list_stations(
    ctx: Context,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    near_lat: float | None = None,
    near_lon: float | None = None,
    radius_km: float = 100.0,
    state: str | None = None,
    region: Region | None = None,
    limit: int = 20,
) -> str:
    """List STOFS output stations, optionally filtered by location, state, or region.

    Uses the built-in station registry (~50 key CO-OPS stations). For the
    complete dynamic list, the station NetCDF file must be downloaded.

    Args:
        model: '2d_global' or '3d_atlantic'.
        near_lat: Filter to stations near this latitude.
        near_lon: Filter to stations near this longitude.
        radius_km: Search radius in km when near_lat/near_lon provided (default 100).
        state: Filter by US state abbreviation (e.g., 'NY', 'FL').
        region: Filter by region ('east_coast', 'gulf', 'west_coast', 'alaska', 'hawaii', 'puerto_rico').
        limit: Max stations to return (default 20).
    """
    try:
        model_label = (
            "STOFS-2D-Global" if model.value == "2d_global" else "STOFS-3D-Atlantic"
        )
        stations = list(STOFS_STATIONS)

        # Region filter
        if region:
            stations = filter_by_region(stations, region.value)

        # State filter
        if state:
            stations = filter_by_state(stations, state)

        # Proximity filter
        if near_lat is not None and near_lon is not None:
            nearby = filter_by_proximity(stations, near_lat, near_lon, radius_km)
            # Add distance to each station dict
            stations = []
            for dist, s in nearby:
                s_copy = dict(s)
                s_copy["distance_km"] = round(dist, 1)
                stations.append(s_copy)

        total = len(stations)
        stations = stations[:limit]

        if not stations:
            filters = []
            if state:
                filters.append(f"state={state}")
            if region:
                filters.append(f"region={region.value}")
            if near_lat is not None:
                filters.append(
                    f"near ({near_lat:.3f}, {near_lon:.3f}) within {radius_km} km"
                )
            return (
                f"No STOFS stations found in the registry matching: {', '.join(filters)}.\n\n"
                "The built-in registry contains ~50 key CO-OPS stations. "
                "For the complete dynamic list, use stofs_get_station_forecast with "
                "a nearby station ID to download the full NetCDF file."
            )

        metadata = [
            f"Model: {model_label}",
            f"Showing {len(stations)} of {total} matching stations",
        ]
        if state:
            metadata.append(f"State: {state.upper()}")
        if region:
            metadata.append(f"Region: {region.value}")
        if near_lat is not None:
            metadata.append(
                f"Near: ({near_lat:.3f}, {near_lon:.3f}), radius {radius_km} km"
            )

        extra_col = (
            ("distance_km", "Distance (km)") if "distance_km" in stations[0] else None
        )

        return format_station_table(
            stations=stations,
            title="STOFS Output Stations",
            metadata_lines=metadata,
            extra_col=extra_col,
        )

    except Exception as e:
        return handle_stofs_error(e, model.value)
