"""Analysis of the recorded two-server Ian session. Standard library only.

    python3 analyze.py [--record session_record.json] [--out results.json]

Reads the archived MCP responses in ``session_record.json`` and computes:

* input checks: record counts, the 6-minute time grid, missing values,
  quality level and data flags, datum, units, truncation;
* a value-by-value comparison with the earlier saved responses in
  ``examples/`` (the only other input; checked by SHA-256);
* non-tidal residuals, observed minus predicted, on exact timestamp matches,
  in decimal arithmetic so ties are exact;
* storm-centre geometry at the residual extremes: best-track position
  interpolated linearly in time (and linearly in latitude and longitude)
  between the bracketing fixes, great-circle distance (haversine, sphere of
  radius 6371.0088 km) and initial bearing from the storm centre to each
  gauge, plus the distance at each bracketing fix and a WGS84 ellipsoid
  (Vincenty inverse) cross-check;
* whether the best-track response has a record at the cited landfall time.

It does not import any Ocean-MCP package and makes no network request.
``replay_offline.py`` reruns it and compares the output with ``results.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

STATIONS = {"8725520": "Fort Myers", "8726520": "St. Petersburg"}
STORM_ID = "AL092022"
WINDOW_START = datetime(2022, 9, 27, 0, 0)
WINDOW_END = datetime(2022, 9, 29, 23, 54)  # end_date 2022-09-29 is inclusive
STEP = timedelta(minutes=6)

SAVED = {
    "water_levels": "examples/ian_coops_water_levels.json",
    "tide_predictions": "examples/ian_coops_tide_predictions.json",
    "best_track": "examples/ian_besttrack_AL092022.json",
}

EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius R1
WGS84_A = 6378137.0
WGS84_F = 1 / 298.257223563

# Cited, not retrieved through MCP: NHC Tropical Cyclone Report, Hurricane Ian
# (AL092022), Bucci, Alaka, Hagen, Delgado and Beven; original 2 April 2023,
# revised 12 March 2026. See references.json for checksum and page numbers.
LANDFALL_CITED = {
    "time_utc": "2022-09-28 19:05",
    "place": "Cayo Costa, Florida",
    "tcr_table1_row": {"lat": 26.7, "lon": -82.2, "min_pressure": 941, "max_wind": 130},
}
TCR_FORT_MYERS_PEAK_FT_ABOVE_MHHW = Decimal("7.26")
FT_PER_M = Decimal("1") / Decimal("0.3048")

# Values the manuscript states and this workflow must reproduce.
TARGETS = {
    "8725520": {
        "kind": "max",
        "value": "2.209",
        "times": ["2022-09-28 22:18", "2022-09-28 22:30"],
    },
    "8726520": {"kind": "min", "value": "-1.755", "times": ["2022-09-28 23:00"]},
}

# CO-OPS Data API response help (references.json): flag order by QC level.
FLAG_NAMES = {
    "v": ["I_inferred", "F_flat_tolerance", "R_rate_of_change", "T_expected_limit"],
    "p": [
        "O_outside_3sigma_count",
        "F_flat_tolerance",
        "R_rate_of_change",
        "L_expected_limit",
    ],
}


# --------------------------------------------------------------------------- helpers


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def find_call(record: dict, tool: str, station: str | None = None) -> dict:
    """The single recorded call for a tool (and station)."""
    hits = [
        c
        for c in record["calls"]
        if c["tool"] == tool
        and (station is None or c["arguments"].get("station_id") == station)
    ]
    if len(hits) != 1:
        raise ValueError(f"expected one {tool} call for {station}, found {len(hits)}")
    return hits[0]


def call_text(call: dict) -> str:
    """The text payload of a recorded CallToolResult."""
    (text,) = [c["text"] for c in call["result"]["content"] if c["type"] == "text"]
    return text


def parse_t(t: str) -> datetime:
    """CO-OPS 'YYYY-MM-DD HH:MM' timestamp."""
    return datetime.strptime(t, "%Y-%m-%d %H:%M")


def parse_bt(t: str) -> datetime:
    """nhc-mcp best-track 'YYYYMMDD HHMM UTC' timestamp."""
    return datetime.strptime(t, "%Y%m%d %H%M UTC")


def fmt(dt: datetime) -> str:
    """Timestamp in the CO-OPS style."""
    return dt.strftime("%Y-%m-%d %H:%M")


def dec(v: str) -> Decimal | None:
    """Decimal from a CO-OPS value string, None if empty."""
    v = (v or "").strip()
    return Decimal(v) if v else None


def deep_diff(a, b, path: str = "") -> list[dict]:
    """Every leaf where two JSON values differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                out.append({"path": p, "saved": "<absent>", "new": b[k]})
            elif k not in b:
                out.append({"path": p, "saved": a[k], "new": "<absent>"})
            else:
                out.extend(deep_diff(a[k], b[k], p))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [{"path": f"{path}.length", "saved": len(a), "new": len(b)}]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(deep_diff(x, y, f"{path}[{i}]"))
        return out
    return (
        [] if a == b and type(a) is type(b) else [{"path": path, "saved": a, "new": b}]
    )


