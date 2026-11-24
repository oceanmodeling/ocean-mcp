# Three short examples and a fourth, for servers the paper does not yet show: report

Run date: 2026-11-21 (UTC). Branch `docs/breadth-examples`, created from the local `origin/main` ref (575cd21) without fetching. The design was committed in `fdce9bb` before anything was recorded; the data and scripts are in `bdadd79`. The B2 and B4 figures were revised on 2026-11-22 in `dffe3cb` (`AMENDMENTS.md` AM6, AM7); no result value changed. B1 session 2 (the buoy observations) was recorded on 2026-11-24, and B1's pairing, statistics and figure were added then.

These are **scripted MCP workflows**. Tools and arguments are fixed in `DESIGN.md` and `scripts/record_session1.py`. No language model was involved. Nothing here tests a safeguard, and none of it is an evaluation.

## How numbers are tagged

| Tag | Meaning |
|---|---|
| `[T: tool, call]` | Returned by that tool, in that call of `archive/session1_record.json` (written **S**). |
| `[C: script:line]` | Computed by the client at that line; also stored in `results/part_b_numbers.json`. |
| `[D: DESIGN.md §n]` | Design parameters. |
| `[E: archive/env_provenance.json]` | Versions and checksums. |

## 1. Summary

| Example | Status | Result |
|---|---|---|
| B1 wave forecast against buoy 44097 (ww3-mcp, ndbc-mcp) | Done (two sessions) | Forecast 2026-11-21 12z, 25 valid times to +72 h [T: ww3_get_forecast_at_point, S1.3]. Client pairing: **25 pairs**, bias +0.074 m, RMSE 0.299 m, MAE 0.197 m, r = 0.972 [C: scripts/analyze_part_b.py:223]. The tool's own comparison returned **2 pairs** [T: ww3_compare_forecast_with_buoy, S1.2]. |
| B2 CBOFS against Baltimore (ofs-mcp, coops-mcp) | Done | 24 pairs; datums as stated by the tool: model `NAVD88`, observations `NAVD` [T: ofs_compare_with_coops, C1] |
| B3 vdatum against CO-OPS datums (vdatum-mcp, coops-mcp) | Done (recorded online) | vdatum − CO-OPS: **+0.1 mm** to MHHW, **−2.8 mm** to NAVD88 [C: scripts/analyze_part_b.py:320]. Neither source states an uncertainty. |
| B4 RTOFS temperature section off Cape Hatteras (rtofs-mcp) | Done | 20 of 20 profiles. Valid 2026-11-21 15:00 UTC [T: rtofs_get_profile_forecast, T3]. Newest run 2026-11-16 12Z [T: rtofs_get_latest_time, T1], i.e. a 123 h forecast [C: scripts/analyze_part_b.py:453]. |

**Session 1.** One client process, PID 195386, held six MCP stdio sessions at once:

| Server | PID |
|---|---|
| ndbc | 195389 |
| ww3 | 195393 |
| ofs | 195398 |
| coops | 195403 |
| vdatum | 195408 |
| rtofs | 195419 |

The PIDs were the same before the first call and after the last. The session made 11 calls between 17:36:44 and 17:37:59 UTC, with no fallback and no repeat. The first buoy and the first OFS pair in each order had data.

**Offline replay.** `run_all.sh`, run from a scratch copy outside the repository inside `unshare -rn`, reproduced every result and figure byte for byte (section 7).

## 2. Versions and wheels

| Server | Version | Wheel SHA-256 |
|---|---|---|
| ww3-mcp | 0.1.3 | `8825e2ce75b1f102f1561c68ac03de12de93e98cbc90090d68a2d3a60b1c942d` |
| ndbc-mcp | 0.1.2 | `0ad49f38aa4822bdfa03be5fe3be381d28b6998c417ac475f5f2184af35c6817` |
| ofs-mcp | 0.1.3 | `f2f4943b0bf0594f2480c93831f0604aa2816365b2c5415e8cc42f5de162de6c` |
| coops-mcp | 0.1.1 | `f9630bc8bf7e024aff0ade1ec2e9a696487e3fdccc1e2b9860a6c5e64846f210` |
| vdatum-mcp | 0.1.1 | `80f3f4ec22f331f37aa341300ea69a7722c7e840ec6d8efc5f45da4d7973fa40` |
| rtofs-mcp | 0.1.4 | `f943d3db9d28c61a8126c99ed569c64bb79e6d9f92338477e75e090839aac033` |

