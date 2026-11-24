# Hurricane Ian (2022) through five MCP servers: report

Run date: 2026-11-21 (UTC). Branch `docs/breadth-examples`, created from the local `origin/main` ref (575cd21) without fetching. The design was committed in `fdce9bb` before anything was recorded; the data and scripts are in `bdadd79`. The figures were revised on 2026-11-22 in `dffe3cb` (`AMENDMENTS.md` A6–A9); no result value changed except the best-track reference in panel (b). On 2026-11-23 the NHC report's quotation on the 160 kt flight-level wind was verified against the PDF (A10). AF301's 10-second peak flight-level wind (A11) and a comparison of AF301's SFMR peak with the report's 137-138 kt (A12) were added as descriptive numbers.

This is a **scripted multi-server MCP workflow**. The tool sequence and the arguments are fixed in `DESIGN.md` and `scripts/record_part_a.py`. No language model selected or invoked a tool. The package tests no safeguard and is not an evaluation.

## How numbers are tagged

| Tag | Meaning |
|---|---|
| `[T: tool, call, file]` | The number was returned by that tool, in that call of that archived file. |
| `[C: script:line]` | The client computed it at that line. The line numbers are also stored in `results/part_a_numbers.json`. |
| `[D: DESIGN.md §n]` | Design parameters: windows, radii, thresholds. |
| `[E: archive/env_provenance.json]` | Versions and checksums. |
| `[N: archive/non_mcp/natural_earth/]` | The one non-MCP input: the Natural Earth 1:50m coastline, drawn for orientation only. |
| `[cited]` | Quoted from a cited document, with the check recorded under `archive/references/`. |

The two archived Part A files are `archive/part_a_record.json.gz` (written **A** below) and the reused `verification/ian_cross_server/session_record.json` (written **I**).

## 1. Summary

1. **Recording.** One client process held three MCP stdio sessions at once (recon-mcp, ww3-mcp, ndbc-mcp) and made six calls between 17:42:03 and 17:42:56 UTC. The nhc-mcp and coops-mcp responses were reused from `verification/ian_cross_server/`. They were read in place, after their SHA-256 was verified, and never written.
2. **Aircraft.** The frozen rule selected **AF301** [C: scripts/analyze_part_a.py:193]: 506 HDOB records with an SFMR wind within 150 km of the storm centre [C: scripts/analyze_part_a.py:193]. The next was AF307 with 415. AF301 also leads after QC removal (437). No mission number is asserted: the HDOB records carry only the call sign.
3. **Buoy.** The amended rule selected **42097 (Pulley Ridge, FL)**, before any value was seen [C: scripts/select_buoy.py, `results/buoy_selection.json`]. Its closest approach is 86.1 km at 08:30 UTC on 28 September. Its wave heights come from **ww3-mcp** (`ww3_get_buoy_history`), because ndbc-mcp cannot return data older than 45 days. ndbc-mcp supplied only the position.
4. **QC flags.** They were decoded from the NHC HDOB format page, which is archived and quote-checked. For AF301 they removed 70 SFMR values, 33 flight-level winds and 7 positions [C: scripts/analyze_part_a.py:231]. Another 207 SFMR values were missing, i.e. null in the response [C: scripts/analyze_part_a.py:231].
5. **Panel (d)** reproduces the published numbers exactly:
   - Fort Myers residual maximum +2.209 m at 22:18 UTC (tied at 22:30) [C: scripts/analyze_part_a.py:532, :551];
   - St. Petersburg residual minimum −1.755 m at 23:00 UTC [C: scripts/analyze_part_a.py:544, :558];
   - Fort Myers observed maximum 2.613 m above MLLW [T: coops_get_water_levels, call 3, I].
6. **The two SFMR tools do not work.** AOML returned HTTP 403 to both `recon_list_sfmr` and `recon_get_sfmr` (section 6).
7. **Offline replay.** `run_all.sh`, run from a scratch copy outside the repository inside `unshare -rn` (no network), reproduced every result and figure byte for byte (section 10).

## 2. What ran

**Wheels.** All installed from PyPI; each SHA-256 matched PyPI's digest. Each installed source tree is file-for-file identical to its release tag [E: archive/env_provenance.json].

