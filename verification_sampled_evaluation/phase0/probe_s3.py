#!/usr/bin/env python3
"""Phase 0 probe: which 12z station files exist on the NOAA open-data buckets for the
sampled dates (S3 ListObjectsV2 with a per-day key prefix; one request per product and date)."""
import datetime as dt, json, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import noaa_fetch as nf

OUT = nf.PKG / "phase0" / "s3_listings"
def dates():
    d0, d1 = dt.date(2026, 6, 1), dt.date(2026, 11, 2)
    weekly = [d0 + dt.timedelta(days=7 * k) for k in range(0, 100) if d0 + dt.timedelta(days=7 * k) <= d1]
    daily = [dt.date(2026, 8, 13) + dt.timedelta(days=k) for k in range(8)]
    return sorted(set(weekly) | set(daily)), weekly, daily

def url(product, d):
    s = d.strftime("%Y%m%d")
    if product == "3d":
        return ("https://noaa-nos-stofs3d-pds.s3.amazonaws.com/?list-type=2&prefix="
                f"STOFS-3D-Atl/stofs_3d_atl.{s}/stofs_3d_atl.t12z.points")
    return f"https://noaa-gestofs-pds.s3.amazonaws.com/?list-type=2&prefix=stofs_2d_glo.{s}/stofs_2d_glo.t12z.points"

def parse(path):
    t = Path(path).read_text()
    return [dict(key=k, size=int(s), last_modified=m) for k, m, s in
            re.findall(r"<Key>([^<]+)</Key><LastModified>([^<]+)</LastModified>.*?<Size>(\d+)</Size>", t, re.S)]

if __name__ == "__main__":
    extra = [dt.date.fromisoformat(a) for a in sys.argv[1:]]
    alld, weekly, daily = dates()
    res = []
    for d in (extra or alld):
        for p in ("3d", "2d"):
            r = nf.fetch(url(p, d), OUT, phase="phase0", tag=f"s3_list_{p}")
            res.append({"product": p, "date": d.isoformat(), "status": r["status"], "sha256": r["sha256"],
                        "path": r["path"], "objects": parse(nf.PKG / r["path"]) if r["path"] else None})
            print(p, d, r["status"], [ (o["key"].split("/")[-1], o["size"]) for o in (res[-1]["objects"] or [])])
    name = "s3_probe_extra.json" if extra else "s3_probe.json"
    (nf.PKG / "phase0" / name).write_text(json.dumps({"weekly": [d.isoformat() for d in weekly],
        "daily": [d.isoformat() for d in daily], "results": res}, indent=1) + "\n")
