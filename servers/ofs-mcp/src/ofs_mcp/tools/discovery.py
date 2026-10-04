"""Tools: ofs_list_models, ofs_get_model_info, ofs_list_cycles, ofs_find_models_for_location."""

from __future__ import annotations

from typing import Literal
import json
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import OFSClient
from ..models import OFS_MODELS, OFSModel
from ..server import mcp
from ..utils import handle_ofs_error


def _get_client(ctx: Context) -> OFSClient:
    return ctx.request_context.lifespan_context["ofs_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ofs_list_models(
    ctx: Context, response_format: Literal["markdown", "json"] = "markdown"
) -> str:
    """List all supported NOAA OFS regional ocean models with key metadata.

    Returns model names, grid types, geographic coverage, cycle schedules,
    forecast lengths, and variables available.

    Args:
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if response_format == "json":
            return json.dumps(
                {
                    model_id: {
                        "name": info["name"],
                        "short_name": info["short_name"],
                        "grid_type": info["grid_type"],
                        "domain_desc": info["domain_desc"],
                        "domain": info["domain"],
                        "states": info["states"],
                        "cycles": info["cycles"],
                        "forecast_hours": info["forecast_hours"],
                        "datum": info["datum"],
                        "variables": list(info.get("nc_vars", {}).keys()),
                    }
                    for model_id, info in OFS_MODELS.items()
                },
                indent=2,
            )

        lines = [
            "# NOAA Operational Forecast System (OFS) Models",
            "",
            "Regional hydrodynamic models providing 48–72 hour water level, "
            "temperature, and salinity forecasts at 6-min intervals.",
            "",
            "| Model ID | Name | Grid | Region | Cycles/day | Forecast | Variables |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]

        for model_id, info in OFS_MODELS.items():
            n_cycles = len(info["cycles"])
            vars_list = "WL, T, S"  # water level, temperature, salinity
            lines.append(
                f"| `{model_id}` | {info['name']} | {info['grid_type'].upper()} "
                f"| {info['domain_desc'][:40]} | {n_cycles}× daily "
                f"| {info['forecast_hours']}h | {vars_list} |"
            )

        lines += [
            "",
            "**Variables**: WL = water level (m, relative to datum), "
            "T = water temperature (°C), S = salinity (PSU)",
            "",
            "Use `ofs_get_model_info` for detailed specs, "
            "`ofs_list_cycles` to check data availability, "
            "`ofs_find_models_for_location` to find models covering a lat/lon.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ofs_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ofs_get_model_info(
    ctx: Context,
    model: OFSModel,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get detailed specifications for a specific OFS model.

    Returns grid type, spatial domain, cycle schedule, vertical levels,
    datum, available variables, and data access URLs.

    Args:
        model: OFS model identifier (e.g., 'cbofs', 'ngofs2').
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        info = OFS_MODELS.get(model.value)
        if not info:
            return f"Unknown model '{model.value}'. Use ofs_list_models to see available models."

        thredds_id = info.get("thredds_id", model.value.upper())
        has_fmrc = info.get("has_fmrc", False)
        if has_fmrc:
            thredds_url = (
                f"https://opendap.co-ops.nos.noaa.gov/thredds/dodsC/"
                f"{thredds_id}/fmrc/Aggregated_7_day_{thredds_id}_Fields_Forecast_best.ncd"
            )
        else:
            thredds_url = None
        s3_prefix = f"https://noaa-nos-ofs-pds.s3.amazonaws.com/{model.value}/netcdf/YYYY/MM/DD/"
        s3_file_type = info.get("s3_file_type", "fields")
        s3_example = (
            f"https://noaa-nos-ofs-pds.s3.amazonaws.com/{model.value}/netcdf/"
            f"YYYY/MM/DD/{model.value}.t{info['cycles'][0]}z."
            f"YYYYMMDD.{s3_file_type}.f001.nc"
        )

        nc_vars = info.get("nc_vars", {})

        if response_format == "json":
            result = {
                "model_id": model.value,
                **info,
                "s3_prefix": s3_prefix,
                "s3_example": s3_example,
            }
            if thredds_url:
                result["thredds_fmrc_url"] = thredds_url
            else:
                result["thredds_note"] = "No FMRC aggregation; use S3 for data access"
            return json.dumps(result, indent=2)

        domain = info["domain"]
        lines = [
            f"## {info['name']} ({info['short_name']})",
            "",
            f"- **Model ID**: `{model.value}`",
            f"- **Grid type**: {info['grid_type'].upper()} "
            f"({'unstructured triangular' if info['grid_type'] == 'fvcom' else 'structured curvilinear'})",
            f"- **Domain**: {info['domain_desc']}",
            f"- **Bounding box**: {domain['lat_min']}–{domain['lat_max']}°N, "
            f"{domain['lon_min']}–{domain['lon_max']}°E",
            f"- **States covered**: {', '.join(info['states'])}",
            f"- **Cycles**: {', '.join(info['cycles'])} UTC ({len(info['cycles'])}× daily)",
            f"- **Forecast length**: {info['forecast_hours']} hours",
            f"- **Nowcast length**: {info['nowcast_hours']} hours",
            f"- **Grid size**: {info['grid_size']}",
            f"- **Vertical layers**: {info['vertical_layers']}",
            f"- **Datum**: {info['datum']}",
            "",
            "### Variables",
            "",
            "| Variable | NetCDF name | Description |",
            "| --- | --- | --- |",
            f"| `water_level` | `{nc_vars.get('water_level', 'zeta')}` | "
            f"Surface elevation (m, relative to {info['datum']}) |",
            f"| `temperature` | `{nc_vars.get('temperature', 'temp')}` | "
            "Water temperature at surface (°C) |",
            f"| `salinity` | `{nc_vars.get('salinity', 'salt')}` | "
            "Salinity at surface (PSU) |",
            "",
            "### Data Access",
            "",
        ]
        if thredds_url:
            lines.append(f"- **THREDDS OPeNDAP (FMRC)**: `{thredds_url}`")
        else:
            lines.append(
                "- **THREDDS OPeNDAP**: *No FMRC aggregation available — use S3*"
            )
        lines += [
            f"- **S3 prefix**: `{s3_prefix}`",
            f"- **S3 example**: `{s3_example}`",
            "",
            "Use `ofs_list_cycles` to check available cycles. "
            "Use `ofs_get_forecast_at_point` to extract forecasts at a location.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ofs_error(e, model.value)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ofs_list_cycles(
    ctx: Context,
    model: OFSModel,
    date: str | None = None,
    num_days: int = 2,
) -> str:
    """List available OFS forecast cycles on AWS S3 for a given model and date range.

    Checks S3 for available forecast files to determine which cycles have been
    published. Useful before calling ofs_get_forecast_at_point.

    Args:
        model: OFS model identifier (e.g., 'cbofs', 'ngofs2').
        date: Specific date in YYYY-MM-DD format. Default: today UTC.
        num_days: Number of past days to check (1–7). Default: 2.
    """
    try:
        client = _get_client(ctx)
        num_days = max(1, min(7, num_days))

        model_info = OFS_MODELS.get(model.value, {})
        cycles = model_info.get("cycles", ["00", "06", "12", "18"])
        model_label = model_info.get("name", model.value.upper())

        if date:
            try:
                end_date = datetime.strptime(date, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return f"Invalid date format '{date}'. Use YYYY-MM-DD."
        else:
            end_date = datetime.now(timezone.utc)

        results = []
        for day_offset in range(num_days):
            check_date = end_date - timedelta(days=day_offset)
            date_str = check_date.strftime("%Y%m%d")
            date_label = check_date.strftime("%Y-%m-%d")

            for cycle in sorted(cycles, reverse=True):
                url = client.build_s3_url(model.value, date_str, cycle, "f", 1)
                exists = await client.check_file_exists(url)
                results.append(
                    {
                        "date": date_label,
                        "cycle": f"{cycle}z",
                        "status": "Available" if exists else "Not available",
                        "url": url if exists else "",
                    }
                )

        available = [r for r in results if r["status"] == "Available"]

        lines = [
            f"## OFS Forecast Cycles — {model_label}",
            f"**Checking**: last {num_days} day(s) | "
            f"**Available**: {len(available)} of {len(results)} cycles",
            "",
            "| Date | Cycle | Status | First Forecast File |",
            "| --- | --- | --- | --- |",
        ]
        for r in results:
            url_cell = f"`{r['url']}`" if r["url"] else "—"
            lines.append(f"| {r['date']} | {r['cycle']} | {r['status']} | {url_cell} |")

        lines.append("")
        if available:
            latest = available[0]
            lines.append(
                f"*Latest available: **{latest['date']} {latest['cycle']}**. "
                f"Use ofs_get_forecast_at_point to retrieve data.*"
            )
        else:
            lines.append(
                f"*No cycles found for {model.value.upper()}. "
                "OFS products typically arrive ~2 hours after cycle time. "
                "Try again later or check a wider date range.*"
            )

        return "\n".join(lines)

    except Exception as e:
        return handle_ofs_error(e, model.value)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ofs_find_models_for_location(
    ctx: Context,
    latitude: float,
    longitude: float,
) -> str:
    """Find which OFS models cover a given latitude/longitude location.

    Uses model bounding boxes to identify all models whose domain includes
    the specified point. Larger regional models may cover the area at
    coarser resolution than smaller local models.

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
    """
    try:
        matching = []
        for model_id, info in OFS_MODELS.items():
            domain = info["domain"]
            if (
                domain["lat_min"] <= latitude <= domain["lat_max"]
                and domain["lon_min"] <= longitude <= domain["lon_max"]
            ):
                matching.append(
                    {
                        "model_id": model_id,
                        "name": info["name"],
                        "grid_type": info["grid_type"],
                        "grid_size": info["grid_size"],
                        "cycles_per_day": len(info["cycles"]),
                        "forecast_hours": info["forecast_hours"],
                        "datum": info["datum"],
                    }
                )

        if not matching:
            # Find closest model domain
            closest = None
            min_dist = float("inf")
            for model_id, info in OFS_MODELS.items():
                domain = info["domain"]
                center_lat = (domain["lat_min"] + domain["lat_max"]) / 2
                center_lon = (domain["lon_min"] + domain["lon_max"]) / 2
                from ..utils import haversine

                dist = haversine(latitude, longitude, center_lat, center_lon)
                if dist < min_dist:
                    min_dist = dist
                    closest = model_id
            return (
                f"No OFS model domain covers ({latitude:.4f}°N, {longitude:.4f}°E). "
                f"The closest model is **{closest.upper()}** "
                f"({OFS_MODELS[closest]['name']}), ~{min_dist:.0f} km away.\n\n"
                "Use ofs_list_models to see all model domains."
            )

        lines = [
            f"## OFS Models Covering ({latitude:.4f}°N, {longitude:.4f}°E)",
            "",
            f"**{len(matching)} model(s) found** covering this location.",
            "",
            "| Model | Name | Grid | Resolution | Cycles/day | Forecast |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for m in matching:
            lines.append(
                f"| `{m['model_id']}` | {m['name']} | {m['grid_type'].upper()} "
                f"| {m['grid_size']} | {m['cycles_per_day']}× daily | {m['forecast_hours']}h |"
            )

        lines += [
            "",
            "Use `ofs_get_forecast_at_point` with any of these model IDs to retrieve forecast data.",
            "Smaller domains generally provide higher spatial resolution for coastal areas.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ofs_error(e)