| Server | Version | Wheel SHA-256 | Used as |
|---|---|---|---|
| nhc-mcp | 0.1.1 | `34bd7bb5b2b1dc6995d20572acff5afc47b198d69570b93bfd5e037035811c25` | reused responses (recorded 2026-11-06 with this wheel) |
| coops-mcp | 0.1.1 | `f9630bc8bf7e024aff0ade1ec2e9a696487e3fdccc1e2b9860a6c5e64846f210` | reused responses (same) |
| recon-mcp | 0.1.3 | `338a5a84ae70c8c0d38b47b6a2c2bfc13543dfb068c0085dd6a1075450d6a9e8` | new session |
| ww3-mcp | 0.1.3 | `8825e2ce75b1f102f1561c68ac03de12de93e98cbc90090d68a2d3a60b1c942d` | new session |
| ndbc-mcp | 0.1.2 | `0ad49f38aa4822bdfa03be5fe3be381d28b6998c417ac475f5f2184af35c6817` | new session (metadata only) |

**Environment.** CPython 3.13.12, uv 0.10.4, MCP SDK 1.30.0, on Linux 6.6.87.2-microsoft-standard-WSL2. The environment was built on 2026-11-21 at 02:11 UTC by `scripts/make_env.py`, outside the repository [E: archive/env_provenance.json].

**Processes.** Client PID 196060. Server PIDs 196076 (`recon_mcp`), 196088 (`ww3_mcp`) and 196092 (`ndbc_mcp`), the same before the first call and after the last. Each server ran from a neutral temporary directory.

**Calls** (`archive/part_a_record.json.gz`; full `CallToolResult`s; stderr logs in `archive/logs/`):

| Key | Tool | Arguments | Started (UTC) | Outcome |
|---|---|---|---|---|
| R1 | `recon_get_hdobs` | 2022-09-28, limit 1000, max_records 20000, json | 17:42:11.427 | 232 bulletins, 4640 records, `truncated: false` [T: recon_get_hdobs, R1, A] |
| R2 | `recon_get_hdobs` | 2022-09-29, same | 17:42:41.317 | 17 bulletins, 340 records, none dated 28 September [T: recon_get_hdobs, R2, A] |
| R3 | `recon_list_sfmr` | ian 2022, json | 17:42:44.888 | HTTP 403 (section 6) |
| R4 | `recon_get_sfmr` | ian 2022, AL09, `NOAA_SFMR20220928H1.nc` | 17:42:48.275 | HTTP 403, reported as a format problem (section 6) |
| N1 | `ndbc_get_station` | 42097 | 17:42:51.752 | 25.704°N, 83.654°W [T: ndbc_get_station, N1, A] |
| W1 | `ww3_get_buoy_history` | 42097, 2022, max_records 5000, json | 17:42:55.265 | `42097h2022.txt.gz`: 11279 rows, the last 5000 returned, from 2022-07-25 23:56 [T: ww3_get_buoy_history, W1, A] |

There were no repeats and no fallbacks: the record's `events` list is empty. The four calls of the feasibility step's AOML retry are not part of this record.

**HDOB records dated 28 September.** R1 and R2 together hold 4637 [T: recon_get_hdobs, R1+R2, A], with no duplicate (call sign, date, time) [C: checked during analysis].

## 3. Reused responses

`verification/ian_cross_server/session_record.json` has SHA-256 `cc8b52830f23ca98be0ea932e196accc2775490cb6c55542608f9f6ee4fcf1bd`, equal to that package's manifest. It is checked before every use by `scripts/common.py`, and by `run_all.sh` step 2.

| Call | Use |
|---|---|
| 1 `nhc_get_best_track` (AL092022) | Track, panel (a) and every distance |
| 2 and 5 `coops_get_station` | Gauge positions: Fort Myers 26.647778, −81.87111 [T: coops_get_station, call 2, I]; St. Petersburg 27.7606, −82.6269 [T: coops_get_station, call 5, I] |
| 3, 4, 6, 7 `coops_get_water_levels`, `coops_get_tide_predictions` | Panel (d) |

## 4. Selections

### 4.1 Buoy (`DESIGN.md` §6.1, `AMENDMENTS.md` A1)

Recomputed offline by `scripts/select_buoy.py` from the archived feasibility responses in `archive/phase0_selection/`: three `ndbc_find_nearest_stations` calls, and `ww3_get_buoy_history` for every candidate.

