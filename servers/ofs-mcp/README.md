# OFS MCP Server

<!-- mcp-name: io.github.oceanmodeling/ofs-mcp -->

MCP server for NOAA's Operational Forecast System (OFS) — regional hydrodynamic ocean models covering US coastal waters.

**Status**: Ready

## Overview

OFS comprises ~15 regional ocean models providing 48–72 hour forecasts of water levels, temperature, and salinity for US coastal bays, estuaries, and offshore waters. This server provides AI assistants with access to model metadata, cycle availability, and forecast extraction at geographic points.

## Supported Models

| Model | Name | Grid | Region |
| --- | --- | --- | --- |
| `cbofs` | Chesapeake Bay OFS | ROMS | Chesapeake Bay, MD/VA |
| `dbofs` | Delaware Bay OFS | ROMS | Delaware Bay, DE/NJ |
| `gomofs` | Gulf of Maine OFS | ROMS | Gulf of Maine, ME/MA |
| `ngofs2` | N. Gulf of Mexico OFS v2 | FVCOM | Gulf Coast, LA/TX |
| `nyofs` | New York/NJ Harbor OFS | POM | NY Harbor, NY/NJ |
| `sfbofs` | San Francisco Bay OFS | FVCOM | San Francisco Bay, CA |
| `tbofs` | Tampa Bay OFS | ROMS | Tampa Bay, FL |
| `wcofs` | West Coast OFS | ROMS | US West Coast, CA–WA |
| `ciofs` | Cook Inlet OFS | ROMS | Cook Inlet, AK |

All models run 4× daily (2× for WCOFS) at 00, 06, 12, 18 UTC with 6-minute output resolution.

## Tools

| Tool | Description |
| --- | --- |
| `ofs_list_models` | List all supported models with metadata |
| `ofs_get_model_info` | Detailed specs for a specific model |
| `ofs_list_cycles` | Check S3 for available forecast cycles |
| `ofs_find_models_for_location` | Which models cover a lat/lon point |
| `ofs_get_forecast_at_point` | Forecast time series at lat/lon |
| `ofs_compare_with_coops` | Compare model vs CO-OPS observations |

## Data Access

Model data is accessed via two strategies:
- **NOAA THREDDS OPeNDAP** (`https://opendap.co-ops.nos.noaa.gov/thredds/`): lazy remote access to BEST aggregations (most efficient, only loads requested variables/points)
- **AWS S3** (`noaa-nos-ofs-pds`): direct download for single forecast timesteps

## Quick Start

```bash
cd servers/ofs-mcp
uv sync
uv run ofs-mcp
```

### MCP Client Config

```json
{
  "mcpServers": {
    "ofs": {
      "command": "uv",
      "args": ["--directory", "/path/to/ocean-mcp/servers/ofs-mcp", "run", "ofs-mcp"]
    }
  }
}
```

## Example Queries

- "What OFS models cover the Chesapeake Bay?"
- "List available CBOFS forecast cycles for today"
- "Get the water level forecast at lat 38.98, lon -76.48 from CBOFS"
- "Compare CBOFS water level with CO-OPS observations at station 8571892"
- "What OFS models are available for San Francisco Bay?"
- "Get temperature forecast at lat 37.8, lon -122.4 from SFBOFS"

## Variables

All models provide surface-layer output:

| Variable | Units | Description |
| --- | --- | --- |
| `water_level` | m | Surface elevation relative to model datum |
| `temperature` | °C | Water temperature at surface sigma layer |
| `salinity` | PSU | Salinity at surface sigma layer |

## Datum Notes

Most OFS models use **NAVD88** as their vertical datum. CO-OPS observations use either NAVD or MSL depending on the station. Small systematic offsets (1–5 cm) are expected when comparing model output to observations due to datum differences and distance between CO-OPS stations and model grid points.

## Data Sources

- [NOAA OFS Overview](https://tidesandcurrents.noaa.gov/models.html)
- [AWS S3: noaa-nos-ofs-pds](https://registry.opendata.aws/noaa-nos-ofs/)
- [NOAA THREDDS](https://opendap.co-ops.nos.noaa.gov/thredds/)
- [CO-OPS API](https://api.tidesandcurrents.noaa.gov/api/prod/)

## License

MIT