# --------------------------------------------------------------------------- geodesy


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance on a sphere of radius EARTH_RADIUS_KM."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, degrees clockwise from true north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def vincenty_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Geodesic distance on the WGS84 ellipsoid (Vincenty 1975 inverse)."""
    a, f = WGS84_A, WGS84_F
    b = a * (1 - f)
    u1 = math.atan((1 - f) * math.tan(math.radians(lat1)))
    u2 = math.atan((1 - f) * math.tan(math.radians(lat2)))
    big_l = math.radians(lon2 - lon1)
    lam = big_l
    su1, cu1, su2, cu2 = math.sin(u1), math.cos(u1), math.sin(u2), math.cos(u2)
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cu2 * sl, cu1 * su2 - su1 * cu2 * cl)
        cs = su1 * su2 + cu1 * cu2 * cl
        sigma = math.atan2(ss, cs)
        sa = cu1 * cu2 * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * su1 * su2 / c2a
        c = f / 16 * c2a * (4 + f * (4 - 3 * c2a))
        lam_prev = lam
        lam = big_l + (1 - c) * f * sa * (
            sigma + c * ss * (c2sm + c * cs * (-1 + 2 * c2sm**2))
        )
        if abs(lam - lam_prev) < 1e-12:
            break
    else:
        raise RuntimeError("Vincenty did not converge")
    u_sq = c2a * (a * a - b * b) / (b * b)
    big_a = 1 + u_sq / 16384 * (4096 + u_sq * (-768 + u_sq * (320 - 175 * u_sq)))
    big_b = u_sq / 1024 * (256 + u_sq * (-128 + u_sq * (74 - 47 * u_sq)))
    ds = (
        big_b
        * ss
        * (
            c2sm
            + big_b
            / 4
            * (
                cs * (-1 + 2 * c2sm**2)
                - big_b / 6 * c2sm * (-3 + 4 * ss**2) * (-3 + 4 * c2sm**2)
            )
        )
    )
    return b * big_a * (sigma - ds) / 1000.0


# --------------------------------------------------------------------------- parsing


def parse_station_markdown(text: str) -> dict:
    """Fields of the coops_get_station markdown response."""

    def field(label: str) -> str | None:
        m = re.search(rf"^\*\*{re.escape(label)}\*\*: (.+)$", text, re.M)
        return m.group(1).strip() if m else None

    datums = {
        m.group(1): m.group(2)
        for m in re.finditer(r"^- \*\*([A-Z0-9]+)\*\*: (-?[0-9.]+) metric$", text, re.M)
    }
    details = {
        m.group(1): m.group(2).strip()
        for m in re.finditer(r"^- \*\*([a-z]+)\*\*: (.+)$", text, re.M)
        if m.group(1)
        in ("accepted", "epoch", "origyear", "meridian", "datum", "timezonecorr")
    }
    return {
        "name": field("Name"),
        "state": field("State"),
        "latitude": field("Latitude"),
        "longitude": field("Longitude"),
        "affiliations": field("Affiliations"),
        "details": details,
        "datums_metric_above_STND": datums,
        "tidal_epoch_in_response": "epoch" in details,
    }


