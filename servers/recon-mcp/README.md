# recon-mcp

MCP server for NOAA hurricane reconnaissance data — HDOB flight observations, Vortex Data Messages, and ATCF aircraft fixes.

## Tools

| Tool | Description |
|------|-------------|
| `recon_list_missions` | List available reconnaissance data files from the NHC archive |
| `recon_get_hdobs` | Get HDOB 30-second flight-level observations (winds, pressure, SFMR) |
| `recon_get_vdms` | Get Vortex Data Messages (storm center fixes with intensity) |
| `recon_get_fixes` | Get ATCF f-deck aircraft fix records |

## Installation

```bash
# With uv
uv pip install .

# Or with pip
pip install .
```

## Usage

```bash
# Run the MCP server
recon-mcp

# Or via Python
python -m recon_mcp
```

## Data Sources

- **NHC Reconnaissance Archive**: `https://www.nhc.noaa.gov/archive/recon/`
- **ATCF Fix Data**: `https://ftp.nhc.noaa.gov/atcf/fix/` (current season; earlier seasons from `https://ftp.nhc.noaa.gov/atcf/archive/`)

<!-- mcp-name: io.github.oceanmodeling/recon-mcp -->
