#!/usr/bin/env python3
"""Apply the recorded amendments to the frozen references, without touching them.

The frozen file references/references.json (freeze commit 5d84c13) is read,
the amendments listed in references/AMENDMENTS.md are applied, and the result
is written to references/references.amended.json, with the amendment log
embedded. Both versions are graded and both results are kept.

Usage: python -I amend_references.py <verification_dir>
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

AMENDMENTS = [
    {
        "id": "A1",
        "recorded": "2026-11-06, after arms A and B were graded and before arms C or D were run on any task",
        "task": "S1",
        "path": ["tasks", "S1", "values", "kind"],
        "frozen": "stats",
        "amended": "stats_if_proceeding",
        "evidence": (
            "references/build_references.py writes S1 values as "
            "{'kind': 'stats_if_proceeding', **compare_values(...)}; compare_values returns its own "
            "'kind': 'stats', which overrides the intended key, so the frozen JSON says 'stats'. "
            "The frozen design states the intended rule (DESIGN.md section 4: 'S1 | if proceeding: N2 values'; "
            "references.json S1 justification: refusal is an accepted outcome), and grade.py has the branch for "
            "'stats_if_proceeding' ('refused (an accepted outcome)' -> not_applicable). With the frozen value, a "
            "workflow that correctly refuses S1 is scored 'not_returned' on axis 1 instead of 'not_applicable'. "
            "Observed: arm B on S1."),
        "effect": "axis 1 only, task S1, workflows that refuse; no other task, axis or rule changes",
    },
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    frozen_path = vdir / "references/references.json"
    frozen = json.loads(frozen_path.read_text())
    doc = copy.deepcopy(frozen)
    for a in AMENDMENTS:
        node = doc
        for k in a["path"][:-1]:
            node = node[k]
        if node[a["path"][-1]] != a["frozen"]:
            raise SystemExit(f"{a['id']}: frozen value is {node[a['path'][-1]]!r}, expected {a['frozen']!r}")
        node[a["path"][-1]] = a["amended"]
    doc["amendments"] = {"frozen_file": "references/references.json", "frozen_sha256": sha256(frozen_path),
                         "applied": AMENDMENTS}
    (vdir / "references/references.amended.json").write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({"applied": [a["id"] for a in AMENDMENTS], "frozen_sha256": sha256(frozen_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