def grid_check(times: list[str]) -> dict:
    """Compare a timestamp list with the expected 6-minute grid of the window."""
    expected = []
    t = WINDOW_START
    while t <= WINDOW_END:
        expected.append(fmt(t))
        t += STEP
    got = set(times)
    return {
        "expected_slots": len(expected),
        "records": len(times),
        "unique_times": len(got),
        "duplicates": len(times) - len(got),
        "missing_slots": [s for s in expected if s not in got],
        "unexpected_times": sorted(got - set(expected)),
        "first": times[0] if times else None,
        "last": times[-1] if times else None,
        "sorted": times == sorted(times),
    }


def check_observations(doc: dict) -> dict:
    """Counts, grid, missing values, quality level and flags of a water-level response."""
    recs = doc["data"]["data"]
    q_counts: dict[str, int] = {}
    flag_counts: dict[str, dict[str, int]] = {}
    nonzero = []
    for r in recs:
        q = r.get("q", "")
        q_counts[q] = q_counts.get(q, 0) + 1
        parts = [int(x) for x in r.get("f", "").split(",")] if r.get("f") else []
        names = FLAG_NAMES.get(q, [f"flag{i}" for i in range(len(parts))])
        per = flag_counts.setdefault(q, {n: 0 for n in names})
        for n, v in zip(names, parts):
            if v:
                per[n] += 1
        if any(parts):
            nonzero.append({"t": r["t"], "v": r["v"], "f": r["f"], "q": q})
    values = [dec(r["v"]) for r in recs]
    present = [v for v in values if v is not None]
    vmax, vmin = max(present), min(present)
    return {
        "request_params": doc["request_params"],
        "datum": doc["request_params"]["datum"],
        "units": doc["request_params"]["units"],
        "time_zone": doc["request_params"]["time_zone"],
        "interval": doc["request_params"]["interval"],
        "record_count": doc["record_count"],
        "total_count": doc["total_count"],
        "truncated": doc["truncated"],
        "metadata": doc["data"]["metadata"],
        "grid": grid_check([r["t"] for r in recs]),
        "missing_values": sum(v is None for v in values),
        "quality_level_counts": q_counts,
        "records_with_nonzero_flag_by_level": flag_counts,
        "records_with_any_nonzero_flag": len(nonzero),
        "nonzero_flag_records": nonzero,
        "observed_max_m": str(vmax),
        "observed_max_times": [r["t"] for r, v in zip(recs, values) if v == vmax],
        "observed_min_m": str(vmin),
        "observed_min_times": [r["t"] for r, v in zip(recs, values) if v == vmin],
    }


def check_predictions(doc: dict) -> dict:
    """Counts, grid and missing values of a tide-prediction response."""
    recs = doc["data"]["predictions"]
    values = [dec(r["v"]) for r in recs]
    return {
        "request_params": doc["request_params"],
        "datum": doc["request_params"]["datum"],
        "units": doc["request_params"]["units"],
        "time_zone": doc["request_params"]["time_zone"],
        "interval": doc["request_params"]["interval"],
        "record_count": doc["record_count"],
        "total_count": doc["total_count"],
        "truncated": doc["truncated"],
        "grid": grid_check([r["t"] for r in recs]),
        "missing_values": sum(v is None for v in values),
        "record_fields": sorted({k for r in recs for k in r}),
    }


# --------------------------------------------------------------------------- analysis


def residuals(obs_doc: dict, pred_doc: dict) -> dict:
    """Observed minus predicted on exact timestamp matches, with all ties at the extremes."""
    obs = {r["t"]: dec(r["v"]) for r in obs_doc["data"]["data"]}
    pred = {r["t"]: dec(r["v"]) for r in pred_doc["data"]["predictions"]}
    common = sorted(
        t for t in set(obs) & set(pred) if obs[t] is not None and pred[t] is not None
    )
    res = {t: obs[t] - pred[t] for t in common}
    rmax, rmin = max(res.values()), min(res.values())

    def at(times: list[str]) -> list[dict]:
        return [
            {
                "t": t,
                "observed_m": str(obs[t]),
                "predicted_m": str(pred[t]),
                "residual_m": str(res[t]),
            }
            for t in times
        ]

    max_times = [t for t in common if res[t] == rmax]
    min_times = [t for t in common if res[t] == rmin]
    return {
        "method": "residual = observed - predicted, exact match on the CO-OPS timestamp string, decimal arithmetic, no interpolation",
        "observed_records": len(obs),
        "predicted_records": len(pred),
        "matched_pairs": len(common),
        "observed_unmatched": sorted(set(obs) - set(common)),
        "predicted_unmatched": sorted(set(pred) - set(common)),
        "max_residual_m": str(rmax),
        "max_times": max_times,
        "max_tie_count": len(max_times),
        "at_max": at(max_times),
        "min_residual_m": str(rmin),
        "min_times": min_times,
        "min_tie_count": len(min_times),
        "at_min": at(min_times),
        "series": [[t, str(res[t])] for t in common],
    }


