# STOFS v3.1 Boston validation case study: technical report

Prepared 2026-11-04 for the Ocean-MCP manuscript (Section 3.1). **Revision 2**, branch `docs/stofs-v31-boston-example-v2`, stacked on `fix/stofs-release-prep`. Revision 1 is on `docs/stofs-v31-boston-example`. Nothing was pushed, merged, tagged or uploaded. `OceanMCP_Manuscript_Draft.docx` was not opened or modified.

> **Revision 2 corrects the datum interpretation of revision 1.** Revision 1 (§3.4, §10.2, §12) stated three things that are now **withdrawn**:
> - that NOAA's STOFS-3D station LMSL at Boston lies about 4 cm below VDatum's LMSL;
> - that the 3D forecast bias would be about −0.18 m against VDatum's LMSL;
> - that 4 cm quantifies the reference uncertainty of the 3D comparison.
>
> Those statements rested on a single-site grid proxy. Across 115 stations the same proxy is centred on zero, and NOAA's own conversion constants match VDatum (§3, item 4). This follows the independent audit of 2026-11-04 (`STOFS_V31_FABLE_AUDIT.md` §5.1), whose analysis was reproduced here with this package's own scripts. All forecast statistics are unchanged. The figure is now two panels, with the statistics in a separate table (§9).

Each statement is marked with its evidence class:

- **[V]** independently verified here, from archived bytes or a recomputation;
- **[D]** NOAA documentation, quoted from the archived page;
- **[A]** assumption;
- **[U]** unresolved.

---

## Summary

- **Software prerequisites [V].**
  - The second review's three critical STOFS blockers were unresolved at `69e721f`. They are fixed on `fix/stofs-datum-hardening` (§0).
  - The independent audit then found shifted no-data sentinels in the real v3.1 files and an unbounded 2D datum fallback. Both are fixed on `fix/stofs-release-prep` (stofs-mcp 0.3.0, unreleased).
  - The comparisons were produced live through the MCP stdio protocol with commit `31e7f6a`, and replayed offline with the 0.3.0 code: identical results (§7).
- **Case.** One fixed, archived cycle: STOFS-2D-Global v3.1 and STOFS-3D-Atlantic v3.1, 2026-10-30 12:00 UTC, at CO-OPS 8443970 (Boston, MA). It was selected before any statistics were computed (§1).
- **Common window [V].** Forecast lead 0 < lead ≤ 48 h: the same 480 six-minute valid times for both models, 2026-10-30 12:06 to 2026-11-01 12:00 UTC, exact timestamp matching, no missing records.
- **Forecast results [V].**

  | | Bias | RMSE | Centred RMSE | r |
  |---|---:|---:|---:|---:|
  | STOFS-2D-Global | −0.0005 m | 0.123 m | 0.123 m | 0.9934 |
  | STOFS-3D-Atlantic | −0.143 m | 0.246 m | 0.200 m | 0.9913 |

- **Independent check [V].** Ocean-MCP and the independent recalculation agree on every metric within 6×10⁻⁵, and point by point. Model values differ only by the server's 4-decimal rounding; observation values are identical.
- **Caveats on interpretation [D/V].**
  - Both products apply observation-based bias corrections (§8), so this is not an independent assessment of model physics.
  - The observations are CO-OPS **preliminary** data.
  - NOAA's STOFS-3D station conversion follows VDatum's xGEOID20b→LMSL transformation. VDatum's LMSL matches the CO-OPS MSL datum at Boston. The 3D bias therefore **cannot be attributed to the station datum conversion** (§3).
  - The remaining reference caveats are the tidal epoch and the unverifiable 2D realization. Present-day sea level at Boston is about 0.15–0.20 m above the 1983–2001 MSL datum epoch.
  - The 3D error is dominated by tidal phase and amplitude (lag +12 min, σ 12.5% high). The mean bias is 34% of the mean squared error.
- **Verdict.** The example is suitable for the manuscript **as a demonstration of retrieval, metadata handling, alignment and reproducible statistics**, not as a skill comparison. Three conditions apply first: release stofs-mcp 0.3.0, rerun once CO-OPS verifies the observations, and deposit the raw inputs in a DOI archive (§11).

---

## 0. Prerequisite: the three critical STOFS defects

These were reproduced against `69e721f` (`fix/stofs-versioned-datum`) with the review's probes, then rerun against the hardened code:

