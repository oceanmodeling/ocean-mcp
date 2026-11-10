#!/usr/bin/env python3
"""Deterministic Phase 2 request plan (DESIGN.md 3 and 6). Writes phase2/fetch_plan.json.

The plan is computed from the frozen design constants below, the Phase 0 station inventory and
the Phase 0 datum metadata. It is the request budget: Phase 2 fetches exactly these URLs, plus
the reserve items of DESIGN.md 6.2, and nothing else.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlencode

PKG = Path(__file__).resolve().parent.parent
APP = "ocean_mcp_wp5"
COOPS = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
S3_3D = "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl"
S3_2D = "https://noaa-gestofs-pds.s3.amazonaws.com"

# --- sampling rule (DESIGN.md 2.1) --------------------------------------------------------
FIRST, LAST = dt.date(2026, 6, 1), dt.date(2026, 11, 2)
WEEKLY = [FIRST + dt.timedelta(days=7 * k) for k in range(30) if FIRST + dt.timedelta(days=7 * k) <= LAST]
DAILY = [dt.date(2026, 8, 13) + dt.timedelta(days=k) for k in range(8)]
CYCLES = sorted(set(WEEKLY) | set(DAILY))
PREVIOUSLY_SEEN = {dt.date(2026, 2, 18), dt.date(2026, 8, 16), dt.date(2026, 8, 17), dt.date(2026, 10, 30)}

# --- observation master blocks (DESIGN.md 3.2): whole UTC days, each <= 29 days, boundaries in
# the gaps between cycle windows so every request any tool makes lies inside one block.
MSL_BLOCKS = [("20260518", "20260530"), ("20260531", "20260627"), ("20260628", "20260725"),
              ("20260726", "20260822"), ("20260823", "20260919"), ("20260920", "20261017"),
              ("20261018", "20261115")]
NAVD_BLOCKS = MSL_BLOCKS[1:]
MONTHLY_RANGE = ("20160101", "20261031")  # 2016-2025 climatology + the 12-month means

# WP1 archive entries that are byte-identical inputs of this sample (seeded by copy, checksums
# verified): 3D 2026-08-16 and 2026-08-17 12z station files.
SEEDED = {
    f"{S3_3D}/stofs_3d_atl.20260816/stofs_3d_atl.t12z.points.cwl.nc": "f78e84ef18ae35083c7efe83c26df4c907d7359fb397155e1c2d748001d02462",
    f"{S3_3D}/stofs_3d_atl.20260817/stofs_3d_atl.t12z.points.cwl.nc": "f47962fa8504ef4017e5a858603fa8ee0894546524e125ec38025e1fe05289c4",
}


def wl(station: str, datum: str, begin: str, end: str) -> str:
    # same parameter set as stofs-mcp 0.3.0 and 0.2.0 fetch_coops_observations
    return COOPS + "?" + urlencode({"station": station, "product": "water_level", "datum": datum,
                                    "units": "metric", "time_zone": "gmt", "format": "json",
                                    "begin_date": begin, "end_date": end, "application": APP})


def monthly(station: str) -> str:
    return COOPS + "?" + urlencode({"station": station, "product": "monthly_mean", "datum": "MSL",
                                    "units": "metric", "time_zone": "gmt", "format": "json",
                                    "begin_date": MONTHLY_RANGE[0], "end_date": MONTHLY_RANGE[1],
                                    "application": APP})


def main() -> None:
    inv = json.loads((PKG / "phase0/station_inventory.json").read_text())
    dsum = {r["id"]: r for r in json.loads((PKG / "phase0/datums_summary.json").read_text())["stations"]}
    items = []
    for d in CYCLES:
        s = d.strftime("%Y%m%d")
        for prod, url in (("3d", f"{S3_3D}/stofs_3d_atl.{s}/stofs_3d_atl.t12z.points.cwl.nc"),
                          ("2d", f"{S3_2D}/stofs_2d_glo.{s}/stofs_2d_glo.t12z.points.cwl.nc"),
                          ("2d_noanomaly", f"{S3_2D}/stofs_2d_glo.{s}/stofs_2d_glo.t12z.points.cwl.noanomaly.nc")):
            items.append({"group": f"s3_{prod}", "url": url, "seed_sha256": SEEDED.get(url),
                          "optional": prod == "2d_noanomaly"})
    for sid, files in sorted(inv["union_ids"].items()):
        in3d = any(f.startswith("3d") for f in files)
        r = dsum.get(sid, {})
        for datum, blocks, needed, pub in (("MSL", MSL_BLOCKS, True, r.get("msl")),
                                           ("NAVD", NAVD_BLOCKS, in3d, r.get("navd"))):
            if not needed:
                continue
            if pub:
                for b in blocks:
                    items.append({"group": f"coops_{datum}", "url": wl(sid, datum, *b), "station": sid})
            else:  # first block only; escalate to all blocks unless CO-OPS answers 400 unsupported datum
                items.append({"group": f"coops_{datum}_unpublished_probe", "url": wl(sid, datum, *blocks[0]),
                              "station": sid, "escalate_blocks": [list(b) for b in blocks[1:]]})
        if r.get("msl"):
            items.append({"group": "coops_monthly_mean", "url": monthly(sid), "station": sid})
    counts = {}
    for it in items:
        if it.get("seed_sha256"):
            key = it["group"] + "_seeded"
        else:
            key = it["group"]
        counts[key] = counts.get(key, 0) + 1
    planned = sum(v for k, v in counts.items() if not k.endswith("_seeded"))
    reserve = {
        "new_station_ids_found_in_downloaded_files": 150,
        "escalation_of_unpublished_datum_probes": 120,
        "replay_rule_validation_live_requests": 4,
        "retries_at_most_one_per_request": 160,
    }
    out = {"cycles": [d.isoformat() for d in CYCLES], "weekly": [d.isoformat() for d in WEEKLY],
           "daily": [d.isoformat() for d in DAILY],
           "previously_seen": sorted(d.isoformat() for d in PREVIOUSLY_SEEN if d in CYCLES),
           "msl_blocks": MSL_BLOCKS, "navd_blocks": NAVD_BLOCKS, "monthly_range": MONTHLY_RANGE,
           "counts": counts, "planned_requests": planned, "reserve": reserve,
           "budget_cap": planned + sum(reserve.values()), "items": items}
    (PKG / "phase2/fetch_plan.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("counts", "planned_requests", "reserve", "budget_cap", "previously_seen")}, indent=1))
    print("cycles", len(CYCLES))


if __name__ == "__main__":
    main()
