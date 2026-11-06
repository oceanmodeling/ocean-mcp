# WP1: scientific-safeguards comparison: report

Run on 2026-11-06, on branch `eval/safeguards-comparison` (local only), in worktree
`.claude/worktrees/safeguards-comparison`.

| Step | Commit |
|---|---|
| Design freeze | `5d84c13` |
| Arms A and B | `96fd7f8` |
| Phase 2 start and amendment A2 | `53d0f3f` |
| This report | the commit that adds this file |

The design is in `DESIGN.md`. Amendments are in `references/AMENDMENTS.md`.

## Summary

- **The validated Python workflow (arm B) and Ocean-MCP 0.3.0 (arm C) agree.**
  - **Values:** arm C ran 17 of the 18 rows and returned every value within tolerance.
  - **Decisions:** they agree on 16 of those 17 rows when the outputs are read plainly. Under the
    frozen grader the count is 15, because of one grader artefact (§1.3).
  - **Where they differ:** on R6, arm C corrects reversed station coordinates silently. Arm B
    reports the correction.
- **What this means.** The contribution measured here is validated checks made reusable through
  MCP. These are not checks that a careful script cannot make.
- **Basic Python (arm A)** gets the nominal numbers right. It proceeds falsely in 11 of 18 rows.
- **The released stofs-mcp 0.2.0 (arm D)** proceeds falsely in 12 rows and refuses falsely in 1.
  Its comparison values for 10 rows come from nearest-equivalent calls. They are shown, but not
  scored.
- **No workflow refused the harmless label variant (S5).** Neither amendment changes this
  conclusion: A1 corrects one reference bug, and A2 is a lenient sensitivity grading.
- **Arms C and D ran as 35 real MCP stdio sessions.** All were valid: replay only, no network,
  0 misses. R7 arm C was not run, because no ww3-mcp 0.1.3 candidate existed (§7).
- **The comparison repeats offline byte for byte.** `./run_all.sh` regenerated every one of the 105
  result and reference files identically.

---

## 1. Per-task results

### 1.1 Three axes, every arm (primary grading)

The primary grading is the frozen references and the frozen grader. Each cell reads values / metadata / decision.

- `[A1: …]` marks the one cell that amendment A1 changes.
- Arm D's nearest-equivalent values are in the last column. They are **not scored**.
- The same data are in `results/table_per_task.{md,csv}`.

| Task | Class | Arm A (basic Python) | Arm B (validated Python) | Arm C (Ocean-MCP 0.3.0) | Arm D (stofs-mcp 0.2.0) | Arm D nearest-equivalent values (UNSCORED) |
|---|---|---|---|---|---|---|
| N1 | nominal | within / correct / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / incomplete / proceed, caveat MISSING | n 541, bias −0.0028, RMSE 0.1164, MAE 0.0912, r 0.9939 |
| N2 | nominal | within / WRONG / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / WRONG / FALSE PROCEED | n 721, bias −0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
| N3 | nominal | within / correct / correct proceed | within / correct / correct proceed | within / correct / correct proceed | within / correct / correct proceed | |
| N4 | nominal | within / correct / correct proceed | within / correct / correct proceed | within / incomplete / correct proceed | within / incomplete / correct proceed | |
| R1a | real defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / incomplete / correct proceed + caveat | OUTSIDE / WRONG / FALSE PROCEED | |
| R1b | real defect | n/a / correct / FALSE PROCEED | n/a / correct / correct refusal | n/a / n/a / correct refusal | n/a / WRONG / FALSE PROCEED | n 721, bias 9,999,999.3293 (×3), r NaN |
| R2 | real defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / incomplete / FALSE PROCEED (plain reading: correct proceed + caveat, §1.3) | OUTSIDE / incomplete / FALSE PROCEED | |
| R3 | real defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / incomplete / correct proceed + caveat | OUTSIDE / incomplete / FALSE PROCEED | |
| R4a | real defect | OUTSIDE / WRONG / FALSE PROCEED | within / correct / correct proceed | within / correct / correct proceed | not supported / incomplete / correct proceed | n 721, bias −0.1318, RMSE 0.2752, MAE 0.2198, r 0.9959 |
| R4b | real defect | within / WRONG / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / WRONG / FALSE PROCEED | n 721, bias +0.0473, RMSE 0.2276, MAE 0.194, r 0.9946 |
| R5 | real defect | n/a / correct / correct proceed + caveat | n/a / correct / correct proceed + caveat | n/a / incomplete / correct proceed + caveat | n/a / incomplete / proceed, caveat MISSING | |
| R6 | real defect | OUTSIDE / n/a / FALSE PROCEED | within / n/a / correct proceed + caveat | within / n/a / proceed, caveat MISSING | not returned / n/a / FALSE REFUSAL | |
| R7 | real defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | candidate not available (all axes) | OUTSIDE / incomplete / FALSE PROCEED | |
| S1 | synthetic | within / correct / FALSE PROCEED | not returned [A1: n/a] / correct / correct refusal | not returned [A1: n/a] / incomplete / correct refusal | not supported / WRONG / FALSE PROCEED | n 721, bias −0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
| S2 | synthetic | n/a / WRONG / FALSE PROCEED | n/a / correct / correct refusal | n/a / correct / correct refusal | n/a / WRONG / FALSE PROCEED | n 721, bias −0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
| S3 | synthetic | n/a / WRONG / FALSE PROCEED | n/a / correct / correct refusal | n/a / correct / correct refusal | n/a / WRONG / FALSE PROCEED | n 541, bias −0.0028, RMSE 0.1164, MAE 0.0912, r 0.9939 |
| S4 | synthetic | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / incomplete / FALSE PROCEED | n 539, bias/RMSE/MAE/r all NaN |
| S5 | synthetic | within / WRONG / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / WRONG / FALSE PROCEED | n 721, bias −0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |

