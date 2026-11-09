# Changelog: ww3-mcp

## 0.1.3 (unreleased)

Changes since 0.1.2 (`ww3-mcp-v0.1.2`, commit `5e45c62`). Only `ww3_get_buoy_history` changes. Its JSON response gains keys, keeps the 0.1.2 keys, and now caps and selects rows differently; see "Output schema" below.

### Scientific corrections

- **Missing-value codes are no longer returned as measurements.** NDBC's historical annual files mark missing values with 9-filled codes, not the `MM` used in realtime files ([NDBC, Measurement Descriptions and Units](https://www.ndbc.noaa.gov/faq/measdes.shtml)). 0.1.2 parsed these files with the realtime parser, so the codes came back as data:
  - For buoy 41009 in 2024, 35,235 of the file's 52,692 rows (66.9%) carry WVHT `99.00`, and 0.1.2 read each as a 99.0 m wave height.
  - With `max_records=100`, 69 of the 101 rows returned had WVHT 99.0, and the markdown summary reported "max 99.0 m, mean 68.0 m".
  - Each column's code is now compared with the field text before number conversion, and a match becomes `null` and is counted. The codes are WDIR/MWD `999`, WSPD/GST/VIS `99.0`, WVHT/DPD/APD/TIDE `99.00`, PRES `9999.0`, ATMP/WTMP/DEWP `999.0`.
  - Genuine values that look similar are kept, e.g. PRES 999.0 hPa (Hurricane Milton, 2024-10-10), MWD 99 degT, DPD 9.09 s.
- **Summary statistics cover the whole file, not a subsample.** 0.1.2 kept every `len // max_records`-th row and computed its summary from those rows only. For 41009 in 2024 with `max_records=5000`, that is every 10th row, whose largest valid wave height is 5.6 m. The file's maximum is 6.32 m at 2024-10-10 08:10 UTC.
  - The summary (valid count, min, max, time of the maximum, rows at the maximum, mean) is now computed over every valid row of the file, whatever `max_records` is.
- **Older file formats.** For pre-2007 headers, 0.1.2 dropped the first data row (taken as a units line). It also gave two-digit years as `0098`, and gave `YYYY` files no timestamp at all. All of these are now handled: one or two header lines, `YY`/`YYYY`/`#YY`, the old names `WD` and `BAR` (renamed to WDIR and PRES), with or without a minute column. Checked on the 41009 files for 1998, 2003, 2006 and 2024.

### Changed behaviour

- **Row cap.** At most `max_records` rows are returned. 0.1.2 returned up to almost twice as many, e.g. 101 for 100 and 5,270 for 5,000.
- **Row selection.** The rows returned are the most recent `max_records` rows of the year, kept consecutively. NDBC's file is oldest-first, and CONVENTIONS.md keeps the tail of such sources. 0.1.2 returned an unannounced stride across the year.
- **Markdown.** Shows the most recent rows, up to `max_records` and at most 100, under a whole-file summary. It ends with a footer naming the rows shown.
- **Missing year.** A year with no annual file (HTTP 404) now returns a message naming the file. 0.1.2 suggested checking forecast cycles. NDBC publishes an annual file only after the year has ended.

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

- New: `utils.parse_ndbc_historical(text) -> (records, info)` and `utils.summarize_values(records, key)`.
- New constants in `models.py`: `NDBC_HISTORICAL_MISSING_CODES`, `NDBC_HISTORICAL_RENAMES`, `NDBC_STDMET_UNITS`.
- `format_wave_observation_table` gains optional `summary_lines` and `footer` arguments. Without them its output is unchanged.
- `parse_ndbc_realtime` is unchanged.

### Known limitations

- The annual files seen hold up to 52,692 rows. Returning all of them is not possible (`max_records` ≤ 5000), and the tool has no date filter, so only the summary covers the whole year.
- Values written as `0.00` in some older files are kept. In 41009's 2003 file, WVHT, DPD and APD are all `0.00` for 24 consecutive hours. NDBC does not document `0.00` as missing.
- Files without a minute column (e.g. 1998) can hold several rows per hour, so `max_time` is to the hour there.
