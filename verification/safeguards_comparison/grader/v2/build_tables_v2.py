#!/usr/bin/env python3
"""Grade arms A, B, C, C-post and D with grader v2 and write the v2 tables.

Shapes follow the v1 files (results/table_per_task.*, table_counts.*, decision_evidence.*),
extended to the five result sets:

  results/grades_v2.{json,csv}            every cell, v2 (all five changes)
  results/table_per_task_v2.{md,csv}      values / metadata / decision per task and arm;
                                          [v1: ...] where v1 differed; arm D's
                                          nearest-equivalent values unscored, as in v1
  results/table_counts_v2.{md,csv}        counts per arm and axis, v1 and v2 side by side
  results/decision_evidence_v2.{md,csv}   the text that triggered every v2 decision grade

Run fairness_check.py first; this script refuses to run if the check has not passed.

Usage: python -I build_tables_v2.py <verification_dir>
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade_v2", HERE / "grade_v2.py")
V2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V2)
ARMS = V2.ARMS
LABEL = {"A": "A basic Python", "B": "B validated Python", "C": "C 0.3.0 pre-fix",
         "Cpost": "C-post 0.3.0 post-fix", "D": "D 0.2.0"}
SHORT = {"within_tolerance": "within", "outside_tolerance": "OUTSIDE", "not_returned": "not returned",
         "not_applicable": "n/a", "not_supported": "not supported", "candidate_not_available": "cand. n/a",
         "correct": "correct", "incomplete": "incomplete", "wrong": "WRONG",
         "correct_proceed": "correct proceed", "correct_proceed_with_caveat": "correct proceed + caveat",
         "proceed_caveat_missing": "proceed, caveat MISSING", "correct_refusal_or_flag": "correct refusal",
         "refusal_cause_not_named": "refusal, cause not named", "false_proceed": "FALSE PROCEED",
         "false_refusal": "FALSE REFUSAL", "error": "ERROR"}
AXES = ("values", "metadata", "metadata_strict", "decision")
CATS = {"values": ["within_tolerance", "outside_tolerance", "not_returned", "not_applicable", "not_supported",
                   "candidate_not_available"],
        "metadata": ["correct", "incomplete", "wrong", "not_applicable", "candidate_not_available"],
        "metadata_strict": ["correct", "incomplete", "wrong", "not_applicable", "candidate_not_available"],
        "decision": ["correct_proceed", "correct_proceed_with_caveat", "correct_refusal_or_flag",
                     "proceed_caveat_missing", "refusal_cause_not_named", "false_proceed", "false_refusal",
                     "candidate_not_available", "error"]}
ABSENCE = {"proceed_caveat_missing", "false_refusal", "refusal_cause_not_named", "error"}


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    res = vdir / "results"
    fc = json.loads((res / "v2_fairness_check.json").read_text())
    if not fc.get("passed"):
        print("fairness check has not passed; v2 tables not written", file=sys.stderr)
        return 2
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    v1 = {(r["task"], r["arm"]): r for r in json.loads((res / "grades_A_B_C_D_Cpost_amended.json").read_text())}
    rows = V2.grade_all(vdir, V2.ALL_CHANGES)
    v2 = {(r["task"], r["arm"]): r for r in rows}
    diff = {(d["task"], d["arm"], d["axis"]): d for d in json.loads((res / "v1_vs_v2_diff.json").read_text())}

    out = [{k: v for k, v in r.items() if k != "_answer"} for r in rows]
    (res / "grades_v2.json").write_text(json.dumps(out, indent=1) + "\n")
    cols = ["task", "class", "arm", "values", "metadata", "metadata_strict", "decision", "nearest_equivalent",
            "values_detail", "metadata_detail", "decision_evidence", "returned_values"]
    with open(res / "grades_v2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    # per task
    md = ["# Per-task grades, grader v2 (all five changes; references with A1)", "",
          "Each cell: values / metadata / decision. [v1: ...] gives the v1 grade where it differs, with the change "
          "number from grader/v2/CHANGES.md. Arm D's nearest-equivalent values are shown for information and are "
          "not scored.", "",
          "| Task | Class | " + " | ".join(LABEL[a] for a in ARMS) + " | Arm D nearest-equivalent values (UNSCORED) |",
          "|---|---|" + "---|" * len(ARMS) + "---|"]
    pt = []
    for t in tasks:
        cells = []
        for a in ARMS:
            g = v2[(t["id"], a)]
            parts = []
            for ax in ("values", "metadata", "decision"):
                s = SHORT[g[ax]]
                d = diff.get((t["id"], a, ax))
                if d:
                    s += f" [v1: {SHORT[d['v1']]}; change {','.join(map(str, d['changes']))}]"
                parts.append(s)
            cells.append(" / ".join(parts))
            pt.append({"task": t["id"], "class": t["class"], "arm": a,
                       **{f"v2_{ax}": g[ax] for ax in AXES}, **{f"v1_{ax}": v1[(t["id"], a)][ax] for ax in AXES},
                       "changed_axes": ";".join(ax for ax in AXES if g[ax] != v1[(t["id"], a)][ax]),
                       "nearest_equivalent": g["nearest_equivalent"], "returned_values": g["returned_values"]})
        dans = v2[(t["id"], "D")]["_answer"]
        ne = ""
        if dans.get("nearest_equivalent"):
            v = dans.get("values") or {}
            ne = (f"n {v.get('n')}, bias {v.get('bias_m')}, RMSE {v.get('rmse_m')}, MAE {v.get('mae_m')}, r {v.get('r')}"
                  if v else "none (declined)")
        md.append(f"| {t['id']} | {t['class']} | " + " | ".join(cells) + f" | {ne} |")
    (res / "table_per_task_v2.md").write_text("\n".join(md) + "\n")
    with open(res / "table_per_task_v2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pt[0]))
        w.writeheader()
        w.writerows(pt)

    # counts, v1 and v2 side by side
    lines = ["# Counts per arm and axis, grader v1 and grader v2 side by side (18 rows per arm; no composite score)",
             "", "v1: grader/grade.py; v2: grader/v2/grade_v2.py; both on the references with amendment A1.", ""]
    crow = []
    for ax in AXES:
        lines += [f"## {ax}", "", "| Outcome | " + " | ".join(f"{LABEL[a]} v1 | v2" for a in ARMS) + " |",
                  "|---|" + "---:|---:|" * len(ARMS)]
        for c in CATS[ax]:
            n1 = [sum(1 for t in tasks if v1[(t["id"], a)][ax] == c) for a in ARMS]
            n2 = [sum(1 for t in tasks if v2[(t["id"], a)][ax] == c) for a in ARMS]
            if any(n1) or any(n2):
                lines.append(f"| {c} | " + " | ".join(f"{x} | {y}" for x, y in zip(n1, n2)) + " |")
                for a, x, y in zip(ARMS, n1, n2):
                    crow.append({"axis": ax, "outcome": c, "arm": a, "v1": x, "v2": y})
        lines.append("")
    lines += ["## Changed cells per arm (v1 -> v2)", "", "| Arm | values | metadata | metadata strict | decision | total |",
              "|---|---:|---:|---:|---:|---:|"]
    for a in ARMS:
        n = [sum(1 for t in tasks if v1[(t["id"], a)][ax] != v2[(t["id"], a)][ax]) for ax in AXES]
        lines.append(f"| {LABEL[a]} | " + " | ".join(map(str, n)) + f" | {sum(n)} |")
    (res / "table_counts_v2.md").write_text("\n".join(lines) + "\n")
    with open(res / "table_counts_v2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["axis", "outcome", "arm", "v1", "v2"])
        w.writeheader()
        w.writerows(crow)

    # decision evidence
    ev = ["# Decision-axis evidence, grader v2", "",
          "For every v2 decision grade: the text that triggered it (the matched passage, or the fixed predicate's "
          "finding). Where the grade was given because something was absent, the output's complete notes and "
          "reported exclusions follow. Cells whose grade changed from v1 give the v1 trigger too.", ""]
    erows = []
    for t in tasks:
        for a in ARMS:
            g, ans = v2[(t["id"], a)], v2[(t["id"], a)]["_answer"]
            e = {"task": t["id"], "arm": a, "decision": g["decision"], "trigger": g["decision_evidence"],
                 "output_notes": " || ".join(ans.get("texts") or []) if g["decision"] in ABSENCE else "",
                 "exclusions_reported": json.dumps(ans.get("exclusions"))[:600],
                 "v1_decision": v1[(t["id"], a)]["decision"], "v1_trigger": v1[(t["id"], a)]["decision_evidence"]}
            erows.append(e)
            ev.append(f"**{t['id']} / {LABEL[a]}: {g['decision']}**")
            ev.append(f"- trigger: `{g['decision_evidence']}`" if g["decision_evidence"]
                      else "- trigger: (no text: correct proceed with no caveat required)")
            if g["decision"] in ABSENCE:
                notes = ans.get("texts") or []
                ev.append("- output notes (complete): " + ("; ".join(f"`{x}`" for x in notes) if notes else "(none)"))
            if g["decision"] != e["v1_decision"]:
                ev.append(f"- v1: {e['v1_decision']}, trigger `{e['v1_trigger']}`")
            ev.append("")
    (res / "decision_evidence_v2.md").write_text("\n".join(ev) + "\n")
    with open(res / "decision_evidence_v2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(erows[0]))
        w.writeheader()
        w.writerows(erows)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
