#!/usr/bin/env python3
"""Study 3: decomposition of the Boston STOFS-3D-Atlantic error, cycle 2026-10-30 12z only
(DESIGN.md section 8). Inputs: the archived Boston-package files (3D station NetCDF sha256
46608194..., CO-OPS MSL water level 8443970 sha256 c207c801...). No Ocean-MCP import.

Window (0, 48] h, as Table 3. e = model - observed.
1. Best lag at sub-sample resolution: the model series is shifted by tau (model value at
   t - tau, cubic-spline interpolation of the 6-minute model series) and tau minimising the
   centred RMSE over the window is found on a 0.1-minute grid in [-60, +60] min. Reported with
   the 6-minute-grid optimum and the parabolic-vertex estimate from the three lags around it.
2. RMSE after removing, each alone and cumulatively in the order mean -> lag -> amplitude:
   (a) the mean error; (b) the best lag; (c) a best-fit amplitude scale alpha applied to the
   model anomaly (least squares of the observed anomaly on the shifted model anomaly).
3. Quality flags of the 480 matched observations by type (O, F, R, L; CO-OPS response help).
4. Table 3 statistics recomputed with flagged observations (any flag > 0) removed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "reference"))
import rules  # noqa: E402

BOSTON = Path("/mnt/d/ocean-mcp/.claude/worktrees/stofs-v31-boston-v2/verification_stofs_v31_boston")
SHA_3D = "4660819425aa1d2eec0e63a37d3a78e8fef2e00f62a1cb56f088347ef51a450f"
CYCLE = dt.datetime(2026, 10, 30, 12, tzinfo=dt.timezone.utc)
LAG_RANGE_MIN, LAG_STEP_MIN = 60.0, 0.1


def load():
    import hashlib
    import netCDF4
    import numpy as np
    p = BOSTON / "data/raw/stofs_3d_atl.20261030.t12z.points.cwl.nc"
    if hashlib.sha256(p.read_bytes()).hexdigest() != SHA_3D:
        raise SystemExit("Boston 3D file checksum differs")
    nc = netCDF4.Dataset(str(p))
    nc.set_auto_mask(False)
    names = [str(s).strip() for s in netCDF4.chartostring(nc.variables["station_name"][:])]
    i = next(k for k, n in enumerate(names) if "8443970" in n.split())
    t = rules.decode_times(np.asarray(nc.variables["time"][:]).tolist(), str(nc.variables["time"].units))
    z = np.asarray(nc.variables["zeta"][:, i], dtype=float)
    nc.close()
    obs = json.loads((BOSTON / "data/coops/water_level_8443970_MSL.json").read_text())["data"]
    return t, z, obs


def centred_rmse(e):
    m = sum(e) / len(e)
    return math.sqrt(sum((x - m) ** 2 for x in e) / len(e))


def main() -> int:  # pragma: no cover - run in Phase 2
    import numpy as np
    from scipy.interpolate import CubicSpline
    t, z, obs = load()
    ts = np.array([(x - CYCLE).total_seconds() / 60 for x in t])  # minutes from cycle
    spline = CubicSpline(ts, z)
    O = {}
    for r in obs:
        tt = dt.datetime.strptime(r["t"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        if rules.in_window(tt, CYCLE, 0.0, 48.0):
            c, v = rules.classify_obs_value(r.get("v"))
            if c == "valid":
                O[(tt - CYCLE).total_seconds() / 60] = (v, rules.obs_flags(r.get("f")))
    tm = np.array(sorted(O))
    ob = np.array([O[k][0] for k in tm])

    def series(tau):  # model at t - tau
        return spline(tm - tau)

    def crmse(tau):
        return centred_rmse(list(series(tau) - ob))

    grid = np.arange(-LAG_RANGE_MIN, LAG_RANGE_MIN + 1e-9, LAG_STEP_MIN)
    vals = np.array([crmse(x) for x in grid])
    tau = float(grid[int(np.argmin(vals))])
    six = np.arange(-60, 61, 6.0)
    v6 = np.array([crmse(x) for x in six])
    k = int(np.argmin(v6))
    vertex = None
    if 0 < k < len(six) - 1:
        y0, y1, y2 = v6[k - 1], v6[k], v6[k + 1]
        den = y0 - 2 * y1 + y2
        vertex = float(six[k] + 3.0 * (y0 - y2) / den) if den != 0 else None
    e0 = series(0.0) - ob
    rm = lambda e: float(math.sqrt(np.mean(np.asarray(e) ** 2)))  # noqa: E731
    m_shift = series(tau)
    ma, oa = m_shift - m_shift.mean(), ob - ob.mean()
    alpha = float(np.dot(ma, oa) / np.dot(ma, ma))
    m0a = series(0.0) - series(0.0).mean()
    alpha0 = float(np.dot(m0a, oa) / np.dot(m0a, m0a))
    out = {
        "n": int(len(tm)), "best_lag_min_0p1_grid": tau, "best_lag_6min_grid": float(six[k]),
        "best_lag_parabolic_vertex_min": vertex,
        "lag_convention": "tau: the model value at t - tau is compared with the observation at t; "
                          "tau < 0 means the model is late (model lags the observations by -tau minutes)",
        "model_lags_observations_by_min": -tau,
        "rmse": {
            "raw": rm(e0),
            "mean_removed": rm(e0 - e0.mean()),
            "lag_removed_only": rm(series(tau) - ob),
            "amplitude_removed_only": rm(alpha0 * (series(0.0) - series(0.0).mean()) + series(0.0).mean() - ob),
            "mean_and_lag_removed": rm((m_shift - ob) - (m_shift - ob).mean()),
            "mean_lag_and_amplitude_removed": rm(alpha * ma - oa),
        },
        "amplitude_scale_alpha_after_lag": alpha, "amplitude_scale_alpha_no_lag": alpha0,
        "flags": {f: int(sum(O[k][1][f] > 0 for k in tm)) for f in rules.FLAG_NAMES},
        "flagged_any": int(sum(any(v > 0 for v in O[k][1].values()) for k in tm)),
    }
    keep = [i for i, k_ in enumerate(tm) if not any(v > 0 for v in O[k_][1].values())]
    out["table3_flagged_removed"] = rules.stats(list(series(0.0)[keep]), list(ob[keep]))
    out["table3_all"] = rules.stats(list(series(0.0)), list(ob))
    od = PKG / "results/study3"
    od.mkdir(parents=True, exist_ok=True)
    (od / "boston_decomposition.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
