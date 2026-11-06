#!/usr/bin/env python3
"""Grade every arm's answers on three independent axes against the frozen references.

Axis 1, values: within_tolerance | outside_tolerance | not_returned | not_applicable |
    not_supported | candidate_not_available
Axis 2, metadata: correct | incomplete | wrong | not_applicable | not_supported |
    candidate_not_available   (also a 'strict' variant, see METADATA RULES)
Axis 3, decision: see references.json decision_outcomes

No composite score is computed. Every detection rule is a fixed regular expression
or a fixed predicate defined in this file; the evidence that triggered it is
written next to each grade so a reader can audit it.

METADATA RULES. Primary: every required field present with an accepted value, and
the datum's stated source of the accepted class. Strict: in addition, every
stated field carries a source. Both are reported; the primary rule is used in
the counts (reason: units and product version are read directly from the file
or the response, whereas the datum is interpreted and version-dependent).

Usage: python -I grade.py <verification_dir> [--arms A,B,C,D]
Reads results/answers/<arm>/<task>.json; writes results/grades.{json,csv,md}.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

# ----------------------------------------------------------- vocabulary ---
DOC_RE = re.compile(r"(documentation|documented|NOMADS|product description|portal|SCN|service change|"
                    r"NOAA doc|notice)", re.I)
FILE_RE = re.compile(r"(file|label|standard_name|long_name|attribute|metadata|netcdf)", re.I)
UNDET_RE = re.compile(r"(undetermined|unknown|unresolved|not established|could not be established|"
                      r"cannot be determined|conflict|absent|missing|unsupported|not documented|undocumented|"
                      r"^none$|^n/?a$)", re.I)
EXCL_WORD = r"(exclud|removed|dropped|skipp|ignored|omitted|filtered|discard|masked|rejected)"

CAVEAT_RE = {
    "realization": [
        (re.compile(r"(realiz|realis|epoch|not (necessarily )?(be )?identical|not guarantee|no guarantee|"
                    r"not (been )?(established|verified|confirmed|demonstrated)|offset|differ|discrepan)", re.I),
         re.compile(r"(datum|LMSL|MSL|mean sea level|reference|vertical)", re.I)),
    ],
    "coords_reversed": [
        (re.compile(r"(swap|revers|transpos|exchang|interchang|flipp|corrected coordinates|"
                    r"coordinate (repair|correction|fix)|lat(itude)?\W.{0,40}lon(gitude)?.{0,40}(order|swapp|revers))",
                    re.I), None),
    ],
    "label_absent_assumed": [
        (re.compile(r"(no|missing|absent|without|lacks?|not (stated|labell?ed|present))[^.]{0,60}"
                    r"(datum|label|standard_name|long_name|attribute)", re.I),
         re.compile(r"(assum|documentation|documented|SCN|inferred|taken from)", re.I)),
    ],
}
CAUSE_RE = {
    "invalid_model_values": [(re.compile(r"(sentinel|no[- ]?data|fill|no (valid|usable)|excluded|implausible|"
                                         r"invalid)", re.I), None)],
    "datum_label_absent": [(re.compile(r"datum", re.I),
                            re.compile(r"(absent|missing|no datum|not (stated|labell?ed|found|present|established|"
                                       r"determined)|undetermined|unknown|could not|cannot)", re.I))],
    "datum_conflict": [(re.compile(r"(conflict|contradict|inconsisten|disagree|mismatch|two different)", re.I),
                        re.compile(r"(datum|label|navd|msl)", re.I))],
    "version_undocumented": [(re.compile(r"(version|v ?4\.0|4\.0\.0)", re.I),
                              re.compile(r"(undocumented|not documented|no documentation|unknown|unsupported|"
                                         r"undetermined|not among|not covered|not one of|not in the documented|"
                                         r"cannot|could not)", re.I))],
}


def family(value) -> str | None:
    """Canonical datum family of a stated datum."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if UNDET_RE.search(s):
        return "undetermined"
    u = s.upper().replace("_", " ")
    if "NAVD" in u:
        return "NAVD88"
    if "MLLW" in u or "MEAN LOWER LOW" in u:
        return "MLLW"
    if re.search(r"\bL?MSL\b", u) or "MEAN SEA LEVEL" in u:
        return "MSL"
    if "GEOID" in u:
        return "GEOID"
    return u