def track_fixes(bt_doc: dict) -> list[dict]:
    """Best-track fixes with parsed times, sorted."""
    fixes = [{**p, "dt": parse_bt(p["datetime"])} for p in bt_doc["track_points"]]
    return sorted(fixes, key=lambda p: p["dt"])


def position_at(fixes: list[dict], when: datetime) -> dict:
    """Storm centre at ``when``: the fix itself, or linear interpolation between the bracketing fixes."""
    for f in fixes:
        if f["dt"] == when:
            return {
                "lat": f["lat"],
                "lon": f["lon"],
                "method": "exact fix",
                "fix_before": f,
                "fix_after": f,
                "fraction": 0.0,
            }
    before = [f for f in fixes if f["dt"] < when]
    after = [f for f in fixes if f["dt"] > when]
    if not before or not after:
        raise ValueError(f"{when} is outside the best track")
    f0, f1 = before[-1], after[0]
    frac = (when - f0["dt"]) / (f1["dt"] - f0["dt"])
    return {
        "lat": f0["lat"] + frac * (f1["lat"] - f0["lat"]),
        "lon": f0["lon"] + frac * (f1["lon"] - f0["lon"]),
        "method": "linear in time, latitude and longitude between bracketing fixes",
        "fix_before": f0,
        "fix_after": f1,
        "fraction": frac,
    }


def link(lat: float, lon: float, gauge: dict) -> dict:
    """Distance and bearing from a storm-centre position to a gauge."""
    d = haversine_km(lat, lon, gauge["lat"], gauge["lon"])
    v = vincenty_km(lat, lon, gauge["lat"], gauge["lon"])
    return {
        "distance_km": round(d, 3),
        "bearing_from_storm_deg": round(
            initial_bearing_deg(lat, lon, gauge["lat"], gauge["lon"]), 2
        ),
        "distance_wgs84_km": round(v, 3),
        "wgs84_minus_sphere_km": round(v - d, 3),
    }


def fix_summary(f: dict) -> dict:
    """A best-track fix without the parsed datetime."""
    return {k: v for k, v in f.items() if k != "dt"}


def geometry(fixes: list[dict], gauges: dict, events: list[dict]) -> dict:
    """Storm-centre geometry at each residual-extreme time."""
    rows = []
    for ev in events:
        when = parse_t(ev["t"])
        pos = position_at(fixes, when)
        rows.append(
            {
                "event": ev["event"],
                "t": ev["t"],
                "minutes_after_cited_landfall": int(
                    (when - parse_t(LANDFALL_CITED["time_utc"])).total_seconds() // 60
                ),
                "storm_centre": {
                    "lat": round(pos["lat"], 5),
                    "lon": round(pos["lon"], 5),
                    "method": pos["method"],
                },
                "interpolation_fraction": round(pos["fraction"], 6),
                "fix_before": fix_summary(pos["fix_before"]),
                "fix_after": fix_summary(pos["fix_after"]),
                "to_gauge": {
                    sid: link(pos["lat"], pos["lon"], g) for sid, g in gauges.items()
                },
                "to_gauge_at_fix_before": {
                    sid: link(pos["fix_before"]["lat"], pos["fix_before"]["lon"], g)
                    for sid, g in gauges.items()
                },
                "to_gauge_at_fix_after": {
                    sid: link(pos["fix_after"]["lat"], pos["fix_after"]["lon"], g)
                    for sid, g in gauges.items()
                },
            }
        )
    return {
        "position_method": "linear interpolation in time between the bracketing best-track fixes; latitude and longitude interpolated linearly in degrees",
        "distance_method": f"haversine great-circle distance on a sphere of radius {EARTH_RADIUS_KM} km (IUGG mean radius); WGS84 ellipsoidal distance (Vincenty inverse) as a cross-check",
        "bearing_method": "initial great-circle bearing from the storm centre to the gauge, degrees clockwise from true north",
        "best_track_precision": "best-track positions are given to 0.1 degree (about 11 km in latitude)",
        "gauges": gauges,
        "events": rows,
    }


