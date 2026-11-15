# CLAUDE.md — Add OPeNDAP Gridded Point Extraction to stofs-mcp

## Overview

Add a new tool `stofs_get_gridded_forecast` and supporting OPeNDAP client code to the existing `stofs-mcp` server. This enables forecast queries at **any arbitrary lat/lon** by remotely slicing STOFS regular-grid data via NOMADS OPeNDAP — no file download required.

This complements the existing station-based tools. The station tools use pre-extracted point files (~385 fixed locations); this new tool uses the interpolated regular grids served via OPeNDAP to reach any coastal point.

---

## Background: How OPeNDAP Works Here

STOFS produces two kinds of gridded output:
1. **Native unstructured mesh** (ADCIRC triangles, 12.8M nodes) — huge files, OPeNDAP cannot do spatial queries on these
2. **Regular-grid GRIB2 regional subsets** — interpolated to structured lat/lon grids, served via NOMADS OPeNDAP

NOMADS OPeNDAP endpoints expose the regular-grid products as remote datasets that xarray can open. When you do `ds.sel(lat=40.7, lon=-74.0, method="nearest")`, only the requested slice is transferred over the network — not the entire grid. This is the key advantage.

### OPeNDAP URL Pattern

```
https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/stofs_2d_glo{YYYYMMDD}/stofs_2d_glo_{CC}z
```

Where `CC` is the cycle hour (00, 06, 12, 18).

Example: `https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/stofs_2d_glo20260219/stofs_2d_glo_00z`

For STOFS-3D-Atlantic:
```
https://nomads.ncep.noaa.gov/dods/stofs_3d_atl/stofs_3d_atl{YYYYMMDD}/stofs_3d_atl_12z
```

### What the OPeNDAP Dataset Contains

The OPeNDAP endpoint serves the data that was interpolated from the native mesh onto regular grids. The dataset has structured dimensions:

```
Dimensions:
  time: ~181 (hourly, 0-180 hours for 2D-Global)
  lat: varies by region
  lon: varies by region

Coordinates:
  time (time)        — datetime or hours since reference
  lat  (lat)         — regularly spaced latitude values
  lon  (lon)         — regularly spaced longitude values

Data variables:
  etsurgetsrg        — storm surge (m)
  etwlswlc           — combined water level (m)  
  etrtpcrlc          — tidal prediction (m)
```

**IMPORTANT:** The variable names on OPeNDAP are different from the native NetCDF files. They use abbreviated GRIB2-style names, not `zeta`. You MUST inspect the actual dataset to confirm the variable names. The names above are based on documented NOMADS conventions for STOFS but may vary. The implementation must handle this discovery dynamically.

### Regional Grid Coverage

The OPeNDAP dataset covers multiple regions at different resolutions. The data is served as one combined dataset — use lat/lon subsetting to query specific points.

| Region | Approx Resolution | Lat Range | Lon Range |
|--------|------------------|-----------|-----------|
| conus.east | 2.5 km (~0.025°) | ~5°N to ~47°N | ~-100°W to ~-50°W |
| conus.west | 2.5 km (~0.025°) | ~20°N to ~55°N | ~-135°W to ~-110°W |
| alaska | 6 km (~0.06°) | ~45°N to ~75°N | ~180°W to ~-120°W |
| hawaii | 2.5 km (~0.025°) | ~15°N to ~25°N | ~-165°W to ~-150°W |
| puertori | 1.25 km (~0.0125°) | ~15°N to ~21°N | ~-70°W to ~-60°W |
| guam | 2.5 km (~0.025°) | ~10°N to ~18°N | ~140°E to ~150°E |

---

## What to Implement

### 1. Add `xarray` dependency

In `pyproject.toml`, add `xarray>=2024.1.0` to the `dependencies` list:

```toml
dependencies = [
    "mcp[cli]>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "netCDF4>=1.7.0",
    "numpy>=1.26.0",
    "xarray>=2024.1.0",
]
```

xarray uses netCDF4 as its engine for OPeNDAP access — no additional dependency needed.

### 2. Add OPeNDAP methods to `client.py`

Add these constants and methods to the existing `STOFSClient` class:

```python
OPENDAP_BASE_2D = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo"
OPENDAP_BASE_3D = "https://nomads.ncep.noaa.gov/dods/stofs_3d_atl"
```

Add a method to build the OPeNDAP URL:

