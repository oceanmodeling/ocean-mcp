#!/usr/bin/env python3
"""Build (or extend) a replay-launcher archive from records of run_log/noaa_requests.jsonl.

Each selected fetch record (final attempt, status recorded, body saved) becomes one archive entry
keyed exactly as the launcher keys requests (``request_key`` of the copied WP1 launcher). The body
file is hard-linked (or copied) into ``<archive>/bodies/<sha256><ext>`` and its SHA-256 is
re-verified. ``kind`` is set by the caller: ``exact`` (S3 files, metadata), ``coops_master``
(CO-OPS water_level with data) or ``coops_error_master`` (CO-OPS error document).

Usage: python -I index_from_fetchlog.py ARCHIVE_DIR --tag TAG [--tag TAG] [--kind auto|exact]
"""
import argparse
import hashlib
import json
import re
import os
import shutil
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "replay"))
import ocean_replay_launcher as L  # noqa: E402  (stdlib-only at import time)

NODATA_SHA256 = "500bdf8b7540e3b178fa94711e95e7bd7633578dac4778da5faed9dc45cbfb0f"


def kind_for(url: str, body: bytes, mode: str) -> str:
    if mode == "exact":
        return "exact"
    if "/api/prod/datagetter" in url and "product=water_level" in url:
        try:
            d = json.loads(body)
        except Exception:
            return "exact"
        if "data" in d and "error" not in d:
            return "coops_master"
        msg = str((d.get("error") or {}).get("message", "")).strip()
        if (hashlib.sha256(body).hexdigest() == NODATA_SHA256 or msg.startswith("The supported Datum values are")
                or re.match(r"^There is no [A-Za-z0-9]+ for the station", msg)):  # amendment A5
            return "coops_error_master"
        return "coops_error_other"  # an acquisition failure: never served, never read as a fact
    return "exact"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--tag", action="append", required=True)
    ap.add_argument("--kind", default="auto", choices=("auto", "exact"))
    a = ap.parse_args()
    root = Path(a.archive)
    (root / "bodies").mkdir(parents=True, exist_ok=True)
    idx_p = root / "index.json"
    doc = json.loads(idx_p.read_text()) if idx_p.exists() else {"format": "ocean-replay-archive/1", "entries": [], "dns": {}}
    have = {L.key_string(e["key"]) for e in doc["entries"]}
    final = {}
    for line in (PKG / "run_log/noaa_requests.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["tag"] in a.tag:
            final[(r["method"], r["url"])] = r  # last attempt wins
    added = 0
    for (method, url), r in final.items():
        if r.get("error") or r.get("path") is None or r["status"] is None:
            continue
        key = L.request_key(method, url)
        ks = L.key_string(key)
        if ks in have:
            continue
        src = PKG / r["path"]
        body = src.read_bytes()
        sha = hashlib.sha256(body).hexdigest()
        if sha != r["sha256"]:
            raise SystemExit(f"sha mismatch {src}")
        dst = root / "bodies" / src.name
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
        doc["entries"].append({
            "id": f"e{len(doc['entries']) + 1:05d}", "kind": kind_for(url, body, a.kind), "key": key, "url": url,
            "response": {"status": r["status"], "headers": [["content-type", r.get("content_type") or ""]],
                         "body_file": f"bodies/{src.name}", "body_sha256": sha, "bytes": len(body)},
            "provenance": {"source": "noaa_fetch", "retrieved_at": r["end_utc"], "tag": r["tag"],
                           "last_modified": r.get("last_modified"), "etag": r.get("etag")},
        })
        have.add(ks)
        added += 1
    idx_p.write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({"archive": str(root), "added": added, "entries": len(doc["entries"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
