# Examples

Scripts that use the Ocean-MCP servers to answer a concrete question and save
a figure (and usually the data behind it) next to the script. Run them from
the repository root.

The scripts get their data in one of three ways:

- **Live, over MCP.** The script starts the servers it needs as MCP stdio
  subprocesses (`uv run --directory servers/<name> python -m <module>`, the
  same command as `.mcp.json`) and calls their tools, exactly as an MCP
  client would. Needs network access, `uv` on `PATH`, and
  `pip install mcp matplotlib numpy`.
- **Replay.** The script re-plots tool output saved earlier (a JSON file in
  this directory, or data embedded in the script), so it runs offline.
  Needs `matplotlib` (and `numpy` for some).
- **Direct import.** The script imports a server's Python client from
  `servers/<name>/src` and calls it without the MCP protocol.

## Live, over MCP

| Script | What it shows | Servers |
|---|---|---|
| [`charleston_vdatum_stofs3d_vs_coops.py`](charleston_vdatum_stofs3d_vs_coops.py) | STOFS-3D-Atlantic (NAVD88) against the Charleston gauge (MLLW), before and after moving the gauge onto NAVD88 with VDatum; the gauge's own datum sheet checks the VDatum offset | stofs, coops, vdatum |
| [`ian_coast_to_river_flooding.py`](ian_coast_to_river_flooding.py) | Hurricane Ian: storm surge at Fort Myers on 28 September, then record crests on the Peace and Myakka rivers on 1 October; Ian's closest approach to the gauge comes from the best track | nhc, coops, usgs |
| [`baltimore_cbofs_vs_stofs2d.py`](baltimore_cbofs_vs_stofs2d.py) | The regional Chesapeake Bay model (CBOFS) and the global STOFS-2D model scored against the Baltimore gauge over the same 48 hours, on MSL | ofs, stofs, coops |
| [`harbor_waterlevel_waves_mcp.py`](harbor_waterlevel_waves_mcp.py) | New York Harbor water level (STOFS-2D vs CO-OPS) with offshore wave height from an NDBC buoy | stofs, coops, ndbc |
| [`battery_stofs2d_vs_coops.py`](battery_stofs2d_vs_coops.py) | STOFS-2D-Global forecast vs CO-OPS observations at The Battery, with skill statistics | stofs, coops |
| [`katrina_besttrack_nhc.py`](katrina_besttrack_nhc.py) | Hurricane Katrina (2005) track and intensity from HURDAT2 | nhc |
| [`major_hurricanes_intensity_nhc.py`](major_hurricanes_intensity_nhc.py) | Intensity life cycles of several major Atlantic hurricanes | nhc |

## Replay of saved tool output

| Script | What it shows | Tool output it reads |
|---|---|---|
| [`ian_coops_surge_vs_blowout.py`](ian_coops_surge_vs_blowout.py) | Ian at landfall: positive surge at Fort Myers, negative surge (blowout) at St. Petersburg | `ian_coops_water_levels.json` (coops) |
| [`ian_water_levels_residuals.py`](ian_water_levels_residuals.py) | Ian: observed water level and the residual after removing the tide, at two gauges | `ian_coops_water_levels.json`, `ian_coops_tide_predictions.json` (coops) |
| [`ian_sfmr_vs_besttrack.py`](ian_sfmr_vs_besttrack.py) | Ian: aircraft SFMR wind profile against the HURDAT2 best-track intensity | `ian_sfmr_NOAA20220928H1.json` (recon), `ian_besttrack_AL092022.json` (nhc) |
| [`ian_sfmr_besttrack_v2.py`](ian_sfmr_besttrack_v2.py) | Earlier version of the SFMR vs best-track figure | same as above |
| [`ri_sst_mur_map.py`](ri_sst_mur_map.py) | MUR sea-surface temperature over Rhode Island and Block Island Sound, 2024-07-15 | `ri_sst_mur_20240715.json` (erddap) |
| [`boston_stofs_validation.py`](boston_stofs_validation.py) | STOFS-2D-Global vs CO-OPS at Boston | embedded in the script (stofs) |
| [`boston_stofs3d_validation.py`](boston_stofs3d_validation.py) | STOFS-3D-Atlantic vs CO-OPS at Boston | embedded in the script (stofs) |
| [`newport_stofs_comparison.py`](newport_stofs_comparison.py) | STOFS-2D-Global vs STOFS-3D-Atlantic forecasts at Newport, RI | embedded in the script (stofs) |
| [`newport_stofs_5day_plot.py`](newport_stofs_5day_plot.py) | Five-day STOFS-2D vs STOFS-3D forecast at Newport, RI | `stofs_2d_newport.json`, `stofs_3d_newport.json` (stofs); the script reads them from a hard-coded absolute path, so edit it before running |

## Direct import of a server client

| Script | What it shows | Server |
|---|---|---|
| [`ian_flight_tracks_map.py`](ian_flight_tracks_map.py) | Ian reconnaissance (SFMR) flight tracks with the best track | recon |
| [`ian_sfmr_radial_profiles.py`](ian_sfmr_radial_profiles.py) | SFMR radial wind profiles from Ian reconnaissance missions | recon |
| [`ri_sst_map.py`](ri_sst_map.py) | Sea-surface temperature map of the Rhode Island coast (needs `cartopy`) | erddap |
| [`demo_nhc_arcgis.py`](demo_nhc_arcgis.py) | Active-storm forecast cone from NHC's ArcGIS service, falling back to Hurricane Milton (2024) off-season (needs `cartopy`) | nhc |

## Writing a new example

Start from one of the live MCP scripts (`charleston_vdatum_stofs3d_vs_coops.py`
is a compact one): it carries the small `call_mcp_tool` helper, asks each tool
for `response_format="json"` where the tool offers it, and writes both the
figure and the data behind it. Keep figures under 1600 px on the long side
(e.g. `figsize=(12, 8.5)` at `dpi=100`), and record in the docstring what you
checked against the live service and when.