def landfall_check(bt_doc: dict) -> dict:
    """Whether the best-track response has a record at the cited landfall time, and what it says."""
    key = parse_t(LANDFALL_CITED["time_utc"]).strftime("%Y%m%d %H%M UTC")
    hits = [p for p in bt_doc["track_points"] if p["datetime"] == key]
    all_keys = sorted({k for p in bt_doc["track_points"] for k in p})
    mentions = [
        p["datetime"]
        for p in bt_doc["track_points"]
        if "landfall" in json.dumps(p).lower()
    ]
    non_synoptic = [
        p["datetime"]
        for p in bt_doc["track_points"]
        if p["datetime"][9:13] not in ("0000", "0600", "1200", "1800")
    ]
    row = LANDFALL_CITED["tcr_table1_row"]
    rec = hits[0] if hits else None
    return {
        "cited": LANDFALL_CITED,
        "record_at_cited_time_present": bool(hits),
        "record": rec,
        "record_fields": sorted(rec) if rec else None,
        "fields_in_any_record": all_keys,
        "response_top_level_keys": sorted(bt_doc),
        "status_values_in_response": sorted(
            {p["status"] for p in bt_doc["track_points"]}
        ),
        "records_mentioning_landfall": mentions,
        "has_record_identifier_field": any(
            k in all_keys for k in ("record_id", "identifier", "record_identifier")
        ),
        "non_synoptic_record_times": non_synoptic,
        "record_matches_tcr_table1_row": bool(rec)
        and all(rec[k] == row[k] for k in ("lat", "lon", "min_pressure", "max_wind")),
        "labelled_landfall_by_tool": bool(mentions),
    }


def compare_saved(saved: dict, new: dict) -> dict:
    """Value-by-value comparison of one saved response with the new one."""
    diffs = deep_diff(saved, new)
    expected = [d for d in diffs if d["path"].endswith("retrieved_at")]
    other = [d for d in diffs if not d["path"].endswith("retrieved_at")]
    return {
        "differences_total": len(diffs),
        "retrieved_at_differences": expected,
        "other_differences": other,
        "identical_apart_from_retrieved_at": not other,
    }


