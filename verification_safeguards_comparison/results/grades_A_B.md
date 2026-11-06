# Grades, arms A, B

| Task | Class | Arm | Values | Metadata (strict) | Decision |
|---|---|---|---|---|---|
| N1 | nominal | A | within_tolerance | correct (correct) | proceed_caveat_missing |
| N1 | nominal | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| N2 | nominal | A | within_tolerance | wrong (wrong) | proceed_caveat_missing |
| N2 | nominal | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| N3 | nominal | A | within_tolerance | correct (correct) | correct_proceed |
| N3 | nominal | B | within_tolerance | correct (correct) | correct_proceed |
| N4 | nominal | A | within_tolerance | correct (correct) | correct_proceed |
| N4 | nominal | B | within_tolerance | correct (correct) | correct_proceed |
| R1a | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R1a | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R1b | real_defect | A | not_applicable | correct (correct) | false_proceed |
| R1b | real_defect | B | not_applicable | correct (correct) | correct_refusal_or_flag |
| R2 | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R2 | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R3 | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R3 | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R4a | real_defect | A | outside_tolerance | wrong (wrong) | false_proceed |
| R4a | real_defect | B | within_tolerance | correct (correct) | correct_proceed |
| R4b | real_defect | A | within_tolerance | wrong (wrong) | proceed_caveat_missing |
| R4b | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R5 | real_defect | A | not_applicable | correct (correct) | correct_proceed_with_caveat |
| R5 | real_defect | B | not_applicable | correct (correct) | correct_proceed_with_caveat |
| R6 | real_defect | A | outside_tolerance | not_applicable (not_applicable) | false_proceed |
| R6 | real_defect | B | within_tolerance | not_applicable (not_applicable) | correct_proceed_with_caveat |
| R7 | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R7 | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| S1 | synthetic | A | within_tolerance | correct (correct) | false_proceed |
| S1 | synthetic | B | not_returned | correct (correct) | correct_refusal_or_flag |
| S2 | synthetic | A | not_applicable | wrong (wrong) | false_proceed |
| S2 | synthetic | B | not_applicable | correct (correct) | correct_refusal_or_flag |
| S3 | synthetic | A | not_applicable | wrong (wrong) | false_proceed |
| S3 | synthetic | B | not_applicable | correct (correct) | correct_refusal_or_flag |
| S4 | synthetic | A | outside_tolerance | correct (correct) | false_proceed |
| S4 | synthetic | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| S5 | synthetic | A | within_tolerance | wrong (wrong) | proceed_caveat_missing |
| S5 | synthetic | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |

## Counts per arm

**Arm A**
- values: not_applicable 4, outside_tolerance 7, within_tolerance 7
- metadata: correct 11, not_applicable 1, wrong 6
- metadata_strict: correct 11, not_applicable 1, wrong 6
- decision: correct_proceed 2, correct_proceed_with_caveat 1, false_proceed 11, proceed_caveat_missing 4

**Arm B**
- values: not_applicable 4, not_returned 1, within_tolerance 13
- metadata: correct 17, not_applicable 1
- metadata_strict: correct 17, not_applicable 1
- decision: correct_proceed 3, correct_proceed_with_caveat 11, correct_refusal_or_flag 4

