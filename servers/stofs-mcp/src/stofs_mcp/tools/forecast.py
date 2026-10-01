"""Tools: stofs_get_station_forecast, stofs_get_point_forecast, stofs_get_max_water_level."""

from __future__ import annotations

from typing import Literal
import json
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import STOFSClient
from ..models import (
    MODEL_DATUMS,
    Region,
    STOFSModel,
    STOFSProduct,
    get_model_label,
)
from ..server import mcp
from ..utils import (
    _haversine,
    cleanup_temp_file,
    extract_point_from_opendap,
    find_nearest_station,
    format_timeseries_table,
    get_opendap_region,
    handle_stofs_error,
    parse_station_netcdf,
    resolve_cycle,
)


def _get_client(ctx: Context) -> STOFSClient:
    return ctx.request_context.lifespan_context["stofs_client"]


def _cap_series_json(result: dict, max_points: int = 2000) -> str:
    """Serialize a forecast result to JSON, capping the times/values series.

    A station/point forecast is a long parallel times[]/values[] series (STOFS
    runs ~1,860 points); the json path would otherwise dump it whole and flood
    the model's context. Keep the first ``max_points`` (the near-term forecast),
    record n_points/total_points/truncated, and stamp retrieved_at (per
    CONVENTIONS.md).
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
async def stofs_get_station_forecast(
    ctx: Context,
    station_id: str,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    product: STOFSProduct = STOFSProduct.CWL,
    cycle_date: str | None = None,
    cycle_hour: str | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get STOFS water level forecast time series at a specific CO-OPS station.

    Downloads the station NetCDF file from AWS S3 (~2–10 MB) and extracts
    the full forecast time series for the specified station.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        model: '2d_global' (global, 4x daily) or '3d_atlantic' (US East/Gulf, 1x daily).
        product: 'cwl' (combined), 'htp' (tidal only), 'swl' (surge only).
                 Note: 3D-Atlantic only supports 'cwl'.
        cycle_date: Date in YYYY-MM-DD format. Default: latest available.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest available.
        response_format: 'markdown' (default) or 'json'.
    """
    tmp_path: Path | None = None
    try:
        client = _get_client(ctx)

        # Validate 3D product limitation
        if model.value == "3d_atlantic" and product.value != "cwl":
            return (
                "STOFS-3D-Atlantic only provides the 'cwl' (combined water level) product. "
                "For tidal ('htp') or surge ('swl') products, use model='2d_global'."
            )

        # Resolve cycle
        cycle = await resolve_cycle(client, model.value, cycle_date, cycle_hour)
        if not cycle:
            return (
                f"No STOFS-{'2D-Global' if model.value == '2d_global' else '3D-Atlantic'} "
                "cycles found for the specified date. "
                "Use stofs_list_cycles to check available data."
            )
        date_str, hour_str = cycle

        # Build URL and download
        url = client.build_station_url(model.value, date_str, hour_str, product.value)
        tmp_path = await client.download_netcdf(url)

        # Parse
        data = parse_station_netcdf(tmp_path, station_id)

        times = data["times"]
        values = data["values"]

        if not times:
            return (
                f"No valid data found for station {station_id} in this STOFS cycle. "
                "The station may be in a dry area or the data may have fill values."
            )

        datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = get_model_label(model.value, date_str)
        product_label = {
            "cwl": "Combined Water Level (tide + surge)",
            "htp": "Harmonic Tidal Prediction",
            "swl": "Surge Water Level (non-tidal residual)",
        }.get(product.value, product.value)

        if response_format == "json":
            return _cap_series_json(
                {
                    "station_id": station_id,
                    "model": model.value,
                    "product": product.value,
                    "cycle_date": date_str,
                    "cycle_hour": hour_str,
                    "datum": datum,
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "model_start": data.get("model_start"),
                    "model_end": data.get("model_end"),
                    "times": times,
                    "values": values,
                }
            )

        return format_timeseries_table(
            times=times,
            values=values,
            title=f"{model_label} Forecast — Station {station_id}",
            metadata_lines=[
                f"Model: {model_label}",
                f"Product: {product_label}",
                f"Cycle: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z",
                f"Datum: {datum}",
                f"Lat/Lon: {data.get('lat', '?')}, {data.get('lon', '?')}",
            ],
        )

    except Exception as e:
        return handle_stofs_error(e, model.value)
    finally:
        cleanup_temp_file(tmp_path)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def stofs_get_point_forecast(
    ctx: Context,
    latitude: float,
    longitude: float,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    product: STOFSProduct = STOFSProduct.CWL,
    cycle_date: str | None = None,
    cycle_hour: str | None = None,
    max_distance_km: float = 50.0,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get STOFS forecast at an arbitrary lat/lon by finding the nearest station.

    Downloads the station file and finds the closest STOFS output point to
    the requested location.

    Args:
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        model: '2d_global' or '3d_atlantic'.
        product: 'cwl', 'htp', or 'swl' (3D only supports 'cwl').
        cycle_date: Date in YYYY-MM-DD format. Default: latest.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest.
        max_distance_km: Maximum search radius to nearest station (default 50 km).
        response_format: 'markdown' or 'json'.
    """
    tmp_path: Path | None = None
    try:
        client = _get_client(ctx)

        if model.value == "3d_atlantic" and product.value != "cwl":
            return "STOFS-3D-Atlantic only supports product='cwl'."

        cycle = await resolve_cycle(client, model.value, cycle_date, cycle_hour)
        if not cycle:
            return (
                "No STOFS cycles found. Use stofs_list_cycles to check available data."
            )
        date_str, hour_str = cycle

        url = client.build_station_url(model.value, date_str, hour_str, product.value)
        tmp_path = await client.download_netcdf(url)

        # Get all station metadata first
        meta = parse_station_netcdf(tmp_path)
        station_names = meta["station_names"]
        lats = meta["lats"]
        lons = meta["lons"]

        if not lats or not lons:
            return "Could not read station coordinates from the STOFS file."

        result = find_nearest_station(
            latitude, longitude, lats, lons, station_names, max_distance_km
        )
        if result is None:
            return (
                f"No STOFS station found within {max_distance_km} km of "
                f"({latitude:.4f}, {longitude:.4f}).\n\n"
                "Suggestions:\n"
                "- Increase max_distance_km\n"
                "- Try model='2d_global' which has ~385 stations (vs ~108 for 3D)\n"
                "- Use stofs_get_gridded_forecast for any lat/lon (uses OPeNDAP regular grid)\n"
                "- Verify the coordinates are in a coastal area"
            )

        nearest_idx, nearest_name, distance_km = result

        # Extract data for nearest station
        data = parse_station_netcdf(tmp_path, nearest_name.strip())
        times = data["times"]
        values = data["values"]

        datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = get_model_label(model.value, date_str)

        if response_format == "json":
            return _cap_series_json(
                {
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "nearest_station": nearest_name.strip(),
                    "distance_km": round(distance_km, 2),
                    "model": model.value,
                    "cycle_date": date_str,
                    "cycle_hour": hour_str,
                    "datum": datum,
                    "times": times,
                    "values": values,
                }
            )

        return format_timeseries_table(
            times=times,
            values=values,
            title=f"{model_label} Point Forecast — ({latitude:.4f}°, {longitude:.4f}°)",
            metadata_lines=[
                f"Nearest STOFS station: {nearest_name.strip()}",
                f"Distance to nearest station: {distance_km:.1f} km",
                f"Cycle: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z",
                f"Datum: {datum}",
            ],
        )

    except Exception as e:
        return handle_stofs_error(e, model.value)
    finally:
        cleanup_temp_file(tmp_path)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def stofs_get_max_water_level(
    ctx: Context,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    cycle_date: str | None = None,
    cycle_hour: str | None = None,
    top_n: int = 20,
    region: Region | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get the stations with the highest predicted water levels in a STOFS cycle.

    Computes the maximum water level across all forecast timesteps for each
    station, then returns the top N sorted by peak value. Uses station files
    (not the large gridded maxele file).

    Args:
        model: '2d_global' or '3d_atlantic'.
        cycle_date: Date in YYYY-MM-DD format. Default: latest.
        cycle_hour: Cycle hour. Default: latest.
        top_n: Number of top stations to return (default 20).
        region: Optional region filter ('east_coast', 'gulf', etc.).
        response_format: 'markdown' or 'json'.
    """
    tmp_path: Path | None = None
    try:
        import numpy as np
        import netCDF4

        client = _get_client(ctx)

        cycle = await resolve_cycle(client, model.value, cycle_date, cycle_hour)
        if not cycle:
            return (
                "No STOFS cycles found. Use stofs_list_cycles to check available data."
            )
        date_str, hour_str = cycle

        url = client.build_station_url(model.value, date_str, hour_str, "cwl")
        tmp_path = await client.download_netcdf(url)

        from ..utils import _detect_variable, _decode_station_names

        nc = netCDF4.Dataset(str(tmp_path), "r")
        try:
            zeta_var_name = _detect_variable(
                nc, ["zeta", "elevation", "water_level", "ssh"]
            )
            sname_var_name = _detect_variable(
                nc, ["station_name", "station", "stationid"]
            )
            lat_var_name = _detect_variable(nc, ["y", "lat", "latitude"])
            lon_var_name = _detect_variable(nc, ["x", "lon", "longitude"])

            if not zeta_var_name:
                return "Could not find water level variable in STOFS NetCDF file."

            zeta = np.array(nc.variables[zeta_var_name][:])
            getattr(nc.variables[zeta_var_name], "_FillValue", 1e37)
            zeta = np.where(np.abs(zeta) > 1e10, np.nan, zeta)

            station_names = (
                _decode_station_names(nc.variables[sname_var_name])
                if sname_var_name
                else []
            )
            lats = (
                list(np.array(nc.variables[lat_var_name][:]).ravel())
                if lat_var_name
                else []
            )
            lons = (
                list(np.array(nc.variables[lon_var_name][:]).ravel())
                if lon_var_name
                else []
            )

        finally:
            nc.close()

        n_stations = zeta.shape[1] if zeta.ndim == 2 else 0
        if n_stations == 0:
            return "Could not determine station count from STOFS file."

        # Compute per-station max
        with np.errstate(all="ignore"):
            max_vals = np.nanmax(zeta, axis=0)

        rows = []
        for i in range(n_stations):
            if np.isnan(max_vals[i]):
                continue
            lat = lats[i] if i < len(lats) else None
            lon = lons[i] if i < len(lons) else None
            name = station_names[i].strip() if i < len(station_names) else str(i)

            # Region filter
            if region and lat is not None and lon is not None:
                from ..stations import REGIONS

                bbox = REGIONS.get(region.value, {})
                if bbox:
                    if not (
                        bbox["lat_min"] <= lat <= bbox["lat_max"]
                        and bbox["lon_min"] <= lon <= bbox["lon_max"]
                    ):
                        continue

            rows.append(
                {
                    "station": name,
                    "max_wl": round(float(max_vals[i]), 3),
                    "lat": round(lat, 4) if lat else "?",
                    "lon": round(lon, 4) if lon else "?",
                }
            )

        rows.sort(key=lambda r: r["max_wl"], reverse=True)
        rows = rows[:top_n]

        datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = get_model_label(model.value, date_str)

        if response_format == "json":
            return json.dumps(
                {
                    "model": model.value,
                    "cycle_date": date_str,
                    "cycle_hour": hour_str,
                    "datum": datum,
                    "top_stations": rows,
                },
                indent=2,
            )

        lines = [
            f"## {model_label} — Peak Water Levels",
            f"**Cycle**: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z | "
            f"**Datum**: {datum} | "
            f"**Showing top {len(rows)} stations**",
            "",
        ]
        if region:
            lines[1] += f" | **Region**: {region.value}"

        lines += [
            "| Rank | Station | Max WL (m) | Lat | Lon |",
            "| --- | --- | --- | --- | --- |",
        ]
        for rank, r in enumerate(rows, 1):
            lines.append(
                f"| {rank} | {r['station']} | {r['max_wl']:.3f} | "
                f"{r['lat']} | {r['lon']} |"
            )

        lines.append("")
        lines.append(f"*Data from NOAA STOFS. Values relative to {datum}.*")
        return "\n".join(lines)

    except Exception as e:
        return handle_stofs_error(e, model.value)
    finally:
        cleanup_temp_file(tmp_path)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def stofs_get_gridded_forecast(
    ctx: Context,
    latitude: float,
    longitude: float,
    model: STOFSModel = STOFSModel.GLOBAL_2D,
    variable: str | None = None,
    cycle_date: str | None = None,
    cycle_hour: str | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """[CURRENTLY UNAVAILABLE — NOMADS OPeNDAP retired Oct 2025, NWS SCN 25-81] Get STOFS forecast at any lat/lon from the regular gridded product via OPeNDAP.

    Unlike stofs_get_station_forecast (limited to ~385 fixed CO-OPS stations),
    this tool queries the STOFS regular-grid product interpolated onto structured
    lat/lon grids and served via NOMADS OPeNDAP. Only the requested grid cell
    is downloaded — no large file transfer required.

    Coverage: US East Coast, Gulf, West Coast, Alaska, Hawaii, Puerto Rico, Guam.
    Resolution: ~2.5 km (conus/hawaii/guam), ~1.25 km (Puerto Rico), ~6 km (Alaska).

    Note: NOMADS OPeNDAP was RETIRED in October 2025 (NWS Service Change Notice
    25-81), so this tool currently returns a retirement notice rather than data.
    Use stofs_get_point_forecast / stofs_get_station_forecast instead (station-
    based, reliable AWS S3). It is kept so the retirement is reported clearly,
    and so it resumes working automatically if NOMADS ever restores the service.

    Args:
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        model: '2d_global' or '3d_atlantic'.
        variable: OPeNDAP variable name. Auto-detected if None.
                  Common names: 'etcwlsfc' (combined WL), 'etsrgsfc' (surge only).
        cycle_date: Date in YYYY-MM-DD format. Default: latest available.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest.
        response_format: 'markdown' or 'json'.
    """
    import asyncio

    try:
        client = _get_client(ctx)

        # Resolve cycle
        cycle = await resolve_cycle(client, model.value, cycle_date, cycle_hour)
        if not cycle:
            return (
                "No STOFS cycles found. Use stofs_list_cycles to check available data."
            )
        date_str, hour_str = cycle

        # Determine the NOMADS region for this lat/lon
        region = get_opendap_region(latitude, longitude)

        # Build OPeNDAP URL (per-region, per-cycle)
        opendap_url = client.build_opendap_url(model.value, date_str, hour_str, region)

        # Check NOMADS availability (fast .das request)
        available, reason = await client.check_opendap_available(opendap_url)
        if not available:
            if reason == "retired":
                return (
                    "NOMADS OPeNDAP has been retired (NWS Service Change Notice "
                    "25-81, effective October 2025). All `/dods/` endpoints now "
                    "return an HTML error page, so this tool cannot retrieve data "
                    "until it is migrated to a replacement backend.\n\n"
                    "Alternatives:\n"
                    "- Use `stofs_get_station_forecast` or `stofs_get_point_forecast` "
                    "(AWS S3 station files — supports historical cycles and works today).\n"
                    "- For actual observed historical water levels, use the coops-mcp "
                    "tool `coops_get_water_levels` with a CO-OPS station ID."
                )
            return (
                f"NOMADS OPeNDAP endpoint not available for cycle "
                f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z "
                f"(reason: {reason}).\n\n"
                "Alternatives:\n"
                "- Try a different cycle with stofs_list_cycles\n"
                "- Use stofs_get_point_forecast (station-based, uses reliable AWS S3)"
            )

        # Run blocking xarray OPeNDAP call in a thread — avoids blocking the event loop
        data = await asyncio.wait_for(
            asyncio.to_thread(
                extract_point_from_opendap,
                opendap_url,
                latitude,
                longitude,
                variable,
            ),
            timeout=60.0,
        )

        if not data["times"]:
            return (
                f"No valid data at ({latitude:.4f}°, {longitude:.4f}°). "
                "The point may be over land or outside the model's grid domain. "
                "Try a location closer to the coast."
            )

        datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = (
            "STOFS-2D-Global" if model.value == "2d_global" else "STOFS-3D-Atlantic"
        )

        # Distance from requested point to actual grid cell center
        snap_dist = _haversine(
            latitude, longitude, data["actual_lat"], data["actual_lon"]
        )

        if response_format == "json":
            return json.dumps(
                {
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "actual_lat": data["actual_lat"],
                    "actual_lon": data["actual_lon"],
                    "grid_resolution_deg": data["grid_resolution_deg"],
                    "snap_distance_km": round(snap_dist, 2),
                    "model": model.value,
                    "region": region,
                    "variable": data["variable"],
                    "cycle_date": date_str,
                    "cycle_hour": hour_str,
                    "datum": datum,
                    "source": "NOMADS OPeNDAP (regular grid)",
                    "n_points": data["n_times"],
                    "times": data["times"],
                    "values": data["values"],
                },
                indent=2,
            )

        metadata = [
            f"Model: {model_label} (regular grid via NOMADS OPeNDAP)",
            f"Region: {region}",
            f"Variable: {data['variable']}",
            f"Cycle: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z",
            f"Datum: {datum}",
            f"Grid point: ({data['actual_lat']}°, {data['actual_lon']}°)",
            f"Grid resolution: ~{data['grid_resolution_deg']}°",
        ]
        if snap_dist > 0.1:
            metadata.append(f"Grid snap distance: {snap_dist:.1f} km")

        return format_timeseries_table(
            times=data["times"],
            values=data["values"],
            title=f"{model_label} Gridded Forecast — ({latitude:.4f}°, {longitude:.4f}°)",
            metadata_lines=metadata,
            source="NOAA STOFS via NOMADS OPeNDAP (regular grid)",
        )

    except asyncio.TimeoutError:
        return (
            "NOMADS OPeNDAP request timed out (>60 s). "
            "NOMADS can be slow during peak hours. Try again later, or use "
            "stofs_get_point_forecast (station-based, AWS S3) as a faster alternative."
        )
    except Exception as e:
        return handle_stofs_error(e, model.value)