**Candidates.** 102 stations lie within 300 km [D: §6.1] of the track between 27 September 00:00 and 30 September 00:00:
- 21 reach the window;
- 32 do not, because their 2022 files have 6- or 10-minute rows and the last 5000 rows start in October to December;
- 49 have no 2022 file.

**Eligible and ranked.** Nine have wave height in the window. Closest approach to the track between 27 September 00:00 and landfall [`results/buoy_selection.json`, computed by `scripts/select_buoy.py`]:

| Buoy | Closest approach (km) | At (UTC, 28 Sep) | Non-null WVHT in window |
|---|---|---|---|
| **42097** Pulley Ridge | 86.1 | 08:30 | 144 |
| 42095 Satan Shoal | 96.7 | 02:00 | 145 |
| 42098 Egmont Channel | 121.7 | 18:25 | 144 |
| 42099 Offshore St. Petersburg | 203.8 | 18:00 | 144 |

The other five are on the Atlantic side, 218.7 km or more away. There is no tie.

**Position.** Buoy 42097 is placed where `ndbc_get_station` puts it today (25.704°N, 83.654°W) [T: ndbc_get_station, N1, A]. This is NDBC's current metadata, not a 2022 position, and no tool returns the 2022 position. The 86.1 km closest approach, and with it the selection, depends on this position.

### 4.2 Aircraft (`DESIGN.md` §6.2)

`results/aircraft_selection.json` [C: scripts/analyze_part_a.py:193]:

| Call sign | Records | Non-null SFMR | SFMR within 150 km | Same, after QC |
|---|---|---|---|---|
| **AF301** | 940 | 733 | **506** | 437 |
| AF307 | 740 | 672 | 415 | 380 |
| AF302 | 720 | 677 | 266 | 216 |
| NOAA2 | 800 | 730 | 188 | 177 |
| AF308 | 920 | 286 | 0 | 0 |
| NOAA3 | 360 | 0 | 0 | 0 |
| NOAA9 | 157 | 0 | 0 | 0 |

- AF301's records on 28 September run from 06:04:30 to 13:54:00 UTC [T: recon_get_hdobs, R1, A].
- Its closest record to the interpolated centre is 1.92 km away [C: scripts/analyze_part_a.py:364].
- Landfall (19:05 UTC) falls after its last record, so panel (b) has no landfall line.
- NOAA2 is the aircraft of the brief's candidate mission 20220928H1. By this rule it ranks fourth.

## 5. HDOB quality-control flags

**Source.** NHC, "High Density Observations (HDOB) Bulletin", `https://www.nhc.noaa.gov/abouthdobs_2007.shtml`.
- Retrieved 2026-11-21 17:30:35 GMT with curl, outside MCP.
- SHA-256 `3ad3a4e2…7eef`; archived in `archive/references/`.
- `scripts/check_references.py` finds all 18 quoted lines in it (`results/references_check.json`).

The page defines the two-digit field "FF". The removal rules are in `DESIGN.md` §7.

| FF | Meaning (first digit / second digit) | AF301 records | SFMR removed | FL wind removed | Positions removed |
|---|---|---|---|---|---|
| 00 | nominal / nominal | 646 | 0 | 0 | 0 |
| 02 | nominal / flight-level winds questionable | 15 | 0 | 15 | 0 |
| 03 | nominal / SFMR questionable | 231 | 56 | 0 | 0 |
| 06 | nominal / FL winds and SFMR questionable | 11 | 9 | 11 | 0 |
| 23 | GA/PS questionable / SFMR questionable | 30 | 0 | 0 | 0 |
| 32 | lat/lon and GA/PS questionable / FL winds questionable | 2 | 0 | 2 | 2 |
| 36 | lat/lon and GA/PS questionable / FL winds and SFMR questionable | 5 | 5 | 5 | 5 |
| **Total** | | 940 | **70** | **33** | **7** |

All counts: [C: scripts/analyze_part_a.py:231], `results/hdob_qc.json`.

- **Flagged records that held no value.** Flag 03 marked 231 records but removed only 56 SFMR values: the other 175 had no SFMR value. Flag 23 removed nothing, because its 30 records carry no SFMR value.
- **Missing values.** 207 SFMR values and 0 flight-level winds were missing (null) [C: scripts/analyze_part_a.py:231].
- **Plotted.** Panel (b) shows 663 SFMR values and 907 flight-level winds [C: `results/panel_b.json`]; panel (a) shows 933 flight-track positions [C: `results/panel_a.json`].
- **No unrecognised code** appeared.

