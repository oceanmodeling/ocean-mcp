#!/usr/bin/env python3
"""Generate manuscript Table 4 from the archived WP1/WP1b/WP1c grades.

Read-only. Standard library only. Nothing is written unless --json is given.

Inputs, relative to ROOT (the WP1 directory `verification_safeguards_comparison/`
on branch `eval/safeguards-comparison`):

  results/grades_A_B_C_D_Cpost_amended.json  grader v1 (frozen grader/grade.py) on the
                                             A1-amended references
  results/grades_v2.json                     grader v2 (grader/v2/grade_v2.py) on the same
                                             A1-amended references
  results/grades_A_B_C_D_Cpost.json          grader v1 on the strictly frozen references
                                             (no A1); supplementary only
  results/grades_A_B_C_D_amended.json        WP1 v1 file without C-post; cross-check only
  results/table_counts_v2.csv                published v1/v2 counts; cross-check only
  tasks/tasks.json                           frozen task statements and inputs
  run_log/mcp_arms_C_D.json                  per-session package versions (arms C and D)
  run_log/sessions/D/R7/{spec,transcript}.json, http_log.jsonl
                                             the arm D R7 session

Counting rules (as specified for Table 4):

  values    graded = within_tolerance + outside_tolerance + not_returned
            ("not returned" is graded and is not correct);
            not graded = not_applicable, not_supported, candidate_not_available
  metadata  graded = correct + incomplete + wrong;
            not graded = not_applicable, not_supported, candidate_not_available
            (the primary metadata axis; the strict axis is printed separately)
  decisions correct = correct_proceed + correct_proceed_with_caveat
                      + correct_refusal_or_flag;
            graded = every row except candidate_not_available

Workflows: A; B; C at the freeze, (a) as recorded and (b) with R7 taken from
arm D's ww3-mcp 0.1.2 session; C after fixes (arm "Cpost"); D.

Usage:
  python3 -I make_table4.py [ROOT] [--json OUT.json]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path(
    "/mnt/d/ocean-mcp/.claude/worktrees/safeguards-comparison/verification_safeguards_comparison"
)

V1_FILE = "results/grades_A_B_C_D_Cpost_amended.json"
V2_FILE = "results/grades_v2.json"
V1_FROZEN_FILE = "results/grades_A_B_C_D_Cpost.json"
V1_WP1_FILE = "results/grades_A_B_C_D_amended.json"
COUNTS_V2_CSV = "results/table_counts_v2.csv"

TASK_ORDER = [
    "N1", "N2", "N3", "N4",
    "R1a", "R1b", "R2", "R3", "R4a", "R4b", "R5", "R6", "R7",
    "S1", "S2", "S3", "S4", "S5",
]
ARMS = ["A", "B", "C", "Cpost", "D"]
ARM_LABEL = {
    "A": "A (basic Python)",
    "B": "B (validated Python)",
    "C": "C at the freeze (0.3.0 pre-fix)",
    "Cpost": "C after fixes (0.3.0 post-fix)",
    "D": "D (stofs-mcp 0.2.0 / released packages)",
}

VALUES_GRADED = {"within_tolerance", "outside_tolerance", "not_returned"}
VALUES_NOT_GRADED = {"not_applicable", "not_supported", "candidate_not_available"}
META_GRADED = {"correct", "incomplete", "wrong"}
META_NOT_GRADED = {"not_applicable", "not_supported", "candidate_not_available"}
DEC_CORRECT = {"correct_proceed", "correct_proceed_with_caveat", "correct_refusal_or_flag"}
DEC_ALL = DEC_CORRECT | {"proceed_caveat_missing", "false_proceed", "false_refusal"}

ABBR = {
    "within_tolerance": "within",
    "outside_tolerance": "OUTSIDE",
    "not_returned": "not returned",
    "not_applicable": "n/a",
    "not_supported": "not supported",
    "candidate_not_available": "cand. n/a",
    "correct": "correct",
    "incomplete": "incomplete",
    "wrong": "WRONG",
    "correct_proceed": "proceed",
    "correct_proceed_with_caveat": "proceed+caveat",
    "correct_refusal_or_flag": "refusal",
    "proceed_caveat_missing": "caveat MISSING",
    "false_proceed": "FALSE PROCEED",
    "false_refusal": "FALSE REFUSAL",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_grades(path: Path) -> dict[tuple[str, str], dict]:
    rows = json.loads(path.read_text())
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["arm"], r["task"])
        if key in out:
            raise SystemExit(f"duplicate grade row {key} in {path}")
        out[key] = r
    for arm in ARMS:
        for task in TASK_ORDER:
            if (arm, task) not in out:
                raise SystemExit(f"missing grade row {(arm, task)} in {path}")
    return out


def workflow_rows(grades: dict, workflow: str) -> list[dict]:
    """The 18 rows of one workflow; 'C_b' is C with R7 taken from arm D."""
    if workflow == "C_b":
        rows = []
        for t in TASK_ORDER:
            src = ("D", t) if t == "R7" else ("C", t)
            rows.append(grades[src])
        return rows
    arm = "C" if workflow == "C_a" else workflow
    return [grades[(arm, t)] for t in TASK_ORDER]


def check_known(rows: list[dict]) -> None:
    for r in rows:
        if r["values"] not in VALUES_GRADED | VALUES_NOT_GRADED:
            raise SystemExit(f"unknown values outcome {r['values']!r} ({r['arm']} {r['task']})")
        for ax in ("metadata", "metadata_strict"):
            if r[ax] not in META_GRADED | META_NOT_GRADED:
                raise SystemExit(f"unknown {ax} outcome {r[ax]!r} ({r['arm']} {r['task']})")
        if r["decision"] not in DEC_ALL | {"candidate_not_available"}:
            raise SystemExit(f"unknown decision {r['decision']!r} ({r['arm']} {r['task']})")


def summarise(rows: list[dict]) -> dict:
    check_known(rows)
    v = Counter(r["values"] for r in rows)
    m = Counter(r["metadata"] for r in rows)
    ms = Counter(r["metadata_strict"] for r in rows)
    d = Counter(r["decision"] for r in rows)
    return {
        "rows": len(rows),
        "values_within": v["within_tolerance"],
        "values_graded": sum(v[k] for k in VALUES_GRADED),
        "values_not_returned": v["not_returned"],
        "values_not_graded": {k: v[k] for k in sorted(VALUES_NOT_GRADED) if v[k]},
        "metadata_correct": m["correct"],
        "metadata_graded": sum(m[k] for k in META_GRADED),
        "metadata_not_graded": {k: m[k] for k in sorted(META_NOT_GRADED) if m[k]},
        "metadata_strict_correct": ms["correct"],
        "metadata_strict_graded": sum(ms[k] for k in META_GRADED),
        "decisions_correct": sum(d[k] for k in DEC_CORRECT),
        "decisions_graded": sum(d[k] for k in DEC_ALL),
        "caveat_missing": d["proceed_caveat_missing"],
        "false_proceed": d["false_proceed"],
        "false_refusal": d["false_refusal"],
        "candidate_not_available_rows": d["candidate_not_available"],
        "raw": {"values": dict(v), "metadata": dict(m), "metadata_strict": dict(ms), "decision": dict(d)},
    }


WORKFLOWS = [
    ("A", "A (basic Python)"),
    ("B", "B (validated Python)"),
    ("C_a", "C at the freeze, (a) as recorded (R7 candidate not available)"),
    ("C_b", "C at the freeze, (b) R7 from arm D's ww3-mcp 0.1.2 session"),
    ("Cpost", "C after fixes (arm C-post)"),
    ("D", "D (stofs-mcp 0.2.0; ww3-mcp 0.1.2 for R7)"),
]


def r7_provenance(root: Path) -> dict:
    """Confirm from the archive that arm D's R7 session ran ww3-mcp 0.1.2 on the frozen NDBC file."""
    tasks = json.loads((root / "tasks/tasks.json").read_text())["tasks"]
    r7 = next(t for t in tasks if t["id"] == "R7")
    frozen_inputs = [(i["entry"], i["sha256"], i["url"]) for i in r7["inputs"]]
    arms_log = json.loads((root / "run_log/mcp_arms_C_D.json").read_text())
    sess = {(s["arm"], s["task"]): s for s in arms_log["sessions"]}
    d_r7 = sess[("D", "R7")]
    c_r7 = sess[("C", "R7")]
    spec = json.loads((root / "run_log/sessions/D/R7/spec.json").read_text())
    transcript = json.loads((root / "run_log/sessions/D/R7/transcript.json").read_text())
    served = [
        json.loads(line)
        for line in (root / "run_log/sessions/D/R7/http_log.jsonl").read_text().splitlines()
        if line.strip()
    ]
    served = [e for e in served if e.get("event") == "served"]
    served_bodies = [(e["entry_id"], e["body_sha256"], e["url"]) for e in served]
    frozen_sha = {s for _, s, _ in frozen_inputs}
    served_sha = {s for _, s, _ in served_bodies}
    out = {
        "task_R7_frozen_inputs": frozen_inputs,
        "task_R7_note": r7.get("note"),
        "arm_D_R7_session_packages_run_log": d_r7.get("packages"),
        "arm_D_R7_session_packages_transcript": transcript.get("packages"),
        "arm_D_R7_server_python": spec["server"]["python"],
        "arm_D_R7_call": spec["calls"],
        "arm_D_R7_bodies_served": served_bodies,
        "arm_D_R7_replay_counts": d_r7.get("http"),
        "arm_C_R7_status": c_r7.get("status"),
        "calls_identical_C_and_D": r7["mcp_calls"]["C"][0]["arguments"]
        == r7["mcp_calls"]["D"][0]["arguments"]
        and r7["mcp_calls"]["C"][0]["tool"] == r7["mcp_calls"]["D"][0]["tool"],
        "ww3_mcp_version_is_0_1_2": (d_r7.get("packages") or {}).get("ww3-mcp") == "0.1.2"
        and (transcript.get("packages") or {}).get("ww3-mcp") == "0.1.2",
        "served_body_is_frozen_input": bool(served_sha) and served_sha <= frozen_sha,
        "replay_clean": d_r7.get("valid") is True
        and (d_r7.get("http") or {}).get("replay_misses") == 0
        and (d_r7.get("http") or {}).get("network_blocked") == 0,
    }
    return out


