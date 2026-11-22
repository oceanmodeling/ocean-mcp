"""Part A analysis (offline, standard library only), as fixed in DESIGN.md 5-7a.

Reads archive/part_a_record.json.gz (new recording) and the reused Ian session
(read in place, checksum verified), and writes the figure inputs and every
number to results/:

  aircraft_selection.json  rule 6.2, counts per call sign (raw and after QC)
  hdob_qc.json             flag decoding and removal counts, selected aircraft
  sfmr_tools.json          the two SFMR tools' responses and the 403 log lines
  panel_a.json ... panel_d.json   figure inputs
  part_a_numbers.json      every reported number with its provenance

Every computed number carries "computed: scripts/analyze_part_a.py:<line>",
the line of the statement that computed it; every returned number names the
tool, the call key and the archived file.

    python3 -I scripts/analyze_part_a.py
"""

from __future__ import annotations

import gzip
import inspect
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    LANDFALL_LATLON,
    LANDFALL_UTC,
    PACKAGE,
    best_track,
    centre_at,
    dump,
    haversine_km,
    ian_call_text,
    parse_utc,
)

ARCHIVE = "archive/part_a_record.json.gz"
IAN = "verification/ian_cross_server/session_record.json"
RADIUS_KM = 150.0
DAY = "20220928"
PANEL_C = ("2022-09-27 00:00", "2022-09-30 00:00")
BT_SHOWN = (parse_utc("2022-09-26 00:00"), parse_utc("2022-09-30 00:00"))
STATIONS = {"8725520": ("Fort Myers", 2, 3, 4), "8726520": ("St. Petersburg", 5, 6, 7)}
EXPECTED = {
    "fort_myers_residual_max_m": "2.209",
    "fort_myers_residual_max_first_time": "2022-09-28 22:18",
    "st_petersburg_residual_min_m": "-1.755",
    "st_petersburg_residual_min_time": "2022-09-28 23:00",
    "fort_myers_observed_max_m": "2.613",
}

NUMBERS: dict[str, dict] = {}


def at() -> str:
    """'scripts/analyze_part_a.py:<line>' of the calling statement."""
    return f"scripts/analyze_part_a.py:{inspect.currentframe().f_back.f_lineno}"


def returned(
    key: str, value, unit: str, tool: str, call: str, source: str = ARCHIVE
) -> None:
    """Register a number a tool returned."""
    NUMBERS[key] = {
        "value": value,
        "unit": unit,
        "kind": "returned",
        "tool": tool,
        "call": call,
        "archive": source,
    }


def computed(key: str, value, unit: str, where: str, how: str) -> None:
    """Register a number the client computed."""
    NUMBERS[key] = {
        "value": value,
        "unit": unit,
        "kind": "computed",
        "computed": where,
        "how": how,
    }


# --------------------------------------------------------------------------- inputs


def part_a() -> dict:
    """The new recording, calls keyed by their DESIGN.md label."""
    rec = json.load(gzip.open(PACKAGE / ARCHIVE, "rt"))
    return {c["key"]: c for c in rec["calls"]}


def text(call: dict) -> str:
    return call["result"]["content"][0]["text"]


