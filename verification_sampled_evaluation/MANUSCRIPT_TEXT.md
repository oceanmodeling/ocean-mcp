# Proposed manuscript text (WP5)

## Text (200 words)

> The datum pairing needs a qualification. STOFS station output on local mean sea level and the
> CO-OPS mean-sea-level datum agree as datums (median difference 3.5 mm, SD 3.7 cm, 199
> stations). However, that datum refers to the 1983–2001 epoch. A mean bias against it
> therefore includes the rise since then, about +0.2 m, unless the model carries present-day
> level.
>
> We tested safeguards on 15,197 station-cycles chosen by a fixed rule: 30 cycles from June
> to November 2026, and every CO-OPS station in the STOFS files. Archived NOAA files were
> replayed through Ocean-MCP (Table X). The tool compared correctly in 9,948 cases
> and correctly declined 5,248: 105 invalid model series and 5,143 cases without usable
> observations. It made no false refusal and passed no invalid value or wrong pairing.
> One refusal message misattributes its cause.
>
> Across stations (Fig. X), the models without observation-based level correction showed bias
> falling with the offset:
> - STOFS-3D before v3.1: slope −0.72;
> - uncorrected STOFS-2D: slope −0.82.
>
> Bias-corrected STOFS-2D showed no dependence (−0.02 [−0.07, 0.03]). STOFS-3D v3.1 was
> inconclusive by our pre-registered rule (−0.01 [−0.52, 0.19]), with a network-mean bias of
> −0.006 m. Boston's −0.143 m equals its pre-v3.1 mean; over 15 v3.1 cycles it averaged
> −0.059 m.

## Table X

Outcomes on 15,197 station-cycles (lead 0–49.7 h) and the cross-station dependence of mean
bias on the offset since the datum epoch.

| | STOFS-3D v2.1 (NAVD88) | STOFS-3D v3.1 (LMSL) | STOFS-2D (LMSL, bias-corrected) |
|---|---:|---:|---:|
| Station-cycles | 1,590 | 2,445 | 11,162 |
| Correct comparison | 1,500 | 2,020 | 6,428 |
| Correct refusal (invalid model series) | 0 | 75 | 30 |
| Not eligible, declined (no usable observations) | 90 | 350 | 4,703 |
| False refusal / undetected problem | 0 / 0 | 0 / 0 | 0 / 0 |
| Other discrepancy (nearest-time pairing, < 1 cm) | 0 | 0 | 1 |
| Stations in the bias regression | 94 | 122 | 114 |
| Slope of mean bias on offset [95% CI] | −0.72 [−1.06, −0.50] | −0.01 [−0.52, 0.19] | −0.02 [−0.07, 0.03] |
| Mean bias / mean offset (m) | −0.101 / +0.156 | −0.006 / +0.215 | +0.001 / +0.215 |

Notes:
- **Offset:** recent mean sea level above the station's MSL datum, from CO-OPS observations
  only.
- **Uncorrected STOFS-2D** (`noanomaly`, same stations): slope −0.82 [−1.28, −0.74], mean bias
  −0.252 m.
- **One-author study:** the reference rules follow the same documentation as the tool.

## Figure X (`figures/bias_vs_offset.png`)

Station mean bias (model − observed, lead 0–49.7 h) against the offset since the datum epoch.
- **Left:** STOFS-3D-Atlantic v3.1, 122 stations.
- **Right:** STOFS-2D-Global, bias-corrected (filled) and uncorrected (open).
- **Markings:** diamonds are the 11 stations of the STOFS-3D open-boundary adjustment; the
  dashed line is bias = −offset.