```python
def build_opendap_url(self, model: str, date: str, cycle: str) -> str:
    """Build NOMADS OPeNDAP URL for STOFS regular-grid data.

    Args:
        model: '2d_global' or '3d_atlantic'.
        date: YYYYMMDD format.
        cycle: '00', '06', '12', '18'.

    Returns:
        OPeNDAP URL string.
    """
    if model == "2d_global":
        return f"{OPENDAP_BASE_2D}/stofs_2d_glo{date}/stofs_2d_glo_{cycle}z"
    elif model == "3d_atlantic":
        return f"{OPENDAP_BASE_3D}/stofs_3d_atl{date}/stofs_3d_atl_{cycle}z"
    else:
        raise ValueError(f"Unknown model '{model}'.")
```

Add a method to check if the OPeNDAP endpoint is reachable:

```python
async def check_opendap_available(self, url: str) -> bool:
    """Check if a NOMADS OPeNDAP endpoint is reachable.

    Tests by fetching the .das (Dataset Attribute Structure) — a small text response.
    """
    client = await self._get_client()
    try:
        response = await client.get(f"{url}.das", timeout=15.0)
        return response.status_code == 200
    except Exception:
        return False
```

### 3. Add OPeNDAP extraction utility in `utils.py`

Add a new function. This is the core logic — it opens the remote dataset, extracts a point, and returns the time series. **This function uses blocking I/O** (xarray's OPeNDAP access is synchronous) so it must be called carefully (see tool implementation below).

```python
def extract_point_from_opendap(
    opendap_url: str,
    latitude: float,
    longitude: float,
    variable: str | None = None,
) -> dict[str, Any]:
    """Extract a time series at a single lat/lon from a NOMADS OPeNDAP dataset.

    Opens the remote dataset with xarray, selects the nearest grid point,
    and returns the time series. Only the requested slice is downloaded.

    Args:
        opendap_url: Full OPeNDAP URL (e.g., https://nomads.ncep.noaa.gov/dods/...).
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        variable: Specific variable name to extract. If None, auto-detect
                  the water level variable.

    Returns:
        Dict with keys:
            - 'times': list of ISO 8601 datetime strings
            - 'values': list of water level values (m)
            - 'actual_lat': float — latitude of the nearest grid point
            - 'actual_lon': float — longitude of the nearest grid point
            - 'variable': str — the variable name used
            - 'n_times': int — number of time steps
            - 'grid_resolution_deg': float — approximate grid spacing

    Raises:
        RuntimeError: If the OPeNDAP endpoint is unreachable or data cannot be read.
        ValueError: If no suitable water level variable is found.
    """
    import xarray as xr
    import numpy as np

    try:
        ds = xr.open_dataset(opendap_url, engine="netcdf4")
    except Exception as e:
        raise RuntimeError(
            f"Cannot open OPeNDAP dataset at {opendap_url}. "
            f"NOMADS may be temporarily unavailable. Error: {e}"
        )

    try:
        # --- Auto-detect water level variable if not specified ---
        if variable is None:
            # Known STOFS OPeNDAP variable names (check in order of preference)
            candidates = [
                "etwlswlc",      # combined water level
                "etsurgetsrg",   # storm surge
                "etrtpcrlc",     # tidal prediction
                "zeta",          # sometimes used
                "water_level",
            ]
            for name in candidates:
                if name in ds.data_vars:
                    variable = name
                    break

            if variable is None:
                available = list(ds.data_vars)
                ds.close()
                raise ValueError(
                    f"No known water level variable found in OPeNDAP dataset. "
                    f"Available variables: {available}. "
                    f"Specify the variable name explicitly."
                )

        if variable not in ds.data_vars:
            available = list(ds.data_vars)
            ds.close()
            raise ValueError(
                f"Variable '{variable}' not found. Available: {available}"
            )

        # --- Select nearest grid point ---
        point = ds[variable].sel(lat=latitude, lon=longitude, method="nearest")

        actual_lat = float(point.lat.values)
        actual_lon = float(point.lon.values)

        # --- Extract time series ---
        values_raw = point.values  # shape: (time,)

        # Handle time coordinate
        times_raw = point.time.values if "time" in point.coords else point.coords[list(point.dims)[0]].values

        # Convert numpy datetime64 to ISO strings
        times_out = []
        for t in times_raw:
            if hasattr(t, "isoformat"):
                times_out.append(t.isoformat()[:16].replace("T", " "))
            else:
                # numpy datetime64
                ts = (t - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                times_out.append(dt.strftime("%Y-%m-%d %H:%M"))

        # Filter NaN / fill values
        values_out = []
        times_filtered = []
        for t_str, v in zip(times_out, values_raw.tolist()):
            if v is not None and not np.isnan(v) and abs(v) < 1e10:
                times_filtered.append(t_str)
                values_out.append(round(float(v), 4))

        # Estimate grid resolution
        if len(ds.lat) > 1:
            grid_res = abs(float(ds.lat[1] - ds.lat[0]))
        else:
            grid_res = 0.0

        return {
            "times": times_filtered,
            "values": values_out,
            "actual_lat": round(actual_lat, 4),
            "actual_lon": round(actual_lon, 4),
            "variable": variable,
            "n_times": len(times_filtered),
            "grid_resolution_deg": round(grid_res, 4),
        }

    finally:
        ds.close()
```

### 4. Add the new tool in `tools/forecast.py`

Add `stofs_get_gridded_forecast` to the existing `tools/forecast.py` file. This tool wraps the OPeNDAP extraction with proper async handling.

**CRITICAL: xarray OPeNDAP access is synchronous (blocking I/O).** You must wrap the call in `asyncio.to_thread()` so it doesn't block the MCP server's event loop.

```python
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
    response_format: str = "markdown",
) -> str:
    """Get STOFS forecast at any lat/lon from the regular gridded product via OPeNDAP.

    Unlike stofs_get_station_forecast (limited to ~385 fixed stations), this tool
    queries the STOFS regular-grid product at any coastal point. Data is fetched
    remotely from NOMADS — only the requested grid cell is downloaded.

    Coverage: US East Coast, West Coast, Gulf, Alaska, Hawaii, Puerto Rico, Guam.
    Resolution: ~2.5 km (conus), ~1.25 km (Puerto Rico), ~6 km (Alaska).

    Note: Uses NOMADS OPeNDAP which has a ~2-day rolling window and can be
    intermittently slow or unavailable. If this fails, use stofs_get_point_forecast
    (station-based) as a fallback.

    Args:
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        model: '2d_global' or '3d_atlantic'.
        variable: OPeNDAP variable name (auto-detected if None).
                  Common: 'etwlswlc' (combined WL), 'etsurgetsrg' (surge).
        cycle_date: Date in YYYY-MM-DD format. Default: latest available.
        cycle_hour: Cycle hour '00', '06', '12', '18'. Default: latest.
        response_format: 'markdown' or 'json'.
    """
    import asyncio

    try:
        client = _get_client(ctx)

        # Resolve cycle
        cycle = await _resolve_cycle(client, model.value, cycle_date, cycle_hour)
        if not cycle:
            return (
                "No STOFS cycles found. Use stofs_list_cycles to check available data."
            )
        date_str, hour_str = cycle

        # Build OPeNDAP URL
        opendap_url = client.build_opendap_url(model.value, date_str, hour_str)

        # Check availability first (fast HTTP check)
        available = await client.check_opendap_available(opendap_url)
        if not available:
            return (
                f"NOMADS OPeNDAP endpoint is not available for cycle "
                f"{date_str} {hour_str}z.\n\n"
                "NOMADS keeps only a ~2-day rolling window and can be intermittently "
                "down. Alternatives:\n"
                "- Try a different cycle with stofs_list_cycles\n"
                "- Use stofs_get_point_forecast (station-based, uses AWS S3 which "
                "is more reliable)"
            )

        # Run the blocking xarray OPeNDAP call in a thread
        from ..utils import extract_point_from_opendap

        data = await asyncio.to_thread(
            extract_point_from_opendap,
            opendap_url,
            latitude,
            longitude,
            variable,
        )

        if not data["times"]:
            return (
                f"No valid data at ({latitude:.4f}, {longitude:.4f}). "
                "The point may be over land or outside the model domain. "
                "Try a location closer to the coast."
            )

        datum = MODEL_DATUMS.get(model.value, "unknown")
        model_label = (
            "STOFS-2D-Global" if model.value == "2d_global"
            else "STOFS-3D-Atlantic"
        )

        dist_note = ""
        # Approximate distance from requested point to actual grid cell center
        from ..utils import _haversine
        snap_dist = _haversine(
            latitude, longitude, data["actual_lat"], data["actual_lon"]
        )
        if snap_dist > 0.1:
            dist_note = f"Grid snap distance: {snap_dist:.1f} km"

        if response_format == "json":
            return json.dumps({
                "query_lat": latitude,
                "query_lon": longitude,
                "actual_lat": data["actual_lat"],
                "actual_lon": data["actual_lon"],
                "grid_resolution_deg": data["grid_resolution_deg"],
                "snap_distance_km": round(snap_dist, 2),
                "model": model.value,
                "variable": data["variable"],
                "cycle_date": date_str,
                "cycle_hour": hour_str,
                "datum": datum,
                "source": "NOMADS OPeNDAP (regular grid)",
                "n_points": data["n_times"],
                "times": data["times"],
                "values": data["values"],
            }, indent=2)

        metadata = [
            f"Model: {model_label} (regular grid via OPeNDAP)",
            f"Variable: {data['variable']}",
            f"Cycle: {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {hour_str}z",
            f"Datum: {datum}",
            f"Grid point: ({data['actual_lat']}, {data['actual_lon']})",
            f"Grid resolution: ~{data['grid_resolution_deg']}°",
        ]
        if dist_note:
            metadata.append(dist_note)

        return format_timeseries_table(
            times=data["times"],
            values=data["values"],
            title=f"{model_label} Gridded Forecast — ({latitude:.4f}°, {longitude:.4f}°)",
            metadata_lines=metadata,
            source="NOAA STOFS via NOMADS OPeNDAP",
        )

    except Exception as e:
        return handle_stofs_error(e, model.value)
```

### 5. Update `stofs_get_point_forecast` to mention the gridded alternative

In the existing `stofs_get_point_forecast` tool, update the "no station found" error message to mention the gridded tool as an alternative. Find the block that returns the "No STOFS station found" message and add a line:

```python
"- Use stofs_get_gridded_forecast for any lat/lon (uses OPeNDAP regular grid)\n"
```

### 6. Update `stofs_get_system_info` 

In the `SPECS` dict for each model, add a line about OPeNDAP availability:

```python
"opendap": "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/ (regular grid, ~2-day window)",
```

And for 3D:
```python
"opendap": "https://nomads.ncep.noaa.gov/dods/stofs_3d_atl/ (regular grid, ~2-day window)",
```

---

## What NOT to Change

- Do NOT add xarray to any of the station-based code paths

---

## Add Tests

### Unit test in `tests/test_utils.py`

Add a test for the OPeNDAP URL builder:

```python
class TestBuildOpendapUrl:
    def setup_method(self):
        self.client = STOFSClient()

    def test_2d_global(self):
        url = self.client.build_opendap_url("2d_global", "20260219", "12")
        assert "nomads.ncep.noaa.gov/dods/stofs_2d_glo" in url
        assert "stofs_2d_glo20260219" in url
        assert "stofs_2d_glo_12z" in url

    def test_3d_atlantic(self):
        url = self.client.build_opendap_url("3d_atlantic", "20260219", "12")
        assert "stofs_3d_atl" in url
        assert "stofs_3d_atl_12z" in url

    def test_invalid_model(self):
        with pytest.raises(ValueError):
            self.client.build_opendap_url("invalid", "20260219", "12")
```

### Live integration test in `tests/test_live.py`

Add a test that tries to open the OPeNDAP endpoint (skip if NOMADS is down):

```python
@pytest.mark.asyncio
async def test_opendap_endpoint_reachable(client):
    """Check that the NOMADS OPeNDAP endpoint is reachable."""
    from stofs_mcp.utils import resolve_latest_cycle

    cycle = await resolve_latest_cycle(client, "2d_global", num_days=3)
    if cycle is None:
        pytest.skip("No STOFS cycle found")

    date_str, hour_str = cycle
    url = client.build_opendap_url("2d_global", date_str, hour_str)
    available = await client.check_opendap_available(url)

    if not available:
        pytest.skip("NOMADS OPeNDAP not reachable (may be temporarily down)")

    print(f"\nOPeNDAP reachable: {url}")


@pytest.mark.asyncio
async def test_opendap_point_extraction(client):
    """Extract a single point from STOFS via OPeNDAP."""
    from stofs_mcp.utils import resolve_latest_cycle, extract_point_from_opendap

    cycle = await resolve_latest_cycle(client, "2d_global", num_days=3)
    if cycle is None:
        pytest.skip("No STOFS cycle found")

    date_str, hour_str = cycle
    url = client.build_opendap_url("2d_global", date_str, hour_str)

    available = await client.check_opendap_available(url)
    if not available:
        pytest.skip("NOMADS OPeNDAP not reachable")

    # The Battery, NY — well within the conus.east grid
    data = extract_point_from_opendap(url, 40.7, -74.0)

    print(f"\nVariable: {data['variable']}")
    print(f"Grid point: ({data['actual_lat']}, {data['actual_lon']})")
    print(f"Resolution: {data['grid_resolution_deg']}°")
    print(f"Time steps: {data['n_times']}")

    assert data["n_times"] > 0, "Expected at least some data points"
    assert len(data["values"]) == len(data["times"])
    # Grid point should be near the requested location
    assert abs(data["actual_lat"] - 40.7) < 0.1
    assert abs(data["actual_lon"] - (-74.0)) < 0.1
```

---

## Update Evaluation

Add two questions to `eval/evaluation.xml`:

```xml
<question id="11">
    <prompt>Get the STOFS water level forecast at lat 36.85, lon -75.98 (Virginia Beach) using the gridded product.</prompt>
    <expected_tools>stofs_get_gridded_forecast</expected_tools>
    <expected_info>time series from OPeNDAP regular grid, grid snap distance, resolution</expected_info>
</question>

<question id="12">
    <prompt>Compare the gridded forecast vs the station forecast near The Battery, NY. How different are they?</prompt>
    <expected_tools>stofs_get_gridded_forecast, stofs_get_station_forecast</expected_tools>
    <expected_info>two time series from different data sources, user can compare values</expected_info>
</question>
```

---

## Update README.md

Add `stofs_get_gridded_forecast` to the tools table:

```
| `stofs_get_gridded_forecast` | Forecast at any lat/lon via OPeNDAP (regular grid, no download) |
```

Add an example query:
```
- "Get the STOFS forecast at lat 36.85, lon -75.98 using the gridded product"
```

Add a note under "Data Sources":
```
- **NOMADS OPeNDAP**: `nomads.ncep.noaa.gov/dods/stofs_2d_glo/` (remote slice of regular-grid data, ~2-day window)
```

---

## Key Implementation Notes

1. **`asyncio.to_thread()` is mandatory.** xarray's netCDF4 engine for OPeNDAP is synchronous. Without `to_thread()`, the MCP server event loop blocks during the remote data fetch (5-30 seconds), preventing other tool calls from being processed.

2. **NOMADS is unreliable.** OPeNDAP endpoints go down frequently — during maintenance windows, heavy load, or system updates. Every code path must handle connection failures gracefully and suggest the station-based fallback. Never let a NOMADS failure crash the server.

3. **The variable names are not guaranteed.** NOMADS OPeNDAP variable names can change between STOFS versions. The implementation must auto-detect variable names by inspecting `ds.data_vars`, not hardcode them. The candidate list is a starting hint, not a contract.

4. **Land points return NaN.** When the requested lat/lon falls over land, the nearest grid cell will have NaN values. Filter these out and return a clear message suggesting the user try a point closer to the coast.

5. **The OPeNDAP grid is coarser than the native mesh.** The regular grid is ~2.5 km resolution — much coarser than the native ADCIRC mesh which has 80-120 m coastal resolution. Station point files sample the native mesh. So for locations near CO-OPS stations, the station-based tools will give more accurate results. The gridded tool is for locations far from any station.

6. **Do not cache xarray datasets across tool calls.** Each `xr.open_dataset()` opens a network connection. Holding it open between tool calls risks stale connections, timeouts, and resource leaks. Open fresh each time — the OPeNDAP server handles caching on its side.

7. **Longitude convention.** NOMADS OPeNDAP may use 0-360 longitude instead of -180 to 180. If the user provides negative longitude (Western hemisphere), you may need to convert: `lon_360 = longitude % 360`. Check the actual `ds.lon` values to determine which convention is in use, and convert if needed.

8. **Timeout handling.** NOMADS OPeNDAP can be very slow (30+ seconds) during peak hours. The xarray call inside `to_thread()` does not respect the httpx timeout. Consider wrapping the `to_thread()` call in `asyncio.wait_for(coro, timeout=60)` and catching `asyncio.TimeoutError`.

---

## Summary: Two Data Access Strategies

After this implementation, stofs-mcp has two complementary strategies:

| | Station Files (existing) | OPeNDAP Grid (new) |
|---|---|---|
| **Source** | AWS S3 (.nc download) | NOMADS OPeNDAP (remote slice) |
| **Coverage** | ~385 fixed CO-OPS stations | Any lat/lon in grid domain |
| **Resolution** | Native mesh (80-120m coastal) | Regular grid (~2.5 km) |
| **Reliability** | High (S3 rarely down) | Medium (NOMADS can be flaky) |
| **Speed** | ~5-10 sec (download + parse) | ~5-30 sec (network dependent) |
| **Retention** | Days-weeks on S3 | ~2 days on NOMADS |
| **Best for** | Known stations, validation | Arbitrary points, exploration |
| **Tools** | stofs_get_station_forecast, stofs_get_point_forecast, stofs_compare_with_observations | stofs_get_gridded_forecast |
