# Changelog: stofs-mcp

## 0.3.0 (unreleased)

Changes since 0.2.0 (`stofs-mcp-v0.2.0`, commit `5e45c62`). This release changes default behaviour and output schemas. Callers that parse JSON responses should read "Output schema" below.

### Scientific corrections

- **Version-aware vertical datum.** The STOFS v3.1 upgrade, operational from the 2026-08-17 12z cycle, moved STOFS-3D-Atlantic station NetCDF from NAVD88 to LMSL (NWS SCN 26-51). 0.2.0 labelled every 3D cycle NAVD88 and compared it against CO-OPS NAVD; at Boston that misstated the bias by 9.2 cm.
  - The datum is now read from each file's `zeta` metadata.
  - The CO-OPS request datum follows it: LMSL → MSL, NAVD88 → NAVD.
- **No assumed datum for unfamiliar metadata.** Labels are classified as absent, generic, recognized, unsupported or conflicting. The datum becomes `undetermined`, and no comparison is made, in these cases:
  - an unrecognized explicit reference (e.g. NGVD29, NAVD2022, ellipsoid, GMSL);
  - contradictory attributes;
  - a 3D file without a datum label;
  - a 2D file from an unrecognized producer or an undocumented version.
- **Version-bounded STOFS-2D fallback.** 2D files carry ADCIRC's generic "above geoid" label, so their datum comes from documentation. That happens only for documented versions:
  - STOFS_2D_GLOBAL V3.1.x and V2.1.x resolve to LMSL with no warning;
  - ESTOFS GLOBAL V2.1.x resolves to LMSL with a "datum assumed" warning;
  - any other version (e.g. V3.2, V4.0) is `undetermined`.
- **Shifted no-data sentinels and implausible values are excluded.** NOAA station files contain no-data codes shifted by a per-station constant, so they no longer equal `_FillValue`:
  - STOFS-3D v3.1 writes 1e7 + c at five Caribbean stations;
  - STOFS-2D v3.1 writes −99999 + 0.4 during dry periods.

  0.2.0 ranked the 3D sentinels as 9,999,999 m water levels and returned them as forecasts. The new rule, applied by every tool:
  - |value| ≥ 10⁴ m is a `sentinel`;
  - 50 m ≤ |value| < 10⁴ m is `implausible` (the rationale is in `models.py`; e.g. STOFS-2D station SA816 reports 90–136 m).
- **Swapped coordinates repaired.** In pre-v3.1 STOFS-3D files, 105 of 108 rows store latitude in `x`. Point lookup and region filtering failed for those cycles.
- **Coordinate corrections are reported** (WP1 finding D1). The station, point and max tools now say when the STOFS-3D coordinate check swapped records: how many, by what rule, and whether the station returned was one of them, with its stored values. Before, the correction was silent.
  - A record that reads as neither orientation is not guessed. Its position is reported as undetermined, it is not used for location, and its latitude and longitude are `null`. This happens when the coordinates have the same sign, are zero or are not finite; no real file checked so far contains such a record.
- **Non-finite values.** NaN, ±Inf, masked and fill values are excluded and counted, never replaced by zero. JSON never contains `NaN` or `Infinity`.
- **Pairing.** One-to-one: exact timestamps first, then the nearest unused observation within 3 min, with ties going to the earlier one. Arithmetic is in UTC. 0.2.0 could pair one observation with two model times, and its results depended on the host timezone.

### New parameters

- `stofs_compare_with_observations(lead_start_hours=None, lead_end_hours=None)`: a lead-time window (lead_start < lead ≤ lead_end, measured from the cycle time) for comparing models over identical valid times. When set, it replaces `hours_to_compare`.

### Changed defaults and behaviour

- `stofs_compare_with_observations`:
  - The default `hours_to_compare` changed from **24 to 72**, because a 24 h window starting at the nowcast missed peaks a day after the cycle.
  - The window is measured from the file's first record, even if that record is invalid.
  - Clamping to 96 h is disclosed.
  - Observations are requested only for the window.
  - Comparison is refused, with a reason and no CO-OPS request, when the datum is undetermined or has no CO-OPS equivalent, or when every model value is excluded.
- An invalid cycle hour (e.g. "07" for 2D, "00" for 3D) is rejected before any network access.
- `stofs_get_max_water_level` no longer ranks sentinel or implausible values. It lists stations without any valid value in `excluded_stations`.
- Station and point tools explain an all-excluded series instead of returning its values.

### Output schema (JSON)

- **Added, all station tools:**
  - `datum_source`;
  - `datum_warning` (null when there is nothing to report);
  - `datum_provenance`: datum, resolution, comparable, source, warning, documented_datum, product_version, raw attributes.
