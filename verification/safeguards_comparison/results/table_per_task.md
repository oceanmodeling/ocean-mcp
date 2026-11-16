# Per-task grades (primary: frozen references and grader)

Each cell: values / metadata / decision. [A1: …] shows the amended value where amendment A1 changes it. Arm D's nearest-equivalent values are shown for information and are not scored.

| Task | Class | Arm A | Arm B | Arm C | Arm D | Arm D nearest-equivalent values (UNSCORED) |
|---|---|---|---|---|---|---|
| N1 | nominal | within / correct / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / incomplete / proceed, caveat MISSING | n 541, bias -0.0028, RMSE 0.1164, MAE 0.0912, r 0.9939 |
| N2 | nominal | within / WRONG / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / WRONG / FALSE PROCEED | n 721, bias -0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
| N3 | nominal | within / correct / correct proceed | within / correct / correct proceed | within / correct / correct proceed | within / correct / correct proceed |  |
| N4 | nominal | within / correct / correct proceed | within / correct / correct proceed | within / incomplete / correct proceed | within / incomplete / correct proceed |  |
| R1a | real_defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / incomplete / correct proceed + caveat | OUTSIDE / WRONG / FALSE PROCEED |  |
| R1b | real_defect | n/a / correct / FALSE PROCEED | n/a / correct / correct refusal | n/a / n/a / correct refusal | n/a / WRONG / FALSE PROCEED | n 721, bias 9999999.3293, RMSE 9999999.3293, MAE 9999999.3293, r nan |
| R2 | real_defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / incomplete / FALSE PROCEED | OUTSIDE / incomplete / FALSE PROCEED |  |
| R3 | real_defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / incomplete / correct proceed + caveat | OUTSIDE / incomplete / FALSE PROCEED |  |
| R4a | real_defect | OUTSIDE / WRONG / FALSE PROCEED | within / correct / correct proceed | within / correct / correct proceed | not supported / incomplete / correct proceed | n 721, bias -0.1318, RMSE 0.2752, MAE 0.2198, r 0.9959 |
| R4b | real_defect | within / WRONG / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / WRONG / FALSE PROCEED | n 721, bias 0.0473, RMSE 0.2276, MAE 0.194, r 0.9946 |
| R5 | real_defect | n/a / correct / correct proceed + caveat | n/a / correct / correct proceed + caveat | n/a / incomplete / correct proceed + caveat | n/a / incomplete / proceed, caveat MISSING |  |
| R6 | real_defect | OUTSIDE / n/a / FALSE PROCEED | within / n/a / correct proceed + caveat | within / n/a / proceed, caveat MISSING | not returned / n/a / FALSE REFUSAL |  |
| R7 | real_defect | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | cand. n/a / cand. n/a / cand. n/a | OUTSIDE / incomplete / FALSE PROCEED |  |
| S1 | synthetic | within / correct / FALSE PROCEED | not returned [A1: n/a] / correct / correct refusal | not returned [A1: n/a] / incomplete / correct refusal | not supported / WRONG / FALSE PROCEED | n 721, bias -0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
| S2 | synthetic | n/a / WRONG / FALSE PROCEED | n/a / correct / correct refusal | n/a / correct / correct refusal | n/a / WRONG / FALSE PROCEED | n 721, bias -0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
| S3 | synthetic | n/a / WRONG / FALSE PROCEED | n/a / correct / correct refusal | n/a / correct / correct refusal | n/a / WRONG / FALSE PROCEED | n 541, bias -0.0028, RMSE 0.1164, MAE 0.0912, r 0.9939 |
| S4 | synthetic | OUTSIDE / correct / FALSE PROCEED | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / incomplete / FALSE PROCEED | n 539, bias nan, RMSE nan, MAE nan, r nan |
| S5 | synthetic | within / WRONG / proceed, caveat MISSING | within / correct / correct proceed + caveat | within / correct / correct proceed + caveat | not supported / WRONG / FALSE PROCEED | n 721, bias -0.013, RMSE 0.2149, MAE 0.1864, r 0.9886 |
