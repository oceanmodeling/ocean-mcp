#!/usr/bin/env python3
"""Study 2: does the STOFS-3D-Atlantic station mean bias track the rise in mean sea level since
the tidal-datum epoch? Pre-registered analysis (DESIGN.md section 7). No Ocean-MCP import.

Inputs: reference/results/<window>/cases.jsonl, the monthly-mean and MSL water-level archives,
the datums archive, reference/boundary_stations.json. Outputs: results/study2/*, figures/.
Everything that decides a result is a constant or a function here, fixed before any sampled
model file is downloaded.
"""

from __future__ import annotations

import datetime as dt
import math
import random
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "reference"))

UTC = dt.timezone.utc
MIN_PAIR_FRACTION = 0.80        # case: >= 80% of the window's 6-minute times paired
MIN_CYCLES = 5                  # station: >= 5 entering cycles in the period
MIN_MONTHS = 10                 # O12: >= 10 of the 12 verified monthly means
CLIM_YEARS = range(2016, 2026)  # seasonal climatology: verified monthly means 2016-2025
CLIM_MIN_MONTHS_PER_YEAR = 10   # a year enters the climatology with >= 10 months
CLIM_MIN_YEARS = 5              # a calendar month's anomaly needs >= 5 years
O29_HALF_DAYS = 14.5            # O29: [cycle - 14.5 d, cycle + 14.5 d)
O29_MIN_FRACTION = 0.80         # O29: >= 80% of the 6,960 six-minute times valid
N_BOOT = 10_000
SEED = 20261109
CI = (2.5, 97.5)
MIN_STATIONS = 15               # fewer stations -> inconclusive by rule


def _month_back(y: int, m: int, k: int) -> tuple[int, int]:
    mm = m - k
    return y + (mm - 1) // 12, (mm - 1) % 12 + 1


def _monthly_map(monthly: list[dict]) -> dict:
    return {(int(r["year"]), int(r["month"])): float(r["MSL"]) for r in monthly if r.get("MSL") not in (None, "")}


# ------------------------------------------------------------------ offsets (observations only)
def o12_before(monthly: list[dict], y: int, m: int) -> tuple[float | None, int]:
    """Mean verified monthly MSL (datum MSL) over the 12 calendar months before month (y, m)."""
    have = _monthly_map(monthly)
    vals = [have[w] for w in (_month_back(y, m, k) for k in range(1, 13)) if w in have]
    return (sum(vals) / len(vals) if len(vals) >= MIN_MONTHS else None), len(vals)


def o12(monthly: list[dict], cycle: dt.datetime) -> tuple[float | None, int]:
    """The brief's estimate: the 12 months before the cycle's month (per cycle)."""
    return o12_before(monthly, cycle.year, cycle.month)


def seasonal_anomaly(monthly: list[dict]) -> dict[int, float]:
    """Calendar-month anomaly of verified monthly MSL relative to each year's own mean,
    averaged over CLIM_YEARS (years with >= 10 months; months with >= 5 years)."""
    have = _monthly_map(monthly)
    acc: dict[int, list[float]] = {}
    for y in CLIM_YEARS:
        ms = {m: have[(y, m)] for m in range(1, 13) if (y, m) in have}
        if len(ms) < CLIM_MIN_MONTHS_PER_YEAR:
            continue
        ym = sum(ms.values()) / len(ms)
        for m, v in ms.items():
            acc.setdefault(m, []).append(v - ym)
    return {m: sum(v) / len(v) for m, v in acc.items() if len(v) >= CLIM_MIN_YEARS}


def o29(records: list[tuple[dt.datetime, dict]], cycle: dt.datetime) -> tuple[float | None, float]:
    """Mean valid observed level (datum MSL) over [cycle - 14.5 d, cycle + 14.5 d)."""
    import rules
    lo = cycle - dt.timedelta(days=O29_HALF_DAYS)
    hi = cycle + dt.timedelta(days=O29_HALF_DAYS)
    expected = int(round(2 * O29_HALF_DAYS * 240))
    vals = []
    for t, r in records:
        if lo <= t < hi:
            c, v = rules.classify_obs_value(r.get("v"))
            if c == "valid":
                vals.append(v)
    frac = len(vals) / expected
    return (sum(vals) / len(vals) if frac >= O29_MIN_FRACTION else None), frac


# ------------------------------------------------------------------ regression and bootstrap
def ols(x: list[float], y: list[float]) -> tuple[float, float]:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx == 0:
        return float("nan"), float("nan")
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    return b, my - b * mx