def cross_checks(root: Path, v1: dict, v2: dict, counts: dict) -> list[str]:
    msgs = []
    # 1. arms A-D in the WP1b v1 file equal the WP1 v1 file (adding C-post changed nothing else)
    wp1 = load_grades_partial(root / V1_WP1_FILE)
    diff = [
        k
        for k, r in wp1.items()
        for ax in ("values", "metadata", "metadata_strict", "decision")
        if v1[k][ax] != r[ax]
    ]
    msgs.append(
        f"v1 arms A-D in {V1_FILE} equal {V1_WP1_FILE}: {'yes' if not diff else 'NO ' + str(diff)}"
    )
    # 2. our counts equal the published table_counts_v2.csv for every arm/axis/outcome
    pub = {}
    with open(root / COUNTS_V2_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            pub[(row["axis"], row["outcome"], row["arm"])] = (int(row["v1"]), int(row["v2"]))
    bad = []
    for (axis, outcome, arm), (p1, p2) in pub.items():
        c1 = counts["v1"][arm]["raw"].get(axis, {}).get(outcome, 0)
        c2 = counts["v2"][arm]["raw"].get(axis, {}).get(outcome, 0)
        if (c1, c2) != (p1, p2):
            bad.append((axis, outcome, arm, (p1, p2), (c1, c2)))
    msgs.append(
        f"counts reproduce {COUNTS_V2_CSV} ({len(pub)} cells): {'yes' if not bad else 'NO ' + str(bad)}"
    )
    return msgs


def load_grades_partial(path: Path) -> dict[tuple[str, str], dict]:
    return {(r["arm"], r["task"]): r for r in json.loads(path.read_text())}


def fmt_frac(a: int, b: int) -> str:
    return f"{a} of {b}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=str(DEFAULT_ROOT))
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()
    root = Path(args.root)

    files = [V1_FILE, V2_FILE, V1_FROZEN_FILE, V1_WP1_FILE, COUNTS_V2_CSV, "tasks/tasks.json",
             "run_log/mcp_arms_C_D.json", "run_log/sessions/D/R7/spec.json",
             "run_log/sessions/D/R7/http_log.jsonl", "run_log/sessions/D/R7/transcript.json"]
    v1 = load_grades(root / V1_FILE)
    v2 = load_grades(root / V2_FILE)
    v1f = load_grades(root / V1_FROZEN_FILE)

    graders = {"v1": v1, "v2": v2}
    table = {g: {wf: summarise(workflow_rows(grades, wf)) for wf, _ in WORKFLOWS} for g, grades in graders.items()}
    table_frozen_v1 = {wf: summarise(workflow_rows(v1f, wf)) for wf, _ in WORKFLOWS}
    per_arm_counts = {g: {arm: summarise(workflow_rows(grades, arm if arm != "C" else "C_a"))
                          for arm in ARMS} for g, grades in graders.items()}

    p = print
    p("# Table 4, generated by make_table4.py")
    p()
    p(f"Root: `{root}`")
    p()
    p("Input files (SHA-256):")
    p()
    for f in files:
        p(f"- `{f}` `{sha256(root / f)}`")
    p()
    p("Grader v1 = frozen `grader/grade.py` on the A1-amended references "
      f"(`{V1_FILE}`); grader v2 = `grader/v2/grade_v2.py` on the same references (`{V2_FILE}`).")
    p()
    p("Values graded = within + outside + not returned (not returned is graded and not correct); "
      "not applicable, not supported and candidate-not-available rows are not graded. "
      "Metadata graded = correct + incomplete + wrong. Correct decisions = correct proceed + "
      "correct proceed with caveat + correct refusal; candidate-not-available rows have no decision.")
    p()

    p("## Table 4 (v1 · v2)")
    p()
    p("| Workflow | Values within tolerance / graded | Metadata correct / graded | Correct decisions / graded | Caveat missing | False proceed | False refusal |")
    p("|---|---|---|---|---|---|---|")
    for wf, label in WORKFLOWS:
        a, b = table["v1"][wf], table["v2"][wf]
        p(f"| {label} "
          f"| {fmt_frac(a['values_within'], a['values_graded'])} · {fmt_frac(b['values_within'], b['values_graded'])} "
          f"| {fmt_frac(a['metadata_correct'], a['metadata_graded'])} · {fmt_frac(b['metadata_correct'], b['metadata_graded'])} "
          f"| {fmt_frac(a['decisions_correct'], a['decisions_graded'])} · {fmt_frac(b['decisions_correct'], b['decisions_graded'])} "
          f"| {a['caveat_missing']} · {b['caveat_missing']} "
          f"| {a['false_proceed']} · {b['false_proceed']} "
          f"| {a['false_refusal']} · {b['false_refusal']} |")
    p()
    p("Rows not graded on values, per workflow (v1; identical under v2 unless stated):")
    p()
    for wf, label in WORKFLOWS:
        a, b = table["v1"][wf], table["v2"][wf]
        extra = "" if a["values_not_graded"] == b["values_not_graded"] else f"; v2 {b['values_not_graded']}"
        nr = f", not returned {a['values_not_returned']}" if a["values_not_returned"] else ""
        p(f"- {label}: {a['values_not_graded']}{nr}; metadata not graded {a['metadata_not_graded']}{extra}")
    p()

    p("## Supplement: strict metadata axis (v1 · v2)")
    p()
    p("| Workflow | Strict metadata correct / graded |")
    p("|---|---|")
    for wf, label in WORKFLOWS:
        a, b = table["v1"][wf], table["v2"][wf]
        p(f"| {label} | {fmt_frac(a['metadata_strict_correct'], a['metadata_strict_graded'])} · "
          f"{fmt_frac(b['metadata_strict_correct'], b['metadata_strict_graded'])} |")
    p()

    p("## Supplement: grader v1 on the strictly frozen references (no amendment A1)")
    p()
    p("Grader v2 is defined only on the A1 references, so this has no v2 counterpart.")
    p()
    p("| Workflow | Values | Metadata | Correct decisions | Caveat missing | False proceed | False refusal |")
    p("|---|---|---|---|---|---|---|")
    for wf, label in WORKFLOWS:
        a = table_frozen_v1[wf]
        p(f"| {label} | {fmt_frac(a['values_within'], a['values_graded'])} "
          f"| {fmt_frac(a['metadata_correct'], a['metadata_graded'])} "
          f"| {fmt_frac(a['decisions_correct'], a['decisions_graded'])} "
          f"| {a['caveat_missing']} | {a['false_proceed']} | {a['false_refusal']} |")
    p()

    p("## R7 for 'C at the freeze (b)': arm D's session")
    p()
    prov = r7_provenance(root)
    p(f"- Arm C R7 status (run_log/mcp_arms_C_D.json): `{prov['arm_C_R7_status']}`")
    p(f"- Arm D R7 packages (run_log/mcp_arms_C_D.json): `{json.dumps(prov['arm_D_R7_session_packages_run_log'])}`")
    p(f"- Arm D R7 packages (run_log/sessions/D/R7/transcript.json `packages`): `{json.dumps(prov['arm_D_R7_session_packages_transcript'])}`")
    p(f"- Arm D R7 server interpreter (spec.json `server.python`): `{prov['arm_D_R7_server_python']}`")
    p(f"- Arm D R7 call: `{json.dumps(prov['arm_D_R7_call'][0])}`")
    p(f"- Frozen R7 input (tasks/tasks.json `inputs`): `{prov['task_R7_frozen_inputs']}`")
    p(f"- Bodies served to arm D R7 (http_log.jsonl `served`): `{prov['arm_D_R7_bodies_served']}`")
    p(f"- Replay counts: `{json.dumps(prov['arm_D_R7_replay_counts'])}`")
    p(f"- Checks: ww3-mcp 0.1.2 = {prov['ww3_mcp_version_is_0_1_2']}; served body is the frozen input = "
      f"{prov['served_body_is_frozen_input']}; replay clean = {prov['replay_clean']}; "
      f"arm C and arm D R7 calls identical = {prov['calls_identical_C_and_D']}")
    for g, grades in graders.items():
        r = grades[("D", "R7")]
        p(f"- {g} grades of arm D R7: values `{r['values']}` ({r['values_detail']}); metadata "
          f"`{r['metadata']}` ({r['metadata_detail']}); strict `{r['metadata_strict']}`; decision "
          f"`{r['decision']}` ({r['decision_evidence']})")
    p()

    p("## Per-row grades, all five workflows (values / metadata / decision)")
    p()
    hdr = "| Task | " + " | ".join(f"{a} v1 | {a} v2" for a in ARMS) + " |"
    p(hdr)
    p("|---|" + "---|" * (2 * len(ARMS)))
    per_row = []
    for t in TASK_ORDER:
        cells = []
        rec = {"task": t}
        for a in ARMS:
            for g, grades in graders.items():
                r = grades[(a, t)]
                cell = " / ".join(ABBR[r[ax]] for ax in ("values", "metadata", "decision"))
                cells.append(cell)
                rec[f"{a}_{g}"] = {ax: r[ax] for ax in ("values", "metadata", "metadata_strict", "decision")}
        per_row.append(rec)
        p(f"| {t} | " + " | ".join(cells) + " |")
    p()

    p("## Strict-metadata cells that differ between v1 and v2")
    p()
    strict_diff = []
    for a in ARMS:
        for t in TASK_ORDER:
            x, y = v1[(a, t)], v2[(a, t)]
            if x["metadata_strict"] != y["metadata_strict"]:
                strict_diff.append({"arm": a, "task": t, "v1": x["metadata_strict"], "v2": y["metadata_strict"],
                                    "v1_detail": x["metadata_detail"], "v2_detail": y["metadata_detail"]})
    p("| # | Workflow | Task | v1 (before) | v2 (after) | v1 detail |")
    p("|---|---|---|---|---|---|")
    for i, d in enumerate(strict_diff, 1):
        p(f"| {i} | {ARM_LABEL[d['arm']]} | {d['task']} | {d['v1']} | {d['v2']} | {d['v1_detail'] or '(none)'} |")
    by_arm = Counter(d["arm"] for d in strict_diff)
    p()
    p(f"Total {len(strict_diff)}: " + ", ".join(f"{ARM_LABEL[a]} {by_arm[a]}" for a in ARMS))
    p()

    all_diff = []
    for a in ARMS:
        for t in TASK_ORDER:
            for ax in ("values", "metadata", "metadata_strict", "decision"):
                if v1[(a, t)][ax] != v2[(a, t)][ax]:
                    all_diff.append({"arm": a, "task": t, "axis": ax, "v1": v1[(a, t)][ax], "v2": v2[(a, t)][ax]})
    p(f"All v1/v2 differing cells (any axis): {len(all_diff)} "
      f"({', '.join(f'{a} {sum(1 for d in all_diff if d['arm'] == a)}' for a in ARMS)})")
    p()

    p("## Cross-checks")
    p()
    counts = {"v1": per_arm_counts["v1"], "v2": per_arm_counts["v2"]}
    for m in cross_checks(root, v1, v2, counts):
        p(f"- {m}")

    if args.json_out:
        out = {
            "root": str(root),
            "inputs_sha256": {f: sha256(root / f) for f in files},
            "rules": {
                "values_graded": sorted(VALUES_GRADED),
                "values_not_graded": sorted(VALUES_NOT_GRADED),
                "metadata_graded": sorted(META_GRADED),
                "decisions_correct": sorted(DEC_CORRECT),
            },
            "table4": {g: {wf: {k: v for k, v in s.items() if k != "raw"} for wf, s in t.items()}
                       for g, t in table.items()},
            "table4_v1_frozen_references": {wf: {k: v for k, v in s.items() if k != "raw"}
                                            for wf, s in table_frozen_v1.items()},
            "r7_provenance": prov,
            "arm_D_R7_grades": {g: {k: grades[("D", "R7")][k] for k in
                                    ("values", "values_detail", "metadata", "metadata_strict",
                                     "metadata_detail", "decision", "decision_evidence", "returned_values")}
                                for g, grades in graders.items()},
            "per_row": per_row,
            "strict_metadata_v1_v2_diff": strict_diff,
            "all_v1_v2_diff": all_diff,
        }
        Path(args.json_out).write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
