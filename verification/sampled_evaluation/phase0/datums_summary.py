#!/usr/bin/env python3
"""Phase 0: MSL / NAVD88 publication and epoch class per mapped station (from the datums archive)."""
import collections, json, sys
from pathlib import Path
PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "reference"))
import archive_io as aio
from classify import load_datums, epoch_class
d = load_datums([aio.Archive(PKG / "data/archive/meta")])
inv = json.loads((PKG / "phase0/station_inventory.json").read_text())["union_ids"]
rows = [dict(id=s, in3d=any(f.startswith("3d") for f in fs), epoch=d.get(s, {}).get("epoch"),
             ec=epoch_class(d.get(s, {}).get("epoch")) if s in d else "none",
             msl="MSL" in d.get(s, {}).get("published", []), navd="NAVD88" in d.get(s, {}).get("published", []))
        for s, fs in sorted(inv.items())]
(PKG / "phase0/datums_summary.json").write_text(json.dumps({"stations": rows}, indent=1) + "\n")
print(collections.Counter(r["ec"] for r in rows))
