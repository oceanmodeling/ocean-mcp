#!/usr/bin/env python3
"""Seed the base replay archive from inputs that earlier packages already archived.

Each listed file is *copied* (never moved) into the archive under its SHA-256,
and the copy's checksum is compared with the checksum recorded by the package
that archived it. The original files are not modified.

Seeded entries carry ``provenance.source = "seeded"`` with the origin file,
its recorded SHA-256, the source URL and the original retrieval time. Their
HTTP headers are synthetic (the original packages archived bodies only); the
servers read only the body and the status.

Usage: python -I seed_archive.py <repo_root> <archive_dir>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_launcher():
    import importlib.util

    spec = importlib.util.spec_from_file_location("ocean_replay_launcher", HERE / "ocean_replay_launcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    repo = Path(sys.argv[1]).resolve()
    archive_dir = Path(sys.argv[2]).resolve()
    L = load_launcher()
    arc = L.Archive(archive_dir, writable=True)

    boston = repo / ".claude/worktrees/stofs-v31-boston-v2/verification_stofs_v31_boston"
    bman = json.loads((boston / "data/manifest.json").read_text())["entries"]
    wp0 = repo / "verification_release_readiness/results/t3_evidence"

    seeds = []
    for name, ctype in (("stofs_2d_global", "application/x-netcdf"), ("stofs_3d_atlantic", "application/x-netcdf")):
        e = bman[name]
        seeds.append(
            dict(
                kind="exact",
                url=e["url"],
                file=boston / e["file"],
                sha=e["sha256"],
                retrieved_at=e["retrieved_at"],
                headers=[["content-type", ctype], ["last-modified", e["last_modified"]], ["etag", e["etag"]]],
                origin=f"Boston package data/manifest.json entry {name!r}",
            )
        )
    # CO-OPS Boston water level, MSL: the master for every 2026-10-30 Boston window.
    ce = next(v for k, v in bman.items() if k.startswith("coops_water_level"))
    from urllib.parse import urlencode

    url = ce["url"] + "?" + urlencode(ce["params"])
    seeds.append(
        dict(
            kind="coops_master",
            url=url,
            file=boston / ce["file"],
            sha=ce["sha256"],
            retrieved_at=ce["retrieved_at"],
            headers=[["content-type", "application/json;charset=UTF-8"]],
            origin="Boston package data/manifest.json CO-OPS water_level entry",
        )
    )
    # NDBC 41009 historical stdmet 2024, kept by WP0.
    fetch_txt = (wp0 / "ww3_ndbc_41009h2024_fetch.txt").read_text().split()
    retrieved = fetch_txt[0]
    ndbc_url = next(t for t in fetch_txt if t.startswith("url=")).split("=", 1)[1]
    seeds.append(
        dict(
            kind="exact",
            url=ndbc_url,
            file=wp0 / "downloads/41009h2024.txt",
            sha="f149d373877f4892f75092a969a0b12c27da7c8d54e0db9827a8fbcaef0bc648",
            retrieved_at=retrieved,
            headers=[["content-type", "text/plain; charset=UTF-8"]],
            origin="WP0 verification_release_readiness/results/t3_evidence/downloads (SHA256SUMS)",
        )
    )

    report = []
    for s in seeds:
        got = sha256(s["file"])
        if got != s["sha"]:
            print(f"CHECKSUM MISMATCH {s['file']}: {got} != {s['sha']}", file=sys.stderr)
            return 1
        key = L.request_key("GET", s["url"])
        if L.key_string(key) in arc.by_key:
            report.append({"url": s["url"], "status": "already seeded"})
            continue
        body = s["file"].read_bytes()
        entry = arc.add(
            key,
            s["url"],
            200,
            s["headers"],
            body,
            {
                "source": "seeded",
                "retrieved_at": s["retrieved_at"],
                "origin_file": str(s["file"].relative_to(repo)),
                "origin_sha256": s["sha"],
                "origin_record": s["origin"],
                "headers_synthetic": True,
            },
            kind=s["kind"],
        )
        if s["kind"] == "coops_master":
            arc.verified_master(entry)  # proves the byte-exact round trip now
        report.append({"url": s["url"], "entry": entry["id"], "sha256": got, "bytes": len(body)})
        # the copy must equal the origin, and the origin must be unchanged
        assert sha256(archive_dir / entry["response"]["body_file"]) == got == sha256(s["file"])
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
