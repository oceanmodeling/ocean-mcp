#!/usr/bin/env python3
"""Study 1: outcome class of every case, from the reference record and the tool's MCP response.

Frozen with DESIGN.md (section 4.5-4.7). The grading rules are fixed here before any session
is run. Inputs:
  * reference/results/w49_7/cases.jsonl          (reference/classify.py, window (0, 49.7] h)
  * run_log/sessions/stofs030/<product>_<YYYYMMDD>/transcript.json.gz
  * run_log/sessions/stofs020/<product>_<YYYYMMDD>/transcript.json.gz   (contrast)
Outputs (results/study1/): outcomes.jsonl, outcomes.csv, counts_*.csv, contrast_020.csv.

Outcome classes (DESIGN.md 4.5):
  correct_comparison | correct_refusal | refusal_reason_differs | false_refusal
  | undetected_problem | not_eligible | other_discrepancy
with a sub-label (e.g. reason matched / differed; which statistic differed).

The refusal-reason patterns below were written from the message strings of stofs-mcp 0.3.0
(adapter knowledge, a stated limitation); they do not influence the reference.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

PKG = Path(__file__).resolve().parent.parent
TOL_M = 0.01  # brief: statistics equal to the separate-code recalculation within 1 cm

# Frozen call templates (DESIGN.md 5.3). call_id == case_id == f"{product}_{YYYYMMDD}_{station}".
MODEL_ARG = {"3d": "3d_atlantic", "2d": "2d_global"}


def call_030(case: dict) -> dict:
    d = case["cycle"][:10]
    return {"call_id": case["case_id"], "tool": "stofs_compare_with_observations",
            "arguments": {"station_id": case["station_id"], "model": MODEL_ARG[case["product"]],
                          "cycle_date": d, "cycle_hour": "12", "lead_start_hours": 0,
                          "lead_end_hours": 49.7, "response_format": "json"}}


def call_020(case: dict) -> dict:
    d = case["cycle"][:10]
    return {"call_id": case["case_id"], "tool": "stofs_compare_with_observations",
            "arguments": {"station_id": case["station_id"], "model": MODEL_ARG[case["product"]],
                          "cycle_date": d, "cycle_hour": "12",
                          "hours_to_compare": 72 if case["product"] == "3d" else 54,
                          "response_format": "json"}}


def call_coops(station_id: str) -> dict:
    return {"call_id": f"datums_{station_id}", "tool": "coops_get_datums",
            "arguments": {"station_id": station_id, "units": "metric"}}


class MarkdownSuccess(RuntimeError):
    """A non-JSON response that looks like a successful comparison: the frozen call template
    (response_format="json") was not used; grading refuses to read it as a decline."""


_MD_SUCCESS = re.compile(r"\bRMSE\b.*\bBias\b|\bBias\b.*\bRMSE\b", re.S | re.I)

REASON_PATTERNS = [  # (tool reason, regex on the response text)
    ("no_valid_model", re.compile(r"No usable STOFS values|No valid STOFS values in the comparison window")),
    ("datum_undeterminable", re.compile(r"vertical datum of the STOFS values .* could not be established", re.S)),
    ("datum_no_coops_equivalent", re.compile(r"has no CO-OPS equivalent")),
    ("obs_unavailable", re.compile(r"Could not fetch CO-OPS observations|No CO-OPS observations available")),
    ("obs_all_invalid", re.compile(r"none has a usable value")),
    ("align_failed", re.compile(r"Could not align")),
    ("station_not_in_file", re.compile(r"not found in this STOFS file")),
    ("http_error", re.compile(r"^HTTP \d{3} error")),
    ("unexpected_error", re.compile(r"^Unexpected error")),
]
# Which tool reasons count as matching which reference reasons.
MATCHES = {
    "no_valid_model_in_window": {"no_valid_model"},
    "datum_undeterminable": {"datum_undeterminable", "datum_no_coops_equivalent"},
    "paired_datum_not_published": {"obs_unavailable"},
    "no_valid_obs_in_window": {"obs_unavailable", "obs_all_invalid"},
    "no_common_valid_times": {"align_failed", "obs_unavailable"},
}


def load_transcripts(root: Path) -> dict:
    """case_id -> call record (content text, parsed JSON or None, http events, validity)."""
    out = {}
    for p in sorted(root.glob("*/transcript.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            tr = json.load(fh)
        for c in tr["calls"]:
            text = "".join(x.get("text", "") for x in c["content"] if x.get("type") == "text")
            try:
                js = json.loads(text)
            except ValueError:
                js = None
            out[c["call_id"]] = {"text": text, "json": js if isinstance(js, dict) else None,
                                 "http": c.get("http", []), "valid": c.get("valid", False),
                                 "session_valid": tr.get("valid", False), "session": tr["session_id"]}
    return out


def requested_coops(http: list[dict]) -> dict | None:
    for e in http:
        if e.get("event") == "served" and "/api/prod/datagetter" in e.get("url", ""):
            p = dict(parse_qsl(urlsplit(e["url"]).query))
            return {"datum": p.get("datum"), "begin": p.get("begin_date"), "end": p.get("end_date"),
                    "rule": e.get("rule"), "wp5_rule": e.get("wp5_rule"), "status": e.get("status")}
    return None


def tool_reason(text: str) -> str:
    for name, rx in REASON_PATTERNS:
        if rx.search(text):
            return name
    return "unclassified"


def grade(ref: dict, call: dict | None) -> dict:
    """One case. Returns the outcome class, sub-label and the evidence used."""
    if call is None:
        return {"class": "not_run", "sub": "no call recorded"}
    if not call["valid"]:
        return {"class": "invalid_session", "sub": "replay miss or network attempt"}
    exp = ref["expected"]
    js = call["json"]
    proceeded = js is not None and "statistics" in js
    req = requested_coops(call["http"])
    ev = {"tool_proceeded": proceeded, "requested_coops": req}
    if not proceeded and js is None and _MD_SUCCESS.search(call["text"]) and "Nothing was compared" not in call["text"]:
        raise MarkdownSuccess(f"{ref['case_id']}: response is not JSON but reads as a comparison")
    if not proceeded:
        reason = tool_reason(call["text"])
        ev["tool_reason"] = reason
        ev["tool_text"] = call["text"][:600]
        if exp["expected"] == "compare":
            if exp.get("refusal_also_acceptable") and reason == "datum_undeterminable":
                return {"class": "correct_refusal", "sub": "refusal accepted for an unlabelled file", **ev}
            return {"class": "false_refusal", "sub": reason, **ev}
        ok = any(reason in MATCHES.get(r, set()) for r in exp["reasons"])
        if exp["expected"] == "refuse":
            # a decline counts as a correct refusal only when its reason matches
            return {"class": "correct_refusal" if ok else "refusal_reason_differs",
                    "sub": "reason matches" if ok else f"reason differs ({reason})", **ev}
        # not eligible is a reference property; the tool's handling is the sub-label
        return {"class": "not_eligible", "sub": "declined, reason matches" if ok else f"declined, other reason ({reason})", **ev}

    # the tool proceeded
    pair_ok = (js.get("stofs_datum") == ref["reference_datum"]
               and req is not None and req["datum"] == ref["observations"].get("paired_datum")
               and js.get("coops_datum") == ref["observations"].get("paired_datum"))
    ev["tool_pairing"] = {"stofs_datum": js.get("stofs_datum"), "coops_datum": js.get("coops_datum"),
                          "requested": req and req["datum"]}
    ev["reference_pairing"] = {"model": ref["reference_datum"], "coops": ref["observations"].get("paired_datum")}
    if exp["expected"] in ("refuse", "not_eligible"):
        return {"class": "undetected_problem", "sub": f"compared a case the reference rules out ({','.join(exp['reasons'])})", **ev}
    if not pair_ok:
        return {"class": "undetected_problem", "sub": "wrong datum pairing", **ev}
    if ref.get("substring_collision"):
        ev["identity_note"] = "the ID also occurs in an earlier record's name; the tool may read another record"
    ts, rs = js.get("statistics") or {}, ref["statistics"]
    diffs = {}
    for k in ("bias", "rmse", "mae"):
        if ts.get(k) is None or rs.get(k) is None:
            diffs[k] = None
        else:
            diffs[k] = ts[k] - rs[k]
    ev["stat_diffs"] = diffs
    ev["n_tool"], ev["n_ref"] = ts.get("n"), rs.get("n")
    n_ok = ts.get("n") == rs.get("n")
    stat_ok = all(d is not None and abs(d) <= TOL_M for d in diffs.values())
    # counts: model exclusions over the whole station series; observation exclusions over the
    # range the tool requested (see DESIGN.md 4.5)
    tex = (js.get("window") or {}).get("excluded_model_records") or {}
    t_model_excl = sum(int(v) for v in tex.values())
    r_model_excl = sum(v for k, v in ref["model_counts_all"].items() if k != "valid")
    ev["model_excluded"] = {"tool": t_model_excl, "reference": r_model_excl, "tool_detail": tex}
    oq = js.get("observation_quality") or {}
    t_obs_excl = sum(int(oq.get(k, 0)) for k in ("missing", "nonfinite", "sentinel", "implausible"))
    ev["obs_excluded_tool"] = t_obs_excl
    invalid_in_window = sum(v for k, v in ref["model_counts_window"].items() if k != "valid")
    nearest = int(((js.get("alignment") or {}).get("nearest")) or 0)
    ev["tool_nearest_pairs"] = nearest
    if not (n_ok and stat_ok):
        extra = (ts.get("n") or 0) - (rs.get("n") or 0)
        if extra > 0 and invalid_in_window + int(ref["observations"].get("counts", {}).get("implausible", 0)) > 0 \
                and extra > nearest:
            return {"class": "undetected_problem", "sub": "a value the reference excludes entered a statistic", **ev}
        if nearest > 0:
            return {"class": "other_discrepancy", "sub": f"tool paired {nearest} observations by nearest time (reference: exact only)", **ev}
        if ref.get("substring_collision"):
            return {"class": "other_discrepancy", "sub": "station identity (ID substring of an earlier record)", **ev}
        return {"class": "other_discrepancy", "sub": "statistics or n differ from the recalculation", **ev}
    if t_model_excl != r_model_excl:
        sub = ("count differs: values within the reference bound's margin outside the window"
               if invalid_in_window == 0 else "count differs")
        return {"class": "other_discrepancy", "sub": sub, **ev}
    return {"class": "correct_comparison", "sub": "", **ev}


def grade_contrast_020(ref: dict, call: dict | None) -> dict:
    """stofs-mcp 0.2.0: decision and pairing only (DESIGN.md 4.7)."""
    if call is None or not call["valid"]:
        return {"decision": "not_run" if call is None else "invalid_session"}
    js = call["json"]
    proceeded = js is not None and "statistics" in js
    req = requested_coops(call["http"])
    paired = ref["observations"].get("paired_datum")
    return {"decision": "proceed" if proceeded else "decline",
            "reason": None if proceeded else tool_reason(call["text"]),
            "requested_datum": req and req["datum"], "reference_paired_datum": paired,
            "pairing": None if req is None else ("right" if req["datum"] == paired else "wrong"),
            "expected": ref["expected"]["expected"]}


def main() -> int:  # pragma: no cover - run in Phase 2
    ref_p = PKG / "reference/results/w49_7/cases.jsonl"
    refs = [json.loads(x) for x in ref_p.read_text().splitlines()]
    t030 = load_transcripts(PKG / "run_log/sessions/stofs030")
    t020 = load_transcripts(PKG / "run_log/sessions/stofs020")
    out = PKG / "results/study1"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in refs:
        g = grade(r, t030.get(r["case_id"]))
        c = grade_contrast_020(r, t020.get(r["case_id"]))
        rows.append({"case_id": r["case_id"], "product": r["product"], "cycle": r["cycle"],
                     "station_id": r["station_id"], "expected": r["expected"]["expected"],
                     "class": g["class"], "sub": g["sub"], "evidence": g, "contrast_020": c})
    with open(out / "outcomes.jsonl", "w") as fh:
        for x in rows:
            fh.write(json.dumps(x, sort_keys=True) + "\n")
    print(Counter((x["product"], x["class"]) for x in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
