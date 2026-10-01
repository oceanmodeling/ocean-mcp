"""Tool: stofs_compare_with_observations — STOFS vs CO-OPS validation."""

from __future__ import annotations

from typing import Literal
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import STOFSClient
from ..models import (
    COOPS_VALIDATION_DATUMS,
    MODEL_DATUMS,
    STOFSModel,
    get_model_label,
)
from ..server import mcp
from ..utils import (
    align_timeseries,
    cleanup_temp_file,
    compute_peak_stats,
    compute_validation_stats,
    handle_stofs_error,
    parse_station_netcdf,
    resolve_cycle,
)

# Markdown row cap — hourly points over the 96 h maximum window fit under it.
_MARKDOWN_MAX_ROWS = 100


def _get_client(ctx: Context) -> STOFSClient:
    return ctx.request_context.lifespan_context["stofs_client"]


def _hourly_indices(times: list[str]) -> list[int]:
    """Indices of the first point in each clock hour (the :00 sample when present).

    The aligned series is 6-minute, so a 48 h comparison is ~480 points; one
    per hour keeps the response small while the statistics still use them all.
    """
    seen: set[str] = set()
    indices = []
    for i, t in enumerate(times):
        hour = t[:13]
        if hour not in seen:
            seen.add(hour)
            indices.append(i)
    return indices


