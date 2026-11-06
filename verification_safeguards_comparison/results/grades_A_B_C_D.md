# Grades, arms A, B, C, D

| Task | Class | Arm | Values | Metadata (strict) | Decision |
|---|---|---|---|---|---|
| N1 | nominal | A | within_tolerance | correct (correct) | proceed_caveat_missing |
| N1 | nominal | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| N1 | nominal | C | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| N1 | nominal | D | not_supported (nearest equivalent) | incomplete (incomplete) | proceed_caveat_missing |
| N2 | nominal | A | within_tolerance | wrong (wrong) | proceed_caveat_missing |
| N2 | nominal | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| N2 | nominal | C | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| N2 | nominal | D | not_supported (nearest equivalent) | wrong (wrong) | false_proceed |
| N3 | nominal | A | within_tolerance | correct (correct) | correct_proceed |
| N3 | nominal | B | within_tolerance | correct (correct) | correct_proceed |
| N3 | nominal | C | within_tolerance | correct (correct) | correct_proceed |
| N3 | nominal | D | within_tolerance | correct (correct) | correct_proceed |
| N4 | nominal | A | within_tolerance | correct (correct) | correct_proceed |
| N4 | nominal | B | within_tolerance | correct (correct) | correct_proceed |
| N4 | nominal | C | within_tolerance | incomplete (incomplete) | correct_proceed |
| N4 | nominal | D | within_tolerance | incomplete (incomplete) | correct_proceed |
| R1a | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R1a | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R1a | real_defect | C | within_tolerance | incomplete (incomplete) | correct_proceed_with_caveat |
| R1a | real_defect | D | outside_tolerance | wrong (wrong) | false_proceed |
| R1b | real_defect | A | not_applicable | correct (correct) | false_proceed |
| R1b | real_defect | B | not_applicable | correct (correct) | correct_refusal_or_flag |
| R1b | real_defect | C | not_applicable | not_applicable (not_applicable) | correct_refusal_or_flag |
| R1b | real_defect | D | not_applicable (nearest equivalent) | wrong (wrong) | false_proceed |
| R2 | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R2 | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R2 | real_defect | C | within_tolerance | incomplete (incomplete) | false_proceed |
| R2 | real_defect | D | outside_tolerance | incomplete (incomplete) | false_proceed |
| R3 | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R3 | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R3 | real_defect | C | within_tolerance | incomplete (incomplete) | correct_proceed_with_caveat |
| R3 | real_defect | D | outside_tolerance | incomplete (incomplete) | false_proceed |
| R4a | real_defect | A | outside_tolerance | wrong (wrong) | false_proceed |
| R4a | real_defect | B | within_tolerance | correct (correct) | correct_proceed |
| R4a | real_defect | C | within_tolerance | correct (correct) | correct_proceed |
| R4a | real_defect | D | not_supported (nearest equivalent) | incomplete (incomplete) | correct_proceed |
| R4b | real_defect | A | within_tolerance | wrong (wrong) | proceed_caveat_missing |
| R4b | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R4b | real_defect | C | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R4b | real_defect | D | not_supported (nearest equivalent) | wrong (wrong) | false_proceed |
| R5 | real_defect | A | not_applicable | correct (correct) | correct_proceed_with_caveat |
| R5 | real_defect | B | not_applicable | correct (correct) | correct_proceed_with_caveat |
| R5 | real_defect | C | not_applicable | incomplete (incomplete) | correct_proceed_with_caveat |
| R5 | real_defect | D | not_applicable | incomplete (incomplete) | proceed_caveat_missing |
| R6 | real_defect | A | outside_tolerance | not_applicable (not_applicable) | false_proceed |
| R6 | real_defect | B | within_tolerance | not_applicable (not_applicable) | correct_proceed_with_caveat |
| R6 | real_defect | C | within_tolerance | not_applicable (not_applicable) | proceed_caveat_missing |
| R6 | real_defect | D | not_returned | not_applicable (not_applicable) | false_refusal |
| R7 | real_defect | A | outside_tolerance | correct (correct) | false_proceed |
| R7 | real_defect | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| R7 | real_defect | C | candidate_not_available | candidate_not_available (candidate_not_available) | candidate_not_available |
| R7 | real_defect | D | outside_tolerance | incomplete (incomplete) | false_proceed |
| S1 | synthetic | A | within_tolerance | correct (correct) | false_proceed |
| S1 | synthetic | B | not_returned | correct (correct) | correct_refusal_or_flag |
| S1 | synthetic | C | not_returned | incomplete (incomplete) | correct_refusal_or_flag |
| S1 | synthetic | D | not_supported (nearest equivalent) | wrong (wrong) | false_proceed |
| S2 | synthetic | A | not_applicable | wrong (wrong) | false_proceed |
| S2 | synthetic | B | not_applicable | correct (correct) | correct_refusal_or_flag |
| S2 | synthetic | C | not_applicable | correct (incomplete) | correct_refusal_or_flag |
| S2 | synthetic | D | not_applicable (nearest equivalent) | wrong (wrong) | false_proceed |
| S3 | synthetic | A | not_applicable | wrong (wrong) | false_proceed |
| S3 | synthetic | B | not_applicable | correct (correct) | correct_refusal_or_flag |
| S3 | synthetic | C | not_applicable | correct (incomplete) | correct_refusal_or_flag |
| S3 | synthetic | D | not_applicable (nearest equivalent) | wrong (wrong) | false_proceed |
| S4 | synthetic | A | outside_tolerance | correct (correct) | false_proceed |
| S4 | synthetic | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| S4 | synthetic | C | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| S4 | synthetic | D | not_supported (nearest equivalent) | incomplete (incomplete) | false_proceed |
| S5 | synthetic | A | within_tolerance | wrong (wrong) | proceed_caveat_missing |
| S5 | synthetic | B | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| S5 | synthetic | C | within_tolerance | correct (correct) | correct_proceed_with_caveat |
| S5 | synthetic | D | not_supported (nearest equivalent) | wrong (wrong) | false_proceed |

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

**Arm C**
- values: candidate_not_available 1, not_applicable 4, not_returned 1, within_tolerance 12
- metadata: candidate_not_available 1, correct 9, incomplete 6, not_applicable 2
- metadata_strict: candidate_not_available 1, correct 7, incomplete 8, not_applicable 2
- decision: candidate_not_available 1, correct_proceed 3, correct_proceed_with_caveat 8, correct_refusal_or_flag 4, false_proceed 1, proceed_caveat_missing 1

**Arm D**
- values: not_applicable 4, not_returned 1, not_supported 7, outside_tolerance 4, within_tolerance 2
- metadata: correct 1, incomplete 8, not_applicable 1, wrong 8
- metadata_strict: correct 1, incomplete 8, not_applicable 1, wrong 8
- decision: correct_proceed 3, false_proceed 12, false_refusal 1, proceed_caveat_missing 2

