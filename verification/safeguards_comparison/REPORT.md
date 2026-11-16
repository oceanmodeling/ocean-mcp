# WP1: scientific-safeguards comparison: report

Run on 2026-11-06, on branch `eval/safeguards-comparison` (local only), in worktree
`.claude/worktrees/safeguards-comparison`.

| Step | Commit |
|---|---|
| Design freeze | `5d84c13` |
| Arms A and B | `96fd7f8` |
| Phase 2 start and amendment A2 | `53d0f3f` |
| Arms C and D, grading, first report | `e74f02b` |
| WP1b: amendment A3 (R7) | `fe1cac5` |
| WP1b: arm C-post sessions and gradings | `03509ee` |
| WP1b: report revision | `45c68df` |
| WP1c: grader v2 and this revision | the commit that adds `grader/v2/` |

**WP1b (2026-11-08/09).** Three fixes were approved after WP1:

- D1 and D2 in stofs-mcp 0.3.0, on `fix/stofs-post-wp1`;
- D3 in erddap-mcp, on `fix/erddap-griddap-units`;
- the ww3-mcp 0.1.3 history fix, from WP0b.

Arm C was then rerun as **arm C-post (0.3.0 post-fix)**. The pre-fix results below are unchanged.
The post-fix results are added in §1.5, and in the C-post columns of §2, §4 and §6.

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
- **WP1c: grader v2** (§1.3a, `grader/v2/CHANGES.md`).
  - **What it is:** a versioned correction of five documented defects of the frozen grader (v1),
    applied identically to all five result sets.
  - **What it leaves alone:** no task, reference, tolerance, category, arm or archived output was
    changed, and v1 and its results stay in the record.
  - **Fairness check:** passed. 14 cells change, all in arms C and C-post, and each traces to one
    listed change. No cell of arms A, B or D changes.
  - **Arm C-post under v2:** the reference decision in 18 of 18 rows and 13 of 13 values within
    tolerance, the same as arm B.
  - **Arm C (pre-fix) under v2:** 16 of 17 rows; R6, the silent coordinate correction, remains.
- **WP1b: after the three approved fixes, arm C-post (0.3.0 post-fix) matches arm B on every
  decision when read plainly** (§1.5):
  - **Values:** 12 of 13 graded values are within tolerance under the frozen grader. R7 is the
    exception; under amendment A3, which reads the maximum the response states, it is within too
    (13 of 13).
  - **Decisions:** 16 of 18 match the reference under the frozen grader, and 18 of 18 when read
    plainly. Two C-post responses are misread by the frozen adapters: R2 (as for arm C) and R7.
  - **What changed from arm C**, only where the brief expected:
    - R6 now reports its coordinate correction;
    - N4, R1a, R2, R3 and R5 now state units;
    - R7 now runs.
  - **Sessions:** all 18 C-post sessions were valid, with no network and 0 misses.
  - **Reproducibility:** `run_all.sh` reproduces both runs from freshly built environments,
    byte-identically.

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

### 1.3a Grader v2 (WP1c)

Two reviews accept the comparison but not "read plainly" as the basis for a reported count. So
the misreadings documented in §1.3 and §1.5, and the R7 answer selection of amendment A3, are
corrected by a versioned grader, `grader/v2/`, applied identically to every arm.

**v1 and its results are not changed.** v2 imports v1 and re-uses every rule, pattern and
predicate. It differs in exactly five places (`grader/v2/CHANGES.md`), each written for any arm's
output format:

| # | Change | v1 behaviour that was a grader defect |
|---|---|---|
| 1 | The value-bound predicate tests only water-level (metre-valued, `_m`) fields. Counts, correlations, distances, SST and text are excluded by name | It flagged R2 because the adapter's `n_values` (1,813) exceeded 30 m |
| 2 | A refusal that names the cause needs no datum-source field | It graded "datum could not be established" as incomplete for lacking a source that cannot exist |
| 3 | Units given per column satisfy the requirement when the graded column (R7 `WVHT`, N4 `analysed_sst`) has the expected unit | It compared ww3-mcp 0.1.3's whole units map with "m" |
| 4 | R7 exclusion counts are read under every key name any arm uses: v1's four, `excluded_counts`, `summary.missing`, and `missing_values.excluded_counts`, the latter two at the graded column | It missed ww3-mcp 0.1.3's report of 35,235 excluded values |
| 5 | The R7 value is the maximum the response states as its answer (`summary.max`), otherwise the maximum over the returned rows (amendment A3) | It graded the 5,000-row sample (5.35 m) instead of the stated whole-file maximum (6.32 m) |