The reference values, tolerances and sources are in `DESIGN.md` §4 and `references/references.json`.
The arms' returned numbers are in `results/table_per_task.csv`, column `returned_values`.

**Reading the arm A and arm D failures.**

- **R1a.** Both ranked the five Caribbean no-data stations first, at 9,999,999.4 to 9,999,999.6 m.
- **R1b.** Both computed a bias of about 9,999,999.33 m:
  - arm A against CO-OPS MSL;
  - arm D against NAVD, over its nearest-equivalent window.
- **R2.** Both returned a minimum of −99,998.6 m.
- **R3.** Both ranked SA816 first, at 136.2 m.
- **R7.**
  - Arm A returned 99.0 m.
  - Arm D also returned 99.0 m. Its subsample also shows WVHT 99.0 in 3,520 of 5,270 rows.
- **S4.** Arm A's statistics are NaN or Inf (n 480). Arm D's are NaN (n 539), and its JSON
  contains NaN tokens.
- **R4a and R4b.** Each arm uses one fixed pairing for both cycles, so each gets one of the two
  wrong:
  - **arm A** pairs LMSL with MSL. It is wrong on R4a (bias −0.2155 against the reference
    −0.1235) and right on R4b.
  - **arm D** pairs NAVD88 with NAVD. It is right on R4a and wrong on R4b. Its nearest-equivalent
    R4b bias is +0.047 m, against the reference −0.035 m.
- **R6.**
  - **Arm A** read `x` as longitude, as the attribute says, and chose Trident Pier, FL, 1,772 km
    away.
  - **Arm D** answered "No STOFS station found within 50.0 km".

### 1.2 Amendment A2: S2 and S3 under a lenient decision rule (sensitivity; frozen remains primary)

The lenient rule also accepts a proceed when three things hold:

- the conflict (S2) or the undocumented version (S3) is stated;
- the datum is attributed to documentation or labelled an assumption;
- the pairing is consistent.

| Task | Arm | Action | Decision, frozen | Decision, lenient | Metadata, frozen | Metadata, lenient |
|---|---|---|---|---|---|---|
| S2 | A | proceed | false proceed | false proceed | wrong | correct |
| S2 | B | refuse | correct refusal | correct refusal | correct | correct |
| S2 | C | refuse | correct refusal | correct refusal | correct | correct |
| S2 | D | proceed | false proceed | false proceed | wrong | wrong |
| S3 | A | proceed | false proceed | false proceed | wrong | correct |
| S3 | B | refuse | correct refusal | correct refusal | correct | correct |
| S3 | C | refuse | correct refusal | correct refusal | correct | correct |
| S3 | D | proceed | false proceed | false proceed | wrong | wrong |

- **No decision changes.** No workflow proceeded while stating the cause:
  - arms A and D proceeded silently;
  - arms B and C declined.

  The fact that the frozen "refuse only" rule coincides with stofs-mcp 0.3.0's behaviour does not
  drive any result.
- **Arm A's lenient metadata becomes "correct",** because its fixed pairing is attributed to
  documentation. Its decision stays false, because it never noticed the conflict.

Output: `results/sensitivity_A2.{md,csv,json}`.

### 1.3 Rows where a plain reading disagrees with the grader (grader not changed)

| Task | Arm | Axis | Grader | Plain reading | Why |
|---|---|---|---|---|---|
| R2 | C | decision | false proceed | correct proceed + caveat | See the explanation below the table |
| S1 | C | metadata | incomplete | correct | See the explanation below the table |