| Blocker (second review) | At `69e721f` | After hardening |
|---|---|---|
| C1. Unknown or conflicting datum metadata | `…_above_ngvd29` → silently **LMSL**, note "names no specific datum". `…_above_NAVD2022` → **NAVD88**. standard_name navd88 + long_name msl → NAVD88, no flag | NGVD29 / NAVD2022 → *unsupported*, datum `undetermined`, comparison refused. Contradictory attributes → *conflicting*, refused |
| C2. Warnings and provenance missing in tools | Station JSON for a NAVD88 file on a v3.1 cycle: no warning | Station, point, max and compare tools all emit `datum_warning` and `datum_provenance`, in JSON and Markdown |
| C3. NaN / Infinity / masked / invalid JSON | Compare with NaN/Infinity observations → JSON containing `Infinity` | Non-finite, masked and fill values are excluded and counted. All JSON uses `allow_nan=False` after null-normalization |

`fix/stofs-datum-hardening` (stacked on `fix/stofs-versioned-datum`; neither existing branch was modified):

| Commit | Change |
|---|---|
| `a263b9c` | C1: classify labels as absent / generic / recognized / unsupported / conflicting. Documented fallback only for ADCIRC STOFS-2D/ESTOFS files. Raw attributes and product version kept |
| `103eee0` | C2: provenance and warnings in every station-based tool. Stale `fetch_coops_observations` docstring fixed |
| `8d93b45` | C3: one validity rule (mask, `_FillValue`, `missing_value`, ±Inf/NaN), counted exclusions, strict JSON. Max tool fixed (a dry station could rank at −99999 m) |
| `c370b2b` | Second review H2: one-to-one, exact-first, deterministic UTC pairing (an observation was reused before). Quality counts over matched pairs. Window measured from the raw file start. Invalid cycle hours rejected |
| `31e7f6a` | Feature: `lead_start_hours` / `lead_end_hours` (window lead_start < lead ≤ lead_end from the cycle time), needed for same-valid-time comparisons |

Verification of the branch [V]:

- 298 unit tests pass (234 before; 64 new regression tests), including the stdio protocol test.
- Live suite: 5 passed, 2 skipped (NOMADS OPeNDAP retired, pre-existing).
- Lint (`ruff check` and `ruff format --check`) passes on all 312 server files, and `uv build` succeeds.
- Real NOAA files resolve as expected:

  | File | Resolved datum |
  |---|---|
  | 3D 2026-02-18 (`stofs.v2.1.18`) | NAVD88 |
  | 3D 2026-10-30 (`stofs.v3.1.6`) | LMSL |
  | 2D 2026-10-30 12z (`STOFS_2D_GLOBAL V3.1.0`) | LMSL (documented fallback) |
  | ESTOFS 2022-12-01 | LMSL (documented fallback) |

- Full CI has **not** run, because nothing was pushed.

### Revision 2: fixes after the independent audit (`fix/stofs-release-prep`, stofs-mcp 0.3.0)

| Commit | Change |
|---|---|
| `0e07048` | **Audit C-1, critical.** Shifted no-data sentinels: \|v\| ≥ 10⁴ m is excluded as `sentinel`, and 50 m ≤ \|v\| < 10⁴ m as `implausible`, in every tool, counted by reason. The max tool names excluded stations |
| `52f5ae6` | **Audit M-2.** The STOFS-2D datum fallback is limited to documented versions (V2.1, V3.1; ESTOFS V2.1 with a warning). V4.0 and other unknown versions are `undetermined` |
| `1240d98` | Audit minor findings: "above the geoid" wording, null quality flags, duplicate model times, NumPy arrays in JSON, docstring |
| `db234f7` | Audit M-3. The 0.2.0 maps `MODEL_DATUMS` / `COOPS_VALIDATION_DATUMS` are restored as deprecated. Version bumped to 0.3.0, and a CHANGELOG added |

The sentinel defect affected **this cycle's 3D file**, at five Caribbean stations, not Boston:
- At `31e7f6a`, the max-water-level tool ranked them at 9,999,999.4–9,999,999.6 m.
- The station tool returned 1,200 values of ≈ 10⁷ m labelled LMSL.
- `scripts/02b_replay_tools_offline.py` reruns all four affected tools on the archived file with the 0.3.0 code. Those stations are excluded and named, and the top 3D value is 3.3 m at Eastport (`results/replay_offline.json`).
- The Boston series contains no excluded value, and its comparisons are identical.

0.3.0 verification [V]: 356 tests pass on CPython 3.11.14, 3.12.3 and 3.13.2. CI's lint and format checks pass; the wheel and sdist build; live tests give 5 passed, 2 skipped.

Not addressed: coordinate validation (second review H1), `swl` residual labelling, VDatum output provenance, the retired gridded route. See §10.

---

## 1. Selected cycle and justification

**2026-10-30 12:00 UTC**, the primary candidate in the brief.