**Unchanged:** task statements, references (both graders use the A1-amended references),
tolerances, decision categories, caveat and cause patterns, arms and archive.

**Fairness check** (`grader/v2/fairness_check.py`, `results/v2_fairness_check.json`). It was run
before v2 was used:

1. **Baseline:** recomputing v1 from the archived answers reproduces the published v1 grades.
2. **Faithfulness:** v2 with all five changes switched off reproduces every v1 grade on every axis,
   and every archived answer.
3. **Attribution:** every cell that differs under v2 was re-graded with one change enabled at a
   time. Each of the 14 changed cells is produced by exactly one change, and
   0 are unexplained.

There are also 17 self-tests (`grader/v2/test_grade_v2.py`), with controls. They check, for
example, that a real −99,998.6 m level still fails, that a proceed still needs a datum source, and
that a units map without the graded column is "not stated".

**Changed cells per arm:**

- **Arms A, B and D:** 0.
- **Arm C:** 5, of which 2 are on the three graded axes and 3 in the strict-metadata column.
- **Arm C-post:** 9, of which 5 are on the graded axes and 4 strict.

| Arm | Task | Axis | v1 | v2 | Change |
|---|---|---|---|---|---|
| C | R2 | decision | false_proceed | correct_proceed_with_caveat | 1 |
| C | S1 | metadata | incomplete | correct | 2 |
| C | S1 | metadata_strict | incomplete | correct | 2 |
| C | S2 | metadata_strict | incomplete | correct | 2 |
| C | S3 | metadata_strict | incomplete | correct | 2 |
| C-post | R2 | decision | false_proceed | correct_proceed_with_caveat | 1 |
| C-post | R7 | values | outside_tolerance | within_tolerance | 5 |
| C-post | R7 | metadata | wrong | correct | 3 |
| C-post | R7 | metadata_strict | wrong | correct | 3 |
| C-post | R7 | decision | proceed_caveat_missing | correct_proceed_with_caveat | 4 |
| C-post | S1 | metadata | incomplete | correct | 2 |
| C-post | S1 | metadata_strict | incomplete | correct | 2 |
| C-post | S2 | metadata_strict | incomplete | correct | 2 |
| C-post | S3 | metadata_strict | incomplete | correct | 2 |

**The §1.3 and §1.5 disagreements are all resolved by these changes:**

- R2 (C, C-post) by change 1;
- S1 metadata (C, C-post) by change 2;
- R7 metadata by change 3;
- R7 decision by change 4;
- R7 values by change 5.

No disagreement remains between v2 and the outputs.

**What the check does not show.** All five defects were found after the v1 grades were seen, and
every misgraded cell was in an Ocean-MCP arm. The check proves traceability; it does not prove
the absence of selection. Known lenient v1 grades (arm A on R5, arm D on R4a; §1.3 notes) are left
as they were, and no systematic search was made for over-lenient grades.

The v2 tables are in `results/table_per_task_v2.*`, `results/table_counts_v2.*`,
`results/decision_evidence_v2.*`, `results/v1_vs_v2_diff.*` and `results/grades_v2.*`.

### 1.4 The exact text behind every decision grade

Appendix A lists all 72 decision grades with the text that triggered each. Where a grade was given
because something was absent, it gives the output's complete notes. Source:
`results/decision_evidence.{md,csv}`.

### 1.5 WP1b: arm C-post (Ocean-MCP 0.3.0 post-fix)

**What arm C-post is.** It sends arm C's frozen calls, unchanged, through real MCP stdio sessions:

- replay mode, inside `unshare -rn`;
- the same archive stacks as Phase 2;
- graded by the frozen grader and adapters, unchanged.

Its packages are:

- **stofs-mcp 0.3.0 post-fix:** `fix/stofs-post-wp1` `52c7f46`, wheel sha256 `ba4edc2e…be9a`;
- **erddap-mcp 0.1.3:** `fix/erddap-griddap-units` `3834480`, wheel `b7c6d76b…9739`;
- **ww3-mcp 0.1.3:** WP0b, `148f84c`, wheel `7d359c4f7bb85b7b604656d51cef60d699a8a7016f4969cfb3b41e7d6be1bf17`;
- **coops-mcp 0.1.1:** as in arm C.

All share one environment. Every other dependency is pinned to arm C's versions
(`environment/cpost.{constraints,freeze}.txt`).

**The ww3-mcp 0.1.3 wheel was present when WP1b started.** It is at
`verification_ww3_history_fix/dist/`, with the sha256 above. It requested the same archived NDBC
URL, so there was no replay miss.

