"""Part B analysis (offline, standard library only), as fixed in DESIGN.md 3-6.

Reads archive/session1_record.json (and archive/session2_record.json once B1's
second session exists) and writes to results/:

  b1_session1.json    station, the tool's own comparison, the forecast
  b1_pairs.json       client pairing and statistics (only after session 2)
  b2.json             ofs_compare_with_coops output and the CO-OPS datums table
  b3_table.json/.md   vdatum against CO-OPS station datums at Fort Myers
  b4_section.json     RTOFS temperature section, run and valid time
  part_b_numbers.json every reported number with its provenance

    python3 -I scripts/analyze_part_b.py
"""

from __future__ import annotations

import inspect
import json
import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
RES = PACKAGE / "results"
S1 = "archive/session1_record.json"
S2 = "archive/session2_record.json"
PEAK_MLLW_MM = (
    2613  # Fort Myers observed peak, verification/ian_cross_server (results.json)
)
PAIR_TOL = timedelta(minutes=30)
NUMBERS: dict[str, dict] = {}


def at() -> str:
    """'scripts/analyze_part_b.py:<line>' of the calling statement."""
    return f"scripts/analyze_part_b.py:{inspect.currentframe().f_back.f_lineno}"


def returned(key, value, unit, tool, call, source=S1):
    if isinstance(value, float) and math.isnan(value):
        value = "NaN (non-standard JSON token in the tool response)"
    NUMBERS[key] = {
        "value": value,
        "unit": unit,
        "kind": "returned",
        "tool": tool,
        "call": call,
        "archive": source,
    }


def computed(key, value, unit, where, how):
    NUMBERS[key] = {
        "value": value,
        "unit": unit,
        "kind": "computed",
        "computed": where,
        "how": how,
    }