- It is after the v3.1 implementation (2026-08-17 12z) [D].
- It is the only daily cycle of STOFS-3D-Atlantic (12z) and one of the four 2D-Global cycles.
- Both station NetCDF files were present on NOAA's S3 archive. HEAD and download both succeeded, Last-Modified 2026-10-30 19:43 and 19:57 UTC [V].
- The cycle was fixed before any statistics were computed. It was not chosen as "latest", and no other cycle was tried.
- Boston has both products' station output and continuous 6-minute observations for the window: 721 records, none missing [V].

## 2. Exact datasets and NOAA sources

All bytes were retrieved 2026-11-04 21:52 UTC by `scripts/00_fetch_inputs.py`. `data/manifest.json` records the URL, query parameters, size, SHA-256, retrieval time and Last-Modified for 59 objects.

| Input | Source | Size | SHA-256 |
|---|---|---:|---|
| STOFS-2D-Global station NetCDF | `https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.20261030/stofs_2d_glo.t12z.points.cwl.nc` | 25,231,796 B | `f1ed4e592982fc5974d5356ba06a90c00bdb41ead0308163221a54b018746c23` |
| STOFS-3D-Atlantic station NetCDF | `https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/stofs_3d_atl.20261030/stofs_3d_atl.t12z.points.cwl.nc` | 8,297,477 B | `4660819425aa1d2eec0e63a37d3a78e8fef2e00f62a1cb56f088347ef51a450f` |
| CO-OPS water level, 8443970, MSL, metric, GMT, 2026-10-29 12:00 to 2026-11-01 12:00 | `api.tidesandcurrents.noaa.gov/api/prod/datagetter` (product `water_level`) | 54,345 B | `c207c80138900573e09fe2733efdc2c055b923c9dc39f5c594d46d4d84ff8d6d` |
| CO-OPS station datums | `…/mdapi/prod/webapi/stations/8443970/datums.json?units=metric` | 2,225 B | `1be5e5d22f3e210a51696ad825624e9daac9081010e0a3224992ccbed74e3ae1` |
| CO-OPS monthly mean sea level, MSL, 2025-01 to 2026-10 | datagetter, `monthly_mean` | 5,896 B | `c6c0aa19b6eecd11aa6690f633c8ab47bee567e74c5bff76b153cca17b8fd5fc` |
| NWS SCN 26-51 (STOFS v3.1) | `weather.gov/media/notification/pdf_2026/scn26-51_STOFS.v3.1.pdf` | 58,017 B | `65621c7b068cdd6ffa4e0c7d397aa404f97313fc7ef3f7c0316827d5802b2370` |
| NOAA STOFS portal, 3D / 2D | `polar.ncep.noaa.gov/estofs/atl.htm`, `glo.htm` | 15,816 / 15,333 B | `40a2a7de…` / `5c2b5aeb…` |
| NOMADS STOFS-Global description | `nomads.ncep.noaa.gov/txt_descriptions/STOFS_Global_txt.html` | 4,839 B | `616165ee…` |
| STOFS-3D GRIB2 conus.east f000–f048 (49 files, §3 check only) | `…/stofs_3d_atl.20261030/stofs_3d_atl.t12z.conus.east.fHHH.grib2` | ~53 MB | per file in the manifest |

Archiving:

- **Committed:** the CO-OPS responses, the NOAA documentation pages, the Boston extracts from both NetCDF files (`data/derived/`, every record plus all metadata), all results and figures.
- **Not committed (gitignored):** the full NetCDF (33 MB) and GRIB2 (53 MB) files. They are on disk in `data/raw/`, identified by checksum, and re-fetchable. **They have not been deposited in a permanent archive.**
- Checksums identify the retrieved bytes. They do not guarantee that the upstream object is immutable.

## 3. Product versions and vertical references

| | STOFS-2D-Global | STOFS-3D-Atlantic |
|---|---|---|
| Product version [V] | `STOFS_2D_GLOBAL.V3.1.0` (global `title`; `version` = "unknown"), ADCIRC | package `stofs.v3.1.6` (global `history`: `…packages/stofs.v3.1.6/fix/stofs_3d_atl/stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco`), SCHISM |
| File coverage [V] | 1,860 records, 2026-10-30 06:06 to 2026-11-07 00:00 (lead −5.9 to +180 h) | 1,200 records, 2026-10-29 12:06 to 2026-11-03 12:00 (lead −23.9 to +96 h) |
| `zeta` label [V] | `sea_surface_height_above_geoid` (ADCIRC default, names no datum) | `sea_surface_height_above_msl` |
| Documented station datum [D] | NOMADS: "STOFS-2D-Global water level forecast guidance is referenced to Local Mean Sea Level (LMSL) for gridded and station output (SHEF files are referenced to MLLW)." | SCN 26-51 and portal: "Station netCDF output will now be referenced to local mean sea level (LMSL) (no longer NAVD88), while gridded output will remain referenced to xGEOID20b." The portal adds: "Operational implementation … occurred at the 12 UTC cycle on August 17 2026" |
| Resolution by Ocean-MCP [V] | `documented_fallback` → LMSL, no warning | `file_metadata` → LMSL, no warning |
| Boston output point [V] | 42.35488 N, 71.04857 W (178 m from the gauge) | 42.35390 N, 71.05028 W (gauge coordinates) |
| CO-OPS request datum | MSL | MSL |