**R2, arm C.**

- **Cause.** The frozen `value_beyond_bound` predicate tests every numeric field in an answer's
  values. The frozen station adapter adds `n_values` (1,813) to those values, and 1,813 > 30 m, so
  the predicate fires.
- **The tool's actual output.**
  - It returned min −0.109 m, which is within tolerance.
  - It reported `excluded_model_records.sentinel = 47`, the reference count.

**S1, arm C.**

- **The tool's output.** The tool declined, stating that the vertical datum "could not be
  established".
- **Cause.** The adapter records this as datum `undetermined` with no source field. The frozen S1
  source rule asks for a source before it looks at the value.

Grades that are right but need context (`results/disagreements.md`):

- **R6, arm D: false refusal.** The question was answerable. 0.2.0 declined because it does not
  detect the reversed coordinates.
- **N1, arm D: caveat missing.** 0.2.0's JSON has no datum note. Its markdown, which was not
  requested, says "small systematic offsets (1–5 cm) are expected".
- **R4a, arm D: correct.** It is correct only because 0.2.0 hard-codes NAVD88 for STOFS-3D.
- **R7, arm D.**
  - ww3-mcp 0.1.2 returns every 10th of 52,692 rows.
  - The largest valid value in that subsample is 5.6 m, against 6.32 m for the year.
  - So a missing-value fix alone would not reach the reference value.

### 1.4 The exact text behind every decision grade

Appendix A lists all 72 decision grades with the text that triggered each. Where a grade was given
because something was absent, it gives the output's complete notes. Source:
`results/decision_evidence.{md,csv}`.

## 2. Counts per arm (18 rows each; no composite score)

Primary grading. Under A1, values `not returned` becomes `not applicable` for S1 in arms B and C;
nothing else changes. All tables are in `results/table_counts.{md,csv}`.

| Axis | Outcome | A | B | C | D |
|---|---|---:|---:|---:|---:|
| Values | within tolerance | 7 | 13 | 12 | 2 |
| | outside tolerance | 7 | 0 | 0 | 4 |
| | not returned | 0 | 1 (A1: 0) | 1 (A1: 0) | 1 |
| | not applicable | 4 | 4 (A1: 5) | 4 (A1: 5) | 4 |
| | **not supported** | 0 | 0 | 0 | **7** |
| | candidate not available | 0 | 0 | 1 | 0 |
| Metadata | correct | 11 | 17 | 9 | 1 |
| | incomplete | 0 | 0 | 6 | 8 |
| | wrong | 6 | 0 | 0 | 8 |
| | not applicable / candidate not available | 1 / 0 | 1 / 0 | 2 / 1 | 1 / 0 |
| Metadata, strict | correct / incomplete / wrong | 11 / 0 / 6 | 17 / 0 / 0 | 7 / 8 / 0 | 1 / 8 / 8 |
| Decision | correct proceed | 2 | 3 | 3 | 3 |
| | correct proceed with required caveat | 1 | 11 | 8 | 0 |
| | correct refusal naming the cause | 0 | 4 | 4 | 0 |
| | proceed, required caveat missing | 4 | 0 | 1 | 2 |
| | **false proceed** | **11** | **0** | **1** (plain reading 0) | **12** |
| | **false refusal** | **0** | **0** | **0** | **1** |
| | candidate not available | 0 | 0 | 1 | 0 |

Arm D's nearest-equivalent calls cover 10 rows, and their values are never scored. Seven of them
are "not supported". For the other three (R1b, S2, S3) the reference is a refusal, so values are
"not applicable".

**Where arm C's metadata is "incomplete" (6 rows):**

- **The JSON names no units:**
  - stofs-mcp's max tool (R1a, R3);
  - its station tool (R2, R5);
  - erddap-mcp's griddap tool (N4).
- **S1:** see §1.3.

## 3. Which rule each task needed, and where it lives

Arm B's rules are in `arms/B/arm_b.py` (summary in `arms/B/RULES.md`). Arm C's are in stofs-mcp
0.3.0, `servers/stofs-mcp/src/stofs_mcp/` at `db234f7`, or in the other packages as named.