- **Added, station and point tools:** `excluded_model_records`, with counts for `masked_or_fill`, `nonfinite`, `sentinel` and `implausible`.
- **Added, `stofs_get_max_water_level`:** `excluded_values`, `excluded_stations`.
- **Added, `stofs_get_station_forecast`, `stofs_get_point_forecast` and `stofs_get_max_water_level`** (WP1 findings D1, D2), placed after `datum_provenance`:
  - `units`, from the file's `zeta:units` (`"m"` in every STOFS station file; `"m"` if the attribute is missing, as the comparison tool assumes);
  - `coordinate_warning`, one sentence or null;
  - `coordinate_provenance`, with `checked`, `rule`, `stations_in_file`, `stations_corrected`, `stations_undetermined` and `undetermined_stations`. The station and point tools add `station` (`corrected`, `undetermined`, `stored_x`, `stored_y`).
- **Markdown, the same three tools:** one "Coordinate warning" line when a correction was made or a record is undetermined.
- **Added, `stofs_compare_with_observations`:**
  - `cycle_time`, `window_lead_hours`, `statistics_by_segment` (nowcast/forecast);
  - `window` (definition, file start, requested end, model-available and matched spans, excluded records);
  - `lead_window_hours` and `coverage_note` (when a lead window is used);
  - `hours_to_compare_requested` (when clamped);
  - `stofs_datum_source`, `datum_provenance`, `datum_note`;
  - `statistics.max_abs_error`, `statistics.n_excluded_nonfinite`;
  - `alignment`, an object with the method and the exact, nearest, unmatched, bad-time and duplicate counts (0.2.0 had no such key);
  - `observation_quality`, with record, status, flag and exclusion counts and a `matched` sub-object (0.2.0 had no such key);
  - `station_warning`, one sentence or null (see "WP5 fixes" below).
- **Changed, `stofs_compare_with_observations`:**
  - `statistics.correlation` is `null` for a constant series (0.2.0 emitted `NaN`).
  - `hours_to_compare` is `null` when a lead window is used.
  - `statistics.peak_error` is kept as a legacy alias of `max_abs_error`, which is max |model − observed|. It is not the error in the peak water level; that is `summary.peak_error_m`.

### WP5 fixes (from the sampled evaluation of 15,197 station-cycles)

- **CO-OPS rejections are reported with CO-OPS's message.** When the CO-OPS Data API rejects a
  request with a JSON error (for example HTTP 400 "There is no MSL for the station: …" or "The
  supported Datum values are: …"), `fetch_coops_observations` raises `ValueError` with that
  message, so `stofs_compare_with_observations` answers "Could not fetch CO-OPS observations:
  CO-OPS API error: <message>". Before, the HTTP error reached the generic handler, which blamed
  the S3 bucket and suggested a retry (465 cases in the sampled evaluation).
- **Duplicated station identifiers are reported.** When more than one record of a station file
  matches the requested identifier, the first is still used, and `stofs_compare_with_observations`
  and `stofs_get_station_forecast` add `station_warning` (JSON) and a "Station warning" line
  (Markdown). They name the matching records, the one used, and the largest absolute difference
  between their valid values: in the comparison window for the comparison, and over the series
  for the station forecast. In real STOFS-2D-Global files, 8414721 sits on "Fort Point, ME" and
  "Frankfort, ME", whose values differ by up to 0.15 m.
- **The tidal-datum epoch in the datum note.** When observations are requested on a CO-OPS tidal
  datum (MSL, MLLW, …), `datum_note` adds that the datum is defined on a tidal-datum epoch (1983–2001
  at most stations), that recent mean sea level may differ from it, and that a mean bias includes
  that difference unless the model carries present-day mean level. The station's epoch is not
  fetched or checked.

### Python API

- `stofs_mcp.models.MODEL_DATUMS` and `COOPS_VALIDATION_DATUMS` keep their 0.2.0 values but emit a `DeprecationWarning`. They are wrong for STOFS-3D cycles from 2026-08-17 12z, and no tool uses them. Use `utils.resolve_station_datum()` / `models.documented_station_datum()` and `COOPS_DATUM_FOR_MODEL_DATUM` instead. Planned removal: 1.0.
- New public helpers: `classify_datum_label`, `read_datum_metadata`, `resolve_station_datum`, `documented_fallback`, `datum_provenance`, `valid_values`, `exclusion_masks`, `value_exclusion_reason`, `match_timeseries`, `dumps_strict`, `unswap_station_coords`.
- `parse_station_netcdf()` returns extra keys (datum classification, `product`, `n_records`, `excluded_model_records`, `coordinate_check`, `units`) and accepts `model=`.
- New helpers for the coordinate report and units: `check_station_coords`, `coordinate_provenance`, `coordinate_warning`, `coordinate_markdown_lines`, `zeta_units`. `unswap_station_coords` keeps its signature; a record that reads as neither orientation now comes back as NaN instead of unchanged.
- `align_timeseries()` keeps its signature, but pairing is now one-to-one.

### Known limitations

- The retired NOMADS OPeNDAP route (`stofs_get_gridded_forecast`) still returns a retirement notice.
- `swl` (surge residual) output is still labelled with the station datum.
- Coordinate repair is limited to the STOFS-3D sign pattern; station identity is not validated.
