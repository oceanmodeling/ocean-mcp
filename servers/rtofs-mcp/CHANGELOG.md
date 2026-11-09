# Changelog: rtofs-mcp

## 0.1.4 (unreleased)

Changes since 0.1.3 (`rtofs-mcp-v0.1.3`, commit `0fccf15`). One tool is renamed; nothing else changes.

### Renamed tool (breaking for callers of the old name)

- **`rtofs_compare_with_observations` is now `rtofs_compare_forecast_times`.**
- **Why:** the tool never used observations. It reads RTOFS values at one point over the 24 h window that ends at a reference time (default: now). It reports the values at the window's first, middle and last valid time steps and the change from the first to the last. The old name suggested a comparison of the model with observations.
- **No alias.** The old name is removed, so the server still lists 8 tools. A client or saved prompt that calls `rtofs_compare_with_observations` now gets an unknown-tool error and must use the new name.
- **Description.** The tool description that clients see now begins: "Compare RTOFS values at two forecast times at one location; no observations are involved."
- **Unchanged:** arguments (`latitude`, `longitude`, `variable`, `time`, `response_format`), defaults, the HYCOM THREDDS request and the markdown and JSON output.

### Python API

- `rtofs_mcp.tools.analysis.rtofs_compare_with_observations` is renamed to `rtofs_mcp.tools.analysis.rtofs_compare_forecast_times`.
