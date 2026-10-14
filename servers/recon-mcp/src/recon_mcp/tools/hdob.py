"""Tool: recon_get_hdobs — fetch and parse HDOB flight-level observations."""

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
    parse_hdob_message,
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
async def recon_get_hdobs(
    ctx: Context,
    year: int,
    basin: str = "al",
    month: int | None = None,
    day: int | None = None,
    limit: int = 20,
    max_records: int = 2000,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get HDOB (High Density Observation) flight-level reconnaissance data.

    HDOB bulletins contain 30-second averaged observations from hurricane
    hunter aircraft including flight-level winds, SFMR surface winds,
    pressure, temperature, and position. This is the primary real-time
    reconnaissance data feed.

    Args:
        year: Year of data (e.g., 2024).
        basin: Basin — 'al' (Atlantic, default), 'ep' (East Pacific), or 'cp' (Central Pacific).
        month: Optional month filter (1-12).
        day: Optional day filter (1-31).
        limit: Maximum number of HDOB bulletins to parse (default 20).
        max_records: Cap on observations returned (default 2000). Bulletins
            are already fetched newest-first, so only the most recent
            max_records observations are kept, and the output flags any
            truncation.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        url = client.build_archive_dir_url(year, "hdob", basin)
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
                f"## HDOB Observations\n\n"
                f"No HDOB bulletins found for {year} in the {basin.upper()} basin"
                f"{f' for {month:02d}' if month else ''}"
                f"{f'/{day:02d}' if day else ''}.\n\n"
                f"*HDOB data is only available during active reconnaissance missions.*"
            )

        # Fetch and parse each HDOB bulletin
        all_observations: list[dict] = []
        bulletin_count = 0

        for entry in entries:
            file_url = url + entry["href"]
            try:
                text = await client.fetch_text(file_url)
                parsed = parse_hdob_message(text)
                bulletin_count += 1

                header = parsed.get("header", {})
                aircraft = header.get("aircraft", "Unknown")
                for obs in parsed.get("observations", []):
                    obs["aircraft"] = aircraft
                    obs["source_file"] = entry["filename"]
                    all_observations.append(obs)
            except Exception:
                continue

        if not all_observations:
            return (
                f"## HDOB Observations\n\n"
                f"Found {len(entries)} HDOB files but could not parse observations.\n"
                f"The files may be empty or in an unexpected format."
            )

        if response_format == "json":
            return format_json_response(
                all_observations,
                context=f"HDOB observations from {bulletin_count} bulletins, {year} {basin.upper()}",
                max_records=max_records,
            )

        columns = [
            ("date", "Date"),
            ("time", "Time (UTC)"),
            ("lat", "Lat"),
            ("lon", "Lon"),
            ("static_pressure_mb", "P (mb)"),
            ("extrapolated_slp_mb", "SLP (mb)"),
            ("fl_wind_dir_deg", "WDir"),
            ("fl_wind_speed_kt", "WSpd (kt)"),
            ("sfmr_sfc_wind_kt", "SFMR (kt)"),
            ("sfmr_rain_rate_mmhr", "Rain (mm/h)"),
            ("aircraft", "Aircraft"),
        ]

        metadata = [
            f"Year: {year}",
            f"Basin: {basin.upper()}",
            f"Bulletins parsed: {bulletin_count}",
        ]
        if month:
            metadata.append(f"Month: {month:02d}")
        if day:
            metadata.append(f"Day: {day:02d}")

        return format_tabular_data(
            data=all_observations,
            columns=columns,
            title="HDOB Flight-Level Observations",
            metadata_lines=metadata,
            count_label="observations",
            max_rows=max_records,
        )

    except Exception as e:
        return handle_recon_error(e, f"fetching HDOB data for {year}")
