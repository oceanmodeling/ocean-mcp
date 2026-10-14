"""Tool: recon_get_fixes — fetch and parse ATCF f-deck aircraft fix data."""

from typing import Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ReconClient
from ..server import mcp
from ..utils import (
    format_json_response,
    format_tabular_data,
    handle_recon_error,
    parse_atcf_fix_record,
)


def _get_client(ctx: Context) -> ReconClient:
    return ctx.request_context.lifespan_context["recon_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def recon_get_fixes(
    ctx: Context,
    basin: str,
    storm_number: int,
    year: int,
    max_records: int = 2000,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get ATCF f-deck aircraft fix data for a tropical cyclone.

    F-deck data contains structured aircraft and satellite position fixes
    including lat/lon, wind speed, and pressure. This is the most
    machine-readable format for reconnaissance fix data. Current-season
    storms come from ATCF fix/, earlier seasons from the ATCF archive.

    Args:
        basin: Basin code — 'al' (Atlantic), 'ep' (East Pacific), or 'cp' (Central Pacific).
        storm_number: Storm number within the season (e.g., 14 for AL142024).
        year: 4-digit year (e.g., 2024).
        max_records: Cap on fix records returned (default 2000). The f-deck
            is served chronologically oldest-first, so only the most recent
            max_records fixes are kept, and the output flags any
            truncation.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        text, url = await client.fetch_fdeck(basin, storm_number, year)

        records: list[dict] = []
        for line in text.strip().split("\n"):
            record = parse_atcf_fix_record(line)
            if record:
                records.append(record)

        if not records:
            storm_label = f"{basin.upper()}{storm_number:02d}{year}"
            return (
                f"## ATCF Aircraft Fixes\n\n"
                f"No fix records found for {storm_label}.\n"
                f"The f-deck file may be empty or the storm may not have "
                f"reconnaissance data.\n\n"
                f"*Source: {url}*"
            )

        if response_format == "json":
            storm_label = f"{basin.upper()}{storm_number:02d}{year}"
            return format_json_response(
                records,
                context=f"ATCF f-deck fixes for {storm_label}",
                max_records=max_records,
                keep="tail",
            )

        columns = [
            ("datetime", "Date/Time"),
            ("fix_type", "Fix Type"),
            ("lat", "Lat"),
            ("lon", "Lon"),
            ("max_wind_kt", "Wind (kt)"),
            ("min_pressure_mb", "Pressure (mb)"),
        ]

        storm_label = f"{basin.upper()}{storm_number:02d}{year}"
        return format_tabular_data(
            data=records,
            columns=columns,
            title=f"ATCF Aircraft Fixes — {storm_label}",
            metadata_lines=[
                f"Storm: {storm_label}",
                f"Basin: {basin.upper()}",
                f"Year: {year}",
            ],
            count_label="fix records",
            source="NOAA NHC ATCF",
            max_rows=max_records,
            keep="tail",
        )

    except Exception as e:
        storm_label = f"{basin.upper()}{storm_number:02d}{year}"
        return handle_recon_error(e, f"fetching ATCF fixes for {storm_label}")