| Task | Rule needed | Arm B (user script) | Arm C (tool) |
|---|---|---|---|
| N1 | 2D datum from documentation (label is generic); CO-OPS datum; realization caveat; lead window; one-to-one UTC pairing | B-D1, B-D2, B-D4, B-T2, B-T3 | `utils.documented_fallback` + `models.DOCUMENTED_2D_STATION_DATUM`; `resolve_station_datum`; `datum_note` in `tools/validation.py`; `lead_start_hours` / `lead_end_hours`; `utils.align_timeseries` |
| N2 | 3D datum from the file label, consistent with SCN 26-51; then as N1 | B-D3, B-D1, B-D2, B-D4, B-T2, B-T3 | `utils.classify_datum_label`, `read_datum_metadata`, `resolve_station_datum`; then as N1 |
| N3 | Same datum, units and time zone for observations and predictions; exact-time difference | B-R1 | **No tool.** coops-mcp has no residual tool; the frozen client join in `grader/adapters.py` did it. coops-mcp supplies the datum in `request_params` |
| N4 | Null is missing, not zero; units from the response | B-E1 | **No rule needed in the tool.** erddap-mcp passes ERDDAP's nulls through unchanged. Its JSON omits units |
| R1a | No-data/plausibility screen of model values; name excluded stations | B-Q1 (30 m bound) | `utils.exclusion_masks` (`NO_DATA_MAGNITUDE_M` 10⁴ m, `PLAUSIBLE_WATER_LEVEL_M` 50 m); max tool `excluded_stations` |
| R1b | Same screen; decline when no valid model value remains | B-Q1 | Same screen through `valid_values`; the compare tool declines before any CO-OPS request (1 HTTP request in the session) |
| R2 | Same screen on a station series (shifted dry value −99998.6) | B-Q1 | `exclusion_masks` (`sentinel`); `excluded_model_records` in the station tool |
| R3 | Same screen (physically implausible values, SA816) | B-Q1 | `exclusion_masks` (`implausible`); max tool `excluded_stations` |
| R4a, R4b | Datum by product version from the file, not a fixed pairing; CO-OPS datum follows it | B-D1, B-D3, B-D2 | `resolve_station_datum` with `COOPS_DATUM_FOR_MODEL_DATUM` |
| R5 | 2D datum from documentation, attributed to it | B-D1 | `documented_fallback`; `datum_source` / `datum_provenance` |
| R6 | Detect and correct reversed coordinates, and say so | B-C1 (product-domain test; reported) | `utils.unswap_station_coords` (sign pattern; **silent**) |
| R7 | NDBC historical 9-fill codes are missing | B-W1 | ww3-mcp 0.1.2 has no such rule (WP0 F1); candidate 0.1.3 not available |
| S1 | Missing 3D datum label: decline (or flag an assumption) | B-D3 | `resolve_station_datum` (absent label: undetermined, refused) |
| S2 | Conflicting labels: decline | B-D3 | `combine_datum_attributes` (conflicting: refused) |
| S3 | Undocumented 2D version: decline | B-D1 (documented versions only) | `documented_fallback` bounded to documented versions (commit `52f5ae6`) |
| S4 | Blank and non-finite observations excluded and counted; finite statistics | B-Q2 | Observation screening in `tools/validation.py` (`observation_quality.missing` / `nonfinite`); `dumps_strict` |
| S5 | Recognise a harmless wording variant (the CF standard name) | B-D3 (token classifier) | `classify_datum_label` |

**In every row except N3, N4 and R7, the rule the task needed is written once in the tool and is
available to any MCP client.** For arm B, the same rule had to be written in the user's script.

## 4. Defects found

**No fix was approved or applied.** All results above are from the code under test. Per the brief,
each defect is reported with a proposed fix.

**In the 0.3.0 candidate (stofs-mcp at `db234f7`):**

1. **Silent coordinate repair** (R6).
   - **Behaviour.** `unswap_station_coords` (`utils.py:474`) swaps the reversed records of pre-v3.1
     STOFS-3D files. The point, station and max responses do not say so, and do not keep the raw
     coordinates. This is the open item H1 of the second review and item 9 of
     `STOFS_FINAL_HARDENING_REPORT.md` §8.
   - **Proposed fix.** When a record is swapped, return `coordinates: {corrected: true, rule,
     raw_x, raw_y}` and a sentence in the JSON and markdown. Add a regression test on the
     2026-02-18 file.
   - **Pre-fix result:** R6 arm C, "proceed, caveat missing".
2. **No `units` field in the JSON** of `stofs_get_max_water_level`, `stofs_get_station_forecast`
   and `stofs_get_point_forecast`. `stofs_compare_with_observations` has one.
   - **Proposed fix.** Add `"units"` from `zeta:units`, defaulting to "m".
   - **Effect now:** metadata incomplete for R1a, R3 and R5 in arm C.
   - The same gap is in 0.2.0.

**Outside the candidate:**

3. **erddap-mcp 0.1.2: no units in the griddap JSON** (N4, arms C and D). This was already noted
   in the second review D3. Proposed fix: carry ERDDAP's `columnUnits`.