| Task | Arm C (pre-fix) | Arm C-post (post-fix) | Changed axes |
|---|---|---|---|
| N4 | within / incomplete / correct proceed | within / **correct** / correct proceed | metadata (units stated: `{"analysed_sst": "degree_C"}`) |
| R1a | within / incomplete / correct proceed + caveat | within / **correct** / correct proceed + caveat | metadata (`units: "m"`) |
| R2 | within / incomplete / FALSE PROCEED (artefact) | within / **correct** / FALSE PROCEED (same artefact, §1.3) | metadata |
| R3 | within / incomplete / correct proceed + caveat | within / **correct** / correct proceed + caveat | metadata |
| R5 | n/a / incomplete / correct proceed + caveat | n/a / **correct** / correct proceed + caveat | metadata |
| R6 | within / n/a / proceed, caveat MISSING | within / n/a / **correct proceed + caveat** | decision |
| R7 | candidate not available | OUTSIDE (frozen) / WRONG (artefact) / proceed, caveat MISSING (artefact) | all (now run) |
| the other 11 | | identical | none |

**Every change is one the brief expected.** No other task changed on any axis
(`results/wp1b_C_vs_Cpost.{md,csv}`).

**R6, the text that now triggers "correct proceed + caveat":**

> `coordinate_warning: 105 of 108 station records in this file store latitude in x and longitude in y, the reverse of their attributes; their coordinates were swapped (rule: a record reading as latitude < 0 < longitude cannot lie in the STOFS-3D-Atlantic domain). This station's coordinates were corrected (stored x=42.3539103827, y=-71.0502859522).`

**R7 graded two ways (amendment A3), frozen first** (`results/r7_A3.{md,csv,json}`):

| Arm | Frozen: value used / grades (values, metadata, decision) | Amended: value used / grades |
|---|---|---|
| A | 99.0 / outside, correct, false proceed | 99.0 / same |
| B | 6.32 / within, correct, correct proceed + caveat | 6.32 / same |
| C (pre-fix) | candidate not available | candidate not available |
| D | 99.0 / outside, incomplete, false proceed | 99.0 / same |
| C-post | **5.35** / outside, wrong, caveat missing | **6.32** / **within**, wrong, caveat missing |

The text that triggered each C-post R7 reading:

- **Frozen:** `maximum WVHT over the 5000 returned rows = 5.35 (row time 2024-12-15 17:40)`.
- **Amended:** `summary: {"units": "m", "covers": "all 52692 rows of the file", "missing": 35235, "valid": 17457, "max": 6.32, "max_time": "2024-10-10 08:10"}`.

For every other arm the two readings agree.

**Rows where a plain reading of C-post disagrees with the grader** (`results/wp1b_disagreements.md`).
The grader is not changed:

| Task | Axis | Grader | Plain reading | Triggering text and reason |
|---|---|---|---|---|
| R2 | decision | false proceed | correct proceed + caveat | As for arm C (§1.3): `value beyond 30.0 m: ['n_values=1813']`. The tool returned min −0.109 m and `excluded_model_records.sentinel = 47` |
| S1 | metadata | incomplete | correct | As for arm C: `model_datum source not stated` for a datum the tool says "could not be established" |
| R7 | metadata | wrong | correct | ww3-mcp 0.1.3 states units per column, `units = {"WVHT": "m", …}`, plus `summary.units = "m"`. The frozen adapter compares the whole map with "m" |
| R7 | decision | caveat missing | correct proceed + caveat | Trigger `no excluded_records`. The response states `summary.missing = 35235`, and `missing_values` gives NDBC's rule (a field equal to its column's 9-filled code is returned as null and counted), the codes (`WVHT 99.00`) and the documentation URL. The frozen adapter looks only for top-level keys named `excluded`, `excluded_values`, `missing` or `excluded_records`. A3 concerns the value and does not change this axis |

**A2 with C-post.** C-post refuses S2 and S3, naming the cause, as arm C does, so the frozen and
lenient grades agree (`results/sensitivity_A2_with_Cpost.*`). The WP1 A2 files are unchanged.

Appendix B gives the triggering text for every C-post decision grade.

## 2. Counts per arm (18 rows each; no composite score)

**Graders v1 and v2, side by side, v1 first.**

- **v1** is the frozen grader. **v2** is the corrected grader (§1.3a).
- **References:** both use the A1-amended references. The strictly frozen v1 grading, without A1,
  differs only in S1 values for arms B, C and C-post ("not returned" instead of "not applicable");
  it is in `results/grades_*` without the `_amended` suffix.
- **Arm columns:**
  - C is the pre-fix 0.3.0 candidate;
  - C-post is the post-fix candidate (WP1b).
