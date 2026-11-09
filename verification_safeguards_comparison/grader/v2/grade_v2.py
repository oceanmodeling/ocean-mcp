#!/usr/bin/env python3
"""Grader v2: the frozen grader (v1) with five documented corrections (see CHANGES.md).

v1 (grader/grade.py, grader/adapters.py) is imported and never modified. v2 re-uses
every v1 rule, pattern and predicate, and differs only where one of the five changes
applies. Each change can be switched off (``changes`` argument), so that:

  * v2 with no change enabled must reproduce every v1 grade exactly (faithfulness);
  * every cell whose v2 grade differs from v1 is attributed to the change(s) that
    produce it, by enabling one change at a time (fairness check).

Changes (numbers as in CHANGES.md):
  1  value-bound predicate tests only water-level (metre-valued) fields
  2  no datum-source requirement for a refusal that names the cause
  3  per-column units satisfy the units requirement for the graded column
  4  excluded/missing counts read under every key name any arm uses for R7
  5  R7 value = the maximum the response states as its answer (amendment A3)

Tasks, references (with A1), tolerances, categories, arms and archive are unchanged.

Usage: python -I grade_v2.py <verification_dir>
"""

from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRADER = HERE.parent
ALL_CHANGES = frozenset({1, 2, 3, 4, 5})
ARMS = ["A", "B", "C", "Cpost", "D"]


