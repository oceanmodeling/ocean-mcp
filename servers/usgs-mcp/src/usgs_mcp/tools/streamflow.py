"""Streamflow data tools for USGS Water Services."""

from datetime import datetime, timezone
from typing import Literal
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import USGSClient
from ..models import describe_exclusions, format_parameter, screen_series_values
from ..server import mcp


def _get_client(ctx: Context) -> USGSClient:
    return ctx.request_context.lifespan_context["usgs_client"]


def _cap_waterml(data: dict, max_points: int) -> dict:
    """Cap each WaterML time series to its most recent ``max_points`` values
    and wrap the payload with a truncation envelope.

    The raw USGS IV/DV JSON is unbounded (a long ``period`` can be tens of
    thousands of records), and dumping it whole floods the model's context.
    This keeps the most recent points and tells the model it was truncated.
    """
    total = 0
    returned = 0
    truncated = False
    for ts in data.get("value", {}).get("timeSeries", []):
        for vset in ts.get("values", []):
            vals = vset.get("value", [])
            total += len(vals)
            if len(vals) > max_points:
                vset["value"] = vals[-max_points:]  # keep the most recent
                truncated = True
            returned += len(vset["value"])
    envelope: dict = {"truncated": truncated, "returned": returned, "total": total}
    envelope["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if truncated:
        envelope["hint"] = (
            f"Showing the most recent {returned} of {total} points. Narrow "
            "`period`, or use response_format='markdown' for a summary."
        )
    envelope["data"] = data
    return envelope


def _handle_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    import httpx

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Site not found. Verify the 8-digit USGS site number."
        return f"HTTP Error {status}: The USGS API may be temporarily unavailable."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The USGS API may be experiencing high load."
    return f"Unexpected error: {type(e).__name__}: {e}"


def _extract_timeseries(data: dict) -> tuple[list[dict], str, str]:
    """Extract time series values from USGS JSON (WaterML) response.

    Returns (values_list, variable_name, unit_code).
    """
    ts_list = data.get("value", {}).get("timeSeries", [])
    if not ts_list:
        return [], "Unknown", ""

    ts = ts_list[0]
    var_info = ts.get("variable", {})
    var_name = var_info.get("variableName", "Unknown")
    unit = var_info.get("unit", {}).get("unitCode", "")

    values = []
    for val_set in ts.get("values", []):
        for v in val_set.get("value", []):
            values.append(
                {
                    "datetime": v.get("dateTime", ""),
                    "value": v.get("value", ""),
                    "qualifier": ",".join(
                        q.get("qualifierCode", "") if isinstance(q, dict) else str(q)
                        for q in v.get("qualifiers", [])
                    ),
                }
            )
    return values, var_name, unit


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_instantaneous_values(
    ctx: Context,
    site_number: str,
    parameter_code: str = "00060",
    period: str = "P7D",
    response_format: Literal["markdown", "json"] = "markdown",
    max_points: int = 2000,
) -> str:
    """Get real-time (instantaneous) streamflow data from a USGS site.

    Returns ~15-minute interval data for up to the last 120 days.
    Common use: checking current river conditions and recent trends.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        parameter_code: USGS parameter code — '00060' (discharge, default) or '00065' (gage height).
        period: ISO 8601 duration for lookback period (default 'P7D' = 7 days). Max 'P120D'.
        response_format: Output format — 'markdown' (default) or 'json'.
        max_points: For json output, cap each series to the most recent N points
            (default 2000) so a long period doesn't flood context; the response
            carries a {truncated,returned,total} envelope.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        client = _get_client(ctx)
        data = await client.get_json(
            "iv",
            {
                "sites": site_number,
                "parameterCd": parameter_code,
                "period": period,
            },
        )

        if response_format == "json":
            import json

            return json.dumps(_cap_waterml(data, max_points), indent=2)

        values, var_name, unit = _extract_timeseries(data)

        if not values:
            return f"No instantaneous data found for site {site_number}."

        param_label = format_parameter(parameter_code)
        lines = [f"## Instantaneous Values — Site {site_number}"]
        lines.append(f"**Parameter**: {param_label}")
        lines.append(f"**Period**: {period}")
        lines.append(f"**Records**: {len(values)}")

        # Current value
        latest = values[-1]
        lines.append(f"**Current**: {latest['value']} {unit} ({latest['datetime']})")
        lines.append("")

        # Show last 20 values as a table
        display = values[-20:]
        lines.append("| DateTime | Value | Qualifier |")
        lines.append("|----------|-------|-----------|")
        for v in display:
            dt = v["datetime"].replace("T", " ")[:19]
            lines.append(f"| {dt} | {v['value']} {unit} | {v['qualifier']} |")

        if len(values) > 20:
            lines.append(f"\n*Showing last 20 of {len(values)} records.*")

        lines.append("")
        lines.append("*Data from USGS Water Services (instantaneous values).*")
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_daily_values(
    ctx: Context,
    site_number: str,
    start_date: str,
    end_date: str,
    parameter_code: str = "00060",
    stat_code: str = "00003",
    response_format: Literal["markdown", "json"] = "markdown",
    max_points: int = 2000,
) -> str:
    """Get daily mean/min/max streamflow values from a USGS site.

    Returns daily statistical values over a date range. Decades of historical
    data are available at most sites.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        start_date: Start date as YYYY-MM-DD.
        end_date: End date as YYYY-MM-DD.
        parameter_code: USGS parameter code — '00060' (discharge, default) or '00065' (gage height).
        stat_code: Statistic code — '00003' (mean, default), '00001' (max), '00002' (min).
        response_format: Output format — 'markdown' (default) or 'json'.
        max_points: For json output, cap each series to the most recent N points
            (default 2000) so a multi-decade range doesn't flood context; the
            response carries a {truncated,returned,total} envelope.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        # Validate date format
        from datetime import datetime

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return "Validation Error: Dates must be in YYYY-MM-DD format."

        if end_dt < start_dt:
            return "Validation Error: end_date must be on or after start_date."

        client = _get_client(ctx)
        data = await client.get_json(
            "dv",
            {
                "sites": site_number,
                "parameterCd": parameter_code,
                "startDT": start_date,
                "endDT": end_date,
                "statCd": stat_code,
            },
        )

        if response_format == "json":
            import json

            return json.dumps(_cap_waterml(data, max_points), indent=2)

        values, var_name, unit = _extract_timeseries(data)

        if not values:
            return (
                f"No daily data found for site {site_number} in the requested period."
            )

        stat_labels = {"00003": "Mean", "00001": "Maximum", "00002": "Minimum"}
        stat_label = stat_labels.get(stat_code, stat_code)
        param_label = format_parameter(parameter_code)

        lines = [f"## Daily Values — Site {site_number}"]
        lines.append(f"**Parameter**: {param_label}")
        lines.append(f"**Statistic**: {stat_label}")
        lines.append(f"**Period**: {start_date} to {end_date}")
        lines.append(f"**Records**: {len(values)}")
        lines.append("")

        lines.append("| Date | Value | Qualifier |")
        lines.append("|------|-------|-----------|")
        display = values[:50]
        for v in display:
            dt = v["datetime"][:10]
            lines.append(f"| {dt} | {v['value']} {unit} | {v['qualifier']} |")

        if len(values) > 50:
            lines.append(f"\n*Showing first 50 of {len(values)} records.*")

        lines.append("")
        lines.append("*Data from USGS Water Services (daily values).*")
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_hydrograph(
    ctx: Context,
    site_number: str,
    days: int = 7,
    include_median: bool = True,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get streamflow data formatted for hydrograph context.

    Fetches recent instantaneous values and optionally compares them to
    historical daily median statistics for context. Useful for understanding
    whether current conditions are above or below normal.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        days: Number of days of recent data (default 7, max 120).
        include_median: Include historical median comparison (default True).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        if days < 1 or days > 120:
            return "Validation Error: Days must be between 1 and 120."

        client = _get_client(ctx)

        # Fetch recent IV data
        iv_data = await client.get_json(
            "iv",
            {
                "sites": site_number,
                "parameterCd": "00060",
                "period": f"P{days}D",
            },
        )

        values, var_name, unit = _extract_timeseries(iv_data)

        if not values:
            return f"No instantaneous data found for site {site_number}."

        # Summary stats over valid readings only: readings equal to the
        # series' declared noDataValue (-999999, e.g. qualifier Ice) are not
        # measurements and are excluded and counted (see models.py).
        ts = iv_data["value"]["timeSeries"][0]
        valid, screen = screen_series_values(ts)
        if not valid:
            return (
                f"No valid numeric data for site {site_number}: "
                f"{screen['readings']:,} readings, {describe_exclusions(screen)}."
            )
        numeric_vals = [v["value"] for v in valid]
        latest = screen["latest"]

        # "Current" is the latest reading only if it is a measurement.
        current = None if latest["excluded_reason"] else numeric_vals[-1]
        min_val = min(numeric_vals)
        max_val = max(numeric_vals)
        mean_val = sum(numeric_vals) / len(numeric_vals)

        # Determine trend from recent values
        if len(numeric_vals) >= 4:
            recent_quarter = numeric_vals[-(len(numeric_vals) // 4) :]
            recent_mean = sum(recent_quarter) / len(recent_quarter)
            if recent_mean > mean_val * 1.1:
                trend = "Rising"
            elif recent_mean < mean_val * 0.9:
                trend = "Falling"
            else:
                trend = "Stable"
        else:
            trend = "Insufficient data"

        result = {
            "site_number": site_number,
            "period_days": days,
            "current_cfs": current,
            "min_cfs": min_val,
            "max_cfs": max_val,
            "mean_cfs": round(mean_val, 1),
            "trend": trend,
            "num_readings": len(numeric_vals),
            "readings_total": screen["readings"],
            "excluded_readings": screen["excluded"],
            "no_data_value": screen["no_data_value"],
        }
        if screen["excluded_qualifiers"]:
            result["excluded_qualifiers"] = screen["excluded_qualifiers"]
        if current is None:
            result["current_note"] = (
                f"The latest reading ({latest['datetime']}) is not a measurement "
                f"(value {latest['value']}, qualifiers {latest['qualifiers'] or 'none'}); "
                "current_cfs is null and min/max/mean exclude it."
            )
            result["last_valid_cfs"] = numeric_vals[-1]
            result["last_valid_time"] = valid[-1]["datetime"]

        # Fetch median stats if requested
        median_value = None
        if include_median:
            try:
                stat_rows = await client.get_rdb(
                    "stat",
                    {
                        "sites": site_number,
                        "statReportType": "daily",
                        "statTypeCd": "median",
                        "parameterCd": "00060",
                    },
                )
                if stat_rows:
                    # Get today's month/day and find matching stat
                    from datetime import UTC, datetime

                    now = datetime.now(UTC)
                    month_str = f"{now.month}"
                    day_str = f"{now.day}"
                    for sr in stat_rows:
                        if (
                            sr.get("month_nu") == month_str
                            and sr.get("day_nu") == day_str
                        ):
                            try:
                                median_value = float(sr.get("p50_va", ""))
                            except (ValueError, TypeError):
                                pass
                            break
                    if median_value is not None:
                        result["median_cfs"] = median_value
                        if current is not None:
                            pct = (
                                ((current - median_value) / median_value * 100)
                                if median_value > 0
                                else 0
                            )
                            result["pct_of_median"] = round(pct, 1)
                        else:
                            result["pct_of_median"] = None
            except Exception:
                pass  # Median stats are best-effort

        if response_format == "json":
            import json

            return json.dumps(result, indent=2)

        lines = [f"## Hydrograph Summary — Site {site_number}"]
        lines.append(f"**Period**: Last {days} days")
        lines.append(
            f"**Readings**: {len(numeric_vals):,} valid of {screen['readings']:,} "
            f"(excluded: {describe_exclusions(screen)})"
        )
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        if current is not None:
            lines.append(f"| Current | {current:.1f} {unit} |")
        else:
            lines.append(
                f"| Current | no data: latest reading {latest['datetime']} is "
                f"{latest['value']} (qualifiers {latest['qualifiers'] or 'none'}) |"
            )
            lines.append(
                f"| Last valid | {numeric_vals[-1]:.1f} {unit} ({valid[-1]['datetime']}) |"
            )
        lines.append(f"| Minimum | {min_val:.1f} {unit} |")
        lines.append(f"| Maximum | {max_val:.1f} {unit} |")
        lines.append(f"| Mean | {mean_val:.1f} {unit} |")
        lines.append(f"| Trend | {trend} |")

        if median_value is not None:
            lines.append(f"| Historical Median | {median_value:.1f} {unit} |")
            pct = result.get("pct_of_median")
            if pct is None:
                lines.append("| vs. Median | not computed (no current measurement) |")
            elif pct > 0:
                lines.append(f"| vs. Median | {pct:+.1f}% (above normal) |")
            else:
                lines.append(f"| vs. Median | {pct:+.1f}% (below normal) |")

        lines.append("")
        lines.append("*Data from USGS Water Services.*")
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)
