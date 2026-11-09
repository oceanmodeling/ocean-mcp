# Grader v2: what it changes from v1

## What v1 and v2 are

- **v1** is the frozen grader: `grader/grade.py` and `grader/adapters.py`, as committed in
  `5d84c13`. It is unchanged, and every v1 result file stays in the record.
- **v2** is `grader/v2/grade_v2.py`. It imports v1 and re-uses every v1 rule, pattern, predicate
  and adapter. It differs only in the five places listed below.
- **Both use the same references.** These are `references/references.amended.json`: the frozen
  references with amendment A1, the S1 values-kind bug recorded before arms C and D ran.
- **Each change can be switched off.** With all five off, v2 reproduces every v1 grade and every
  archived answer, as `fairness_check.py` verifies.

## What did not change

- the task statements and definitions (`tasks/tasks.json`);
- the reference values and outcomes (`references/`);
- the tolerances and decision categories;
- the caveat and cause patterns, and every other predicate;
- the arms, their code and their archived outputs;
- the replay archive.

## The five changes

### Change 1. Value-bound predicate (R2)

**v1.** The predicate `value_beyond_bound` (`grade.py`, `false_proceed`) tests every numeric field
of an answer's `values` against the 30 m physical bound.

**v2.** It tests only water-level fields: real-valued fields whose name ends in `_m` (metres).
Every other field that occurs in any arm's values is excluded by name. The list is exhaustive for
the archived outputs:

| Field | What it is |
|---|---|
| `n` | number of compared pairs (count) |
| `n_values` | number of values a tool returned (count) |
| `cells` | number of grid cells (count) |
| `finite` | number of finite cells (count) |
| `r` | Pearson correlation (dimensionless) |
| `distance_km` | distance to a station (km) |
| `min`, `max` | SST range (degree_C) |
| `station`, `time`, `times_utc`, `top` | text, time stamps, lists |

Booleans are excluded by type. The predicate is used by R2 and R7 only.

**v1 grades affected:**

| Arm | Row | v1 → v2 | v1 triggering text (Appendix A/B) |
|---|---|---|---|
| C | R2, decision | false proceed → correct proceed + caveat | `value beyond 30.0 m: ['n_values=1813']` |
| C-post | R2, decision | false proceed → correct proceed + caveat | `value beyond 30.0 m: ['n_values=1813']` |

Under v2, the caveat check (unchanged) then finds the reported exclusion,
`excluded_model_records.sentinel = 47`.

**Not affected:** arms A and D. Their R2 answer is a real −99,998.6 m level, which still fails,
with v1 trigger `value beyond 30.0 m: ['min_m=-99998.6'...]`.

**Why this was a grader defect.**
- The bound is a physical limit on water levels; a count of returned values is not a water level.
- `n_values` was added to the answer by the frozen station adapter itself, as context. It is not
  a value the tool reported as a level.
- The task (R2: "the lowest water level") and its reference (−0.109 m) concern a level only.

### Change 2. Source rule for refusals (S1, and the strict column of S2/S3)

**v1.** For the datum, the metadata axis asks for a stated source before it considers the value.
A tool that declines, saying the datum "could not be established", is recorded as datum
`undetermined` with no source field, and graded "incomplete". In the strict column the same
happens for S2 and S3.

**v2.** When the arm refused and its refusal names the cause (decision `correct_refusal_or_flag`,
detected by the unchanged cause patterns), the metadata axis does not additionally require a
datum source field. This applies to the primary and the strict column.
- A proceed still requires the source.
- A refusal that does not name the cause keeps v1's rule.

**v1 grades affected:**

| Arm | Row | v1 → v2 | v1 triggering text |
|---|---|---|---|
| C, C-post | S1, metadata (and strict) | incomplete → correct | `model_datum source not stated` |
| C, C-post | S2, metadata strict | incomplete → correct | `strict: no source for model_datum` |
| C, C-post | S3, metadata strict | incomplete → correct | `strict: no source for model_datum` |

The refusal texts that name the cause:
- **S1:** `No comparison: the vertical datum of the STOFS values for station 8443970 could not be established.`
- **S2:** `… The file's datum attributes contradict each other …`
- **S3:** `… STOFS_2D_GLOBAL V4.0.0 is not a version whose station datum is documented …`

**Not affected:** arm B. Its refusals state a source, so they are correct under both versions.

**Why this was a grader defect.** A source is evidence for a stated datum. A refusal states that
no datum can be established, which is the reference outcome. There is no datum whose source could
be given, so asking for one penalises the correct answer for lacking a field that cannot exist.

### Change 3. Units given per column (R7 metadata)

**v1.** The units value is compared with the expected unit as a whole. A response that gives units
per column, such as `{"WVHT": "m", "TIDE": "ft", …}`, fails as `wrong`.

**v2.** A per-column units map satisfies the requirement when the column the task grades carries
the expected unit.
- **The graded column** is a property of the task statement: R7 grades `WVHT`; N4 grades
  `analysed_sst`.