STOFS-3D-Atlantic distinguishes station NetCDF combined water level (**LMSL**) from gridded water level (**xGEOID20b**) [D]. Only station NetCDF is used in the comparison.

### LMSL versus the CO-OPS MSL datum

No offset was applied anywhere. These are evaluations of the reference, not corrections.

1. **The CO-OPS MSL datum is an epoch datum [V].** At Boston it is the 1983–2001 tidal-epoch mean: MSL 2.660 m and NAVD88 2.752 m above station datum, so NAVD88 − MSL = 0.092 m.
2. **Present-day water levels sit above that epoch [V].**
   - Over 2025-10 to 2026-09, Boston's monthly mean sea level averaged **+0.148 m** relative to the MSL datum (range +0.054 to +0.237 m). 2026-10 was not yet available.
   - The observed mean over the forecast window was **+0.202 m**.
   - A model whose output is referenced to the epoch datum must reproduce this present-day offset, either physically or through observation-based correction (§8).
3. **VDatum's LMSL matches the CO-OPS MSL datum at Boston [V].** VDatum gives NAVD88→LMSL **0.0917 m** at the gauge; CO-OPS gives NAVD88 − MSL **0.092 m**.
   - Grids: `us_noaa_nos_LMSL-ITRF2020_2020.0_nwldatum_4.7.0_20240621_3.tif`, `xGEOID20B.tif`, `us_noaa_g2018u0.tif`.
   - The ITRF2020 2020.0 frame epoch in the grid names is a different concept from the 1983–2001 tidal epoch.
4. **NOAA's 3D station LMSL is the VDatum LMSL [V].** Two independent lines of evidence for this cycle come from `scripts/05c`–`05e`, written to `results/allstations_grid_vs_vdatum.json`.

   **(a) NOAA's own conversion constants.** Five Caribbean stations hold 1e7 + c for every record, a no-data value to which NOAA's xGEOID20b→LMSL post-processing added the station constant c. So c can be read directly, with no grid involved:

   | Station | NOAA c (m) | VDatum xGEOID20b→LMSL (m) | NOAA − VDatum (m) |
   |---|---:|---:|---:|
   | 9751401 Lime Tree Bay, VI | −0.5562 | −0.5565 | +0.0003 |
   | 9752235 Culebra, PR | −0.4500 | −0.4506 | +0.0006 |
   | 9751381 Lameshur Bay, VI | −0.4180 | −0.4171 | −0.0009 |
   | 9752695 Esperanza, PR | −0.4768 | −0.4833 | +0.0064 |
   | 9751364 Christiansted, VI | −0.5893 | −0.5645 | −0.0248 |

   **(b) Station minus grid, at every station.** The criteria are those of the audit:
   - a wet GRIB2 cell (finite in all 49 hourly fields) within 4 km;
   - an hourly station-minus-grid SD below 5 cm over lead 0–48 h;
   - residual = mean(station − xGEOID20b grid) − VDatum xGEOID20b→LMSL at the station.

   133 stations have a wet cell within 4 km, and **115** meet both criteria:

   | Statistic | Residual (m) |
   |---|---:|
   | Median | +0.0001 |
   | Mean | +0.0003 |
   | SD (sample / population) | 0.0455 / 0.0453 |
   | 10th / 90th percentile | −0.0130 / +0.0277 |
   | Northeast, lat > 40 N, n = 17: median, SD (population) | −0.0008, 0.0168 |
   | Largest \|residual\| | Pilottown, LA −0.439 (Mississippi River); Dahlgren, VA +0.103; Freeport Harbor, TX +0.065 |

   **Interpretation.** NOAA's station conversion follows the VDatum xGEOID20b→LMSL transformation (the vendored `nwldatum_4.7.0` grids). The constants agree to within 1 mm at three sites, and the all-station residual is centred on zero.

   **Boston.** Station minus grid at the nearest wet cell (0.86 km) is +0.4583 m (SD 0.0052 m), against VDatum's +0.4176 m, a residual of **+0.0407 m**.
   - It is the largest of the 17 Northeast stations, and its |residual| exceeds that of 93% of all 115.
   - It is a **station-versus-grid-cell residual, not a datum difference.** The inner harbour is below the 2.5 km grid scale, with one wet cell within 3 km. The proxy's site-level spread (SD ≈ 4.5 cm, tails of ±3–10 cm) is as large as the residual.
   - The 5.3 and 5.5 km cells that revision 1 cited as corroboration are compared with the same Boston series, so they are not independent evidence.

   **Not claimed.** This does not establish millimetre-level absolute accuracy of the reference at Boston:
   - Site-level departures of NOAA's constant from the vendored VDatum version cannot be excluded at Boston, as Christiansted shows (−2.5 cm, plausibly a grid-version difference), although nothing indicates one.
   - VDatum's own transformation uncertainty is not quantified here.
   - At the gauge, VDatum's direct xGEOID20b→LMSL path (0.4176 m) and its path through NAVD88 (0.3305 + 0.0917 = 0.4222 m) differ by 4.6 mm.