def units_family(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("m", "meter", "meters", "metre", "metres", "metric"):
        return "m"
    if s in ("degree_c", "degc", "°c", "celsius", "deg c", "degrees c", "degree c", "degrees_c"):
        return "degree_C"
    return s


ACCEPT_FAMILY = {"LMSL": "MSL", "MSL": "MSL", "NAVD88": "NAVD88", "NAVD": "NAVD88", "MLLW": "MLLW",
                 "undetermined": "undetermined"}


def match_rules(rules, text: str):
    for a, b in rules:
        ma = a.search(text)
        if ma and (b is None or b.search(text)):
            lo = max(0, ma.start() - 80)
            return text[lo: ma.end() + 80].replace("\n", " ")
    return None


def finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# --------------------------------------------------------------- values ---
def grade_values(ref, ans):
    spec = ref["values"]
    kind = spec["kind"]
    if ans["status"] == "candidate_not_available":
        return "candidate_not_available", ""
    if ans["status"] == "not_supported":
        return "not_supported", ""
    if kind == "not_applicable":
        return "not_applicable", ""
    if kind == "stats_if_proceeding" and ans.get("action") == "refuse":
        return "not_applicable", "refused (an accepted outcome)"
    if ans.get("nearest_equivalent"):
        return "not_supported", "nearest equivalent call; values reported separately, not graded"
    if ans.get("action") != "proceed":
        return "not_returned", "no values (declined or failed)"
    v = ans.get("values") or {}
    tol = spec.get("tol", {})
    ref_v = spec["values"]
    detail = []
    ok = True
    if kind in ("stats", "stats_if_proceeding", "griddap", "scalar"):
        for k, r in ref_v.items():
            x = v.get(k)
            if x is None:
                return "not_returned", f"{k} missing"
            if not finite(x):
                ok = False
                detail.append(f"{k}={x} (not finite)")
                continue
            d = abs(x - r)
            if d > tol.get(k, 0) + 1e-12:
                ok = False
                detail.append(f"{k}: {x} vs {r} (|d|={d:.4g} > {tol.get(k, 0)})")
    elif kind == "residual":
        x = v.get("residual_max_m")
        if x is None:
            return "not_returned", "residual missing"
        if not finite(x) or abs(x - ref_v["residual_max_m"]) > tol["residual_max_m"] + 1e-12:
            ok = False
            detail.append(f"residual {x} vs {ref_v['residual_max_m']}")
        times = v.get("times_utc") or []
        if not times or any(t not in ref_v["time_utc_any_of"] for t in times):
            ok = False
            detail.append(f"times {times} not within {ref_v['time_utc_any_of']}")
    elif kind == "ranking":
        top = v.get("top") or []
        if len(top) < len(ref_v["top"]):
            return "not_returned", f"{len(top)} stations returned"
        for i, (r, key) in enumerate(zip(ref_v["top"], spec["station_keys"])):
            got = top[i]
            if key not in str(got.get("station", "")).split() and key not in str(got.get("station", "")):
                ok = False
                detail.append(f"rank {i + 1}: {got.get('station')} (expected {key})")
            elif not finite(got.get("max_m")) or abs(got["max_m"] - r["max_m"]) > tol["max_m"] + 1e-12:
                ok = False
                detail.append(f"rank {i + 1}: {got.get('max_m')} vs {r['max_m']:.4f}")
    elif kind == "top1":
        st, x = v.get("station"), v.get("max_m")
        if st is None or x is None:
            return "not_returned", "station or value missing"
        if ref_v["station"] not in str(st):
            ok = False
            detail.append(f"station {st} (expected {ref_v['station']})")
        if not finite(x) or abs(x - ref_v["max_m"]) > tol["max_m"] + 1e-12:
            ok = False
            detail.append(f"max {x} vs {ref_v['max_m']:.4f}")
    elif kind == "nearest":
        st, d = v.get("station"), v.get("distance_km")
        if st is None or d is None:
            return "not_returned", "station or distance missing"
        if ref_v["station"] not in str(st):
            ok = False
            detail.append(f"station {st} (expected {ref_v['station']})")
        if not finite(d) or abs(d - ref_v["distance_km"]) > tol["distance_km"]:
            ok = False
            detail.append(f"distance {d} km vs {ref_v['distance_km']:.4f}")
    else:
        raise ValueError(kind)
    return ("within_tolerance" if ok else "outside_tolerance"), "; ".join(detail)


# ------------------------------------------------------------- metadata ---
def grade_source(rule, fam, source):
    """'ok' | 'missing' | 'wrong' for a datum source."""
    if rule in (None, "ANY"):
        return "ok"
    if not source:
        return "missing"
    s = str(source)
    if rule == "DOC":
        if DOC_RE.search(s):
            return "ok"
        return "wrong"
    if rule == "FILE_OR_DOC":
        return "ok" if (DOC_RE.search(s) or FILE_RE.search(s)) else "wrong"
    if rule == "S1_RULE":
        if fam == "undetermined":
            return "ok"
        return "ok" if DOC_RE.search(s) else "wrong"
    raise ValueError(rule)


def grade_metadata(ref, ans):
    spec = ref["metadata"]
    if ans["status"] == "candidate_not_available":
        return "candidate_not_available", "candidate_not_available", ""
    if ans["status"] == "not_supported":
        return "not_supported", "not_supported", ""
    if not spec:
        return "not_applicable", "not_applicable", ""
    md = ans.get("metadata") or {}
    wrong, incomplete, strict_missing, detail = [], [], [], []
    any_present = False
    for field, rule in spec.items():
        entry = md.get(field) or {}
        val, src = entry.get("value"), entry.get("source")
        if val is None or (isinstance(val, str) and not val.strip()):
            if rule.get("required"):
                incomplete.append(f"{field} not stated")
            continue
        any_present = True
        if field.endswith("datum"):
            fam = family(val)
            accepted = {ACCEPT_FAMILY.get(a, a) for a in rule["accept"]}
            if fam not in accepted:
                wrong.append(f"{field}={val!r} ({fam}) not in {sorted(accepted)}")
                continue
            sres = grade_source(rule.get("source"), fam, src)
            if sres == "wrong":
                wrong.append(f"{field} source {src!r} not of class {rule.get('source')}")
            elif sres == "missing":
                incomplete.append(f"{field} source not stated")
            if not src:
                strict_missing.append(field)
        elif field == "units":
            if units_family(val) not in rule["accept"]:
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
    if wrong:
        primary = "wrong"
    elif incomplete:
        primary = "incomplete"
    else:
        primary = "correct"
    strict = primary if primary != "correct" else ("incomplete" if strict_missing else "correct")
    detail = wrong + incomplete + ([f"strict: no source for {', '.join(strict_missing)}"] if strict_missing else [])
    return primary, strict, "; ".join(detail)


# ------------------------------------------------------------- decision ---
def all_text(ans) -> str:
    parts = list(ans.get("texts") or [])
    for e in ans.get("exclusions") or []:
        parts.append(f"excluded {e.get('count')} {e.get('what')} {e.get('reason')} {' '.join(e.get('names') or [])}")
    return "\n".join(str(p) for p in parts)


def caveat_present(cav, ans):
    code = cav["code"]
    text = all_text(ans)
    excl = ans.get("exclusions") or []
    if code in CAVEAT_RE:
        return match_rules(CAVEAT_RE[code], text)
    if code == "doc_source":
        src = ((ans.get("metadata") or {}).get("model_datum") or {}).get("source")
        return src if src and DOC_RE.search(str(src)) else None
    if code == "excluded_stations":
        names = " ".join(n for e in excl for n in (e.get("names") or [])) + " " + text
        if cav.get("ids") and all(i in names for i in cav["ids"]):
            return "named: " + ", ".join(cav["ids"])
        for e in excl:
            if e.get("count") in (cav.get("count_any_of") or []):
                return f"count {e['count']} {e.get('what')}"
        return None
    if code in ("excluded_records", "excluded_obs"):
        counts = [e.get("count") for e in excl if isinstance(e.get("count"), int)]
        if code == "excluded_obs":
            obs = [e.get("count") for e in excl if str(e.get("what", "")).startswith("obs")
                   and isinstance(e.get("count"), int)]
            if sum(obs) in cav["count_any_of"]:
                return f"observation exclusions {obs}"
        want = cav["count_any_of"]
        if want == "any_positive":
            hit = [c for c in counts if c > 0]
            return f"counts {hit}" if hit else None
        for c in counts:
            if c in want:
                return f"count {c}"
        for c in want:
            m = re.search(rf"\b{c}\b[^.]{{0,80}}{EXCL_WORD}|{EXCL_WORD}[^.]{{0,80}}\b{c}\b", text, re.I)
            if m:
                return m.group(0)
        return None
    raise ValueError(code)


def pairing_ok(dec, ans):
    p = dec.get("pairing")
    if not p:
        return True, ""
    md = ans.get("metadata") or {}
    if p.get("same_datum"):
        a = family((md.get("obs_datum") or {}).get("value"))
        b = family((md.get("pred_datum") or {}).get("value"))
        return (a is not None and a == b), f"obs {a} / predictions {b}"
    want = ACCEPT_FAMILY[p["obs_datum"]]
    got = family((md.get("obs_datum") or {}).get("value"))
    return got == want, f"observation datum {got} (required {want})"


def false_proceed(dec, ans):
    pred = dec.get("false_proceed_if")
    v = ans.get("values") or {}
    if pred is None:
        return None
    if pred == "sentinel_in_answer":
        strs = [str(x.get("station")) for x in v.get("top") or []] + [str(v.get("station", ""))]
        bad = [i for i in dec["sentinel_ids"] if any(i in s for s in strs)]
        vals = [x.get("max_m") for x in v.get("top") or []] + [v.get("max_m")]
        big = [x for x in vals if finite(x) and abs(x) > 30]
        if bad or big:
            return f"no-data or implausible station in the answer: {bad or big}"
        return None
    if pred == "value_beyond_bound":
        big = [f"{k}={x}" for k, x in v.items() if finite(x) and abs(x) > dec["bound_m"]]
        return f"value beyond {dec['bound_m']} m: {big}" if big else None
    if pred == "wrong_datum":
        fam = family(((ans.get("metadata") or {}).get("model_datum") or {}).get("value"))
        return None if fam == "MSL" else f"datum stated as {fam}"
    if pred == "wrong_station":
        st = str(v.get("station", ""))
        return None if dec["station"] in st else f"station {st}"
    if pred == "nulls_as_values":
        if (finite(v.get("finite")) and v["finite"] > 9301) or (finite(v.get("min")) and v["min"] < 0.5):
            return "nulls counted as values"
        return None
    if pred == "s4_invalid":
        stats = [v.get(k) for k in ("bias_m", "rmse_m", "mae_m", "r")]
        if any(s is not None and not finite(s) for s in stats):
            return f"non-finite statistics {stats}"
        if v.get("n") is not None and not ans.get("nearest_equivalent") and v["n"] != dec["n_expected"]:
            return f"n={v['n']} (expected {dec['n_expected']})"
        if ans.get("nearest_equivalent") and any(s is not None and not finite(s) for s in stats):
            return "non-finite statistics"
        return None
    raise ValueError(pred)


def grade_decision(ref, ans):
    dec = ref["decision"]
    if ans["status"] == "candidate_not_available":
        return "candidate_not_available", ""
    if ans["status"] == "not_supported":
        return "not_supported", ""
    if ans["status"] == "error" or ans.get("action") not in ("proceed", "refuse"):
        return "error", "; ".join(ans.get("texts") or [])[:300]
    kind = dec["kind"]
    text = all_text(ans)
    if ans["action"] == "refuse":
        if kind in ("proceed", "proceed_with_caveat"):
            return "false_refusal", text[:300]
        hit = match_rules(CAUSE_RE[dec["cause"]], text)
        return ("correct_refusal_or_flag", hit) if hit else ("refusal_cause_not_named", text[:300])
    # proceeded
    if kind == "refuse":
        return "false_proceed", "proceeded where the reference is a refusal"
    ok, why = pairing_ok(dec, ans)
    if not ok:
        return "false_proceed", why
    fp = false_proceed(dec, ans)
    if fp:
        return "false_proceed", fp
    if kind == "proceed":
        return "correct_proceed", why
    cav = dec["caveat"]
    hit = caveat_present(cav, ans)
    if kind == "refuse_or_flagged_proceed":
        return ("correct_proceed_with_caveat", hit) if hit else ("false_proceed", "proceeded without the flag")
    return ("correct_proceed_with_caveat", hit) if hit else ("proceed_caveat_missing", f"no {cav['code']}")


# ----------------------------------------------------------------- main ---
def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    arms = sys.argv[sys.argv.index("--arms") + 1].split(",") if "--arms" in sys.argv else ["A", "B", "C", "D"]
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    refs = json.loads((vdir / "references/references.json").read_text())["tasks"]
    rows = []
    for t in tasks:
        for arm in arms:
            p = vdir / "results/answers" / arm / f"{t['id']}.json"
            if not p.exists():
                rows.append({"task": t["id"], "class": t["class"], "arm": arm, "values": "missing_answer",
                             "metadata": "missing_answer", "metadata_strict": "missing_answer",
                             "decision": "missing_answer"})
                continue
            ans = json.loads(p.read_text())
            ref = refs[t["id"]]
            v, vd = grade_values(ref, ans)
            m, ms, md = grade_metadata(ref, ans)
            d, dd = grade_decision(ref, ans)
            rows.append({"task": t["id"], "class": t["class"], "arm": arm, "values": v, "values_detail": vd,
                         "metadata": m, "metadata_strict": ms, "metadata_detail": md,
                         "decision": d, "decision_evidence": (dd or "")[:400],
                         "nearest_equivalent": bool(ans.get("nearest_equivalent")),
                         "returned_values": json.dumps(ans.get("values"), default=str)[:400]})
    out = vdir / "results"
    tag = "_".join(arms)
    (out / f"grades_{tag}.json").write_text(json.dumps(rows, indent=1) + "\n")
    cols = ["task", "class", "arm", "values", "metadata", "metadata_strict", "decision", "nearest_equivalent",
            "values_detail", "metadata_detail", "decision_evidence", "returned_values"]
    with open(out / f"grades_{tag}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    # counts per arm and axis
    counts: dict = {}
    for r in rows:
        for axis in ("values", "metadata", "metadata_strict", "decision"):
            counts.setdefault(r["arm"], {}).setdefault(axis, {}).setdefault(r[axis], 0)
            counts[r["arm"]][axis][r[axis]] += 1
    (out / f"counts_{tag}.json").write_text(json.dumps(counts, indent=1) + "\n")
    lines = [f"# Grades, arms {', '.join(arms)}", "",
             "| Task | Class | Arm | Values | Metadata (strict) | Decision |", "|---|---|---|---|---|---|"]
    for r in rows:
        ne = " (nearest equivalent)" if r.get("nearest_equivalent") else ""
        lines.append(f"| {r['task']} | {r['class']} | {r['arm']} | {r['values']}{ne} | {r['metadata']} "
                     f"({r['metadata_strict']}) | {r['decision']} |")
    lines += ["", "## Counts per arm", ""]
    for arm, ax in counts.items():
        lines.append(f"**Arm {arm}**")
        for axis, c in ax.items():
            lines.append(f"- {axis}: " + ", ".join(f"{k} {n}" for k, n in sorted(c.items())))
        lines.append("")
    (out / f"grades_{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
