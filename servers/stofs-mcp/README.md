# STOFS MCP Server

<!-- mcp-name: io.github.oceanmodeling/stofs-mcp -->

MCP server providing AI assistants with access to NOAA's Storm Tide Operational Forecast System (STOFS) — operational storm surge and water level forecasts, and validation against CO-OPS observations.

**Status: Ready**

## Tools

| Tool | Description |
|------|-------------|
| `stofs_list_cycles` | List available STOFS forecast cycles on AWS S3 |
| `stofs_get_station_forecast` | Get water level forecast time series at a CO-OPS station |
| `stofs_get_point_forecast` | Get forecast at arbitrary lat/lon (nearest STOFS station) |
| `stofs_get_gridded_forecast` | Forecast at any lat/lon via OPeNDAP (regular grid, no download) |
| `stofs_compare_with_observations` | Compare STOFS forecast vs CO-OPS observations (bias, RMSE, correlation); optional lead-time window (`lead_start_hours`, `lead_end_hours`) for same-valid-time comparisons |
| `stofs_get_max_water_level` | Get top stations by peak predicted water level in a cycle |
| `stofs_get_system_info` | STOFS model specifications, datums, cycle schedule |
| `stofs_list_stations` | List STOFS output stations, filter by state/region/proximity |

## STOFS Models

### STOFS-2D-Global (ADCIRC)
- **Domain**: Global unstructured mesh (~12.8M nodes)
- **Cycles**: 4x daily — 00, 06, 12, 18 UTC
- **Forecast**: 180 hours (7.5 days)
- **Stations**: ~385 output points at 6-minute resolution
- **Datum**: LMSL (Local Mean Sea Level)
- **Data**: [s3://noaa-gestofs-pds](https://noaa-gestofs-pds.s3.amazonaws.com)

### STOFS-3D-Atlantic (SCHISM)
- **Domain**: US East Coast + Gulf of Mexico + Puerto Rico (~2.9M nodes)
- **Cycles**: 1x daily — 12 UTC
- **Forecast**: 96 hours (4 days)
- **Stations**: 108 output points (v2.1); 166 from the v3.1 upgrade, at 6-minute resolution
- **Datum**: station NetCDF NAVD88 before the v3.1 upgrade (2026-08-17 12z cycle), LMSL from it; gridded output xGEOID20b
- **Data**: [s3://noaa-nos-stofs3d-pds](https://noaa-nos-stofs3d-pds.s3.amazonaws.com)

## Vertical Datums

> ⚠️ Datum differences matter when comparing models and observations:
> - **STOFS-2D station files**: LMSL (Local Mean Sea Level). The files label `zeta`
>   `sea_surface_height_above_geoid`, which is ADCIRC's generic default, not the datum.
> - **STOFS-3D station files**: NAVD88 through the 2026-08-16 cycle (v2.1); LMSL from
>   the 2026-08-17 12z cycle (v3.1, NWS SCN 26-51). Gridded output stays on xGEOID20b.
> - The station tools read the datum from each file's `zeta` metadata and report it with
>   its provenance (`datum_provenance`) and any `datum_warning`. STOFS-2D-Global files,
>   whose label is always ADCIRC's generic "above geoid", fall back to the documented
>   LMSL only for documented versions (STOFS_2D_GLOBAL V2.1, V3.1; ESTOFS GLOBAL V2.1
>   with a warning). An unrecognized explicit reference (e.g. NGVD29, NAVD2022),
>   contradictory attributes, or an undocumented 2D version (e.g. V4.0) make the datum
>   `undetermined`, and no comparison is made.
> - `stofs_compare_with_observations` requests CO-OPS `datum=MSL` for LMSL output and
>   `datum=NAVD` (CO-OPS's identifier for NAVD88) for NAVD88 output. No vertical
>   transformation is applied. LMSL and a station's tidal MSL share a label but not
>   necessarily a realization or epoch, so a mean offset alone does not attribute its cause.

## Data Validity

Values that are masked, equal to the declared fill, non-finite, no-data sentinels
(|value| ≥ 10⁴ m, including codes shifted by a datum or bias constant such as
STOFS-3D's `1e7 + c` and STOFS-2D's `-99999 + 0.4`) or physically implausible
(|value| ≥ 50 m) are excluded by every tool and counted by reason
(`excluded_model_records`, `excluded_values`). `stofs_get_max_water_level` names
stations left without a valid value (`excluded_stations`) instead of ranking them.
See `CHANGELOG.md` for the 0.3.0 changes.

## Quick Start

```bash
git clone https://github.com/oceanmodeling/ocean-mcp.git
cd ocean-mcp/servers/stofs-mcp
uv sync
```

### Configure your MCP client

```json
{
  "mcpServers": {
    "stofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/stofs-mcp", "python", "-m", "stofs_mcp"]
    }
  }
}
```

## Example Queries

- "What is the latest STOFS-2D-Global forecast cycle?"
- "Get the water level forecast for The Battery, NY (station 8518750)"
- "Compare STOFS forecast vs observations at Boston for the past 24 hours"
- "Find STOFS stations within 50 km of New Orleans"
- "What are the top 10 stations with highest predicted water levels?"
- "Get the surge-only forecast at Charleston, SC"
- "Show me the STOFS forecast near lat 29.95, lon -90.07"
- "Get the STOFS forecast at lat 36.85, lon -75.98 (Virginia Beach) using the gridded product"

## Running Tests

```bash
# Unit tests (fast, no network)
uv run pytest tests/test_utils.py -v

# Live integration tests (requires internet, downloads ~5–10 MB)
uv run pytest tests/test_live.py -v -s
```

## Data Sources

- **AWS S3** (primary): `noaa-gestofs-pds` (2D-Global), `noaa-nos-stofs3d-pds` (3D-Atlantic)
- **NOMADS OPeNDAP**: `nomads.ncep.noaa.gov/dods/stofs_2d_glo/` (remote slice of regular-grid data, ~2-day window)
- **CO-OPS API**: `api.tidesandcurrents.noaa.gov` (for observation validation)

## License

MIT
