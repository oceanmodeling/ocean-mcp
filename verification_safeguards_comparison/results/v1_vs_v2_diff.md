# Every cell whose grade differs between grader v1 and grader v2

v1: grader/grade.py with amendment A1 references. v2: grader/v2/grade_v2.py, same references. 'Change' is the CHANGES.md item that, enabled alone, produces the v2 grade.

| Arm | Task | Axis | v1 | v2 | Change |
|---|---|---|---|---|---|
| C | R2 | decision | false_proceed | correct_proceed_with_caveat | 1 (value-bound predicate: water-level fields only) |
| C | S1 | metadata | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C | S1 | metadata_strict | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C | S2 | metadata_strict | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C | S3 | metadata_strict | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C-post | R2 | decision | false_proceed | correct_proceed_with_caveat | 1 (value-bound predicate: water-level fields only) |
| C-post | R7 | values | outside_tolerance | within_tolerance | 5 (R7 value: the maximum the response states (A3)) |
| C-post | R7 | metadata | wrong | correct | 3 (per-column units: the graded column's unit) |
| C-post | R7 | metadata_strict | wrong | correct | 3 (per-column units: the graded column's unit) |
| C-post | R7 | decision | proceed_caveat_missing | correct_proceed_with_caveat | 4 (excluded counts read under every key name used for R7) |
| C-post | S1 | metadata | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C-post | S1 | metadata_strict | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C-post | S2 | metadata_strict | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |
| C-post | S3 | metadata_strict | incomplete | correct | 2 (no datum-source requirement for a refusal naming the cause) |

Changed cells per arm: A 0, B 0, C 5, C-post 9, D 0

Fairness check: PASSED (baseline reproduces the published v1 file; v2 with every change off reproduces v1 and the archived answers; 14 changed cells, 0 unexplained).
