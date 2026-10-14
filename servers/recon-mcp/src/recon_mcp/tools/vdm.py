"""Tool: recon_get_vdms — fetch and parse Vortex Data Messages."""

import re
from datetime import datetime
from typing import Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ReconClient
from ..server import mcp
from ..utils import (
    format_json_response,
    format_tabular_data,
    handle_recon_error,
    parse_directory_listing,
    parse_vdm_message,
)


def _get_client(ctx: Context) -> ReconClient:
    return ctx.request_context.lifespan_context["recon_client"]


def _issued(filename: str) -> datetime | None:
    """Issue time from an archive name such as REPNT2-KNHC.202410071313.txt."""
    match = re.search(r"\.(\d{12})\.txt$", filename)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d%H%M")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def recon_get_vdms(
    ctx: Context,
    year: int,
    basin: str = "al",
    storm_id: str | None = None,
    month: int | None = None,
    day: int | None = None,
    limit: int = 50,
    max_records: int = 2000,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get Vortex Data Messages (VDMs) — storm center fix reports from recon aircraft.

    VDMs contain the most operationally critical reconnaissance data: center
    position, minimum sea-level pressure, max flight-level and surface winds,
    eye diameter, and storm structure. Each VDM represents a single pass
    through or near the storm center.

    Args:
        year: Year of data (e.g., 2024).
        basin: Basin — 'al' (Atlantic, default), 'ep' (East Pacific), or 'cp' (Central Pacific).
        storm_id: Optional storm ID filter (e.g., 'AL142024' for Milton).
        month: Optional month filter (1-12).
        day: Optional day filter (1-31).
        limit: Maximum number of VDMs to parse (default 50).
        max_records: Cap on VDMs returned (default 2000). Files are already
            fetched newest-first, so only the most recent max_records VDMs
            are kept, and the output flags any truncation.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        url = client.build_archive_dir_url(year, "vdm", basin)
        html = await client.list_directory(url)
        entries = parse_directory_listing(html)

        # Filter by date if specified
        if month is not None:
            date_prefix = f"{year}{month:02d}"
            if day is not None:
                date_prefix = f"{year}{month:02d}{day:02d}"
            entries = [e for e in entries if date_prefix in e["filename"]]

        # Sort most recent first and apply limit
        entries.sort(key=lambda e: e["filename"], reverse=True)
        entries = entries[:limit]

        if not entries:
            return (
                f"## Vortex Data Messages\n\n"
                f"No VDM files found for {year} in the {basin.upper()} basin"
                f"{f' for {month:02d}' if month else ''}"
                f"{f'/{day:02d}' if day else ''}.\n\n"
                f"*VDMs are generated during active reconnaissance missions "
                f"when aircraft pass through storm centers.*"
            )

        # Fetch and parse each VDM
        vdms: list[dict] = []

        for entry in entries:
            file_url = url + entry["href"]
            try:
                text = await client.fetch_text(file_url)
                parsed = parse_vdm_message(text, issued=_issued(entry["filename"]))
                parsed["source_file"] = entry["filename"]
                vdms.append(parsed)
            except Exception:
                continue

        # Filter by storm_id if specified
        if storm_id:
            storm_id_upper = storm_id.upper()
            vdms = [
                v for v in vdms if (v.get("storm_id") or "").upper() == storm_id_upper
            ]

        if not vdms:
            filter_note = f" for storm {storm_id}" if storm_id else ""
            return (
                f"## Vortex Data Messages\n\n"
                f"No VDMs found{filter_note} in {year} {basin.upper()} basin.\n\n"
                f"*Parsed {len(entries)} files from archive.*"
            )

        if response_format == "json":
            return format_json_response(
                vdms,
                context=f"VDMs for {year} {basin.upper()}"
                + (f" storm {storm_id}" if storm_id else ""),
                max_records=max_records,
            )

        columns = [
            ("source_file", "File"),
            ("storm_id", "Storm"),
            ("fix_time_utc", "Fix Time (UTC)"),
            ("center_lat", "Lat"),
            ("center_lon", "Lon"),
            ("min_slp_mb", "Min SLP (mb)"),
            ("max_fl_wind_inbound_kt", "FL Wind In (kt)"),
            ("max_sfc_wind_inbound_kt", "Sfc Wind In (kt)"),
            ("eye_diameter_nm", "Eye (NM)"),
        ]

        metadata = [
            f"Year: {year}",
            f"Basin: {basin.upper()}",
        ]
        if storm_id:
            metadata.append(f"Storm: {storm_id}")
        if month:
            metadata.append(f"Month: {month:02d}")

        return format_tabular_data(
            data=vdms,
            columns=columns,
            title="Vortex Data Messages",
            metadata_lines=metadata,
            count_label="VDMs",
            max_rows=max_records,
        )

    except Exception as e:
        return handle_recon_error(e, f"fetching VDMs for {year}")