- **No "read plainly" column under v2.** Every §1.3/§1.5 disagreement is resolved by a listed v2
  change, and none remains.

All tables are in `results/table_counts_v2.{md,csv}` (v1 and v2) and `results/table_counts.*`
(v1, WP1).

| Axis | Outcome | A v1 | A v2 | B v1 | B v2 | C v1 | C v2 | C-post v1 | C-post v2 | D v1 | D v2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Values | within tolerance | 7 | 7 | 13 | 13 | 12 | 12 | 12 | 13 | 2 | 2 |
|  | outside tolerance | 7 | 7 | 0 | 0 | 0 | 0 | 1 | 0 | 4 | 4 |
|  | not returned | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
|  | not applicable | 4 | 4 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 4 |
|  | **not supported** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **7** | **7** |
|  | candidate not available | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| Metadata | correct | 11 | 11 | 17 | 17 | 9 | 10 | 14 | 16 | 1 | 1 |
|  | incomplete | 0 | 0 | 0 | 0 | 6 | 5 | 1 | 0 | 8 | 8 |
|  | wrong | 6 | 6 | 0 | 0 | 0 | 0 | 1 | 0 | 8 | 8 |
|  | not applicable / candidate not available | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 | 2 / 1 | 2 / 1 | 2 / 0 | 2 / 0 | 1 / 0 | 1 / 0 |
| Metadata, strict | correct / incomplete / wrong | 11 / 0 / 6 | 11 / 0 / 6 | 17 / 0 / 0 | 17 / 0 / 0 | 7 / 8 / 0 | 10 / 5 / 0 | 12 / 3 / 1 | 16 / 0 / 0 | 1 / 8 / 8 | 1 / 8 / 8 |
| Decision | correct proceed | 2 | 2 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
|  | correct proceed with required caveat | 1 | 1 | 11 | 11 | 8 | 9 | 9 | 11 | 0 | 0 |
|  | correct refusal naming the cause | 0 | 0 | 4 | 4 | 4 | 4 | 4 | 4 | 0 | 0 |
|  | proceed, required caveat missing | 4 | 4 | 0 | 0 | 1 | 1 | 1 | 0 | 2 | 2 |
|  | **false proceed** | **11** | **11** | **0** | **0** | **1** | **0** | **1** | **0** | **12** | **12** |
|  | **false refusal** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **1** | **1** |
|  | candidate not available | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| Decision | *all correct (sum of the three correct outcomes)* | 3 | 3 | 18 | 18 | 15 | 16 | 16 | 18 | 3 | 3 |

Arm D's nearest-equivalent calls cover 10 rows, and their values are never scored. Seven of them
are "not supported". For the other three (R1b, S2, S3) the reference is a refusal, so values are
"not applicable".

**Where arm C's metadata is "incomplete"** (6 rows under v1; 5 under v2, where change 2 resolves S1):

- **The JSON names no units:**
  - stofs-mcp's max tool (R1a, R3);
  - its station tool (R2, R5);
  - erddap-mcp's griddap tool (N4).
- **S1:** see §1.3. Under v2 this row is correct (change 2).

**Arm C-post** has no incomplete or wrong metadata under v2. Under v1 it had S1 (incomplete) and
R7 (wrong), resolved by changes 2 and 3.

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

**WP1 applied no fix.** Every result in §1.1 to §1.4 is from the code under test. WP1b then
applied the approved fixes on separate branches, and arm C-post reran the tasks with them. The
pre-fix results are kept unchanged. The post-fix results follow each defect below.

| Defect | Fix (branch, commit, wheel sha256) | Task: pre-fix (arm C) → post-fix (arm C-post) |
|---|---|---|
| D1 silent coordinate repair | `fix/stofs-post-wp1` `52c7f46`, stofs-mcp 0.3.0 wheel `ba4edc2e…be9a` | R6 decision: proceed, caveat missing → **correct proceed with the required caveat** (values within both times) |
| D2 no `units` in station/point/max JSON | same commit | metadata incomplete → **correct**: R1a, R2, R3, R5. R6 has no metadata requirement |
| D3 no units in erddap griddap JSON | `fix/erddap-griddap-units` `2567537`, bumped to 0.1.3 in `3834480`, wheel `b7c6d76b…9739` | N4 metadata: incomplete → **correct** (`{"analysed_sst": "degree_C"}`) |
| ww3 history (WP0 F1, WP1 defect 4) | WP0b, `fix/ww3-buoy-history-missing-codes` `148f84c`, ww3-mcp 0.1.3 wheel `7d359c4f…bf17` | R7: candidate not available → values outside under the frozen reading (5.35 m) and **within under A3** (6.32 m). Metadata "wrong" and decision "caveat missing" are grader misreadings (§1.5) |

