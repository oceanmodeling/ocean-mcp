#!/usr/bin/env python3
"""Validate replay rule 3 (CO-OPS slicing) against one real request.

Makes one live CO-OPS request for a sub-window of an archived master that holds
verified data, recording it (record mode) into its own archive,
data/archive/validation_slice/, so that the base archive is not changed and the
Phase 2 sessions keep using the slicing rule. It then asks the replay engine,
on the base archive only, to answer the same request, and compares the two
bodies byte for byte, and record by record.

The request is the one stofs-mcp 0.3.0 makes for task R4b (Boston, datum MSL,
0 < lead <= 48 h of the 2026-08-17 12z cycle), so the check covers the exact
parameter layout the sessions use.

Usage: python -I validate_slice.py <verification_dir>   (harness environment: needs httpx)
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?" + urlencode({
    "station": "8443970", "product": "water_level", "datum": "MSL", "units": "metric", "time_zone": "gmt",
    "format": "json", "begin_date": "20260817 12:06", "end_date": "20260819 12:00", "application": "stofs_mcp"})


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    here = vdir / "replay"
    spec = importlib.util.spec_from_file_location("ocean_replay_launcher", here / "ocean_replay_launcher.py")
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    val_dir = vdir / "data/archive/validation_slice"
    log = vdir / "run_log/validate_slice_record.jsonl"

    # 1. the slice the replay would serve, from the base archive only (no network involved)
    replay = L.Engine("replay", [L.Archive(vdir / "data/archive/base")], None)
    status_s, _, body_s, info_s = replay.replay("GET", URL)

    # 2. one real request, recorded into its own archive
    engine = L.install("record", [str(val_dir)], str(log))
    import httpx

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(URL)
    live = resp.content
    entry = engine.archives[0].by_key[L.key_string(L.request_key("GET", URL))]
    entry["provenance"].update({"input_name": "validation_coops_8443970_MSL_20260817T1206_20260819T1200",
                                "note": "rule-3 validation only; not used by any task"})
    engine.archives[0].save()

    d_live, d_slice = json.loads(live), json.loads(body_s)
    rec_live, rec_slice = d_live.get("data", []), d_slice.get("data", [])
    diffs = [(a, b) for a, b in zip(rec_live, rec_slice) if a != b]
    first_byte_diff = next((i for i, (a, b) in enumerate(zip(live, body_s)) if a != b), None)
    out = {
        "request": URL,
        "live": {"http_status": resp.status_code, "bytes": len(live), "sha256": sha(live),
                 "records": len(rec_live), "q": sorted({r.get("q") for r in rec_live}),
                 "archive_entry": entry["id"], "retrieved_at": entry["provenance"]["retrieved_at"]},
        "slice": {"status": status_s, "bytes": len(body_s), "sha256": sha(body_s), "records": len(rec_slice),
                  **info_s},
        "bytes_identical": live == body_s,
        "metadata_identical": d_live.get("metadata") == d_slice.get("metadata"),
        "record_count_identical": len(rec_live) == len(rec_slice),
        "records_identical": rec_live == rec_slice,
        "differing_records": len(diffs) + abs(len(rec_live) - len(rec_slice)),
        "first_differing_records": diffs[:5],
        "first_byte_difference_at": first_byte_diff,
        "length_difference": len(live) - len(body_s),
    }
    if first_byte_diff is not None:
        lo = max(0, first_byte_diff - 60)
        out["context_live"] = live[lo:first_byte_diff + 60].decode(errors="replace")
        out["context_slice"] = body_s[lo:first_byte_diff + 60].decode(errors="replace")
    (vdir / "run_log/slice_validation.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0 if out["records_identical"] else 4


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
