#!/usr/bin/env python3
"""Build the report tables from the gradings (no grading happens here).

Reads results/grades_A_B_C_D.json (frozen references, primary),
results/grades_A_B_C_D_amended.json (A1), results/sensitivity_A2.json (A2) and the
answers, and writes:

  results/table_per_task.{md,csv}      three axes per task and arm, primary grading;
                                       arm D nearest-equivalent values in a separate,
                                       unscored column
  results/table_counts.{md,csv}        counts per arm and axis (primary and A1)
  results/decision_evidence.{md,csv}   for every decision grade, the exact text that
                                       triggered it; for grades given because something
                                       was absent, the output's complete notes
  results/arm_D_nearest_equivalent_values.{md,csv}
  results/disagreements.{md,csv}       rows where a plain reading of the output
                                       disagrees with the grader (the grader is not changed)

Usage: python -I build_report_tables.py <verification_dir>
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ARMS = ["A", "B", "C", "D"]
V_AB = {"within_tolerance": "within", "outside_tolerance": "OUTSIDE", "not_returned": "not returned",
        "not_applicable": "n/a", "not_supported": "not supported", "candidate_not_available": "cand. n/a",
        "missing_answer": "MISSING"}
M_AB = {"correct": "correct", "incomplete": "incomplete", "wrong": "WRONG", "not_applicable": "n/a",
        "not_supported": "not supported", "candidate_not_available": "cand. n/a", "missing_answer": "MISSING"}
D_AB = {"correct_proceed": "correct proceed", "correct_proceed_with_caveat": "correct proceed + caveat",
        "proceed_caveat_missing": "proceed, caveat MISSING", "correct_refusal_or_flag": "correct refusal",
        "refusal_cause_not_named": "refusal, cause not named", "false_proceed": "FALSE PROCEED",
        "false_refusal": "FALSE REFUSAL", "not_supported": "not supported", "candidate_not_available": "cand. n/a",
        "error": "ERROR", "missing_answer": "MISSING"}
ABSENCE = {"proceed_caveat_missing", "false_refusal", "refusal_cause_not_named", "error"}

# Rows where a plain reading of the output disagrees with the frozen grader. Each entry
# records the grader's value, the plain reading, and why. The script checks that the
# grader's value is still what the entry says.
DISAGREEMENTS = [
    {"task": "R2", "arm": "C", "axis": "decision", "grader": "false_proceed",
     "plain_reading": "correct_proceed_with_caveat",
     "why": ("The frozen predicate 'value_beyond_bound' tests every numeric field of the answer's values. The frozen "
             "station adapter adds n_values (the number of values the tool returned, 1,813) to values, and 1,813 > 30, "
             "so the predicate fires. The water level the tool returned is min -0.109 m (within tolerance), and the "
             "tool reports excluded_model_records sentinel = 47, the reference count. Read plainly, stofs-mcp 0.3.0 "
             "excluded the 47 shifted dry values, reported them and gave the right minimum.")},
    {"task": "S1", "arm": "C", "axis": "metadata", "grader": "incomplete",
     "plain_reading": "correct",
     "why": ("The tool declined, stating that the vertical datum 'could not be established'. The frozen adapter maps "
             "this to model_datum = 'undetermined' with no source (a refusal text has no source field), and the S1 "
             "source rule asks for a source before it looks at the value. For an undetermined datum no source is "
             "meaningful; read plainly, the metadata statement is correct.")},
]
# Grades that are correct but deserve a note in the report (not disagreements)
NOTES = [
    {"task": "R6", "arm": "D", "note": "stofs-mcp 0.2.0 declined ('No STOFS station found within 50.0 km'). The cause "
     "is the reversed coordinates it does not detect; the Boston record is in the file. Graded false refusal: the "
     "question was answerable."},
    {"task": "N1", "arm": "D", "note": "stofs-mcp 0.2.0's JSON response carries no datum note; its markdown response "
     "(not requested) says 'small systematic offsets (1-5 cm) are expected'. The grade reflects the JSON requested."},
    {"task": "R4a", "arm": "D", "note": "stofs-mcp 0.2.0 hard-codes NAVD88/NAVD for STOFS-3D. That is correct for this "
     "v2.1.18 cycle and wrong for the v3.1 cycles (R4b, N2, S5)."},
    {"task": "R7", "arm": "D", "note": "ww3-mcp 0.1.2 returns 5,270 of 52,692 rows (every 10th); 3,520 of them show WVHT 99.0. "
     "The true maximum (6.32 m) is not in the subsample; the largest valid value returned is 5.6 m, so even a "
     "missing-value fix alone would not give the reference value."},
    {"task": "S4", "arm": "D", "note": "stofs-mcp 0.2.0 returned bias, RMSE, MAE and r as NaN (and its JSON contains "
     "NaN tokens, which strict JSON parsers reject)."},
]


def load(p):
    return json.loads(Path(p).read_text())


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    res = vdir / "results"
    tasks = load(vdir / "tasks/tasks.json")["tasks"]
    prim = {(r["task"], r["arm"]): r for r in load(res / "grades_A_B_C_D.json")}
    amd = {(r["task"], r["arm"]): r for r in load(res / "grades_A_B_C_D_amended.json")}
    sens = {(r["task"], r["arm"]): r for r in load(res / "sensitivity_A2.json")}
    answers = {(t["id"], a): load(res / "answers" / a / f"{t['id']}.json") for t in tasks for a in ARMS}

    # --- per-task table
    rows_csv, md = [], ["| Task | Class | Arm A | Arm B | Arm C | Arm D | Arm D nearest-equivalent values (UNSCORED) |",
                        "|---|---|---|---|---|---|---|"]
    for t in tasks:
        cells = []
        for a in ARMS:
            g = prim[(t["id"], a)]
            v = V_AB[g["values"]]
            if amd[(t["id"], a)]["values"] != g["values"]:
                v += f" [A1: {V_AB[amd[(t['id'], a)]['values']]}]"
            cells.append(f"{v} / {M_AB[g['metadata']]} / {D_AB[g['decision']]}")
            rows_csv.append({"task": t["id"], "class": t["class"], "arm": a, "values": g["values"],
                             "values_A1": amd[(t["id"], a)]["values"], "metadata": g["metadata"],
                             "metadata_strict": g["metadata_strict"], "decision": g["decision"],
                             "decision_A2_lenient": sens.get((t["id"], a), {}).get("decision_lenient", ""),
                             "nearest_equivalent": g.get("nearest_equivalent", False),
                             "returned_values": g.get("returned_values", "")})
        d_ans = answers[(t["id"], "D")]
        ne = ""
        if d_ans.get("nearest_equivalent"):
            v = d_ans.get("values") or {}
            ne = (f"n {v.get('n')}, bias {v.get('bias_m')}, RMSE {v.get('rmse_m')}, MAE {v.get('mae_m')}, "
                  f"r {v.get('r')}" if v else "none (declined)")
        md.append(f"| {t['id']} | {t['class']} | " + " | ".join(cells) + f" | {ne} |")
    md = ["# Per-task grades (primary: frozen references and grader)", "",
          "Each cell: values / metadata / decision. [A1: …] shows the amended value where amendment A1 changes it. "
          "Arm D's nearest-equivalent values are shown for information and are not scored.", ""] + md
    (res / "table_per_task.md").write_text("\n".join(md) + "\n")
    with open(res / "table_per_task.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_csv[0].keys()))
        w.writeheader()
        w.writerows(rows_csv)

    # --- counts
    axes = {"values": list(V_AB), "metadata": list(M_AB), "decision": list(D_AB)}
    lines = ["# Counts per arm and axis (18 rows per arm; no composite score)", ""]
    crow = []
    for label, src in (("primary (frozen)", prim), ("with amendment A1", amd)):
        for axis, cats in axes.items():
            present = [c for c in cats if any(src[(t["id"], a)][axis] == c for t in tasks for a in ARMS)]
            lines += [f"## {axis}, {label}", "", "| Outcome | A | B | C | D |", "|---|---|---|---|---|"]
            for c in present:
                n = [sum(1 for t in tasks if src[(t["id"], a)][axis] == c) for a in ARMS]
                lines.append(f"| {c} | " + " | ".join(map(str, n)) + " |")
                crow.append({"grading": label, "axis": axis, "outcome": c, **dict(zip(ARMS, n))})
            lines.append("")
    lines += ["## Separately: false proceeds, false refusals, not supported (primary)", "",
              "| | A | B | C | D |", "|---|---|---|---|---|"]
    for c, axis in (("false_proceed", "decision"), ("false_refusal", "decision"), ("not_supported", "values")):
        n = [sum(1 for t in tasks if prim[(t["id"], a)][axis] == c) for a in ARMS]
        lines.append(f"| {c} ({axis}) | " + " | ".join(map(str, n)) + " |")
    n = [sum(1 for t in tasks if prim[(t["id"], a)]["nearest_equivalent"]) for a in ARMS]
    lines.append("| nearest-equivalent calls (values unscored) | " + " | ".join(map(str, n)) + " |")
    (res / "table_counts.md").write_text("\n".join(lines) + "\n")
    with open(res / "table_counts.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["grading", "axis", "outcome"] + ARMS)
        w.writeheader()
        w.writerows(crow)

    # --- decision evidence
    ev_rows = []
    out = ["# Decision-axis evidence (primary grading)", "",
           "For every grade, the text that triggered it: the matched passage of the output, or the fixed "
           "predicate's finding. Where a grade was given because something was absent (a caveat, a cause, an "
           "answer), the output's complete notes follow, so the absence can be checked.", ""]
    for t in tasks:
        for a in ARMS:
            g = prim[(t["id"], a)]
            ans = answers[(t["id"], a)]
            notes = list(ans.get("texts") or [])
            excl = ans.get("exclusions") or []
            ev = g.get("decision_evidence", "")
            rec = {"task": t["id"], "arm": a, "decision": g["decision"], "trigger": ev,
                   "output_notes": " || ".join(notes) if g["decision"] in ABSENCE else "",
                   "exclusions_reported": json.dumps(excl)[:600]}
            if (t["id"], a) in sens:
                rec["A2_lenient"] = sens[(t["id"], a)]["decision_lenient"]
                rec["A2_trigger"] = sens[(t["id"], a)]["evidence_lenient"]
            ev_rows.append(rec)
            out.append(f"**{t['id']} / arm {a}: {g['decision']}**")
            out.append(f"- trigger: `{ev}`" if ev else "- trigger: (no text: correct proceed with no caveat required)")
            if g["decision"] in ABSENCE:
                out.append("- output notes (complete): " + ("; ".join(f"`{n}`" for n in notes) if notes else "(none)"))
            if excl and g["decision"] in ABSENCE:
                out.append(f"- exclusions reported: `{json.dumps(excl)[:300]}`")
            if (t["id"], a) in sens:
                out.append(f"- A2 lenient: {sens[(t['id'], a)]['decision_lenient']} (`{sens[(t['id'], a)]['evidence_lenient'][:200]}`)")
            out.append("")
    (res / "decision_evidence.md").write_text("\n".join(out) + "\n")
    with open(res / "decision_evidence.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["task", "arm", "decision", "trigger", "output_notes",
                                           "exclusions_reported", "A2_lenient", "A2_trigger"])
        w.writeheader()
        w.writerows(ev_rows)

    # --- arm D nearest-equivalent values
    ne_rows = []
    for t in tasks:
        a = answers[(t["id"], "D")]
        if a.get("nearest_equivalent"):
            ne_rows.append({"task": t["id"], "action": a.get("action"), **{k: a.get("values", {}).get(k) for k in
                            ("n", "bias_m", "rmse_m", "mae_m", "r")},
                            "window": json.dumps(a.get("evidence", {}).get("window")),
                            "call_note": a.get("nearest_equivalent_note")})
    with open(res / "arm_D_nearest_equivalent_values.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ne_rows[0].keys()))
        w.writeheader()
        w.writerows(ne_rows)
    ml = ["# Arm D (stofs-mcp 0.2.0): values from nearest-equivalent calls — UNSCORED", "",
          "0.2.0 has no lead-time window; these windows start at the file start (cycle - 6 h for 2D, cycle - 24 h for 3D) "
          "and end at lead 48.1 h. They answer a different question than the task and are never scored.", "",
          "| Task | Action | n | bias (m) | RMSE (m) | MAE (m) | r | window |", "|---|---|---|---|---|---|---|---|"]
    for r in ne_rows:
        ml.append(f"| {r['task']} | {r['action']} | {r['n']} | {r['bias_m']} | {r['rmse_m']} | {r['mae_m']} | {r['r']} | "
                  f"{r['window']} |")
    (res / "arm_D_nearest_equivalent_values.md").write_text("\n".join(ml) + "\n")

    # --- disagreements
    dl = ["# Rows where a plain reading of the output disagrees with the grader", "",
          "The grader is not changed. Each row gives the grader's value (primary grading), the plain reading and why.", "",
          "| Task | Arm | Axis | Grader | Plain reading | Why |", "|---|---|---|---|---|---|"]
    for d in DISAGREEMENTS:
        got = prim[(d["task"], d["arm"])][d["axis"]]
        if got != d["grader"]:
            raise SystemExit(f"disagreement entry stale: {d['task']} {d['arm']} {d['axis']} is {got}")
        dl.append(f"| {d['task']} | {d['arm']} | {d['axis']} | {d['grader']} | {d['plain_reading']} | {d['why']} |")
    dl += ["", "## Notes on grades that are right but need context", ""]
    dl += [f"- **{n['task']} / arm {n['arm']}**: {n['note']}" for n in NOTES]
    (res / "disagreements.md").write_text("\n".join(dl) + "\n")
    with open(res / "disagreements.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["task", "arm", "axis", "grader", "plain_reading", "why"])
        w.writeheader()
        w.writerows(DISAGREEMENTS)
    print("tables written:", sorted(p.name for p in res.glob("table_*")) + ["decision_evidence.*",
          "arm_D_nearest_equivalent_values.*", "disagreements.*"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
