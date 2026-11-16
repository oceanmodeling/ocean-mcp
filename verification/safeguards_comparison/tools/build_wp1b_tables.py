#!/usr/bin/env python3
"""WP1b tables: arm C (pre-fix) beside arm C-post (0.3.0 post-fix). No grading happens here.

Reads results/grades_A_B_C_D_Cpost.json (frozen grader, primary), the _amended (A1) version,
results/r7_A3.json (A3), results/sensitivity_A2_with_Cpost.json (A2) and the answers; writes:

  results/wp1b_C_vs_Cpost.{md,csv}       per task, both arms, three axes, with what changed
  results/wp1b_counts.{md,csv}            counts per arm and axis, arms A, B, C, C-post, D
  results/wp1b_decision_evidence_Cpost.md the text that triggered every C-post decision grade
  results/wp1b_disagreements.{md,csv}     C-post rows where a plain reading disagrees with the grader

Usage: python -I build_wp1b_tables.py <verification_dir>
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ARMS = ["A", "B", "C", "Cpost", "D"]
LABEL = {"A": "A basic Python", "B": "B validated Python", "C": "C 0.3.0 pre-fix",
         "Cpost": "C-post 0.3.0 post-fix", "D": "D 0.2.0"}
# changes the WP1b brief expects between C and C-post (task: axes)
EXPECTED = {"R6": {"decision", "metadata", "metadata_strict"}, "R7": {"values", "metadata", "metadata_strict", "decision"},
            "N4": {"metadata", "metadata_strict"}}
MAX_STATION_POINT = {"R1a", "R2", "R3", "R5", "R6"}  # tasks using the max, station or point tools
ABSENCE = {"proceed_caveat_missing", "false_refusal", "refusal_cause_not_named", "error"}

DISAGREEMENTS = [
    {"task": "R2", "arm": "Cpost", "axis": "decision", "grader": "false_proceed",
     "plain_reading": "correct_proceed_with_caveat",
     "why": ("Unchanged from arm C (WP1 REPORT section 1.3). The frozen 'value_beyond_bound' predicate counts the "
             "adapter's n_values (1,813) as a water level above 30 m. The tool returned min -0.109 m and reported "
             "excluded_model_records.sentinel = 47.")},
    {"task": "S1", "arm": "Cpost", "axis": "metadata", "grader": "incomplete", "plain_reading": "correct",
     "why": ("Unchanged from arm C. The tool declined: the datum 'could not be established'. The frozen S1 source "
             "rule asks for a source before it reads an undetermined value.")},
    {"task": "R7", "arm": "Cpost", "axis": "metadata", "grader": "wrong", "plain_reading": "correct",
     "why": ("ww3-mcp 0.1.3 reports units per column ({'WVHT': 'm', ...}, from the file's units line) and "
             "summary.units = 'm'. The frozen adapter copies the whole units map as the value and the grader "
             "compares it with 'm'.")},
    {"task": "R7", "arm": "Cpost", "axis": "decision", "grader": "proceed_caveat_missing",
     "plain_reading": "correct_proceed_with_caveat",
     "why": ("The response reports the exclusion: summary.missing = 35235 (WVHT), and missing_values gives NDBC's "
             "rule ('a field equal to its column's code is returned as null and counted here'), the codes "
             "(WVHT 99.00) and the documentation URL. The frozen adapter looks only for top-level keys named "
             "excluded, excluded_values, missing or excluded_records, so it finds no exclusion. A3 does not change "
             "this axis.")},
]


def load(p):
    return json.loads(Path(p).read_text())


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    res = vdir / "results"
    tasks = load(vdir / "tasks/tasks.json")["tasks"]
    prim = {(r["task"], r["arm"]): r for r in load(res / "grades_A_B_C_D_Cpost.json")}
    amd = {(r["task"], r["arm"]): r for r in load(res / "grades_A_B_C_D_Cpost_amended.json")}
    a3 = {r["arm"]: r for r in load(res / "r7_A3.json")}
    sens = {(r["task"], r["arm"]): r for r in load(res / "sensitivity_A2_with_Cpost.json")}
    ans = {(t["id"], a): load(res / "answers" / a / f"{t['id']}.json") for t in tasks for a in ARMS}

    # --- C vs C-post
    rows, md = [], ["# Arm C (0.3.0 pre-fix) and arm C-post (0.3.0 post-fix), primary grading", "",
                    "Each cell: values / metadata / decision. 'Changed' lists the axes that differ; 'expected' says "
                    "whether the WP1b brief expected that change.", "",
                    "| Task | C (pre-fix) | C-post (post-fix) | Changed | Expected |", "|---|---|---|---|---|"]
    for t in tasks:
        c, p = prim[(t["id"], "C")], prim[(t["id"], "Cpost")]
        changed = [ax for ax in ("values", "metadata", "metadata_strict", "decision") if c[ax] != p[ax]]
        exp = EXPECTED.get(t["id"], set()) | ({"metadata", "metadata_strict"} if t["id"] in MAX_STATION_POINT else set())
        expected = "n/a" if not changed else ("yes" if set(changed) <= exp else "NO: " + ", ".join(sorted(set(changed) - exp)))
        rows.append({"task": t["id"], **{f"C_{ax}": c[ax] for ax in ("values", "metadata", "metadata_strict", "decision")},
                     **{f"Cpost_{ax}": p[ax] for ax in ("values", "metadata", "metadata_strict", "decision")},
                     "changed": ";".join(changed), "expected": expected,
                     "Cpost_returned_values": p.get("returned_values", "")})
        md.append(f"| {t['id']} | {c['values']} / {c['metadata']} / {c['decision']} | {p['values']} / {p['metadata']} / "
                  f"{p['decision']} | {', '.join(changed) or '-'} | {expected} |")
    r7 = a3["Cpost"]
    md += ["", f"R7 under amendment A3 (maximum the response states): C-post {r7['amended_value_used']} m, "
           f"{r7['amended_values']} / {r7['amended_metadata']} / {r7['amended_decision']} "
           f"(frozen reading: {r7['frozen_value_used']} m, {r7['frozen_values']}). Arm C: candidate not available both ways."]
    (res / "wp1b_C_vs_Cpost.md").write_text("\n".join(md) + "\n")
    with open(res / "wp1b_C_vs_Cpost.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # --- counts
    cats = {
        "values": ["within_tolerance", "outside_tolerance", "not_returned", "not_applicable", "not_supported",
                   "candidate_not_available"],
        "metadata": ["correct", "incomplete", "wrong", "not_applicable", "candidate_not_available"],
        "metadata_strict": ["correct", "incomplete", "wrong", "not_applicable", "candidate_not_available"],
        "decision": ["correct_proceed", "correct_proceed_with_caveat", "correct_refusal_or_flag",
                     "proceed_caveat_missing", "refusal_cause_not_named", "false_proceed", "false_refusal",
                     "candidate_not_available"],
    }
    lines = ["# Counts per arm and axis, arms A, B, C, C-post, D (18 rows each; no composite score)", ""]
    crow = []
    for label, src in (("primary (frozen)", prim), ("with A1", amd)):
        for axis, cs in cats.items():
            lines += [f"## {axis}, {label}", "", "| Outcome | " + " | ".join(LABEL[a] for a in ARMS) + " |",
                      "|---|" + "---:|" * len(ARMS)]
            for c in cs:
                n = [sum(1 for t in tasks if src[(t["id"], a)][axis] == c) for a in ARMS]
                if any(n):
                    lines.append(f"| {c} | " + " | ".join(map(str, n)) + " |")
                    crow.append({"grading": label, "axis": axis, "outcome": c, **dict(zip(ARMS, n))})
            lines.append("")
    r7v = {a: (a3[a]["frozen_values"], a3[a]["amended_values"]) for a in a3}
    lines += ["## R7 values under A3 (frozen / amended)", "",
              "| Arm | frozen | amended |", "|---|---|---|"] + [f"| {LABEL.get(a, a)} | {f} | {m} |" for a, (f, m) in r7v.items()]
    (res / "wp1b_counts.md").write_text("\n".join(lines) + "\n")
    with open(res / "wp1b_counts.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["grading", "axis", "outcome"] + ARMS)
        w.writeheader()
        w.writerows(crow)

    # --- C-post decision evidence
    out = ["# Arm C-post: text that triggered every decision grade (primary grading)", "",
           "Where a grade was given because something was absent, the output's complete notes and reported "
           "exclusions follow.", ""]
    for t in tasks:
        g, a = prim[(t["id"], "Cpost")], ans[(t["id"], "Cpost")]
        out.append(f"**{t['id']} / C-post: {g['decision']}**")
        ev = g.get("decision_evidence") or ""
        out.append(f"- trigger: `{ev}`" if ev else "- trigger: (no text: correct proceed with no caveat required)")
        if g["decision"] in ABSENCE:
            notes = a.get("texts") or []
            out.append("- output notes (complete): " + ("; ".join(f"`{n}`" for n in notes) if notes else "(none)"))
            out.append(f"- exclusions recorded by the frozen adapter: `{json.dumps(a.get('exclusions'))}`")
        if t["id"] == "R7":
            out.append(f"- A3 value trigger, frozen: `{a3['Cpost']['frozen_value_trigger']}`")
            out.append(f"- A3 value trigger, amended: `{a3['Cpost']['amended_value_trigger']}`")
        if (t["id"], "Cpost") in sens:
            s = sens[(t["id"], "Cpost")]
            out.append(f"- A2 lenient: {s['decision_lenient']} (`{s['evidence_lenient'][:200]}`)")
        out.append("")
    (res / "wp1b_decision_evidence_Cpost.md").write_text("\n".join(out) + "\n")

    # --- disagreements
    dl = ["# Arm C-post: rows where a plain reading disagrees with the grader (grader not changed)", "",
          "| Task | Arm | Axis | Grader | Plain reading | Why |", "|---|---|---|---|---|---|"]
    for d in DISAGREEMENTS:
        got = prim[(d["task"], d["arm"])][d["axis"]]
        if got != d["grader"]:
            raise SystemExit(f"stale disagreement entry: {d['task']} {d['axis']} is {got}")
        dl.append(f"| {d['task']} | C-post | {d['axis']} | {d['grader']} | {d['plain_reading']} | {d['why']} |")
    (res / "wp1b_disagreements.md").write_text("\n".join(dl) + "\n")
    with open(res / "wp1b_disagreements.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(DISAGREEMENTS[0]))
        w.writeheader()
        w.writerows(DISAGREEMENTS)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
