# Changelog: rtofs-mcp

## 0.1.4 (unreleased)

Changes since 0.1.3 (`rtofs-mcp-v0.1.3`, commit `0fccf15`). One tool is renamed, `rtofs_get_latest_time` now reports the dataset's real time range, and three docstrings now describe the default time correctly.

### Renamed tool (breaking for callers of the old name)

- **`rtofs_compare_with_observations` is now `rtofs_compare_forecast_times`.**
- **Why:** the tool never used observations. It reads RTOFS values at one point over the 24 h window that ends at a reference time (default: now). It reports the values at the window's first, middle and last valid time steps and the change from the first to the last. The old name suggested a comparison of the model with observations.
- **No alias.** The old name is removed, so the server still lists 8 tools. A client or saved prompt that calls `rtofs_compare_with_observations` now gets an unknown-tool error and must use the new name.
- **Description.** The tool description that clients see now begins: "Compare RTOFS values at two forecast times at one location; no observations are involved."
- **Unchanged:** arguments (`latitude`, `longitude`, `variable`, `time`, `response_format`), defaults, the HYCOM THREDDS request and the markdown and JSON output.

### Fixed: `rtofs_get_latest_time` reports the dataset's first and last times

- **0.1.3 reported neither end of the data.**
  - `last_time` was the time step nearest the current time: the row NCSS returns for `time=present`.
  - `first_time` was the first `time_origin` attribute in the DAS, which belongs to `tau`.
  - For example, at 2026-11-09T05:42Z it reported 2026-11-06 12:00 to 2026-11-09T06:00Z for ssh. The time coordinate actually ran from 2026-10-30T12:00Z to 2026-11-15T12:00Z, as did THREDDS's own `TimeSpan`.
- **Now** it reads the dataset's time coordinate over OPeNDAP:
  - the DAS gives the CF units of `time` and `time_run`;
  - the `.ascii?time,time_run` request gives their values.
  - `first_time` and `last_time` are the smallest and largest valid values. NaN entries, the coordinate's `missing_value`, are skipped. Units other than `seconds/minutes/hours/days since <UTC date>`, and non-Gregorian calendars, are reported as errors rather than guessed.
- **The response says which dataset the times belong to:** its key, description, THREDDS path and variables. It also gives the number of time steps and their spacing, the newest model run (the largest `time_run`), `timezone`, the time units, the source URL and `retrieved_at`.
- **Requests:** two small OPeNDAP requests (DAS and ASCII time values) replace three. The three were an NCSS query for 1900 whose response was discarded, the DAS, and an NCSS `time=present` query.
- **Errors:** failures are now reported as `RTOFS Error: … — <next step>`, naming the dataset path. 0.1.3 returned a generic "could not retrieve" message for every failure.

### Documentation: default time of the single-time tools

- `rtofs_get_profile_forecast`, `rtofs_get_area_forecast` and `rtofs_get_transect` said their `time` defaults to "latest". They send `time=present`, which THREDDS NCSS resolves to "the time slice closest to" the current time ([NCSS reference](https://docs.unidata.ucar.edu/tds/current/userguide/netcdf_subset_service_ref.html)). That is the step nearest now, not the last forecast step.
- The docstrings now say: "THREDDS returns the nearest time step. Default: the step nearest the current time ('present')."
- Behaviour is unchanged.

### Output schema (JSON, `rtofs_get_latest_time`)

- **Kept:** `dataset`, `first_time`, `last_time`. The values are now the time coordinate's ends, in `YYYY-MM-DDTHH:MM:SSZ` form; 0.1.3's `first_time` had the form `YYYY-MM-DD HH:MM:SS`.
- **Added:** `description`, `thredds_dataset`, `variables`, `n_time_steps`, `time_step_hours` (null if the spacing is uneven), `latest_run`, `timezone`, `time_units`, `source`, `source_url`, `retrieved_at`.

### Python API

- `rtofs_mcp.tools.analysis.rtofs_compare_with_observations` is renamed to `rtofs_mcp.tools.analysis.rtofs_compare_forecast_times`.
- `RTOFSClient.get_dataset_time_range` now raises `RTOFSAPIError` instead of returning `None`.
  - It still returns `first` and `last`, now as ISO 8601 UTC.
  - It adds `n_time_steps`, `time_step_hours`, `latest_run`, `time_units`, `thredds_path` and `source_url`.
- New private helpers in `rtofs_mcp.client`: `_parse_das_attributes`, `_parse_opendap_ascii`, `_cf_time_to_datetime`, `_iso_utc`.