All SHA-256 values match PyPI's digests, and each installed source tree is identical to its release tag [E: archive/env_provenance.json]. The client ran CPython 3.13.12 with MCP SDK 1.30.0.

## 3. B1: GFS-Wave forecast against NDBC 44097

**Calls** (`DESIGN.md` §3; session 1, 2026-11-21):

| Key | Tool | Returned |
|---|---|---|
| S1.1 | `ndbc_get_station` 44097 | Block Island, RI, 40.966°N, 71.123°W [T: ndbc_get_station, S1.1] |
| S1.2 | `ww3_compare_forecast_with_buoy`, `hours_to_compare=24` | Cycle 2026-11-21 12z. Observation window 2026-11-20 17:00 to 2026-11-21 17:00: 48 rows, all with WVHT, 30-min interval. **2 pairs**, at 12:00 and 15:00 (forecast hours 0 and 3). Bias −0.05 m, RMSE 0.05 m, MAE 0.05 m, peak error 0.05 m, correlation `NaN` [T: ww3_compare_forecast_with_buoy, S1.2] |
| S1.3 | `ww3_get_forecast_at_point`, 72 h, 3-hourly, `HTSGW` | Cycle 2026-11-21 12z; 25 valid times, 2026-11-21 12:00 to 2026-11-24 12:00 [T: ww3_get_forecast_at_point, S1.3]. The values are keyed `swh`. |

**The tool's own comparison.**
- **Pairing rule.** The response does not state it [C: scripts/analyze_part_b.py `b1()`, `pairing_rule_stated_in_response: false`]. From the code (`ww3_mcp/utils.py`, `align_timeseries`), each 3-hourly forecast time pairs with the nearest buoy row within ±30 min.
- **Why only 2 pairs.** The observation window ends at the buoy's latest row (17:00) and the forecast starts at the cycle time (12:00). So only valid times between the two can pair: 12:00 and 15:00.
- **The NaN.** With two pairs whose forecasts are equal (0.35 m, 0.35 m) [T: S1.2], the correlation is undefined. The tool emits the bare token `NaN`, which is not valid JSON.

**Session 2** (2026-11-24, `archive/session2_record.json`, SHA-256 `9942129a…f5bf`). One client process (PID 198247) held one session to ndbc-mcp 0.1.2 (PID 198257) from 13:08:17 to 13:08:20 UTC.

| Key | Tool | Arguments | Returned |
|---|---|---|---|
| S2.1 | `ndbc_get_observations` | `station_id="44097"`, `hours=80` (cycle to call time 73.1 h, rounded up, plus 6, by rule), `variables=["WVHT"]`, json, `max_records=2000` | 159 rows, `truncated: false`, from 2026-11-21 04:30 to 2026-11-24 12:30; all 159 carry a WVHT value [T: ndbc_get_observations, S2.1, `archive/session2_record.json`] |

**Observation timestamps.** The tool returns them without a time-zone designator, e.g. `2026-11-24T12:30:00`. NDBC realtime rows are UTC, and the analysis reads all 159 as UTC; it records the count in `results/b1_pairs.json`.

**Gaps.** The rows are 30 minutes apart (median). There are two gaps of 60 minutes: 21 November 23:00 to 22 November 00:00, and 22 November 23:00 to 23 November 00:00. The figure breaks the line there.

**Pairing.** As fixed in `DESIGN.md` §3.3: for each forecast valid time, the nearest observation with WVHT within 30 minutes; if two are equally near, the earlier one.
- All 25 valid times from 21 November 12:00 to 24 November 12:00 have a pair, each with an observation at the same minute [C: scripts/analyze_part_b.py:223].
- No valid time went unpaired.

**Statistics** over the 25 pairs, forecast minus observed, computed by the client [C: scripts/analyze_part_b.py:223]:

| Statistic | Value |
|---|---|
| n | 25 |
| bias, mean(F − O) | +0.074 m |
| RMSE | 0.299 m |
| MAE | 0.197 m |
| Pearson r | 0.972 |
| largest \|F − O\| | 0.83 m, at 2026-11-23 15:00 UTC |

**Against the tool's own comparison.** The tool's comparison from session 1 used the same cycle but paired only 12:00 and 15:00 on 21 November, i.e. forecast hours 0 and 3. That is why the second session was needed (`AMENDMENTS.md` AM2).

