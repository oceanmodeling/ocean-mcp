# Rows where a plain reading of the output disagrees with the grader

The grader is not changed. Each row gives the grader's value (primary grading), the plain reading and why.

| Task | Arm | Axis | Grader | Plain reading | Why |
|---|---|---|---|---|---|
| R2 | C | decision | false_proceed | correct_proceed_with_caveat | The frozen predicate 'value_beyond_bound' tests every numeric field of the answer's values. The frozen station adapter adds n_values (the number of values the tool returned, 1,813) to values, and 1,813 > 30, so the predicate fires. The water level the tool returned is min -0.109 m (within tolerance), and the tool reports excluded_model_records sentinel = 47, the reference count. Read plainly, stofs-mcp 0.3.0 excluded the 47 shifted dry values, reported them and gave the right minimum. |
| S1 | C | metadata | incomplete | correct | The tool declined, stating that the vertical datum 'could not be established'. The frozen adapter maps this to model_datum = 'undetermined' with no source (a refusal text has no source field), and the S1 source rule asks for a source before it looks at the value. For an undetermined datum no source is meaningful; read plainly, the metadata statement is correct. |

## Notes on grades that are right but need context

- **R6 / arm D**: stofs-mcp 0.2.0 declined ('No STOFS station found within 50.0 km'). The cause is the reversed coordinates it does not detect; the Boston record is in the file. Graded false refusal: the question was answerable.
- **N1 / arm D**: stofs-mcp 0.2.0's JSON response carries no datum note; its markdown response (not requested) says 'small systematic offsets (1-5 cm) are expected'. The grade reflects the JSON requested.
- **R4a / arm D**: stofs-mcp 0.2.0 hard-codes NAVD88/NAVD for STOFS-3D. That is correct for this v2.1.18 cycle and wrong for the v3.1 cycles (R4b, N2, S5).
- **R7 / arm D**: ww3-mcp 0.1.2 returns 5,270 of 52,692 rows (every 10th); 3,520 of them show WVHT 99.0. The true maximum (6.32 m) is not in the subsample; the largest valid value returned is 5.6 m, so even a missing-value fix alone would not give the reference value.
- **S4 / arm D**: stofs-mcp 0.2.0 returned bias, RMSE, MAE and r as NaN (and its JSON contains NaN tokens, which strict JSON parsers reject).