def _fmt_m(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.3f} m" if signed else f"{value:.3f} m"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def stofs_compare_with_observations(
    ctx: Context,
    station_id: str,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    cycle_date: str | None = None,
    cycle_hour: str | None = None,
    hours_to_compare: int = 24,
    full_resolution: bool = False,
    max_points: int = 2000,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Compare STOFS forecast against CO-OPS observed water levels at a station.

    Downloads the STOFS station file, fetches CO-OPS observations for the
    overlapping period, and aligns the two series. The response leads with a
    summary — observed and forecast peak (value and time), peak error, peak
    timing error, bias, RMSE — followed by the aligned series. Statistics always
    use every 6-minute point; the returned series is hourly unless
    full_resolution is set.

    The comparison window starts at the beginning of the station file, which is
    the nowcast 6 hours before the cycle time. To cover an event N hours after
    the cycle time, set hours_to_compare to at least N + 6.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        model: '2d_global' or '3d_atlantic'.
        cycle_date: Date in YYYY-MM-DD format. Default: latest.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest.
        hours_to_compare: Hours from the start of the file (default 24, max 96).
        full_resolution: Return every 6-minute point instead of hourly points.
        max_points: Maximum series points to return (default 2000).
        response_format: 'markdown' or 'json'.
    """
    tmp_path: Path | None = None
    try:
        client = _get_client(ctx)
        hours_to_compare = max(1, min(96, hours_to_compare))

        # Resolve cycle (shared resolver — honours a date even without an hour)
        cycle = await resolve_cycle(client, model.value, cycle_date, cycle_hour)
        if not cycle:
            return (
                "No STOFS cycles found. Use stofs_list_cycles to check available data."
            )
        date_str, hour_str = cycle

        # Download and parse STOFS station file
        url = client.build_station_url(model.value, date_str, hour_str, "cwl")
        tmp_path = await client.download_netcdf(url)
        stofs_data = parse_station_netcdf(tmp_path, station_id)

        stofs_times = stofs_data["times"]
        stofs_values = stofs_data["values"]

        if not stofs_times:
            return (
                f"No STOFS data found for station {station_id}. "
                "The station may not be in this model's output."
            )

        # Determine comparison time window
        # Use first hours_to_compare hours of the STOFS time series

        def parse_t(s: str) -> datetime:
            for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
                try:
                    return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse: {s}")

        t_start = parse_t(stofs_times[0])
        t_end_max = t_start + timedelta(hours=hours_to_compare)

        # Clip STOFS to comparison window
        stofs_times_clipped = []
        stofs_values_clipped = []
        for t_str, v in zip(stofs_times, stofs_values):
            t = parse_t(t_str)
            if t <= t_end_max:
                stofs_times_clipped.append(t_str)
                stofs_values_clipped.append(v)

        if not stofs_times_clipped:
            return "Could not determine comparison time window from STOFS data."

        t_end = parse_t(stofs_times_clipped[-1])

        # Fetch CO-OPS observations
        begin_str = t_start.strftime("%Y%m%d %H:%M")
        end_str = t_end.strftime("%Y%m%d %H:%M")
        coops_datum = COOPS_VALIDATION_DATUMS.get(model.value, "MSL")

        try:
            obs_data = await client.fetch_coops_observations(
                station_id, begin_str, end_str, datum=coops_datum
            )
        except ValueError as e:
            return (
                f"Could not fetch CO-OPS observations: {e}\n\n"
                "Possible reasons:\n"
                "- Station may not have real-time data for this period\n"
                "- The period may be in the future (forecast only, no observations yet)\n"
                "- Try a cycle from 24–48 hours ago for the nowcast period"
            )

        obs_records = obs_data.get("data", [])
        if not obs_records:
            return (
                f"No CO-OPS observations available for station {station_id} "
                f"during {begin_str} – {end_str} UTC.\n\n"
                "Observations may not exist yet for this period. "
                "Try using a cycle from 24–48 hours ago."
            )

        # Parse CO-OPS time series
        obs_times = []
        obs_values = []
        for rec in obs_records:
            t_str = rec.get("t", "")
            v_str = rec.get("v", "")
            if not v_str or v_str in ("", " "):
                continue
            try:
                obs_values.append(float(v_str))
                # CO-OPS uses 'YYYY-MM-DD HH:MM' format
                obs_times.append(t_str)
            except (ValueError, TypeError):
                continue

        if not obs_times:
            return "CO-OPS observations returned but all values are missing/flagged."

        # Align time series
        common_times, aligned_stofs, aligned_obs = align_timeseries(
            stofs_times_clipped,
            stofs_values_clipped,
            obs_times,
            obs_values,
        )

        if not common_times:
            return (
                "Could not align STOFS and CO-OPS time series — no matching timestamps.\n"
                "This may indicate a time zone mismatch or insufficient overlap."
            )

        # Statistics always use the full-resolution aligned series
        stats = compute_validation_stats(aligned_stofs, aligned_obs)
        peak = compute_peak_stats(common_times, aligned_stofs, aligned_obs)

        stofs_datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = get_model_label(model.value, date_str)
        datum_note = (
            f"STOFS datum: **{stofs_datum}** | CO-OPS datum: **{coops_datum}** "
            "— small systematic offsets (1–5 cm) are expected"
        )

        # Returned series: hourly unless full_resolution, then capped at
        # max_points keeping the head (as the forecast tools do).
        resolution = "6-minute" if full_resolution else "hourly"
        selected = (
            list(range(len(common_times)))
            if full_resolution
            else _hourly_indices(common_times)
        )
        total_points = len(selected)
        cap = max(1, max_points)
        if response_format != "json":
            cap = min(cap, _MARKDOWN_MAX_ROWS)
        truncated = total_points > cap
        selected = selected[:cap]

        if response_format == "json":
            result = {
                "station_id": station_id,
                "model": model.value,
                "model_label": model_label,
                "cycle_date": date_str,
                "cycle_hour": hour_str,
                "stofs_datum": stofs_datum,
                "coops_datum": coops_datum,
                "units": "m",
                "timezone": "UTC",
                "comparison_start": common_times[0],
                "comparison_end": common_times[-1],
                "summary": {
                    **peak,
                    "bias_m": stats["bias"],
                    "rmse_m": stats["rmse"],
                },
                "statistics": stats,
                "resolution": resolution,
                "n_points": len(selected),
                "total_points": total_points,
                "truncated": truncated,
            }
            if truncated:
                result["hint"] = (
                    f"Showing the first {len(selected)} of {total_points} "
                    f"{resolution} points (truncated to limit response size)."
                )
            if not full_resolution:
                result["resolution_note"] = (
                    f"Hourly points shown; statistics use all {stats['n']} "
                    "6-minute points. Set full_resolution=true for 6-minute data."
                )
            result["retrieved_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            result["comparison"] = [
                {
                    "time": common_times[i],
                    "stofs_m": aligned_stofs[i],
                    "obs_m": aligned_obs[i],
                    "error_m": round(aligned_stofs[i] - aligned_obs[i], 4),
                }
                for i in selected
            ]
            return json.dumps(result, indent=2)

        # Markdown output — summary first, then the (hourly) series
        lines = [
            f"## {model_label} vs Observations — Station {station_id}",
            f"**Cycle**: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z | "
            f"**Window**: {common_times[0]} to {common_times[-1]} UTC "
            f"({hours_to_compare} h requested)",
            f"⚠️  {datum_note}",
            "",
            "### Peak Water Level",
            "| | Value | Time (UTC) |",
            "| --- | --- | --- |",
            f"| Observed peak | {_fmt_m(peak['observed_peak_m'])} "
            f"| {peak['observed_peak_time']} |",
            f"| Forecast peak | {_fmt_m(peak['forecast_peak_m'])} "
            f"| {peak['forecast_peak_time']} |",
            f"| Peak error (forecast − observed) "
            f"| {_fmt_m(peak['peak_error_m'], signed=True)} | |",
            f"| Peak timing error | {peak['peak_timing_error_hours']:+.1f} h "
            "(positive = forecast later) | |",
        ]
        if peak["observed_peak_at_series_end"]:
            lines += [
                "",
                "*The observed maximum is the last overlapping point: water was "
                "still rising when the record ended (gauge outage or short window), "
                "so the true observed peak may be higher.*",
            ]
        lines += [
            "",
            f"### Summary Statistics (all {stats['n']} 6-minute points)",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Bias (mean error) | {_fmt_m(stats['bias'], signed=True)} |",
            f"| RMSE | {_fmt_m(stats['rmse'])} |",
            f"| MAE | {_fmt_m(stats['mae'])} |",
            f"| Max absolute error | {_fmt_m(stats['peak_error'])} |",
            f"| Correlation (R) | {stats['correlation']:.3f} |"
            if stats["correlation"] is not None
            else "| Correlation (R) | N/A |",
            "",
            f"### Time Series Comparison ({resolution})",
            "| Time (UTC) | Forecast (m) | Observed (m) | Error (m) |",
            "| --- | --- | --- | --- |",
        ]
        for i in selected:
            f_v = aligned_stofs[i]
            o_v = aligned_obs[i]
            lines.append(
                f"| {common_times[i]} | {f_v:.3f} | {o_v:.3f} | {f_v - o_v:+.3f} |"
            )

        footer = f"*Showing {len(selected)} of {total_points} {resolution} points"
        if not full_resolution:
            footer += "; set full_resolution=true for 6-minute data"
        lines += [
            "",
            footer + ".*",
            f"*Data: {model_label} vs NOAA CO-OPS observations. "
            f"Datums: {stofs_datum} vs {coops_datum}.*",
        ]
        return "\n".join(lines)

    except Exception as e:
        return handle_stofs_error(e, model.value)
    finally:
        cleanup_temp_file(tmp_path)