Tests and checks for the fixes are in `verification_post_wp1/REPORT.md`, in the main checkout,
untracked. For stofs-mcp, 373 tests were collected and 373 passed on each of 3.11, 3.12 and 3.13;
for erddap-mcp, 124 of 124. Both pass ruff check, ruff format and `uv build`. The text of each
defect below is the WP1 text, with the WP1b outcome added.

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
   - **WP1b fix, as applied.**
     - JSON gains `coordinate_warning` and `coordinate_provenance` beside the datum fields. They
       give the rule, the number of records checked, corrected and undetermined, and the
       station's own flag with its stored x and y.
     - Markdown gains one line.
     - A record that reads as neither orientation is reported as undetermined rather than guessed.
   - **Post-fix result:** R6 arm C-post, "correct proceed with the required caveat".
2. **No `units` field in the JSON** of `stofs_get_max_water_level`, `stofs_get_station_forecast`
   and `stofs_get_point_forecast`. `stofs_compare_with_observations` has one.
   - **Proposed fix.** Add `"units"` from `zeta:units`, defaulting to "m".
   - **Effect now:** metadata incomplete for R1a, R3 and R5 in arm C.
   - The same gap is in 0.2.0.
   - **WP1b fix, as applied.** `"units"` from `zeta:units`, placed after `datum_provenance`.
   - **Post-fix result:** metadata "correct" for R1a, R2, R3 and R5 in arm C-post.

**Outside the candidate:**

3. **erddap-mcp 0.1.2: no units in the griddap JSON** (N4, arms C and D). This was already noted
   in the second review D3. Proposed fix: carry ERDDAP's `columnUnits`.
   - **WP1b fix, as applied.** The units are read from the dataset's info rows (its own metadata),
     never hard-coded. `units_missing` lists any variable without a units attribute.
   - **Post-fix result:** N4 metadata "correct" in arm C-post.
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

   **WP0b fix, as applied (ww3-mcp 0.1.3).**
   - The codes become `null`.
   - The `summary` covers every row of the file: max 6.32 m at 2024-10-10 08:10, 35,235 missing.
   - The tool returns the most recent `max_records` rows, with a truncation envelope.

   **Post-fix result.** R7 arm C-post: the stated maximum is 6.32 m, within tolerance under A3.
   The frozen reading of the returned rows gives 5.35 m.

   **Newer wheel, not used.** A later ww3-mcp 0.1.3 wheel, `ff7cf07a…` from
   `fix/ww3-realtime-row-interval`, another session's WP0c, is in `verification_ww3_interval_fix/dist/`.
   - It was not used, because the WP1b brief names `7d359c4f…bf17`.
   - Its `ww3_get_buoy_history`, `parse_ndbc_historical` and `summarize_values` are byte-identical
     to those of the wheel used. Other files differ (the realtime tools).
   - R7 was not run with it.
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
   - the R2 `n_values` artefact and the S1 source rule, reported in §1.3 and not changed;
   - two WP1b additions, reported in §1.5 and not changed:
     - the R7 units-map reading;
     - the R7 exclusion key names, which miss `summary.missing` and `missing_values`.

   **The R7 value reading needed A3.** The frozen adapter takes the maximum over the returned
   rows, which was adequate only for 0.1.2's whole-year stride.

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
- **Grader v2 was written after the v1 grades were known** (WP1c). Its five changes correct
  documented misreadings, and all of them concerned Ocean-MCP arms. The fairness check shows that
  every v1→v2 difference traces to one generic change and that no cell of arms A, B or D moved. It
  does not show the changes are free of selection; no systematic search was made for v1 grades
  that are too lenient. The v1 grades are reported first throughout.

## 6. Proposed manuscript text (229 words) and table: revised in WP1c

The text now reports grader v1 and grader v2 counts for every arm. Earlier versions are kept in
the appendices:

- WP1, 208 words: Appendix C;
- WP1b, 229 words: Appendix D.

