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
    PLAUSIBLE_WATER_LEVEL_M,
    COOPS_DATUM_FOR_MODEL_DATUM,
    STOFSModel,
    get_model_label,
)
from ..server import mcp
from ..utils import (
    match_timeseries,
    cleanup_temp_file,
    compute_peak_stats,
    compute_validation_stats,
    handle_stofs_error,
    parse_station_netcdf,
    resolve_cycle,
    datum_provenance,
    describe_exclusions,
    dumps_strict,
    resolve_station_datum,
    value_exclusion_reason,
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
    lead_start_hours: float | None = None,
    lead_end_hours: float | None = None,
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

    To compare different models over the same valid times, set a lead-time
    window instead: lead_start_hours < lead <= lead_end_hours, with lead
    measured from the cycle time (e.g. 0 and 48 for the 0-48 h forecast;
    -24 and 0 for the 3D nowcast). Either bound may be omitted. A lead window
    replaces hours_to_compare, and the response says if the file does not
    cover it.

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
            Ignored when a lead window is given.
        lead_start_hours: Exclusive lower lead bound in hours from the cycle
            time (negative = nowcast). Optional.
        lead_end_hours: Inclusive upper lead bound in hours. Optional.
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
            why = describe_exclusions(stofs_data.get("excluded_model_records"))
            return (
                f"No usable STOFS values for station {station_id} in this cycle: all "
                f"{stofs_data.get('n_records', 0)} records were excluded"
                + (f" ({why})" if why else "")
                + ". 'sentinel' values are no-data codes (possibly shifted by a datum "
                "constant); 'implausible' values exceed "
                f"{PLAUSIBLE_WATER_LEVEL_M:g} m. Nothing was compared."
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

        cycle_dt = datetime.strptime(date_str + hour_str, "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
        # The window starts at the file's first record (the nowcast start), not
        # at the first valid value, so a missing leading record cannot shift it.
        raw_start = stofs_data.get("model_start") or stofs_times[0]
        raw_end = stofs_data.get("model_end") or stofs_times[-1]
        t_start = parse_t(raw_start)
        lead_window = lead_start_hours is not None or lead_end_hours is not None
        coverage_note = None
        if lead_window:
            if (
                lead_start_hours is not None
                and lead_end_hours is not None
                and lead_end_hours <= lead_start_hours
            ):
                return "lead_end_hours must be greater than lead_start_hours."
            lo = (
                cycle_dt + timedelta(hours=lead_start_hours)
                if lead_start_hours is not None
                else None
            )
            hi = (
                cycle_dt + timedelta(hours=lead_end_hours)
                if lead_end_hours is not None
                else None
            )
            t_end_max = hi or parse_t(raw_end)

            def in_window(t: datetime) -> bool:
                return (lo is None or t > lo) and (hi is None or t <= hi)

            bounds = (
                "-inf" if lead_start_hours is None else f"{lead_start_hours:g}",
                "+inf" if lead_end_hours is None else f"{lead_end_hours:g}",
            )
            window_definition = (
                f"lead ({bounds[0]}, {bounds[1]}] h from the cycle time "
                f"{cycle_dt:%Y-%m-%d %H:%M} UTC"
            )
            gaps = []
            if lo is not None and t_start > lo + timedelta(minutes=6):
                gaps.append(f"starts at {raw_start} UTC, after the window start")
            if hi is not None and parse_t(raw_end) < hi:
                gaps.append(f"ends at {raw_end} UTC, before the window end")
            if gaps:
                coverage_note = "The station file " + " and ".join(gaps) + "."
        else:
            t_end_max = t_start + timedelta(hours=hours_to_compare)

            def in_window(t: datetime) -> bool:
                return t_start <= t <= t_end_max

            window_definition = f"file start + {hours_to_compare} h"

        # Clip STOFS to comparison window
        stofs_times_clipped = []
        stofs_values_clipped = []
        for t_str, v in zip(stofs_times, stofs_values):
            if in_window(parse_t(t_str)):
                stofs_times_clipped.append(t_str)
                stofs_values_clipped.append(v)

        if not stofs_times_clipped:
            return (
                "No valid STOFS values in the comparison window "
                f"({window_definition}); the station file covers {raw_start} to "
                f"{raw_end} UTC."
            )

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
        begin_str = parse_t(stofs_times_clipped[0]).strftime("%Y%m%d %H:%M")
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
        obs_status: list[str | None] = []
        obs_flagged: list[bool] = []
        obs_quality = {
            "records": len(obs_records),
            "verified": 0,
            "preliminary": 0,
            "unknown_status": 0,
            "flagged": 0,
            "missing": 0,
            "nonfinite": 0,
            "sentinel": 0,
            "implausible": 0,
        }
        for rec in obs_records:
            t_str = rec.get("t", "")
            v_str = rec.get("v", "")
            if not v_str or v_str in ("", " "):
                obs_quality["missing"] += 1
                continue
            try:
                value = float(v_str)
            except (ValueError, TypeError):
                obs_quality["missing"] += 1
                continue
            # Same rule as the model values: "NaN"/"Infinity" parse as floats.
            reason = value_exclusion_reason(value)
            if reason:
                obs_quality[reason] += 1
                continue
            obs_values.append(value)
            obs_times.append(t_str)  # CO-OPS uses 'YYYY-MM-DD HH:MM'
            q = rec.get("q")
            flagged = any(
                flag not in ("", "0") for flag in str(rec.get("f", "")).split(",")
            )
            obs_status.append(q)
            obs_flagged.append(flagged)
            if q == "v":
                obs_quality["verified"] += 1
            elif q == "p":
                obs_quality["preliminary"] += 1
            else:
                obs_quality["unknown_status"] += 1
            obs_quality["flagged"] += flagged

        if not obs_times:
            return (
                f"CO-OPS returned {len(obs_records)} records for station {station_id} "
                f"but none has a usable value ({obs_quality['missing']} missing, "
                f"{obs_quality['nonfinite']} non-finite, {obs_quality['sentinel']} "
                f"sentinel, {obs_quality['implausible']} implausible)."
            )

        # Align: one-to-one, exact timestamps first, then nearest unused
        # observation within 3 min (ties to the earlier one), UTC arithmetic.
        match = match_timeseries(stofs_times_clipped, obs_times)
        common_times = [stofs_times_clipped[fi] for fi, _ in match["pairs"]]
        aligned_stofs = [stofs_values_clipped[fi] for fi, _ in match["pairs"]]
        aligned_obs = [obs_values[oi] for _, oi in match["pairs"]]
        matched_obs = [oi for _, oi in match["pairs"]]
        obs_quality["matched"] = {
            "pairs": len(matched_obs),
            "verified": sum(obs_status[i] == "v" for i in matched_obs),
            "preliminary": sum(obs_status[i] == "p" for i in matched_obs),
            "unknown_status": sum(obs_status[i] not in ("v", "p") for i in matched_obs),
            "flagged": sum(obs_flagged[i] for i in matched_obs),
        }
        alignment = {
            "method": (
                "one-to-one; exact timestamps first, then the nearest unused "
                "observation within 3 min (ties to the earlier); UTC"
            ),
            "exact": match["exact"],
            "nearest": match["nearest"],
            "unmatched_model_records": len(stofs_times_clipped) - len(matched_obs),
            "bad_observation_times": match["bad_observed_times"],
            "duplicate_observation_times": match["duplicate_observed_times"],
        }

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
        if lead_window:
            hours_note = window_definition
        elif hours_requested == hours_to_compare:
            hours_note = f"{hours_to_compare} h"
        else:
            hours_note = (
                f"{hours_requested} h requested, clamped to {hours_to_compare} h"
            )

        # An observed maximum on the last aligned point means the peak was cut
        # off: either the window ends too early or the gauge stopped reporting.
        # Say which, so the caller can widen the window instead of concluding
        # from a truncated record.
        peak_note = None
        if peak["observed_peak_at_series_end"]:
            last_obs = parse_t(common_times[-1])
            if t_end - last_obs <= timedelta(hours=1):
                if lead_window:
                    peak_note = (
                        "The observed maximum is the last point of the lead window "
                        f"({common_times[-1]} UTC), so the true peak may lie after "
                        "it. Re-run with a larger lead_end_hours before drawing "
                        "conclusions about the peak."
                    )
                elif hours_to_compare < 96:
                    peak_note = (
                        "The observed maximum is the last point of the comparison "
                        f"window ({common_times[-1]} UTC), so the true peak may lie "
                        "after it. Re-run with a larger hours_to_compare "
                        f"(now {hours_to_compare} h, max 96) before drawing "
                        "conclusions about the peak."
                    )
                else:
                    peak_note = (
                        "The observed maximum is the last point of the 96 h maximum "
                        "window, so the true peak may lie after it. A later cycle "
                        "would cover it."
                    )
            else:
                peak_note = (
                    f"Observations stop at {common_times[-1]} UTC, before the "
                    f"comparison window ends ({t_end:%Y-%m-%d %H:%M} UTC), and the "
                    "observed maximum is the last observation: the gauge may have "
                    "failed, so the true observed peak may be higher."
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
                "hours_to_compare": None if lead_window else hours_to_compare,
                **(
                    {"hours_to_compare_requested": hours_requested}
                    if hours_requested != hours_to_compare and not lead_window
                    else {}
                ),
                **(
                    {"lead_window_hours": [lead_start_hours, lead_end_hours]}
                    if lead_window
                    else {}
                ),
                **({"coverage_note": coverage_note} if coverage_note else {}),
                "summary": {
                    **peak,
                    "bias_m": stats["bias"],
                    "rmse_m": stats["rmse"],
                },
                **({"peak_note": peak_note} if peak_note else {}),
                "statistics": stats,
                "statistics_by_segment": segments,
                "window": {
                    "definition": window_definition,
                    "file_start": raw_start,
                    "requested_end": t_end_max.strftime("%Y-%m-%d %H:%M"),
                    "model_available": [
                        stofs_times_clipped[0],
                        stofs_times_clipped[-1],
                    ],
                    "matched": [common_times[0], common_times[-1]],
                    "excluded_model_records": stofs_data.get("excluded_model_records"),
                },
                "alignment": alignment,
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
            return dumps_strict(result)

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
        if coverage_note:
            lines += ["", f"**Coverage:** {coverage_note}"]
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
            f"{obs_quality['missing']} missing, {obs_quality['nonfinite']} non-finite, "
            f"{obs_quality['sentinel'] + obs_quality['implausible']} out of range "
            f"(excluded) of {obs_quality['records']} records; matched pairs: "
            f"{obs_quality['matched']['verified']} verified, "
            f"{obs_quality['matched']['preliminary']} preliminary, "
            f"{obs_quality['matched']['flagged']} flagged. Pairs: "
            f"{alignment['exact']} exact, {alignment['nearest']} within 3 min, "
            "one-to-one.*",
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