4. **ww3-mcp 0.1.2: `ww3_get_buoy_history`** (R7, arm D). There are two problems:
   - The 9-fill codes come back as data (WP0 F1).
   - The history tool takes every 10th row and returns at most 5,000. It therefore cannot return
     the annual maximum: the subsample's largest valid value is 5.6 m, against the true 6.32 m at
     2024-10-10 08:10.

   **Proposed fix:**
   - apply NDBC's historical missing codes;
   - compute summary statistics (max with its time, mean, valid count) over all rows before
     subsampling;
   - add the truncation envelope.
5. **stofs-mcp 0.2.0 (released).** These are the version differences that 0.3.0 fixes. Arm D
   shows each of them:
   - STOFS-3D hard-coded as NAVD88 (N2, R4b, S1, S2, S5);
   - no no-data or plausibility screen (R1a, R1b, R2, R3);
   - no coordinate repair (R6);
   - NaN statistics and NaN tokens in its JSON (S4);
   - no datum source or product version;
   - no lead-time window.
6. **My own frozen grader and references:**
   - the S1 values-kind bug, fixed by A1;
   - the R2 `n_values` artefact and the S1 source rule, reported in §1.3 and not changed.

## 5. Limitations

- **One author for everything.** The same author and assistant wrote every arm, the references,
  the grader and the adapters.
- **The designer was not blind.**
  - Before designing, the designer had read stofs-mcp 0.3.0's source (including its 50 m bound and
    sentinel rule) and the reports that show 0.3.0's behaviour on R1–R3.
  - Arm B was written after the grader was frozen, with its patterns known.
  - Arm B uses its own constants and logic, but it is not an independent implementation.
- **The task set is small.** There are 16 tasks and 18 graded rows.
  - Most tasks use one station (Boston, 8443970) or one station file per product and cycle.
  - Twelve of the 18 rows use the two 2026-10-30 12z files; five of those use mutated copies.
  - Each defect is represented once.
- **Five rows are synthetic** (S1–S5), built by mutating real files.
- **The observations behind eight rows were preliminary when archived.** These are the 2026-10-30
  observations (N1, N2, R1b and S1–S5). They were still unrevised on 2026-11-06.
- **Some references are weaker.**
  - **Archived independent sources** cover N1–N4: the Boston recalculation and the second review.
  - **Recalculated by the same author** with a separate pure-Python script are R1a, R2, R3,
    R4a/b, R6, R7 and S4. The physical-bound references are insensitive to the bound chosen
    (intervals in `computed_values.json`). R7 is corroborated by NOAA's ERDDAP copy.
- **Decisions are graded by fixed regular expressions and predicates.** Two cells disagree with a
  plain reading (§1.3). Both are reported, and neither is corrected.
- **Coverage gaps:**
  - **Arm D cannot express the lead-time window.** For 10 rows its comparison values come from
    nearest-equivalent calls and are not scored.
  - **N3 needed a client-side join** for arms C and D.
  - **R7 has no arm C.**
- **Arms A and B do not use searvey, noaa-coops or erddapy.** These clients cannot read archived
  bytes without patching. "Basic Python" is my operational definition, and some of arm A's grades
  follow from it: for example, arm A reports the 3D file's `title` ("SCHISM Model output") as the
  product version.
- **One platform.** Everything ran once on one platform: WSL2 Ubuntu 24.04, CPython 3.13.12,
  mcp 1.30.0.
- **Replay does not test the network.** It serves identical bodies, but seeded entries carry
  synthetic HTTP headers, and latency, timeouts and retries are not exercised.

## 6. Proposed manuscript text (208 words) and table

> We compared four workflows on 18 predeclared task rows built from archived NOAA files: four
> nominal tasks, seven defects present in real operational files and five labelled synthetic
> mutations. Each row was graded separately on values, metadata, and the decision to compare,
> exclude or decline (Table X). Basic Python, using xarray and pandas defaults with a fixed
> documented datum pairing, reproduced the nominal statistics but proceeded falsely in 11 rows. It
> ranked 10^7 m no-data codes as the highest water levels, compared a NAVD88 cycle with
> mean-sea-level observations, chose a station 1,772 km away because coordinates were stored
> reversed, and compared files whose datum labels were missing or contradictory. A validated
> Python workflow, written from NOAA documentation and physical bounds, made the reference decision
> in all 18 rows. Ocean-MCP 0.3.0, called through MCP stdio sessions on the same archived bytes,
> matched every value it returned. It agreed with the validated workflow on 16 of 17 decisions when
> its output is read plainly; it corrected the reversed coordinates without reporting the
> correction. The released version 0.2.0 made 12 false proceeds. The safeguards are therefore not
> beyond a careful script: Ocean-MCP's contribution is validated checks made reusable through MCP.
> One author wrote every workflow, and the task set is small.

