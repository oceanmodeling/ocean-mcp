#!/usr/bin/env python3
"""Check that every archived body is present and matches its SHA-256 (no network).

Usage: python -I verify_archive.py <verification_dir>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    missing, bad, ok = [], [], 0
    for idx in sorted((vdir / "data/archive").rglob("index.json")):
        for e in json.loads(idx.read_text())["entries"]:
            p = idx.parent / e["response"]["body_file"]
            if not p.exists():
                missing.append(str(p.relative_to(vdir)))
                continue
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != e["response"]["body_sha256"]:
                bad.append(str(p.relative_to(vdir)))
            else:
                ok += 1
    print(f"archive bodies: {ok} verified, {len(missing)} missing, {len(bad)} mismatched")
    for m in missing:
        print("  missing", m)
    for b in bad:
        print("  MISMATCH", b)
    return 1 if (missing or bad) else 0


if __name__ == "__main__":
    sys.exit(main())
