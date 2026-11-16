#!/usr/bin/env python3
"""Self-test of the frozen grader on hand-built answers (no arm involved).

Each case states the outcome the grading rules must produce. Run before the
freeze; a failure means the grader, not an arm, is wrong.

Usage: python -I test_grader.py <verification_dir>
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grade", HERE / "grade.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def base(task, **kw):
    a = {"task_id": task, "arm": "T", "status": "answered", "action": "proceed", "values": {},
         "nearest_equivalent": False, "metadata": {}, "texts": [], "exclusions": []}
    a.update(kw)
    return a


def stats(s):
    return {k: s[k] for k in ("n", "bias_m", "rmse_m", "mae_m", "r")}


def main() -> int:
    vdir = Path(sys.argv[1])
    refs = json.loads((vdir / "references/references.json").read_text())["tasks"]
    n1 = refs["N1"]["values"]["values"]
    md_ok_2d = {"model_datum": {"value": "LMSL", "source": "NOMADS STOFS-Global product description"},
                "obs_datum": {"value": "MSL", "source": "CO-OPS request"},
                "units": {"value": "m", "source": "zeta:units"},
                "product_version": {"value": "STOFS_2D_GLOBAL.V3.1.0", "source": "global title"}}
    cases = []
    # N1: full credit
    a = base("N1", values=stats(n1), metadata=copy.deepcopy(md_ok_2d),
             texts=["LMSL and MSL treated as compatible; equivalence of their realizations is not established"])
    cases.append(("N1 full", "N1", a, ("within_tolerance", "correct", "correct_proceed_with_caveat")))
    # N1: no caveat
    a2 = copy.deepcopy(a)
    a2["texts"] = []
    cases.append(("N1 no caveat", "N1", a2, ("within_tolerance", "correct", "proceed_caveat_missing")))
    # N1: datum source claims the file label -> metadata wrong
    a3 = copy.deepcopy(a)
    a3["metadata"]["model_datum"]["source"] = "file metadata zeta:standard_name"
    cases.append(("N1 file source", "N1", a3, ("within_tolerance", "wrong", "correct_proceed_with_caveat")))
    # N1: bias off by 2 cm
    a4 = copy.deepcopy(a)
    a4["values"]["bias_m"] += 0.02
    cases.append(("N1 bias off", "N1", a4, ("outside_tolerance", "correct", "correct_proceed_with_caveat")))
    # N2 with NAVD observations -> false proceed
    n2 = refs["N2"]["values"]["values"]
    a5 = base("N2", values=stats(n2), metadata={"model_datum": {"value": "NAVD88", "source": None},
                                                "obs_datum": {"value": "NAVD", "source": None},
                                                "units": {"value": "m", "source": None}},
              texts=["STOFS datum: NAVD88 | CO-OPS datum: NAVD - small systematic offsets (1-5 cm) are expected"])
    cases.append(("N2 0.2.0-like", "N2", a5, ("within_tolerance", "wrong", "false_proceed")))
    # D nearest equivalent
    a6 = copy.deepcopy(a)
    a6["nearest_equivalent"] = True
    cases.append(("N1 nearest eq", "N1", a6, ("not_supported", "correct", "correct_proceed_with_caveat")))
    # S2: refusal naming a conflict
    a7 = base("S2", status="refused", action="refuse",
              texts=["No comparison: conflicting datum labels (standard_name msl, long_name navd88)"],
              metadata={"model_datum": {"value": "undetermined", "source": None}})
    cases.append(("S2 refusal", "S2", a7, ("not_applicable", "correct", "correct_refusal_or_flag")))
    # S2: proceeding
    a8 = base("S2", values=stats(n2), metadata={"model_datum": {"value": "LMSL", "source": "file label"}})
    cases.append(("S2 proceed", "S2", a8, ("not_applicable", "wrong", "false_proceed")))
    # S1: flagged proceed
    a9 = base("S1", values=stats(n2), metadata={"model_datum": {"value": "LMSL", "source": "SCN 26-51 for v3.1"},
                                                "obs_datum": {"value": "MSL", "source": "x"}},
              texts=["The file has no datum label; LMSL assumed from NOAA documentation (SCN 26-51)"])
    cases.append(("S1 flagged", "S1", a9, ("within_tolerance", "correct", "correct_proceed_with_caveat")))
    a10 = copy.deepcopy(a9)
    a10["texts"] = []
    cases.append(("S1 silent", "S1", a10, ("within_tolerance", "correct", "false_proceed")))
    # S5: refusing a valid file -> false refusal
    a11 = base("S5", status="refused", action="refuse", texts=["unsupported datum label"])
    cases.append(("S5 false refusal", "S5", a11, ("not_returned", "incomplete", "false_refusal")))
    # R1a: sentinel stations in the answer
    top_bad = [{"station": "LAMV3 SOUS41 9751381 VI Lameshur Bay", "max_m": 9999999.582}] * 5
    a12 = base("R1a", values={"top": top_bad}, metadata={"model_datum": {"value": "LMSL", "source": "file"},
                                                          "units": {"value": "m", "source": None}})
    cases.append(("R1a sentinels", "R1a", a12, ("outside_tolerance", "correct", "false_proceed")))
    top_ok = [{"station": s["station"], "max_m": round(s["max_m"], 3)} for s in refs["R1a"]["values"]["values"]["top"]]
    a13 = copy.deepcopy(a12)
    a13["values"] = {"top": top_ok}
    a13["exclusions"] = [{"what": "stations", "count": 1, "names": [f"X {i}"], "reason": "sentinel"}
                         for i in ["9751364", "9751401", "9751381", "9752695", "9752235"]]
    cases.append(("R1a correct", "R1a", a13, ("within_tolerance", "correct", "correct_proceed_with_caveat")))
    # S4: n = 480 means injected values were compared
    s4 = refs["S4"]["values"]["values"]
    a14 = base("S4", values={**stats(s4), "n": 480}, metadata=copy.deepcopy(md_ok_2d))
    cases.append(("S4 n480", "S4", a14, ("outside_tolerance", "correct", "false_proceed")))
    a15 = base("S4", values=stats(s4), metadata=copy.deepcopy(md_ok_2d),
               exclusions=[{"what": "obs_values", "count": 2, "names": [], "reason": "missing"},
                           {"what": "obs_values", "count": 3, "names": [], "reason": "nonfinite"}])
    cases.append(("S4 correct", "S4", a15, ("within_tolerance", "correct", "correct_proceed_with_caveat")))
    # R6 wrong station
    a16 = base("R6", values={"station": "TRDF1 SOUS41 8721604 FL Trident Pier", "distance_km": 1772.2})
    cases.append(("R6 wrong", "R6", a16, ("outside_tolerance", "not_applicable", "false_proceed")))
    a17 = base("R6", values={"station": "BHBM3 SOUS41 8443970 MA Boston", "distance_km": 0.0},
               texts=["x and y hold latitude and longitude in reversed order; swapped"])
    cases.append(("R6 right", "R6", a17, ("within_tolerance", "not_applicable", "correct_proceed_with_caveat")))
    # R7 sentinel 99.0
    a18 = base("R7", values={"max_wvht_m": 99.0}, metadata={"units": {"value": "m", "source": "header"}})
    cases.append(("R7 99", "R7", a18, ("outside_tolerance", "correct", "false_proceed")))
    # R1b correct refusal
    a19 = base("R1b", status="refused", action="refuse",
               texts=["No usable values: all 1200 records are no-data sentinels. Nothing compared."])
    cases.append(("R1b refusal", "R1b", a19, ("not_applicable", "not_applicable", "correct_refusal_or_flag")))
    # candidate not available
    a20 = base("R7", status="candidate_not_available", action=None)
    cases.append(("R7 n/a", "R7", a20, ("candidate_not_available", "candidate_not_available",
                                        "candidate_not_available")))
    # S3 refusal on undocumented version
    a21 = base("S3", status="refused", action="refuse",
               texts=["datum undetermined: product version STOFS_2D_GLOBAL.V4.0.0 is not documented"],
               metadata={"model_datum": {"value": "undetermined", "source": None}})
    cases.append(("S3 refusal", "S3", a21, ("not_applicable", "correct", "correct_refusal_or_flag")))
    # N3
    a22 = base("N3", values={"residual_max_m": 2.209, "times_utc": ["2022-09-28 22:18", "2022-09-28 22:30"]},
               metadata={"obs_datum": {"value": "MLLW", "source": "req"}, "pred_datum": {"value": "MLLW", "source": "req"},
                         "units": {"value": "m", "source": "req"}})
    cases.append(("N3", "N3", a22, ("within_tolerance", "correct", "correct_proceed")))

    fails = 0
    for name, tid, ans, want in cases:
        got = (G.grade_values(refs[tid], ans)[0], G.grade_metadata(refs[tid], ans)[0], G.grade_decision(refs[tid], ans)[0])
        status = "ok" if got == want else "FAIL"
        if got != want:
            fails += 1
        print(f"{status:4} {name:18} got {got} want {want}")
    print(f"{len(cases) - fails}/{len(cases)} grader self-tests pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