def theil_sen(x: list[float], y: list[float]) -> tuple[float, float]:
    s = sorted((y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x)) for j in range(i + 1, len(x)) if x[j] != x[i])
    if not s:
        return float("nan"), float("nan")
    b = s[len(s) // 2] if len(s) % 2 else 0.5 * (s[len(s) // 2 - 1] + s[len(s) // 2])
    ints = sorted(c - b * a for a, c in zip(x, y))
    return b, ints[len(ints) // 2]


def percentile(v: list[float], p: float) -> float:
    v = sorted(v)
    k = (len(v) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return v[f] if f == c else v[f] + (v[c] - v[f]) * (k - f)


def ci(v: list[float]) -> list[float]:
    return [percentile(v, CI[0]), percentile(v, CI[1])] if v else [float("nan"), float("nan")]


def bootstrap(x, y, clusters=None, n_boot=N_BOOT, seed=SEED, boundary=None):
    """Resample stations (or whole clusters) with replacement. ``boundary`` (bool per station)
    adds, per resample, the boundary stations' mean offset and mean bias and the carried
    fraction f = intercept / mean boundary offset."""
    rng = random.Random(seed)
    idx = list(range(len(x)))
    groups = keys = None
    if clusters is not None:
        groups = {}
        for i, g in enumerate(clusters):
            groups.setdefault(g, []).append(i)
        keys = sorted(groups)
    bs, as_, fs, bb, xb = [], [], [], [], []
    for _ in range(n_boot):
        s = [rng.choice(idx) for _ in idx] if groups is None else \
            [i for g in (rng.choice(keys) for _ in keys) for i in groups[g]]
        b, a = ols([x[i] for i in s], [y[i] for i in s])
        if not math.isfinite(b):
            continue
        bs.append(b)
        as_.append(a)
        if boundary is not None:
            sb = [i for i in s if boundary[i]]
            if sb:
                xm = sum(x[i] for i in sb) / len(sb)
                bb.append(sum(y[i] for i in sb) / len(sb))
                xb.append(xm)
                if xm != 0:
                    fs.append(a / xm)
    return {"slope_ci": ci(bs), "intercept_ci": ci(as_), "n_boot_valid": len(bs),
            "carried_fraction_ci": ci(fs), "boundary_mean_bias_ci": ci(bb), "boundary_mean_offset_ci": ci(xb),
            "boundary_bias_plus_offset_ci": ci([p + q for p, q in zip(bb, xb)])}


def slope_reading(n: int, slope_ci: list[float]) -> str:
    """DESIGN.md 7.5. A target is supported only if its value is inside the interval and the
    midpoint -0.5 is outside it."""
    lo, hi = slope_ci
    if n < MIN_STATIONS or not (math.isfinite(lo) and math.isfinite(hi)):
        return "inconclusive"
    inside = lambda v: lo <= v <= hi  # noqa: E731
    if inside(-1) and not inside(0) and not inside(-0.5):
        return "minus_one"
    if inside(0) and not inside(-1) and not inside(-0.5):
        return "zero"
    if -1 < lo and hi < 0:
        return "intermediate"
    if hi < -1 or lo > 0:
        return "outside_both"
    return "inconclusive"


def verdict(n: int, slope_ci: list[float], carried_fraction_ci: list[float] | None) -> str:
    """Pre-registered reading (DESIGN.md 7.5)."""
    s = slope_reading(n, slope_ci)
    if s == "zero":
        return "supports H-carried (slope ~ 0)"
    if s == "intermediate":
        return "intermediate (slope between -1 and 0)"
    if s == "outside_both":
        return "outside both hypotheses (slope beyond -1 or above 0)"
    if s == "inconclusive":
        return "inconclusive (slope)"
    lo, hi = carried_fraction_ci or [float("nan"), float("nan")]
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "slope ~ -1; carried fraction not estimable (no boundary station)"
    if lo <= 0 <= hi and not (lo <= 0.5 <= hi):
        return "supports H-epoch (slope ~ -1, no uniform level carried)"
    if lo > 0:
        return "supports H-uniform (slope ~ -1, a uniform level carried; see carried fraction)"
    if hi < 0:
        return "slope ~ -1 with a negative uniform offset (unexplained)"
    return "slope ~ -1; H-epoch and H-uniform not separable"


def region(lat: float, lon: float) -> str:
    """Cluster for the cluster bootstrap (DESIGN.md 7.4), from station coordinates."""
    if lon > 0 or lon < -125 or lat > 49:
        return "pacific_alaska_islands"
    if lon < -100:
        return "us_west_coast"
    if lat < 20 and lon > -70:
        return "caribbean"
    if lon < -81.5 and lat < 31:
        if lon > -85:
            return "gulf_east"
        if lon > -90:
            return "gulf_central"
        return "gulf_west"
    return f"atlantic_{int(math.floor(lat / 2.0) * 2)}N"


def station_table(cases: list[dict], product: str, period: tuple, window_n: int, monthly: dict,
                  msl_records, stations_meta: dict, epoch_class: dict, boundary: set) -> list[dict]:
    """One row per station. ``period`` = (first cycle, last cycle); ``window_n`` = the window's
    number of 6-minute times (497 for (0, 49.7] h); ``msl_records(station, lo, hi)`` returns
    MSL records from the masters."""
    lo_c, hi_c = period
    by = {}
    for c in cases:
        if c["product"] != product:
            continue
        cyc = dt.datetime.strptime(c["cycle"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        if not (lo_c <= cyc <= hi_c):
            continue
        st = c["statistics"]
        if c["expected"]["expected"] != "compare" or st.get("n", 0) < MIN_PAIR_FRACTION * window_n:
            continue
        by.setdefault(c["station_id"], []).append((cyc, st))
    rows = []
    for sid, lst in sorted(by.items()):
        if len(lst) < MIN_CYCLES:
            continue
        mon = monthly.get(sid, [])
        o12_pre, n_pre = o12_before(mon, lo_c.year, lo_c.month)
        sa = seasonal_anomaly(mon)
        seas = [sa.get(cyc.month) for cyc, _ in lst]
        s_mean = sum(seas) / len(seas) if seas and all(v is not None for v in seas) else None
        o12s = [v for v in (o12(mon, cyc)[0] for cyc, _ in lst) if v is not None]
        o29s = [w for w in (o29(msl_records(sid, cyc - dt.timedelta(days=O29_HALF_DAYS),
                                            cyc + dt.timedelta(days=O29_HALF_DAYS)), cyc)[0] for cyc, _ in lst)
                if w is not None]
        biases = [s["bias"] for _, s in lst]
        n = len(biases)
        mb = sum(biases) / n
        meta = stations_meta.get(sid, {})
        o12b = sum(o12s) / len(o12s) if len(o12s) >= MIN_CYCLES else None
        rows.append({
            "station_id": sid, "name": meta.get("name"), "lat": meta.get("lat"), "lon": meta.get("lng"),
            "n_cycles": n, "bias_mean": mb,
            "bias_sd": math.sqrt(sum((b - mb) ** 2 for b in biases) / (n - 1)) if n > 1 else None,
            "model_mean": sum(s["model_mean"] for _, s in lst) / n,
            "obs_mean": sum(s["obs_mean"] for _, s in lst) / n,
            # primary regressor: annual level of the 12 months before the period + seasonal anomaly
            "X": (o12_pre + s_mean) if (o12_pre is not None and s_mean is not None) else None,
            "O12_pre_period": o12_pre, "n_months_pre_period": n_pre, "S_seasonal": s_mean,
            "O12": o12b, "n_O12": len(o12s),                       # the brief's estimate, per cycle
            "O12_plus_S": (o12b + s_mean) if (o12b is not None and s_mean is not None) else None,
            "O29": sum(o29s) / len(o29s) if len(o29s) >= MIN_CYCLES else None, "n_O29": len(o29s),
            "epoch_class": epoch_class.get(sid), "boundary_station": sid in boundary,
            "region": region(meta["lat"], meta["lng"]) if meta.get("lat") is not None else None,
        })
    return rows


def analyse(rows: list[dict], offset: str = "X", epoch: str = "NTDE_1983_2001",
            drop_boundary: bool = False) -> dict:
    sel = [r for r in rows if r[offset] is not None and r["epoch_class"] == epoch
           and not (drop_boundary and r["boundary_station"])]
    if len(sel) < 3:
        return {"n_stations": len(sel), "verdict": "inconclusive (too few stations)"}
    x, y = [r[offset] for r in sel], [r["bias_mean"] for r in sel]
    bnd = [r["boundary_station"] for r in sel]
    b, a = ols(x, y)
    boot = bootstrap(x, y, boundary=bnd)
    cboot = bootstrap(x, y, clusters=[r["region"] for r in sel], boundary=bnd)
    ts = theil_sen(x, y)
    resid = [yy + xx for xx, yy in zip(x, y)]  # level test: B + X (H-epoch predicts ~0)
    rng = random.Random(SEED)
    lv = [sum(s) / len(s) for s in ([rng.choice(resid) for _ in resid] for _ in range(N_BOOT))]
    xb = [r[offset] for r in sel if r["boundary_station"]]
    bb = [r["bias_mean"] for r in sel if r["boundary_station"]]
    xbar_b = sum(xb) / len(xb) if xb else None
    sx = math.sqrt(sum((v - sum(x) / len(x)) ** 2 for v in x) / (len(x) - 1))
    return {"n_stations": len(sel), "offset": offset, "epoch": epoch, "drop_boundary": drop_boundary,
            "slope": b, "intercept": a, **boot, "cluster_bootstrap": cboot,
            "theil_sen": {"slope": ts[0], "intercept": ts[1]},
            "offset_mean": sum(x) / len(x), "offset_sd": sx, "bias_mean": sum(y) / len(y),
            "level_test_mean_bias_plus_offset": sum(resid) / len(resid), "level_test_ci": ci(lv),
            "boundary_stations_n": len(xb), "boundary_mean_offset_xbar_b": xbar_b,
            "boundary_mean_bias": sum(bb) / len(bb) if bb else None,
            "carried_fraction": (a / xbar_b) if xbar_b else None,
            "slope_reading": slope_reading(len(sel), boot["slope_ci"]),
            "verdict": verdict(len(sel), boot["slope_ci"], boot["carried_fraction_ci"]),
            "verdict_cluster_bootstrap": verdict(len(sel), cboot["slope_ci"], cboot["carried_fraction_ci"])}


if __name__ == "__main__":  # pragma: no cover - wired up in Phase 2 (run_all.sh)
    print("Study 2 analysis module; run through run_all.sh after Phase 2 data exist.")
