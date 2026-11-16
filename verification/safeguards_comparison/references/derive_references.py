#!/usr/bin/env python3
"""Derive the reference values for the WP1 tasks from sources independent of every arm.

This script does not import any arm, any Ocean-MCP package or the replay
launcher. It reads archived bytes through the archive index (stdlib JSON),
decodes NetCDF with netCDF4 (masking and scaling off: raw stored values) and
does all arithmetic in pure Python (math.fsum), as the archived Boston
recalculation did.

Reference classes (see references/README.md):
  IND   archived independent recalculation (Boston package; second review)
  DOC   NOAA documentation, quoted
  PHY   physical bound, with the sensitivity interval that shows the result
        does not depend on the exact bound chosen
  CON   construction of the mutation
  RECALC  recalculated here from the archived bytes by this script, under a
        rule fixed by DOC/PHY/CON. Same author as the arms: a weaker class.

Usage: python -I derive_references.py <verification_dir> <boston_package_dir>
Writes references/computed_values.json.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import netCDF4

EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius
# Physical bound used to recognise values that cannot be coastal water levels
# relative to a tidal or geodetic datum. The largest tidal range on Earth is
# about 16 m (Bay of Fundy; amplitude about 8 m) and the largest recorded storm
# surges are about 8 to 13 m, so |water level| > 30 m is not physical.
# The script also reports the interval of bounds that give the same answer.
PHYS_BOUND_M = 30.0
BOSTON_GAUGE = (42.3539, -71.0503)  # CO-OPS metadata in the archived response


# ---------------------------------------------------------------- archive ---
class Arch:
    def __init__(self, root: Path):
        self.root = root
        self.doc = json.loads((root / "index.json").read_text())

    def find(self, url_contains: str, name: str | None = None) -> dict:
        hits = [e for e in self.doc["entries"]
                if url_contains in e["url"] and (name is None or e["provenance"].get("input_name") == name)]
        if len(hits) != 1:
            raise LookupError(f"{url_contains!r}/{name!r}: {len(hits)} entries")
        return hits[0]

    def path(self, e: dict) -> Path:
        return self.root / e["response"]["body_file"]

    def bytes(self, e: dict) -> bytes:
        return self.path(e).read_bytes()


def by_input(arc: Arch, name: str) -> dict:
    hits = [e for e in arc.doc["entries"] if e["provenance"].get("input_name") == name]
    assert len(hits) == 1, name
    return hits[0]


# ------------------------------------------------------------- utilities ---
def fsum_mean(xs):
    return math.fsum(xs) / len(xs)


def stats(model, obs):
    n = len(model)
    e = [m - o for m, o in zip(model, obs)]
    bias = fsum_mean(e)
    rmse = math.sqrt(fsum_mean([x * x for x in e]))
    mae = fsum_mean([abs(x) for x in e])
    mm, mo = fsum_mean(model), fsum_mean(obs)
    cov = fsum_mean([(m - mm) * (o - mo) for m, o in zip(model, obs)])
    sm = math.sqrt(fsum_mean([(m - mm) ** 2 for m in model]))
    so = math.sqrt(fsum_mean([(o - mo) ** 2 for o in obs]))
    return {"n": n, "bias_m": bias, "rmse_m": rmse, "mae_m": mae, "r": cov / (sm * so)}


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def read_station_file(path: Path) -> dict:
    ds = netCDF4.Dataset(path)
    ds.set_auto_maskandscale(False)
    names = ["".join(c.decode() for c in row).strip() for row in ds["station_name"][:]]
    t = ds["time"]
    m = re.match(r"\s*seconds since (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", t.units)
    base = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    times = [base + timedelta(seconds=float(s)) for s in t[:].tolist()]
    z = ds["zeta"]
    out = {
        "names": names,
        "x": ds["x"][:].tolist(),
        "y": ds["y"][:].tolist(),
        "times": times,
        "zeta": z[:].tolist(),  # [time][station], raw stored values
        "fill": float(z.getncattr("_FillValue")),
        "zeta_attrs": {k: str(z.getncattr(k)) for k in z.ncattrs()},
        "global": {k: str(ds.getncattr(k)) for k in ds.ncattrs()},
    }
    ds.close()
    return out


def station_index(f, coops_id: str) -> int:
    hits = [i for i, n in enumerate(f["names"]) if coops_id in n.split()]
    assert len(hits) == 1, (coops_id, hits)
    return hits[0]


def series(f, i):
    return [row[i] for row in f["zeta"]]


def cycle_of(url: str) -> datetime:
    m = re.search(r"\.(\d{8})/.*\.t(\d{2})z\.", url)
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H")


def coops_records(raw: bytes):
    return json.loads(raw)["data"]


def coops_master(arc: Arch, station: str, datum: str, covering: tuple[datetime, datetime]):
    """Earliest-retrieved archived CO-OPS water_level response for station/datum
    whose requested range covers the window (same rule as the replay)."""
    cands = []
    for e in arc.doc["entries"]:
        if e.get("kind") != "coops_master":
            continue
        q = dict(parse_qsl(urlsplit(e["url"]).query))
        if q.get("station") != station or q.get("datum") != datum:
            continue
        lo = _coops_t(q["begin_date"], False)
        hi = _coops_t(q["end_date"], True)
        if lo <= covering[0] and covering[1] <= hi:
            cands.append((e["provenance"].get("retrieved_at", ""), e["id"], e))
    cands.sort(key=lambda c: (c[0], c[1]))
    return cands[0][2]


def _coops_t(s, end):
    for fmt in ("%Y%m%d %H:%M",):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    d = datetime.strptime(s, "%Y%m%d")
    return d.replace(hour=23, minute=59) if end else d


def obs_map(records):
    """time -> float for records whose v is a finite number; plus counts."""
    out, counts = {}, {"blank": 0, "nonfinite": 0, "nonnumeric": 0}
    for r in records:
        v = r.get("v")
        if v is None or str(v).strip() == "":
            counts["blank"] += 1
            continue
        try:
            x = float(v)
        except ValueError:
            counts["nonnumeric"] += 1
            continue
        if not math.isfinite(x):
            counts["nonfinite"] += 1
            continue
        out[datetime.strptime(r["t"], "%Y-%m-%d %H:%M")] = x
    return out, counts


def valid_model_value(v, fill):
    return math.isfinite(v) and v != fill and abs(v) <= PHYS_BOUND_M


def lead_window_compare(f, idx, cycle, obs, lo_h=0.0, hi_h=48.0):
    model, observed, times, excluded_model = [], [], [], 0
    in_window = 0
    for t, v in zip(f["times"], series(f, idx)):
        lead = (t - cycle).total_seconds() / 3600.0
        if not (lo_h < lead <= hi_h):
            continue
        in_window += 1
        if not valid_model_value(v, f["fill"]):
            excluded_model += 1
            continue
        if t in obs:
            model.append(v)
            observed.append(obs[t])
            times.append(t)
    s = stats(model, observed) if model else None
    return {"stats": s, "model_records_in_window": in_window, "model_records_excluded": excluded_model,
            "pairs": len(model), "first": str(times[0]) if times else None, "last": str(times[-1]) if times else None}


def bound_interval(values_kept_max, values_excluded_min):
    return {"largest_retained_abs_m": values_kept_max, "smallest_excluded_abs_m": values_excluded_min,
            "note": "any physical bound B with largest_retained_abs_m < B <= smallest_excluded_abs_m "
                    "excludes exactly the same values, so the result does not depend on B within it"}


# ------------------------------------------------------------------ main ---
def main() -> int:
    vdir, boston = Path(sys.argv[1]), Path(sys.argv[2])
    base = Arch(vdir / "data/archive/base")
    syn = {t: Arch(vdir / "data/archive/synthetic" / t) for t in ("S1", "S2", "S3", "S4", "S5")}
    out: dict = {"script": "references/derive_references.py", "phys_bound_m": PHYS_BOUND_M}

    url2d = "stofs_2d_glo.20261030/stofs_2d_glo.t12z.points.cwl.nc"
    url3d = "stofs_3d_atl.20261030/stofs_3d_atl.t12z.points.cwl.nc"
    e2d, e3d = base.find(url2d), base.find(url3d)
    f2d, f3d = read_station_file(base.path(e2d)), read_station_file(base.path(e3d))
    c2d, c3d = cycle_of(e2d["url"]), cycle_of(e3d["url"])

    # N1, N2: the archived independent recalculation is the reference (IND)
    ind = json.loads((boston / "results/statistics_independent.json").read_text())["results"]
    def ind_stats(key):
        st = ind[key]["statistics"]
        return {"n": st["n"], "bias_m": st["bias_m"], "rmse_m": st["rmse_m"], "mae_m": st["mae_m"],
                "r": st["pearson_r"]}

    out["N1"] = {"class": "IND", "source": "Boston package results/statistics_independent.json "
                 "(2d_global_forecast)", "stats": ind_stats("2d_global_forecast")}
    out["N2"] = {"class": "IND", "source": "Boston package results/statistics_independent.json "
                 "(3d_atlantic_forecast)", "stats": ind_stats("3d_atlantic_forecast")}
    # cross-check from the archived bytes (consistency of the inputs, not the reference)
    msl_master = coops_master(base, "8443970", "MSL", (datetime(2026, 10, 30, 12, 6), datetime(2026, 11, 1, 12)))
    obs_msl, _ = obs_map(coops_records(base.bytes(msl_master)))
    for tid, f, c in (("N1", f2d, c2d), ("N2", f3d, c3d)):
        chk = lead_window_compare(f, station_index(f, "8443970"), c, obs_msl)
        out[tid]["crosscheck_from_archived_bytes"] = chk
        out[tid]["crosscheck_max_abs_diff"] = max(abs(chk["stats"][k] - out[tid]["stats"][k])
                                                  for k in ("bias_m", "rmse_m", "mae_m", "r"))

    # N3: second review D1 (IND); cross-check against the newly archived bytes
    wl = json.loads(base.bytes(by_input(base, "coops_8725520_water_level_MLLW_20220927_29")))
    pr = json.loads(base.bytes(by_input(base, "coops_8725520_predictions_MLLW_20220927_29")))
    pmap = {r["t"]: float(r["v"]) for r in pr["predictions"]}
    resid = [(r["t"], round(float(r["v"]) - pmap[r["t"]], 3)) for r in wl["data"] if r["v"] and r["t"] in pmap]
    top = max(v for _, v in resid)
    out["N3"] = {"class": "IND", "source": "MANUSCRIPT_SECOND_REVIEW.md section D1",
                 "residual_max_m": 2.209, "first_time_utc": "2022-09-28 22:18", "tie_times_utc": ["2022-09-28 22:18", "2022-09-28 22:30"],
                 "crosscheck_from_archived_bytes": {"records_obs": len(wl["data"]), "records_pred": len(pr["predictions"]),
                                                    "residual_max_m": top, "times": [t for t, v in resid if v == top],
                                                    "obs_quality": sorted({r["q"] for r in wl["data"]}),
                                                    "blank_obs": sum(1 for r in wl["data"] if not r["v"]),
                                                    "obs_22_18": next(r["v"] for r in wl["data"] if r["t"] == "2022-09-28 22:18"),
                                                    "pred_22_18": pmap["2022-09-28 22:18"]}}

    # N4: second review D3 (IND); the archived bytes are the same object (same SHA-256)
    mur = json.loads(base.bytes(by_input(base, "erddap_jplMURSST41_subset")))
    rows = mur["table"]["rows"]
    ci = mur["table"]["columnNames"].index("analysed_sst")
    finite = [r[ci] for r in rows if r[ci] is not None]
    out["N4"] = {"class": "IND", "source": "MANUSCRIPT_SECOND_REVIEW.md section D3",
                 "cells": 17061, "finite": 9301, "null": 7760, "min_degC": 22.199, "max_degC": 23.983,
                 "units": "degree_C",
                 "crosscheck_from_archived_bytes": {"cells": len(rows), "finite": len(finite),
                                                    "min": min(finite), "max": max(finite),
                                                    "units": mur["table"]["columnUnits"][ci],
                                                    "sha256": by_input(base, "erddap_jplMURSST41_subset")["response"]["body_sha256"]}}

    # R1a: STOFS-3D top five by maximum over all records, excluding fill and |v| > bound
    def ranking(f):
        kept_max, excl_min = 0.0, float("inf")
        per = []
        excluded_stations = []
        for i, name in enumerate(f["names"]):
            s = series(f, i)
            good = [v for v in s if valid_model_value(v, f["fill"])]
            bad_phys = [v for v in s if math.isfinite(v) and v != f["fill"] and abs(v) > PHYS_BOUND_M]
            if good:
                kept_max = max(kept_max, max(abs(v) for v in good))
                per.append((max(good), name, i))
            if bad_phys:
                excl_min = min(excl_min, min(abs(v) for v in bad_phys))
                if not good:
                    excluded_stations.append({"station": name, "records": len(bad_phys), "example": bad_phys[0]})
        per.sort(key=lambda p: (-p[0], p[1]))
        return per, kept_max, excl_min, excluded_stations

    per3, kmax3, emin3, ex3 = ranking(f3d)
    out["R1a"] = {"class": "RECALC+PHY", "top5": [{"station": n, "max_m": v} for v, n, _ in per3[:5]],
                  "sixth": {"station": per3[5][1], "max_m": per3[5][0]},
                  "excluded_stations": ex3, "bound_interval": bound_interval(kmax3, emin3),
                  "window": "all 1200 records of the station file (2026-10-29 12:06 to 2026-11-03 12:00)"}
    # same ranking restricted to lead > 0
    def ranking_lead_pos(f, c):
        per = []
        for i, name in enumerate(f["names"]):
            good = [v for t, v in zip(f["times"], series(f, i))
                    if (t - c).total_seconds() > 0 and valid_model_value(v, f["fill"])]
            if good:
                per.append((max(good), name))
        per.sort(key=lambda p: (-p[0], p[1]))
        return per
    lp3 = ranking_lead_pos(f3d, c3d)
    out["R1a"]["lead_gt0_top5"] = [{"station": n, "max_m": v} for v, n in lp3[:5]]

    # R1b: station 9751381
    i = station_index(f3d, "9751381")
    s = series(f3d, i)
    out["R1b"] = {"class": "PHY+CON", "station": f3d["names"][i], "records": len(s),
                  "valid_records": sum(1 for v in s if valid_model_value(v, f3d["fill"])),
                  "distinct_values": sorted(set(s))[:3], "decision": "refuse: no valid model value"}

    # R2: 2D 8571421 minimum
    i = station_index(f2d, "8571421")
    s = series(f2d, i)
    good = [(t, v) for t, v in zip(f2d["times"], s) if valid_model_value(v, f2d["fill"])]
    bad = [v for v in s if not valid_model_value(v, f2d["fill"])]
    good_lead = [(t, v) for t, v in good if (t - c2d).total_seconds() > 0]
    out["R2"] = {"class": "RECALC+PHY", "station": f2d["names"][i], "records": len(s),
                 "valid_records": len(good), "excluded_records": len(bad),
                 "excluded_distinct_values": sorted(set(bad)),
                 "dry_Value_attribute": f2d["global"].get("dry_Value"),
                 "min_m": min(v for _, v in good), "min_time": str(min(good, key=lambda p: p[1])[0]),
                 "max_m": max(v for _, v in good),
                 "lead_gt0": {"valid_records": len(good_lead), "min_m": min(v for _, v in good_lead),
                              "excluded_records": sum(1 for t, v in zip(f2d["times"], s)
                                                      if (t - c2d).total_seconds() > 0 and not valid_model_value(v, f2d["fill"]))},
                 "window": "all 1860 records of the station file (2026-10-30 06:06 to 2026-11-07 00:00)"}

    # R3: 2D highest station
    per2, kmax2, emin2, ex2 = ranking(f2d)
    lp2 = ranking_lead_pos(f2d, c2d)
    out["R3"] = {"class": "RECALC+PHY", "top": {"station": per2[0][1], "max_m": per2[0][0]},
                 "top5": [{"station": n, "max_m": v} for v, n, _ in per2[:5]],
                 "excluded_stations": ex2, "bound_interval": bound_interval(kmax2, emin2),
                 "lead_gt0_top": {"station": lp2[0][1], "max_m": lp2[0][0]},
                 "SA816_range_m": [min(series(f2d, station_index(f2d, "SA816"))), max(series(f2d, station_index(f2d, "SA816")))]}

    # R4: two 3D cycles at Boston, datum pairing fixed by the file label and SCN 26-51
    out["R4"] = {}
    for tid, date, datum_coops in (("R4a", "20260816", "NAVD"), ("R4b", "20260817", "MSL")):
        e = base.find(f"stofs_3d_atl.{date}/stofs_3d_atl.t12z.points.cwl.nc")
        f = read_station_file(base.path(e))
        c = cycle_of(e["url"])
        win = (c + timedelta(minutes=6), c + timedelta(hours=48))
        m = coops_master(base, "8443970", datum_coops, win)
        obs, cnt = obs_map(coops_records(base.bytes(m)))
        res = lead_window_compare(f, station_index(f, "8443970"), c, obs)
        wrong = coops_master(base, "8443970", "MSL" if datum_coops == "NAVD" else "NAVD", win)
        obs_w, _ = obs_map(coops_records(base.bytes(wrong)))
        res_w = lead_window_compare(f, station_index(f, "8443970"), c, obs_w)
        out["R4"][tid] = {"class": "RECALC+DOC", "cycle": str(c), "file_label": f["zeta_attrs"].get("standard_name"),
                          "product_version": re.search(r"stofs\.v[\d.]+\d", f["global"]["history"]).group(0),
                          "coops_datum": datum_coops, "coops_master": m["id"], "obs_counts": cnt,
                          "obs_quality": sorted({r["q"] for r in coops_records(base.bytes(m))}),
                          **res,
                          "for_information_mismatched_datum": {"coops_datum": "MSL" if datum_coops == "NAVD" else "NAVD",
                                                               "stats": res_w["stats"]}}

    # R6: nearest station to the Boston gauge in the 2026-02-18 file
    e = base.find("stofs_3d_atl.20260218/stofs_3d_atl.t12z.points.cwl.nc")
    f = read_station_file(base.path(e))
    ib = station_index(f, "8443970")
    raw = [(haversine_km(BOSTON_GAUGE[0], BOSTON_GAUGE[1], y, x) if -90 <= y <= 90 else float("inf"), n, x, y)
           for n, x, y in zip(f["names"], f["x"], f["y"])]
    raw.sort()
    d_rev = haversine_km(BOSTON_GAUGE[0], BOSTON_GAUGE[1], f["x"][ib], f["y"][ib])
    out["R6"] = {"class": "CON", "station": f["names"][ib], "index": ib,
                 "stored_x_y": [f["x"][ib], f["y"][ib]],
                 "distance_km_with_x_read_as_latitude": d_rev,
                 "gauge": BOSTON_GAUGE,
                 "for_information_naive_nearest_using_attributes_as_labelled":
                     {"station": raw[0][1], "distance_km": raw[0][0], "x": raw[0][2], "y": raw[0][3]}}

    # R7: NDBC 41009 2024 maximum WVHT, NDBC historical missing codes
    txt = base.bytes(base.find("41009h2024.txt.gz")).decode()
    lines = [ln.split() for ln in txt.splitlines() if ln.strip() and not ln.startswith("#")]
    hdr = [ln for ln in txt.splitlines() if ln.startswith("#YY")][0].lstrip("#").split()
    j = hdr.index("WVHT")
    w_raw = [ln[j] for ln in lines]
    w_valid = [(float(v), ln) for v, ln in zip(w_raw, lines) if v not in ("99.00", "99.0", "99")]
    wmax, wrow = max(w_valid, key=lambda p: p[0])
    erd = by_input(base, "erddap_cwwcNDBCMet_41009_2024_WVHT")
    rd = list(csv.reader(io.StringIO(base.bytes(erd).decode())))
    ev = [(float(r[2]), r[1]) for r in rd[2:] if r[2] not in ("NaN", "")]
    emax = max(ev, key=lambda p: p[0])
    out["R7"] = {"class": "DOC+RECALC; corroborated by NOAA CoastWatch ERDDAP cwwcNDBCMet",
                 "rows": len(lines), "wvht_99_rows": sum(1 for v in w_raw if v in ("99.00", "99.0", "99")),
                 "wvht_valid_rows": len(w_valid), "max_wvht_m": wmax,
                 "max_row": " ".join(wrow[:5]),
                 "max_rows_count": sum(1 for v, _ in w_valid if v == wmax),
                 "erddap": {"rows": len(rd) - 2, "non_null": len(ev), "max_m": emax[0], "time": emax[1],
                            "sha256": erd["response"]["body_sha256"]}}

    # S1, S2, S5: values if a workflow proceeds equal N2 (only attributes changed)
    for t in ("S1", "S2", "S5"):
        fs = read_station_file(syn[t].path(syn[t].doc["entries"][0]))
        same = fs["zeta"] == f3d["zeta"] and fs["times"] == f3d["times"] and fs["names"] == f3d["names"]
        out[t] = {"class": "CON", "zeta_identical_to_real_file": same, "zeta_attrs": fs["zeta_attrs"],
                  "values_if_proceeding": out["N2"]["stats"]}
    fs = read_station_file(syn["S3"].path(syn["S3"].doc["entries"][0]))
    out["S3"] = {"class": "CON", "zeta_identical_to_real_file": fs["zeta"] == f2d["zeta"],
                 "title": fs["global"]["title"], "comments": fs["global"]["comments"]}

    # S4: N1 with five observation values made blank or non-finite
    m4 = syn["S4"].doc["entries"][0]
    obs4, cnt4 = obs_map(coops_records(syn["S4"].bytes(m4)))
    res4 = lead_window_compare(f2d, station_index(f2d, "8443970"), c2d, obs4)
    out["S4"] = {"class": "CON+RECALC", "obs_excluded": cnt4, **res4}

    (vdir / "references/computed_values.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str)[:12000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