**Table X.** Outcomes over 18 task rows (four nominal, nine real-file rows covering seven defects,
five synthetic).

| Workflow | Values within tolerance / graded | Correct decisions | Caveat missing | False proceed | False refusal | Not run or not supported |
|---|---:|---:|---:|---:|---:|---|
| Basic Python | 7 / 14 | 3 | 4 | 11 | 0 | – |
| Validated Python | 13 / 13 | 18 | 0 | 0 | 0 | – |
| Ocean-MCP 0.3.0 (MCP) | 12 / 12 | 15 (16)ᵃ | 1 | 1 (0)ᵃ | 0 | R7: candidate not available |
| stofs-mcp 0.2.0 (MCP) | 2 / 6 | 3 | 2 | 12 | 1 | 7 rows: values not supported |

Notes:

- **ᵃ Plain reading.** The grader scores R2 as a false proceed because of a record count (§1.3).
- **Correct decisions** count three outcomes: correct proceed, correct proceed with the required
  caveat, and correct refusal naming the cause.
- **Values** are counted under amendment A1.

## 7. Phase 2 checks requested by the author

- **R7 candidate.** When Phase 2 started (2026-11-06 15:58:13 UTC), `verification_ww3_history_fix/`
  did not exist. No `ww3_mcp-0.1.3*` wheel was found within four levels of the repository, so
  there is no SHA-256 to give. R7 arm C is recorded as "candidate not available", and no session
  was started for it (`run_log/phase2_start.json`).
- **Validation of replay rule 3 (CO-OPS slicing).** One real request was made:
  - the request: Boston, MSL, 2026-08-17 12:06 to 2026-08-19 12:00, `application=stofs_mcp`.
    These are the exact parameters stofs-mcp 0.3.0 sends for R4b, and the data are verified;
  - the comparison: the response was compared with the replay's slice of archived master `e0009`
    (2026-08-15 to 08-19);
  - the result: the two are **byte-identical** (36,255 bytes, SHA-256 `527d5660…155bd`, 480
    records, all `q = v`), with no differing record.

  The live response is archived separately (`data/archive/validation_slice/`), so the sessions
  still exercised the slicing rule. Details are in `run_log/slice_validation.json`.
- **A2.** It was recorded and committed (`53d0f3f`) before any arm C or D session was run (§1.2).
- **Evidence and disagreements.** See §1.3, §1.4 and Appendix A.
- **Arm D's nearest-equivalent values** are in the last column of §1.1 and in
  `results/arm_D_nearest_equivalent_values.{md,csv}`, unscored.

## 8. How the MCP arms ran on archived bytes

- **Launcher.** `replay/ocean_replay_launcher.py` is outside every package.
  - It patches `httpx.AsyncHTTPTransport.handle_async_request` and
    `httpx.HTTPTransport.handle_request`. In replay mode it also patches `socket.getaddrinfo`,
    `create_connection` and `connect`.
  - It then runs the unmodified package's `__main__`.
- **Matching rules:**
  1. exact URL and query match, ignoring CO-OPS `application`;
  2. a HEAD request answered from the archived GET;
  3. CO-OPS water-level slicing from a master. The master's byte layout is verified by a byte-exact
     round trip, and the rule was validated against a live request (§7).
- **Sessions.** Every session ran inside `unshare -rn`, and its network probe recorded "Network is
  unreachable".
  - Any miss or blocked attempt invalidates a session. There were none.
  - Every request, with the archive entry that answered it and the SHA-256 of the served bytes, is
    in `run_log/sessions/<arm>/<task>/http_log.jsonl`.
  - The full MCP exchange of each session is in its `transcript.json`: initialize, tool schemas,
    every call and every response.
- **Phase 0 proof** (`phase0/phase0_check.json`). The archived Boston comparisons reproduce exactly
  through a real session against the 0.3.0 wheel.

**What ran through real MCP stdio sessions:**

| Arm | Package (versions read in-session) | Sessions |
|---|---|---|
| C | stofs-mcp 0.3.0 (WP0 wheel `29fcb737…dafdd`), coops-mcp 0.1.1, erddap-mcp 0.1.2 | 17 |
| D | stofs-mcp 0.2.0, coops-mcp 0.1.1, erddap-mcp 0.1.2, ww3-mcp 0.1.2 (all PyPI) | 18 |

- All 35 sessions use mcp 1.30.0 and Python 3.13.12, and all were valid.
- The Phase 0 sessions are listed in `DESIGN.md` §1.
- **Not run through MCP:** R7 arm C (no candidate).
- `run_all.sh` repeated all sessions offline with identical answers and grades.