**Figure** `figures/b1_ww3_44097_90mm.pdf` and `…_600dpi.png`, 90 mm × 78 mm.
- Observations as a line, broken at the two gaps. The forecast as a line with markers at the 3-hourly valid times.
- The client statistics are printed below the axes, labelled as computed by the client. The time axis is labelled "Time (UTC), 2026".
- Smallest font 8.0 pt. The legend covers no data, and no text leaves the page.

**Draft caption, B1 (38 words).** GFS-Wave forecast (2026-11-21 12z, ww3-mcp) and significant wave height observed at NDBC 44097, Block Island (ndbc-mcp, recorded three days later). Statistics computed by the client from 25 pairs within 30 min; the tool's own comparison returned 2 pairs.

## 4. B2: CBOFS against CO-OPS Baltimore (8574680)

**C1 `ofs_compare_with_coops`** (cbofs, 8574680, 24 h, json):
- Window 2026-11-20 17:37:33 to 2026-11-21 17:37:33 UTC, i.e. the 24 h before the call [T: ofs_compare_with_coops, C1].
- Model grid point 1.16 km from the gauge [T: C1].
- **24 pairs**: bias +0.0996 m, RMSE 0.1064 m, MAE 0.0996 m, peak error 0.1727 m, correlation 0.9644 [T: ofs_compare_with_coops, C1].
- Datums as the tool states them: `model_datum: NAVD88` and `obs_datum: NAVD` [T: C1].

**C2 `coops_get_datums`** (8574680): CO-OPS publishes 15 datums for Baltimore, NAVD88 among them [T: coops_get_datums, C2].

**Note on the datum.** This tool pairs a fixed, documented datum. `model_datum` comes from the server's model table: NAVD88 for CBOFS, mapped to the CO-OPS datum `NAVD`. The tool neither resolves the datum per model file nor declines when it cannot confirm it. The response also names no model run or cycle: the series is the THREDDS FMRC "best" aggregation.

**Figure** `figures/b2_ofs_cbofs_baltimore_90mm.pdf` and `…_600dpi.png`, 90 mm × 78 mm. The time axis is labelled "Time (UTC), 2026" (AM7). Smallest font 8.0 pt. The legend covers no data, and the statistics are printed below the axes.

**Draft caption, B2 (38 words).** CBOFS water level (ofs-mcp) against CO-OPS observations at Baltimore, 8574680, for the 24 h before the call (20–21 November 2026). Datums as the tool states them: model NAVD88 from a fixed table, observations NAVD. Statistics returned by ofs_compare_with_coops.

## 5. B3: vertical-datum conversion at Fort Myers (8725520)

**Inputs.**
- Position 26.647778, −81.87111, from `coops_get_station` in `verification/ian_cross_server/session_record.json`, call 2. The recording script checked it against that text.
- Value 2.613 m above MLLW, the Fort Myers observed peak from the same package.

| Target | `vdatum_convert` | From `coops_get_datums` | vdatum − CO-OPS |
|---|---|---|---|
| MHHW | **2.2121 m** [T: vdatum_convert, V1] | **2.212 m** = 2.613 − (1.730 − 1.329) [C: scripts/analyze_part_b.py:320] | **+0.1 mm** [C: :320] |
| NAVD88 | **2.2922 m** [T: vdatum_convert, V2] | **2.295 m** = 2.613 − (1.647 − 1.329) [C: :320] | **−2.8 mm** [C: :320] |

The CO-OPS datums are in metres above station datum: MHHW 1.730, MLLW 1.329, NAVD88 1.647 [T: coops_get_datums, V3]. MHHW − MLLW = 0.401 m, as the Ian package found from `coops_get_station`.

**Uncertainty stated.**
- `vdatum_convert`: none. Its response names neither the grid nor an uncertainty.
- `coops_get_datums`: none. It also names no tidal epoch.

**Grids, from the vdatum-mcp source.** Not from the response:
- `us_noaa_nos_{MLLW,MHHW}-ITRF2020_2020.0_nwldatum_4.7.0_20240621_3.tif` on the `noaa-nos-stofs2d-pds` S3 bucket;
- for NAVD88, a Helmert chain plus `us_noaa_g2018u0.tif` (GEOID18).

**Online only.** The calls were made with `online=true`. **`run_all.sh` replays the archived responses; the conversion itself cannot be rerun offline**, because vdatum-mcp fetches its grids over HTTPS (defect 5).

The table is `results/b3_table.md` and `.json`; there is no figure.

