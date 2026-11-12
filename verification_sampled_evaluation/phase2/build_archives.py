#!/usr/bin/env python3
"""Build the Phase 2 replay archives from the fetch log (DESIGN.md 3, 5.2).

  data/archive/models   S3 station files (exact; the two seeded WP1 files with their provenance)
  data/archive/coops    CO-OPS water_level masters (data, no-data, unsupported datum, other errors)
  data/archive/refonly  CO-OPS monthly means (read by the reference only; never offered to a tool)
  data/archive/meta     CO-OPS datums.json (Phase 0; already built)
  data/archive/templates the CO-OPS no-data template (Phase 0; already built)

Then checks: every data master round-trips byte-exactly through the WP1 serializer; every
error master is classified; nothing is listed twice. Writes run_log/archives_check.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "replay"))
import wp5_launcher  # noqa: E402,F401  (WP5 rules incl. amendment A6)
import ocean_replay_launcher as L  # noqa: E402

PY = sys.executable


def run(archive: str, tags: list[str]) -> None:
    cmd = [PY, "-I", str(PKG / "phase2/index_from_fetchlog.py"), str(PKG / archive)]
    for t in tags:
        cmd += ["--tag", t]
    print(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip())


def seed_models() -> None:
    root = PKG / "data/archive/models"
    idx = root / "index.json"
    doc = json.loads(idx.read_text())
    have = {L.key_string(e["key"]) for e in doc["entries"]}
    for it in json.loads((PKG / "phase2/fetch_plan.json").read_text())["items"]:
        if not it.get("seed_sha256"):
            continue
        key = L.request_key("GET", it["url"])
        if L.key_string(key) in have:
            continue
        src = PKG / "data/raw/models" / f"{it['seed_sha256']}.nc"
        body = src.read_bytes()
        assert hashlib.sha256(body).hexdigest() == it["seed_sha256"]
        dst = root / "bodies" / src.name
        if not dst.exists():
            os.link(src, dst)
        doc["entries"].append({"id": f"e{len(doc['entries']) + 1:05d}", "kind": "exact", "key": key, "url": it["url"],
                               "response": {"status": 200, "headers": [["content-type", "application/x-netcdf"]],
                                            "body_file": f"bodies/{src.name}", "body_sha256": it["seed_sha256"],
                                            "bytes": len(body)},
                               "provenance": {"source": "seeded from the WP1 archive (fetched 2026-11-06; S3 "
                                              "Last-Modified before that)"}})
    idx.write_text(json.dumps(doc, indent=1) + "\n")


def check() -> dict:
    out = {}
    for name in ("models", "coops", "refonly", "meta", "templates"):
        p = PKG / "data/archive" / name / "index.json"
        if not p.exists():
            out[name] = "missing"
            continue
        a = L.Archive(p.parent)
        kinds, bad_rt, dup = {}, [], 0
        keys = set()
        for e in a.doc["entries"]:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
            ks = L.key_string(e["key"])
            dup += ks in keys
            keys.add(ks)
            if e["kind"] == "coops_master":
                try:
                    a.verified_master(e)
                except L.ReplayMiss:
                    bad_rt.append(e["id"])
                a._verified_masters.clear()
        out[name] = {"entries": len(a.doc["entries"]), "kinds": kinds, "duplicate_keys": dup,
                     "masters_failing_round_trip": bad_rt}
    return out


def main() -> int:
    run("data/archive/models", ["s3_3d", "s3_2d", "s3_2d_noanomaly"])
    seed_models()
    run("data/archive/coops", ["coops_MSL", "coops_NAVD", "coops_MSL_unpublished_probe",
                               "coops_NAVD_unpublished_probe", "coops_MSL_unpublished_probe_escalated",
                               "coops_NAVD_unpublished_probe_escalated", "supp_coops_MSL", "supp_coops_NAVD",
                               "supp_exact_range"])
    run("data/archive/refonly", ["coops_monthly_mean", "supp_monthly_mean"])
    res = check()
    (PKG / "run_log/archives_check.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
    ok = all(isinstance(v, dict) and not v["masters_failing_round_trip"] and not v["duplicate_keys"] for v in res.values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