> We compared four workflows on 18 predeclared task rows built from archived NOAA files: four
> nominal tasks, seven defects present in real operational files and five labelled synthetic
> mutations. Each row was graded separately on values, metadata, and the decision to compare,
> exclude or decline (Table X). Basic Python, with library defaults and one fixed documented datum
> pairing, reproduced the nominal statistics but proceeded falsely in 11 rows. It ranked 10^7 m
> no-data codes as the highest water levels, compared a NAVD88 cycle with mean-sea-level
> observations, chose a station 1,772 km away because coordinates were stored reversed, and compared
> files whose datum labels were missing or contradictory. A validated Python workflow, written from
> NOAA documentation and physical bounds, made the reference decision in all 18 rows. The evaluation
> exposed three defects in the Ocean-MCP release candidate, now fixed: an unreported coordinate
> correction, missing units, and wave-height fill codes returned as data. After the fixes, the
> candidate, run through MCP on the same archived bytes, made the reference decision in all 18 rows
> under grader v2 and 16 under the frozen grader. Grader v2 corrects five documented grader defects,
> was applied identically to all arms, and changed no task, reference or tolerance. Released
> stofs-mcp 0.2.0 made 12 false proceeds under both. Ocean-MCP's contribution is validated checks
> made reusable through MCP. One author wrote every workflow; the task set is small.

**Table X.** Outcomes over 18 task rows (four nominal, nine real-file rows covering seven defects,
five synthetic). Each cell gives the frozen grader v1 first, then grader v2.

| Workflow | Values within tolerance / graded | Correct decisions | Caveat missing | False proceed | False refusal |
|---|---|---|---|---|---|
| Basic Python | 7/14 · 7/14 | 3 · 3 | 4 · 4 | 11 · 11 | 0 · 0 |
| Validated Python | 13/13 · 13/13 | 18 · 18 | 0 · 0 | 0 · 0 | 0 · 0 |
| Ocean-MCP 0.3.0 candidate, before fixesᵃ | 12/12 · 12/12 | 15 · 16 | 1 · 1 | 1 · 0 | 0 · 0 |
| Ocean-MCP 0.3.0 candidate, after fixesᵇ | 12/13 · 13/13 | 16 · 18 | 1 · 0 | 1 · 0 | 0 · 0 |
| stofs-mcp 0.2.0ᶜ | 2/6 · 2/6 | 3 · 3 | 2 · 2 | 12 · 12 | 1 · 1 |

Notes:

- **ᵃ Before fixes:** R7 was not run, because no candidate wave tool existed.
- **ᵇ After fixes:** the release candidate is stofs-mcp 0.3.0 with the coordinate and units fixes,
  erddap-mcp 0.1.3 and ww3-mcp 0.1.3.
- **ᶜ stofs-mcp 0.2.0:** in 7 rows its values are "not supported", because it has no lead-time
  window.
- **Correct decisions** count three outcomes: correct proceed, correct proceed with the required
  caveat, and correct refusal naming the cause.
- **Both graders** use the same references and tolerances. The five v2 corrections are listed in
  §1.3a.

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
| C-post (WP1b) | stofs-mcp 0.3.0 post-fix (`ba4edc2e…be9a`), erddap-mcp 0.1.3 (`b7c6d76b…9739`), ww3-mcp 0.1.3 (`7d359c4f…bf17`), coops-mcp 0.1.1 | 18 |

- All 53 sessions (35 in WP1, 18 for C-post in WP1b) use mcp 1.30.0 and Python 3.13.12, and all
  were valid.
- The Phase 0 sessions are listed in `DESIGN.md` §1.
- **Not run through MCP:** R7 for the pre-fix arm C, which had no candidate at Phase 2 start. R7
  with the later ww3-mcp wheel `ff7cf07a…` was not run either.
- **First repeat (WP1):** `run_all.sh` repeated all WP1 sessions offline with identical answers
  and grades.
- **WP1b repeat, after a WSL crash.** The crash wiped the scratch environments, so all eight
  environments were rebuilt from `environment/*.freeze.txt` with uv-managed CPython 3.13.12. One
  `run_all.sh` then reran:
  - Phase 0, the references and arms A and B;
  - arms C and D, with the Phase 2 start state of no ww3 candidate;
  - arm C-post;
  - all gradings and tables.
  Every result, reference and synthetic file came out byte-identical to commit `03509ee`. The log
  is in `verification_post_wp1/logs/run_all_repeat_after_crash.log` in the main checkout.

## 9. Preservation

**WP1c (checked on 2026-11-09, after commit `3a3ccd3`):**

- **Reproduction before v2.** `run_all.sh` reproduced every archived output byte for byte before
  any v2 work: 53 valid sessions, and no tracked result, answer, reference or archive file differed
  from `45c68df`. The log is in `verification_post_wp1/logs/run_all_wp1c_before_v2.log`.
- **Reproduction after v2.** The extended `run_all.sh` (step 9: v2 self-tests, fairness check, v2
  tables) then reproduced the sessions, the v1 grading and the v2 grading byte-identically to
  `3a3ccd3`. The log is in `…/run_all_wp1c_with_v2.log`. Run logs carry new time stamps only; they
  were restored to their committed versions.
