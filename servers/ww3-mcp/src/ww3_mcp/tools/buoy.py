"""Tools: ww3_get_buoy_observations, ww3_get_buoy_history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
import json

import httpx
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import WW3Client
from ..models import NDBC_HISTORICAL_MISSING_CODES, NDBC_HISTORY_BASE
from ..server import mcp
from ..utils import (
    format_wave_observation_table,
    handle_ww3_error,
    parse_ndbc_historical,
    parse_ndbc_realtime,
    select_recent_window,
    summarize_values,
)

NDBC_MEASDES_URL = "https://www.ndbc.noaa.gov/faq/measdes.shtml"


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
async def ww3_get_buoy_observations(
    ctx: Context,
    station_id: str,
    hours: int = 24,
    response_format: Literal["markdown", "json"] = "markdown",
    max_records: int = 2000,
) -> str:
    """Get recent wave observations from an NDBC buoy.

    Fetches realtime standard meteorological data from NDBC including wave
    height, dominant period, average period, mean wave direction, wind speed,
    and wind direction. NDBC's realtime file holds about the last 45 days, at
    the station's own reporting interval (e.g. 10 minutes at 41009, 30 at
    44025; NDBC says most stations report hourly). The window is selected by
    timestamp, so it covers the requested hours at any interval.

    Args:
        station_id: NDBC station ID (e.g., '41025', '46042', '44013').
        hours: Hours of observations to return, counted back from the latest
            row in the file (default 24, max 1080).
        response_format: 'markdown' (default) or 'json'.
        max_records: Cap on JSON rows returned (default 2000). Rows are
            newest-first, so the most recent are kept, and the response flags
            any truncation. The markdown summary covers the whole window.
    """
    try:
        client = _get_client(ctx)
        hours_requested = hours
        hours = max(1, min(1080, hours))
        max_records = max(1, max_records)

        raw_text = await client.fetch_ndbc_realtime(station_id)
        records = parse_ndbc_realtime(raw_text)

        if not records:
            return (
                f"No observation data available for NDBC station '{station_id}'. "
                "Verify the station ID using ww3_find_buoys."
            )

        rows, window = select_recent_window(records, hours)
        if not rows:
            return (
                f"No timestamped observations for NDBC station '{station_id}' "
                f"({window['rows_in_file']} rows, none with a usable time)."
            )
        notes = []
        if hours != hours_requested:
            notes.append(
                f"hours={hours_requested} was clamped to {hours} (allowed 1-1080)."
            )
        if not window["covers_full_window"]:
            notes.append(
                f"The file reaches back only to {window['oldest_time_in_file']} UTC, "
                f"so the window is shorter than {hours} h."
            )

        if response_format == "json":
            returned = rows[:max_records]  # newest-first: keep the most recent
            truncated = len(rows) > max_records
            payload: dict = {
                "station_id": station_id,
                "timezone": "UTC",
                "window": window,
                "truncated": truncated,
                "returned": len(returned),
                "total": len(rows),
            }
            if truncated:
                payload["hint"] = (
                    f"Only the most recent {len(returned)} of the {len(rows)} rows in "
                    "the window are returned; raise max_records or request fewer hours."
                )
            if notes:
                payload["notes"] = notes
            payload["records"] = len(returned)  # kept from 0.1.2: rows returned
            payload["observations"] = returned
            payload["retrieved_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            return json.dumps(payload, indent=2)

        wvht = summarize_values(rows, "WVHT")
        interval = window["typical_interval_minutes"]
        summary_lines = [
            f"**Window**: {hours} h before the latest row "
            f"({window['window_start']} to {window['latest_time']} UTC): "
            f"{len(rows):,} rows"
            + (f", typically every {interval} min" if interval else ""),
            (
                f"**Wave height (WVHT)**: {wvht['valid']:,} of {len(rows):,} rows valid; "
                f"max {wvht['max']:.2f} m at {wvht['max_time']} UTC; "
                f"min {wvht['min']:.2f} m; mean {wvht['mean']:.2f} m"
                if wvht["valid"]
                else "**Wave height (WVHT)**: no valid value in the window"
            ),
        ]
        summary_lines += [f"*{n}*" for n in notes]
        return format_wave_observation_table(
            rows, station_id=station_id, summary_lines=summary_lines
        )

    except Exception as e:
        return handle_ww3_error(e, f"buoy {station_id}")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_get_buoy_history(
    ctx: Context,
    station_id: str,
    year: int,
    max_records: int = 500,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get historical annual wave observations from an NDBC buoy.

    Fetches NDBC's historical annual standard meteorological file for one
    year. Missing values, which these files mark with 9-filled codes (e.g.
    WVHT 99.00), are returned as null and counted, never as measurements.
    The wave-height summary (valid count, min, max and its time, mean) covers
    every row of the file. The rows returned are the most recent
    max_records rows of the year (the file is oldest-first), and the response
    states how many rows the file has and how many were returned.

    Args:
        station_id: NDBC station ID (e.g., '41025', '46042').
        year: Year to fetch (e.g., 2023). NDBC publishes an annual file only
            after the year has ended.
        max_records: Maximum rows to return (default 500, max 5000). Does not
            change the summary, which always covers the whole file.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        max_records = max(1, min(5000, max_records))
        filename = f"{station_id}h{year}.txt.gz"

        try:
            raw_text = await client.fetch_ndbc_history(station_id, year)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return (
                    f"No NDBC historical annual file for station '{station_id}', "
                    f"year {year} ({filename}: HTTP 404, not found). NDBC "
                    "publishes an annual file only after the year has ended, and "
                    "only for years in which the station reported. For the last "
                    "~45 days use ww3_get_buoy_observations."
                )
            raise

        records, info = parse_ndbc_historical(raw_text)

        if not records:
            return (
                f"No historical data available for NDBC station '{station_id}' "
                f"in year {year}. The station may not have data for that year."
            )

        total = len(records)
        units = info["units"]
        wvht = summarize_values(records, "WVHT")
        excluded = {c: n for c, n in info["missing_counts"].items() if n}

        # The file is oldest-first, so the most recent rows are kept
        # (CONVENTIONS.md). Statistics above use every row, not these.
        rows = records[-max_records:]
        truncated = total > max_records
        selection = (
            f"the most recent {len(rows)} of {total} rows (the file is "
            f"oldest-first); the summary covers all {total} rows"
            if truncated
            else f"all {total} rows of the file"
        )
        time_note = (
            None
            if info["minute_column"]
            else "This file has no minute column: timestamps are on the hour "
            "and several rows can share one."
        )

        if response_format == "json":
            payload = {
                "station_id": station_id,
                "year": year,
                "source": {
                    "product": "NDBC historical standard meteorological data",
                    "file": filename,
                    "url": (
                        f"{NDBC_HISTORY_BASE}?filename={filename}"
                        "&dir=data/historical/stdmet/"
                    ),
                },
                "timezone": "UTC",
                "units": units,
                "units_source": info["units_source"],
                "file_format": {
                    k: info[k]
                    for k in (
                        "header_lines",
                        "columns",
                        "renamed",
                        "two_digit_year",
                        "minute_column",
                    )
                },
                "rows_in_file": total,
                "malformed_rows_skipped": info["malformed_rows_skipped"],
                "missing_values": {
                    "rule": (
                        "NDBC historical files mark a missing value with a "
                        "column-specific 9-filled code; a field equal to its "
                        "column's code is returned as null and counted here"
                    ),
                    "documentation": NDBC_MEASDES_URL,
                    "codes": {
                        c: NDBC_HISTORICAL_MISSING_CODES[c]
                        for c in info["missing_counts"]
                        if c in NDBC_HISTORICAL_MISSING_CODES
                    },
                    "excluded_counts": info["missing_counts"],
                },
                "summary": {
                    "variable": "WVHT",
                    "units": units.get("WVHT", "m"),
                    "covers": f"all {total} rows of the file",
                    "missing": info["missing_counts"].get("WVHT", 0),
                    **wvht,
                },
                "row_selection": selection,
                "truncated": truncated,
                "returned": len(rows),
                "total": total,
            }
            if truncated:
                payload["hint"] = (
                    f"Only the most recent {len(rows)} rows are returned "
                    "(max_records, up to 5000). The summary statistics are "
                    "computed over every row of the file."
                )
            if time_note:
                payload["time_note"] = time_note
            payload["records"] = len(rows)  # kept from 0.1.2: rows returned
            payload["observations"] = rows
            payload["retrieved_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            return json.dumps(payload, indent=2)

        if wvht["valid"]:
            wave_line = (
                f"**Wave height (WVHT), every row of the file**: "
                f"{wvht['valid']:,} of {total:,} rows valid; "
                f"max {wvht['max']:.2f} m at {wvht['max_time']} UTC; "
                f"min {wvht['min']:.2f} m; mean {wvht['mean']:.2f} m"
            )
        else:
            wave_line = (
                f"**Wave height (WVHT)**: no valid value in the {total:,} rows "
                "of the file"
            )
        summary_lines = [
            wave_line,
            (
                "**Missing values excluded** (NDBC 9-filled codes, shown as —): "
                + ", ".join(f"{c} {n:,}" for c, n in excluded.items())
                if excluded
                else "**Missing values**: none"
            ),
        ]
        if time_note:
            summary_lines.append(f"*{time_note}*")
        shown = rows[-100:]
        footer = (
            f"*Showing the most recent {len(shown)} of {total:,} rows "
            f"({shown[0]['timestamp']} to {shown[-1]['timestamp']} UTC). "
            "The summary above covers every row of the file.*"
        )
        table = format_wave_observation_table(
            shown, station_id=station_id, summary_lines=summary_lines, footer=footer
        )
        return f"### Historical Data — {year}\n\n{table}"

    except Exception as e:
        return handle_ww3_error(e, f"buoy {station_id} history {year}")
