#!/usr/bin/env python3
"""POST HOC, NOT PRE-REGISTERED: influence of the single riverine leverage station 8764044
(Berwick, Atchafalaya River; X = -0.45 m driven by river stage) on the Study 2 regressions.
Reported beside, never instead of, the frozen results. Same functions as study2_regression."""
import csv, json, sys
from pathlib import Path
PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "analysis"))
import study2_regression as s2  # noqa: E402

DROP = "8764044"
NUM = {"lat", "lon", "n_cycles", "bias_mean", "bias_sd", "model_mean", "obs_mean", "X", "O12_pre_period",
       "n_months_pre_period", "S_seasonal", "O12", "n_O12", "O12_plus_S", "O29", "n_O29"}


def load(name):
    rows = []
    for r in csv.DictReader(open(PKG / "results/study2" / name)):
        for k in NUM:
            r[k] = float(r[k]) if r.get(k) not in (None, "") else None
        r["boundary_station"] = r["boundary_station"] == "True"
        rows.append(r)
    return rows


out = {}
post3d = load("station_table_3d_post.csv")
for label, rows in (("3d_post", post3d), ("3d_pre", load("station_table_3d_pre.csv")),
                    ("2d_noanomaly_same_stations", [r for r in load("station_table_2d_noanomaly_post_all.csv")
                                                     if r["station_id"] in {x["station_id"] for x in post3d}])):
    kept = [r for r in rows if r["station_id"] != DROP]
    for name, rr in (("all", rows), (f"without_{DROP}", kept)):
        a = s2.analyse(rr, "X")
        out[f"{label}_{name}"] = {k: a.get(k) for k in ("n_stations", "slope", "slope_ci", "intercept", "intercept_ci",
                                                       "theil_sen", "carried_fraction_ci", "slope_reading", "verdict",
                                                       "verdict_cluster_bootstrap", "level_test_mean_bias_plus_offset")}
(PKG / "results/study2/posthoc_leverage.json").write_text(json.dumps(out, indent=1) + "\n")
for k, v in out.items():
    print(k, v["n_stations"], round(v["slope"], 3), [round(x, 2) for x in v["slope_ci"]], "TS", round(v["theil_sen"]["slope"], 3), v["verdict"])