## 6. The two SFMR tools

Both tools read AOML's SFMR archive, and both failed (`results/sfmr_tools.json`; server log `archive/logs/part_a_recon-mcp.stderr.log`).

| Tool | Text returned (`isError` false) | Upstream request in the log |
|---|---|---|
| `recon_list_sfmr` (R3) | "Error during listing SFMR files for ian (2022): HTTP 403: Forbidden. The NHC server may be temporarily unavailable. Please try again." | `https://www.aoml.noaa.gov/ftp/hrd/data/sfmr/2022/ian/` → 403 |
| `recon_get_sfmr` (R4) | "Could not process any SFMR files. The files may be in an unexpected format or the best track may not overlap the flight times." | `…/sfmr/2022/ian/NOAA_SFMR20220928H1.nc` → 403 |

The same 403 occurred three times in the feasibility step (02:14, 02:18 and 02:43 UTC). Those responses are in `../breadth_examples/archive/phase0_evidence/`. The July 2026 example `examples/ian_sfmr_NOAA20220928H1.json` shows that `recon_get_sfmr` worked then.

## 7. Panels: data and numbers

| Panel | Data | Numbers |
|---|---|---|
| (a) | Best track 26 September 00:00 to 30 September 00:00, 21 records [T: nhc_get_best_track, call 1, I] [D: §5]. Gauges (calls 2, 5). Buoy at its present ndbc-mcp position (N1). AF301 flight track (R1, QC-passing positions). Landfall point 26.7°N 82.2°W (NHC TCR, cited). Coastline: Natural Earth 1:50m [N], 34 of 1429 parts, 9720 vertices, in `results/coastline_subset.json` (extracted by `scripts/coastline.py`). | The coastline is the only non-MCP input; no MCP server supplies one. |
| (b) | AF301 SFMR and flight-level wind, kt, right axis m/s. Best track as markers at its 6-hourly times, joined by straight lines in time; the line runs toward the 18:00 value and is clipped at the axis edge (A6). | SFMR maximum after QC 137 kt at 10:29:30 [T: recon_get_hdobs, R1, A]. Flight-level maximum after QC 142 kt at 12:42:00 [T: recon_get_hdobs, R1, A]. Best track 120 kt at 06:00, 140 kt at 12:00 and 135 kt at 18:00 UTC [T: nhc_get_best_track, call 1, I]. |
| (c) | 42097 WVHT, 27 September 00:00 to 30 September 00:00 [D: §5], from ww3-mcp. | Window rows and nulls below. Maximum 8.31 m at 11:26 UTC on 28 September [T: ww3_get_buoy_history, W1, A]. |
| (d) | Observed water level (MLLW) and residual at both gauges. | 720 matched timestamps per station [C: scripts/analyze_part_a.py:532]. Extremes as in section 1. |

**Panel (b): what the three winds are.**
- **Averaging periods.** The best-track wind is a 1-minute maximum sustained value. The SFMR wind is the highest 10-second mean in each 30-second record. The flight-level wind is a 30-second mean at the aircraft's altitude. The three are not interchangeable.
- **AF301's peak.** Its flight-level wind of 142 kt (30-s mean) is from one Air Force aircraft on one flight.
- **The NHC report's figure.** NHC Tropical Cyclone Report, Hurricane Ian, p. 5: “During the missions, the maximum 10-second averaged flight-level winds reported in the hurricane’s core were 160 kt from a NOAA aircraft at 750 mb (an altitude of about 6800 ft) at 1013 UTC 28 September.” [cited; verified in `archive/references/tcr_quote_check.json`].
  - The report is the revision of 12 March 2026, retrieved 2026-11-23 01:47:01 GMT from `https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf`: 7,049,210 bytes, 72 pages, SHA-256 `804d2a867917d4ab157e5b2b1e444d21d306379a08d07ffd7059d157a4b15fce`. That is the same file `verification/ian_cross_server` verified on 2026-11-06.
  - `scripts/record_tcr_quote.py` checked the passage the way `ian_cross_server/record_references.py` does: pypdf 6.12.0, all whitespace removed, curly quotation marks read as straight, found on p. 5. The PDF is not archived; its URL, size and SHA-256 are.
