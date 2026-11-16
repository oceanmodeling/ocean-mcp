#!/usr/bin/env python3
"""Phase 0 probe: CO-OPS datums (metadata API) for every mapped station ID; one request each."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import noaa_fetch as nf
M = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
inv = json.loads((nf.PKG / "phase0/station_inventory.json").read_text())
ids = sys.argv[1:] or sorted(inv["union_ids"])
out_p = nf.PKG / "phase0/datums_probe.jsonl"
done = set()
if out_p.exists():
    done = {json.loads(l)["id"] for l in out_p.read_text().splitlines() if l.strip()}
for sid in ids:
    if sid in done:
        continue
    r = nf.fetch(f"{M}/stations/{sid}/datums.json?units=metric", nf.PKG / "phase0/coops/datums", phase="phase0", tag="coops_datums")
    with open(out_p, "a") as fh:
        fh.write(json.dumps({"id": sid, "status": r["status"], "sha256": r["sha256"], "path": r["path"], "error": r["error"]}) + "\n")
print("done", len(ids))
