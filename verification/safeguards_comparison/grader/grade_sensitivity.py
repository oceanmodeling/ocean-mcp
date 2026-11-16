#!/usr/bin/env python3
"""Amendment A2: sensitivity grading of S2 and S3 with a lenient decision rule.

Requested by the author on 2026-11-06, before arms C and D were run. Reason given:
the frozen 'refuse only' rule for S2 and S3 coincides with what stofs-mcp 0.3.0
implements, and the designer had read that source.

The frozen grading stays primary. This script reports, for S2 and S3 and every
arm, the frozen grade next to a lenient grade. The lenient rule ALSO accepts
proceeding when all three hold:

  1. the output states the cause explicitly: for S2 the datum conflict, for S3
     that the product version is undocumented (the frozen cause patterns
     CAUSE_RE['datum_conflict'] and CAUSE_RE['version_undocumented'] of grade.py);
  2. the datum used is attributed to documentation (the frozen DOC_RE on the
     stated datum source) or labelled as an assumption (ASSUMPTION_RE below, on
     the datum source or the output's texts);
  3. the comparison is internally consistent: the observation datum is the
     CO-OPS datum of the stated model datum (MSL for LMSL/MSL, NAVD for NAVD88).

A refusal is graded exactly as in the frozen rule. Metadata, lenient: the
model datum may also be LMSL/MSL or NAVD88 if condition 2 holds. Values are not
re-graded (they stay 'not_applicable', as frozen); returned values are listed.

The frozen grading functions of grade.py are used unchanged; the references are
references.amended.json (A1, which concerns S1 only).

Usage: python -I grade_sensitivity.py <verification_dir> [--arms A,B,C,D] [--selftest]
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade", HERE / "grade.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

ASSUMPTION_RE = re.compile(r"(assum|presum|taken from (the )?(NOAA )?documentation|per (the )?documentation)", re.I)
CAUSE = {"S2": "datum_conflict", "S3": "version_undocumented"}
COOPS_FAMILY = {"MSL": "MSL", "NAVD88": "NAVD88"}


def attributed(ans) -> str | None:
    md = (ans.get("metadata") or {}).get("model_datum") or {}
    src = str(md.get("source") or "")
    if src and G.DOC_RE.search(src):
        return f"datum source: {src[:160]}"
    blob = src + "\n" + G.all_text(ans)
    m = ASSUMPTION_RE.search(blob)
    if m:
        lo = max(0, m.start() - 80)
        return blob[lo:m.end() + 80].replace("\n", " ")
    return None


def lenient_decision(task, ref, ans):
    frozen, ev = G.grade_decision(ref, ans)
    if ans.get("action") != "proceed" or ans.get("status") in ("error", "not_supported", "candidate_not_available"):
        return frozen, ev
    text = G.all_text(ans)
    cause = G.match_rules(G.CAUSE_RE[CAUSE[task]], text)
    attr = attributed(ans)
    md = ans.get("metadata") or {}
    mfam = G.family((md.get("model_datum") or {}).get("value"))
    ofam = G.family((md.get("obs_datum") or {}).get("value"))
    consistent = mfam in COOPS_FAMILY and ofam == COOPS_FAMILY[mfam]
    if cause and attr and consistent:
        return "correct_proceed_with_caveat", f"cause: {cause} | attribution: {attr} | pairing {mfam}/{ofam}"
    missing = [n for n, ok in (("cause stated", cause), ("datum attributed to documentation or assumption", attr),
                               ("consistent pairing", consistent)) if not ok]
    return "false_proceed", f"lenient rule not met: missing {missing}; pairing {mfam}/{ofam}"


def lenient_metadata(ref, ans):
    frozen = G.grade_metadata(ref, ans)
    md = (ans.get("metadata") or {}).get("model_datum") or {}
    fam = G.family(md.get("value"))
    if fam in ("MSL", "NAVD88"):
        attr = attributed(ans)
        if attr:
            return "correct", f"{fam} with {attr[:120]}"
        return "wrong", f"{fam} not attributed to documentation or an assumption"
    return frozen[0], frozen[2]


def grade(vdir: Path, arms):
    refs = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]
    rows = []
    for task in ("S2", "S3"):
        for arm in arms:
            p = vdir / "results/answers" / arm / f"{task}.json"
            if not p.exists():
                continue
            ans = json.loads(p.read_text())
            fd, fev = G.grade_decision(refs[task], ans)
            fm, _, fmd = G.grade_metadata(refs[task], ans)
            ld, lev = lenient_decision(task, refs[task], ans)
            lm, lmd = lenient_metadata(refs[task], ans)
            rows.append({"task": task, "arm": arm, "action": ans.get("action"),
                         "decision_frozen": fd, "decision_lenient": ld,
                         "metadata_frozen": fm, "metadata_lenient": lm,
                         "evidence_frozen": (fev or "")[:400], "evidence_lenient": (lev or "")[:400],
                         "returned_values": json.dumps(ans.get("values"), default=str)[:300]})
    return rows


def selftest() -> int:
    vdir = HERE.parent
    refs = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]

    def a(**kw):
        x = {"status": "answered", "action": "proceed", "values": {}, "metadata": {}, "texts": [], "exclusions": []}
        x.update(kw)
        return x

    msl = {"model_datum": {"value": "LMSL", "source": "NOAA documentation (SCN 26-51) for v3.1"},
           "obs_datum": {"value": "MSL", "source": "x"}}
    cases = [
        ("S2", a(status="refused", action="refuse", texts=["conflicting datum labels msl / navd88"]),
         "correct_refusal_or_flag"),
        ("S2", a(metadata=msl, texts=["The labels conflict (msl vs navd88); LMSL taken from documentation"]),
         "correct_proceed_with_caveat"),
        ("S2", a(metadata=msl, texts=[]), "false_proceed"),
        ("S2", a(metadata={"model_datum": {"value": "LMSL", "source": "documentation"},
                           "obs_datum": {"value": "NAVD", "source": "x"}},
                 texts=["labels conflict"]), "false_proceed"),
        ("S3", a(metadata={"model_datum": {"value": "LMSL", "source": None}, "obs_datum": {"value": "MSL"}},
                 texts=["Product version V4.0.0 is not documented; LMSL is assumed"]), "correct_proceed_with_caveat"),
        ("S3", a(metadata={"model_datum": {"value": "LMSL", "source": "fixed pairing"}, "obs_datum": {"value": "MSL"}},
                 texts=[]), "false_proceed"),
    ]
    fails = 0
    for task, ans, want in cases:
        got = lenient_decision(task, refs[task], ans)[0]
        fails += got != want
        print(("ok  " if got == want else "FAIL"), task, got, "want", want)
    print(f"{len(cases) - fails}/{len(cases)} A2 self-tests pass")
    return 1 if fails else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    vdir = Path(sys.argv[1]).resolve()
    arms = sys.argv[sys.argv.index("--arms") + 1].split(",") if "--arms" in sys.argv else ["A", "B", "C", "D"]
    rows = grade(vdir, arms)
    out = vdir / "results"
    (out / "sensitivity_A2.json").write_text(json.dumps(rows, indent=1) + "\n")
    cols = list(rows[0].keys()) if rows else []
    with open(out / "sensitivity_A2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    lines = ["# Amendment A2: S2 and S3, frozen ('refuse only') vs lenient grading", "",
             "| Task | Arm | Action | Decision, frozen (primary) | Decision, lenient | Metadata, frozen | Metadata, lenient |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['task']} | {r['arm']} | {r['action']} | {r['decision_frozen']} | {r['decision_lenient']} | "
                     f"{r['metadata_frozen']} | {r['metadata_lenient']} |")
    (out / "sensitivity_A2.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
