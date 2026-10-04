"""Tools: ofs_get_forecast_at_point, ofs_compare_with_coops."""

from __future__ import annotations

from typing import Literal
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import OFSClient
from ..models import OFS_MODELS, OFSModel, OFSVariable
from ..server import mcp
from ..utils import (
    align_timeseries,
    clean_timeseries,
    cleanup_temp_file,
    compute_validation_stats,
    extract_point_timeseries,
    format_timeseries_table,
    handle_ofs_error,
)


def _get_client(ctx: Context) -> OFSClient:
    return ctx.request_context.lifespan_context["ofs_client"]


def _cap_series_json(result: dict, max_points: int = 2000) -> str:
    """Serialize a forecast result to JSON, capping the times/values series.

    A point forecast is a parallel times[]/values[] series; the json path would
    otherwise dump it whole. Keep the first ``max_points``, record
    n_points/total_points/truncated, and stamp retrieved_at (per CONVENTIONS.md).
    """
    times = result.get("times", []) or []
    values = result.get("values", []) or []
    total = len(times)
    truncated = total > max_points
    if truncated:
        times = times[:max_points]
        values = values[:max_points]
        result["times"] = times
        result["values"] = values
    result["n_points"] = len(times)
    result["total_points"] = total
    result["truncated"] = truncated
    result["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if truncated:
        result["hint"] = (
            f"Showing the first {len(times)} of {total} forecast points "
            "(truncated to limit response size)."
        )
    return json.dumps(result, indent=2)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ofs_get_forecast_at_point(
    ctx: Context,
    latitude: float,
    longitude: float,
    model: OFSModel,
    variable: OFSVariable = OFSVariable.WATER_LEVEL,
    max_distance_km: float = 100.0,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get an OFS model forecast time series at a geographic point.

    Connects to the NOAA THREDDS OPeNDAP server to lazily extract the
    forecast at the nearest model grid point without downloading the full
    gridded file. Falls back to S3 download if OPeNDAP is unavailable.

    Args:
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        model: OFS model to query (e.g., 'cbofs', 'ngofs2', 'wcofs').
        variable: Variable to retrieve — 'water_level', 'temperature', or 'salinity'.
        max_distance_km: Maximum distance to nearest grid point in km (default 100).
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_path: Path | None = None
    nc = None
    try:
        client = _get_client(ctx)
        model_info = OFS_MODELS.get(model.value, {})
        model_name = model_info.get("name", model.value.upper())
        datum = model_info.get("datum", "NAVD88")

        # Validate query point is within model domain
        domain = model_info.get("domain", {})
        if domain:
            lat_min = domain.get("lat_min", -90)
            lat_max = domain.get("lat_max", 90)
            lon_min = domain.get("lon_min", -180)
            lon_max = domain.get("lon_max", 180)
            if not (lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max):
                matching = []
                for m_key, m_info in OFS_MODELS.items():
                    d = m_info.get("domain", {})
                    if d.get("lat_min", -90) <= latitude <= d.get(
                        "lat_max", 90
                    ) and d.get("lon_min", -180) <= longitude <= d.get("lon_max", 180):
                        matching.append(f"{m_info['short_name']} ({m_key})")
                suggestion = (
                    f" Try: {', '.join(matching)}."
                    if matching
                    else " Use ofs_find_models_for_location to find a suitable model."
                )
                return (
                    f"Location ({latitude:.4f}°N, {longitude:.4f}°E) is outside the "
                    f"{model_name} domain ({lat_min}–{lat_max}°N, "
                    f"{lon_min}–{lon_max}°E).{suggestion}"
                )

        # Variable labels and units
        var_labels = {
            "water_level": ("Water Level", "m"),
            "temperature": ("Water Temperature", "°C"),
            "salinity": ("Salinity", "PSU"),
        }
        var_label, var_units = var_labels.get(variable.value, (variable.value, ""))

        # --- Try OPeNDAP first (lazy loading — most efficient) ---
        opendap_error = None
        from_s3_fallback = False
        try:
            nc = client.open_opendap(model.value)
            data = extract_point_timeseries(
                nc, model.value, variable.value, latitude, longitude, max_distance_km
            )
            data_source = "NOAA THREDDS OPeNDAP (FMRC aggregation)"
            cycle_info = "FMRC (latest nowcast + forecast)"

        except RuntimeError as e:
            opendap_error = str(e)
            nc = None

        # --- Fallback: download f001.nc from S3 ---
        if nc is None:
            cycle = await client.resolve_latest_cycle(model.value)
            if not cycle:
                return (
                    f"No {model_name} cycles found on S3. "
                    f"Use ofs_list_cycles to check availability.\n\n"
                    f"OPeNDAP error: {opendap_error}"
                )
            date_str, hour_str = cycle
            from_s3_fallback = True

            import netCDF4

            # One S3 file is a single forecast hour and 50–120 MB; models
            # without an FMRC aggregation have no practical way to serve a
            # continuous series, so we fetch one hour and return it as an
            # explicit limited snapshot rather than 404-looping gigabytes.
            url = client.build_s3_url(model.value, date_str, hour_str, "f", 1)
            tmp_path = await client.download_netcdf(url)
            nc = netCDF4.Dataset(str(tmp_path), "r")
            data = extract_point_timeseries(
                nc, model.value, variable.value, latitude, longitude, max_distance_km
            )
            d_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            data_source = f"NOAA OFS S3 (single forecast hour, {d_fmt} {hour_str}z)"
            cycle_info = (
                f"{d_fmt} {hour_str}z (single forecast hour — limited time series)"
            )

        # Clean timeseries: sort, dedup, extract longest contiguous block
        cleaned = clean_timeseries(data["times"], data["values"])
        times = cleaned["times"]
        values = cleaned["values"]

        if not times:
            # Zero valid points = genuinely on land / dry-masked / off-grid.
            return (
                f"No valid {var_label} data at "
                f"({latitude:.4f}°N, {longitude:.4f}°E) from {model_name}. "
                "The nearest grid cell may be on land, dry/masked, or outside "
                "the model domain."
            )
        if cleaned["is_sparse"] and not from_s3_fallback:
            # FMRC stitched series too fragmented to be useful (not "on land").
            return (
                f"{model_name} returned only a sparse, fragmented series at "
                f"({latitude:.4f}°N, {longitude:.4f}°E) "
                f"({len(times)} point(s)) — not enough for a reliable time "
                "series. Try another cycle or model."
            )
        # Otherwise: a valid series, or a legitimate single-hour S3 snapshot
        # (cycle_info already flags the limitation). Don't discard real data.

        # Build cleanup metadata for transparency
        cleanup_notes = []
        if cleaned["n_duplicates_removed"] > 0:
            cleanup_notes.append(
                f"{cleaned['n_duplicates_removed']} duplicate timestamps removed"
            )
        if cleaned["n_segments"] > 1:
            cleanup_notes.append(
                f"{cleaned['n_segments']} segments found, kept longest "
                f"({len(times)} points)"
            )

        if response_format == "json":
            result = {
                "query_lat": latitude,
                "query_lon": longitude,
                "model": model.value,
                "variable": variable.value,
                "nearest_point_lat": data["lat"],
                "nearest_point_lon": data["lon"],
                "distance_km": data["distance_km"],
                "datum": datum,
                "units": var_units,
                "cycle": cycle_info,
                "n_points": len(times),
                "times": times,
                "values": values,
            }
            if cleanup_notes:
                result["cleanup_notes"] = cleanup_notes
            return _cap_series_json(result)

        metadata = [
            f"Query location: ({latitude:.4f}°N, {longitude:.4f}°E)",
            f"Nearest model point: ({data['lat']:.4f}°N, {data['lon']:.4f}°E), "
            f"{data['distance_km']:.1f} km away",
            f"Datum: {datum}",
            f"Cycle: {cycle_info}",
            f"Source: {data_source}",
        ]
        if cleanup_notes:
            metadata.append(f"Cleanup: {'; '.join(cleanup_notes)}")

        return format_timeseries_table(
            times=times,
            values=values,
            title=f"{model_name} — {var_label} Forecast",
            metadata_lines=metadata,
            units=var_units,
        )

    except Exception as e:
        return handle_ofs_error(e, model.value)
    finally:
        if nc:
            try:
                nc.close()
            except Exception:
                pass
        cleanup_temp_file(tmp_path)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ofs_compare_with_coops(
    ctx: Context,
    station_id: str,
    model: OFSModel,
    hours_to_compare: int = 24,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Compare OFS model water level forecast against CO-OPS observations at a station.

    Fetches the model forecast at the nearest grid point to the CO-OPS station
    and compares it with the observed water level. Computes bias, RMSE, MAE,
    peak error, and correlation.

    Args:
        station_id: CO-OPS station ID (e.g., '8571892' for Cambridge, MD).
        model: OFS model identifier (e.g., 'cbofs', 'ngofs2').
        hours_to_compare: Hours of comparison period (default 24, max 96).
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_path: Path | None = None
    nc = None
    try:
        client = _get_client(ctx)
        hours_to_compare = max(1, min(96, hours_to_compare))

        model_info = OFS_MODELS.get(model.value, {})
        model_name = model_info.get("name", model.value.upper())
        model_datum = model_info.get("datum", "NAVD88")

        # CO-OPS datum mapping
        coops_datum = "NAVD" if "NAVD" in model_datum else "MSL"

        # --- Step 1: Get CO-OPS station metadata ---
        station_meta_url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}.json"
        httpx_client = await client._get_client()
        meta_resp = await httpx_client.get(station_meta_url)

        station_name = station_id
        station_lat = None
        station_lon = None

        if meta_resp.status_code == 200:
            meta = meta_resp.json()
            stations = meta.get("stations", [])
            if stations:
                s = stations[0]
                station_name = s.get("name", station_id)
                station_lat = float(s.get("lat", 0))
                station_lon = float(s.get("lng", 0))

        if station_lat is None:
            return (
                f"Could not retrieve metadata for CO-OPS station '{station_id}'. "
                "Verify the station ID using the CO-OPS MCP server or "
                "https://tidesandcurrents.noaa.gov/stationhome.html"
            )

        # --- Step 1b: Validate station is within model domain ---
        domain = model_info.get("domain", {})
        if domain:
            lat_min = domain.get("lat_min", -90)
            lat_max = domain.get("lat_max", 90)
            lon_min = domain.get("lon_min", -180)
            lon_max = domain.get("lon_max", 180)
            if not (
                lat_min <= station_lat <= lat_max and lon_min <= station_lon <= lon_max
            ):
                # Find which models DO cover this location
                matching = []
                for m_key, m_info in OFS_MODELS.items():
                    d = m_info.get("domain", {})
                    if d.get("lat_min", -90) <= station_lat <= d.get(
                        "lat_max", 90
                    ) and d.get("lon_min", -180) <= station_lon <= d.get(
                        "lon_max", 180
                    ):
                        matching.append(f"{m_info['short_name']} ({m_key})")
                suggestion = (
                    f" Try: {', '.join(matching)}."
                    if matching
                    else " Use ofs_find_models_for_location to find a suitable model."
                )
                return (
                    f"Station {station_id} ({station_name}) at "
                    f"({station_lat:.4f}°N, {station_lon:.4f}°E) is outside the "
                    f"{model_name} domain ({lat_min}–{lat_max}°N, {lon_min}–{lon_max}°E)."
                    f"{suggestion}"
                )

        # --- Step 2: Fetch model forecast at station location ---
        opendap_error = None
        from_s3_fallback = False
        try:
            nc = client.open_opendap(model.value)
            model_data = extract_point_timeseries(
                nc, model.value, "water_level", station_lat, station_lon
            )
        except RuntimeError as e:
            opendap_error = str(e)
            nc = None

        if nc is None:
            cycle = await client.resolve_latest_cycle(model.value)
            if not cycle:
                return (
                    f"No {model_name} cycles found. "
                    f"Use ofs_list_cycles to check availability.\n\n"
                    f"OPeNDAP error: {opendap_error}"
                )
            date_str, hour_str = cycle
            from_s3_fallback = True
            import netCDF4

            url = client.build_s3_url(model.value, date_str, hour_str, "f", 1)
            tmp_path = await client.download_netcdf(url)
            nc = netCDF4.Dataset(str(tmp_path), "r")
            model_data = extract_point_timeseries(
                nc, model.value, "water_level", station_lat, station_lon
            )

        # Clean model timeseries: dedup, sort, extract longest contiguous block
        cleaned = clean_timeseries(model_data["times"], model_data["values"])
        model_times = cleaned["times"]
        model_values = cleaned["values"]

        if not model_times:
            return (
                f"No {model_name} water level data near CO-OPS station "
                f"{station_id} ({station_name}) at ({station_lat:.4f}°N, "
                f"{station_lon:.4f}°E) — the nearest grid cell may be on "
                "land/masked or outside the model domain."
            )
        if from_s3_fallback and cleaned["is_sparse"]:
            # One S3 hour can't be compared to an observation time series.
            # Either the model has no FMRC aggregation, or it has one that
            # failed to open (THREDDS is intermittently unavailable).
            if model_info.get("has_fmrc", False):
                return (
                    f"{model_name}'s THREDDS FMRC aggregation could not be "
                    f"opened ({opendap_error}), and the S3 fallback holds only "
                    f"a single forecast hour (files are 50–120 MB each) — not "
                    f"enough to validate against the CO-OPS series at "
                    f"{station_name}. THREDDS outages are usually brief; try "
                    f"again shortly."
                )
            return (
                f"{model_name} has no FMRC aggregation, so only a single "
                f"forecast hour is retrievable from S3 (files are 50–120 MB "
                f"each) — not enough to validate against the CO-OPS series at "
                f"{station_name}. Use an FMRC-backed model (e.g. cbofs, dbofs, "
                f"gomofs) for this station, or query the model point directly "
                f"with ofs_get_forecast_at_point."
            )
        if cleaned["is_sparse"]:
            return (
                f"{model_name} returned too sparse/fragmented a series near "
                f"CO-OPS station {station_id} ({len(model_times)} point(s)) "
                "to validate reliably."
            )

        # --- Step 3: Determine comparison time window ---
        # Use the model's time range, clipped to hours_to_compare
        def parse_dt(s: str) -> datetime:
            return datetime.strptime(s[:16], "%Y-%m-%d %H:%M").replace(
                tzinfo=timezone.utc
            )

        model_start = parse_dt(model_times[0])
        model_end = parse_dt(model_times[-1])

        # For comparison, use the PAST hours_to_compare hours ending at "now"
        now_utc = datetime.now(timezone.utc)
        obs_end = min(now_utc, model_end)
        obs_start = max(obs_end - timedelta(hours=hours_to_compare), model_start)

        begin_str = obs_start.strftime("%Y%m%d %H:%M")
        end_str = obs_end.strftime("%Y%m%d %H:%M")

        # --- Step 4: Fetch CO-OPS observations ---
        obs_data = await client.fetch_coops_observations(
            station_id, begin_str, end_str, coops_datum
        )

        obs_list = obs_data.get("data", [])
        if not obs_list:
            return (
                f"No CO-OPS observations available for station {station_id} "
                f"({station_name}) from {begin_str} to {end_str}.\n\n"
                f"Requested datum: {coops_datum}. "
                "The station may not report in this datum. Try a different datum."
            )

        obs_times = [entry["t"] for entry in obs_list]
        obs_values = []
        for entry in obs_list:
            try:
                obs_values.append(float(entry["v"]))
            except (ValueError, KeyError):
                obs_values.append(None)

        # Filter None values
        obs_times_clean = [t for t, v in zip(obs_times, obs_values) if v is not None]
        obs_values_clean = [v for v in obs_values if v is not None]

        # --- Step 5: Clip model to same time window ---
        model_clipped_times = []
        model_clipped_values = []
        for t, v in zip(model_times, model_values):
            try:
                dt = parse_dt(t)
                if obs_start <= dt <= obs_end:
                    model_clipped_times.append(t)
                    model_clipped_values.append(v)
            except ValueError:
                continue

        # --- Step 6: Align and compute stats ---
        common_times, aligned_model, aligned_obs = align_timeseries(
            model_clipped_times,
            model_clipped_values,
            obs_times_clean,
            obs_values_clean,
        )

        stats = compute_validation_stats(aligned_model, aligned_obs)

        grid_dist = model_data["distance_km"]

        if response_format == "json":
            return json.dumps(
                {
                    "station_id": station_id,
                    "station_name": station_name,
                    "station_lat": station_lat,
                    "station_lon": station_lon,
                    "model": model.value,
                    "model_datum": model_datum,
                    "obs_datum": coops_datum,
                    "model_grid_distance_km": grid_dist,
                    "period_start": obs_start.isoformat(),
                    "period_end": obs_end.isoformat(),
                    "stats": stats,
                    "comparison_times": common_times,
                    "model_values": aligned_model,
                    "obs_values": aligned_obs,
                },
                indent=2,
            )

        # --- Markdown output ---
        def fmt_stat(v: float | None, suffix: str = " m") -> str:
            if v is None:
                return "N/A"
            return f"{v:+.3f}{suffix}" if suffix == " m" else f"{v:.4f}"

        lines = [
            f"## {model_name} vs CO-OPS Observations",
            f"**Station**: {station_id} — {station_name}",
            f"**Location**: ({station_lat:.4f}°N, {station_lon:.4f}°E)",
            f"**Model grid point**: {grid_dist:.1f} km from station",
            f"**Period**: {obs_start.strftime('%Y-%m-%d %H:%M')} – "
            f"{obs_end.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Model datum**: {model_datum} | **Obs datum**: {coops_datum}",
            "",
        ]

        if stats["n"] == 0:
            lines.append(
                "*No overlapping data points found for the comparison period. "
                "Model time series may not overlap with observation period.*"
            )
            return "\n".join(lines)

        lines += [
            "### Validation Statistics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Bias (mean error) | {fmt_stat(stats['bias'])} |",
            f"| RMSE | {fmt_stat(stats['rmse'])} |",
            f"| MAE | {fmt_stat(stats['mae'])} |",
            f"| Peak Error | {fmt_stat(stats['peak_error'])} |",
            f"| Correlation (R) | {fmt_stat(stats['correlation'], '')} |",
            f"| Comparison Points | {stats['n']} |",
            "",
        ]

        # Hourly sample of comparison table
        step = max(1, len(common_times) // 48)
        show_times = common_times[::step]
        show_model = aligned_model[::step]
        show_obs = aligned_obs[::step]
        show_err = [m - o for m, o in zip(show_model, show_obs)]

        if len(show_times) < len(common_times):
            lines.append(
                f"*Showing every {step}th of {len(common_times)} comparison points*"
            )
        lines += [
            "",
            "### Time Series Comparison",
            "",
            "| Time (UTC) | Model (m) | Observed (m) | Error (m) |",
            "| --- | --- | --- | --- |",
        ]
        for t, m_v, o_v, e_v in zip(show_times, show_model, show_obs, show_err):
            lines.append(f"| {t} | {m_v:.3f} | {o_v:.3f} | {e_v:+.3f} |")

        lines += [
            "",
            f"> ⚠️ Small systematic offsets may exist due to datum differences "
            f"({model_datum} vs CO-OPS {coops_datum}) and distance between "
            f"CO-OPS station and nearest model grid point ({grid_dist:.1f} km).",
            "",
            f"*Data: {model_name} via NOAA THREDDS/S3 + CO-OPS API.*",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ofs_error(e, model.value)
    finally:
        if nc:
            try:
                nc.close()
            except Exception:
                pass
        cleanup_temp_file(tmp_path)