def compute(record: dict, repo: Path = REPO) -> dict:
    """Everything in results.json, from the session record and the saved examples."""
    bt_doc = json.loads(call_text(find_call(record, "nhc_get_best_track")))
    stations, obs_docs, pred_docs = {}, {}, {}
    for sid in STATIONS:
        stations[sid] = parse_station_markdown(
            call_text(find_call(record, "coops_get_station", sid))
        )
        obs_docs[sid] = json.loads(
            call_text(find_call(record, "coops_get_water_levels", sid))
        )
        pred_docs[sid] = json.loads(
            call_text(find_call(record, "coops_get_tide_predictions", sid))
        )

    # Saved earlier responses.
    saved_bytes = {k: (repo / p).read_bytes() for k, p in SAVED.items()}
    saved = {k: json.loads(b) for k, b in saved_bytes.items()}
    comparison = {
        "files": {
            k: {"path": SAVED[k], "sha256": sha256_bytes(b)}
            for k, b in saved_bytes.items()
        },
        "best_track": compare_saved(saved["best_track"], bt_doc),
    }
    for sid in STATIONS:
        comparison[f"water_levels_{sid}"] = compare_saved(
            saved["water_levels"][sid], obs_docs[sid]
        )
        comparison[f"tide_predictions_{sid}"] = compare_saved(
            saved["tide_predictions"][sid], pred_docs[sid]
        )

    # Gauge coordinates from coops_get_station; cross-checked against the observation envelope.
    gauges = {}
    for sid, st in stations.items():
        lat, lon = float(st["latitude"]), float(st["longitude"])
        env = obs_docs[sid]["data"]["metadata"]
        gauges[sid] = {
            "name": st["name"],
            "lat": lat,
            "lon": lon,
            "source": "coops_get_station",
            "observation_metadata_lat_lon": [env["lat"], env["lon"]],
            "offset_from_observation_metadata_m": round(
                haversine_km(lat, lon, float(env["lat"]), float(env["lon"])) * 1000, 1
            ),
        }

    res = {sid: residuals(obs_docs[sid], pred_docs[sid]) for sid in STATIONS}
    fm, sp = res["8725520"], res["8726520"]
    events = [{"event": "Fort Myers residual maximum", "t": t} for t in fm["max_times"]]
    events += [
        {"event": "St. Petersburg residual minimum", "t": t} for t in sp["min_times"]
    ]
    fixes = track_fixes(bt_doc)

    targets = {}
    for sid, tgt in TARGETS.items():
        r = res[sid]
        val, times = (
            (r["max_residual_m"], r["max_times"])
            if tgt["kind"] == "max"
            else (r["min_residual_m"], r["min_times"])
        )
        targets[sid] = {
            **tgt,
            "obtained_value": val,
            "obtained_times": times,
            "reproduced": Decimal(val) == Decimal(tgt["value"])
            and times == tgt["times"],
        }

    # Extra consistency check against the TCR (not part of the residual pipeline).
    fm_obs = check_observations(obs_docs["8725520"])
    dat = stations["8725520"]["datums_metric_above_STND"]
    above_mhhw_m = Decimal(fm_obs["observed_max_m"]) - (
        Decimal(dat["MHHW"]) - Decimal(dat["MLLW"])
    )
    above_mhhw_ft = (above_mhhw_m * FT_PER_M).quantize(Decimal("0.01"))

    first_fm, first_sp = parse_t(fm["max_times"][0]), parse_t(sp["min_times"][0])
    return {
        "generated_by": "analyze.py",
        "session_record_sha256": None,  # filled in by main()
        "session_window_utc": [
            record["session_started_at"],
            record["session_finished_at"],
        ],
        "package_versions": {
            k: v["version"] for k, v in record["packages"]["servers"].items()
        },
        "mcp_sdk_version": record["client"]["mcp_sdk_version"],
        "server_processes": record["server_processes_before_first_call"],
        "server_processes_unchanged_through_session": record[
            "server_processes_before_first_call"
        ]
        == record["server_processes_after_last_call"],
        "calls": [
            {
                k: c[k]
                for k in (
                    "seq",
                    "server",
                    "tool",
                    "arguments",
                    "started_at",
                    "elapsed_s",
                    "text_sha256",
                    "result_sha256",
                )
            }
            for c in record["calls"]
        ],
        "station_metadata": stations,
        "input_verification": {
            "observations": {sid: check_observations(d) for sid, d in obs_docs.items()},
            "predictions": {sid: check_predictions(d) for sid, d in pred_docs.items()},
            "best_track": {
                "storm_id": bt_doc["storm_id"],
                "source": bt_doc["source"],
                "count": bt_doc["count"],
                "track_points": len(bt_doc["track_points"]),
                "first": bt_doc["track_points"][0]["datetime"],
                "last": bt_doc["track_points"][-1]["datetime"],
            },
            "comparison_with_saved": comparison,
        },
        "residuals": res,
        "targets": targets,
        "all_targets_reproduced": all(t["reproduced"] for t in targets.values()),
        "timing": {
            "fort_myers_max_first_minus_cited_landfall_min": int(
                (first_fm - parse_t(LANDFALL_CITED["time_utc"])).total_seconds() // 60
            ),
            "st_petersburg_min_minus_cited_landfall_min": int(
                (first_sp - parse_t(LANDFALL_CITED["time_utc"])).total_seconds() // 60
            ),
            "st_petersburg_min_minus_fort_myers_max_first_min": int(
                (first_sp - first_fm).total_seconds() // 60
            ),
        },
        "geometry": geometry(fixes, gauges, events),
        "landfall": landfall_check(bt_doc),
        "extra_check_fort_myers_peak_vs_tcr": {
            "observed_max_m_mllw": fm_obs["observed_max_m"],
            "observed_max_times": fm_obs["observed_max_times"],
            "mhhw_minus_mllw_m": str(Decimal(dat["MHHW"]) - Decimal(dat["MLLW"])),
            "observed_max_above_mhhw_m": str(above_mhhw_m),
            "observed_max_above_mhhw_ft": str(above_mhhw_ft),
            "tcr_value_ft_above_mhhw": str(TCR_FORT_MYERS_PEAK_FT_ABOVE_MHHW),
            "agrees_to_0_01_ft": above_mhhw_ft == TCR_FORT_MYERS_PEAK_FT_ABOVE_MHHW,
            "datum_source": "coops_get_station expand=datums (MHHW, MLLW above station datum)",
        },
    }


