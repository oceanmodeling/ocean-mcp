| Metric | Definition | Unit | 2D forecast | 3D forecast | 2D nowcast | 3D nowcast |
|---|---|---|---:|---:|---:|---:|
| Matched pairs | count of exact-timestamp pairs |  | 480 | 480 | 60 | 240 |
| Mean bias | mean(e) | m | −0.0005 | −0.1430 | −0.0182 | −0.0295 |
| RMSE | sqrt(mean(e^2)) | m | 0.123 | 0.246 | 0.024 | 0.225 |
| MAE | mean(\|e\|) | m | 0.100 | 0.209 | 0.020 | 0.200 |
| Centred RMSE | sqrt(mean((e − mean(e))^2)) | m | 0.123 | 0.200 | 0.015 | 0.223 |
| Pearson r | cov(M,O)/(sd(M) sd(O)) |  | 0.9934 | 0.9913 | 0.9999 | 0.9866 |
| Max \|e\| | max(\|e\|) | m | 0.266 | 0.535 | 0.057 | 0.398 |
| max(M) − max(O) | max(M) − max(O) | m | −0.067 | +0.013 | −0.004 | +0.071 |
| sd(M)/sd(O) | ratio of population standard deviations |  | 1.007 | 1.125 | 1.006 | 1.095 |
| Best-correlated lag | lag maximizing r(M(t+lag), O(t)), 6-min steps | min | −12 | +12 | 0 | +18 |

e = model − observed. Forecast window: 0 < lead ≤ 48 h (same 480 valid times for both models). Nowcast windows differ (6 h vs 24 h) and are not comparable.