5. **2D realization [U].** The 2D files carry no specific label, and there is no xGEOID-based gridded product to test the conversion against, so NOAA's 2D LMSL realization cannot be checked from these data. The 2D station bias correction (§8) ties the output's recent mean to CO-OPS observations, which limits but does not identify any reference difference.

Conclusion:
- The STOFS-3D station values are traceable to VDatum LMSL. VDatum LMSL matches the CO-OPS MSL datum at Boston (0.0917 vs 0.092 m via NAVD88). The 3D bias (−0.143 m) therefore cannot be attributed to the station datum conversion.
- Two reference caveats remain. The first is the tidal epoch: present-day sea level is +0.15–0.20 m above the 1983–2001 datum, and the model must carry that offset through its physics or its observation-based correction. The second is the unverifiable 2D realization.
- Matching labels alone were not taken as proof of compatibility.

## 4. Observation retrieval and alignment

- **Request [V].** One archived request: `station=8443970`, `product=water_level`, `datum=MSL`, `units=metric`, `time_zone=gmt`, 2026-10-29 12:00 to 2026-11-01 12:00 UTC. It returned **721 records**, 6-minute sampling, with 0 missing, 0 non-finite, 0 malformed and 0 duplicate.
- **Status and flags [V].**
  - All records are **preliminary** (`q = "p"`); none is verified.
  - In the forecast window, 110 of the 480 matched observations have a nonzero `O` flag: the count of 1-second samples outside 3σ within the 6-minute average. None has an F (flat), R (rate-of-change) or L (limit) flag.
  - Flagged records are kept and counted, not removed.
- **Ocean-MCP pairing [V].** One-to-one, exact timestamps first, then the nearest unused observation within 3 min, with ties going to the earlier observation; UTC arithmetic. All pairs in all four windows were exact: 480 / 60 / 480 / 240 exact, 0 nearest, 0 unmatched model records.
- **Independent pairing [V].** Exact timestamps only. It gives the identical pair sets.
- **Live versus archived [V].** Ocean-MCP fetched its own observations at 21:55 UTC, 3 minutes after the archive retrieval. Its paired observation values are identical to the archived response (max difference 0.0 m).

## 5. Forecast-window definition

- **Common forecast window (primary): 0 < lead ≤ 48 h from 2026-10-30 12:00 UTC.** Valid times 2026-10-30 12:06 to 2026-11-01 12:00 UTC: 480 six-minute times, identical for both models. Both files cover the full window [V].
- **Nowcast windows, reported separately and not compared across models:**
  - 2D: −6 < lead ≤ 0 h, 60 points (2026-10-30 06:06 to 12:00);
  - 3D: −24 < lead ≤ 0 h, 240 points (2026-10-29 12:06 to 2026-10-30 12:00).

  The nowcast durations differ, so the two nowcasts are not like for like.
- **Model records.** In every window, no model record was masked, fill or non-finite. Lead 0 (the cycle time) belongs to the nowcast segment, matching Ocean-MCP's segment convention.

## 6. Numerical verification table

Here e = model − observed, in metres.