def geometry_table(results: dict) -> str:
    """Markdown table of the storm-centre geometry."""
    g = results["geometry"]
    sids = list(g["gauges"])
    names = {sid: g["gauges"][sid]["name"] for sid in sids}
    values = {}
    for sid, r in results["residuals"].items():
        for row in r["at_max"] + r["at_min"]:
            values[(sid, row["t"])] = row["residual_m"]

    def when(dt: datetime) -> str:
        return dt.strftime("%d %b %H:%M")

    def cell(link_: dict) -> str:
        return f"{link_['distance_km']:.1f} km, {link_['bearing_from_storm_deg']:.0f}°"

    head = (
        "| Time (UTC) | Event | Storm centre (°N, °W) | "
        + " | ".join(f"{names[s]} ({s})" for s in sids)
        + " |"
    )
    sep = "|---|---|---|" + "---|" * len(sids)
    lines = [head, sep]
    seen_fixes = {}
    for ev in g["events"]:
        c = ev["storm_centre"]
        sid = next(s for s in sids if ev["event"].startswith(names[s]))
        label = f"{ev['event']}, {Decimal(values[(sid, ev['t'])]):+} m"
        lines.append(
            f"| {when(parse_t(ev['t']))} | {label} | {c['lat']:.3f}, {-c['lon']:.3f} (interpolated) | "
            + " | ".join(cell(ev["to_gauge"][s]) for s in sids)
            + " |"
        )
        for side in ("fix_before", "fix_after"):
            f = ev[side]
            seen_fixes[f["datetime"]] = (f, ev[f"to_gauge_at_{side}"])
    for dt in sorted(seen_fixes):
        f, links = seen_fixes[dt]
        lines.append(
            f"| {when(parse_bt(dt))} | Best-track fix (brackets the events) | {f['lat']:.1f}, {-f['lon']:.1f} | "
            + " | ".join(cell(links[s]) for s in sids)
            + " |"
        )
    bracket = " and ".join(parse_bt(dt).strftime("%H:%M") for dt in sorted(seen_fixes))
    lines.append("")
    lines.append(
        f"Distance: haversine great circle, sphere of radius {EARTH_RADIUS_KM} km. Bearing: initial bearing from "
        "the storm centre to the gauge, degrees clockwise from true north. Storm centre at event times: linear "
        f"interpolation in time between the bracketing best-track fixes ({bracket} UTC). Best-track positions "
        "are given to 0.1°."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write results.json and geometry_table.md."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", default=str(HERE / "session_record.json"))
    ap.add_argument("--out", default=str(HERE / "results.json"))
    ap.add_argument("--table", default=str(HERE / "geometry_table.md"))
    args = ap.parse_args()
    raw = Path(args.record).read_bytes()
    results = compute(json.loads(raw))
    results["session_record_sha256"] = sha256_bytes(raw)
    Path(args.out).write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    Path(args.table).write_text(geometry_table(results))
    for sid, t in results["targets"].items():
        print(
            f"{sid}: {t['kind']} {t['obtained_value']} m at {t['obtained_times']}  reproduced={t['reproduced']}"
        )
    print(geometry_table(results))


if __name__ == "__main__":
    main()
