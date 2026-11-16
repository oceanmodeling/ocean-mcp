# OceanMCP

A monorepo of independently installable MCP servers for ocean and coastal data workflows.

[![PyPI](https://img.shields.io/pypi/v/coops-mcp)](https://pypi.org/project/coops-mcp/)
[![CI](https://github.com/oceanmodeling/ocean-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/oceanmodeling/ocean-mcp/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-listed-blue)](https://registry.modelcontextprotocol.io/?q=oceanmodeling)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Servers

| Server | PyPI | Description |
|--------|------|-------------|
| [coops-mcp](servers/coops-mcp/) | [![PyPI](https://img.shields.io/pypi/v/coops-mcp)](https://pypi.org/project/coops-mcp/) | NOAA CO-OPS tides, water levels, currents, meteorological data |
| [erddap-mcp](servers/erddap-mcp/) | [![PyPI](https://img.shields.io/pypi/v/erddap-mcp)](https://pypi.org/project/erddap-mcp/) | Universal ERDDAP data access across 80+ public servers |
| [nhc-mcp](servers/nhc-mcp/) | [![PyPI](https://img.shields.io/pypi/v/nhc-mcp)](https://pypi.org/project/nhc-mcp/) | NHC storm tracks, advisories, HURDAT2 best track data |
| [recon-mcp](servers/recon-mcp/) | [![PyPI](https://img.shields.io/pypi/v/recon-mcp)](https://pypi.org/project/recon-mcp/) | Hurricane reconnaissance data (HDOB, Vortex Data Messages, ATCF fixes) |
| [stofs-mcp](servers/stofs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/stofs-mcp)](https://pypi.org/project/stofs-mcp/) | NOAA STOFS storm surge forecasts and observation validation |
| [ofs-mcp](servers/ofs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/ofs-mcp)](https://pypi.org/project/ofs-mcp/) | NOAA OFS regional ocean model forecasts (water level, temperature, salinity) |
| [rtofs-mcp](servers/rtofs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/rtofs-mcp)](https://pypi.org/project/rtofs-mcp/) | NOAA RTOFS global ocean forecasts (SST, salinity, currents, SSH) via HYCOM THREDDS |
| [ww3-mcp](servers/ww3-mcp/) | [![PyPI](https://img.shields.io/pypi/v/ww3-mcp)](https://pypi.org/project/ww3-mcp/) | GFS-Wave (WAVEWATCH III) forecasts and NDBC buoy wave observations |
| [ndbc-mcp](servers/ndbc-mcp/) | [![PyPI](https://img.shields.io/pypi/v/ndbc-mcp)](https://pypi.org/project/ndbc-mcp/) | NOAA NDBC buoy observations — waves, SST, wind, pressure (1,300+ stations) |
| [winds-mcp](servers/winds-mcp/) | [![PyPI](https://img.shields.io/pypi/v/winds-mcp)](https://pypi.org/project/winds-mcp/) | NWS surface wind observations from ASOS / AWOS stations |
| [usgs-mcp](servers/usgs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/usgs-mcp)](https://pypi.org/project/usgs-mcp/) | USGS Water Services — streamflow, NWS/NWPS flood status, peak events |
| [goes-mcp](servers/goes-mcp/) | [![PyPI](https://img.shields.io/pypi/v/goes-mcp)](https://pypi.org/project/goes-mcp/) | NOAA GOES-18/19 satellite imagery — visible, infrared, water vapor |
| [vdatum-mcp](servers/vdatum-mcp/) | [![PyPI](https://img.shields.io/pypi/v/vdatum-mcp)](https://pypi.org/project/vdatum-mcp/) | Vertical datum conversion — NAVD88, MLLW, MHHW, LMSL, xGEOID20b and more |
| [adcirc-mcp](servers/adcirc-mcp/) | [![PyPI](https://img.shields.io/pypi/v/adcirc-mcp)](https://pypi.org/project/adcirc-mcp/) | ADCIRC model setup debugging, parameter lookup, config validation |
| [schism-mcp](servers/schism-mcp/) | [![PyPI](https://img.shields.io/pypi/v/schism-mcp)](https://pypi.org/project/schism-mcp/) | SCHISM model setup debugging, parameter lookup, config validation |

**No API keys required for the data servers** — all servers above use free, publicly available datasets. The exceptions are `hpc-system-mcp` and `ufs-runner-mcp` (below), which require actual NOAA RDHPCS cluster access and, in `ufs-runner-mcp`'s case, submit real Slurm jobs.

Additional servers live in this repo but are not yet published to PyPI (install from source): `hpc-system-mcp` and `ufs-runner-mcp` (NOAA RDHPCS / UFS-Coastal HPC workflows — require cluster access), and `alert-mcp` (CO-OPS threshold alerting).

There is also a 19th server in this repo, `nos-workflow-mcp`, which is experimental and still a work in progress (its full implementation lives on an unmerged branch — `main` carries only a minimal subset). It's intentionally left out of the table above and not yet ready for general use.

## Quick Start

### Install from PyPI

```bash
# uvx (recommended) — runs without permanent install, like npx for Python
uvx coops-mcp

# pip — install into current environment
pip install coops-mcp

# pipx — install in isolated environment with CLI entry point
pipx install coops-mcp
```

Replace `coops-mcp` with any published server: `erddap-mcp`, `nhc-mcp`, `recon-mcp`, `stofs-mcp`, `ofs-mcp`, `rtofs-mcp`, `ww3-mcp`, `ndbc-mcp`, `winds-mcp`, `usgs-mcp`, `goes-mcp`, `vdatum-mcp`, `adcirc-mcp`, `schism-mcp`.

### Install from source

```bash
git clone https://github.com/oceanmodeling/ocean-mcp.git
cd ocean-mcp/servers/coops-mcp  # or any other server directory under servers/
uv sync
```

### Configure your MCP client

Add to your MCP settings (e.g., project `.mcp.json`):

**Using PyPI packages (recommended):**

```json
{
  "mcpServers": {
    "coops": {
      "command": "uvx",
      "args": ["coops-mcp"]
    },
    "erddap": {
      "command": "uvx",
      "args": ["erddap-mcp"]
    },
    "nhc": {
      "command": "uvx",
      "args": ["nhc-mcp"]
    },
    "recon": {
      "command": "uvx",
      "args": ["recon-mcp"]
    },
    "stofs": {
      "command": "uvx",
      "args": ["stofs-mcp"]
    },
    "ofs": {
      "command": "uvx",
      "args": ["ofs-mcp"]
    },
    "rtofs": {
      "command": "uvx",
      "args": ["rtofs-mcp"]
    },
    "ww3": {
      "command": "uvx",
      "args": ["ww3-mcp"]
    }
  }
}
```

<details>
<summary>Using local source checkout</summary>

```json
{
  "mcpServers": {
    "coops": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/coops-mcp", "python", "-m", "coops_mcp"]
    },
    "erddap": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/erddap-mcp", "python", "-m", "erddap_mcp"]
    },
    "nhc": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/nhc-mcp", "python", "-m", "nhc_mcp"]
    },
    "recon": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/recon-mcp", "python", "-m", "recon_mcp"]
    },
    "stofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/stofs-mcp", "python", "-m", "stofs_mcp"]
    },
    "ofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/ofs-mcp", "python", "-m", "ofs_mcp"]
    },
    "rtofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/rtofs-mcp", "python", "-m", "rtofs_mcp"]
    },
    "ww3": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/ww3-mcp", "python", "-m", "ww3_mcp"]
    }
  }
}
```

</details>

## Example Queries

With servers configured, you can ask your AI assistant naturally:

**CO-OPS queries:**
- "Get current water levels at The Battery, NY"
- "Find tide stations near Miami Beach"
- "What are the flood statistics for Charleston, SC?"
- "Show me the sea level trend at San Francisco"

**ERDDAP queries:**
- "Search for sea surface temperature datasets on CoastWatch"
- "Get chlorophyll data off the California coast for January 2024"
- "What ERDDAP servers cover the US East Coast?"
- "List all glider datasets on IOOS Gliders ERDDAP"

**NHC queries:**
- "Are there any active tropical cyclones right now?"
- "Show me Hurricane Katrina's track"
- "Search for Category 5 hurricanes in the Atlantic"
- "What is the forecast track for the active storm?"

**Recon queries:**
- "List HDOB reconnaissance flights for the 2024 Atlantic season"
- "Get HDOB flight-level observations from October 7, 2024"
- "Show me the Vortex Data Messages for Hurricane Milton"
- "Get ATCF aircraft fix data for storm AL14 2024"

**STOFS queries:**
- "Get the STOFS water level forecast for The Battery, NY"
- "Compare STOFS forecast vs observations at Boston for the past 24 hours"
- "What are the top stations with highest predicted water levels?"
- "Find STOFS stations within 50 km of New Orleans"

**OFS queries:**
- "What OFS models cover the Chesapeake Bay?"
- "Get the water level forecast at lat 38.98, lon -76.48 from CBOFS"
- "Compare CBOFS water level with CO-OPS observations at station 8571892"
- "List available NGOFS2 forecast cycles for today"

**RTOFS queries:**
- "Get the RTOFS sea surface temperature forecast at 40°N, 74°W"
- "Show me a temperature depth profile in the Gulf Stream"
- "What RTOFS datasets are currently available on HYCOM THREDDS?"
- "Get a vertical transect of salinity from Miami to Bermuda"
- "Show the SST area forecast for the Gulf of Mexico"

**WW3 queries:**
- "What GFS-Wave model grids are available?"
- "Find NDBC buoys near Cape Hatteras"
- "Get the latest wave observations from buoy 41025"
- "Show me the GFS-Wave forecast at 35°N, 75°W for the next 48 hours"
- "Compare the wave forecast against buoy 41025 observations"

**Cross-server queries:**
- "Find CO-OPS stations near this ERDDAP buoy location"
- "Compare tide station data with nearby ERDDAP satellite SST"
- "Is there an active hurricane threatening the Gulf Coast? If so, show me the STOFS surge forecast for New Orleans"
- "Get the CBOFS water level forecast at Chesapeake Bay and compare it with the CO-OPS tide prediction for the same station"
- "Show me sea surface temperature from ERDDAP near The Battery and the current water level from CO-OPS"
- "Which NHC storms have hit the Gulf Coast historically? Show the CO-OPS flood statistics for impacted stations"
- "Get the STOFS gridded forecast and the OFS water level forecast at the same location and compare them"

## Architecture

Each server is fully self-contained with its own `pyproject.toml`, dependencies, and tests. See [docs/architecture.md](docs/architecture.md) for details on shared conventions.

**Shared patterns across servers:**
- FastMCP for MCP server framework
- httpx for async HTTP clients
- Pydantic models, with `Literal[...]` types for constrained parameters
- Read-only tools by default — the data-fetching servers only fetch, never
  modify, anything. `ufs-runner-mcp` (submits/cancels Slurm jobs) and
  `alert-mcp` (creates/pauses/deletes in-memory alert state) are the two
  exceptions, each with a small number of tools marked `readOnlyHint=False`
- `response_format` output as markdown (default), json, geojson, or image, depending on the tool
- Actionable error messages with suggestions

See [CONVENTIONS.md](CONVENTIONS.md) for the full response/behavior contract (output caps, `retrieved_at`, error format, HTTP retries, dependency bounds).

Reproducible verification and evaluation packages for the server releases are in [`verification/`](verification/README.md).

## Citation

If you use this project in your research or work, please cite:

```bibtex
@software{jisan2025oceanmcp,
  author    = {Jisan, Mansur Ali},
  title     = {Ocean MCP: Real-Time Marine Data, MCP-Native},
  year      = {2025},
  url       = {https://github.com/oceanmodeling/ocean-mcp},
  note      = {MCP servers for NOAA CO-OPS, ERDDAP, NHC, Recon, STOFS, OFS, RTOFS, WW3, NDBC, USGS, winds, GOES, ADCIRC, and SCHISM data}
}
```

## License

Licensed under the MIT License. You may use, modify, and distribute this software under the MIT terms. See [LICENSE](LICENSE) for details.