- **Different averaging periods.** The report's 160 kt is a 10-second average. AF301's 142 kt is a 30-second mean, so the two are not directly comparable.
- **AF301's 10-second peak, for comparison.** HDOB records also carry the highest 10-second mean flight-level wind in each 30-second record (`peak_fl_wind_kt`).
  - After the same QC removal as the 30-second wind, AF301's maximum is **144 kt at 12:43:00 UTC** on 28 September [T: recon_get_hdobs, R1, A].
  - 907 values remain after QC [C: scripts/analyze_part_a.py:630]; QC removed 33 [C: :637]. QC removal does not change the maximum.
  - This number is descriptive only. It is not plotted, and the figure is unchanged (A11).
- **SFMR peak, next to the NHC report.**
  - **AF301.** Its SFMR maximum after QC removal is 137 kt at 10:29:30 UTC [T: recon_get_hdobs, R1, A]. That record carries FF 00 [T: recon_get_hdobs, R1, A]. It is the HDOB record nearest 1030 UTC.
  - **The report**, p. 5: “There were also multiple peak SFMR surface wind estimates from both Air Force and NOAA aircraft of 137-138 kt at 1030 UTC and 1013 UTC, respectively.” [cited; verified in `archive/references/tcr_quote_check.json`].
  - **Context, from the next sentence of the report**, p. 5: “The SFMR data from the Air Force instrument was flagged as unreliable in the real-time products, but reprocessing in the post-storm analysis using an updated algorithm no longer flagged the peak values.” [cited; verified as above].
  - **Flags around the peak.** In the real-time HDOB records used here, the AF301 SFMR values from 10:30:00 onward carry SFMR-questionable flags and are removed by the QC rule (`DESIGN.md` §7).
  - **Before QC removal**, AF301's SFMR maximum is 138 kt at 12:05:30 UTC, with FF 03 (SFMR questionable) [T: recon_get_hdobs, R1, A]. QC removal therefore lowers AF301's SFMR maximum from 138 to 137 kt.
  - **Not compared.** The reprocessed post-storm SFMR data the report refers to are not available through MCP here: the AOML SFMR tools fail (section 6).
  - This comparison is descriptive only. No figure changed (A12).

**Panel (c) details.**
- 144 window rows [C: scripts/analyze_part_a.py:465], 0 with null WVHT [C: :465].
- Median spacing 30 min [C: :465]; 0 gaps and 0 missing slots implied by that spacing [C: :465].
- The first window row is at 00:26 [C: :506].
- The whole 2022 file has 0 WVHT values coded as missing [T: ww3_get_buoy_history, W1, A, `missing_values.excluded_counts`].
- There is no second axis: WSPD and PRES are null in every window row; the buoy reports waves only.

## 8. Figures

| File | Content | Smallest font | Legend over data |
|---|---|---|---|
| `figures/ian_4panel_190mm.pdf`, `…_600dpi.png` | Main figure, 190 mm × 130 mm, panels (a)–(d) | 8.0 pt | none (0 points inside any legend) |
| `figures/ian_2panel_fallback_190mm.pdf`, `…_600dpi.png` | Fallback, 190 mm × 125 mm: (a) track with AF301 SFMR along the flight, (b) water levels | 8.0 pt | none |

**Checks.** Reported in `results/figure_checks.json`:
- font sizes used: 8.0, 8.5 and 10 pt (panel labels "(a)"–"(d)");
- no legend covers a data point drawn inside the axes;
- no legend overlaps a panel label, leaves the page, or touches another panel's axes or tick marks (in particular, the legend of (d) clears (c));
- no two texts overlap, and no drawn text leaves the page;
- on the map, the landfall star does not overlap the Fort Myers triangle, and no label overlaps a marker.

**Map key.** The key and the colorbar sit below the map, outside it, because the coastline fills the map's south-west corner (A7).

**Landfall line.** Drawn in (c) and (d) of the main figure and in (b) of the fallback. Not drawn in (b) of the main figure, which ends at 13:54 UTC.

**Draft caption, main figure (69 words).** Hurricane Ian (2022) through five MCP servers. (a) Best track coloured by maximum wind (nhc-mcp), tide gauges (coops-mcp), buoy 42097 at its present ndbc-mcp position, AF301 track (recon-mcp), Natural Earth coastline. (b) AF301 SFMR (10-s maximum) and flight-level (30-s mean) winds, QC-flagged values removed; best track (1-min, 6-hourly); the flight ends before landfall. (c) Wave height, 42097 (ww3-mcp). (d) Water level above MLLW and residual. Dashed: landfall, 19:05 UTC.

