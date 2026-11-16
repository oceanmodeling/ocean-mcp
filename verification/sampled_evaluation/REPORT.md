# WP5: sampled evaluation of the STOFS safeguards, and a multi-station test of the mean-level bias

Branch `eval/sampled-evaluation` in worktree `.claude/worktrees/sampled-evaluation`, local only.

| Step | Commit / date |
|---|---|
| Design freeze (Phase 1) | `2ea1e00` |
| Amendments A1–A4, before any sampled download | `8a7318d` |
| Phase 2 checkpoint (downloads, A5, A6, pipeline) | `d767d62` |
| Results and this report | the commit that adds this file |

The design is in `DESIGN.md`; every change after the freeze is in `AMENDMENTS.md` (A1–A6 and
implementation notes N1–N5); the brief is `ClaudeCode_Prompt_WP5_Sampled_Evaluation.md`.

## Summary

**Datum pairing: a qualification is needed, not a correction.**
- STOFS LMSL and CO-OPS MSL agree as datums. VDatum's LMSL and the CO-OPS MSL datum differ by a
  median of +3.5 mm (SD 3.7 cm) at 199 stations (A1).
- But the CO-OPS MSL datum is defined on the 1983–2001 epoch. A mean bias against it therefore
  contains the rise in sea level since then (here about +0.2 m), unless the model carries
  present-day mean level.
- Products without observation-based level control do not carry it. Both the pre-v3.1
  STOFS-3D and the uncorrected STOFS-2D (`noanomaly`) show station biases that fall with the
  offset at a slope near −1:
  - 3D v2.1: slope −0.72 [−1.06, −0.50]; mean bias −0.10 m against a mean offset of +0.16 m;
  - uncorrected 2D: slope −0.82 [−1.28, −0.74]; mean bias −0.25 m against +0.22 m.
- The bias-corrected 2D station output removes the dependence: slope −0.02 [−0.07, +0.03].
- STOFS-3D v3.1 carries the mean level on average: mean bias −0.006 m against a mean offset of
  +0.215 m.
- **Study 2 primary result: inconclusive by the pre-registered rule.** The v3.1 slope is −0.01
  [−0.52, +0.19], an interval that contains both 0 and the −0.5 midpoint.
  - Without the four cycles right after the upgrade (S11, S4), it reads "supports H-carried",
    and the reading is robust.
  - One riverine station has high leverage (§2.8, post hoc).
- **Boston.**
  - Over 15 v3.1 cycles the mean bias is −0.059 ± 0.026 m, against an offset of +0.170 m.
  - The −0.143 m of 30 October (outside this sample) is therefore not representative of v3.1 at
    Boston.
  - It equals the pre-v3.1 mean bias at Boston (−0.143 m, NAVD against NAVD), which is about
    minus the offset.

**Study 1: 15,197 station-cycle cases in 60 files.**
- **The tool's outcome:**
  - 9,948 correct comparisons;
  - 105 correct refusals, with the reason matching;
  - 5,143 not-eligible cases, all declined;
  - **0 false refusals and 0 undetected problems**;
  - 1 other discrepancy: a nearest-time observation pairing, within 2.3 mm.
- **Two defects found, not fixed:**
  - In 465 not-eligible cases at 15 stations, the refusal message blames the S3 bucket. The
    real cause is CO-OPS rejecting an unpublished datum (HTTP 400).
  - Duplicated station IDs in the 2D files are not flagged. At 8414721 the two records differ
    by up to 0.15 m.
- **Bounds:** no model value lies between 30 and 50 m, so the tool's 50 m bound and the
  reference's 30 m bound never disagreed.
- **stofs-mcp 0.2.0** paired every v3.1 case with NAVD (2,445 wrong pairings). It proceeded in
  1,767 of them, including all 75 Caribbean no-data cases.

**MCP sessions.** All 121 real MCP stdio sessions were valid:
- 30,783 calls and 61,042 replayed requests;
- 0 replay misses and 0 network attempts;
- six live replay-rule checks, each byte-identical.

**Requests.** NOAA requests: 483 in Phase 0 and 4,012 in Phase 2, against a cap of 4,298. **Study 3**
is in §3.

---

## 1. Study 1: behaviour of the safeguards on sampled data

Unit: one case = (product, cycle, CO-OPS station ID); 15,197 cases, 389 distinct stations
(164 in 3D files, 374 in 2D files), 60 files. Window 0 < lead ≤ 49.7 h. Classes as frozen in
DESIGN.md §4.5. Full tables: `results/study1/tables.md`, `by_station.csv`, `by_cycle.csv`,
`by_defect.csv`, `individual_cases.csv`, `outcomes.jsonl`.

### 1.1 Outcome classes per product

**Sample without the previously seen cycles** (28 dates):

| class | 3D v2.1 (NAVD88) | 3D v3.1 (LMSL) | 2D | all |
|---|---:|---:|---:|---:|
| correct comparison | 1,400 | 1,886 | 5,996 | 9,282 |
| correct refusal (reason matches) | 0 | 70 | 28 | 98 |
| refusal, reason differs | 0 | 0 | 0 | 0 |
| false refusal | 0 | 0 | 0 | 0 |
| undetected problem | 0 | 0 | 0 | 0 |
| not eligible | 84 | 326 | 4,391 | 4,801 |
| other discrepancy | 0 | 0 | 1 | 1 |
| total | 1,484 | 2,282 | 10,416 | 14,182 |

**Previously seen cycles** (2026-08-16 and 2026-08-17): 1,015 cases.
- 666 correct comparisons, 7 correct refusals and 342 not eligible.
- No false refusal, undetected problem or other discrepancy, the same pattern as the rest.

**All cycles:** 9,948 / 105 / 0 / 0 / 0 / 5,143 / 1, in the order of the table, out of 15,197.

**Distinct stations and files per class:**

| class | cases | stations | files |
|---|---:|---:|---:|
| correct comparison | 9,948 | 226 | 60 |
| correct refusal | 105 | 6 | 45 |
| not eligible | 5,143 | 169 | 60 |
| other discrepancy | 1 | 1 | 1 |

### 1.2 Defect classes (reference properties) and what the tool did

| defect | cases | stations | files | tool outcome |
|---|---:|---:|---:|---|
| model no-data codes (|v| ≥ 1,000 m) in the series | 122 | 9 | 44 | 75 correct refusals (3D v3.1: five Caribbean stations, 1e7 + c in every record); 47 correct comparisons (2D: −99998.6 dry values at 8779748, 8571421, 8652587, excluded and counted exactly as the reference counts them) |
| model fill (= `_FillValue`/`dry_Value`) in the series | 196 | 12 | 30 | 30 correct refusals (2D 9753216 Fajardo: every record fill), 165 not eligible, 1 correct comparison |
| station ID on more than one record | 146 | 6 | 45 | 72 correct comparisons, 74 not eligible; see §1.3 D-2 |
| observations flagged (O, F, R or L) | 3,117 | 226 | 60 | counted, never filtered (design) |
| observations with missing values | 94 | 41 | 27 | 76 correct comparisons, 15 not eligible, 2 correct refusals, 1 other |
| paired datum not published (what CO-OPS served) | 465 | 15 | 45 | 465 not eligible, all with the misleading message of §1.3 D-1 |
| no valid paired observation in the window | 5,143 | 169 | 60 | 5,143 not eligible |
| fewer than 80% of the window paired | 23 | 5 | 19 | 23 correct comparisons |

