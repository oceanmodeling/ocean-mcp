#!/usr/bin/env python3
"""Amendment A3: grade R7 two ways, frozen first.

Requested by the author on 2026-11-08, before arm C-post was run.

frozen   The frozen adapter (grader/adapters.py adapt_buoy_max) takes the maximum
         WVHT over the rows the response returns. That was adequate for ww3-mcp
         0.1.2, whose returned rows were a stride through the whole year.
amended  The maximum the response reports as its answer to the task: a stated
         whole-response maximum (a numeric `summary.max`, with `summary.max_time`)
         when the response has one; otherwise the frozen reading (maximum over the
         returned rows), because the response states no other answer. For arms A
         and B the answer is the value the script reports, so both readings agree.

Everything else is the frozen grading: grade_values, grade_metadata and
grade_decision of grader/grade.py on references.amended.json (A1 concerns S1
only); exclusions and notes come from the frozen adapter unchanged. The grader
and adapters are not modified.

Writes results/r7_A3.{json,csv,md}, with the triggering text of each grade.

Usage: python -I grade_r7_a3.py <verification_dir> [--arms A,B,C,D,Cpost] [--selftest]
"""

from __future__ import annotations

import copy
import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load("grade")
AD = _load("adapters")


def stated_maximum(transcript: dict):
    """The maximum a ww3 history response states as its answer, if it states one."""
    if not transcript or not transcript.get("calls"):
        return None
    obj = AD._parse(AD._call_text(transcript["calls"][0]))
    if isinstance(obj, dict) and isinstance(obj.get("summary"), dict):
        s = obj["summary"]
        if isinstance(s.get("max"), (int, float)):
            return {"max_wvht_m": s["max"], "time": s.get("max_time"),
                    "trigger": "summary: " + json.dumps({k: s.get(k) for k in s if k in
                                                         ("max", "max_time", "valid", "missing", "covers", "units")})}
    return None


def frozen_trigger(ans: dict) -> str:
    v = ans.get("values") or {}
    ev = ans.get("evidence") or {}
    if "max_wvht_m" not in v:
        return "no value"
    if ev.get("returned_records") is not None:
        return (f"maximum WVHT over the {ev['returned_records']} returned rows = {v['max_wvht_m']} "
                f"(row time {v.get('time')})")
    return f"value the script reports: {v['max_wvht_m']} at {v.get('time')}"


def grade_both(vdir: Path, arms):
    refs = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]
    ref = refs["R7"]
    rows = []
    for arm in arms:
        p = vdir / "results/answers" / arm / "R7.json"
        if not p.exists():
            continue
        ans = json.loads(p.read_text())
        tr_path = vdir / "run_log/sessions" / arm / "R7/transcript.json"
        transcript = json.loads(tr_path.read_text()) if tr_path.exists() else None
        out = {"arm": arm, "status": ans.get("status")}
        for label, a in (("frozen", ans), ("amended", None)):
            if label == "amended":
                a = copy.deepcopy(ans)
                stated = stated_maximum(transcript) if arm not in ("A", "B") else None
                if stated:
                    a["values"] = {"max_wvht_m": stated["max_wvht_m"], "time": stated["time"]}
                    trig = stated["trigger"]
                else:
                    trig = frozen_trigger(ans) + " (no stated whole-response maximum; frozen reading used)"
            else:
                trig = frozen_trigger(ans)
            v, vd = G.grade_values(ref, a)
            m, ms, md = G.grade_metadata(ref, a)
            d, dd = G.grade_decision(ref, a)
            out.update({f"{label}_value_used": (a.get("values") or {}).get("max_wvht_m"),
                        f"{label}_time": (a.get("values") or {}).get("time"),
                        f"{label}_values": v, f"{label}_values_detail": vd,
                        f"{label}_metadata": m, f"{label}_decision": d,
                        f"{label}_value_trigger": trig, f"{label}_decision_trigger": (dd or "")[:300]})
        rows.append(out)
    return rows


def selftest() -> int:
    vdir = HERE.parent
    ref = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]["R7"]
    fake_tr = {"calls": [{"content": [{"type": "text", "text": json.dumps(
        {"summary": {"max": 6.32, "max_time": "2024-10-10 08:10", "valid": 17457, "missing": 35235},
         "observations": [{"WVHT": 5.35}, {"WVHT": None}]})}]}]}
    st = stated_maximum(fake_tr)
    ok1 = st and st["max_wvht_m"] == 6.32
    old_tr = {"calls": [{"content": [{"type": "text", "text": json.dumps({"observations": [{"WVHT": 99.0}]})}]}]}
    ok2 = stated_maximum(old_tr) is None
    a = {"status": "answered", "action": "proceed", "values": {"max_wvht_m": 6.32}, "metadata": {}, "texts": [],
         "exclusions": [], "nearest_equivalent": False}
    ok3 = G.grade_values(ref, a)[0] == "within_tolerance"
    for name, ok in (("stated summary max is read", ok1), ("no summary -> frozen reading", ok2),
                     ("6.32 within tolerance", ok3)):
        print("ok  " if ok else "FAIL", name)
    n = sum(bool(x) for x in (ok1, ok2, ok3))
    print(f"{n}/3 A3 self-tests pass")
    return 0 if n == 3 else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    vdir = Path(sys.argv[1]).resolve()
    arms = sys.argv[sys.argv.index("--arms") + 1].split(",") if "--arms" in sys.argv else ["A", "B", "C", "D", "Cpost"]
    rows = grade_both(vdir, arms)
    res = vdir / "results"
    (res / "r7_A3.json").write_text(json.dumps(rows, indent=1) + "\n")
    with open(res / "r7_A3.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    lines = ["# R7 graded two ways (amendment A3): frozen first", "",
             "| Arm | Frozen: value used | Frozen: values / metadata / decision | Amended: value used | "
             "Amended: values / metadata / decision |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['arm']} | {r['frozen_value_used']} | {r['frozen_values']} / {r['frozen_metadata']} / "
                     f"{r['frozen_decision']} | {r['amended_value_used']} | {r['amended_values']} / "
                     f"{r['amended_metadata']} / {r['amended_decision']} |")
    lines += ["", "## Triggering text", ""]
    for r in rows:
        lines += [f"**Arm {r['arm']}**",
                  f"- frozen value: `{r['frozen_value_trigger']}`",
                  f"- frozen decision: `{r['frozen_decision_trigger']}`",
                  f"- amended value: `{r['amended_value_trigger']}`",
                  f"- amended decision: `{r['amended_decision_trigger']}`", ""]
    (res / "r7_A3.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