## 9. Preservation

These checks were run after the last commit:

- No existing branch, worktree or raw input was changed. In detail:
  - **Worktree HEADs:** `stofs-hardening 31e7f6a`, `stofs-release db234f7`,
    `stofs-v31-boston 933000d` and `stofs-v31-boston-v2 57e853e` are unchanged, with no tracked
    changes.
  - **Main checkout:** `b562bf4` on `fix/stofs-compare-window-default`, with no tracked changes.
  - **ian-cross-server:** it moved to `2e05098` during this work. That was the parallel WP2
    session, not this one.
- The checksums of the Boston raw files, the WP0 download, the WP0 wheel and manifest, and the
  manuscript DOCX are unchanged.
- Nothing was pushed, pulled, fetched, merged, rebased, tagged, published or uploaded. There are
  still 44 tags and 0 stashes.
- NOAA was contacted only for the 18 recorded input requests and the one rule-3 validation
  request. The 18 requests went sequentially with 4 s pauses:
  - 3 S3 station files;
  - 8 CO-OPS responses;
  - 4 ERDDAP requests, one of them a 400 caused by my lower-case variable name, which is kept in
    the archive;
  - 3 documentation pages.

---

## Appendix A. Decision-axis evidence for all 72 grades (primary grading)

Generated from `results/decision_evidence.md`. The trigger is one of:

- the passage of the output that a fixed pattern matched;
- the finding of a fixed predicate;
- for a grade given because something was absent, the output's complete notes.

- trigger: `no realization`
- output notes (complete): (none)

**N1 / arm B: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**N1 / arm C: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N1 / arm D: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**N2 / arm A: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**N2 / arm B: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**N2 / arm C: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N2 / arm D: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

**N3 / arm A: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / arm B: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / arm C: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N3 / arm D: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N4 / arm A: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / arm B: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / arm C: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**N4 / arm D: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**R1a / arm A: false_proceed**
- trigger: `no-data or implausible station in the answer: ['9751364', '9751401', '9751381', '9752695', '9752235']`

**R1a / arm B: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1a / arm C: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1a / arm D: false_proceed**
- trigger: `no-data or implausible station in the answer: ['9751364', '9751401', '9751381', '9752695', '9752235']`

**R1b / arm A: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**R1b / arm B: correct_refusal_or_flag**
- trigger: `[B-Q1] No valid model value for LAMV3 SOUS41 9751381 VI Lameshur Bay, St John in 0 < lead <= 48`

**R1b / arm C: correct_refusal_or_flag**
- trigger: `No usable STOFS values for station 9751381 in this cycle: all 1200 records were excluded `

**R1b / arm D: false_proceed**
- trigger: `proceeded where the reference is a refusal`

**R2 / arm A: false_proceed**
- trigger: `value beyond 30.0 m: ['min_m=-99998.6']`

**R2 / arm B: correct_proceed_with_caveat**
- trigger: `count 47`

**R2 / arm C: false_proceed**
- trigger: `value beyond 30.0 m: ['n_values=1813']`

**R2 / arm D: false_proceed**
- trigger: `value beyond 30.0 m: ['min_m=-99998.6', 'n_values=1860']`

**R3 / arm A: false_proceed**
- trigger: `no-data or implausible station in the answer: ['SA816']`

**R3 / arm B: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R3 / arm C: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R3 / arm D: false_proceed**
- trigger: `no-data or implausible station in the answer: ['SA816']`

**R4a / arm A: false_proceed**
- trigger: `observation datum MSL (required NAVD88)`

**R4a / arm B: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4a / arm C: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4a / arm D: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4b / arm A: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**R4b / arm B: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**R4b / arm C: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**R4b / arm D: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

**R5 / arm A: correct_proceed_with_caveat**
- trigger: `fixed pairing from current product documentation (NOMADS STOFS-Global product description)`

**R5 / arm B: correct_proceed_with_caveat**
- trigger: `NOAA documentation: NOMADS STOFS-Global product description (station output referenced to LMSL)`

**R5 / arm C: correct_proceed_with_caveat**
- trigger: `NOAA documentation (STOFS_2D_GLOBAL V3.1.0: NOMADS STOFS-Global description (archived 2026-11-04): station and gridded output referenced to LMSL); file label zeta:standard_name=sea_surface_height_above_geoid names no specific datum`

**R5 / arm D: proceed_caveat_missing**
- trigger: `no doc_source`
- output notes (complete): (none)

**R6 / arm A: false_proceed**
- trigger: `station TRDF1 SOUS41 8721604 FL Trident Pier, Port Canaver`