**Statements that do not fit within 70 words.** For the text, or for a longer caption:
- Buoy 42097 is plotted at the position `ndbc-mcp` returns today, not its 2022 position, and the 86.1 km closest approach depends on it.
- AF301's peak flight-level wind, 142 kt (30-s mean), is from one Air Force aircraft. The NHC report's 160 kt is a 10-second average from a NOAA aircraft at 750 mb at 1013 UTC 28 September (NHC report, p. 5, verified). AF301's own 10-second peak is 144 kt at 12:43 UTC.
- The best-track wind is a 1-minute value, the SFMR wind a 10-second maximum and the flight-level wind a 30-second mean.

**Draft caption, fallback (44 words).** Hurricane Ian (2022). (a) Best track (nhc-mcp), tide gauges (coops-mcp), buoy 42097 at its present ndbc-mcp position, Natural Earth coastline, and aircraft AF301's track coloured by SFMR surface wind (10-s maximum), QC-flagged values removed (recon-mcp). (b) Water level above MLLW and residual. Dashed: landfall.

## 9. Paragraph for the paper (116 words)

The revised Figure 4 draws on five servers. Responses from nhc-mcp (`nhc_get_best_track`) and coops-mcp (`coops_get_station`, `coops_get_water_levels`, `coops_get_tide_predictions`), archived from an earlier scripted session, are reused unchanged. In a new session, one client held stdio sessions to three more servers. recon-mcp's `recon_get_hdobs` returned 4637 high-density aircraft observations for 28 September 2022. ww3-mcp's `ww3_get_buoy_history` returned buoy 42097's 2022 NDBC record, and ndbc-mcp's `ndbc_get_station` its position. The client computed the storm-centre distances that selected aircraft AF301 and buoy 42097 by rules fixed in advance. It also decoded the HDOB quality flags and computed the residuals (+2.209 m, −1.755 m). Both AOML SFMR tools failed (HTTP 403). The coastline, from Natural Earth, is the only input not obtained through MCP.

## 10. Offline replay

**Command.**

```bash
bash verification/ian_multi_server/run_all.sh
```

The executable bit is set in Git (this drive does not keep file modes, so `bash run_all.sh` is the safe form).

**Steps.**
1. Every archived file against `archive/MANIFEST.sha256` (202 files).
2. The reused Ian session against its SHA-256.
3. The 18 HDOB quotations.
4. The buoy selection.
5. The analysis.
6. The coastline subset from the archived Natural Earth file (standard library).
7. The figures: matplotlib 3.10.8 from `scripts/requirements-figures.txt`, uv `--offline`.
8. All 16 outputs against `results/SHA256SUMS`.

**Check run.**
- Run from a scratch copy outside the repository: `git archive` of the needed packages into a fresh folder, inside `unshare -rn`, so no network interface existed.
  - First on `bdadd79`, before the figure revisions (`/mnt/d/ocean-mcp-wp9/scratch_runall_20261121T175901Z`).
  - Again on `dffe3cb`, after them (`/mnt/d/ocean-mcp-wp9/scratch_runall_dffe3cb`).
  - Again on `71c99eb`, after the quotation check and the added number (`/mnt/d/ocean-mcp-wp9/scratch_runall_71c99eb`).
  - Again on `b3864ac`, after the SFMR comparison (`/mnt/d/ocean-mcp-wp9/scratch_runall_b3864ac`).
  - Again on `e9914ef`, after B1 session 2 and the restored uv cache (`/mnt/d/ocean-mcp-wp9/scratch_runall_e9914ef`).
- Result every time: **exit 0, "OK: every output matches"**.
- **No file differed.**
- **The uv cache.** The figure step uses the pinned plotting packages from uv's cache (`--offline`). That cache is not part of the package.
  - On this machine it was emptied on 2026-11-23, so on 2026-11-24 the ten pinned packages were downloaded again from PyPI, with the author's agreement.
  - Each wheel's SHA-256 matched PyPI's published digest; the list is in `archive/plotting_wheels_2026-11-24.json`.
  - With them, this package's replay again matched every output byte for byte.
  - The resolver also installs `tzdata` 2026.6, an unpinned dependency of python-dateutil 4.0.0. It changed no output.
  - On a fresh machine, run the figure environment once with the network on before the offline replay.