def hdob_records(calls: dict) -> list[dict]:
    """R1 + R2 observations dated 28 Sep 2022, with call key and aware time."""
    out = []
    for key in ("R1", "R2"):
        for o in json.loads(text(calls[key]))["data"]:
            if o["date"] != DAY:
                continue
            t = datetime.strptime(o["date"] + o["time"], "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
            out.append({**o, "call": key, "t": t})
    out.sort(key=lambda o: (o["aircraft"], o["t"]))
    return out


def station_latlon(md: str) -> tuple[float, float]:
    """Coordinates from coops_get_station / ndbc_get_station markdown."""
    la = re.search(r"\*\*Latitude\*\*:\s*(-?\d+(?:\.\d+)?)", md)
    lo = re.search(r"\*\*Longitude\*\*:\s*(-?\d+(?:\.\d+)?)", md)
    return float(la.group(1)), float(lo.group(1))


# --------------------------------------------------------------------------- QC flags (DESIGN.md 7)


def decode_ff(ff) -> dict:
    """NHC HDOB FF field -> which variables are questionable."""
    if not isinstance(ff, str) or not re.fullmatch(r"\d\d", ff):
        return {"position": True, "sfmr": True, "fl_wind": True, "recognised": False}
    d1, d2 = ff
    pos_ok = d1 in "0123"
    met_ok = d2 in "01234569"
    return {
        "position": (d1 in "13") if pos_ok else True,
        "sfmr": (d2 in "3569") if met_ok else True,
        "fl_wind": (d2 in "2469") if met_ok else True,
        "recognised": pos_ok and met_ok,
    }


# --------------------------------------------------------------------------- analysis


def select_aircraft(obs: list[dict], track: list[dict]) -> dict:
    """DESIGN.md 6.2."""
    per = {}
    for o in obs:
        a = per.setdefault(
            o["aircraft"],
            {
                "records": 0,
                "sfmr_nonnull": 0,
                "sfmr_within_150km": 0,
                "sfmr_within_150km_after_qc": 0,
            },
        )
        a["records"] += 1
        if o["sfmr_sfc_wind_kt"] is None:
            continue
        a["sfmr_nonnull"] += 1
        if o["lat"] is None or o["lon"] is None:
            continue
        c = centre_at(track, o["t"])
        if c is None or haversine_km(c[0], c[1], o["lat"], o["lon"]) > RADIUS_KM:
            continue
        a["sfmr_within_150km"] += 1
        q = decode_ff(o["qc_flags"])
        if not q["sfmr"] and not q["position"]:
            a["sfmr_within_150km_after_qc"] += 1
    ranked = sorted(
        per.items(),
        key=lambda kv: (-kv[1]["sfmr_within_150km"], -kv[1]["sfmr_nonnull"], kv[0]),
    )
    ranked_qc = sorted(
        per.items(),
        key=lambda kv: (
            -kv[1]["sfmr_within_150km_after_qc"],
            -kv[1]["sfmr_nonnull"],
            kv[0],
        ),
    )
    return {
        "rule": "most HDOB records with non-null SFMR within 150 km of the interpolated best-track centre, observation date 2022-09-28 UTC; ties: more non-null SFMR, then call sign",
        "per_call_sign": dict(ranked),
        "selected": ranked[0][0],
        "selected_after_qc_sensitivity": ranked_qc[0][0],
        "computed": at(),
    }


def qc_report(sel: list[dict]) -> dict:
    """Flag values and removals for the selected aircraft."""
    by_flag = {}
    for o in sel:
        ff = o["qc_flags"]
        q = decode_ff(ff)
        f = by_flag.setdefault(
            str(ff),
            {
                "records": 0,
                "decoded": q,
                "sfmr_removed": 0,
                "fl_wind_removed": 0,
                "positions_removed": 0,
            },
        )
        f["records"] += 1
        f["sfmr_removed"] += int(q["sfmr"] and o["sfmr_sfc_wind_kt"] is not None)
        f["fl_wind_removed"] += int(q["fl_wind"] and o["fl_wind_speed_kt"] is not None)
        f["positions_removed"] += int(
            q["position"] and o["lat"] is not None and o["lon"] is not None
        )
    return {
        "source": "NHC, High Density Observations (HDOB) Bulletin, https://www.nhc.noaa.gov/abouthdobs_2007.shtml (archive/references/abouthdobs_2007.shtml)",
        "records": len(sel),
        "missing_sfmr_null": sum(o["sfmr_sfc_wind_kt"] is None for o in sel),
        "missing_fl_wind_null": sum(o["fl_wind_speed_kt"] is None for o in sel),
        "missing_position_null": sum(o["lat"] is None or o["lon"] is None for o in sel),
        "by_flag": dict(sorted(by_flag.items())),
        "sfmr_removed_total": sum(f["sfmr_removed"] for f in by_flag.values()),
        "fl_wind_removed_total": sum(f["fl_wind_removed"] for f in by_flag.values()),
        "positions_removed_total": sum(
            f["positions_removed"] for f in by_flag.values()
        ),
        "computed": at(),
    }


def residuals(obs_resp: dict, pred_resp: dict) -> list[tuple[str, int, int, int]]:
    """(time, observed mm, predicted mm, residual mm) on exact timestamp matches."""
    pred = {
        p["t"]: int(Decimal(p["v"]) * 1000) for p in pred_resp["data"]["predictions"]
    }
    out = []
    for o in obs_resp["data"]["data"]:
        if o["v"] in ("", None) or o["t"] not in pred:
            continue
        ob = int(Decimal(o["v"]) * 1000)
        out.append((o["t"], ob, pred[o["t"]], ob - pred[o["t"]]))
    return out


def mm(x: int) -> str:
    """Integer millimetres as a metre string with 3 decimals."""
    return str(Decimal(x) / 1000)


def main() -> None:
    calls = part_a()
    track = best_track()
    obs = hdob_records(calls)

    # ---- aircraft (6.2)
    sel_info = select_aircraft(obs, track)
    dump(PACKAGE / "results" / "aircraft_selection.json", sel_info)
    ac = sel_info["selected"]
    sel = [o for o in obs if o["aircraft"] == ac]
    computed("aircraft_selected", ac, "call sign", sel_info["computed"], "rule 6.2")
    computed(
        "aircraft_sfmr_within_150km",
        sel_info["per_call_sign"][ac]["sfmr_within_150km"],
        "records",
        sel_info["computed"],
        "count, rule 6.2",
    )
    returned(
        "hdob_records_28sep_all_aircraft",
        len(obs),
        "records",
        "recon_get_hdobs",
        "R1+R2",
    )
    returned("hdob_records_selected", len(sel), "records", "recon_get_hdobs", "R1+R2")

    # ---- QC (7)
    qc = qc_report(sel)
    dump(PACKAGE / "results" / "hdob_qc.json", qc)
    for k in (
        "sfmr_removed_total",
        "fl_wind_removed_total",
        "positions_removed_total",
        "missing_sfmr_null",
        "missing_fl_wind_null",
    ):
        computed(
            f"qc_{k}", qc[k], "records", qc["computed"], "flag decoding, DESIGN.md 7"
        )

    # ---- panel (b)
    rows = []
    for o in sel:
        q = decode_ff(o["qc_flags"])
        c = centre_at(track, o["t"])
        d = (
            None
            if c is None or o["lat"] is None
            else round(haversine_km(c[0], c[1], o["lat"], o["lon"]), 2)
        )
        rows.append(
            {
                "time": o["t"].strftime("%Y-%m-%d %H:%M:%S"),
                "sfmr_kt": None if q["sfmr"] else o["sfmr_sfc_wind_kt"],
                "fl_wind_kt": None if q["fl_wind"] else o["fl_wind_speed_kt"],
                "distance_to_centre_km": d,
            }
        )
    span = (sel[0]["t"], sel[-1]["t"])
    landfall_in_b = span[0] <= LANDFALL_UTC <= span[1]
    sfmr_vals = [(r["sfmr_kt"], r["time"]) for r in rows if r["sfmr_kt"] is not None]
    fl_vals = [
        (r["fl_wind_kt"], r["time"]) for r in rows if r["fl_wind_kt"] is not None
    ]
    dists = [
        r["distance_to_centre_km"]
        for r in rows
        if r["distance_to_centre_km"] is not None
    ]
    # Best track for reference (AMENDMENTS.md A6): the 6-hourly records (00, 06, 12, 18 UTC)
    # from the last one at or before the first record to the first one at or after the last.
    six = [p for p in track if p["datetime"][9:13] in ("0000", "0600", "1200", "1800")]
    i0 = max(i for i, p in enumerate(six) if p["time"] <= span[0])
    i1 = min(i for i, p in enumerate(six) if p["time"] >= span[1])
    bt_ref = [
        {
            "time": p["time"].strftime("%Y-%m-%d %H:%M"),
            "max_wind_kt": p["max_wind"],
            "record": p["datetime"],
        }
        for p in six[i0 : i1 + 1]
    ]
    panel_b = {
        "aircraft": ac,
        "unit": "kt",
        "first_time": span[0].strftime("%Y-%m-%d %H:%M:%S"),
        "last_time": span[1].strftime("%Y-%m-%d %H:%M:%S"),
        "landfall_in_range": landfall_in_b,
        "best_track": bt_ref,
        "best_track_rule": "6-hourly best-track records (1-min maximum sustained wind) bracketing the flight; drawn as markers joined by straight lines in time, clipped at the axis edge",
        "rows": rows,
    }
    dump(PACKAGE / "results" / "panel_b.json", panel_b)
    returned(
        "aircraft_first_record", panel_b["first_time"], "UTC", "recon_get_hdobs", "R1"
    )
    returned(
        "aircraft_last_record", panel_b["last_time"], "UTC", "recon_get_hdobs", "R1"
    )
    smax = max(sfmr_vals)
    flmax = max(fl_vals)
    returned("sfmr_max_kt_after_qc", smax[0], "kt", "recon_get_hdobs", "R1")
    returned("sfmr_max_time", smax[1], "UTC", "recon_get_hdobs", "R1")
    returned("fl_wind_max_kt_after_qc", flmax[0], "kt", "recon_get_hdobs", "R1")
    returned("fl_wind_max_time", flmax[1], "UTC", "recon_get_hdobs", "R1")
    computed(
        "aircraft_min_distance_to_centre_km",
        min(dists),
        "km",
        at(),
        "haversine to interpolated centre",
    )
    for r in bt_ref:
        returned(
            f"best_track_{r['time'][11:13]}{r['time'][14:16]}_max_wind_kt",
            r["max_wind_kt"],
            "kt (1-min)",
            "nhc_get_best_track",
            "call 1",
            IAN,
        )

    # ---- panel (a)
    bt_shown = [
        {
            k: p[k]
            for k in (
                "datetime",
                "lat",
                "lon",
                "max_wind",
                "min_pressure",
                "status",
                "category",
            )
        }
        for p in track
        if BT_SHOWN[0] <= p["time"] <= BT_SHOWN[1]
    ]
    stations = {}
    for sid, (name, sc, _, _) in STATIONS.items():
        la, lo = station_latlon(ian_call_text(sc))
        stations[sid] = {
            "name": name,
            "lat": la,
            "lon": lo,
            "source": f"coops_get_station, {IAN} call {sc}",
        }
    blat, blon = station_latlon(text(calls["N1"]))
    flight = [
        {"time": o["t"].strftime("%H:%M:%S"), "lat": o["lat"], "lon": o["lon"]}
        for o in sel
        if o["lat"] is not None
        and o["lon"] is not None
        and not decode_ff(o["qc_flags"])["position"]
    ]
    panel_a = {
        "best_track": bt_shown,
        "tide_gauges": stations,
        "buoy": {
            "id": "42097",
            "lat": blat,
            "lon": blon,
            "source": f"ndbc_get_station, {ARCHIVE} N1",
        },
        "flight_track": {"aircraft": ac, "points": flight},
        "landfall": {
            "time_utc": LANDFALL_UTC.strftime("%Y-%m-%d %H:%M"),
            "lat": LANDFALL_LATLON[0],
            "lon": LANDFALL_LATLON[1],
            "source": "NHC TCR (revised 12 March 2026), verification/ian_cross_server/references.json",
        },
    }
    dump(PACKAGE / "results" / "panel_a.json", panel_a)
    returned("buoy_lat", blat, "deg", "ndbc_get_station", "N1")
    returned("buoy_lon", blon, "deg", "ndbc_get_station", "N1")

    # ---- panel (c)
    w = json.loads(text(calls["W1"]))
    win = [o for o in w["observations"] if PANEL_C[0] <= o["timestamp"] <= PANEL_C[1]]
    times = [parse_utc(o["timestamp"]) for o in win]
    steps = [(b - a).total_seconds() / 60 for a, b in zip(times, times[1:])]
    med = statistics.median(steps)
    gaps = [
        (win[i]["timestamp"], win[i + 1]["timestamp"], s)
        for i, s in enumerate(steps)
        if s > 1.5 * med
    ]
    implied_missing = sum(round(s / med) - 1 for _, _, s in gaps)
    wv = [o["WVHT"] for o in win]
    n = len(win)
    second = {v: sum(o.get(v) is not None for o in win) for v in ("WSPD", "PRES")}
    second_axis = next(
        (v for v in ("WSPD", "PRES") if n and second[v] / n >= 0.9), None
    )
    first_needed = win[0]["timestamp"] if win else None
    panel_c = {
        "station_id": "42097",
        "source": "ww3_get_buoy_history (ww3-mcp), NDBC annual file "
        + w["source"]["file"],
        "window": PANEL_C,
        "unit": w["units"].get("WVHT", "m"),
        "rows": [{"time": o["timestamp"], "wvht_m": o["WVHT"]} for o in win],
        "median_interval_min": med,
        "gaps": [{"after": a, "before": b, "minutes": s} for a, b, s in gaps],
        "second_axis": second_axis,
        "second_axis_nonnull": second,
        "file_first_returned": w["observations"][0]["timestamp"],
        "window_reached": w["observations"][0]["timestamp"] <= PANEL_C[0],
        "file_missing_counts_whole_year": w["missing_values"]["excluded_counts"],
        "computed": at(),
    }
    dump(PACKAGE / "results" / "panel_c.json", panel_c)
    returned(
        "buoy_rows_in_file", w["rows_in_file"], "rows", "ww3_get_buoy_history", "W1"
    )
    computed(
        "buoy_rows_in_window",
        n,
        "rows",
        panel_c["computed"],
        "rows with timestamp in window",
    )
    computed(
        "buoy_wvht_null_in_window",
        sum(v is None for v in wv),
        "rows",
        panel_c["computed"],
        "null WVHT (tool maps 9-codes to null)",
    )
    computed(
        "buoy_median_interval_min",
        med,
        "min",
        panel_c["computed"],
        "median spacing of window rows",
    )
    computed(
        "buoy_gaps", len(gaps), "gaps", panel_c["computed"], "spacing > 1.5 x median"
    )
    computed(
        "buoy_implied_missing_slots",
        implied_missing,
        "slots",
        panel_c["computed"],
        "sum(round(gap/median) - 1)",
    )
    valid = [(v, o["timestamp"]) for v, o in zip(wv, win) if v is not None]
    vmax = max(valid)
    returned("buoy_wvht_max_m", vmax[0], "m", "ww3_get_buoy_history", "W1")
    returned("buoy_wvht_max_time", vmax[1], "UTC", "ww3_get_buoy_history", "W1")
    computed("buoy_first_window_row", first_needed, "UTC", at(), "first row in window")

    # ---- panel (d)
    series = {}
    checks = {}
    for sid, (name, _, oc, pc) in STATIONS.items():
        r = residuals(json.loads(ian_call_text(oc)), json.loads(ian_call_text(pc)))
        series[sid] = {
            "name": name,
            "times": [t for t, *_ in r],
            "observed_m": [mm(o) for _, o, _, _ in r],
            "residual_m": [mm(x) for *_, x in r],
            "n_matched": len(r),
        }
        if sid == "8725520":
            rmax = max(x for *_, x in r)
            tmax = [t for t, *_, x in r if x == rmax]
            omax = max(o for _, o, _, _ in r)
            checks["fort_myers_residual_max_m"] = mm(rmax)
            checks["fort_myers_residual_max_first_time"] = tmax[0]
            checks["fort_myers_residual_max_ties"] = tmax
            checks["fort_myers_observed_max_m"] = mm(omax)
            computed(
                "fort_myers_residual_max_m",
                mm(rmax),
                "m",
                at(),
                "max(observed - predicted), integer mm",
            )
        else:
            rmin = min(x for *_, x in r)
            tmin = [t for t, *_, x in r if x == rmin]
            checks["st_petersburg_residual_min_m"] = mm(rmin)
            checks["st_petersburg_residual_min_time"] = tmin[0]
            computed(
                "st_petersburg_residual_min_m",
                mm(rmin),
                "m",
                at(),
                "min(observed - predicted), integer mm",
            )
    computed(
        "fort_myers_residual_max_time",
        checks["fort_myers_residual_max_ties"],
        "UTC",
        at(),
        "times of the maximum",
    )
    computed(
        "st_petersburg_residual_min_time",
        checks["st_petersburg_residual_min_time"],
        "UTC",
        at(),
        "time of the minimum",
    )
    returned(
        "fort_myers_observed_max_m",
        checks["fort_myers_observed_max_m"],
        "m MLLW",
        "coops_get_water_levels",
        "call 3",
        IAN,
    )
    mismatch = {k: (checks[k], v) for k, v in EXPECTED.items() if checks[k] != v}
    panel_d = {
        "datum": "MLLW",
        "unit": "m",
        "stations": series,
        "checks": checks,
        "expected": EXPECTED,
        "match": not mismatch,
    }
    dump(PACKAGE / "results" / "panel_d.json", panel_d)

    # ---- SFMR tools (R3, R4)
    logs = (PACKAGE / "archive" / "logs" / "part_a_recon-mcp.stderr.log").read_text()
    flat = re.sub(r"\s+", " ", logs)
    lines = re.findall(
        r"HTTP Request: GET .*? \S+:\d+ (https://www\.aoml\.noaa\.gov\S*(?: \S+)*?) \"HTTP/1\.1 (\d{3})",
        flat,
    )
    dump(
        PACKAGE / "results" / "sfmr_tools.json",
        {
            "recon_list_sfmr": {
                "is_error_flag": calls["R3"]["is_error"],
                "text": text(calls["R3"]),
            },
            "recon_get_sfmr": {
                "is_error_flag": calls["R4"]["is_error"],
                "text": text(calls["R4"]),
            },
            "aoml_requests_in_server_log": [
                {"url": re.sub(r"\s+", "", u), "status": s} for u, s in lines
            ],
        },
    )

    dump(PACKAGE / "results" / "part_a_numbers.json", NUMBERS)
    if mismatch:
        raise SystemExit(f"panel (d) differs from the published numbers: {mismatch}")
    print(
        f"aircraft {ac}; QC removed SFMR {qc['sfmr_removed_total']}, FL {qc['fl_wind_removed_total']}, positions {qc['positions_removed_total']}; panel (d) matches"
    )


if __name__ == "__main__":
    main()