**R6 / arm B: correct_proceed_with_caveat**
- trigger: `[B-C1] 105 of 108 station records store latitude in x and longitude in y (reversed relative to their attributes); they were swapped before the distance search. `

**R6 / arm C: proceed_caveat_missing**
- trigger: `no coords_reversed`
- output notes (complete): (none)

**R6 / arm D: false_refusal**
- trigger: `No STOFS station found within 50.0 km of (42.3539, -71.0503).

Suggestions:
- Increase max_distance_km
- Try model='2d_global' which has ~385 stations (vs ~108 for 3D)
- Use stofs_get_gridded_forecast for any lat/lon (uses OPeNDAP regular grid)
- Verify the coordinates are in a coastal area`
- output notes (complete): `No STOFS station found within 50.0 km of (42.3539, -71.0503).

Suggestions:
- Increase max_distance_km
- Try model='2d_global' which has ~385 stations (vs ~108 for 3D)
- Use stofs_get_gridded_forecast for any lat/lon (uses OPeNDAP regular grid)
- Verify the coordinates are in a coastal area`

**R7 / arm A: false_proceed**
- trigger: `value beyond 30.0 m: ['max_wvht_m=99.0']`

**R7 / arm B: correct_proceed_with_caveat**
- trigger: `counts [35235]`

**R7 / arm C: candidate_not_available**
- trigger: (no text: correct proceed with no caveat required)

**R7 / arm D: false_proceed**
- trigger: `value beyond 30.0 m: ['max_wvht_m=99.0']`

**S1 / arm A: false_proceed**
- trigger: `proceeded without the flag`

**S1 / arm B: correct_refusal_or_flag**
- trigger: `[B-D3] The zeta variable carries no datum label (no standard_name or long_name). STOFS-3D station output is labelled in N`

**S1 / arm C: correct_refusal_or_flag**
- trigger: `No comparison: the vertical datum of the STOFS values for station 8443970 could not be established. The file name`

**S1 / arm D: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

**S2 / arm A: false_proceed**
- trigger: `proceeded where the reference is a refusal`
- A2 lenient: false_proceed (`lenient rule not met: missing ['cause stated']; pairing MSL/MSL`)

**S2 / arm B: correct_refusal_or_flag**
- trigger: `[B-D3] Conflicting datum labels on zeta: {'standard_name': 'sea_surface_height_above_msl', 'lon`
- A2 lenient: correct_refusal_or_flag (`[B-D3] Conflicting datum labels on zeta: {'standard_name': 'sea_surface_height_above_msl', 'lon`)

**S2 / arm C: correct_refusal_or_flag**
- trigger: `alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`
- A2 lenient: correct_refusal_or_flag (`alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`)

**S2 / arm D: false_proceed**
- trigger: `proceeded where the reference is a refusal`
- A2 lenient: false_proceed (`lenient rule not met: missing ['cause stated', 'datum attributed to documentation or assumption']; pairing NAVD88/NAVD88`)

**S3 / arm A: false_proceed**
- trigger: `proceeded where the reference is a refusal`
- A2 lenient: false_proceed (`lenient rule not met: missing ['cause stated']; pairing MSL/MSL`)

**S3 / arm B: correct_refusal_or_flag**
- trigger: `'long_name': 'water surface elevation above geoid'} names no datum, and product version 4.0.0 is not documented (documented: STOFS_2D_GLOBAL V3.1). Datum undetermined;`
- A2 lenient: correct_refusal_or_flag (`'long_name': 'water surface elevation above geoid'} names no datum, and product version 4.0.0 is not documented (documented: STOFS_2D_GLOBAL V3.1). Datum undetermined;`)

**S3 / arm C: correct_refusal_or_flag**
- trigger: `s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`
- A2 lenient: correct_refusal_or_flag (`s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`)

**S3 / arm D: false_proceed**
- trigger: `proceeded where the reference is a refusal`
- A2 lenient: false_proceed (`lenient rule not met: missing ['cause stated', 'datum attributed to documentation or assumption']; pairing MSL/MSL`)

**S4 / arm A: false_proceed**
- trigger: `non-finite statistics [nan, inf, inf, nan]`

**S4 / arm B: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S4 / arm C: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S4 / arm D: false_proceed**
- trigger: `non-finite statistics [nan, nan, nan, nan]`

**S5 / arm A: proceed_caveat_missing**
- trigger: `no realization`
- output notes (complete): (none)

**S5 / arm B: correct_proceed_with_caveat**
- trigger: `h mean-sea-level datums and are treated as compatible, but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 National Tidal Datum Epoch [COO`

**S5 / arm C: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**S5 / arm D: false_proceed**
- trigger: `observation datum NAVD88 (required MSL)`