- The figures are byte-reproducible because the PDF and PNG metadata carry no dates. Two earlier consecutive runs in the worktree also matched (15 of 15 files).

## 11. Defects and oddities

None was fixed. The evidence files are named for each.

1. **`ww3_get_buoy_history` is case-sensitive.**
   - Request `station_id="VENF1"`, year 2022 → "No NDBC historical annual file for station 'VENF1', year 2022 (VENF1h2022.txt.gz: HTTP 404, not found). NDBC publishes an annual file only after the year has ended, and only for years in which the station reported…".
   - Request `station_id="venf1"` → `venf1h2022.txt.gz`, 8736 rows.
   - The client builds the file name from the ID as given; NDBC's file names are lower case, while NDBC's station list and ndbc-mcp return upper-case IDs.
   - Evidence: `../breadth_examples/archive/phase0_evidence/ww3_history_VENF1_upper.json.gz`, `ww3_history_venf1_lower.json.gz`; all 80 cases in `archive/phase0_selection/ww3_history_{upper,lower}/`.
2. **`recon_get_sfmr` hides the upstream error.** HTTP 403 on the NetCDF file is reported as "unexpected format or the best track may not overlap". The per-file loop catches every exception and continues. Evidence: R4 and `archive/logs/part_a_recon-mcp.stderr.log`; `../breadth_examples/archive/phase0_evidence/recon_get_sfmr_H1.*`.
3. **`recon_list_sfmr` names the wrong server.** "The NHC server may be temporarily unavailable" for a 403 from `www.aoml.noaa.gov`. Evidence: R3, the same log; `phase0_evidence/recon_list_sfmr*.json`.
4. **rtofs reports an out-of-range time as land.**
   - Request: `rtofs_get_area_forecast` for 26.0–26.5°N, 83.5–83.0°W (open Gulf) at `2022-09-28T12:00:00Z` → "No valid data in bounding box … The area may be entirely over land."
   - The server log shows four HTTP 400 responses from `tds.hycom.org` NCSS.
   - The same box without a time returns 4 valid points. The docstring's "THREDDS returns the nearest time step" does not hold outside the axis.
   - Evidence: `phase0_evidence/rtofs_area_2022.json`, `.stderr.log`, `rtofs_area_now.json`.
5. **vdatum's offline mode cannot work.**
   - With `online=false` in a fresh process, MLLW→MHHW and MLLW→NAVD88 fail ("File not found or invalid"): the grids are HTTPS URLs.
   - After one `online=true` call in the same process, `online=false` calls succeed, because PROJ networking stays enabled process-wide.
   - Errors come back as text with `isError` false. The MLLW→MHHW pipeline contains a literal `None` step.
   - Evidence: `phase0_evidence/vdatum_nonet.*` (network namespace), `vdatum_net.*`.
6. **`goes_get_image` in markdown mode makes no request.** It returns a URL for a GOES-19 image at 2022-09-28 12:00, before that satellite was launched. Image mode then reports 404 with "The timestamp may be too old". Evidence: `phase0_evidence/goes_image_20220928120000.*` (no HTTP request in its log), `goes_image_img_20220928120000.*`.
7. **`ww3_list_cycles` lists cycles no tool can serve.** For `date="2022-09-28"` it lists four 2022 cycles as "Available" and points to `ww3_get_forecast_at_point`, which has no date argument and always uses the newest cycle. Evidence: `phase0_evidence/ww3_list_cycles_20220928.json`.
8. **Responses leave out information:**
   - `ww3_compare_forecast_with_buoy` does not state its pairing rule (nearest row within ±30 min, from the code) [`../breadth_examples/archive/session1_record.json` S1.2];
   - HDOB records carry the call sign but no mission number [R1];
   - `ofs_compare_with_coops` names no model run or cycle [session 1, C1].
9. **Possibly stale upstream data.** HYCOM's newest run, reported by `rtofs_get_latest_time`, was 2026-11-16 12Z both at 02:35 UTC and at 17:37 UTC on 2026-11-21. That is five days old. Not verified independently. Evidence: `phase0_evidence/rtofs_latest_time_sst.json`; session 1, T1.

**Found during this run** (details in `../breadth_examples/REPORT.md`):

