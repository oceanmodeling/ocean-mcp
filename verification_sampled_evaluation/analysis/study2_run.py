#!/usr/bin/env python3
"""Study 2 driver: runs the frozen analysis (study2_regression.py) on the Phase 2 reference
records, with the pre-registered controls and sensitivities (DESIGN.md 7.3-7.6) and amendments
A1-A4. Writes results/study2/{results.json, station_table_*.csv, tables.md} and
figures/bias_vs_offset.png. No Ocean-MCP import."""
from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "reference"))
sys.path.insert(0, str(PKG / "analysis"))
import archive_io as aio  # noqa: E402
import study2_regression as s2  # noqa: E402
from classify import epoch_class, load_datums  # noqa: E402

U = dt.timezone.utc
OUT = PKG / "results/study2"
POST = (dt.datetime(2026, 8, 17, 12, tzinfo=U), dt.datetime(2026, 11, 2, 12, tzinfo=U))
PRE = (dt.datetime(2026, 6, 1, 12, tzinfo=U), dt.datetime(2026, 8, 16, 12, tzinfo=U))
ALL = (PRE[0], POST[1])
S11 = (dt.datetime(2026, 8, 24, 12, tzinfo=U), POST[1])
DAILY_EXTRA = {"2026-08-18", "2026-08-19", "2026-08-20"}
PREV = {"2026-08-16", "2026-08-17"}
WIN_N = {"w49_7": 497, "w24_8": 248, "w48": 480}
SEP_MSG = "not separable: depends on whether the model carries the seasonal cycle"


def load_cases(name):
    p = PKG / "reference/results" / name / "cases.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else None


def inputs():
    monthly = {}
    for e in aio.Archive(PKG / "data/archive/refonly").entries:
        p = aio.params(e)
        if p.get("product") == "monthly_mean":
            d = json.loads(aio.Archive(PKG / "data/archive/refonly").body(e))
            monthly[p["station"]] = d.get("data", [])
    obs = aio.CoopsObs([aio.Archive(PKG / "data/archive/coops")])

    last = {"sid": None}

    def msl_records(sid, lo, hi):
        if (sid, "MSL") not in obs.masters:
            return []
        if sid != last["sid"]:
            obs.release(keep_station=sid)  # memory only
            last["sid"] = sid
        return obs.records(sid, "MSL", lo, hi)["records"]
    datums = load_datums([aio.Archive(PKG / "data/archive/meta")])
    ec = {s: epoch_class(m.get("epoch")) for s, m in datums.items()}
    meta = {}
    for p in sorted((PKG / "phase0/coops").glob("*.json")):
        d = json.loads(p.read_text())
        if isinstance(d, dict) and "stations" in d:
            for s in d["stations"]:
                meta.setdefault(s["id"], s)
    boundary = {s["id"] for s in json.loads((PKG / "reference/boundary_stations.json").read_text())["stations"]}
    a1 = json.loads((PKG / "results/a1/datum_consistency.json").read_text())
    dmap = {r["station_id"]: r["d_m"] for r in a1["rows"]}
    return monthly, msl_records, meta, ec, boundary, dmap


def table(cases, product, period, win, ctx, keep=lambda c: True):
    monthly, msl_records, meta, ec, boundary, _ = ctx
    return s2.station_table([c for c in cases if keep(c)], product, period, WIN_N[win], monthly, msl_records,
                            meta, ec, boundary)


def a2(rows, label):
    """Amendment A2: slope reading on X; carried fraction and level test under X and O12_pre."""
    vx = s2.analyse(rows, "X")
    vo = s2.analyse(rows, "O12_pre_period")
    res = {"label": label, "X": vx, "O12_pre": vo}
    if vx.get("slope_reading") == "minus_one":
        n = vx["n_stations"]
        v1 = s2.verdict(n, vx["slope_ci"], vx["carried_fraction_ci"])
        v2 = s2.verdict(n, vx["slope_ci"], vo.get("carried_fraction_ci"))
        res["verdict_A2"] = v1 if v1 == v2 else SEP_MSG
        res["verdicts_by_offset"] = {"X": v1, "O12_pre": v2}
    else:
        res["verdict_A2"] = vx.get("verdict")
    c1 = vx.get("verdict_cluster_bootstrap")
    res["robust"] = c1 == vx.get("verdict")
    return res