def dump(name: str, obj) -> None:
    RES.mkdir(exist_ok=True)
    (RES / name).write_text(
        json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_calls(path: str) -> tuple[dict, dict]:
    """Calls keyed by label (a repeat 'S1.3r' replaces 'S1.3'), and the record."""
    rec = json.loads((PACKAGE / path).read_text())
    calls = {}
    for c in rec["calls"]:
        calls[c["key"].rstrip("r") if c["key"].endswith("r") else c["key"]] = c
    return calls, rec


def text(call) -> str:
    return call["result"]["content"][0]["text"]


def md_table(md: str) -> dict:
    """'| NAME | value | description |' rows of a markdown table -> {NAME: value string}."""
    out = {}
    for m in re.finditer(r"^\|\s*([A-Z0-9]+)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|", md, re.M):
        out[m.group(1)] = m.group(2)
    return out


def latlon(md: str) -> tuple[float, float]:
    la = re.search(r"\*\*Latitude\*\*:\s*(-?\d+(?:\.\d+)?)", md)
    lo = re.search(r"\*\*Longitude\*\*:\s*(-?\d+(?:\.\d+)?)", md)
    return float(la.group(1)), float(lo.group(1))


# --------------------------------------------------------------------------- B1


def b1(calls: dict, rec: dict) -> None:
    sid = next(
        e["station_id"] for e in rec["events"] if e["note"].startswith("B1: buoy")
    )
    lat, lon = latlon(text(calls["S1.1"]))
    cmp = json.loads(text(calls["S1.2"]))
    fc = json.loads(text(calls["S1.3"]))
    var = next(iter(fc["values"][0]))  # the tool returns the GRIB short name ('swh')
    forecast = [
        {"time": tm, "hs_m": v.get(var)} for tm, v in zip(fc["times"], fc["values"])
    ]
    out = {
        "station_id": sid,
        "station_lat": lat,
        "station_lon": lon,
        "forecast": {
            "cycle": fc["cycle"],
            "grid": fc["grid"],
            "variable_key_returned": var,
            "variables_requested": fc["variables"],
            "n_points": fc["n_points"],
            "series": forecast,
        },
        "tool_comparison": {
            k: cmp[k]
            for k in (
                "cycle",
                "observation_window",
                "comparison_times",
                "forecast_values",
                "observed_values",
            )
        },
        "tool_comparison_stats": {
            k: ("NaN" if isinstance(v, float) and math.isnan(v) else v)
            for k, v in cmp["stats"].items()
        },
        "pairing_rule_stated_in_response": any(
            k in json.dumps(cmp).lower() for k in ("tolerance", "pairing", "nearest")
        ),
    }
    dump("b1_session1.json", out)
    returned("b1_station", sid, "id", "ndbc_get_station", "S1.1")
    returned("b1_cycle", fc["cycle"], "cycle", "ww3_get_forecast_at_point", "S1.3")
    returned(
        "b1_forecast_valid_times",
        fc["n_points"],
        "times",
        "ww3_get_forecast_at_point",
        "S1.3",
    )
    returned(
        "b1_tool_pairs",
        cmp["stats"]["n"],
        "pairs",
        "ww3_compare_forecast_with_buoy",
        "S1.2",
    )
    returned(
        "b1_tool_pair_times",
        cmp["comparison_times"],
        "UTC",
        "ww3_compare_forecast_with_buoy",
        "S1.2",
    )
    for k in ("bias", "rmse", "mae", "peak_error", "correlation"):
        returned(
            f"b1_tool_{k}",
            cmp["stats"][k],
            "m" if k != "correlation" else "-",
            "ww3_compare_forecast_with_buoy",
            "S1.2",
        )
    if not (PACKAGE / S2).exists():
        print("B1: session 2 not archived yet; pairing not computed")
        return
    calls2, _ = load_calls(S2)
    obs_resp = json.loads(text(calls2["S2.1"]))
    naive = 0
    obs = []
    for r in obs_resp["records"]:
        if r.get("WVHT") is None or not r.get("datetime"):
            continue
        t = datetime.fromisoformat(r["datetime"])
        if t.tzinfo is None:
            naive += 1
            t = t.replace(tzinfo=timezone.utc)  # NDBC realtime2 rows are UTC
        obs.append((t, float(r["WVHT"])))
    obs.sort()
    pairs = []
    for f in forecast:
        if f["hs_m"] is None:
            continue
        tf = datetime.strptime(f["time"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        near = [(abs(t - tf), t, v) for t, v in obs if abs(t - tf) <= PAIR_TOL]
        if near:
            _, t, v = min(near)  # nearest; equidistant -> earlier (tuple order)
            pairs.append(
                {
                    "forecast_time": f["time"],
                    "obs_time": t.strftime("%Y-%m-%d %H:%M"),
                    "forecast_m": f["hs_m"],
                    "observed_m": v,
                }
            )
    n = len(pairs)
    e = [p["forecast_m"] - p["observed_m"] for p in pairs]
    stats = {
        "n": n,
        "bias_m": sum(e) / n if n else None,
        "rmse_m": math.sqrt(sum(x * x for x in e) / n) if n else None,
        "mae_m": sum(abs(x) for x in e) / n if n else None,
        "r": _pearson(
            [p["forecast_m"] for p in pairs], [p["observed_m"] for p in pairs]
        )
        if n >= 3
        else None,
        "max_abs_error_m": max((abs(x), p["forecast_time"]) for x, p in zip(e, pairs))
        if n
        else None,
        "computed": at(),
    }
    dump(
        "b1_pairs.json",
        {
            "rule": "nearest observation with non-null WVHT within 30 min (inclusive) of each forecast valid time; equidistant -> earlier",
            "obs_rows_with_wvht": len(obs),
            "obs_naive_timestamps": naive,
            "observations": [
                {"time": t.strftime("%Y-%m-%d %H:%M"), "wvht_m": v} for t, v in obs
            ],
            "pairs": pairs,
            "stats": stats,
        },
    )
    for k in ("n", "bias_m", "rmse_m", "mae_m", "r"):
        computed(
            f"b1_client_{k}",
            stats[k],
            "m" if k.endswith("_m") else "-",
            stats["computed"],
            "DESIGN.md 3.3",
        )


def _pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


# --------------------------------------------------------------------------- B2


def b2(calls: dict) -> None:
    d = json.loads(text(calls["C1"]))
    datums = md_table(text(calls["C2"]))
    dump(
        "b2.json",
        {
            "compare": d,
            "coops_datums_m_above_stnd": datums,
            "navd88_published_by_coops": "NAVD88" in datums,
        },
    )
    returned("b2_model", d["model"], "-", "ofs_compare_with_coops", "C1")
    returned(
        "b2_station",
        f"{d['station_id']} {d['station_name']}",
        "-",
        "ofs_compare_with_coops",
        "C1",
    )
    returned("b2_model_datum", d["model_datum"], "-", "ofs_compare_with_coops", "C1")
    returned("b2_obs_datum", d["obs_datum"], "-", "ofs_compare_with_coops", "C1")
    returned(
        "b2_period",
        [d["period_start"], d["period_end"]],
        "UTC",
        "ofs_compare_with_coops",
        "C1",
    )
    returned(
        "b2_grid_distance_km",
        d["model_grid_distance_km"],
        "km",
        "ofs_compare_with_coops",
        "C1",
    )
    for k, u in (
        ("n", "pairs"),
        ("bias", "m"),
        ("rmse", "m"),
        ("mae", "m"),
        ("peak_error", "m"),
        ("correlation", "-"),
    ):
        returned(f"b2_{k}", d["stats"][k], u, "ofs_compare_with_coops", "C1")


# --------------------------------------------------------------------------- B3


def mm(s: str) -> int:
    return int(Decimal(s) * 1000)


def b3(calls: dict) -> None:
    out_re = re.compile(r"\*\*Output:\*\*\s*(-?\d+\.\d+) m")
    v_mhhw = out_re.search(text(calls["V1"])).group(1)
    v_navd = out_re.search(text(calls["V2"])).group(1)
    dat = md_table(text(calls["V3"]))
    mhhw, mllw, navd = mm(dat["MHHW"]), mm(dat["MLLW"]), mm(dat["NAVD88"])
    c_mhhw = PEAK_MLLW_MM - (mhhw - mllw)
    c_navd = PEAK_MLLW_MM - (navd - mllw)
    where = at()
    v_mhhw_t, v_navd_t = (
        int(Decimal(v_mhhw) * 10000),
        int(Decimal(v_navd) * 10000),
    )  # tenths of mm
    rows = [
        {
            "target": "MHHW",
            "vdatum_m": v_mhhw,
            "coops_m": str(Decimal(c_mhhw) / 1000),
            "diff_mm": str(Decimal(v_mhhw_t - 10 * c_mhhw) / 10),
        },
        {
            "target": "NAVD88",
            "vdatum_m": v_navd,
            "coops_m": str(Decimal(c_navd) / 1000),
            "diff_mm": str(Decimal(v_navd_t - 10 * c_navd) / 10),
        },
    ]
    unc = {
        k: bool(
            re.search(r"uncertain|accuracy|sigma|±|confidence", text(calls[k]), re.I)
        )
        for k in ("V1", "V2", "V3")
    }
    table = {
        "position": {
            "lat": calls["V1"]["arguments"]["lat"],
            "lon": calls["V1"]["arguments"]["lon"],
            "source": "coops_get_station, verification/ian_cross_server/session_record.json call 2",
        },
        "input": "2.613 m above MLLW (Fort Myers observed peak, verification/ian_cross_server)",
        "coops_datums_m_above_stnd": {
            k: dat[k] for k in ("MHHW", "MLLW", "NAVD88", "STND")
        },
        "rows": rows,
        "uncertainty_stated": {
            "vdatum_convert (V1, V2)": unc["V1"] or unc["V2"],
            "coops_get_datums (V3)": unc["V3"],
        },
        "computed": where,
    }
    dump("b3_table.json", table)
    md = [
        "| Target datum | vdatum_convert (m) | From CO-OPS station datums (m) | vdatum - CO-OPS (mm) |",
        "|---|---|---|---|",
        *[
            f"| {r['target']} | {r['vdatum_m']} | {r['coops_m']} | {r['diff_mm']} |"
            for r in rows
        ],
        "",
        f"Input 2.613 m above MLLW at {table['position']['lat']}, {table['position']['lon']}. "
        f"CO-OPS datums (m above STND): MHHW {dat['MHHW']}, MLLW {dat['MLLW']}, NAVD88 {dat['NAVD88']}. "
        f"Uncertainty stated: vdatum_convert {'yes' if table['uncertainty_stated']['vdatum_convert (V1, V2)'] else 'none'}; "
        f"coops_get_datums {'yes' if unc['V3'] else 'none'}.",
    ]
    (RES / "b3_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    returned("b3_vdatum_mhhw_m", v_mhhw, "m MHHW", "vdatum_convert", "V1")
    returned("b3_vdatum_navd88_m", v_navd, "m NAVD88", "vdatum_convert", "V2")
    for k in ("MHHW", "MLLW", "NAVD88"):
        returned(f"b3_coops_{k}_m", dat[k], "m above STND", "coops_get_datums", "V3")
    computed(
        "b3_coops_mhhw_m",
        rows[0]["coops_m"],
        "m MHHW",
        where,
        "2.613 - (MHHW - MLLW), integer mm",
    )
    computed(
        "b3_coops_navd88_m",
        rows[1]["coops_m"],
        "m NAVD88",
        where,
        "2.613 - (NAVD88 - MLLW), integer mm",
    )
    computed(
        "b3_diff_mhhw_mm",
        rows[0]["diff_mm"],
        "mm",
        where,
        "vdatum - CO-OPS, tenths of mm",
    )
    computed(
        "b3_diff_navd88_mm",
        rows[1]["diff_mm"],
        "mm",
        where,
        "vdatum - CO-OPS, tenths of mm",
    )


# --------------------------------------------------------------------------- B4


def b4(calls: dict, rec: dict) -> None:
    t1 = json.loads(text(calls["T1"]))
    t2 = json.loads(text(calls["T2"]))
    t3 = json.loads(text(calls["T3"]))
    req = calls["T2"]["arguments"]["time"]
    run_known = req >= t1["latest_run"]
    with_levels = sum(p["n_levels"] > 0 for p in t2["transect"])
    out = {
        "line": {
            "start": t2["start"],
            "end": t2["end"],
            "total_distance_km": t2["total_distance_km"],
            "n_points": t2["n_points"],
        },
        "variable": t2["variable"],
        "unit": t2["unit"],
        "requested_time": req,
        "time_echoed_by_profile_tool": t3["time"],
        "dataset_axis": [t1["first_time"], t1["last_time"]],
        "latest_run": t1["latest_run"],
        "run_inferred": t1["latest_run"] if run_known else None,
        "forecast_hour_inferred": (
            datetime.fromisoformat(req.replace("Z", "+00:00"))
            - datetime.fromisoformat(t1["latest_run"].replace("Z", "+00:00"))
        ).total_seconds()
        / 3600
        if run_known
        else None,
        "profiles_with_levels": with_levels,
        "failed": with_levels < 10,
        "points": [
            {
                "distance_km": p["distance_km"],
                "lat": p["lat"],
                "lon": p["lon"],
                "levels": p["profile"],
            }
            for p in t2["transect"]
        ],
        "computed": at(),
    }
    dump("b4_section.json", out)
    returned("b4_latest_run", t1["latest_run"], "UTC", "rtofs_get_latest_time", "T1")
    returned("b4_axis", out["dataset_axis"], "UTC", "rtofs_get_latest_time", "T1")
    returned("b4_time_echoed", t3["time"], "UTC", "rtofs_get_profile_forecast", "T3")
    returned(
        "b4_total_distance_km",
        t2["total_distance_km"],
        "km",
        "rtofs_get_transect",
        "T2",
    )
    returned(
        "b4_profiles_with_levels", with_levels, "profiles", "rtofs_get_transect", "T2"
    )
    computed(
        "b4_forecast_hour",
        out["forecast_hour_inferred"],
        "h",
        out["computed"],
        "requested time - latest_run",
    )
    vals = [
        (lv["value"], lv["depth"], p["distance_km"])
        for p in t2["transect"]
        for lv in p["profile"]
    ]
    returned(
        "b4_temp_max",
        max(vals),
        "degC, depth m, distance km",
        "rtofs_get_transect",
        "T2",
    )
    returned(
        "b4_max_depth_levels",
        max(p["n_levels"] for p in t2["transect"]),
        "levels",
        "rtofs_get_transect",
        "T2",
    )


def main() -> None:
    calls, rec = load_calls(S1)
    b1(calls, rec)
    b2(calls)
    b3(calls)
    b4(calls, rec)
    dump("part_b_numbers.json", NUMBERS)
    print(f"Part B analysis: {len(NUMBERS)} numbers")


if __name__ == "__main__":
    main()
