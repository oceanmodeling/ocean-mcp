# Changelog: ww3-mcp

## 0.1.3 (unreleased)

Changes since 0.1.2 (`ww3-mcp-v0.1.2`, commit `5e45c62`). Three tools change: `ww3_get_buoy_history`, `ww3_get_buoy_observations` and `ww3_compare_forecast_with_buoy`. Their JSON responses gain keys and keep the 0.1.2 keys. The history tool now caps and selects rows differently; see "Output schema" below.

### Scientific corrections

- **Realtime observation windows cover the requested hours.** `ww3_get_buoy_observations(hours=N)` and `ww3_compare_forecast_with_buoy(hours_to_compare=N)` took the first N rows of NDBC's realtime2 file, assuming one row per hour. Rows actually come at each station's own interval: NDBC says "Most stations report hourly" (https://www.ndbc.noaa.gov/faq/rt_data_access.shtml), but 41009 writes a row every 10 minutes and 44025 every 30.
  - For 41009 on 2026-11-09, `hours=24` returned 24 rows covering 3 h 50 min.
  - The comparison tool paired the forecast with that same short window. With `hours_to_compare=6` against the 18z cycle it found no overlapping observation at all.
  - Both tools now keep the rows whose timestamp lies within N hours before the latest row in the file (both ends included), whatever the interval: 145 rows (24 h) at 41009 and 46 at 44025.
- **Forecast-observation pairing no longer depends on the host time zone.** `align_timeseries`, used by `ww3_compare_forecast_with_buoy`, parsed the UTC times as naive datetimes and called `.timestamp()`, which reads them as host-local time. On a host with daylight saving, two times on either side of the local clock change came out an hour apart, so pairs within the ±30 min tolerance were lost:
  - **America/New_York host:** forecast 2026-11-01 02:00 against 41009's 01:50 row; the gap was computed as 70 minutes.
  - **Europe/Berlin host:** the GFS-Wave valid time 2026-10-25 03:00 against the 02:50 row.
  - **The fix:** parsed times are now UTC-aware before any arithmetic, as in stofs-mcp 0.3.0. On a UTC host the result is unchanged.

- **Missing-value codes are no longer returned as measurements.** NDBC's historical annual files mark missing values with 9-filled codes, not the `MM` used in realtime files ([NDBC, Measurement Descriptions and Units](https://www.ndbc.noaa.gov/faq/measdes.shtml)). 0.1.2 parsed these files with the realtime parser, so the codes came back as data:
  - For buoy 41009 in 2024, 35,235 of the file's 52,692 rows (66.9%) carry WVHT `99.00`, and 0.1.2 read each as a 99.0 m wave height.
  - With `max_records=100`, 69 of the 101 rows returned had WVHT 99.0, and the markdown summary reported "max 99.0 m, mean 68.0 m".
  - Each column's code is now compared with the field text before number conversion, and a match becomes `null` and is counted. The codes are WDIR/MWD `999`, WSPD/GST/VIS `99.0`, WVHT/DPD/APD/TIDE `99.00`, PRES `9999.0`, ATMP/WTMP/DEWP `999.0`.
  - Genuine values that look similar are kept, e.g. PRES 999.0 hPa (Hurricane Milton, 2024-10-10), MWD 99 degT, DPD 9.09 s.
- **Summary statistics cover the whole file, not a subsample.** 0.1.2 kept every `len // max_records`-th row and computed its summary from those rows only. For 41009 in 2024 with `max_records=5000`, that is every 10th row, whose largest valid wave height is 5.6 m. The file's maximum is 6.32 m at 2024-10-10 08:10 UTC.
  - The summary (valid count, min, max, time of the maximum, rows at the maximum, mean) is now computed over every valid row of the file, whatever `max_records` is.
- **Older file formats.** For pre-2007 headers, 0.1.2 dropped the first data row (taken as a units line). It also gave two-digit years as `0098`, and gave `YYYY` files no timestamp at all. All of these are now handled: one or two header lines, `YY`/`YYYY`/`#YY`, the old names `WD` and `BAR` (renamed to WDIR and PRES), with or without a minute column. Checked on the 41009 files for 1998, 2003, 2006 and 2024.

### Changed behaviour

`ww3_get_buoy_history`:

- **Row cap.** At most `max_records` rows are returned. 0.1.2 returned up to almost twice as many, e.g. 101 for 100 and 5,270 for 5,000.
- **Row selection.** The rows returned are the most recent `max_records` rows of the year, kept consecutively. NDBC's file is oldest-first, and CONVENTIONS.md keeps the tail of such sources. 0.1.2 returned an unannounced stride across the year.
- **Markdown.** Shows the most recent rows, up to `max_records` and at most 100, under a whole-file summary. It ends with a footer naming the rows shown.
- **Missing year.** A year with no annual file (HTTP 404) now returns a message naming the file. 0.1.2 suggested checking forecast cycles. NDBC publishes an annual file only after the year has ended.

`ww3_get_buoy_observations`:

- **Window by timestamp.** The window is now selected by timestamp (see above). A 24 h window at a 10-minute station is about 145 rows, against 24 before.
- **New parameter `max_records`** (default 2000, as in CONVENTIONS.md). It caps the JSON rows, keeping the most recent, since the file is newest-first. It is the only interface addition in these changes.
- **Notes.** A clamped `hours` value (allowed 1-1080), or a file that does not reach back to the window start, is reported in `notes`.
- **Markdown.** States the window and the interval found in the data. Its wave-height summary covers every row in the window.

`ww3_compare_forecast_with_buoy`:

- **Observation window.** Its observations are the rows within `hours_to_compare` hours before the latest buoy row, selected by timestamp.
- **Unchanged.** The forecast hours fetched (0 to `hours_to_compare`, every 3 h, from the latest cycle) and the pairing rule are unchanged. The pairing gives each forecast time the nearest observation with a WVHT within ±30 min; on a tie, the earlier row in the file wins (the newer observation). Its time arithmetic is now in UTC, whatever the host time zone (see above).

### Output schema (JSON, `ww3_get_buoy_observations` and `ww3_compare_forecast_with_buoy`)

- **`ww3_get_buoy_observations`.**
  - Kept: `station_id`, `records` (now equal to `returned`), `observations`.
  - Added:
    - `timezone` (UTC);
    - `window` (`hours`, `reference`, `latest_time`, `window_start`, `rows_in_file`, `rows_in_window`, `undated_rows`, `oldest_time_in_file`, `covers_full_window`, `typical_interval_minutes`);
    - the truncation envelope `truncated`, `returned`, `total`, `hint` (when truncated);
    - `notes` (when any), `retrieved_at`.
- **`ww3_compare_forecast_with_buoy`.** Adds `observation_window` (the same fields plus `rows_with_wvht`). The markdown also gains an "Observations" line naming the window.

### Output schema (JSON, `ww3_get_buoy_history`)

- **Kept:** `station_id`, `year`, `records` (now always equal to `returned`), `observations`.
- **Added:**
  - `source` (product, file, URL), `timezone` (UTC), `units`, `units_source`;
  - `file_format` (header lines, column names, renames, two-digit year, minute column);
  - `rows_in_file`, `malformed_rows_skipped`;
  - `missing_values` (rule, documentation URL, per-column `codes` and `excluded_counts`);
  - `summary` (`variable`, `units`, `covers`, `missing`, `valid`, `min`, `max`, `max_time`, `max_count`, `mean`);
  - `row_selection`, and the truncation envelope `truncated`, `returned`, `total`, `hint` (when truncated);
  - `time_note` (when the file has no minute column), `retrieved_at`.
- **Changed:** values in `observations` that were missing-value codes are now `null`. Two-digit years are now four digits.

### Python API

- New: `utils.parse_ndbc_historical(text) -> (records, info)`, `utils.summarize_values(records, key)` and `utils.select_recent_window(records, hours) -> (rows, info)`.
- New constants in `models.py`: `NDBC_HISTORICAL_MISSING_CODES`, `NDBC_HISTORICAL_RENAMES`, `NDBC_STDMET_UNITS`.
- `format_wave_observation_table` gains optional `summary_lines` and `footer` arguments. Without them its output is unchanged.
- `parse_ndbc_realtime` is unchanged.

### Known limitations

- The annual files seen hold up to 52,692 rows. Returning all of them is not possible (`max_records` ≤ 5000), and the tool has no date filter, so only the summary covers the whole year.
- Values written as `0.00` in some older files are kept. In 41009's 2003 file, WVHT, DPD and APD are all `0.00` for 24 consecutive hours. NDBC does not document `0.00` as missing.
- Files without a minute column (e.g. 1998) can hold several rows per hour, so `max_time` is to the hour there.
