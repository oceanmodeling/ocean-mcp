"""Buoy selection for panel (c), recomputed offline (DESIGN.md 6.1, AMENDMENTS.md A1).

Inputs, all archived:
  * the best track: verification/ian_cross_server/session_record.json, call 1
    (read in place, checksum verified);
  * archive/phase0_selection/ndbc_nearest_{1,2,3}.json: ndbc_find_nearest_stations
    around three track points (Phase 0, 2026-11-21);
  * archive/phase0_selection/ww3_history_{upper,lower}/<id>.json.gz:
    ww3_get_buoy_history(<id>, 2022, 5000, json) for every candidate (upper-case
    IDs first; IDs with letters that got HTTP 404 were repeated in lower case).

Counts only: no WVHT value is used, only whether it is null.

    python3 -I scripts/select_buoy.py      -> results/buoy_selection.json
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    LANDFALL_UTC,
    PACKAGE,
    best_track,
    dump,
    haversine_km,
    parse_utc,
    sample_track,
)

SEL = PACKAGE / "archive" / "phase0_selection"
CANDIDATE_RADIUS_KM = 300.0
WINDOW = ("2022-09-27 00:00", "2022-09-30 00:00")  # panel (c), both ends included


def candidates() -> dict:
    """Stations returned by the three ndbc_find_nearest_stations calls."""
    out = {}
    for i in (1, 2, 3):
        rec = json.loads((SEL / f"ndbc_nearest_{i}.json").read_text())
        fc = json.loads(rec["result"]["content"][0]["text"])
        for f in fc["features"]:
            p = f["properties"]
            lon, lat = f["geometry"]["coordinates"]
            out[p["id"]] = {
                "id": p["id"],
                "name": p["name"],
                "type": p["type"],
                "lat": lat,
                "lon": lon,
            }
    return out


def history(sid: str) -> tuple[str, dict | str]:
    """The archived ww3_get_buoy_history text for a station (lower case if repeated)."""
    lower = SEL / "ww3_history_lower" / f"{sid.lower()}.json.gz"
    upper = SEL / "ww3_history_upper" / f"{sid}.json.gz"
    path = lower if lower.exists() else upper
    rec = json.load(gzip.open(path, "rt"))
    text = rec["result"]["content"][0]["text"]
    try:
        return str(path.relative_to(PACKAGE)), json.loads(text)
    except json.JSONDecodeError:
        return str(path.relative_to(PACKAGE)), text


def main() -> None:
    track = best_track()
    full = sample_track(
        track, parse_utc("2022-09-27 00:00"), parse_utc("2022-09-30 00:00")
    )
    to_landfall = sample_track(track, parse_utc("2022-09-27 00:00"), LANDFALL_UTC)
    rows = []
    for sid, st in candidates().items():
        d_full = min(haversine_km(la, lo, st["lat"], st["lon"]) for _, la, lo in full)
        if d_full > CANDIDATE_RADIUS_KM:
            continue
        d_lf, t_lf = min(
            (haversine_km(la, lo, st["lat"], st["lon"]), t) for t, la, lo in to_landfall
        )
        src, h = history(sid)
        row = {
            **st,
            "min_dist_window_km": round(d_full, 1),
            "closest_approach_to_landfall_km": round(d_lf, 1),
            "closest_approach_time": t_lf.strftime("%Y-%m-%d %H:%M"),
            "history_response": src,
        }
        if isinstance(h, str):
            row["status"] = (
                "no 2022 file (HTTP 404)" if "HTTP 404" in h else "text: " + h[:80]
            )
        else:
            obs = h["observations"]
            first = obs[0]["timestamp"] if obs else None
            win = [o for o in obs if WINDOW[0] <= o["timestamp"] <= WINDOW[1]]
            reach = first is not None and first <= WINDOW[0]
            row.update(
                status="window reached" if reach else "window not reached",
                rows_in_file=h["rows_in_file"],
                first_returned=first,
                rows_in_window=len(win),
                wvht_valid=sum(o.get("WVHT") is not None for o in win),
                wspd_valid=sum(o.get("WSPD") is not None for o in win),
                pres_valid=sum(o.get("PRES") is not None for o in win),
            )
        rows.append(row)
    eligible = [
        r for r in rows if r["status"] == "window reached" and r["wvht_valid"] > 0
    ]
    eligible.sort(
        key=lambda r: (r["closest_approach_to_landfall_km"], -r["wvht_valid"], r["id"])
    )
    result = {
        "rule": (
            "Among candidates within 300 km of the best track (27 Sep 00:00-30 Sep 00:00 UTC) "
            "whose 2022 file reaches the panel window and has >=1 non-null WVHT in it: the "
            "smallest closest approach to the best track between 27 Sep 00:00 and landfall "
            "(28 Sep 19:05 UTC); ties by the larger non-null WVHT count in the window."
        ),
        "window": WINDOW,
        "landfall_utc": LANDFALL_UTC.strftime("%Y-%m-%d %H:%M"),
        "n_candidates_within_300km": len(rows),
        "eligible_ranked": [
            {
                k: r[k]
                for k in (
                    "id",
                    "name",
                    "closest_approach_to_landfall_km",
                    "closest_approach_time",
                    "wvht_valid",
                )
            }
            for r in eligible
        ],
        "selected": eligible[0]["id"] if eligible else None,
        "tie_at_top": len(eligible) > 1
        and eligible[0]["closest_approach_to_landfall_km"]
        == eligible[1]["closest_approach_to_landfall_km"],
        "candidates": sorted(rows, key=lambda r: r["min_dist_window_km"]),
    }
    dump(PACKAGE / "results" / "buoy_selection.json", result)
    top = eligible[0]
    print(
        f"selected {top['id']} ({top['name']}): {top['closest_approach_to_landfall_km']} km at "
        f"{top['closest_approach_time']} UTC; {top['wvht_valid']} non-null WVHT; "
        f"{len(rows)} candidates, {len(eligible)} eligible"
    )


if __name__ == "__main__":
    main()
