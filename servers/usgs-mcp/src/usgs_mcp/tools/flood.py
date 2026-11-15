"""Flood analysis tools for USGS Water Services."""

from typing import Literal
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import USGSClient
from ..models import screen_series_values
from ..server import mcp


def _get_client(ctx: Context) -> USGSClient:
    return ctx.request_context.lifespan_context["usgs_client"]


# NWS flood-category labels, in ascending severity.
_NWS_CAT_LABEL = {
    "no_flooding": "No Flooding",
    "action": "Action Stage",
    "minor": "Minor Flood",
    "moderate": "Moderate Flood",
    "major": "Major Flood",
}
_NWS_CAT_ORDER = ["action", "minor", "moderate", "major"]


def _valid_threshold(x: object) -> float | None:
    """NWPS encodes an undefined stage/flow threshold as -9999."""
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if v <= -9990 else v


def _nwps_flood(nwps: dict) -> dict | None:
    """Extract NWS flood-stage classification from an NWPS gauge record.

    Returns ``None`` when the site has no usable stage thresholds — i.e. it
    is not a real NWS flood-forecast point — so the caller falls back to a
    clearly-labelled streamflow anomaly rather than inventing flood categories.
    """
    flood = nwps.get("flood") or {}
    cats = flood.get("categories") or {}
    thresholds: dict[str, dict[str, float | None]] = {}
    for name in _NWS_CAT_ORDER:
        c = cats.get(name) or {}
        thresholds[name] = {
            "stage": _valid_threshold(c.get("stage")),
            "flow": _valid_threshold(c.get("flow")),
        }
    if not any(thresholds[n]["stage"] is not None for n in _NWS_CAT_ORDER):
        return None  # no official NWS stage thresholds

    obs = (nwps.get("status") or {}).get("observed") or {}
    obs_stage = _valid_threshold(obs.get("primary"))
    obs_cat = (nwps.get("ObservedFloodCategory") or "").strip().lower()
    if obs_cat not in _NWS_CAT_LABEL:
        # NWPS didn't label it → derive from observed stage vs thresholds.
        obs_cat = "no_flooding"
        if obs_stage is not None:
            for name in _NWS_CAT_ORDER:  # ascending severity
                s = thresholds[name]["stage"]
                if s is not None and obs_stage >= s:
                    obs_cat = name
    fcst_cat = (nwps.get("ForecastFloodCategory") or "").strip().lower()
    return {
        "lid": nwps.get("lid") or "",
        "category": obs_cat,
        "label": _NWS_CAT_LABEL.get(obs_cat, obs_cat or "Unknown"),
        "forecast_category": fcst_cat if fcst_cat in _NWS_CAT_LABEL else "",
        "observed_stage": obs_stage,
        "stage_unit": flood.get("stageUnits") or obs.get("primaryUnit") or "ft",
        "flow_unit": flood.get("flowUnits") or "cfs",
        "thresholds": thresholds,
    }


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


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_peak_streamflow(
    ctx: Context,
    site_number: str,
    start_year: int | None = None,
    end_year: int | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get annual peak streamflow records for a USGS site.

    Returns the highest flow recorded each year, including discharge and
    gage height. Many sites have 50+ years of record. Useful for flood
    frequency analysis and understanding historical flood severity.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        start_year: Optional start year filter.
        end_year: Optional end year filter.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        params: dict = {"site_no": site_number}
        if start_year:
            params["begin_date"] = f"{start_year}-01-01"
        if end_year:
            params["end_date"] = f"{end_year}-12-31"

        client = _get_client(ctx)
        rows = await client.get_peak(params)

        if not rows:
            return f"No peak streamflow records found for site {site_number}."

        if response_format == "json":
            import json

            return json.dumps(rows, indent=2)

        # Find the period of record max
        max_flow = 0.0
        max_row = None
        for row in rows:
            try:
                flow = float(row.get("peak_va", "0"))
                if flow > max_flow:
                    max_flow = flow
                    max_row = row
            except (ValueError, TypeError):
                pass

        lines = [f"## Peak Streamflow — Site {site_number}"]
        lines.append(f"**Records**: {len(rows)} years")
        if max_row:
            lines.append(
                f"**Period of Record Max**: {max_flow:,.0f} cfs on {max_row.get('peak_dt', '?')}"
            )
        lines.append("")

        lines.append("| Date | Discharge (cfs) | Gage Height (ft) | Code |")
        lines.append("|------|-----------------|-------------------|------|")
        for row in rows:
            date = row.get("peak_dt", "—")
            flow = row.get("peak_va", "—")
            ght = row.get("gage_ht", "—")
            code = row.get("peak_cd", "")
            marker = " **MAX**" if row is max_row else ""
            lines.append(f"| {date} | {flow}{marker} | {ght} | {code} |")

        lines.append("")
        lines.append("*Data from USGS Water Services (peak streamflow).*")
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
async def usgs_get_flood_status(
    ctx: Context,
    site_number: str,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Assess current flood conditions at a USGS site.

    Combines current instantaneous data with peak flow history and
    statistical context to determine whether conditions are normal,
    above normal, or at flood stage.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        client = _get_client(ctx)

        # Fetch current value
        iv_data = await client.get_json(
            "iv",
            {
                "sites": site_number,
                "parameterCd": "00060",
                "period": "P1D",
            },
        )

        ts_list = iv_data.get("value", {}).get("timeSeries", [])
        if not ts_list:
            return f"No current data available for site {site_number}."

        ts = ts_list[0]
        site_name = ts.get("sourceInfo", {}).get("siteName", site_number)
        unit = ts.get("variable", {}).get("unit", {}).get("unitCode", "cfs")

        all_vals = []
        for val_set in ts.get("values", []):
            all_vals.extend(val_set.get("value", []))

        if not all_vals:
            return f"No current readings for site {site_number}."

        # The latest reading is the current flow only if it is a measurement:
        # USGS writes the series' noDataValue (-999999) with a qualifier such
        # as Ice when there is none (see models.screen_series_values).
        _, screen = screen_series_values(ts)
        latest = screen["latest"]
        current_time = latest["datetime"]
        current_flow = None if latest["excluded_reason"] else float(latest["value"])
        if latest["excluded_reason"] == "non_numeric" and screen["valid"] == 0:
            return f"Error: Could not parse current flow value for site {site_number}."

        # Fetch peak history
        peak_flow = None
        peak_date = None
        try:
            peak_rows = await client.get_peak({"site_no": site_number})
            for row in peak_rows:
                try:
                    flow = float(row.get("peak_va", "0"))
                    if peak_flow is None or flow > peak_flow:
                        peak_flow = flow
                        peak_date = row.get("peak_dt", "?")
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

        # Fetch monthly stats for context
        median_flow = None
        try:
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            stat_rows = await client.get_rdb(
                "stat",
                {
                    "sites": site_number,
                    "statReportType": "daily",
                    "statTypeCd": "median",
                    "parameterCd": "00060",
                },
            )
            month_str = f"{now.month}"
            day_str = f"{now.day}"
            for sr in stat_rows:
                if sr.get("month_nu") == month_str and sr.get("day_nu") == day_str:
                    try:
                        median_flow = float(sr.get("p50_va", ""))
                    except (ValueError, TypeError):
                        pass
                    break
        except Exception:
            pass

        # --- Official NWS flood stage (NWPS), when this site is a forecast point ---
        nwps_raw = await client.get_nwps_gauge(site_number)
        nws = _nwps_flood(nwps_raw) if nwps_raw else None

        # Streamflow anomaly vs the daily median — context in both paths, and
        # the *labelled status only* when the site has no NWS flood stage.
        anomaly = None
        if current_flow is not None and median_flow and median_flow > 0:
            ratio = current_flow / median_flow
            if ratio > 5.0:
                anomaly = "Much Above Normal"
            elif ratio > 3.0:
                anomaly = "Well Above Normal"
            elif ratio > 2.0:
                anomaly = "Above Normal"
            elif ratio > 1.5:
                anomaly = "Slightly Above Normal"
            elif ratio < 0.5:
                anomaly = "Below Normal"
            else:
                anomaly = "Normal"

        if nws is not None:
            status = nws["label"]
            flood_source = "NWS/NWPS"
        else:
            status = anomaly or "Unknown"
            flood_source = "USGS flow anomaly (not NWS flood stage)"

        pct_of_peak = None
        if current_flow is not None and peak_flow and peak_flow > 0:
            pct_of_peak = round(current_flow / peak_flow * 100, 1)

        result = {
            "site_number": site_number,
            "site_name": site_name,
            "current_flow_cfs": current_flow,
            "current_time": current_time,
            "status": status,
            "flood_source": flood_source,
        }
        if current_flow is None:
            result["current_flow_note"] = (
                f"The latest reading ({current_time}) is not a measurement (value "
                f"{latest['value']}, qualifiers {latest['qualifiers'] or 'none'}), so "
                "current flow and every flow ratio below are null."
            )
            result["readings_excluded_last_24h"] = screen["excluded"]
        if nws is not None:
            result["nws_lid"] = nws["lid"]
            result["nws_flood_category"] = nws["category"]
            if nws["forecast_category"]:
                result["nws_forecast_category"] = nws["forecast_category"]
            result["observed_stage"] = nws["observed_stage"]
            result["stage_unit"] = nws["stage_unit"]
            result["flood_thresholds"] = nws["thresholds"]
        else:
            result["note"] = (
                "No NWS flood thresholds for this site (not an NWS forecast "
                "point). 'status' is a streamflow anomaly vs the daily median, "
                "not flood stage."
            )
            if current_flow is not None and median_flow and median_flow > 0:
                result["flow_vs_median_ratio"] = round(current_flow / median_flow, 2)

        if median_flow is not None:
            result["median_flow_cfs"] = median_flow
            result["pct_of_median"] = (
                round(current_flow / median_flow * 100, 1)
                if current_flow is not None and median_flow > 0
                else None
            )
        if peak_flow is not None:
            result["peak_of_record_cfs"] = peak_flow
            result["peak_of_record_date"] = peak_date
            result["pct_of_peak"] = pct_of_peak

        if response_format == "json":
            import json

            return json.dumps(result, indent=2)

        lines = [f"## Flood Status — {site_name}"]
        lines.append(f"**Site**: {site_number}")
        if nws is not None:
            lid = f" {nws['lid']}" if nws["lid"] else ""
            lines.append(f"**Status**: **{status}** (NWS{lid} flood category)")
            if nws["observed_stage"] is not None:
                lines.append(
                    f"**Observed Stage**: {nws['observed_stage']:.2f} "
                    f"{nws['stage_unit']}"
                )
            if nws["forecast_category"]:
                lines.append(
                    f"**Forecast Flood Category**: "
                    f"{_NWS_CAT_LABEL.get(nws['forecast_category'], nws['forecast_category'])}"
                )
        else:
            lines.append(f"**Status**: **{status}**")
        if current_flow is not None:
            lines.append(f"**Current Flow**: {current_flow:,.1f} {unit}")
        else:
            lines.append(
                f"**Current Flow**: no data — latest reading is {latest['value']} "
                f"(qualifiers {latest['qualifiers'] or 'none'}), not a measurement"
            )
        lines.append(f"**As of**: {current_time}")
        lines.append("")

        if nws is None:
            lines.append(
                "> ⚠️ Not an NWS flood-forecast point — no official flood "
                "thresholds. The status above is a **streamflow anomaly** vs "
                "the daily median, *not* flood stage."
            )
            lines.append("")

        if median_flow is not None:
            pct = result.get("pct_of_median")
            lines.append(f"**Historical Median (today)**: {median_flow:,.1f} {unit}")
            if pct is not None:
                lines.append(f"**Current vs Median**: {pct:.0f}%")

        if peak_flow is not None:
            lines.append(f"**Peak of Record**: {peak_flow:,.0f} {unit} ({peak_date})")
            if pct_of_peak is not None:
                lines.append(f"**Current vs Peak**: {pct_of_peak:.1f}%")

        lines.append("")
        if nws is not None:
            lines.append("### NWS Flood Categories")
            lines.append("| Category | Stage | Flow |")
            lines.append("| --- | --- | --- |")
            for name in _NWS_CAT_ORDER:
                t = nws["thresholds"][name]
                s = (
                    f"{t['stage']:.2f} {nws['stage_unit']}"
                    if t["stage"] is not None
                    else "—"
                )
                fl = (
                    f"{t['flow']:,.0f} {nws['flow_unit']}"
                    if t["flow"] is not None
                    else "—"
                )
                lines.append(f"| {_NWS_CAT_LABEL[name]} | {s} | {fl} |")
            lines.append("")
            lines.append(
                "*Flood categories from NWS/NWPS; observations from USGS. "
                "Stage compared to official NWS flood-stage thresholds.*"
            )
        else:
            lines.append("### Streamflow Anomaly Tiers (not flood stage)")
            lines.append("- **Normal**: 0.5–1.5x daily median")
            lines.append("- **Slightly Above Normal**: 1.5–2x")
            lines.append("- **Above Normal**: 2–3x")
            lines.append("- **Well Above Normal**: 3–5x")
            lines.append("- **Much Above Normal**: >5x")
            lines.append("- **Below Normal**: <0.5x")
            lines.append("")
            lines.append(
                "*Data from USGS Water Services. This site is not an NWS "
                "flood-forecast point, so no official flood stage is available.*"
            )
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)
