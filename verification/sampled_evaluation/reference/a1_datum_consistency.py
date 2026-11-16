#!/usr/bin/env python3
"""Amendment A1: per-station datum consistency d_s = Delta_V(s) - C_s (AMENDMENTS.md A1).

Delta_V(s): NOAA coastalmodeling_vdatum convert("navd88", "lmsl", lat, lon, z=0) at the station,
            i.e. the elevation of the NAVD88 zero above VDatum's LMSL surface;
C_s:        NAVD88 - MSL from the station's CO-OPS datums.json (both relative to station datum).
d_s > 0 means the CO-OPS MSL datum lies above VDatum's LMSL at the station.

The library is the unchanged copy in reference/vendor_coastalmodeling_vdatum/ (checked against
SHA256SUMS), loaded as a stand-alone package; no Ocean-MCP package is imported. The two grids are
local files fetched once through phase0/noaa_fetch.py; PROJ network access is disabled.

Usage:
  python -I a1_datum_consistency.py --fetch-grids            # two logged requests
  python -I a1_datum_consistency.py --run OUT.json           # offline
Run in .envs/vdatum (pyproj 3.8.0, numpy 2.5.4).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
VENDOR = HERE / "vendor_coastalmodeling_vdatum"
GRID_DIR = PKG / "data/raw/vdatum_grids"
GRIDS = {
    "NAVD88_G2018": "https://cdn.proj.org/us_noaa_g2018u0.tif",
    "LMSL_ITRF2020_2020": ("https://noaa-nos-stofs2d-pds.s3.amazonaws.com/_archive/coastalmodeling-vdatum/"
                           "us_noaa_nos_LMSL-ITRF2020_2020.0_nwldatum_4.7.0_20240621_3.tif"),
}
BOSTON = {"lat": 42.3539, "lon": -71.05028, "navd88_to_lmsl_boston_package": 0.09173215948229796}
TOL_SAME = 1e-6
S10_LIMIT_M = 0.03


def load_library():
    for line in (VENDOR / "SHA256SUMS").read_text().splitlines():
        sha, name = line.split()
        if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != sha:
            raise SystemExit(f"vendored file changed: {name}")
    spec = importlib.util.spec_from_file_location("cm_vdatum", VENDOR / "__init__.py",
                                                  submodule_search_locations=[str(VENDOR)])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["cm_vdatum"] = pkg
    spec.loader.exec_module(pkg)
    import importlib as il
    return il.import_module("cm_vdatum.vdatum"), il.import_module("cm_vdatum._path")


def fetch_grids() -> None:
    sys.path.insert(0, str(PKG / "phase0"))
    import noaa_fetch as nf
    out = {}
    for name, url in GRIDS.items():
        r = nf.fetch(url, GRID_DIR, phase="phase2", tag="a1_vdatum_grid")
        out[name] = {k: r[k] for k in ("url", "status", "bytes", "sha256", "path", "end_utc")}
        print(json.dumps(out[name]))
    (PKG / "run_log/a1_grids.json").write_text(json.dumps(out, indent=1) + "\n")


def run(out_path: Path) -> int:
    import numpy as np
    import pyproj
    vd, path = load_library()
    grids = json.loads((PKG / "run_log/a1_grids.json").read_text())
    import os
    for name, g in grids.items():
        p = PKG / g["path"]
        if hashlib.sha256(p.read_bytes()).hexdigest() != g["sha256"]:
            raise SystemExit(f"grid changed: {p}")
        named = GRID_DIR / g["url"].rsplit("/", 1)[1]  # PROJ needs the .tif name
        if not named.exists():
            os.link(p, named)
        setattr(path, name, str(named))
    pyproj.network.set_network_enabled(active=False)

    sys.path.insert(0, str(HERE))
    import archive_io as aio
    from classify import load_datums, epoch_class
    datums = load_datums([aio.Archive(PKG / "data/archive/meta")])
    lists = {}
    for p in sorted((PKG / "phase0/coops").glob("*.json")):
        d = json.loads(p.read_text())
        if isinstance(d, dict) and "stations" in d:
            for s in d["stations"]:
                lists.setdefault(s["id"], s)
    boundary = {s["id"] for s in json.loads((HERE / "boundary_stations.json").read_text())["stations"]}

    _, _, zb = vd.convert("navd88", "lmsl", np.array([BOSTON["lat"]]), np.array([BOSTON["lon"]]),
                          np.zeros(1), online=False)
    boston_same = abs(float(zb[0]) - BOSTON["navd88_to_lmsl_boston_package"]) <= TOL_SAME

    rows, skipped = [], []
    ids = sorted(s for s, m in datums.items() if {"MSL", "NAVD88"} <= set(m.get("published", [])))
    for sid in ids:
        st = lists.get(sid)
        m = datums[sid]
        if not st or st.get("lat") is None:
            skipped.append({"station_id": sid, "reason": "no coordinates in the CO-OPS lists"})
            continue
        c = m["values"]["NAVD88"] - m["values"]["MSL"]
        _, _, z = vd.convert("navd88", "lmsl", np.array([float(st["lat"])]), np.array([float(st["lng"])]),
                             np.zeros(1), online=False)
        dv = float(z[0])
        if not math.isfinite(dv):
            skipped.append({"station_id": sid, "name": st.get("name"), "reason": "outside the VDatum grids (non-finite)"})
            continue
        rows.append({"station_id": sid, "name": st.get("name"), "lat": st["lat"], "lon": st["lng"],
                     "delta_v_navd88_above_lmsl_m": dv, "c_navd88_minus_msl_m": c, "d_m": dv - c,
                     "epoch": m.get("epoch"), "epoch_class": epoch_class(m.get("epoch")),
                     "boundary_station": sid in boundary, "s10_keep": abs(dv - c) <= S10_LIMIT_M})
    ds = [r["d_m"] for r in rows]
    big = max(rows, key=lambda r: abs(r["d_m"])) if rows else None
    out = {"sign_convention": "d = Delta_V - C = (CO-OPS MSL) - (VDatum LMSL); > 0: CO-OPS MSL above VDatum LMSL",
           "boston_check": {"offline": float(zb[0]), "boston_package": BOSTON["navd88_to_lmsl_boston_package"],
                            "same_within_1e-6_m": boston_same},
           "n_stations_both_datums": len(ids), "n_evaluated": len(rows), "n_not_evaluated": len(skipped),
           "median_m": statistics.median(ds) if ds else None, "sd_m": statistics.stdev(ds) if len(ds) > 1 else None,
           "largest_abs": big and {k: big[k] for k in ("station_id", "name", "d_m", "epoch")},
           "n_abs_le_0_03": sum(abs(x) <= S10_LIMIT_M for x in ds),
           "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str, "grids": grids,
           "rows": rows, "not_evaluated": skipped}
    out_path.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("boston_check", "n_evaluated", "n_not_evaluated", "median_m", "sd_m",
                                          "largest_abs", "n_abs_le_0_03")}, indent=1))
    return 0 if boston_same else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-grids", action="store_true")
    ap.add_argument("--run")
    a = ap.parse_args()
    if a.fetch_grids:
        fetch_grids()
    if a.run:
        sys.exit(run(Path(a.run)))