- **If the graded column is absent** from the map, the units are "not stated" (incomplete).
- **If it carries another unit,** they are "wrong".

**v1 grades affected:**

| Arm | Row | v1 → v2 | v1 triggering text |
|---|---|---|---|
| C-post | R7, metadata (and strict) | wrong → correct | `units={'WDIR': 'degT', 'WSPD': 'm/s', 'GST': 'm/s', 'WVHT': 'm', …}` |

**Not affected:** no other arm gives a map for a graded task. The erddap-mcp 0.1.3 map for N4 was
already read at `analysed_sst` by the v1 adapter.

**Why this was a grader defect.** The units requirement concerns the graded quantity. A map that
states "m" for `WVHT` states the graded quantity's unit exactly. Comparing the whole map with one
string tests the response's layout, not its content.

### Change 4. Excluded-count detection (R7 decision)

**v1.** For R7, the frozen adapter looks for exclusion counts only under the top-level keys
`excluded`, `excluded_values`, `missing` and `excluded_records`.

**v2.** The R7 adapter reads excluded or missing counts under every key name used by any arm's R7
output:
- the four v1 keys;
- top-level `excluded_counts`;
- `summary.missing`;
- `missing_values.excluded_counts`.

A per-column count map is read at the graded column (`WVHT`) only. Arms A and B produce their
exclusions directly in the answer file (`exclusions`), which v1 already reads. ww3-mcp 0.1.2 (arm D)
reports no count under any name.

**v1 grades affected:**

| Arm | Row | v1 → v2 | v1 triggering text |
|---|---|---|---|
| C-post | R7, decision | proceed, caveat missing → correct proceed + caveat | `no excluded_records` |

The v2 trigger is `counts [35235, 35235]`, from `summary.missing` and
`missing_values.excluded_counts.WVHT`.

**Not affected:** arm D (no count), arm A (none) and arm B (already correct).

**Why this was a grader defect.**
- The reference asks whether the exclusion of the 9-filled values is *reported*.
- ww3-mcp 0.1.3 reports it, with NDBC's rule, the codes and the count (35,235). It uses names the
  frozen adapter did not know, because they did not exist when the adapter was written.
- Recognising a report should depend on its content, not on one tool version's key names.

### Change 5. Answer selection (R7 values; amendment A3)

**v1.** The frozen adapter takes the maximum WVHT over the rows the response returns.

**v2.** The graded value is the maximum a response states as its answer to the task: a numeric
`summary.max` for the graded variable, with its time, when the response states one.
- A response that states no maximum is graded on the maximum over its returned rows. That is the
  only answer it gives.
- For arms A and B the answer is the value the script reports.
- The rule is the same for every arm.

**v1 grades affected:**

| Arm | Row | v1 → v2 | v1 triggering text |
|---|---|---|---|
| C-post | R7, values | outside tolerance → within tolerance | `max_wvht_m: 5.35 vs 6.32 (|d|=0.97 > 0.001)`, the maximum over the 5,000 most recent rows |

The v2 value is 6.32 m, from `summary.max`, with `max_time` 2024-10-10 08:10.

**Not affected:**
- arm D: ww3-mcp 0.1.2 states no maximum, so its 99.0 m over the returned rows is kept;
- arms A and B: they already report their stated value;
- arm C: candidate not available.

**Why this was a grader defect.**
- The task asks for "the highest significant wave height" in the year.
- ww3-mcp 0.1.3 answers it directly, computed over all 52,692 rows. It returns the most recent
  `max_records` rows as a separate, labelled sample.
- Grading the sample's maximum grades a quantity the response did not offer as its answer.
- v1's rule was adequate only for 0.1.2, whose returned rows were a stride through the whole year
  (amendment A3).

## Result of the fairness check

`results/v2_fairness_check.json` and `results/v1_vs_v2_diff.*`:

- The published v1 grades are reproduced from the archived answers.
- v2 with every change off reproduces every v1 grade and every archived answer.
- 14 cells differ:
  - 5 in arm C: 2 on the three graded axes, plus 3 in the strict-metadata column;
  - 9 in arm C-post: 5 on the three graded axes, plus 4 in the strict column;
  - 0 in arms A, B and D.
- Each difference is produced by exactly one change enabled alone, and none is unexplained.

**What the check does and does not show.** All five defects were identified after the v1 grades
were seen, and every misgraded cell belonged to an Ocean-MCP arm. The check shows that each
difference traces to a stated, generic change. It cannot show that the set of changes is free of
selection.
- **Known lenient grades, left as they are.** The WP1 report notes v1 grades that are correct for
  reasons unrelated to safeguards: arm A on R5 (its fixed documented pairing) and arm D on R4a
  (0.2.0 hard-codes NAVD88). v2 leaves them unchanged.
- **No systematic search** was made for v1 grades that are too lenient.