10. `ww3_compare_forecast_with_buoy` returned the bare token `NaN` for `correlation` with 2 pairs. That is not valid JSON, and strict parsers reject it.
11. `ww3_get_forecast_at_point` keyed its values `swh` (the GRIB short name) when `HTSGW` was requested.
12. `rtofs_get_transect` returns no valid time in its JSON.
13. `ndbc_get_station` returns present-day metadata. No 2022 buoy position is available through MCP.

## 12. Amendments

In order (`AMENDMENTS.md`):
- **A1** Buoy rule: closest approach before landfall. Before any value was seen.
- **A2** HDOB source and aircraft rule, QC decoding, SFMR tools recorded as not working. Before any value was seen.
- **A3** No river gauge. Before any value was seen.
- **A4** Buoy values from ww3-mcp, ndbc-mcp for metadata. Before any value was seen.
- **A5** Figure layout, map extent, direct labels, panel (b) line breaks, panel (d) legend. After the values were seen; no number changed.
- **A6** Panel (b) best track: 6-hourly markers joined linearly in time, replacing a nearest-record step whose jump at 09:00 was an artifact. After the values were seen; `panel_b.json` and the best-track entries of `part_a_numbers.json` changed.
- **A7** Panel (a): Natural Earth coastline (the one non-MCP input); key and colorbar below the map; smaller landfall and gauge markers so they do not overlap; labels moved; fallback page 125 mm tall. Layout.
- **A8** Panel labels "(a)"–"(d)"; panel heights adjusted so the legend of (d) clears (c). Layout.
- **A9** Caption and report statements on the buoy position, the peak flight-level wind and the averaging periods. Text only.
- **A10** The NHC report quotation on the 160 kt flight-level wind verified against the PDF (p. 5; SHA-256 recorded). Text only.
- **A11** AF301's 10-second peak flight-level wind (144 kt at 12:43 UTC, after QC) added as a descriptive number. After the values were seen; not plotted.
- **A12** AF301's SFMR peak (137 kt at 10:29:30 UTC after QC; 138 kt at 12:05:30 before QC) set beside the NHC report's 137-138 kt, with two verified report sentences. After the values were seen; descriptive only, no figure change.

## 13. Limitations

- **One live run.** HDOB bulletins and NDBC annual files are archival but can be reissued.
- **One environment.** Client and servers share one virtual environment; the servers are separate processes.
- **Positions.** The buoy position is current metadata, not the 2022 position, and the 86.1 km closest approach depends on it. The best track is given to 0.1° and interpolated linearly in time.
- **Markdown parsing.** Coordinates come from markdown for `coops_get_station` and `ndbc_get_station`.
- **Coastline.** It comes from Natural Earth, not from MCP. It is drawn for orientation only and enters no number.
- **Linux-only process evidence** (`/proc`).

## 14. Reproduce

```bash
cd verification/ian_multi_server
python3 scripts/make_env.py /path/to/new-env --repo ../.. --out /tmp/prov.json   # PyPI wheels, hashes checked
/path/to/new-env/bin/python scripts/record_part_a.py      # live; refuses to overwrite the archive
python3 -I scripts/build_manifests.py                     # after a new recording only
bash run_all.sh                                           # offline replay and comparison
```

## 15. Files

| Path | Content |
|---|---|
| `DESIGN.md`, `AMENDMENTS.md` | Frozen design and the amendments |
| `archive/part_a_record.json.gz` | The session: calls, full results, processes, tool listings |
| `archive/logs/` | Server stderr logs (HTTP status codes) |
| `archive/phase0_selection/` | Feasibility responses that select the buoy |
| `archive/references/` | NHC HDOB format page and its HTTP headers; `tcr_quote_check.json`, the five verified NHC report passages with the PDF's SHA-256 |
| `archive/env_provenance.json` | Wheels, digests, freeze, installed source against the tags |
| `archive/plotting_wheels_2026-11-24.json` | The plotting wheels downloaded on 2026-11-24, with SHA-256 checked against PyPI |
| `archive/non_mcp/natural_earth/` | Natural Earth 1:50m coastline (shapefile parts) and `SOURCE.md`: source URL, SHA-256, terms |
| `scripts/` | Recording, selection, analysis, coastline extraction, figures, manifests; `record_tcr_quote.py` (needs the PDF, not part of the offline replay) |
| `results/` | Selections, QC, panel inputs, coastline subset, numbers with provenance, figure checks, `SHA256SUMS` |
| `figures/` | PDF and 600 dpi PNG |