**Draft caption, B3 table (30 words).** The Fort Myers peak (2.613 m above MLLW) converted with vdatum_convert and with the CO-OPS station datums (coops_get_datums). Differences: +0.1 mm (MHHW), −2.8 mm (NAVD88). Neither source states an uncertainty.

## 6. B4: RTOFS temperature section off Cape Hatteras

**Calls** (`DESIGN.md` §6):

| Key | Tool | Returned |
|---|---|---|
| T1 | `rtofs_get_latest_time` (dataset `sst`, the 3D temperature) | Axis 2026-11-12 12:00 to 2026-11-24 12:00; newest run **2026-11-16 12:00 UTC** [T: rtofs_get_latest_time, T1] |
| T2 | `rtofs_get_transect` | From 35.55°N 75.25°W to 33.95°N 73.30°W, 20 points, temperature, time `2026-11-21T15:00:00Z` (the latest 3-hourly step before the call, by rule). Total distance 251.78 km [T: rtofs_get_transect, T2]. 20 of 20 profiles have levels [T: T2]; the first three are on the shelf (10–12 levels, to 25–35 m). Warmest value 25.55 °C at the surface, 66 km along the line [T: T2]. The JSON carries no time. |
| T3 | `rtofs_get_profile_forecast` at the tool's point 10 with the same time | Echoed time 2026-11-21T15:00:00Z [T: rtofs_get_profile_forecast, T3] |

**Run.** The valid time is later than the newest run. The FMRC "best" aggregation therefore serves it from the 2026-11-16 12Z run: a 123 h forecast [C: scripts/analyze_part_b.py:453]. This is an inference from how such an aggregation is built.

**The tool did not fail**, so B4 is included.

**Figure** `figures/b4_rtofs_hatteras_section_190mm.pdf` and `…_600dpi.png`, 190 mm × 80 mm, 0–1000 m.
- Cells without interpolation.
- Colour scale `viridis`, sequential and perceptually uniform, from the lowest to the highest value down to 1000 m (AM6).
- Below the model sea bed the profiles return no values; that area is light grey (AM6).
- Smallest font 8.0 pt. No legend; no text off the page.

**Draft caption, B4 (38 words).** RTOFS (HYCOM ESPC-D-V02) temperature section across the Gulf Stream off Cape Hatteras, 0–1000 m, valid 15:00 UTC 21 November 2026, from rtofs-mcp. Newest run reported: 16 November 2026 12Z (123-h forecast). Grey: below model sea bed. Triangles: profiles.

## 7. Offline replay

**Command.**

```bash
bash verification/breadth_examples/run_all.sh
```

The executable bit is set in Git (this drive does not keep file modes, so `bash run_all.sh` is the safe form).

**Steps.**
1. Every archived file against `archive/MANIFEST.sha256` (42 files).
2. The Ian session checksum.
3. The analysis, now including B1's pairing and statistics.
4. The figures, now including B1: matplotlib 3.10.8, uv `--offline`.
5. 14 outputs against `results/SHA256SUMS`.

**Check run.**
- Run from a scratch copy outside the repository, inside `unshare -rn`:
  - first on `bdadd79` (`/mnt/d/ocean-mcp-wp9/scratch_runall_20261121T175901Z`);
  - again on `dffe3cb`, after the figure revisions (`/mnt/d/ocean-mcp-wp9/scratch_runall_dffe3cb`).
  - again on `e9914ef`, after B1 session 2 (`/mnt/d/ocean-mcp-wp9/scratch_runall_e9914ef`).
- Result every time: **exit 0, "OK: every output matches"**. **No file differed.**
- Before session 2, the run printed that session 2 was not archived. B3 is always replayed from the archived responses only.

**The uv cache.** The figure step uses the pinned plotting packages from uv's cache (`--offline`). That cache is not part of the package.
- On this machine it was emptied on 2026-11-23, so on 2026-11-24 the ten pinned packages were downloaded again from PyPI, with the author's agreement.
- Each wheel's SHA-256 matched PyPI's published digest; the list is in `archive/plotting_wheels_2026-11-24.json`.
- With them, every previously committed figure and result was reproduced byte for byte.
- The resolver also installs `tzdata` 2026.6, a dependency of python-dateutil 4.0.0 that `scripts/requirements-figures.txt` does not pin. It changed no output.
- On a fresh machine, run the figure environment once with the network on before the offline replay.

## 8. Defects and oddities

