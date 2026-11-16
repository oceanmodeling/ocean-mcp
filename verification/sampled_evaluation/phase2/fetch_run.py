#!/usr/bin/env python3
"""Phase 2 acquisition driver (DESIGN.md 3 and 6). NOT RUN before the user says "proceed".

Fetches the items of phase2/fetch_plan.json in order through phase0/noaa_fetch.py (one request
at a time, >= 1.2 s apart, at most one retry, budget-checked against the cap), skipping items
already fetched, seeding the two WP1 files by copy (checksum verified), and escalating an
unpublished-datum probe to all blocks only when CO-OPS did not answer with the HTTP 400
unsupported-datum document. Archives are built afterwards with phase2/index_from_fetchlog.py.

Usage: python -I fetch_run.py [--groups G ...] [--skip-optional]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "phase0"))
import noaa_fetch as nf  # noqa: E402

WP1_BODIES = Path("/mnt/d/ocean-mcp/.claude/worktrees/safeguards-comparison/"
                  "verification_safeguards_comparison/data/archive/base/bodies")
OUT = {"s3": PKG / "data/raw/models", "coops": PKG / "data/raw/coops"}
UNSUPPORTED = "The supported Datum values are"


def done_urls() -> dict:
    out = {}
    if nf.LOG.exists():
        for line in nf.LOG.read_text().splitlines():
            r = json.loads(line)
            if r["phase"] == "phase2":
                out[r["url"]] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", nargs="*")
    ap.add_argument("--skip-optional", action="store_true")
    a = ap.parse_args()
    plan = json.loads((PKG / "phase2/fetch_plan.json").read_text())
    nf.set_budget("phase2", plan["budget_cap"])
    done = done_urls()
    seeds = []
    for it in plan["items"]:
        if a.groups and it["group"] not in a.groups:
            continue
        if it.get("optional") and a.skip_optional:
            continue
        if it.get("seed_sha256"):
            src = WP1_BODIES / f"{it['seed_sha256']}.nc"
            if hashlib.sha256(src.read_bytes()).hexdigest() != it["seed_sha256"]:
                raise SystemExit(f"seed checksum mismatch: {src}")
            dst = OUT["s3"] / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
            seeds.append({"url": it["url"], "sha256": it["seed_sha256"], "path": str(dst.relative_to(PKG))})
            continue
        if it["url"] in done and done[it["url"]]["error"] is None:
            continue
        kind = "s3" if it["group"].startswith("s3_") else "coops"
        r = nf.fetch(it["url"], OUT[kind], phase="phase2", tag=it["group"])
        print(json.dumps({"group": it["group"], "status": r["status"], "bytes": r["bytes"], "url": it["url"][:120]}), flush=True)
        if it.get("escalate_blocks"):
            body = (PKG / r["path"]).read_bytes() if r.get("path") else b""
            unsupported = r["status"] == 400 and UNSUPPORTED in body.decode("utf-8", "replace")
            if not unsupported:
                base, query = it["url"].split("?", 1)
                for b0, b1 in it["escalate_blocks"]:
                    q = dict(parse_qsl(query))
                    q["begin_date"], q["end_date"] = b0, b1
                    url = base + "?" + urlencode(q)
                    if url in done:
                        continue
                    r2 = nf.fetch(url, OUT["coops"], phase="phase2", tag=it["group"] + "_escalated")
                    print(json.dumps({"group": it["group"] + "_escalated", "status": r2["status"], "url": url[:120]}), flush=True)
    (PKG / "run_log/phase2_seeds.json").write_text(json.dumps(seeds, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