- **v1 untouched.** The v1 grader (`grader/*.py`), task definitions, references, arms, replay
  archive, synthetic files, run logs and all v1 result files are byte-identical to `45c68df`. The
  WP1c commits add only `grader/v2/`, 12 new `results/*v2*` files, and edits to `REPORT.md`,
  `README.md` and `run_all.sh`.
- **No remote operation.** Nothing was pushed, pulled, fetched, merged, rebased, tagged or
  published. There are 44 tags and 0 stashes, `eval/safeguards-comparison` has no upstream, and
  `origin/main` is still `53fe506`.
- **No MCP session was added for WP1c.** The sessions run by `run_all.sh` replayed the archive
  without network, as before.

**WP1b (checked on 2026-11-09, before the commit that adds this revision):**

- **Existing branches and worktrees:** all unchanged. The only new commits on an existing branch
  are the permitted ones on `eval/safeguards-comparison`, all under
  `verification_safeguards_comparison/`.
- **New branches, each in its own new worktree, none with an upstream:**
  - `fix/stofs-post-wp1` (`52c7f46`, from `fix/stofs-release-prep` `db234f7`, changes only under
    `servers/stofs-mcp/`);
  - `fix/erddap-griddap-units` (`2567537`, `3834480`, from `origin/main` `53fe506`, changes only
    under `servers/erddap-mcp/`).

  The automatically set upstream of the erddap branch was removed.
- **State checked:**
  - main checkout `b562bf4`, no tracked changes;
  - `fix/stofs-release-prep` `db234f7`, unchanged;
  - 44 tags, 0 stashes.
- **Checksums unchanged:**
  - the Boston raw files;
  - WP0's manifest and wheel;
  - WP0b's ww3-mcp wheel;
  - the manuscript DOCX.

  Nothing under `verification_release_readiness/` or `verification_ww3_history_fix/` was edited.
- **No remote operation:** nothing was pushed, pulled, fetched, merged, rebased, tagged or
  published.
- **Not this session's work:** these worktrees appeared during WP1b from other sessions:
  - `readme-vdatum`;
  - `ww3-history-fix`;
  - `ww3-interval-fix` (now `4171783`);
  - `rtofs-rename`;
  - `usgs-nodata`.

  This session did not touch them.
- **Network use in WP1b:** none by any MCP session, and no NOAA download. The only downloads were
  package installs from PyPI while building environments.

**WP1, run after the WP1 commit:**

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

## Appendix B. Arm C-post (WP1b): text behind every decision grade (primary grading)

Generated from `results/wp1b_decision_evidence_Cpost.md`.

Where a grade was given because something was absent, the output's complete notes and reported exclusions follow.

**N1 / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N2 / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**N3 / C-post: correct_proceed**
- trigger: `obs MLLW / predictions MLLW`

**N4 / C-post: correct_proceed**
- trigger: (no text: correct proceed with no caveat required)

**R1a / C-post: correct_proceed_with_caveat**
- trigger: `named: 9751364, 9751401, 9751381, 9752695, 9752235`

**R1b / C-post: correct_refusal_or_flag**
- trigger: `No usable STOFS values for station 9751381 in this cycle: all 1200 records were excluded `

**R2 / C-post: false_proceed**
- trigger: `value beyond 30.0 m: ['n_values=1813']`

**R3 / C-post: correct_proceed_with_caveat**
- trigger: `named: SA816`

**R4a / C-post: correct_proceed**
- trigger: `observation datum NAVD88 (required NAVD88)`

**R4b / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

**R5 / C-post: correct_proceed_with_caveat**
- trigger: `NOAA documentation (STOFS_2D_GLOBAL V3.1.0: NOMADS STOFS-Global description (archived 2026-11-04): station and gridded output referenced to LMSL); file label zeta:standard_name=sea_surface_height_above_geoid names no specific datum`

**R6 / C-post: correct_proceed_with_caveat**
- trigger: `coordinate_warning: 105 of 108 station records in this file store latitude in x and longitude in y, the reverse of their attributes; their coordinates were swapped (rule: a record reading as`

**R7 / C-post: proceed_caveat_missing**
- trigger: `no excluded_records`
- output notes (complete): `hint: Only the most recent 5000 rows are returned (max_records, up to 5000). The summary statistics are computed over every row of the file.`
- exclusions recorded by the frozen adapter: `[]`
- A3 value trigger, frozen: `maximum WVHT over the 5000 returned rows = 5.35 (row time 2024-12-15 17:40)`
- A3 value trigger, amended: `summary: {"units": "m", "covers": "all 52692 rows of the file", "missing": 35235, "valid": 17457, "max": 6.32, "max_time": "2024-10-10 08:10"}`

