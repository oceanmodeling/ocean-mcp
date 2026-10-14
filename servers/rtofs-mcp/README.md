# RTOFS MCP Server

<!-- mcp-name: io.github.oceanmodeling/rtofs-mcp -->

MCP server for accessing **NOAA RTOFS** (Real-Time Ocean Forecast System) global ocean forecast data. Provides SST, salinity, ocean currents, and sea surface height from the operational HYCOM/ESPC model via the HYCOM THREDDS Data Server.

## Features

- Global 1/12° ocean forecasts (~8 km resolution)
- 8-day forecast horizon, updated daily
- Temperature, salinity, currents at all depth levels
- Sea surface height (SSH) at hourly resolution
- Point queries, depth profiles, area grids, and vertical transects
- Pure httpx — no NetCDF/xarray dependencies needed

## Installation

```bash
# Using uvx (recommended)
uvx rtofs-mcp

# Using pip
pip install rtofs-mcp
```

## Tools

| Tool | Description |
| --- | --- |
| `rtofs_get_system_info` | RTOFS overview — resolution, variables, coverage (no HTTP) |
| `rtofs_list_datasets` | List HYCOM THREDDS datasets with live availability check |
| `rtofs_get_latest_time` | Query latest forecast time from THREDDS |
| `rtofs_get_surface_forecast` | Surface time series at a point (SST, SSS, currents, SSH) |
| `rtofs_get_profile_forecast` | 3D depth profile at a point (temp, salinity, currents vs depth) |
| `rtofs_get_area_forecast` | Surface forecast for a bounding box (parallel point queries) |
| `rtofs_get_transect` | Vertical transect between two points (parallel depth profiles) |
| `rtofs_compare_with_observations` | Change at a point over the 24 h before a time (default: now) |

## Example Queries

- "What is the current SST at The Battery, NYC?"
- "Show me a temperature depth profile at 35°N, 74°W in the Gulf Stream"
- "Get the SST forecast for the next 8 days at latitude 25, longitude -80"
- "Show a vertical transect of temperature from Miami to Bermuda"
- "What are the ocean currents at 40°N, 74°W?"

## Data Source

**HYCOM THREDDS Data Server** (`https://tds.hycom.org/thredds/`)

ESPC-D-V02 datasets (operational HYCOM/RTOFS):
- `FMRC_ESPC-D-V02_ssh` — Sea Surface Height (2D, hourly)
- `FMRC_ESPC-D-V02_t3z` — Water Temperature (3D, 3-hourly)
- `FMRC_ESPC-D-V02_s3z` — Salinity (3D, 3-hourly)
- `FMRC_ESPC-D-V02_uv3z` — Ocean Currents u/v (3D, 3-hourly)

Data is queried via THREDDS NCSS (NetCDF Subset Service) which returns CSV for point queries — no NetCDF library required.

## Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "rtofs": {
      "command": "uvx",
      "args": ["rtofs-mcp"]
    }
  }
}
```

## Development

```bash
cd servers/rtofs-mcp
uv sync --group dev
uv run rtofs-mcp                                          # Start server
uv run pytest tests/ --ignore=tests/test_live.py -v       # Unit tests
uv run pytest tests/test_live.py -v                       # Integration tests
```

## License

MIT
