#!/usr/bin/env python3
"""Write data/manifest.json: every input with SHA-256, source URL and retrieval time.

Lists each entry of the base and synthetic replay archives, re-hashes every
body on disk, and records the WP0 manifest and the stofs-mcp 0.3.0 wheel this
package depends on. Fails if a body on disk does not match its index.

Usage: python -I build_manifest.py <verification_dir> <repo_root>
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    vdir, repo = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    entries, bad = [], []
    for idx in sorted((vdir / "data/archive").rglob("index.json")):
        arc = idx.parent
        doc = json.loads(idx.read_text())
        for e in doc["entries"]:
            body = arc / e["response"]["body_file"]
            present = body.exists()
            ok = present and sha256(body) == e["response"]["body_sha256"]
            if present and not ok:
                bad.append(str(body))
            p = e["provenance"]
            entries.append({
                "archive": str(arc.relative_to(vdir)), "entry": e["id"], "kind": e.get("kind"),
                "url": e["url"], "http_status": e["response"]["status"], "bytes": e["response"]["bytes"],
                "sha256": e["response"]["body_sha256"], "body_file": e["response"]["body_file"],
                "body_present": present, "source": p.get("source"), "retrieved_at": p.get("retrieved_at"),
                "input_name": p.get("input_name"), "tasks": p.get("tasks") or ([p["task"]] if p.get("task") else None),
                "origin_file": p.get("origin_file"), "origin_sha256": p.get("origin_sha256"),
                "mutation": p.get("mutation"), "label": p.get("label"), "note": p.get("note"),
            })
        if doc.get("dns"):
            entries.append({"archive": str(arc.relative_to(vdir)), "dns_answers_recorded": doc["dns"]})
    wp0 = repo / "verification_release_readiness"
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "sha256 identifies the archived bytes; it does not guarantee that an upstream object is immutable. "
                "CO-OPS 2026-10-29..11-01 observations were preliminary (q=p) when archived. Entries with source "
                "'synthetic' are controlled mutations. 'seeded' entries were copied from earlier packages, whose "
                "manifests recorded their retrieval.",
        "depends_on": {
            "wp0_manifest": {"path": "verification_release_readiness/manifest.json",
                             "sha256": sha256(wp0 / "manifest.json")},
            "stofs_mcp_0.3.0_wheel": {"path": "verification_release_readiness/dist/stofs_mcp-0.3.0-py3-none-any.whl",
                                      "sha256": sha256(wp0 / "dist/stofs_mcp-0.3.0-py3-none-any.whl")},
            "boston_independent_statistics": {
                "path": ".claude/worktrees/stofs-v31-boston-v2/verification_stofs_v31_boston/results/statistics_independent.json",
                "sha256": sha256(repo / ".claude/worktrees/stofs-v31-boston-v2/verification_stofs_v31_boston/results/statistics_independent.json")},
        },
        "entries": entries,
    }
    wheels = vdir / "arms/C_post/wheels.json"
    if wheels.exists():  # WP1b: the packages of arm C-post
        for w in json.loads(wheels.read_text())["wheels"]:
            out["depends_on"][f"cpost_{w['package']}_wheel"] = {
                "path": str(Path(w["path"]).relative_to(repo)), "version": w["version"],
                "built_from": w["built_from"], "sha256": sha256(Path(w["path"]))}
    out = {
        **out,
    }
    (vdir / "data/manifest.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{sum(1 for e in entries if 'sha256' in e)} entries; mismatches: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