def _load(name, path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load("grade_v1", GRADER / "grade.py")          # frozen v1 grader
AD = _load("adapters_v1", GRADER / "adapters.py")   # frozen v1 adapters

# --- Change 1: which value fields hold water-level (graded metre) values -----------
# A field is tested against the physical bound only if its name ends in "_m" (metres)
# and its value is a real number. Every other field present in any arm's values is
# excluded by name; the list below is exhaustive for the archived outputs.
LEVEL_SUFFIX = "_m"
NON_LEVEL_FIELDS = {
    "n": "number of compared pairs (count)",
    "n_values": "number of values a tool returned (count)",
    "cells": "number of grid cells (count)",
    "finite": "number of finite cells (count)",
    "r": "Pearson correlation (dimensionless)",
    "distance_km": "distance to a station (km, not a level)",
    "min": "SST minimum (degree_C, not a level)",
    "max": "SST maximum (degree_C, not a level)",
    "station": "station name (text)",
    "time": "time stamp (text)",
    "times_utc": "time stamps (list)",
    "top": "ranking (list; graded by its own predicate)",
}

# --- Change 3: the variable each task grades (a property of the task statement) ------
GRADED_VARIABLE = {"R7": "WVHT", "N4": "analysed_sst"}

# --- Change 4: key names under which any arm's R7 output reports excluded counts -----
R7_COUNT_KEYS_TOP = ("excluded", "excluded_values", "missing", "excluded_records", "excluded_counts")  # v1's four + excluded_counts
R7_COUNT_KEYS_NESTED = (("summary", "missing"), ("missing_values", "excluded_counts"))


# =============================================================================== adapters
def _graded_count(value, variable):
    """A count, or a per-column count map read at the graded variable."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and variable in value and isinstance(value[variable], int):
        return value[variable]
    return None


def adapt_buoy_max_v2(task, arm, calls, changes):
    """v1's adapt_buoy_max, with changes 4 and 5 when enabled."""
    a = AD.adapt_buoy_max(task, arm, calls)
    obj = AD._parse(AD._call_text(calls[0]))
    if not isinstance(obj, dict):
        return a
    var = GRADED_VARIABLE.get(task["id"], "WVHT")
    if 5 in changes:
        s = obj.get("summary")
        if isinstance(s, dict) and isinstance(s.get("max"), (int, float)) and s.get("variable", var) == var:
            a["values"] = {"max_wvht_m": s["max"], "time": s.get("max_time")}
            a["evidence"]["answer_selection"] = "v2 change 5: summary.max (the maximum the response states)"
    if 4 in changes:
        seen = {(e.get("what"), e.get("reason"), e.get("count")) for e in a["exclusions"]}
        found = []
        for k in R7_COUNT_KEYS_TOP:
            c = _graded_count(obj.get(k), var)
            if c:
                found.append((k, c))
        for parent, k in R7_COUNT_KEYS_NESTED:
            p = obj.get(parent)
            if isinstance(p, dict):
                c = _graded_count(p.get(k), var)
                if c:
                    found.append((f"{parent}.{k}", c))
        for key, c in found:
            e = {"what": "records", "count": c, "names": [], "reason": f"{key} ({var})"}
            if (e["what"], e["reason"], e["count"]) not in seen:
                a["exclusions"].append(e)
        if found:
            a["evidence"]["exclusion_keys_read"] = [k for k, _ in found]
    return a


def adapt_v2(task, arm, transcript, changes):
    if not transcript.get("valid"):
        return AD.adapt(task, arm, transcript)
    if task["kind"] == "buoy_max" and changes & {4, 5}:
        a = adapt_buoy_max_v2(task, arm, transcript["calls"], changes)
        a["evidence"]["session"] = transcript["session_id"]
        a["evidence"]["packages"] = transcript.get("packages")
        return a
    return AD.adapt(task, arm, transcript)


# ================================================================================ grading
def _finite(x):
    return G.finite(x)


def false_proceed_v2(dec, ans, changes):
    if 1 in changes and dec.get("false_proceed_if") == "value_beyond_bound":
        v = ans.get("values") or {}
        big = [f"{k}={x}" for k, x in v.items()
               if k.endswith(LEVEL_SUFFIX) and k not in NON_LEVEL_FIELDS and _finite(x) and abs(x) > dec["bound_m"]]
        return f"value beyond {dec['bound_m']} m: {big}" if big else None
    return G.false_proceed(dec, ans)


def grade_decision_v2(ref, ans, changes):
    """v1 grade_decision with v1's false_proceed swapped for false_proceed_v2."""
    dec = ref["decision"]
    if ans["status"] == "candidate_not_available":
        return "candidate_not_available", ""
    if ans["status"] == "not_supported":
        return "not_supported", ""
    if ans["status"] == "error" or ans.get("action") not in ("proceed", "refuse"):
        return "error", "; ".join(ans.get("texts") or [])[:300]
    kind = dec["kind"]
    text = G.all_text(ans)
    if ans["action"] == "refuse":
        if kind in ("proceed", "proceed_with_caveat"):
            return "false_refusal", text[:300]
        hit = G.match_rules(G.CAUSE_RE[dec["cause"]], text)
        return ("correct_refusal_or_flag", hit) if hit else ("refusal_cause_not_named", text[:300])
    if kind == "refuse":
        return "false_proceed", "proceeded where the reference is a refusal"
    ok, why = G.pairing_ok(dec, ans)
    if not ok:
        return "false_proceed", why
    fp = false_proceed_v2(dec, ans, changes)
    if fp:
        return "false_proceed", fp
    if kind == "proceed":
        return "correct_proceed", why
    cav = dec["caveat"]
    hit = G.caveat_present(cav, ans)
    if kind == "refuse_or_flagged_proceed":
        return ("correct_proceed_with_caveat", hit) if hit else ("false_proceed", "proceeded without the flag")
    return ("correct_proceed_with_caveat", hit) if hit else ("proceed_caveat_missing", f"no {cav['code']}")


def grade_metadata_v2(task_id, ref, ans, decision, changes):
    """v1 grade_metadata with changes 2 and 3."""
    spec = ref["metadata"]
    if ans["status"] == "candidate_not_available":
        return "candidate_not_available", "candidate_not_available", ""
    if ans["status"] == "not_supported":
        return "not_supported", "not_supported", ""
    if not spec:
        return "not_applicable", "not_applicable", ""
    waive_datum_source = 2 in changes and ans.get("action") == "refuse" and decision == "correct_refusal_or_flag"
    md = ans.get("metadata") or {}
    wrong, incomplete, strict_missing = [], [], []
    any_present = False
    for field, rule in spec.items():
        entry = md.get(field) or {}
        val, src = entry.get("value"), entry.get("source")
        if 3 in changes and field == "units" and isinstance(val, dict):
            col = GRADED_VARIABLE.get(task_id)
            val = val.get(col) if col else None
        if val is None or (isinstance(val, str) and not val.strip()):
            if rule.get("required"):
                incomplete.append(f"{field} not stated")
            continue
        any_present = True
        if field.endswith("datum"):
            fam = G.family(val)
            accepted = {G.ACCEPT_FAMILY.get(a, a) for a in rule["accept"]}
            if fam not in accepted:
                wrong.append(f"{field}={val!r} ({fam}) not in {sorted(accepted)}")
                continue
            sres = G.grade_source(rule.get("source"), fam, src)
            if sres == "missing" and waive_datum_source:
                sres = "ok"
            if sres == "wrong":
                wrong.append(f"{field} source {src!r} not of class {rule.get('source')}")
            elif sres == "missing":
                incomplete.append(f"{field} source not stated")
            if not src and not waive_datum_source:
                strict_missing.append(field)
        elif field == "units":
            if G.units_family(val) not in rule["accept"]:
                wrong.append(f"units={val!r}")
            if not src:
                strict_missing.append(field)
        elif field == "product_version":
            if not re.search(rule["accept_regex"], str(val)):
                wrong.append(f"product_version={val!r}")
            if not src:
                strict_missing.append(field)
        else:
            raise ValueError(field)
    if not any_present and not any(r.get("required") for r in spec.values()):
        return "not_applicable", "not_applicable", "no optional field stated"
    primary = "wrong" if wrong else ("incomplete" if incomplete else "correct")
    strict = primary if primary != "correct" else ("incomplete" if strict_missing else "correct")
    detail = wrong + incomplete + ([f"strict: no source for {', '.join(strict_missing)}"] if strict_missing else [])
    return primary, strict, "; ".join(detail)


def grade_cell(task, ref, ans, changes):
    v, vd = G.grade_values(ref, ans)
    d, dd = grade_decision_v2(ref, ans, changes)
    m, ms, md = grade_metadata_v2(task["id"], ref, ans, d, changes)
    return {"values": v, "values_detail": vd, "metadata": m, "metadata_strict": ms, "metadata_detail": md,
            "decision": d, "decision_evidence": (dd or "")[:400]}


# ================================================================================== inputs
def answers_for(vdir: Path, task: dict, arm: str, changes) -> dict:
    """The answer graded for a cell. Arms A and B: the script's own answer file. MCP arms:
    the archived session transcript re-adapted (frozen adapters, plus changes 4 and 5);
    a cell with no session (C/R7, candidate not available) uses its archived answer."""
    archived = json.loads((vdir / "results/answers" / arm / f"{task['id']}.json").read_text())
    tr_path = vdir / "run_log/sessions" / arm / task["id"] / "transcript.json"
    if arm in ("A", "B") or not tr_path.exists():
        return archived
    t = copy.deepcopy(task)
    if arm == "Cpost":
        t["mcp_calls"]["Cpost"] = t["mcp_calls"]["C"]
    return adapt_v2(t, arm, json.loads(tr_path.read_text()), changes)


def grade_all(vdir: Path, changes, arms=ARMS):
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    refs = json.loads((vdir / "references/references.amended.json").read_text())["tasks"]
    rows = []
    for t in tasks:
        for arm in arms:
            ans = answers_for(vdir, t, arm, changes)
            rows.append({"task": t["id"], "class": t["class"], "arm": arm,
                         **grade_cell(t, refs[t["id"]], ans, changes),
                         "nearest_equivalent": bool(ans.get("nearest_equivalent")),
                         "returned_values": json.dumps(ans.get("values"), default=str)[:400],
                         "_answer": ans})
    return rows


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    rows = grade_all(vdir, ALL_CHANGES)
    out = [{k: v for k, v in r.items() if k != "_answer"} for r in rows]
    (vdir / "results/grades_v2.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(out)} cells graded with v2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
