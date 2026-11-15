"""Convert archived MCP session transcripts (arms C and D) into answer records.

An adapter only transcribes what the tool returned: it copies numbers, datum
fields and verbatim notes, warnings and refusal texts. It adds no domain
judgement. The one computation it performs is the frozen client join for N3
(coops-mcp has no residual tool), defined in ``residual_join``.

Answer record (shared with arms A and B):

    task_id, arm, status ('answered' | 'refused' | 'not_supported' |
    'candidate_not_available' | 'error'), action ('proceed' | 'refuse' | None),
    values {...}, nearest_equivalent (bool), nearest_equivalent_note,
    metadata {field: {value, source}}, texts [verbatim strings],
    exclusions [{what, count, names, reason}], evidence {...}
"""

from __future__ import annotations

import json
import math
import re

UNDET_RE = re.compile(
    r"(undetermined|unknown|unresolved|not established|could not be established|cannot be determined|"
    r"conflict|absent|missing|unsupported|not documented|undocumented)",
    re.I,
)


def _parse(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _call_text(call: dict) -> str:
    parts = [c.get("text", "") for c in call.get("content", []) if c.get("type") == "text"]
    return "\n".join(parts)


def _notes(obj: dict) -> list[str]:
    """Verbatim strings from fields whose name says they are a note, warning or hint."""
    out = []
    for k, v in obj.items():
        if isinstance(v, str) and re.search(r"(note|warning|hint|caveat|message)", k, re.I):
            out.append(f"{k}: {v}")
    prov = obj.get("datum_provenance")
    if isinstance(prov, dict) and isinstance(prov.get("warning"), str):
        out.append(f"datum_provenance.warning: {prov['warning']}")
    for k in ("warnings", "notes"):
        if isinstance(obj.get(k), list):
            out += [f"{k}: {x}" for x in obj[k] if isinstance(x, str)]
    return out


def _datum_meta(obj: dict) -> dict:
    prov = obj.get("datum_provenance") if isinstance(obj.get("datum_provenance"), dict) else {}
    model_source = obj.get("stofs_datum_source") or obj.get("datum_source") or prov.get("source")
    version = prov.get("product_version")
    return {
        "model_datum": {"value": obj.get("stofs_datum", obj.get("datum")), "source": model_source},
        "product_version": {"value": version,
                            "source": "tool datum_provenance.product_version" if version else None},
    }


def _blank(task_id, arm, call_ids):
    return {"task_id": task_id, "arm": arm, "status": None, "action": None, "values": {},
            "nearest_equivalent": False, "nearest_equivalent_note": None, "metadata": {},
            "texts": [], "exclusions": [], "evidence": {"call_ids": call_ids}}


def _excl_from_counts(counts, what):
    out = []
    if isinstance(counts, dict):
        for k, v in counts.items():
            if isinstance(v, (int, float)) and v:
                out.append({"what": what, "count": int(v), "names": [], "reason": k})
    return out


# ---------------------------------------------------------------- stofs ---
def adapt_compare(task, arm, calls):
    call = calls[0]
    a = _blank(task["id"], arm, [call["call_id"]])
    spec = next(c for c in task["mcp_calls"][arm] if c["call_id"] == call["call_id"])
    a["nearest_equivalent"] = bool(spec.get("nearest_equivalent"))
    a["nearest_equivalent_note"] = spec.get("nearest_equivalent_note")
    text = _call_text(call)
    obj = _parse(text)
    if isinstance(obj, dict) and isinstance(obj.get("statistics"), dict):
        st = obj["statistics"]
        a.update(status="answered", action="proceed")
        a["values"] = {"n": st.get("n"), "bias_m": st.get("bias"), "rmse_m": st.get("rmse"),
                       "mae_m": st.get("mae"), "r": st.get("correlation")}
        a["metadata"] = _datum_meta(obj)
        a["metadata"]["obs_datum"] = {"value": obj.get("coops_datum"),
                                      "source": "tool response field coops_datum (CO-OPS request datum)"
                                      if obj.get("coops_datum") else None}
        a["metadata"]["units"] = {"value": obj.get("units"),
                                  "source": "tool response field units" if obj.get("units") else None}
        a["texts"] = _notes(obj)
        win = obj.get("window") if isinstance(obj.get("window"), dict) else {}
        a["exclusions"] = _excl_from_counts(win.get("excluded_model_records"), "model_records")
        oq = obj.get("observation_quality") if isinstance(obj.get("observation_quality"), dict) else {}
        a["exclusions"] += _excl_from_counts({k: oq.get(k) for k in ("missing", "nonfinite", "sentinel", "implausible")
                                              if k in oq}, "obs_values")
        a["evidence"]["window"] = {k: obj.get(k) for k in ("comparison_start", "comparison_end", "window_lead_hours",
                                                           "hours_to_compare")}
    else:
        a.update(status="refused", action="refuse")
        a["texts"] = [text]
        a["metadata"] = {"model_datum": {"value": "undetermined" if UNDET_RE.search(text) and
                                         re.search(r"datum", text, re.I) else None, "source": None}}
    return a


def adapt_max(task, arm, calls):
    call = calls[0]
    a = _blank(task["id"], arm, [call["call_id"]])
    text = _call_text(call)
    obj = _parse(text)
    if isinstance(obj, dict) and isinstance(obj.get("top_stations"), list):
        a.update(status="answered", action="proceed")
        top = [{"station": r.get("station"), "max_m": r.get("max_wl")} for r in obj["top_stations"]]
        a["values"] = {"top": top}
        if top:
            a["values"].update({"station": top[0]["station"], "max_m": top[0]["max_m"]})
        a["metadata"] = _datum_meta(obj)
        a["metadata"]["units"] = {"value": obj.get("units"), "source": "tool response field units"
                                  if obj.get("units") else None}
        a["texts"] = _notes(obj)
        for s in obj.get("excluded_stations") or []:
            reasons = s.get("reasons") if isinstance(s, dict) else None
            a["exclusions"].append({"what": "stations", "count": 1,
                                    "names": [s.get("station") if isinstance(s, dict) else str(s)],
                                    "reason": json.dumps(reasons) if reasons else ""})
        a["exclusions"] += _excl_from_counts(obj.get("excluded_values"), "model_values")
    else:
        a.update(status="refused", action="refuse", texts=[text])
    return a


def adapt_station(task, arm, calls):
    call = calls[0]
    a = _blank(task["id"], arm, [call["call_id"]])
    text = _call_text(call)
    obj = _parse(text)
    if isinstance(obj, dict) and isinstance(obj.get("values"), list):
        a.update(status="answered", action="proceed")
        vals = [v for v in obj["values"] if isinstance(v, (int, float)) and math.isfinite(v)]
        a["values"] = {"min_m": min(vals) if vals else None, "n_values": len(obj["values"])}
        a["metadata"] = _datum_meta(obj)
        a["metadata"]["units"] = {"value": obj.get("units"), "source": "tool response field units"
                                  if obj.get("units") else None}
        a["texts"] = _notes(obj)
        a["exclusions"] = _excl_from_counts(obj.get("excluded_model_records"), "model_records")
    else:
        a.update(status="refused", action="refuse", texts=[text])
    return a


def adapt_point(task, arm, calls):
    call = calls[0]
    a = _blank(task["id"], arm, [call["call_id"]])
    text = _call_text(call)
    obj = _parse(text)
    if isinstance(obj, dict) and "nearest_station" in obj:
        a.update(status="answered", action="proceed")
        a["values"] = {"station": obj.get("nearest_station"), "distance_km": obj.get("distance_km")}
        a["metadata"] = _datum_meta(obj)
        a["texts"] = _notes(obj)
    else:
        a.update(status="refused", action="refuse", texts=[text])
    return a


# -------------------------------------------------------------- others ---
def residual_join(obs_records, pred_records):
    """Frozen N3 client join: exact time match, observed minus predicted,
    rounded to 1 mm; maximum and every time attaining it."""
    pred = {r["t"]: float(r["v"]) for r in pred_records if str(r.get("v", "")).strip()}
    resid = []
    for r in obs_records:
        v = str(r.get("v", "")).strip()
        if v and r["t"] in pred:
            resid.append((r["t"], round(float(v) - pred[r["t"]], 3)))
    if not resid:
        return None, []
    top = max(x for _, x in resid)
    return top, [t for t, x in resid if x == top]


def adapt_residual(task, arm, calls):
    a = _blank(task["id"], arm, [c["call_id"] for c in calls])
    wl, pr = (_parse(_call_text(c)) for c in calls)
    if not (isinstance(wl, dict) and isinstance(pr, dict)):
        a.update(status="refused", action="refuse", texts=[_call_text(c) for c in calls])
        return a
    obs = (wl.get("data") or {}).get("data", [])
    preds = (pr.get("data") or {}).get("predictions", [])
    top, times = residual_join(obs, preds)
    a.update(status="answered", action="proceed")
    a["values"] = {"residual_max_m": top, "times_utc": times}
    wp, pp = wl.get("request_params") or {}, pr.get("request_params") or {}
    a["metadata"] = {
        "obs_datum": {"value": wp.get("datum"), "source": "coops-mcp response request_params.datum"},
        "pred_datum": {"value": pp.get("datum"), "source": "coops-mcp response request_params.datum"},
        "units": {"value": "m" if wp.get("units") == "metric" else wp.get("units"),
                  "source": "coops-mcp response request_params.units"},
    }
    a["texts"] = _notes(wl) + _notes(pr)
    a["evidence"]["records"] = {"obs": len(obs), "pred": len(preds), "obs_truncated": wl.get("truncated"),
                                "pred_truncated": pr.get("truncated")}
    a["evidence"]["client_join"] = "grader/adapters.py residual_join (frozen)"
    return a


def adapt_griddap(task, arm, calls):
    call = calls[0]
    a = _blank(task["id"], arm, [call["call_id"]])
    obj = _parse(_call_text(call))
    if not (isinstance(obj, dict) and isinstance(obj.get("data"), list)):
        a.update(status="refused", action="refuse", texts=[_call_text(call)])
        return a
    var = (obj.get("variables") or ["analysed_sst"])[0]
    vals = [r.get(var) for r in obj["data"]]
    fin = [v for v in vals if isinstance(v, (int, float)) and math.isfinite(v)]
    a.update(status="answered", action="proceed")
    a["values"] = {"cells": len(vals), "finite": len(fin), "min": min(fin) if fin else None,
                   "max": max(fin) if fin else None}
    units = obj.get("units")
    if isinstance(units, dict):
        units = units.get(var)
    a["metadata"] = {"units": {"value": units, "source": "tool response field units" if units else None}}
    a["texts"] = _notes(obj)
    a["evidence"]["envelope"] = {k: obj.get(k) for k in ("record_count", "total", "truncated")}
    return a


def adapt_buoy_max(task, arm, calls):
    call = calls[0]
    a = _blank(task["id"], arm, [call["call_id"]])
    obj = _parse(_call_text(call))
    if not (isinstance(obj, dict) and isinstance(obj.get("observations"), list)):
        a.update(status="refused", action="refuse", texts=[_call_text(call)])
        return a
    recs = obj["observations"]
    w = [(r.get("WVHT"), r) for r in recs if isinstance(r.get("WVHT"), (int, float))]
    a.update(status="answered", action="proceed")
    if w:
        top, row = max(w, key=lambda p: p[0])
        a["values"] = {"max_wvht_m": top, "time": row.get("time") or row.get("timestamp")}
    a["metadata"] = {"units": {"value": obj.get("units"), "source": "tool response field units"
                               if obj.get("units") else None}}
    a["texts"] = _notes(obj)
    for k in ("excluded", "excluded_values", "missing", "excluded_records"):
        if isinstance(obj.get(k), dict):
            a["exclusions"] += _excl_from_counts(obj[k], "records")
        elif isinstance(obj.get(k), int) and obj[k]:
            a["exclusions"].append({"what": "records", "count": obj[k], "names": [], "reason": k})
    a["evidence"]["returned_records"] = len(recs)
    a["evidence"]["records_field"] = obj.get("records")
    return a


ADAPTERS = {
    "compare": adapt_compare, "max": adapt_max, "station_min": adapt_station,
    "station_datum": adapt_station, "nearest": adapt_point, "residual": adapt_residual,
    "griddap": adapt_griddap, "buoy_max": adapt_buoy_max,
}


def adapt(task: dict, arm: str, transcript: dict) -> dict:
    if not transcript.get("valid"):
        a = _blank(task["id"], arm, [])
        a.update(status="error", texts=["session invalid: replay miss or blocked network attempt"])
        return a
    calls = transcript["calls"]
    a = ADAPTERS[task["kind"]](task, arm, calls)
    a["evidence"]["session"] = transcript["session_id"]
    a["evidence"]["packages"] = transcript.get("packages")
    return a
