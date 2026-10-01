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
    compute_validation_stats,
    handle_stofs_error,
    parse_station_netcdf,
    resolve_cycle,
)


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
async def stofs_compare_with_observations(
    ctx: Context,
    station_id: str,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    cycle_date: str | None = None,
    cycle_hour: str | None = None,
    hours_to_compare: int = 24,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Compare STOFS forecast against CO-OPS observed water levels at a station.

    Downloads the STOFS station file, fetches CO-OPS observations for the
    overlapping period, aligns the time series, and computes validation metrics
    (bias, RMSE, MAE, peak error, correlation).

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        model: '2d_global' or '3d_atlantic'.
        cycle_date: Date in YYYY-MM-DD format. Default: latest.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest.
        hours_to_compare: Hours of overlap to compare (default 24, max 96).
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

        # Compute statistics
        stats = compute_validation_stats(aligned_stofs, aligned_obs)

        stofs_datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = get_model_label(model.value, date_str)
        datum_note = (
            f"STOFS datum: **{stofs_datum}** | CO-OPS datum: **{coops_datum}** "
            "— small systematic offsets (1–5 cm) are expected"
        )

        if response_format == "json":
            return json.dumps(
                {
                    "station_id": station_id,
                    "model": model.value,
                    "cycle_date": date_str,
                    "cycle_hour": hour_str,
                    "stofs_datum": stofs_datum,
                    "coops_datum": coops_datum,
                    "comparison_start": common_times[0] if common_times else "",
                    "comparison_end": common_times[-1] if common_times else "",
                    "statistics": stats,
                    "comparison": [
                        {
                            "time": t,
                            "stofs_m": f,
                            "obs_m": o,
                            "error_m": round(f - o, 4),
                        }
                        for t, f, o in zip(common_times, aligned_stofs, aligned_obs)
                    ],
                },
                indent=2,
            )

        # Markdown output
        lines = [
            f"## STOFS vs Observations — Station {station_id}",
            f"**Model**: {model_label} | "
            f"**Cycle**: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z | "
            f"**Period**: {hours_to_compare} hours",
            f"⚠️  {datum_note}",
            "",
            "### Summary Statistics",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Bias (mean error) | {stats['bias']:+.3f} m |"
            if stats["bias"] is not None
            else "| Bias | N/A |",
            f"| RMSE | {stats['rmse']:.3f} m |"
            if stats["rmse"] is not None
            else "| RMSE | N/A |",
            f"| MAE | {stats['mae']:.3f} m |"
            if stats["mae"] is not None
            else "| MAE | N/A |",
            f"| Peak Error | {stats['peak_error']:.3f} m |"
            if stats["peak_error"] is not None
            else "| Peak Error | N/A |",
            f"| Correlation (R) | {stats['correlation']:.3f} |"
            if stats["correlation"] is not None
            else "| Correlation | N/A |",
            f"| Comparison Points | {stats['n']} |",
            "",
            "### Time Series Comparison (up to 50 rows shown)",
            "| Time (UTC) | STOFS (m) | Observed (m) | Error (m) |",
            "| --- | --- | --- | --- |",
        ]

        # Show up to 50 rows (subsample if needed)
        step = max(1, len(common_times) // 50)
        for i in range(0, len(common_times), step):
            t = common_times[i]
            f_v = aligned_stofs[i]
            o_v = aligned_obs[i]
            err = f_v - o_v
            lines.append(f"| {t} | {f_v:.3f} | {o_v:.3f} | {err:+.3f} |")

        lines.append("")
        lines.append(
            f"*Data: {model_label} vs NOAA CO-OPS observations. Datums: {stofs_datum} vs {coops_datum}.*"
        )
        return "\n".join(lines)

    except Exception as e:
        return handle_stofs_error(e, model.value)
    finally:
        cleanup_temp_file(tmp_path)
