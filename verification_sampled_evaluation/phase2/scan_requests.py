#!/usr/bin/env python3
"""Pre-session scan (DESIGN.md 3.2, acquisition only; never used by the reference or the grading).

For every downloaded station file (cwl): map the station IDs (Phase 0 rule), list IDs that are
not in the Phase 0 union, and compute the CO-OPS range stofs-mcp 0.2.0 will request for each
case (its window starts at the first value that is neither _FillValue nor |v| > 1e10, and runs
72 h (3D) or 54 h (2D), capped at the file end). Ranges that do not lie inside one master block
are listed with the exact begin/end strings the tool sends. 0.3.0's range always lies inside the
lead window and therefore inside a block (check_blocks.py).

Writes phase2/scan_requests.json and phase2/fetch_plan_supplement.json (new IDs: datums, masters,
monthly mean; out-of-block ranges: one exact-range master each).
Usage: python -I scan_requests.py   (in .envs/ref)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "phase2"))
sys.path.insert(0, str(PKG / "reference"))
import netCDF4  # noqa: E402
import numpy as np  # noqa: E402

import plan  # noqa: E402
import rules  # noqa: E402

U = dt.timezone.utc
TOK = re.compile(r"(?<!\d)\d{7}(?!\d)")
MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"


def blocks(bs):
    return [(dt.datetime.strptime(a, "%Y%m%d").replace(tzinfo=U),
             dt.datetime.strptime(b, "%Y%m%d").replace(tzinfo=U) + dt.timedelta(hours=23, minutes=59)) for a, b in bs]


def main() -> int:
    recs = [json.loads(x) for x in (PKG / "run_log/noaa_requests.jsonl").read_text().splitlines()]
    files = {}
    for r in recs:
        if r["phase"] == "phase2" and r["tag"] in ("s3_3d", "s3_2d") and r["status"] == 200:
            files[r["url"]] = PKG / r["path"]
    for it in json.loads((PKG / "phase2/fetch_plan.json").read_text())["items"]:
        if it.get("seed_sha256"):
            files[it["url"]] = PKG / "data/raw/models" / f"{it['seed_sha256']}.nc"
    act = {s["id"] for s in json.loads((PKG / "phase0/coops/d9ae610d14ccb426fce30ec9daad921a8f57169e9ff57ad6610a204aad457284.json").read_text())["stations"]}
    his = {s["id"] for s in json.loads((PKG / "phase0/coops/b34a6a56c4c0be623b3de3a3cac8632770d55207ef66b0f8dc927e80952a28e9.json").read_text())["stations"]}
    union = json.loads((PKG / "phase0/station_inventory.json").read_text())["union_ids"]
    dsum = {r["id"]: r for r in json.loads((PKG / "phase0/datums_summary.json").read_text())["stations"]}
    new_ids, out_of_block, per_file = {}, [], []
    for url, p in sorted(files.items()):
        prod = "3d" if "stofs_3d_atl" in url else "2d"
        day = re.search(r"\.(\d{8})/", url).group(1)
        C = dt.datetime.strptime(day + "12", "%Y%m%d%H").replace(tzinfo=U)
        nc = netCDF4.Dataset(str(p))
        nc.set_auto_mask(False)
        names = [str(s).strip() for s in netCDF4.chartostring(nc.variables["station_name"][:])]
        t = rules.decode_times(np.asarray(nc.variables["time"][:]).tolist(), str(nc.variables["time"].units))
        z = nc.variables["zeta"]
        fill = float(np.asarray(z.getncattr("_FillValue")).ravel()[0]) if "_FillValue" in z.ncattrs() else None
        Z = np.asarray(z[:], dtype=float)
        g = {k: str(nc.getncattr(k)) for k in nc.ncattrs()}
        nc.close()
        ids = []
        for i, n in enumerate(names):
            m = [x for x in TOK.findall(n) if x in act or x in his]
            if len(m) == 1 and m[0] not in ids:
                ids.append(m[0])
        per_file.append({"url": url, "version": rules.product_version(prod, g), "n_records": len(names),
                         "n_ids": len(ids), "title": g.get("title"), "history_head": g.get("history", "")[:120]})
        H = 72 if prod == "3d" else 54
        datum = "NAVD" if prod == "3d" else "MSL"
        bl = blocks(plan.NAVD_BLOCKS if datum == "NAVD" else plan.MSL_BLOCKS)
        for sid in ids:
            if sid not in union:
                new_ids.setdefault(sid, set()).add(prod)
            j = next(i for i, n in enumerate(names) if sid in n)  # 0.2.0 picks the first substring match
            col = Z[:, j]
            ok = ~(np.abs(col) > 1e10)
            if fill is not None:
                ok &= col != fill
            idx = np.nonzero(ok)[0]
            if idx.size == 0:
                continue
            t0 = t[idx[0]]
            tmax = t0 + dt.timedelta(hours=H)
            last = max(t[i] for i in idx if t[i] <= tmax)
            if not any(a <= t0 and last <= b for a, b in bl):
                out_of_block.append({"product": prod, "cycle": day, "station": sid, "datum": datum,
                                     "begin": t0.strftime("%Y%m%d %H:%M"), "end": last.strftime("%Y%m%d %H:%M")})
    items = []
    for sid, prods in sorted(new_ids.items()):
        items.append({"group": "supp_datums", "url": f"{MDAPI}/stations/{sid}/datums.json?units=metric", "station": sid})
        for b in plan.MSL_BLOCKS:
            items.append({"group": "supp_coops_MSL", "url": plan.wl(sid, "MSL", *b), "station": sid})
        if "3d" in prods:
            for b in plan.NAVD_BLOCKS:
                items.append({"group": "supp_coops_NAVD", "url": plan.wl(sid, "NAVD", *b), "station": sid})
        items.append({"group": "supp_monthly_mean", "url": plan.monthly(sid), "station": sid})
    for o in out_of_block:
        items.append({"group": "supp_exact_range", "url": plan.wl(o["station"], o["datum"], o["begin"], o["end"]),
                      "station": o["station"], "note": f"0.2.0 range outside a block, {o['product']} {o['cycle']}"})
    (PKG / "phase2/scan_requests.json").write_text(json.dumps(
        {"files": per_file, "new_ids": {k: sorted(v) for k, v in new_ids.items()},
         "out_of_block_020": out_of_block, "datums_known_unpublished": {k: dsum[k] for k in ()}}, indent=1) + "\n")
    (PKG / "phase2/fetch_plan_supplement.json").write_text(json.dumps({"items": items}, indent=1) + "\n")
    print(json.dumps({"files": len(per_file), "new_ids": len(new_ids), "out_of_block_020": len(out_of_block),
                      "supplement_requests": len(items),
                      "versions": sorted({(f["url"].split("/")[2][:12], f["version"]) for f in per_file})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
