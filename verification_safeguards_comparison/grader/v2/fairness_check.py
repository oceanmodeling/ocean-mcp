#!/usr/bin/env python3
"""Fairness check for grader v2. It must pass before v2 is used.

1. Baseline: the published v1 grades (grader/grade.py on references.amended.json,
   i.e. v1 with amendment A1) for arms A, B, C, C-post and D:
   results/grades_A_B_C_D_Cpost_amended.json. They are recomputed here with v1 from the
   archived answers and must match the file.
2. Faithfulness: v2 with every change disabled must reproduce every v1 grade on every
   axis, and its re-adapted MCP answers must equal the archived answers.
3. Difference and attribution: v2 with all five changes is compared with v1. For each
   cell and axis that differs, each change is enabled alone; the change(s) that alone
   produce the v2 grade are recorded. A difference no single change explains is then
   tested against every combination; if none explains it, the check FAILS and v2 must
   not be used. v2 is never adjusted to remove a difference.

Writes results/v2_fairness_check.json and results/v1_vs_v2_diff.{json,csv,md}.
Exit 0 only if the check passes.

Usage: python -I fairness_check.py <verification_dir>
"""

from __future__ import annotations

import csv
import importlib.util
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade_v2", HERE / "grade_v2.py")
V2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V2)
AXES = ("values", "metadata", "metadata_strict", "decision")
CHANGE_TITLE = {1: "value-bound predicate: water-level fields only",
                2: "no datum-source requirement for a refusal naming the cause",
                3: "per-column units: the graded column's unit",
                4: "excluded counts read under every key name used for R7",
                5: "R7 value: the maximum the response states (A3)"}


def key(r):
    return (r["task"], r["arm"])


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    refs = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]
    report = {"baseline": "v1 grader (grader/grade.py) with amendment A1 references, arms A, B, C, Cpost, D"}

    # 1. baseline from the published file, re-derived with v1 from the archived answers
    published = {key(r): r for r in json.loads((vdir / "results/grades_A_B_C_D_Cpost_amended.json").read_text())}
    v1 = {}
    for t in tasks:
        for arm in V2.ARMS:
            ans = json.loads((vdir / "results/answers" / arm / f"{t['id']}.json").read_text())
            vv = V2.G.grade_values(refs[t["id"]], ans)[0]
            m, ms, _ = V2.G.grade_metadata(refs[t["id"]], ans)
            d, dd = V2.G.grade_decision(refs[t["id"]], ans)
            v1[(t["id"], arm)] = {"values": vv, "metadata": m, "metadata_strict": ms, "decision": d,
                                  "decision_evidence": (dd or "")[:400]}
    mism = [(k, ax) for k in v1 for ax in AXES if v1[k][ax] != published[k][ax]]
    report["baseline_matches_published_v1_file"] = not mism
    if mism:
        report["baseline_mismatches"] = mism
        (vdir / "results/v2_fairness_check.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
        print("FAIL: v1 recomputation differs from the published v1 grades:", mism)
        return 2

    # 2. faithfulness
    off = {key(r): r for r in V2.grade_all(vdir, frozenset())}
    unfaithful = [(k, ax, v1[k][ax], off[k][ax]) for k in v1 for ax in AXES if v1[k][ax] != off[k][ax]]
    answer_diffs = []
    for k, r in off.items():
        archived = json.loads((vdir / "results/answers" / k[1] / f"{k[0]}.json").read_text())
        if json.loads(json.dumps(r["_answer"], default=str)) != archived:
            answer_diffs.append(k)
    report["v2_with_no_change_reproduces_v1"] = not unfaithful
    report["v2_with_no_change_reproduces_archived_answers"] = not answer_diffs
    if unfaithful or answer_diffs:
        report["unfaithful_cells"] = unfaithful
        report["answer_differences"] = answer_diffs
        (vdir / "results/v2_fairness_check.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
        print("FAIL: v2 with every change off does not reproduce v1:", unfaithful, answer_diffs)
        return 3

    # 3. differences and attribution
    full = {key(r): r for r in V2.grade_all(vdir, V2.ALL_CHANGES)}
    single = {c: {key(r): r for r in V2.grade_all(vdir, frozenset({c}))} for c in sorted(V2.ALL_CHANGES)}
    diffs, unexplained = [], []
    for k in sorted(v1, key=lambda x: ([t["id"] for t in tasks].index(x[0]), V2.ARMS.index(x[1]))):
        for ax in AXES:
            if v1[k][ax] == full[k][ax]:
                continue
            explained = [c for c in sorted(single) if single[c][k][ax] == full[k][ax]]
            if not explained:
                for n in range(2, 6):
                    for combo in itertools.combinations(sorted(V2.ALL_CHANGES), n):
                        r = {key(x): x for x in V2.grade_all(vdir, frozenset(combo))}[k]
                        if r[ax] == full[k][ax]:
                            explained = [list(combo)]
                            break
                    if explained:
                        break
            row = {"task": k[0], "arm": k[1], "axis": ax, "v1": v1[k][ax], "v2": full[k][ax],
                   "changes": explained, "v1_trigger": v1[k]["decision_evidence"] if ax == "decision" else "",
                   "v2_trigger": full[k]["decision_evidence"] if ax == "decision" else full[k].get("metadata_detail", "")
                   if ax.startswith("metadata") else full[k].get("values_detail", "")}
            diffs.append(row)
            if not explained:
                unexplained.append(row)
    report["changed_cells"] = len(diffs)
    report["changed_cells_per_arm"] = {a: sum(1 for d in diffs if d["arm"] == a) for a in V2.ARMS}
    report["unexplained"] = unexplained
    report["passed"] = not unexplained
    (vdir / "results/v2_fairness_check.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    (vdir / "results/v1_vs_v2_diff.json").write_text(json.dumps(diffs, indent=1, default=str) + "\n")
    with open(vdir / "results/v1_vs_v2_diff.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["arm", "task", "axis", "v1", "v2", "changes", "v1_trigger", "v2_trigger"])
        w.writeheader()
        for d in diffs:
            w.writerow({**d, "changes": ";".join(str(c) for c in d["changes"])})
    label = {"Cpost": "C-post"}
    lines = ["# Every cell whose grade differs between grader v1 and grader v2", "",
             "v1: grader/grade.py with amendment A1 references. v2: grader/v2/grade_v2.py, same references. "
             "'Change' is the CHANGES.md item that, enabled alone, produces the v2 grade.", "",
             "| Arm | Task | Axis | v1 | v2 | Change |", "|---|---|---|---|---|---|"]
    for d in sorted(diffs, key=lambda d: (V2.ARMS.index(d["arm"]), d["task"], AXES.index(d["axis"]))):
        ch = ", ".join(f"{c} ({CHANGE_TITLE[c]})" if isinstance(c, int) else "+".join(map(str, c)) for c in d["changes"])
        lines.append(f"| {label.get(d['arm'], d['arm'])} | {d['task']} | {d['axis']} | {d['v1']} | {d['v2']} | {ch or 'UNEXPLAINED'} |")
    lines += ["", "Changed cells per arm: " + ", ".join(f"{label.get(a, a)} {n}" for a, n in report["changed_cells_per_arm"].items()),
              "", f"Fairness check: {'PASSED' if report['passed'] else 'FAILED'} "
              f"(baseline reproduces the published v1 file; v2 with every change off reproduces v1 and the "
              f"archived answers; {len(diffs)} changed cells, {len(unexplained)} unexplained)."]
    (vdir / "results/v1_vs_v2_diff.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if report["passed"] else 4


if __name__ == "__main__":
    sys.exit(main())