**Not found anywhere in the sample:**
- datum-label defects: every 3D label matched the documented datum for its version, and every
  2D label was the generic "geoid";
- non-finite model values;
- values outside a CF valid range;
- ID substring collisions.

**Not-eligible cases:**
- 4,678 were declined with a matching reason ("Could not fetch CO-OPS observations … No data was
  found");
- 465 with the misleading message of D-1.

### 1.3 Every false refusal, undetected problem and other discrepancy

- **False refusals:** none.
- **Undetected problems:** none.
- **Other discrepancy (1): `2d_20261102_9440083`.**
  - The tool paired one observation by nearest time within 3 min, which its documented method
    allows. The reference pairs exact timestamps only.
  - As a result n = 457 against 456. The differences are bias +2.3 mm, RMSE +6.4 mm and MAE
    +1.9 mm, all inside 1 cm. The datum pairing and the exclusion counts agree.
  - Evidence is in `individual_cases.csv`.

**Defects found (recorded, not fixed; proposed fixes only):**

- **D-1. Misleading refusal reason when CO-OPS rejects the datum** (465 cases, 15 stations: 14
  2D-only stations without an MSL datum, e.g. 8531232, 8578240, plus 9441644, and one 3D v3.1
  station).
  - CO-OPS answers HTTP 400 ("There is no MSL for the station: …" or "The supported Datum values
    are: …").
  - `fetch_coops_observations` calls `raise_for_status()`, so the error reaches
    `handle_stofs_error`, which reports "HTTP 400 error (2d_global). The STOFS S3 bucket may be
    temporarily unavailable. Please try again."
  - The decline is correct but the reason is wrong, and it invites a retry that cannot succeed.
  - **Proposed fix:** in `fetch_coops_observations`, read the JSON `error.message` before
    `raise_for_status()` and raise `ValueError` with it. The compare tool's existing branch then
    says "Could not fetch CO-OPS observations: CO-OPS API error: There is no MSL for the
    station …". Add a test with the archived 400 body.
- **D-2. Duplicated station IDs are not reported.**
  - Six IDs occur on two records:
    - 3D v2.1: 8651370 Duck and 8661070 Springmaid Pier, whose two records are identical in the
      window;
    - 2D: 8414721, 8416731, 8423898, 8639348, 8651370 and 8661070.
  - In the 2D files the two records differ by up to 0.151 m (8414721), 0.033 m (8416731), 0.017
    m (8423898), 0.010 m, 0.003 m and 0.002 m in the window.
  - The tool takes the first record whose name contains the ID, as the reference does by
    design, and says nothing.
  - **Proposed fix:** when more than one record matches, return `station_warning` naming the
    records, the one used and the largest difference in the window.
- **Not a defect, noted:** the nearest-time pairing above is the documented method.

### 1.4 Model values between 20 m and 100 m

- **Where they are:** 371 values in all records of all 60 files, all at the 2D point
  `UJ816 SOUS00 SA816` (Sea of Azov, not a CO-OPS station).
  - Range 85.66–99.98 m.
  - They occur in 11 files (2D v3.1), 229 of them inside a window.
- **Bound comparison:** no value has 30 m < |v| < 50 m, so no case is classed differently under
  the tool's 50 m bound and the reference's 30 m bound.
- **S9:** bounds of 20, 50 and 100 m reclassify 0 mapped cases.
- **A 100 m bound** would keep SA816's values below 100 m, as the hardening report said.

### 1.5 stofs-mcp 0.2.0 contrast (decision and pairing only)

| product | reference | 0.2.0 decision | CO-OPS datum requested | cases |
|---|---|---|---|---:|
| 2D | compare | proceed | MSL (right) | 6,429 |
| 2D | not eligible | decline | MSL (right) | 4,703 |
| 2D | refuse | decline | none | 30 |
| 3D v2.1 | compare / not eligible | proceed / decline | NAVD (right) | 1,500 / 90 |
| 3D v3.1 | compare | proceed | **NAVD (wrong)** | 1,690 |
| 3D v3.1 | compare | decline | **NAVD (wrong)**; the station has no NAVD | 330 |
| 3D v3.1 | not eligible | decline / proceed | **NAVD (wrong)** | 348 / 2 |
| 3D v3.1 | refuse (no-data codes) | **proceed** | **NAVD (wrong)** | 75 |

### 1.6 coops-mcp 0.1.1

- **Calls:** `coops_get_datums` was called for all 389 stations in one valid session.
- **What a client can learn:** in every case the response shows MSL and NAVD88 exactly as the
  metadata API lists them, so a client can tell whether the paired datum is published.
- **What it cannot learn:** the response never states the tidal-datum epoch, so through MCP a
  client cannot learn the epoch that Study 2 depends on.

### 1.7 Other observations

- **Preliminary observations:** 931 of the 9,949 cases with pairs contain at least one
  preliminary paired observation; in 9,018 all paired observations are verified.
- **Version against date:**
  - The 2D file of 2026-08-16 12z is V3.1.0, one cycle before the portal's documented date
    (2026-08-17 12z for both products).
  - The 3D switches at 2026-08-17 12z, as documented.
  - SCN 26-51 had announced 7 July, and its update 11 August.
- **Metadata against service:**
  - At 10 Puerto Rico and USVI stations the metadata lists no NAVD88, yet CO-OPS serves data for
    `datum=NAVD`.
  - This matters only for 0.2.0's 3D pairing; no reference pairing uses NAVD there.
- **Provisional datum.** Three Louisiana stations on the modified epoch (8760721, 8760922,
  8762075) carry a CO-OPS "Provisional Datum" disclaimer in their observations from 2026-10-18.
  The reference reads only the data (A6).

---

## 2. Study 2: does the STOFS-3D-Atlantic mean bias track the rise since the datum epoch?

Hypotheses, quantities and the decision rule were fixed before any sampled file was read
(DESIGN.md §7, amendments A1–A3). B = station mean of the window-mean error (model − observed);
X = recent MSL above the station's CO-OPS MSL datum = 12-month verified mean before the period
+ 2016–2025 seasonal anomaly of the cycle months (observations only). NTDE stations unless
stated. Intervals: 95% station bootstrap (10,000 resamples, seed 20261109).

### 2.1 Regressions

| analysis | stations | slope [95% CI] | Theil–Sen | intercept (m) [95% CI] | mean X (m) | mean B (m) | level B + X (m) [95% CI] | verdict (A2) | cluster bootstrap |
|---|---:|---|---:|---|---:|---:|---|---|---|
| **3D v3.1, post-transition (primary)** | 122 | −0.01 [−0.52, +0.19] | −0.22 | −0.004 [−0.048, +0.112] | +0.215 | −0.006 | +0.209 [+0.187, +0.230] | **inconclusive (slope)** | same (slope CI [−0.57, +0.82]); robust |
| 2D, same stations (control) | 114 | −0.02 [−0.07, +0.03] | −0.03 | +0.007 | +0.215 | +0.001 | +0.216 [+0.199, +0.229] | supports H-carried | robust |
| 2D, all eligible stations | 184 | −0.02 [−0.10, +0.04] | +0.03 | +0.004 | +0.158 | +0.001 | +0.158 [+0.140, +0.175] | supports H-carried | robust |
| 3D v2.1, pre-transition (NAVD vs NAVD) | 94 | −0.72 [−1.06, −0.50] | −0.84 | +0.010 | +0.156 | −0.101 | +0.054 [+0.040, +0.069] | not separable: depends on whether the model carries the seasonal cycle (X: H-epoch; O12_pre: not separable) | fragile (cluster CI [−1.34, −0.11]) |
| 2D `noanomaly` (uncorrected), same stations | 114 | −0.82 [−1.28, −0.74] | −1.11 | −0.076 | +0.215 | −0.252 | −0.037 [−0.046, −0.028] | not separable: depends on the seasonal cycle (X: H-epoch; O12_pre: negative offset) | robust (cluster CI [−1.23, −0.71]) |
| 2D `noanomaly`, all stations | 184 | −1.42 [−1.77, −1.12] | −1.17 | +0.066 | +0.158 | −0.158 | −0.000 [−0.018, +0.019] | outside both (slope below −1) | fragile |
| 3D v3.1, modified-epoch stations | 8 | −0.45 [−1.95, +0.50] | — | +0.144 | — | — | +0.236 | inconclusive (too few) | — |

**Boundary-adjustment stations, 3D v3.1:**
- mean B = −0.049 m;
- mean X = +0.251 m;
- so the carried level L = B̄ + X̄ = +0.20 m, with a carried-fraction interval of
  [−0.19, +0.45] under the primary fit.

The adjustment brings the network mean near zero but does not zero its own stations.

### 2.2 Sensitivity runs (none replaces the primary)

| run | stations | slope [95% CI] | verdict |
|---|---:|---|---|
| S1 window (0, 24.8] h | 122 | −0.01 [−0.54, +0.18] | inconclusive |
| S1 window (0, 48] h | 122 | −0.01 [−0.52, +0.19] | inconclusive |
| S2 X = O12 + S (per cycle) | 122 | −0.04 [−0.68, +0.10] | inconclusive |
| S2 X = O12 (the brief's annual estimate) | 124 | −0.40 [−1.55, −0.06] | inconclusive |
| S2 X = O29 (shares the window; cannot corroborate H-epoch) | 127 | −0.48 [−1.20, −0.16] | inconclusive |
| S3 without the 11 boundary stations | 111 | +0.02 [−0.49, +0.29] | supports H-carried |
| S4 weekly cycles only (without 08-18 to 08-20) | 122 | +0.07 [−0.18, +0.43] | supports H-carried; robust |
| S5 without previously seen cycles | 122 | +0.01 [−0.42, +0.26] | supports H-carried; fragile |
| S6 modified epochs pooled | 130 | −0.12 [−0.70, +0.04] | inconclusive |
| S7 cases with ≥ 90% verified observations | 122 | −0.10 [−0.75, +0.04] | inconclusive |
| S8 2D control, all 30 cycles | 184 | +0.01 [−0.01, +0.03] | supports H-carried |
| S10 stations with \|d\| ≤ 0.03 m (A1) | 82 | −0.24 [−0.83, +0.24] | inconclusive |
| S11 cycles from 2026-08-24 (spin-up excluded, A3) | 122 | +0.10 [−0.08, +0.50] | supports H-carried; robust |

**A2 (primary):**
- The slope reading is inconclusive under both offset definitions.
- The level test gives +0.209 [+0.187, +0.230] with X = O12_pre + S, and +0.138 [+0.120, +0.155]
  with X = O12_pre.

### 2.3 A3: spin-up and the boundary stations, per cycle

From `results/study2/tables.md`, NTDE stations entering each cycle:

- **3D v2.1 (2026-06-01 to 08-16):**
  - mean bias −0.03 to −0.15 m;
  - at the boundary stations −0.03 to −0.23 m.
- **3D v3.1:**
  - the mean bias jumps at 2026-08-17 to −0.012 m, and stays within −0.04 to +0.04 m to
    2026-11-02;
  - at the boundary stations −0.002 to −0.113 m (mean −0.05).
- **2D corrected:** within ±0.03 m every cycle.
- **2D uncorrected:**
  - −0.09 to −0.12 m from June to August, then a steady fall to −0.23 m in late October;
  - at the boundary stations −0.23 to −0.40 m.
  - This tracks the seasonal autumn high, which the uncorrected model does not carry.

### 2.4 A4: Boston 8443970

- **Per cycle:** in `results/study2/results.json` → `A4_boston` and `results/study2/tables.md`.
- **Means over the sampled cycles:**

| product | cycles | paired datum | mean bias (m) | model mean (m) | observed mean (m) | X (m) |
|---|---:|---|---:|---:|---:|---:|
| 3D v2.1 | 15 | NAVD | −0.143 | −0.064 | +0.080 | +0.151 |
| 3D v3.1 | 15 | MSL | −0.059 (SD 0.026; range −0.110 to −0.019) | +0.124 | +0.183 | +0.170 |
| 2D corrected | 30 | MSL | about 0 (per cycle −0.04 to +0.03) | | | |
| 2D uncorrected | 30 | MSL | −0.250 (SD 0.041) | −0.066 | +0.183 | +0.170 |

All Boston windows have n = 497.

### 2.5 A1: datum consistency d = (CO-OPS MSL) − (VDatum LMSL)

- **Same setup as the Boston package:** the offline VDatum value at the Boston gauge equals the
  Boston package's bit for bit (0.09173215948229796 m).
- **Coverage:** of the 217 stations with MSL and NAVD88, 199 were evaluated. 18 could not be:
  outside the VDatum grids or no coordinates (table in `results/study2/tables.md`).
- **Statistics:** median d +0.0035 m, SD 0.037 m; |d| ≤ 0.03 m at 156.
- **Largest |d|:** +0.193 m at 8774770 Rockport TX, on the modified 2002–2006 epoch.
- **Data:** `results/a1/datum_consistency.{json,csv}`.

### 2.6 Figure

`figures/bias_vs_offset.png`:
- **Left panel:** station mean bias against X for 3D v3.1.
- **Right panel:** the same for 2D, corrected (filled) and uncorrected (open).
- **Lines:** the H-epoch line B = −X and the OLS fits.

### 2.7 Which hypothesis the data support

- **By the pre-registered rule, the primary analysis is inconclusive.**
  - The v3.1 slope interval [−0.52, +0.19] contains 0 and reaches past −0.5.
  - The cluster bootstrap agrees.
- **What the data do show for v3.1 is not H-epoch at the network scale.**
  - H-epoch predicts a mean bias near −0.215 m; it is −0.006 m.
  - The level test is +0.209 against 0 predicted by H-epoch.
- **With the four days right after the upgrade excluded** (S11, S4), the v3.1 reading becomes
  "supports H-carried".
- **The two products without observation-based level control show what H-epoch predicts:**
  - slopes near −1;
  - a mean bias of about minus the mean offset.

  Whether they also carry a uniform level (H-uniform) is not separable here: the answer depends
  on whether the model carries the seasonal cycle (A2).
- **The bias-corrected 2D output carries present-day level by construction.**

### 2.8 Post hoc, not pre-registered: one high-leverage station

**The station.** 8764044 Berwick (Atchafalaya River) has X = −0.45 m.
- That value is driven by river stage: its seasonal anomaly is −0.26 m and its 12-month level
  −0.19 m.
- It is the only station with X < 0 in the primary set.
- The pre-registered Theil–Sen slope (−0.22, against OLS −0.01) already signals its influence.

**Without it** (`results/study2/posthoc_leverage.json`):

| analysis | slope [95% CI] | verdict |
|---|---|---|
| 3D v3.1 | −0.16 [−0.66, +0.29] | still inconclusive |
| 3D v2.1 | −0.82 [−1.13, −0.53] | H-epoch |
| 2D uncorrected | −1.08 [−1.33, −0.86] | H-epoch |

This is reported for transparency and changes no frozen result.

---

## 3. Study 3: decomposition of the Boston error (2026-10-30 12z, window (0, 48] h)

`results/study3/boston_decomposition.json`; archived Boston files only.

| quantity | value |
|---|---|
| n | 480 |
| best lag, 0.1-min grid (cubic spline) | model **late by 14.0 min** |
| best lag, 6-min grid / parabolic vertex | 12 min / 13.97 min (model late) |
| RMSE, raw | 0.2456 m |
| after removing the mean only | 0.1996 m |
| after removing the best lag only | 0.2049 m |
| after removing the amplitude scale only (α = 0.881) | 0.2000 m |
| after mean + lag | 0.1522 m |
| after mean + lag + amplitude (α = 0.889) | 0.0756 m |
| quality flags of the 480 matched observations | 110 O (1-s samples outside 3σ), 0 F, 0 R, 0 L |
| Table 3 with the 110 flagged observations removed (n = 370) | bias −0.1390, RMSE 0.2403, MAE 0.2044, max \|e\| 0.511 m, r 0.9885, σM/σO 1.133 |
| Table 3, all 480 (check) | bias −0.1430, RMSE 0.2456, MAE 0.2086 m, r 0.9913 (as published) |

How the RMSE is made up:
- **The mean (−0.143 m)** accounts for 34% of the MSE.
- **The 14-minute lag and the 11–12% excess amplitude** together account for most of the rest.
- **What remains** after all three is 7.6 cm.
- **Removing the flagged observations** changes the bias by 4 mm.

---

## 4. Amendments and deviations

Full text and evidence in `AMENDMENTS.md`.

- **A1–A4** (author, before any sampled download; `8a7318d`): datum consistency and S10;
  seasonal separability; spin-up S11 and the per-cycle table; the Boston table.
- **A5** (after download, before any classification or session): CO-OPS's second
  unpublished-datum wording, "There is no MSL for the station". Without it, classification
  would have stopped at those cases. Under the frozen rule those 465 cases have no result; under
  A5 they are "not eligible".
- **A6** (same timing): masters with a trailing "disclaimers" key. 3 of 2,293 masters could not
  be sliced by the WP1 serializer.
- **Implementation notes N1–N5:** plotting, memory, lag-sign label, grid fetch, report parser.
  None changes a rule or a result.
- **Pre-freeze review:** DESIGN.md §13.
- **Post hoc, clearly labelled:** §2.8 only.
- **Operational:**
  - The controlling session crashed twice while jobs ran in parallel; the second crash took WSL
    down with it. Partial outputs were deleted and rerun.
  - Every session and classification in the results ran to completion. The final runs were
    strictly serial at low priority.
  - The run-time projection after the first 2D 0.3.0 session was 0.36 s per call, 3.1 h serial
    (`run_log/runtime_projection.json`). The serial sessions took 2.2 h.

## 5. What ran through real MCP sessions and what did not

**Through real MCP stdio sessions** (replay mode, inside `unshare -rn`, mcp 1.30.0, CPython
3.13.12):

| package | identity | sessions | calls |
|---|---|---:|---:|
| stofs-mcp 0.3.0 post-fix | wheel `ba4edc2e…be9a` | 60 | 15,197 |
| stofs-mcp 0.2.0 | PyPI | 60 | 15,197 |
| coops-mcp 0.1.1 | PyPI | 1 | 389 |

- **Validity:** all 121 sessions are valid, with 0 misses, 0 blocked attempts and 61,042 replayed
  requests.
- **Replay rules used:**
  - WP1 slicing;
  - 4b no-data: 9,164 times;
  - 4a and A5 unpublished datum: 1,410;
  - 5 empty slice: 11.
- **Live validation:** six byte-identical live checks (`run_log/rule_validation.json`).
- **Transcripts:** `run_log/sessions/*/*/transcript.json.gz`, with checksums in
  `run_log/sessions_manifest.json`.

**Not through MCP** (reference code only, no Ocean-MCP import):
- the reference classification and statistics;
- the 2D `noanomaly` analysis, which the tool does not serve;
- Study 2, Study 3 and A1.

**Not run:**
- the human check itself: the package is prepared, but no colleague has classified it;
- a full `./run_all.sh` repeat from scratch after the crashes. Every step was run individually,
  in the order the script uses.

## 6. Requests, preservation and restrictions

**NOAA requests:**
- **Phase 0:** 483.
- **Phase 2:** 4,006 downloads plus 6 live rule checks, a total of 4,012 against the cap of
  4,298.
- **Retries and errors:** one retry (a 504), no error.
- **Gaps between requests:** sequential, at least 1.2 s apart.
- **Records:** every request is in `run_log/noaa_requests.jsonl` with its URL, UTC times and
  SHA-256.

**Non-NOAA downloads:**
- PyPI packages;
- the GEOID18 grid from cdn.proj.org (logged);
- three documentation files (`phase0/docs/nonnoaa/sources.jsonl`).

**Preservation.** Checked before commit and repeated in the final message:
- no existing branch or worktree changed;
- nothing was pushed, pulled, fetched, merged, rebased, tagged or published;
- server source and tests are unchanged.

## 7. Limitations

- **One author and assistant.**
  - The same author and assistant wrote the tool's fixes, the reference rules, the grader, the
    design and this report.
  - The reference rules come from the same reading of the documentation as the tool's.
  - The designer had read the tool's source, including its 50 m bound and refusal messages, and
    the grader's reason patterns use those messages.
  - The only outside check of the design was the pre-freeze review by a separate assistant
    session. The human check is prepared, not done.
- **The documentation decides what "correct" means.** For a datum, "correct" means what NOAA
  documentation and the file's labels say. Where both are wrong, the reference is wrong too.
  - The boundary-station list comes from code version v3.1.7; the sampled files name v3.1.4 to
    v3.1.7.
- **Preliminary observations:** 931 of the 9,949 cases with pairs contain preliminary paired
  observations. S7 restricts Study 2 to verified data.
- **Stations are not independent.** They share weather, boundary forcing and regional sea-level
  anomalies; the cluster bootstrap addresses part of this.
  - The primary fit is sensitive to one riverine station (§2.8).
  - The cross-station spread of X is modest: SD 0.07 m in the 3D domain.
- **Seasonal correction.** It assumes the 2016–2025 seasonal cycle applies in 2026. A2 shows the
  H-epoch/H-uniform distinction depends on it.
- **What the sampling rule leaves out:**
  - other products: gridded, SHEF, `autoval`, `htp`, `swl`, `temp.salt.vel`;
  - December–May;
  - 2D cycles other than 12z;
  - nowcast segments;
  - STOFS-3D-Pacific.
- **Replay** serves bodies with minimal headers; timeouts and retries are not exercised.

## 8. human_check

`human_check/`:
- **The cases:** 30 station-cycles drawn by the frozen rule (seed 20261109; 20 random and 10
  non-routine, shuffled).
- **For each case:**
  - a plot of the raw model series and the observed series, on MSL and on NAVD where available,
    with no statistic shown;
  - a text file with the file's datum attributes and the station's CO-OPS datums and epoch.
- **Sealed:** the tool's and the reference's outcomes are in `SEALED_outcomes.json`
  (SHA-256 `fadff751ba8a0c5d37f139e44239719f83274fd1d481f77637028afab633a9e7`).
- **Form:** the colleague fills in `classification_form.csv` before opening the sealed file.
- **Draw result:** the 10 non-routine draws are all not-eligible cases, since the non-routine
  pool is mostly those. The 20 random draws are 11 comparisons and 9 not eligible.

## 9. Proposed manuscript text (≤ 200 words), table and figure

See `MANUSCRIPT_TEXT.md`.

## 10. Repeat everything offline

`./run_all.sh` (sessions take about 2.2 h, run serially); `SESSIONS=skip ./run_all.sh` reuses
the archived transcripts and redoes all analysis. Inputs are only the archives under
`data/archive/`, the VDatum grids under `data/raw/vdatum_grids/` and the WP1 archive for the
self-test.

---

## Appendix A. Per-station table, STOFS-3D-Atlantic v3.1 (post-transition), all stations entering

Bias = mean over cycles of the window-mean error. X = O12_pre + S. O12 and O29 are the
brief's two estimates. The last column is the 3D v2.1 (NAVD vs NAVD) mean bias.

| station | name | epoch | boundary | cycles | bias mean (m) | bias SD | model mean | obs mean | X = O12_pre+S | O12 (brief) | O29 (brief) | S | pre-transition bias (NAVD) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8410140 | Eastport | NTDE |  | 15 | -0.046 | +0.028 | +0.081 | +0.127 | +0.142 | +0.143 | +0.148 | +0.001 | -0.228 |
| 8411060 | Cutler Farris Wharf | NTDE |  | 15 | -0.077 | +0.027 | +0.072 | +0.149 | +0.135 | +0.131 | +0.164 | +0.005 | -0.173 |
| 8413320 | Bar Harbor | NTDE |  | 15 | -0.081 | +0.026 | +0.069 | +0.149 | +0.147 | +0.134 | +0.165 | +0.015 | — |
| 8418150 | Portland | NTDE |  | 15 | -0.049 | +0.024 | +0.082 | +0.131 | +0.130 | +0.107 | +0.145 | +0.023 | -0.120 |
| 8443970 | Boston | NTDE |  | 15 | -0.059 | +0.026 | +0.124 | +0.183 | +0.170 | +0.144 | +0.198 | +0.028 | -0.143 |
| 8447386 | Fall River | NTDE |  | 14 | -0.087 | +0.025 | +0.134 | +0.221 | +0.206 | +0.155 | +0.234 | +0.052 | -0.135 |
| 8447435 | Chatham | NTDE |  | 15 | -0.117 | +0.030 | +0.019 | +0.136 | — | — | +0.161 | +0.020 | -0.220 |
| 8447930 | Woods Hole | NTDE |  | 15 | -0.097 | +0.024 | +0.138 | +0.235 | +0.221 | +0.168 | +0.243 | +0.053 | -0.154 |
| 8449130 | Nantucket Island | NTDE |  | 15 | -0.112 | +0.024 | +0.121 | +0.233 | +0.216 | +0.176 | +0.245 | +0.042 | — |
| 8452660 | Newport | NTDE | yes | 15 | -0.068 | +0.022 | +0.153 | +0.222 | +0.200 | +0.145 | +0.228 | +0.056 | -0.119 |
| 8452944 | Conimicut Light | NTDE |  | 15 | -0.054 | +0.023 | +0.150 | +0.204 | +0.186 | +0.134 | +0.211 | +0.052 | — |
| 8454000 | Providence | NTDE |  | 15 | -0.065 | +0.027 | +0.138 | +0.203 | +0.194 | +0.142 | +0.206 | +0.052 | -0.120 |
| 8461490 | New London | NTDE |  | 15 | -0.103 | +0.025 | +0.128 | +0.231 | +0.202 | +0.152 | +0.242 | +0.051 | -0.180 |
| 8465705 | New Haven | NTDE |  | 15 | -0.060 | +0.023 | +0.145 | +0.206 | +0.178 | +0.113 | +0.220 | +0.065 | — |
| 8467150 | Bridgeport | NTDE |  | 15 | -0.101 | +0.023 | +0.132 | +0.233 | +0.200 | +0.135 | +0.248 | +0.065 | -0.174 |
| 8510560 | Montauk | NTDE |  | 15 | -0.096 | +0.022 | +0.146 | +0.241 | +0.213 | +0.154 | +0.250 | +0.060 | -0.166 |
| 8516945 | Kings Point | NTDE |  | 15 | -0.066 | +0.025 | +0.182 | +0.248 | +0.208 | +0.138 | +0.264 | +0.071 | -0.151 |
| 8518750 | The Battery | NTDE |  | 15 | -0.074 | +0.027 | +0.161 | +0.234 | +0.201 | +0.123 | +0.243 | +0.075 | -0.162 |
| 8518962 | Turkey Point Hudson River NERRS | NTDE |  | 15 | -0.099 | +0.034 | +0.083 | +0.182 | +0.183 | +0.131 | +0.210 | +0.051 | — |
| 8531680 | Sandy Hook | NTDE | yes | 15 | -0.099 | +0.024 | +0.190 | +0.289 | +0.242 | +0.169 | +0.297 | +0.072 | -0.202 |
| 8534720 | Atlantic City | NTDE | yes | 15 | -0.165 | +0.025 | +0.150 | +0.315 | +0.255 | +0.166 | +0.311 | +0.086 | -0.194 |
| 8536110 | Cape May | NTDE | yes | 15 | -0.078 | +0.028 | +0.239 | +0.317 | +0.277 | +0.188 | +0.320 | +0.084 | -0.192 |
| 8537121 | Ship John Shoal | NTDE |  | 15 | -0.198 | +0.029 | +0.129 | +0.326 | +0.303 | +0.206 | +0.343 | +0.092 | — |
| 8539094 | Burlington, Delaware River | NTDE |  | 15 | -0.098 | +0.035 | +0.097 | +0.195 | +0.144 | +0.085 | +0.223 | +0.060 | — |
| 8540433 | Marcus Hook | NTDE |  | 15 | -0.125 | +0.032 | +0.119 | +0.244 | +0.217 | +0.132 | +0.272 | +0.084 | -0.177 |
| 8545240 | Philadelphia | NTDE |  | 15 | -0.158 | +0.042 | +0.055 | +0.213 | +0.192 | +0.109 | +0.247 | +0.080 | -0.206 |
| 8546252 | Bridesburg | NTDE |  | 15 | -0.103 | +0.030 | +0.109 | +0.212 | +0.171 | +0.101 | +0.241 | +0.069 | — |
| 8548989 | Newbold | NTDE |  | 15 | -0.093 | +0.040 | +0.097 | +0.190 | +0.130 | +0.078 | +0.216 | +0.053 | — |
| 8551762 | Delaware City | NTDE |  | 15 | -0.097 | +0.027 | +0.138 | +0.236 | +0.217 | +0.118 | +0.261 | +0.096 | — |
| 8555889 | Brandywine Shoal Light | NTDE |  | 15 | -0.105 | +0.028 | +0.192 | +0.298 | +0.257 | +0.168 | +0.302 | +0.085 | — |
| 8557380 | Lewes | NTDE | yes | 15 | -0.099 | +0.031 | +0.214 | +0.312 | +0.264 | +0.174 | +0.315 | +0.086 | -0.209 |
| 8570283 | Ocean City Inlet | NTDE |  | 15 | -0.086 | +0.035 | +0.221 | +0.307 | +0.272 | +0.180 | +0.310 | +0.086 | -0.194 |
| 8571421 | Bishops Head | NTDE |  | 15 | -0.144 | +0.041 | +0.125 | +0.270 | +0.256 | +0.160 | +0.285 | +0.091 | -0.216 |
| 8571892 | Cambridge | NTDE |  | 15 | -0.100 | +0.036 | +0.140 | +0.240 | +0.227 | +0.138 | +0.256 | +0.085 | -0.198 |
| 8573364 | Tolchester Beach | NTDE |  | 15 | -0.150 | +0.047 | +0.087 | +0.237 | +0.233 | +0.143 | +0.258 | +0.086 | -0.179 |
| 8573927 | Chesapeake City | NTDE |  | 15 | -0.102 | +0.044 | +0.132 | +0.234 | +0.230 | +0.144 | +0.259 | +0.083 | -0.116 |
| 8574680 | Baltimore | NTDE |  | 15 | -0.169 | +0.041 | +0.081 | +0.250 | +0.238 | +0.142 | +0.270 | +0.093 | -0.199 |
| 8575512 | Annapolis | NTDE |  | 15 | -0.113 | +0.039 | +0.159 | +0.272 | +0.264 | +0.166 | +0.289 | +0.094 | -0.226 |
| 8577330 | Solomons Island | NTDE |  | 13 | -0.093 | +0.033 | +0.165 | +0.258 | +0.252 | +0.165 | +0.267 | +0.082 | -0.226 |
| 8594900 | Washington | NTDE |  | 15 | -0.163 | +0.035 | +0.073 | +0.236 | +0.208 | +0.121 | +0.250 | +0.081 | -0.210 |
| 8631044 | Wachapreague | NTDE |  | 15 | -0.105 | +0.036 | +0.212 | +0.317 | +0.279 | +0.179 | +0.319 | +0.093 | — |
| 8632200 | Kiptopeke | NTDE | yes | 15 | -0.100 | +0.031 | +0.161 | +0.261 | +0.229 | +0.132 | +0.261 | +0.090 | -0.057 |
| 8635027 | Dahlgren | NTDE |  | 15 | -0.022 | +0.035 | +0.292 | +0.314 | +0.290 | +0.191 | +0.328 | +0.093 | -0.231 |
| 8635750 | Lewisetta | NTDE |  | 15 | -0.138 | +0.027 | +0.190 | +0.328 | +0.300 | +0.200 | +0.338 | +0.095 | -0.298 |
| 8636580 | Windmill Point | NTDE |  | 15 | -0.084 | +0.027 | +0.242 | +0.326 | +0.296 | +0.198 | +0.333 | +0.091 | -0.213 |
| 8637689 | Yorktown USCG Training Center | NTDE |  | 15 | -0.096 | +0.029 | +0.197 | +0.292 | +0.260 | +0.158 | +0.292 | +0.094 | -0.206 |
| 8638610 | Sewells Point | NTDE |  | 15 | -0.129 | +0.038 | +0.162 | +0.291 | +0.266 | +0.165 | +0.289 | +0.090 | -0.214 |
| 8638901 | CBBT, Chesapeake Channel | NTDE |  | 15 | -0.079 | +0.037 | +0.182 | +0.261 | +0.233 | +0.138 | +0.258 | +0.085 | — |
| 8639348 | Money Point | NTDE |  | 15 | -0.117 | +0.038 | +0.189 | +0.306 | +0.265 | +0.169 | +0.305 | +0.088 | — |
| 8651370 | Duck | NTDE | yes | 15 | -0.101 | +0.044 | +0.184 | +0.285 | +0.250 | +0.150 | +0.275 | +0.089 | -0.224 |
| 8652587 | Oregon Inlet Marina | NTDE |  | 15 | -0.057 | +0.040 | +0.174 | +0.231 | +0.215 | +0.147 | +0.246 | +0.066 | -0.157 |
| 8654467 | USCG Station Hatteras | NTDE |  | 15 | -0.045 | +0.027 | +0.202 | +0.247 | +0.214 | +0.133 | +0.234 | +0.070 | -0.152 |
| 8656483 | Beaufort, Duke Marine Lab | NTDE |  | 15 | +0.050 | +0.058 | +0.318 | +0.268 | +0.239 | +0.144 | +0.252 | +0.087 | -0.048 |
| 8658120 | Wilmington | NTDE |  | 15 | +0.060 | +0.048 | +0.271 | +0.211 | +0.194 | +0.101 | +0.203 | +0.084 | -0.088 |
| 8658163 | Wrightsville Beach | NTDE | yes | 15 | +0.041 | +0.057 | +0.354 | +0.313 | +0.275 | +0.169 | +0.283 | +0.097 | -0.115 |
| 8661070 | Springmaid Pier | NTDE | yes | 15 | +0.054 | +0.054 | +0.333 | +0.279 | +0.239 | +0.131 | +0.241 | +0.099 | -0.120 |
| 8665530 | Charleston | NTDE | yes | 15 | +0.064 | +0.053 | +0.364 | +0.300 | +0.255 | +0.145 | +0.263 | +0.099 | -0.090 |
| 8670870 | Fort Pulaski | NTDE | yes | 15 | +0.007 | +0.052 | +0.335 | +0.328 | +0.280 | +0.163 | +0.287 | +0.104 | -0.132 |
| 8679598 | Kings Bay MSF Pier | NTDE |  | 15 | +0.100 | +0.047 | +0.386 | +0.286 | — | +0.114 | +0.251 | — | — |
| 8720030 | Fernandina Beach | NTDE |  | 15 | +0.087 | +0.048 | +0.374 | +0.287 | +0.239 | +0.119 | +0.251 | +0.107 | -0.065 |
| 8720218 | Mayport (Bar Pilots Dock) | NTDE |  | 15 | +0.078 | +0.040 | +0.343 | +0.266 | +0.221 | +0.098 | +0.228 | +0.110 | -0.068 |
| 8720219 | Dames Point | NTDE |  | 15 | +0.115 | +0.039 | +0.391 | +0.277 | +0.240 | +0.108 | +0.243 | +0.119 | -0.049 |
| 8720226 | Southbank Riverwalk, St Johns River | NTDE |  | 15 | +0.158 | +0.040 | +0.409 | +0.252 | +0.227 | +0.094 | +0.221 | +0.119 | -0.062 |
| 8721604 | Trident Pier, Port Canaveral | NTDE |  | 15 | +0.055 | +0.041 | +0.355 | +0.300 | +0.254 | +0.159 | +0.262 | +0.084 | -0.061 |
| 8722670 | Lake Worth Pier, Atlantic Ocean | NTDE |  | 15 | +0.036 | +0.071 | +0.305 | +0.269 | +0.239 | +0.155 | +0.243 | +0.078 | -0.054 |
| 8722956 | South Port Everglades | NTDE |  | 15 | +0.006 | +0.065 | +0.259 | +0.252 | +0.233 | +0.139 | +0.230 | +0.087 | -0.058 |
| 8723214 | Virginia Key | NTDE |  | 15 | +0.030 | +0.057 | +0.304 | +0.274 | +0.256 | +0.168 | +0.256 | +0.082 | -0.029 |
| 8723970 | Vaca Key, Florida Bay | NTDE |  | 15 | +0.057 | +0.054 | +0.323 | +0.266 | +0.237 | +0.154 | +0.257 | +0.081 | +0.017 |
| 8724580 | Key West | NTDE |  | 15 | +0.068 | +0.050 | +0.325 | +0.257 | +0.219 | +0.135 | +0.251 | +0.083 | +0.044 |
| 8725114 | Naples Bay, North | NTDE |  | 15 | +0.044 | +0.050 | +0.267 | +0.223 | — | +0.121 | +0.229 | — | — |
| 8725520 | Fort Myers | NTDE |  | 15 | +0.076 | +0.048 | +0.292 | +0.216 | +0.216 | +0.119 | +0.222 | +0.093 | +0.016 |
| 8726384 | Port Manatee | NTDE |  | 15 | +0.067 | +0.055 | +0.299 | +0.232 | +0.230 | +0.136 | +0.238 | +0.091 | -0.011 |
| 8726520 | St. Petersburg | NTDE |  | 15 | +0.094 | +0.055 | +0.298 | +0.205 | +0.204 | +0.114 | +0.213 | +0.088 | -0.018 |
| 8726607 | Old Port Tampa | NTDE |  | 15 | +0.082 | +0.056 | +0.298 | +0.217 | +0.218 | +0.126 | +0.226 | +0.090 | +0.006 |
| 8726724 | Clearwater Beach | NTDE |  | 15 | +0.090 | +0.052 | +0.332 | +0.242 | +0.243 | +0.147 | +0.247 | +0.094 | -0.013 |
| 8727520 | Cedar Key | NTDE |  | 15 | +0.039 | +0.068 | +0.254 | +0.216 | +0.223 | +0.126 | +0.234 | +0.096 | -0.037 |
| 8728690 | Apalachicola | NTDE |  | 15 | +0.106 | +0.058 | +0.285 | +0.179 | +0.202 | +0.101 | +0.195 | +0.096 | +0.023 |
| 8729108 | Panama City | NTDE |  | 15 | +0.119 | +0.042 | +0.331 | +0.212 | +0.210 | +0.107 | +0.223 | +0.101 | +0.026 |
| 8729210 | Panama City Beach | NTDE |  | 15 | +0.055 | +0.042 | +0.291 | +0.236 | +0.228 | +0.123 | +0.250 | +0.104 | -0.030 |
| 8729840 | Pensacola | NTDE |  | 15 | +0.050 | +0.043 | +0.294 | +0.244 | +0.240 | +0.137 | +0.257 | +0.100 | -0.075 |
| 8735180 | Dauphin Island | NTDE |  | 15 | +0.078 | +0.047 | +0.286 | +0.209 | +0.213 | +0.120 | +0.221 | +0.089 | -0.038 |
| 8735391 | Dog River Bridge | NTDE |  | 15 | +0.100 | +0.052 | +0.323 | +0.223 | +0.216 | +0.133 | +0.227 | +0.079 | — |
| 8735523 | East Fowl River Bridge | NTDE |  | 15 | +0.085 | +0.048 | +0.322 | +0.237 | +0.235 | +0.147 | +0.246 | +0.084 | — |
| 8736897 | Coast Guard Sector Mobile | NTDE |  | 15 | +0.055 | +0.053 | +0.289 | +0.234 | +0.228 | +0.139 | +0.236 | +0.084 | -0.070 |
| 8737048 | Mobile State Docks | NTDE |  | 15 | +0.092 | +0.052 | +0.278 | +0.187 | +0.180 | +0.116 | +0.189 | +0.061 | -0.013 |
| 8737138 | Chickasaw Creek | NTDE |  | 15 | +0.110 | +0.046 | +0.291 | +0.181 | +0.171 | +0.116 | +0.183 | +0.052 | +0.085 |
| 8738043 | West Fowl River Bridge | NTDE |  | 15 | +0.086 | +0.049 | +0.316 | +0.230 | +0.222 | +0.130 | +0.238 | +0.088 | — |
| 8739803 | Bayou La Batre Bridge | NTDE |  | 15 | +0.077 | +0.051 | +0.305 | +0.228 | +0.235 | +0.141 | +0.238 | +0.090 | — |
| 8747437 | Bay Waveland Yacht Club | NTDE |  | 15 | +0.108 | +0.053 | +0.304 | +0.196 | +0.217 | +0.116 | +0.214 | +0.094 | -0.005 |
| 8760721 | Pilottown | modified |  | 15 | +0.049 | +0.049 | +0.009 | -0.040 | -0.123 | -0.107 | -0.020 | -0.021 | — |
| 8760922 | Pilots Station East, S.W. Pass | modified |  | 15 | -0.246 | +0.054 | +0.159 | +0.404 | +0.388 | +0.323 | +0.419 | +0.061 | — |
| 8761305 | Shell Beach | NTDE |  | 15 | -0.130 | +0.054 | +0.100 | +0.230 | +0.261 | +0.152 | +0.258 | +0.098 | -0.087 |
| 8761724 | Grand Isle | modified |  | 15 | +0.181 | +0.050 | +0.318 | +0.137 | +0.157 | +0.060 | +0.149 | +0.090 | — |
| 8761927 | New Canal Station | NTDE |  | 15 | +0.205 | +0.049 | +0.373 | +0.168 | +0.227 | +0.121 | +0.197 | +0.094 | +0.058 |
| 8764044 | Berwick, Atchafalaya River | NTDE |  | 15 | -0.039 | +0.056 | -0.228 | -0.189 | -0.447 | -0.198 | -0.187 | -0.256 | +0.048 |
| 8764227 | LAWMA, Amerada Pass | NTDE |  | 15 | +0.039 | +0.048 | +0.257 | +0.219 | +0.184 | +0.151 | +0.219 | +0.027 | -0.076 |
| 8764314 | Eugene Island, North of, Atchafalaya Bay | NTDE |  | 15 | -0.060 | +0.047 | +0.264 | +0.324 | +0.244 | +0.179 | +0.326 | +0.067 | — |
| 8766072 | Freshwater Canal Locks | NTDE |  | 15 | +0.081 | +0.043 | +0.305 | +0.224 | +0.219 | +0.133 | +0.225 | +0.078 | -0.170 |
| 8767816 | Lake Charles | NTDE |  | 15 | +0.139 | +0.043 | +0.316 | +0.177 | +0.174 | +0.109 | +0.165 | +0.060 | -0.047 |
| 8767961 | Bulk Terminal | NTDE |  | 15 | +0.099 | +0.044 | +0.316 | +0.216 | +0.196 | +0.129 | +0.205 | +0.062 | -0.082 |
| 8768094 | Calcasieu Pass | NTDE |  | 15 | +0.113 | +0.042 | +0.308 | +0.195 | +0.195 | +0.106 | +0.191 | +0.082 | -0.039 |
| 8770475 | Port Arthur | NTDE |  | 15 | +0.090 | +0.041 | +0.294 | +0.204 | +0.185 | +0.119 | +0.199 | +0.059 | -0.042 |
| 8770520 | Rainbow Bridge | NTDE |  | 15 | +0.092 | +0.035 | +0.299 | +0.207 | +0.170 | +0.118 | +0.199 | +0.045 | +0.002 |
| 8770613 | Morgans Point, Barbours Cut | NTDE |  | 15 | +0.098 | +0.042 | +0.258 | +0.160 | +0.164 | +0.087 | +0.158 | +0.071 | -0.048 |
| 8770777 | Manchester | NTDE |  | 15 | +0.053 | +0.042 | +0.212 | +0.159 | +0.164 | +0.077 | +0.160 | +0.082 | -0.062 |
| 8770808 | High Island | NTDE |  | 15 | +0.085 | +0.031 | +0.394 | +0.309 | +0.298 | +0.211 | +0.297 | +0.081 | -0.030 |
| 8770822 | Texas Point, Sabine Pass | NTDE |  | 15 | +0.054 | +0.042 | +0.279 | +0.225 | +0.215 | +0.125 | +0.224 | +0.082 | -0.123 |
| 8770971 | Rollover Pass | NTDE |  | 15 | +0.084 | +0.034 | +0.410 | +0.325 | +0.310 | +0.228 | +0.314 | +0.075 | -0.048 |
| 8771013 | Eagle Point, Galveston Bay | NTDE |  | 15 | +0.095 | +0.042 | +0.350 | +0.254 | +0.264 | +0.182 | +0.255 | +0.074 | — |
| 8771341 | Galveston Bay Entrance, North Jetty | NTDE |  | 15 | +0.069 | +0.042 | +0.281 | +0.212 | +0.281 | +0.184 | +0.212 | +0.084 | -0.116 |
| 8771450 | Galveston Pier 21 | NTDE |  | 15 | +0.093 | +0.043 | +0.293 | +0.200 | +0.213 | +0.124 | +0.200 | +0.082 | -0.052 |
| 8771486 | Galveston Railroad Bridge | NTDE |  | 14 | +0.075 | +0.045 | +0.286 | +0.210 | — | — | +0.223 | +0.078 | -0.044 |
| 8771972 | San Luis Pass | NTDE |  | 14 | +0.072 | +0.062 | +0.276 | +0.204 | +0.207 | +0.139 | +0.206 | +0.059 | -0.063 |
| 8772471 | Freeport Harbor | NTDE |  | 15 | +0.101 | +0.041 | +0.345 | +0.243 | +0.253 | +0.172 | +0.240 | +0.073 | — |
| 8772985 | Sargent | NTDE |  | 15 | +0.082 | +0.037 | +0.263 | +0.181 | +0.192 | +0.107 | +0.170 | +0.077 | — |
| 8773037 | Seadrift | modified |  | 15 | +0.083 | +0.029 | +0.259 | +0.176 | +0.188 | +0.113 | +0.166 | +0.066 | -0.083 |
| 8773146 | Matagorda City | NTDE |  | 15 | +0.079 | +0.030 | +0.277 | +0.197 | +0.202 | +0.121 | +0.189 | +0.073 | — |
| 8773259 | Port Lavaca | modified |  | 15 | +0.190 | +0.034 | +0.384 | +0.194 | +0.186 | +0.106 | +0.187 | +0.075 | — |
| 8773701 | Port O'Connor | modified |  | 15 | +0.086 | +0.033 | +0.276 | +0.190 | +0.194 | +0.115 | +0.181 | +0.072 | -0.094 |
| 8773767 | Matagorda Bay Entrance Channel | NTDE |  | 15 | +0.136 | +0.040 | +0.349 | +0.213 | +0.212 | +0.136 | +0.204 | +0.071 | -0.044 |
| 8774230 | Aransas Wildlife Refuge | modified |  | 6 | +0.066 | +0.036 | +0.435 | +0.369 | — | — | — | +0.151 | — |
| 8774770 | Rockport | modified |  | 15 | +0.137 | +0.027 | +0.331 | +0.195 | +0.188 | +0.128 | +0.182 | +0.055 | -0.187 |
| 8775237 | Port Aransas | NTDE |  | 15 | +0.027 | +0.035 | +0.241 | +0.213 | +0.219 | +0.141 | +0.203 | +0.070 | -0.114 |
| 8775241 | Aransas, Aransas Pass | NTDE |  | 15 | +0.115 | +0.040 | +0.329 | +0.214 | +0.224 | +0.156 | +0.205 | +0.065 | -0.034 |
| 8775296 | USS Lexington, Corpus Christi Bay | modified |  | 15 | +0.067 | +0.037 | +0.225 | +0.159 | +0.165 | +0.094 | +0.148 | +0.063 | -0.098 |
| 8775792 | Packery Channel | NTDE |  | 15 | +0.104 | +0.039 | +0.295 | +0.190 | +0.194 | +0.130 | +0.175 | +0.057 | -0.112 |
| 8775870 | Bob Hall Pier, Corpus Christi | NTDE |  | 8 | +0.061 | +0.054 | +0.339 | +0.279 | — | — | +0.298 | +0.160 | — |
| 8779280 | Realitos Peninsula | NTDE |  | 15 | +0.035 | +0.047 | +0.312 | +0.277 | +0.256 | +0.202 | +0.259 | +0.050 | — |
| 8779748 | South Padre Island CG Station | NTDE |  | 15 | +0.016 | +0.040 | +0.240 | +0.224 | +0.222 | +0.150 | +0.212 | +0.065 | -0.143 |
| 8779749 | SPI Brazos Santiago | NTDE |  | 15 | +0.106 | +0.040 | +0.306 | +0.199 | +0.199 | +0.129 | +0.188 | +0.063 | -0.042 |
| 8779770 | Port Isabel | NTDE |  | 15 | -0.015 | +0.044 | +0.211 | +0.226 | +0.222 | +0.151 | +0.215 | +0.065 | -0.178 |
| 9751639 | Charlotte Amalie | NTDE |  | 15 | -0.146 | +0.044 | +0.047 | +0.193 | +0.159 | +0.118 | +0.199 | +0.046 | — |
| 9755371 | San Juan, La Puntilla, San Juan Bay | NTDE |  | 15 | -0.120 | +0.052 | +0.080 | +0.200 | +0.163 | +0.121 | +0.201 | +0.046 | — |
| 9759110 | Magueyes Island | NTDE |  | 10 | +0.199 | +0.043 | +0.409 | +0.210 | +0.175 | +0.141 | +0.227 | +0.038 | — |
| 9759394 | Mayaguez | NTDE |  | 15 | -0.143 | +0.045 | +0.079 | +0.222 | +0.194 | +0.155 | +0.232 | +0.045 | — |
| 9759938 | Mona Island | NTDE |  | 15 | -0.179 | +0.046 | +0.033 | +0.212 | +0.175 | +0.138 | +0.224 | +0.042 | — |
