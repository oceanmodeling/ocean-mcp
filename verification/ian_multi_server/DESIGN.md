# Design: Hurricane Ian (2022) through five MCP servers

Frozen on 2026-11-21 (UTC), before the Part A recording. Later changes go in `AMENDMENTS.md`, each with its time, its reason, and whether it was made before or after values were seen.

This is a **scripted multi-server MCP workflow**. The tool sequence and every argument are fixed here and in `scripts/record_part_a.py`. No language model selects or invokes a tool. The package tests no safeguard and is not an evaluation.

## 1. What had been seen before this design was written

The feasibility step (Phase 0, 2026-11-21 02:11–02:45 UTC) used the same released wheels. It saw the following, and nothing else:

- **Reconnaissance:** HDOB record counts per aircraft call sign on 28 September 2022 (totals, non-null SFMR, non-null flight-level wind) and the time span of each aircraft. The distance to the storm centre was not computed. Separately, the first 1.5 kB of the July file `examples/ian_sfmr_NOAA20220928H1.json` was printed; it shows three SFMR radial bins for the N42RF flight.
- **Buoys:** for the 102 NDBC stations within 300 km of the track, counts of non-null WVHT, WSPD and PRES in the window. No value was looked at.
- **No river gauge is used** (decision 4 of the author's reply), so the USGS counts seen in Phase 0 play no part here.
- **Reused responses:** the water-level values were already published by `verification/ian_cross_server/` (+2.209 m, −1.755 m, 2.613 m).

## 2. Servers

One environment holds the released PyPI wheels; every server runs as its own process from a neutral working directory. The SHA-256 values below are those of the PyPI wheels, recorded in Phase 0; `scripts/make_env.py` checks them again.

| Server | Version | Wheel SHA-256 | Role |
|---|---|---|---|
| nhc-mcp | 0.1.1 | `34bd7bb5b2b1dc6995d20572acff5afc47b198d69570b93bfd5e037035811c25` | Best track (reused response) |
| coops-mcp | 0.1.1 | `f9630bc8bf7e024aff0ade1ec2e9a696487e3fdccc1e2b9860a6c5e64846f210` | Station metadata, water levels, predictions (reused responses) |
| recon-mcp | 0.1.3 | `338a5a84ae70c8c0d38b47b6a2c2bfc13543dfb068c0085dd6a1075450d6a9e8` | HDOB flight-level and SFMR winds (new recording) |
| ww3-mcp | 0.1.3 | `8825e2ce75b1f102f1561c68ac03de12de93e98cbc90090d68a2d3a60b1c942d` | Buoy wave height for 2022 from the NDBC annual file (new recording) |
| ndbc-mcp | 0.1.2 | `0ad49f38aa4822bdfa03be5fe3be381d28b6998c417ac475f5f2184af35c6817` | Buoy station metadata only (new recording) |

ndbc-mcp cannot return 2022 observations: it reads NDBC `realtime2`, at most 1080 h back. Wave heights therefore come from `ww3_get_buoy_history` (ww3-mcp). Every caption and the report name ww3-mcp as their source.

## 3. Reused responses (read-only)

- **Source:** `verification/ian_cross_server/session_record.json`, read in place and never written.
- **Check before use:** its SHA-256 must be `cc8b52830f23ca98be0ea932e196accc2775490cb6c55542608f9f6ee4fcf1bd`, the value in that package's `manifest.json`. Any mismatch stops the run.

| Call | Server | Tool | Arguments |
|---|---|---|---|
| 1 | nhc-mcp | `nhc_get_best_track` | AL092022, json |
| 2, 5 | coops-mcp | `coops_get_station` | 8725520 (Fort Myers), 8726520 (St. Petersburg); expand details and datums; metric |
| 3, 6 | coops-mcp | `coops_get_water_levels` | 2022-09-27 to 2022-09-29, MLLW, metric, GMT, 6-min, json |
| 4, 7 | coops-mcp | `coops_get_tide_predictions` | same arguments as the water levels |

## 4. New recording (Part A)

One client process holds three MCP stdio sessions at once: recon-mcp, ww3-mcp and ndbc-mcp. The calls run in the fixed order below, with a 3 s pause before each call after the first. Each server's stderr log is archived, because it shows the upstream HTTP status codes.

| # | Server | Tool | Arguments |
|---|---|---|---|
| R1 | recon-mcp | `recon_get_hdobs` | `year=2022, basin="al", month=9, day=28, limit=1000, max_records=20000, response_format="json"` |
| R2 | recon-mcp | `recon_get_hdobs` | same, `day=29` (bulletins filed just after midnight can hold observations from 28 September) |
| R3 | recon-mcp | `recon_list_sfmr` | `year=2022, storm_name="ian", response_format="json"` |
| R4 | recon-mcp | `recon_get_sfmr` | `year=2022, storm_name="ian", storm_number=9, filename="NOAA_SFMR20220928H1.nc", response_format="json"` |
| N1 | ndbc-mcp | `ndbc_get_station` | `station_id=<selected buoy>` |
| W1 | ww3-mcp | `ww3_get_buoy_history` | `station_id=<selected buoy>, year=2022, max_records=5000, response_format="json"` |

- **R3 and R4 document the two SFMR tools as not working.** In Phase 0 both received HTTP 403 from AOML. If either now works, its response is archived and reported, but it is not used in any panel.
- **Retries:** none. A failure is recorded as it is. If R1, R2, N1 or W1 fails, the call is repeated once after 60 s and the repeat is logged in `AMENDMENTS.md`.
- **Truncation:** R1 and R2 must report `truncated: false`. W1 must reach back to 2022-09-27 00:00, i.e. the first returned row is no later than that time; otherwise the panel cannot be drawn and this is reported.

## 5. Times

| Item | Definition |
|---|---|
| Landfall | 19:05 UTC 28 September 2022, Cayo Costa, 26.7°N 82.2°W. Cited from the NHC Tropical Cyclone Report (revised 12 March 2026), as quoted and checksummed in `verification/ian_cross_server/references.json`. Not taken from a tool. |
| Best track shown | Records from 2022-09-26 00:00 to 2022-09-30 00:00 UTC. |
| Panel (b) | HDOB observations of the selected aircraft whose observation time (UTC) falls on 2022-09-28. |
| Panel (c) | 2022-09-27 00:00 to 2022-09-30 00:00 UTC, both ends included. |
| Panel (d) | 2022-09-27 00:00 to 2022-09-29 23:54 UTC (the window of the reused responses). |

HDOB observation time is the record's date and `hhmmss`. Per the NHC format document it is the midpoint of the 30-s averaging interval.

## 6. Selection rules

### 6.1 Buoy (rule as amended, `AMENDMENTS.md` A1)

**Candidates.** The Phase 0 candidate set:
- the stations returned by `ndbc_find_nearest_stations` around three track points;
- that lie within 300 km of the best track between 27 September 00:00 and 30 September 00:00 UTC;
- for which `ww3_get_buoy_history` (2022) reaches the panel window and returns at least one non-null WVHT in it.

**Rule.** The buoy whose closest approach to the best track between 2022-09-27 00:00 and the landfall time (2022-09-28 19:05 UTC) is smallest. Ties go to the larger number of non-null WVHT rows in the panel (c) window.

**Geometry.**
- Track: linear interpolation in time between best-track records, latitude and longitude each linear in degrees, sampled every 5 minutes.
- Distance: haversine, sphere of radius 6371.0088 km.
- Station positions: from `ndbc_find_nearest_stations`, i.e. NDBC's current `activestations.xml`. A buoy's 2022 position may differ slightly; no tool returns the 2022 position.

**Outcome.** Computed before this design was written, from positions and counts only: **42097 (Pulley Ridge, FL)**, closest approach 86.1 km at 08:30 UTC on 28 September; 144 non-null WVHT rows in the window. The next candidate is 42095 at 96.7 km. `scripts/select_buoy.py` recomputes this offline from the archived Phase 0 responses in `archive/phase0_selection/`.

**Not reachable.** Four stations that are probably wave buoys cannot be candidates: 41009, 41010, 42056 and 42036. Their 2022 files have 10-minute rows, and the last 5000 rows begin in late November.

### 6.2 Aircraft

**Data.** The records of R1 and R2 whose observation date is 2022-09-28 (UTC).

**Count.** For each aircraft call sign (the tool's `aircraft` field), count the records that meet all of these:
- `sfmr_sfc_wind_kt` is not null;
- latitude and longitude are not null;
- the distance to the best-track centre at the record time is at most 150 km.

The centre comes from the best track interpolated linearly in time as in 6.1. Records outside the best track's time span are not counted.

**Selection.** The call sign with the largest count is selected.
- Ties go to the larger number of records with non-null SFMR on 28 September, then to alphabetical order.
- The count uses the records as returned, before any QC removal. The count after QC removal (section 7) is also reported, as a sensitivity check; it does not change the selection.

**Labelling.** The selected aircraft is labelled by its call sign. No mission number is asserted: the HDOB records carry the call sign only.

## 7. HDOB quality-control flags

**Source.** NHC, "High Density Observations (HDOB) Bulletin", `https://www.nhc.noaa.gov/abouthdobs_2007.shtml`.
- Retrieved 2026-11-21 17:30:35 GMT with curl, outside MCP.
- SHA-256 `3ad3a4e221296fb7889c495b962fd6aa1bdfe9ae21f1664bf03ffb4fef337eef`.
- Archived as `archive/references/abouthdobs_2007.shtml`.
- `scripts/check_references.py` checks the quoted lines against it.

**FF: two digits.** recon-mcp passes the field through undecoded, as the string `qc_flags`.

First digit, positional variables:

| Code | Meaning (quoted) |
|---|---|
| 0 | All parameters of nominal accuracy |
| 1 | Lat/lon questionable |
| 2 | Geopotential altitude or static pressure questionable |
| 3 | Both lat/lon and GA/PS questionable |

Second digit, meteorological variables:

| Code | Meaning (quoted) |
|---|---|
| 0 | All parameters of nominal accuracy |
| 1 | T or TD questionable |
| 2 | Flight-level winds questionable |
| 3 | SFMR parameter(s) questionable |
| 4 | T/TD and FL winds questionable |
| 5 | T/TD and SFMR questionable |
| 6 | FL winds and SFMR questionable |
| 9 | T/TD, FL winds, and SFMR questionable |

**Removal rules, applied to the plotted series only:**

| Removed | When | What is removed |
|---|---|---|
| SFMR surface wind (and its rain rate) | Second digit is 3, 5, 6 or 9 | The value |
| Flight-level wind | Second digit is 2, 4, 6 or 9 | The value |
| Position | First digit is 1 or 3 | The record, from the flight track in panel (a) only |
| Unrecognised code | A digit not in the tables, or a field that is not two digits | Every variable the digit governs |

T/TD and GA/PS flags remove nothing, because those variables are not used.

**Reporting.** The report gives, for the selected aircraft, the number of records with each flag value, and the number of SFMR values, flight-level wind values and positions each flag removed.

**Missing values** (`999` in the bulletin) arrive as null from the tool. They are counted separately from flag removals.

## 7a. Variables, units and derived numbers

| Quantity | Source | Unit | Computed by |
|---|---|---|---|
| SFMR surface wind: highest 10-s mean in the encoding interval (NHC document) | R1/R2 `sfmr_sfc_wind_kt` | kt | returned |
| Flight-level wind, 30-s mean | R1/R2 `fl_wind_speed_kt` | kt | returned |
| Best-track maximum wind at the nearest record | call 1 `max_wind` of the best-track record nearest in time to each HDOB record (equidistant: earlier record) | kt | client |
| Distance of an HDOB record to the storm centre | R1/R2 position, call 1 interpolated centre | km | client |
| Significant wave height | W1 `WVHT` (the tool returns NDBC 9-filled codes as null) | m | returned |
| Water level, prediction | calls 3, 4, 6, 7 | m, MLLW | returned |
| Residual = observed − predicted, exact timestamp match, integer millimetres | calls 3, 4, 6, 7 | m | client |

- **Axes.** Winds are plotted in kt, with a right-hand axis in m/s (1 kt = 1852/3600 m/s exactly).
- **Panel (c) gaps.** The line breaks where WVHT is null or where consecutive rows are more than 1.5 times the median row interval apart. The report counts window rows, null WVHT rows, and missing slots implied by the median interval.
- **Panel (c) second axis.** A second axis (WSPD or PRES) is drawn only if that variable is non-null in at least 90 % of the window rows. 42097 is listed with no meteorological sensors, so none is expected.
- **Panel (d) checks.** `run_all.sh` fails unless:
  - Fort Myers has a residual maximum of +2.209 m, first reached at 22:18 UTC on 28 September (tied at 22:30);
  - St. Petersburg has a residual minimum of −1.755 m at 23:00 UTC;
  - the Fort Myers observed maximum is 2.613 m above MLLW.

## 8. Figures

**Main figure.** Four panels, 190 mm × 130 mm, vector PDF and 600 dpi PNG. The page size is exact: `bbox_inches` is not used.

| Panel | Content |
|---|---|
| (a) | Best track in longitude/latitude, coloured by the Saffir–Simpson category that nhc-mcp returns (it derives `category` from `max_wind`). Also: the two tide gauges (positions from calls 2 and 5), the buoy (position from N1), the selected aircraft's flight track (QC-passing positions) and the landfall point (TCR). No coastline: no MCP server supplies one, and a non-MCP coastline would be an unarchived input. |
| (b) | SFMR surface wind and flight-level wind against time for the selected aircraft, with the best-track maximum wind at the nearest record as a step line. |
| (c) | WVHT at 42097 against time. Gaps as defined above. |
| (d) | Observed water level and residual at Fort Myers and St. Petersburg in one panel. |

**Style** (as in the 190 mm Boston figure):
- palette `#2a78d6`, `#eb6834`, ink `#0b0b0b`;
- no title inside the image; bold panel labels at top left;
- no text under 8 pt at final size;
- landfall as a dashed vertical line on the time panels (b, c, d) where 19:05 UTC lies inside the axis range. If it falls outside a panel's range, the caption says so.

**Checks after drawing**, reported in `results/figure_checks.json`:
- smallest font size at final size;
- whether any legend's bounding box contains a plotted data point, in display coordinates.

**Fallback figure.** Two panels, 190 mm wide:
- (a) best track with the selected aircraft's flight track, coloured by QC-passing SFMR wind;
- (b) the water levels as in (d).

## 9. Offline replay

`run_all.sh` needs no network. It:
1. checks the SHA-256 of every archived file against `archive/MANIFEST.sha256`, and of the reused Ian session;
2. re-runs the selection, the analysis and the figures;
3. compares every result and figure file with `results/SHA256SUMS`;
4. exits non-zero on any mismatch.

**Environment.**
- Analysis: standard library only (`python3 -I`).
- Figures: the pinned plotting set in `scripts/requirements-figures.txt` (matplotlib 3.10.8 on CPython 3.13.12), installed by uv from its cache with `--offline`.

The check is run once from a scratch copy outside the repository, inside `unshare -rn` (no network interface).

## 10. Not done

- No language model, no prompt, no evaluation.
- No server code changed.
- No USGS gauge.
- No AOML SFMR NetCDF data (the tools that read it fail; see R3, R4).