**S1 / C-post: correct_refusal_or_flag**
- trigger: `No comparison: the vertical datum of the STOFS values for station 8443970 could not be established. The file name`

**S2 / C-post: correct_refusal_or_flag**
- trigger: `alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`
- A2 lenient: correct_refusal_or_flag (`alues for station 8443970 could not be established. The file's datum attributes contradict each other (zeta:standard_name=sea_surface_height_above_msl; zeta:long_name=wat`)

**S3 / C-post: correct_refusal_or_flag**
- trigger: `s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`
- A2 lenient: correct_refusal_or_flag (`s no specific vertical datum and no documented default applies: STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented (documented: STOFS_2D_GLOB`)

**S4 / C-post: correct_proceed_with_caveat**
- trigger: `observation exclusions [2, 3]`

**S5 / C-post: correct_proceed_with_caveat**
- trigger: ` | CO-OPS datum: MSL. No vertical transformation is applied. Matching labels do not guarantee identical realizations or epochs, so a mean offset (bias) alone does not show w`

## Appendix C. Section 6 as proposed in WP1 (superseded by the WP1b revision)

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

## Appendix D. Section 6 as proposed in WP1b (superseded by the WP1c revision)

The text is revised because the release candidate's counts changed after the approved fixes. The
WP1 version (208 words) is kept, superseded, in Appendix C.

> We compared four workflows on 18 predeclared task rows built from archived NOAA files: four
> nominal tasks, seven defects present in real operational files and five labelled synthetic
> mutations. Each row was graded separately on values, metadata, and the decision to compare,
> exclude or decline (Table X). Basic Python, with library defaults and one fixed documented datum
> pairing, reproduced the nominal statistics but proceeded falsely in 11 rows. It ranked 10^7 m
> no-data codes as the highest water levels, compared a NAVD88 cycle with mean-sea-level
> observations, chose a station 1,772 km away because coordinates were stored reversed, and compared
> files whose datum labels were missing or contradictory. A validated Python workflow, written from
> NOAA documentation and physical bounds, made the reference decision in all 18 rows. The evaluation
> exposed three defects in the Ocean-MCP release candidate, now fixed: an unreported coordinate
> correction, missing units, and wave-height fill codes returned as data. After the fixes, the
> candidate, run through MCP on the same archived bytes, returned every value within tolerance (R7
> read from its stated maximum) and matched the validated workflow on all 18 decisions read plainly;
> the frozen grader, misreading two responses, scores 16. The released stofs-mcp 0.2.0 made 12 false
> proceeds. The safeguards are not beyond a careful script: Ocean-MCP's contribution is validated
> checks made reusable through MCP. One author wrote every workflow; the task set is small.

**Table X.** Outcomes over 18 task rows (four nominal, nine real-file rows covering seven defects,
five synthetic).

| Workflow | Values within tolerance / graded | Correct decisions | Caveat missing | False proceed | False refusal | Not run or not supported |
|---|---:|---:|---:|---:|---:|---|
| Basic Python | 7 / 14 | 3 | 4 | 11 | 0 | – |
| Validated Python | 13 / 13 | 18 | 0 | 0 | 0 | – |
| Ocean-MCP 0.3.0 candidate, before fixes (MCP) | 12 / 12 | 15 (16)ᵃ | 1 | 1 (0)ᵃ | 0 | R7: candidate not available |
| Ocean-MCP 0.3.0 candidate, after fixes (MCP) | 12 / 13 (13 / 13)ᵇ | 16 (18)ᵃ | 1 (0)ᵃ | 1 (0)ᵃ | 0 | – |
| stofs-mcp 0.2.0 (MCP) | 2 / 6 | 3 | 2 | 12 | 1 | 7 rows: values not supported |

Notes:

- **ᵃ Plain reading** (§1.3, §1.5):
  - The grader scores R2 as a false proceed because it counts a record count as a water level.
  - After the fixes, it also scores R7 as "caveat missing", because ww3-mcp 0.1.3 reports its
    exclusions under key names the frozen adapter does not read.
- **ᵇ Under amendment A3:** R7 is read from the maximum the response states.
- **The "after fixes" row** combines three packages:
  - stofs-mcp 0.3.0 with D1 and D2 (`52c7f46`);
  - erddap-mcp 0.1.3 (`3834480`);
  - ww3-mcp 0.1.3 (WP0b `148f84c`).
- **Correct decisions** count three outcomes: correct proceed, correct proceed with the required
  caveat, and correct refusal naming the cause.
- **Values** are counted under amendment A1.