None was fixed. The nine defects from the feasibility step are listed in full, with requests, responses and evidence paths, in `../ian_multi_server/REPORT.md` §11. Their evidence files are in `archive/phase0_evidence/`.

| # | Defect | Evidence here |
|---|---|---|
| 1 | `ww3_get_buoy_history` is case-sensitive (VENF1 404, venf1 8736 rows) | `ww3_history_VENF1_upper.json.gz`, `ww3_history_venf1_lower.json.gz`, `ww3_hist_case_venf1_lower.json` |
| 2 | `recon_get_sfmr` reports HTTP 403 as a format or track problem | `recon_get_sfmr_H1.json`, `.stderr.log` |
| 3 | `recon_list_sfmr` blames the NHC server for an AOML 403 | `recon_list_sfmr.json`, `_retry1.json`, `_retry2.json`, `.stderr.log` |
| 4 | `rtofs_get_area_forecast` reports an out-of-range time (HTTP 400) as "over land" | `rtofs_area_2022.json`, `.stderr.log`, `rtofs_area_now.json` |
| 5 | vdatum `online=false` fails in a fresh process and is ignored after an online call; errors returned with `isError` false; a `None` pipeline step | `vdatum_nonet.*`, `vdatum_net.*` |
| 6 | `goes_get_image` in markdown mode returns an unchecked URL, even for GOES-19 in 2022 | `goes_image_20220928120000.*`, `goes_image_img_20220928120000.*` |
| 7 | `ww3_list_cycles` lists 2022 cycles that no tool can serve | `ww3_list_cycles_20220928.json` |
| 8 | Responses leave out the pairing rule (ww3 comparison), the mission number (HDOB) and the model run (OFS comparison) | session 1 S1.2 and C1; `../ian_multi_server` R1 |
| 9 | HYCOM's newest run five days old at 02:35 and 17:37 UTC on 21 November | `rtofs_latest_time_sst.json`; session 1 T1 |

**Found in this run.**

10. **`ww3_compare_forecast_with_buoy` emits invalid JSON.** It returned `"correlation": NaN` for 2 pairs [S1.2]. Strict JSON parsers reject the bare token. The analysis stores it as the string "NaN".
11. **`ww3_get_forecast_at_point` renames the variable.** It keyed its values `swh` when `variables=["HTSGW"]` was requested [S1.3]. A client looking for `HTSGW` finds nothing.
12. **`rtofs_get_transect` returns no time** in its JSON [T2]. The valid time had to be fixed by the request and echoed by T3.

## 9. Amendments

In order (`AMENDMENTS.md`):
The amendments were relabelled AM1–AM7 on 2026-11-22, so that none shares a name with examples B1–B4. The old labels were B1–B5 = AM1–AM5.

- **AM1** Newest GFS-Wave cycle for example B1; the FMRC series for example B2; the tools have no cycle argument. Before any value was seen.
- **AM2** Example B1 recorded in two sessions, with client pairing. Before any value was seen.
- **AM3** Example B4 as a section off Cape Hatteras. Before any value was seen.
- **AM4** Example B3 recorded online. B3's values had been seen in the feasibility step; no argument affecting the value changed.
- **AM5** Figure details: B4 colour range and profile markers, B2 statistics placement. After the values were seen; no number changed.
- **AM6** B4 colour scale `viridis` instead of a diverging scale; light grey below the model sea bed. Layout; no number changed.
- **AM7** B2 time axis labelled "Time (UTC), 2026" (and B1 when drawn). Layout; no number changed.

## 10. Files

| Path | Content |
|---|---|
| `DESIGN.md`, `AMENDMENTS.md` | Frozen design and the amendments |
| `archive/session1_record.json` | Session 1: calls, full results, processes, tool listings |
| `archive/session2_record.json` | Session 2 (B1 observations): the call, full result, processes |
| `archive/plotting_wheels_2026-11-24.json` | The plotting wheels downloaded on 2026-11-24, with SHA-256 checked against PyPI |
| `archive/logs/` | Server stderr logs |
| `archive/phase0_evidence/` | Feasibility responses that document defects 1–9; the feasibility scripts as run |
| `archive/env_provenance.json` | Wheels, digests, freeze, source against the tags |
| `scripts/` | Recording (sessions 1 and 2), analysis, figures, manifests |
| `results/` | Per-example results, numbers with provenance, figure checks, `SHA256SUMS` |
| `figures/` | B1, B2 and B4, PDF and 600 dpi PNG |