| Metric | Definition | 2D forecast | 3D forecast | 2D nowcast | 3D nowcast |
|---|---|---:|---:|---:|---:|
| Window (lead, h) | lead_start < lead ≤ lead_end | (0, 48] | (0, 48] | (−6, 0] | (−24, 0] |
| Matched pairs n | | 480 | 480 | 60 | 240 |
| Mean signed bias | mean(e) | −0.0005 | −0.1430 | −0.0182 | −0.0295 |
| RMSE | √mean(e²) | 0.1230 | 0.2456 | 0.0238 | 0.2252 |
| MAE | mean\|e\| | 0.1000 | 0.2086 | 0.0196 | 0.2002 |
| Centred RMSE | √mean((e − ē)²) | 0.1230 | 0.1996 | 0.0153 | 0.2232 |
| Pearson r | cov(M,O)/(σM σO) | 0.9934 | 0.9913 | 0.9999 | 0.9866 |
| Max \|e\| (time UTC) | max\|e\| | 0.266 (10-31 11:54) | 0.535 (10-31 14:42) | 0.057 | 0.398 |
| max(M) − max(O) | | −0.067 | +0.013 | −0.004 | +0.072 |
| Observed max (time) | | 2.002 (10-30 18:54) | 2.002 (10-30 18:54) | 1.502 | 1.996 |
| Model max (time) | | 1.935 (10-30 19:12) | 2.015 (10-30 19:18) | 1.498 | 2.067 |
| Mean model / mean obs | | 0.2015 / 0.2020 | 0.0590 / 0.2020 | 0.4459 / 0.4641 | 0.1685 / 0.1980 |
| σM / σO | | 1.0705 / 1.0635 | 1.1968 / 1.0635 | 0.9003 / 0.8948 | 1.2466 / 1.1380 |
| Excluded model records | | 0 | 0 | 0 | 0 |
| Excluded observations | | 0 | 0 | 0 | 0 |
| Preliminary / flagged obs | | 480 / 110 | 480 / 110 | 60 / 24 | 240 / 65 |

These numbers describe this one window; they are not attributions. The 3D centred RMSE (about 0.20 m) is larger than the 2D value even though correlation is high. In the forecast window the 3D standard deviation exceeds the observed by 12.5%, and its best-correlated lag is +12 min (model later; +18 min in the nowcast). The 2D amplitude agrees within 1%, with a best-correlated lag of −12 min. The 480 six-minute samples are serially correlated, so they are not 480 independent cases.

## 7. Independent recalculation

`scripts/03_verify_independent.py` uses only the archived extracts and the CO-OPS response, does not import Ocean-MCP, and runs in an isolated uv-managed environment of 16 packages in which `stofs_mcp` is not importable.

| Window | Max metric difference (Ocean-MCP vs independent) | Same valid times | Max model-value diff | Max obs-value diff | Verdict |
|---|---:|---|---:|---:|---|
| 2D forecast | 3.0×10⁻⁵ | yes | 5.0×10⁻⁵ m | 0 | agree |
| 2D nowcast | 4.6×10⁻⁵ | yes | 5.0×10⁻⁵ m | 0 | agree |
| 3D forecast | 5.8×10⁻⁵ | yes | 5.0×10⁻⁵ m | 0 | agree |
| 3D nowcast | 4.0×10⁻⁵ | yes | 5.0×10⁻⁵ m | 0 | agree |

The comparison covers n, bias, RMSE, MAE, r, max|e| and max(M) − max(O). Centred RMSE, which Ocean-MCP does not report, was cross-checked against √(RMSE² − bias²) from the MCP values. The tolerance is 1×10⁻⁴ (3×10⁻⁴ for the derived centred RMSE). The model-value differences are exactly the server's 4-decimal rounding of model values (≤5×10⁻⁵ m). No disagreement was flagged. Rerunning steps 01–06 in the isolated environment reproduced the independent statistics file **byte for byte**.

The exact MCP requests and raw responses are in `results/mcp/*.json`, with server `stofs-mcp 0.2.0`, MCP SDK 1.30.0, CPython 3.13.2 and git commit `31e7f6a`.

**Offline replay with the 0.3.0 code [V].** `scripts/02b_replay_tools_offline.py` reruns the four archived requests through the tool functions of `fix/stofs-release-prep` (stofs-mcp 0.3.0), with no network. Station files come from copies of `data/raw`, and observations from the archived CO-OPS response.
- All four comparisons are **identical** to the live MCP responses: same series, statistics and peak error (`results/replay_offline.json`).
- The archived NetCDF checksums are unchanged by the run.

## 8. Operational bias correction: caveats

Both products use recent CO-OPS observations operationally. **The results are not an independent validation of uncorrected model physics.**

- **STOFS-2D-Global v3.1 [D].** The 2D-Global upgrade includes "a gridded bias correction. This bias correction uses the current station bias correction approach used in operational STOFS2D-Global (v2.1), which corrects the station water level forecast guidance biases by removing the bias between the observed water levels at NOS/CO-OPS stations and most recent 5 days of nowcast water levels … The result is that both station and gridded output is bias corrected." The near-zero 2D forecast bias (−0.0005 m) is therefore expected by design, and is not evidence of independent skill or reference agreement.
- **STOFS-3D-Atlantic v3.1 [D].** "Inclusion of a dynamic adjustment (bias correction) of open boundary conditions, to account for missing physics in the model, including steric effects … calculated by averaging the model's nowcast bias for the past two days over 11 U.S. East Coast open coast NOS/CO-OPS stations. This bias is then uniformly applied to the open boundary conditions."
- **[U]** Which 11 stations NOAA uses is not stated, so whether Boston is among them is unknown. The exact correction values applied to this cycle are not in the station files.
- No other observation-dependent adjustment was found in the documents reviewed (SCN 26-51, NOAA portal, NOMADS description).

