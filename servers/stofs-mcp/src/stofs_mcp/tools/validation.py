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
    COOPS_DATUM_FOR_MODEL_DATUM,
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
    datum_provenance,
    resolve_station_datum,
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
    hours_to_compare: int = 72,
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
    the nowcast: 6 hours before the cycle time for 2d_global, 24 hours before
    it for 3d_atlantic. To cover an event N hours after the cycle time, set
    hours_to_compare to at least N + 6 (2D) or N + 24 (3D). The response gives
    the window's lead times and separate nowcast/forecast statistics.

    The model datum is read from the station file (STOFS-3D station output
    changed from NAVD88 to LMSL at the 2026-08-17 12z v3.1 cycle) and CO-OPS
    observations are requested in the matching datum; no vertical
    transformation is applied. Pairs match the nearest observation within
    3 minutes. CO-OPS quality flags and verified/preliminary status are
    counted and reported, not used to filter.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        model: '2d_global' or '3d_atlantic'.
        cycle_date: Date in YYYY-MM-DD format. Default: latest.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest.
        hours_to_compare: Hours from the start of the file (default 72, max 96).
        full_resolution: Return every 6-minute point instead of hourly points.
        max_points: Maximum series points to return (default 2000).
        response_format: 'markdown' or 'json'.
    """
    tmp_path: Path | None = None
    try:
        client = _get_client(ctx)
        hours_requested = hours_to_compare
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

        # The model datum comes from the file (version-dependent: STOFS-3D
        # station output moved from NAVD88 to LMSL at the v3.1 cycle), and the
        # CO-OPS request datum follows it, never a fixed per-model choice.
        datum_info = resolve_station_datum(model.value, date_str, hour_str, stofs_data)
        stofs_datum = datum_info["datum"]
        if not datum_info["comparable"]:
            return (
                f"No comparison: the vertical datum of the STOFS values for station "
                f"{station_id} could not be established. "
                f"{datum_info['datum_warning']} "
                f"Datum attributes: {json.dumps(datum_info['attributes'])}."
            )
        coops_datum = COOPS_DATUM_FOR_MODEL_DATUM.get(stofs_datum)
        if coops_datum is None:
            return (
                f"STOFS values for this cycle are referenced to {stofs_datum} "
                f"({datum_info['datum_source']}), which has no CO-OPS "
                "equivalent, so no like-for-like comparison is possible. "
                "Convert the values first (e.g. with vdatum-mcp) and compare "
                "them against coops_get_water_levels."
            )

        # Fetch CO-OPS observations
        begin_str = t_start.strftime("%Y%m%d %H:%M")
        end_str = t_end.strftime("%Y%m%d %H:%M")

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

        # Parse CO-OPS time series, counting quality status (not filtering on
        # it: limit flags also trip on genuine storm extremes).
        obs_times = []
        obs_values = []
        obs_quality = {
            "verified": 0,
            "preliminary": 0,
            "flagged": 0,
            "missing": 0,
        }
        for rec in obs_records:
            t_str = rec.get("t", "")
            v_str = rec.get("v", "")
            if not v_str or v_str in ("", " "):
                obs_quality["missing"] += 1
                continue
            try:
                obs_values.append(float(v_str))
                # CO-OPS uses 'YYYY-MM-DD HH:MM' format
                obs_times.append(t_str)
            except (ValueError, TypeError):
                obs_quality["missing"] += 1
                continue
            q = rec.get("q")
            if q == "v":
                obs_quality["verified"] += 1
            elif q == "p":
                obs_quality["preliminary"] += 1
            if any(flag not in ("", "0") for flag in str(rec.get("f", "")).split(",")):
                obs_quality["flagged"] += 1

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

        # Nowcast (at or before the cycle time) and forecast segments differ in
        # kind, so report them separately as well as together.
        cycle_dt = datetime.strptime(date_str + hour_str, "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )

        def lead_h(t_str: str) -> float:
            return round((parse_t(t_str) - cycle_dt).total_seconds() / 3600, 2)

        nowcast_idx = [i for i, t in enumerate(common_times) if lead_h(t) <= 0]
        forecast_idx = [i for i, t in enumerate(common_times) if lead_h(t) > 0]
        segments = {
            name: compute_validation_stats(
                [aligned_stofs[i] for i in idx], [aligned_obs[i] for i in idx]
            )
            for name, idx in (("nowcast", nowcast_idx), ("forecast", forecast_idx))
        }
        lead_start = lead_h(common_times[0])
        lead_end = lead_h(common_times[-1])
        hours_note = (
            f"{hours_to_compare} h"
            if hours_requested == hours_to_compare
            else f"{hours_requested} h requested, clamped to {hours_to_compare} h"
        )

        # An observed maximum on the last aligned point means the peak was cut
        # off: either the window ends too early or the gauge stopped reporting.
        # Say which, so the caller can widen the window instead of concluding
        # from a truncated record.
        peak_note = None
        if peak["observed_peak_at_series_end"]:
            last_obs = parse_t(common_times[-1])
            if t_end - last_obs <= timedelta(hours=1):
                if hours_to_compare < 96:
                    peak_note = (
                        "The observed water level was still rising at the end of "
                        f"the comparison window ({common_times[-1]} UTC), so the "
                        "peak is outside it. Re-run with a larger hours_to_compare "
                        f"(now {hours_to_compare} h, max 96) to capture the peak "
                        "before drawing conclusions."
                    )
                else:
                    peak_note = (
                        "The observed water level was still rising at the end of "
                        "the 96 h maximum window, so the peak is outside it. Use a "
                        "later cycle to capture the peak."
                    )
            else:
                peak_note = (
                    f"Observations stop at {common_times[-1]} UTC, before the "
                    f"comparison window ends ({t_end:%Y-%m-%d %H:%M} UTC), while "
                    "the water was still rising: the gauge may have failed, so the "
                    "true observed peak is likely higher."
                )

        model_label = get_model_label(model.value, date_str)
        datum_note = (
            f"STOFS datum: **{stofs_datum}** ({datum_info['datum_source']}) | "
            f"CO-OPS datum: **{coops_datum}**. No vertical transformation is "
            "applied. Matching labels do not guarantee identical realizations "
            "or epochs, so a mean offset (bias) alone does not show whether its "
            "cause is the reference or the model."
        )
        if datum_info["datum_warning"]:
            datum_note += f" Warning: {datum_info['datum_warning']}"

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
                "stofs_datum_source": datum_info["datum_source"],
                "datum_provenance": datum_provenance(datum_info),
                **(
                    {"stofs_datum_warning": datum_info["datum_warning"]}
                    if datum_info["datum_warning"]
                    else {}
                ),
                "coops_datum": coops_datum,
                "datum_note": datum_note.replace("**", ""),
                "units": "m",
                "timezone": "UTC",
                "comparison_start": common_times[0],
                "comparison_end": common_times[-1],
                "cycle_time": cycle_dt.strftime("%Y-%m-%d %H:%M"),
                "window_lead_hours": [lead_start, lead_end],
                "hours_to_compare": hours_to_compare,
                **(
                    {"hours_to_compare_requested": hours_requested}
                    if hours_requested != hours_to_compare
                    else {}
                ),
                "summary": {
                    **peak,
                    "bias_m": stats["bias"],
                    "rmse_m": stats["rmse"],
                },
                **({"peak_note": peak_note} if peak_note else {}),
                "statistics": stats,
                "statistics_by_segment": segments,
                "alignment": "nearest observation within 3 minutes",
                "observation_quality": obs_quality,
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
            f"(lead {lead_start:+.1f} h to {lead_end:+.1f} h from the cycle time; "
            f"{hours_note})",
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
        if peak_note:
            lines += ["", f"**Note:** {peak_note}"]
        lines += [
            "",
            f"### Summary Statistics (all {stats['n']} 6-minute points)",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Bias (mean error) | {_fmt_m(stats['bias'], signed=True)} |",
            f"| RMSE | {_fmt_m(stats['rmse'])} |",
            f"| MAE | {_fmt_m(stats['mae'])} |",
            f"| Max absolute error, max(abs(F − O)) | {_fmt_m(stats['max_abs_error'])} |",
            f"| Correlation (R) | {stats['correlation']:.3f} |"
            if stats["correlation"] is not None
            else "| Correlation (R) | N/A |",
            "",
            "| Segment | Points | Bias | RMSE |",
            "| --- | --- | --- | --- |",
            *(
                f"| {name.capitalize()} | {seg['n']} "
                f"| {_fmt_m(seg['bias'], signed=True)} | {_fmt_m(seg['rmse'])} |"
                for name, seg in segments.items()
            ),
            "",
            f"*Observations: {obs_quality['verified']} verified, "
            f"{obs_quality['preliminary']} preliminary, "
            f"{obs_quality['flagged']} with CO-OPS quality flags (not filtered), "
            f"{obs_quality['missing']} missing. Pairs match within 3 minutes.*",
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
