#!/usr/bin/env python3
"""Grade with the amended references, using the frozen grading functions unchanged.

Imports grader/grade.py (freeze commit 5d84c13) and calls its grade_values,
grade_metadata and grade_decision on references/references.amended.json.
Writes results/grades_<arms>_amended.{json,csv,md}. The frozen grading
(grade.py on references.json) is kept alongside.

Usage: python -I grade_amended.py <verification_dir> [--arms A,B,C,D]
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade", HERE / "grade.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    arms = sys.argv[sys.argv.index("--arms") + 1].split(",") if "--arms" in sys.argv else ["A", "B", "C", "D"]
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    amended = json.loads((vdir / "references/references.amended.json").read_text())
    refs = amended["tasks"]
    rows = []
    for t in tasks:
        for arm in arms:
            p = vdir / "results/answers" / arm / f"{t['id']}.json"
            if not p.exists():
                rows.append({"task": t["id"], "class": t["class"], "arm": arm, "values": "missing_answer",
                             "metadata": "missing_answer", "metadata_strict": "missing_answer",
                             "decision": "missing_answer"})
                continue
            ans = json.loads(p.read_text())
            v, vd = G.grade_values(refs[t["id"]], ans)
            m, ms, md = G.grade_metadata(refs[t["id"]], ans)
            d, dd = G.grade_decision(refs[t["id"]], ans)
            rows.append({"task": t["id"], "class": t["class"], "arm": arm, "values": v, "values_detail": vd,
                         "metadata": m, "metadata_strict": ms, "metadata_detail": md, "decision": d,
                         "decision_evidence": (dd or "")[:400], "nearest_equivalent": bool(ans.get("nearest_equivalent")),
                         "returned_values": json.dumps(ans.get("values"), default=str)[:400]})
    out = vdir / "results"
    tag = "_".join(arms) + "_amended"
    (out / f"grades_{tag}.json").write_text(json.dumps(rows, indent=1) + "\n")
    cols = ["task", "class", "arm", "values", "metadata", "metadata_strict", "decision", "nearest_equivalent",
            "values_detail", "metadata_detail", "decision_evidence", "returned_values"]
    with open(out / f"grades_{tag}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    counts: dict = {}
    for r in rows:
        for axis in ("values", "metadata", "metadata_strict", "decision"):
            counts.setdefault(r["arm"], {}).setdefault(axis, {}).setdefault(r[axis], 0)
            counts[r["arm"]][axis][r[axis]] += 1
    (out / f"counts_{tag}.json").write_text(json.dumps(counts, indent=1) + "\n")
    lines = [f"# Grades, arms {', '.join(arms)}, amended references ({', '.join(a['id'] for a in amended['amendments']['applied'])})",
             "", "| Task | Class | Arm | Values | Metadata (strict) | Decision |", "|---|---|---|---|---|---|"]
    for r in rows:
        ne = " (nearest equivalent)" if r.get("nearest_equivalent") else ""
        lines.append(f"| {r['task']} | {r['class']} | {r['arm']} | {r['values']}{ne} | {r['metadata']} "
                     f"({r['metadata_strict']}) | {r['decision']} |")
    lines += ["", "## Counts per arm", ""]
    for arm, ax in counts.items():
        lines.append(f"**Arm {arm}**")
        for axis, c in ax.items():
            lines.append(f"- {axis}: " + ", ".join(f"{k} {n}" for k, n in sorted(c.items())))
        lines.append("")
    (out / f"grades_{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-12:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
