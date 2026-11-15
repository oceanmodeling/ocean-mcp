#!/usr/bin/env python3
"""Write the Phase 0 session specs for a given environments directory.

The committed specs in phase0/ record the absolute paths of the original run.
This regenerates the same sessions (same calls, same archives) for a repeat.

Usage: python -I make_phase0_specs.py <verification_dir> <envs_dir> <out_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    vdir, envs, out = (Path(a).resolve() for a in sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=True)
    base = str(vdir / "data/archive/base")
    for src in sorted((vdir / "phase0").glob("spec_*.json")):
        spec = json.loads(src.read_text())
        env_name = Path(spec["server"]["python"]).parents[1].name
        spec["server"]["python"] = str(envs / env_name / "bin/python")
        spec["server"]["archives"] = [base]
        (out / src.name).write_text(json.dumps(spec, indent=1) + "\n")
    print(f"phase0 specs written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