## 9. Figures and reproduction

**Publication figure (revision 2), two panels**, produced by `scripts/06b_figure_two_panel.py`:

- `figures/boston_stofs_v31_fig.pdf` and `.svg` (vector);
- `figures/boston_stofs_v31_fig_300dpi.png` (2244×1560);
- `figures/boston_stofs_v31_fig_preview.png` (150 dpi, 1122×780, for on-screen review).

Design:

- Sized for a 190 mm column; every font is 8–8.5 pt at final size, so all are ≥ 7 pt.
- **A:** observed, 2D and 3D water level over the common forecast window, with valid time below and lead time above. The y-label reads "model LMSL / gauge MSL, no offset applied".
- **B:** signed errors.
- No statistics or metadata appear inside the image.

**Caption:** `figures/boston_stofs_v31_fig_caption.md`, generated by `scripts/06c_statistics_table.py` from the results so its numbers cannot drift. It states:
- cycle, valid times, lead window, product versions, and datums with their provenance;
- the preliminary status of the observations;
- both operational bias corrections;
- that the 3D error is dominated by phase and amplitude;
- input checksums.

**Statistics table** (`scripts/06c_statistics_table.py`), with definitions and units for all four windows:
- `results/table_boston_v31_statistics.csv` and `.json` (machine-readable, full precision);
- `.md` and `.tex` (for typesetting).

The revision-1 three-panel figure (`figures/boston_stofs_v31_validation*`, `scripts/06_figure.py`) is kept for the record and superseded. Its numbers are correct, but its footer type was 6.3 pt and its statistics were rendered as an image.

Reproduction commands, run from the repository root on this branch:

```bash
cd verification_stofs_v31_boston
RUN="uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt python"
$RUN scripts/00_fetch_inputs.py --grib      # or --verify-only to check checksums
$RUN scripts/01_extract_boston.py
(cd .. && uv run --project servers/stofs-mcp python verification_stofs_v31_boston/scripts/02_run_ocean_mcp.py)
(cd .. && uv run --project servers/stofs-mcp python verification_stofs_v31_boston/scripts/02b_replay_tools_offline.py)   # offline; exit 1 if a replay differs
$RUN scripts/03_verify_independent.py      # exit 1 on any Ocean-MCP disagreement
$RUN scripts/04_datum_assessment.py
(cd .. && uv run --project servers/vdatum-mcp python verification_stofs_v31_boston/scripts/05a_vdatum_offsets.py)
$RUN scripts/05b_lmsl_realization_check.py
$RUN scripts/05c_station_table.py
(cd .. && uv run --project servers/vdatum-mcp python verification_stofs_v31_boston/scripts/05d_vdatum_allstations.py)
$RUN scripts/05e_grid_vs_vdatum_allstations.py
$RUN scripts/06b_figure_two_panel.py
$RUN scripts/06c_statistics_table.py
```

Notes on running:

- **Offline replay.** With the raw files present and checked, steps 01, 02b, 03 (against the archived `results/mcp`), 04, 05b, 05c, 05e, 06b and 06c run offline.
- **Live steps.**
  - Step 02 fetches live data from S3 and CO-OPS (4 + 4 requests).
  - Steps 05a and 05d download the VDatum grids on first use.
  - Step 00 makes 2 S3 requests (49 more with `--grib`), 4 CO-OPS requests with 2 s pauses, and 4 documentation requests.
- **Storage.** `data/raw` needs 86 MB.
- **Paths.** All paths are relative to the package. Set `STOFS_V31_DATA` to keep data elsewhere.
- **Environments** are recorded in `environment/`: system, the isolated analysis environment, and the stofs-mcp and vdatum-mcp environments.

## 10. Remaining uncertainties and limitations

1. **Preliminary observations [V].** Every matched observation is preliminary and may be revised when CO-OPS verifies the data. The exact response used is archived with its checksum.
2. **Reference [V/U].**
   - NOAA's 3D station conversion follows VDatum. At Boston no conversion discrepancy is evident, but the grid proxy cannot resolve the reference at one site better than a few centimetres, and VDatum's own uncertainty is not quantified (§3).
   - The 2D realization is unverifiable here.
   - CO-OPS MSL is a 1983–2001 epoch datum, while present-day sea level is about 0.15–0.20 m higher. That epoch offset is the one reference effect that is real and unquantified in the comparison.
