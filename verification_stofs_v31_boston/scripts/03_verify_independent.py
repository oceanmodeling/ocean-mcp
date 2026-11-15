"""Step 3: independent recalculation, and comparison with the Ocean-MCP results.

Uses only the archived inputs: data/derived/boston_<model>.json (extracted from
the raw NetCDF by step 1) and the archived CO-OPS response. Does not import
Ocean-MCP. Pairs by exact timestamp, computes every statistic from its
definition (e = M - O, metres):

  bias = mean(e)            RMSE = sqrt(mean(e^2))       MAE = mean(|e|)
  CRMSE = sqrt(mean((e - mean(e))^2)) = sqrt(RMSE^2 - bias^2)
  r = cov(M, O) / (sd(M) sd(O))   (population moments)
  max|e| = max(|e|)          dmax = max(M) - max(O)

then compares with results/mcp/*.json. The server rounds model values to
4 decimals before its statistics, so agreement is judged at 1e-4 m (1e-4 for r).

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/03_verify_independent.py
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta

import numpy as np

import _common as c

TOL = 1e-4
FLAG_NAMES = ("O", "F", "R", "L")  # CO-OPS f: outliers, flat, rate-of-change, limit


def obs_records() -> tuple[dict, dict]:
    raw = c.load_json(c.COOPS / "water_level_8443970_MSL.json")
    obs, excluded = {}, {"missing": 0, "nonfinite": 0, "bad_time": 0, "duplicate": 0}
    for r in raw["data"]:
        try:
            t = datetime.strptime(r["t"], "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            excluded["bad_time"] += 1
            continue
        if not r.get("v", "").strip():
            excluded["missing"] += 1
            continue
        v = float(r["v"])
        if not math.isfinite(v):
            excluded["nonfinite"] += 1
            continue
        if t in obs:
            excluded["duplicate"] += 1
            continue
        flags = [int(x) for x in r.get("f", "0,0,0,0").split(",")]
        obs[t] = {"v": v, "q": r.get("q"), "flags": flags, "s": r.get("s")}
    return obs, {"records": len(raw["data"]), "excluded": excluded}


def stats(m: np.ndarray, o: np.ndarray, t: list[datetime]) -> dict:
    e = m - o
    bias = float(e.mean())
    rmse = float(np.sqrt((e**2).mean()))
    crmse = float(np.sqrt(((e - bias) ** 2).mean()))
    sm, so = float(m.std()), float(o.std())
    r = (
        float(((m - m.mean()) * (o - o.mean())).mean() / (sm * so))
        if sm and so
        else None
    )
    ie, im, io = int(np.argmax(np.abs(e))), int(np.argmax(m)), int(np.argmax(o))
    return {
        "n": int(len(e)),
        "bias_m": bias,
        "rmse_m": rmse,
        "mae_m": float(np.abs(e).mean()),
        "crmse_m": crmse,
        "pearson_r": r,
        "max_abs_error_m": float(abs(e[ie])),
        "max_abs_error_time": t[ie].strftime("%Y-%m-%d %H:%M"),
        "model_max_m": float(m[im]),
        "model_max_time": t[im].strftime("%Y-%m-%d %H:%M"),
        "obs_max_m": float(o[io]),
        "obs_max_time": t[io].strftime("%Y-%m-%d %H:%M"),
        "max_model_minus_max_obs_m": float(m[im] - o[io]),
        "model_mean_m": float(m.mean()),
        "obs_mean_m": float(o.mean()),
        "model_sd_m": sm,
        "obs_sd_m": so,
        "error_min_m": float(e.min()),
        "error_max_m": float(e.max()),
    }


def window(model: str, name: str, lo: float, hi: float, obs: dict) -> dict:
    ex = c.load_json(c.DERIVED / f"boston_{model}.json")
    cycle = datetime.strptime(c.CYCLE_ISO, "%Y-%m-%d %H:%M")
    in_win, model_excluded = [], 0
    for r in ex["records"]:
        t = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S")
        lead = (t - cycle) / timedelta(hours=1)
        if lo < lead <= hi:
            if r["excluded"]:
                model_excluded += 1
            else:
                in_win.append((t, r["value_m"]))
    pairs = [(t, v, obs[t]) for t, v in in_win if t in obs]
    t = [p[0] for p in pairs]
    m = np.array([p[1] for p in pairs])
    o = np.array([p[2]["v"] for p in pairs])
    q = [p[2]["q"] for p in pairs]
    flagged = [p for p in pairs if any(p[2]["flags"])]
    flag_counts = {
        n: sum(1 for p in pairs if p[2]["flags"][k]) for k, n in enumerate(FLAG_NAMES)
    }
    leads = [(x - cycle) / timedelta(hours=1) for x in t]
    return {
        "model": model,
        "label": ex["label"],
        "window": name,
        "lead_window_hours": [lo, hi],
        "definition": f"{lo:g} < lead <= {hi:g} h from {c.CYCLE_ISO} UTC",
        "model_records_in_window": len(in_win) + model_excluded,
        "model_records_excluded": model_excluded,
        "matched_pairs": len(pairs),
        "unmatched_model_records": len(in_win) - len(pairs),
        "first_valid_time": t[0].strftime("%Y-%m-%d %H:%M"),
        "last_valid_time": t[-1].strftime("%Y-%m-%d %H:%M"),
        "lead_hours_range": [round(min(leads), 2), round(max(leads), 2)],
        "matching": "exact timestamp (no tolerance needed: both series are on the 6-min grid)",
        "matched_obs_quality": {
            "preliminary": q.count("p"),
            "verified": q.count("v"),
            "other": len(q) - q.count("p") - q.count("v"),
            "with_any_flag": len(flagged),
            "flag_counts": flag_counts,
        },
        "statistics": stats(m, o, t),
        "series": [
            {"time": x.strftime("%Y-%m-%d %H:%M"), "model_m": mv, "obs_m": ov}
            for x, mv, ov in zip(t, m.tolist(), o.tolist())
        ],
    }


def compare_with_mcp(ind: dict, name: str) -> dict:
    mcp = c.load_json(c.RESULTS / "mcp" / f"{name}.json")["response"]
    st, sm = ind["statistics"], mcp["statistics"]
    checks = {
        "n": (ind["matched_pairs"], sm["n"]),
        "bias_m": (st["bias_m"], sm["bias"]),
        "rmse_m": (st["rmse_m"], sm["rmse"]),
        "mae_m": (st["mae_m"], sm["mae"]),
        "pearson_r": (st["pearson_r"], sm["correlation"]),
        "max_abs_error_m": (st["max_abs_error_m"], sm["max_abs_error"]),
        "max_model_minus_max_obs_m": (
            st["max_model_minus_max_obs_m"],
            mcp["summary"]["peak_error_m"],
        ),
        "crmse_m (MCP: sqrt(rmse^2 - bias^2))": (
            st["crmse_m"],
            math.sqrt(max(sm["rmse"] ** 2 - sm["bias"] ** 2, 0.0)),
        ),
    }
    rows, disagree = {}, []
    for k, (a, b) in checks.items():
        tol = 0 if k == "n" else (3e-4 if k.startswith("crmse") else TOL)
        diff = abs(a - b)
        ok = diff <= tol
        rows[k] = {
            "independent": a,
            "ocean_mcp": b,
            "abs_diff": diff,
            "tolerance": tol,
            "agree": ok,
        }
        if not ok:
            disagree.append(k)
    # Point by point: same valid times, model within rounding, identical obs.
    series_mcp = {p["time"]: p for p in mcp["comparison"]}
    times_equal = [p["time"] for p in ind["series"]] == [
        p["time"] for p in mcp["comparison"]
    ]
    dm = max(
        abs(p["model_m"] - series_mcp[p["time"]]["stofs_m"]) for p in ind["series"]
    )
    do = max(abs(p["obs_m"] - series_mcp[p["time"]]["obs_m"]) for p in ind["series"])
    point = {
        "same_valid_times": times_equal,
        "max_abs_model_value_diff_m": dm,
        "max_abs_obs_value_diff_m": do,
        "agree": times_equal and dm <= 5.0001e-5 and do == 0,
    }
    if not point["agree"]:
        disagree.append("pointwise")
    return {
        "window": name,
        "mcp_datums": [mcp["stofs_datum"], mcp["coops_datum"]],
        "mcp_window": mcp["window"],
        "mcp_alignment": mcp["alignment"],
        "mcp_observation_quality": mcp["observation_quality"],
        "metrics": rows,
        "pointwise": point,
        "disagreements": disagree,
    }


def main() -> int:
    obs, obs_meta = obs_records()
    results, comparisons = {}, {}
    for model in c.STOFS_FILES:
        wins = {"forecast": c.FORECAST_WINDOW, "nowcast": c.NOWCAST_WINDOWS[model]}
        for wname, (lo, hi) in wins.items():
            name = f"{model}_{wname}"
            results[name] = window(model, wname, lo, hi, obs)
            comparisons[name] = compare_with_mcp(results[name], name)
            st = results[name]["statistics"]
            print(
                f"{name:22} n={st['n']:3} bias={st['bias_m']:+.4f} rmse={st['rmse_m']:.4f} "
                f"mae={st['mae_m']:.4f} crmse={st['crmse_m']:.4f} r={st['pearson_r']:.4f} "
                f"max|e|={st['max_abs_error_m']:.4f} dmax={st['max_model_minus_max_obs_m']:+.4f} "
                f"| vs MCP: {'AGREE' if not comparisons[name]['disagreements'] else comparisons[name]['disagreements']}"
            )
    c.dump_json(
        {
            "case": {"cycle": c.CYCLE_ISO + " UTC", "station": c.STATION},
            "observations": obs_meta,
            "definitions": __doc__.split("Uses only")[1].split("Usage")[0].strip(),
            "results": results,
        },
        c.RESULTS / "statistics_independent.json",
    )
    c.dump_json(comparisons, c.RESULTS / "mcp_vs_independent.json")
    return 0 if all(not v["disagreements"] for v in comparisons.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