def pooled(rows):
    r2 = copy.deepcopy(rows)
    for r in r2:
        if r["epoch_class"] in ("NTDE_1983_2001", "modified_5yr"):
            r["epoch_class"] = "pooled"
    return r2


def write_rows(name, rows):
    if not rows:
        return
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def figure(post3d, post2d, noan, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, rows, title, r in ((axes[0], post3d, "STOFS-3D-Atlantic v3.1 (LMSL vs MSL)", res["primary"]["X"]),
                               (axes[1], post2d, "STOFS-2D-Global (LMSL vs MSL)", res["control_2d_same_stations"]["X"])):
        nt = [x for x in rows if x["X"] is not None and x["epoch_class"] == "NTDE_1983_2001"]
        ax.scatter([x["X"] for x in nt if not x["boundary_station"]], [x["bias_mean"] for x in nt if not x["boundary_station"]],
                   s=14, c="#4C72B0", label="NTDE stations")
        ax.scatter([x["X"] for x in nt if x["boundary_station"]], [x["bias_mean"] for x in nt if x["boundary_station"]],
                   s=30, marker="D", c="#DD8452", label="boundary-adjustment stations")
        if ax is axes[1] and noan:
            nn = [x for x in noan if x["X"] is not None and x["epoch_class"] == "NTDE_1983_2001"]
            ax.scatter([x["X"] for x in nn], [x["bias_mean"] for x in nn], s=10, facecolors="none",
                       edgecolors="#55A868", label="2D noanomaly (uncorrected)")
        xs = [x["X"] for x in nt] or [0, 0.3]
        lo, hi = min(xs) - 0.02, max(xs) + 0.02
        ax.plot([lo, hi], [-lo, -hi], "k--", lw=1, label="bias = −offset (H-epoch)")
        ax.axhline(0, color="0.5", lw=0.8)
        if r.get("slope") is not None and r.get("n_stations", 0) >= 3:
            ax.plot([lo, hi], [r["intercept"] + r["slope"] * lo, r["intercept"] + r["slope"] * hi], "-", c="#C44E52",
                    lw=1.5, label=f"OLS slope {r['slope']:.2f} [{r['slope_ci'][0]:.2f}, {r['slope_ci'][1]:.2f}]")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("offset X = recent MSL above the station MSL datum (m)")
        ax.legend(fontsize=7, loc="lower left")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("station mean bias, model − observed (m), lead (0, 49.7] h")
    fig.tight_layout()
    (PKG / "figures").mkdir(exist_ok=True)
    fig.savefig(PKG / "figures/bias_vs_offset.png", dpi=100)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = inputs()
    dmap = ctx[5]
    w = load_cases("w49_7")
    noan = load_cases("noanomaly_w49_7")
    res = {}
    t3 = table(w, "3d", POST, "w49_7", ctx)
    res["primary"] = a2(t3, "3D post-transition, NTDE, X, (0, 49.7] h")
    same = {r["station_id"] for r in t3}
    t2_all = table(w, "2d", POST, "w49_7", ctx)
    t2 = [r for r in t2_all if r["station_id"] in same]
    res["control_2d_same_stations"] = a2(t2, "2D post, stations of the primary analysis")
    res["control_2d_all_stations"] = a2(t2_all, "2D post, all eligible 2D stations")
    t3pre = table(w, "3d", PRE, "w49_7", ctx)
    res["pre_transition_3d"] = a2(t3pre, "3D pre-transition (v2.1, NAVD88 vs NAVD)")
    tn, tn_all = [], []
    if noan:
        tn_all = table(noan, "2d", POST, "w49_7", ctx)
        tn = [r for r in tn_all if r["station_id"] in same]
        res["supplementary_2d_noanomaly_same_stations"] = a2(tn, "2D noanomaly post, primary stations")
        res["supplementary_2d_noanomaly_all"] = a2(tn_all, "2D noanomaly post, all")
    res["modified_epoch_3d_post"] = s2.analyse(t3, "X", epoch="modified_5yr")
    sens = {}
    for win in ("w24_8", "w48"):
        cw = load_cases(win)
        if cw:
            sens[f"S1_{win}"] = a2(table(cw, "3d", POST, win, ctx), f"S1 window {win}")
    for off in ("O12_plus_S", "O12", "O29"):
        sens[f"S2_{off}"] = s2.analyse(t3, off)
    sens["S3_without_boundary_stations"] = s2.analyse(t3, "X", drop_boundary=True)
    sens["S4_weekly_only"] = a2(table(w, "3d", POST, "w49_7", ctx, lambda c: c["cycle"][:10] not in DAILY_EXTRA), "S4")
    sens["S5_without_previously_seen"] = a2(table(w, "3d", POST, "w49_7", ctx, lambda c: c["cycle"][:10] not in PREV), "S5")
    sens["S6_modified_epochs_pooled"] = s2.analyse(pooled(t3), "X", epoch="pooled")

    def verified90(c):
        oc = c["observations"].get("counts", {})
        n = c["statistics"].get("n", 0)
        return n > 0 and oc.get("verified", 0) >= 0.9 * n
    sens["S7_verified_only"] = a2(table(w, "3d", POST, "w49_7", ctx, verified90), "S7")
    sens["S8_2d_all_cycles"] = a2(table(w, "2d", ALL, "w49_7", ctx), "S8")
    sens["S10_abs_d_le_0_03"] = a2([r for r in t3 if r["station_id"] in dmap and abs(dmap[r["station_id"]]) <= 0.03], "S10")
    sens["S11_from_2026_08_24"] = a2(table(w, "3d", S11, "w49_7", ctx), "S11")
    res["sensitivity"] = sens

    # A3: per cycle and product, mean bias over all entering stations and over boundary stations
    boundary = ctx[4]
    a3 = []
    for name, cs in (("3d", w), ("2d", w), ("2d_noanomaly", noan or [])):
        prod = "2d" if name.startswith("2d") else "3d"
        by = defaultdict(list)
        for c in cs:
            if c["product"] == prod and c["expected"]["expected"] == "compare" and c["statistics"].get("n", 0) >= 0.8 * 497 \
                    and ctx[3].get(c["station_id"]) == "NTDE_1983_2001":
                by[c["cycle"][:10]].append(c)
        for day, lst in sorted(by.items()):
            b = [c["statistics"]["bias"] for c in lst]
            bb = [c["statistics"]["bias"] for c in lst if c["station_id"] in boundary]
            a3.append({"product": name, "cycle": day, "n_stations": len(b), "mean_bias_all": sum(b) / len(b),
                       "n_boundary": len(bb), "mean_bias_boundary": sum(bb) / len(bb) if bb else None})
    res["A3_per_cycle"] = a3
    # A4: Boston
    a4 = []
    for name, cs in (("3d", w), ("2d", w), ("2d_noanomaly", noan or [])):
        prod = "2d" if name.startswith("2d") else "3d"
        for c in cs:
            if c["product"] == prod and c["station_id"] == "8443970":
                st = c["statistics"]
                a4.append({"product": name, "cycle": c["cycle"][:10], "paired_datum": c["observations"].get("paired_datum"),
                           "n": st.get("n"), "bias": st.get("bias"), "model_mean": st.get("model_mean"),
                           "obs_mean": st.get("obs_mean"), "expected": c["expected"]["expected"]})
    res["A4_boston"] = sorted(a4, key=lambda r: (r["product"], r["cycle"]))
    for n, rows in (("3d_post", t3), ("3d_pre", t3pre), ("2d_post_all", t2_all), ("2d_noanomaly_post_all", tn_all)):
        write_rows(f"station_table_{n}.csv", rows)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    figure(t3, t2, tn, res)
    print(json.dumps({k: (v.get("verdict_A2") if isinstance(v, dict) else None) for k, v in res.items()
                      if isinstance(v, dict) and "verdict_A2" in v}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
