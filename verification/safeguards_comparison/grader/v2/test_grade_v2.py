#!/usr/bin/env python3
"""Self-tests of grader v2 on hand-built answers (no arm involved).

For each of the five changes: one case it must change, and negative controls it must
not change. Every case is graded with v2 (all changes on) and with v2 with every change
off, which must equal v1.

Usage: python -I test_grade_v2.py <verification_dir>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade_v2", HERE / "grade_v2.py")
V2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V2)
ON, OFF = V2.ALL_CHANGES, frozenset()


def ans(**kw):
    a = {"status": "answered", "action": "proceed", "values": {}, "nearest_equivalent": False, "metadata": {},
         "texts": [], "exclusions": [], "evidence": {}}
    a.update(kw)
    return a


def cell(refs, task, a, changes):
    r = V2.grade_cell({"id": task}, refs[task], a, changes)
    return r["values"], r["metadata"], r["decision"]


def main() -> int:
    vdir = Path(sys.argv[1])
    refs = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]
    doc = {"model_datum": {"value": "LMSL", "source": "NOAA documentation (NOMADS)"},
           "units": {"value": "m", "source": "file"}}
    cases = []
    # change 1: a count in values does not trigger the bound; a real level beyond it still does
    c1 = ans(values={"min_m": -0.109, "n_values": 1813}, metadata=doc,
             exclusions=[{"what": "model_records", "count": 47, "names": [], "reason": "sentinel"}])
    cases += [("1: count field ignored", "R2", c1, ON, (None, None, "correct_proceed_with_caveat")),
              ("1: v1 behaviour kept when off", "R2", c1, OFF, (None, None, "false_proceed"))]
    c1n = ans(values={"min_m": -99998.6, "n_values": 1860}, metadata=doc)
    cases.append(("1 control: a no-data level still fails", "R2", c1n, ON, ("outside_tolerance", None, "false_proceed")))
    # change 2: refusal naming the cause needs no datum source; a proceed still does
    c2 = ans(status="refused", action="refuse", metadata={"model_datum": {"value": "undetermined", "source": None}},
             texts=["No comparison: the vertical datum could not be established; no datum label"])
    cases += [("2: refusal with cause", "S1", c2, ON, (None, "correct", "correct_refusal_or_flag")),
              ("2: v1 behaviour kept when off", "S1", c2, OFF, (None, "incomplete", "correct_refusal_or_flag"))]
    c2n = ans(values={"n": 480, "bias_m": -0.143, "rmse_m": 0.2456, "mae_m": 0.2086, "r": 0.9913},
              metadata={"model_datum": {"value": "LMSL", "source": None}, "obs_datum": {"value": "MSL", "source": "x"}},
              texts=["datum label absent; LMSL assumed from documentation"])
    cases.append(("2 control: a proceed still needs the datum source", "S1", c2n, ON, (None, "incomplete", None)))
    c2r = ans(status="refused", action="refuse", metadata={"model_datum": {"value": "undetermined", "source": None}},
              texts=["something failed"])
    cases.append(("2 control: refusal not naming the cause keeps v1 metadata", "S1", c2r, ON,
                  (None, "incomplete", "refusal_cause_not_named")))
    # change 3: per-column units read at the graded column
    c3 = ans(values={"max_wvht_m": 6.32}, metadata={"units": {"value": {"WVHT": "m", "TIDE": "ft"}, "source": "file"}},
             exclusions=[{"what": "records", "count": 35235, "names": [], "reason": "missing"}])
    cases += [("3: per-column units", "R7", c3, ON, ("within_tolerance", "correct", "correct_proceed_with_caveat")),
              ("3: v1 behaviour kept when off", "R7", c3, OFF, ("within_tolerance", "wrong", None))]
    c3n = ans(values={"max_wvht_m": 6.32}, metadata={"units": {"value": {"TIDE": "ft"}, "source": "file"}})
    cases.append(("3 control: graded column absent -> not stated", "R7", c3n, ON, (None, "incomplete", None)))
    c3w = ans(values={"max_wvht_m": 6.32}, metadata={"units": {"value": {"WVHT": "ft"}, "source": "file"}})
    cases.append(("3 control: wrong unit in the graded column", "R7", c3w, ON, (None, "wrong", None)))
    fails = 0
    for name, task, a, ch, want in cases:
        got = cell(refs, task, a, ch)
        ok = all(w is None or w == g for w, g in zip(want, got))
        fails += not ok
        print(("ok  " if ok else "FAIL"), name, got)
    # changes 4 and 5: the R7 adapter on a response shaped like ww3-mcp 0.1.3 and 0.1.2
    task = {"id": "R7", "kind": "buoy_max", "mcp_calls": {"T": [{"call_id": "x"}]}}
    new = {"summary": {"variable": "WVHT", "max": 6.32, "max_time": "2024-10-10 08:10", "missing": 35235},
           "missing_values": {"excluded_counts": {"WVHT": 35235, "TIDE": 52692}},
           "observations": [{"WVHT": 5.35, "timestamp": "2024-12-15 17:40"}, {"WVHT": None}]}
    old = {"observations": [{"WVHT": 99.0, "timestamp": "2024-01-01 00:00"}, {"WVHT": 3.2}]}
    tr = lambda o: {"valid": True, "session_id": "t", "calls": [{"call_id": "x", "content": [{"type": "text", "text": json.dumps(o)}]}]}
    checks = [
        ("5: stated maximum used", V2.adapt_v2(task, "T", tr(new), ON)["values"]["max_wvht_m"] == 6.32),
        ("5 off: max over rows (v1)", V2.adapt_v2(task, "T", tr(new), OFF)["values"]["max_wvht_m"] == 5.35),
        ("5 control: no summary -> max over rows", V2.adapt_v2(task, "T", tr(old), ON)["values"]["max_wvht_m"] == 99.0),
        ("4: counts read at summary.missing and excluded_counts[WVHT]",
         sorted(e["count"] for e in V2.adapt_v2(task, "T", tr(new), ON)["exclusions"]) == [35235, 35235]),
        ("4 off: none (v1)", V2.adapt_v2(task, "T", tr(new), OFF)["exclusions"] == []),
        ("4 control: other columns' counts not read",
         52692 not in [e["count"] for e in V2.adapt_v2(task, "T", tr(new), ON)["exclusions"]]),
    ]
    for name, ok in checks:
        fails += not ok
        print(("ok  " if ok else "FAIL"), name)
    n = len(cases) + len(checks)
    print(f"{n - fails}/{n} v2 self-tests pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