3. **Bias corrections [D].** Both products are corrected with CO-OPS observations, and the 2D correction targets station biases directly. The comparison measures the corrected operational guidance.
4. **Scope.** One station, one cycle and one 48 h window, with serially correlated samples. The models' output points differ by 178 m. This is not a skill assessment and not evidence that either model is more accurate in general. The cycle was not chosen for its statistics.
5. **Nowcast windows differ** (6 h versus 24 h) and are reported only for completeness.
6. **Software status.** The live results come from `31e7f6a`, and the offline replay from 0.3.0 (`fix/stofs-release-prep`). Both are unmerged and unreleased. A release and full supported-Python CI on GitHub are still needed; Python 3.11–3.13 pass locally. The remaining second-review items have not been addressed:
   - coordinate validation (H1);
   - `swl` semantics (H3);
   - VDatum output provenance (H5).
7. **Raw-input archive.** The full NetCDF and GRIB2 files are checksummed and re-fetchable but not deposited in a permanent archive.
8. **Side finding [V].** CO-OPS's derived-product endpoint `dpapi/prod/webapi/product/sealvltrends.json?station=8443970` returned a single record for **Kings Point (8516945)**, also with `affil=US` and with no station given. coops-mcp's `coops_get_sea_level_trends` calls this endpoint, so it may report another station's trend. I did not test that tool here. The trend is not used in this package; it should be investigated separately.

## 11. Suitability for the manuscript

**Suitable as the main Section 3.1 demonstration, under these conditions:**

1. Merge and release `fix/stofs-release-prep` (stofs-mcp 0.3.0) together with its base branches. It contains the sentinel fix, without which the 3D product's Caribbean stations read as 10⁷ m. Cite the released version, and rerun step 02 against the release.
2. Rerun steps 00–06 once CO-OPS has verified the 2026-10-29 to 11-01 observations, and report any change. Alternatively, state explicitly that the observations are preliminary and cite the archived response.
3. Deposit the package and the raw inputs (about 33 MB of NetCDF; the GRIB2 files are optional) in a DOI archive.
4. Present the example as a workflow demonstration, not a model comparison.

## 12. Recommendations for revising Section 3.1

These are instructions, not rewritten prose.

- **Replace** the February 2026 STOFS-2D/3D examples as the primary demonstration with this fixed 2026-10-30 12z v3.1 case: one station, one common valid-time window (0 < lead ≤ 48 h, 480 pairs), exact matching.
- **State the vertical references with provenance:**
  - 3D LMSL from file metadata (`sea_surface_height_above_msl`, `stofs.v3.1.6`);
  - 2D LMSL from NOAA documentation (its files carry a generic "above geoid" label);
  - CO-OPS MSL (1983–2001 epoch).
  - Add that no transformation was applied.
  - Add that the 3D station conversion was checked against VDatum. NOAA's constants match it at sentinel stations, and the residual across 115 stations is centred on zero, so the 3D bias cannot be attributed to the conversion.
  - Name the remaining caveats: the tidal epoch, and the unverifiable 2D realization.
  - Do **not** claim a centimetre-level datum difference, or millimetre-level absolute accuracy, at Boston.
- **Report** the forecast statistics from the separate table (`results/table_boston_v31_statistics.*`) with definitions and units. Describe the 3D error as dominated by phase and amplitude (lag +12 min, σ 12.5% high; bias is 34% of the MSE). Say that observations are preliminary and flags were retained.
- **Disclose both bias corrections** (§8), and say explicitly that the low 2D bias is expected from its CO-OPS-based station correction.
- **Do not** rank the models, attribute the 3D bias (−0.143 m) to a datum or to physics, or describe either product as validated.
- **Demonstrate the software contribution:**
  - datum resolution with provenance (`datum_provenance`), and refusal of unknown or conflicting references (cite the regression tests);
  - the lead-time window that made the comparison like for like;
  - strict JSON;
  - agreement with the independent recalculation (§7).
- **Cite** the release, the archive DOI, the exact MCP requests (`results/mcp`), and the reproduction commands.

### The historical February 2026 case

**Recommendation: remove it from the main validation example (option 3) and move it to supplementary material (option 2). Keep at most one sentence in the main text as a metadata caution (option 1).** For example: the v2.1 examples exposed a version-dependent datum transition and a coordinate-order defect, both now handled by the software.

Its windows are not comparable (lead −5.9..+11.3 h versus −23.9..+0.1 h), and its central interpretation (−0.324 m as a datum offset) was not supported. Any supplementary version must use the corrected interpretation in `verification_2026-11-02/REPORT.md`. The original examples and research files were not modified or deleted.
