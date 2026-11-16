# Counts per arm and axis, grader v1 and grader v2 side by side (18 rows per arm; no composite score)

v1: grader/grade.py; v2: grader/v2/grade_v2.py; both on the references with amendment A1.

## values

| Outcome | A basic Python v1 | v2 | B validated Python v1 | v2 | C 0.3.0 pre-fix v1 | v2 | C-post 0.3.0 post-fix v1 | v2 | D 0.2.0 v1 | v2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| within_tolerance | 7 | 7 | 13 | 13 | 12 | 12 | 12 | 13 | 2 | 2 |
| outside_tolerance | 7 | 7 | 0 | 0 | 0 | 0 | 1 | 0 | 4 | 4 |
| not_returned | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| not_applicable | 4 | 4 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 4 |
| not_supported | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 7 |
| candidate_not_available | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

## metadata

| Outcome | A basic Python v1 | v2 | B validated Python v1 | v2 | C 0.3.0 pre-fix v1 | v2 | C-post 0.3.0 post-fix v1 | v2 | D 0.2.0 v1 | v2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| correct | 11 | 11 | 17 | 17 | 9 | 10 | 14 | 16 | 1 | 1 |
| incomplete | 0 | 0 | 0 | 0 | 6 | 5 | 1 | 0 | 8 | 8 |
| wrong | 6 | 6 | 0 | 0 | 0 | 0 | 1 | 0 | 8 | 8 |
| not_applicable | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 1 | 1 |
| candidate_not_available | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

## metadata_strict

| Outcome | A basic Python v1 | v2 | B validated Python v1 | v2 | C 0.3.0 pre-fix v1 | v2 | C-post 0.3.0 post-fix v1 | v2 | D 0.2.0 v1 | v2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| correct | 11 | 11 | 17 | 17 | 7 | 10 | 12 | 16 | 1 | 1 |
| incomplete | 0 | 0 | 0 | 0 | 8 | 5 | 3 | 0 | 8 | 8 |
| wrong | 6 | 6 | 0 | 0 | 0 | 0 | 1 | 0 | 8 | 8 |
| not_applicable | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 1 | 1 |
| candidate_not_available | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

## decision

| Outcome | A basic Python v1 | v2 | B validated Python v1 | v2 | C 0.3.0 pre-fix v1 | v2 | C-post 0.3.0 post-fix v1 | v2 | D 0.2.0 v1 | v2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| correct_proceed | 2 | 2 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| correct_proceed_with_caveat | 1 | 1 | 11 | 11 | 8 | 9 | 9 | 11 | 0 | 0 |
| correct_refusal_or_flag | 0 | 0 | 4 | 4 | 4 | 4 | 4 | 4 | 0 | 0 |
| proceed_caveat_missing | 4 | 4 | 0 | 0 | 1 | 1 | 1 | 0 | 2 | 2 |
| false_proceed | 11 | 11 | 0 | 0 | 1 | 0 | 1 | 0 | 12 | 12 |
| false_refusal | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| candidate_not_available | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

## Changed cells per arm (v1 -> v2)

| Arm | values | metadata | metadata strict | decision | total |
|---|---:|---:|---:|---:|---:|
| A basic Python | 0 | 0 | 0 | 0 | 0 |
| B validated Python | 0 | 0 | 0 | 0 | 0 |
| C 0.3.0 pre-fix | 0 | 1 | 3 | 1 | 5 |
| C-post 0.3.0 post-fix | 1 | 2 | 4 | 2 | 9 |
| D 0.2.0 | 0 | 0 | 0 | 0 | 0 |
