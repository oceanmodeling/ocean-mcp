"""Part B, session 1 (live): B1 first part, B2, B3, B4, as fixed in DESIGN.md.

One client process, six MCP stdio sessions (ndbc-mcp, ww3-mcp, ofs-mcp,
coops-mcp, vdatum-mcp, rtofs-mcp). Writes archive/session1_record.json and
archive/logs/session1_<server>.stderr.log. Prints status lines only.

    <env>/bin/python scripts/record_session1.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO_ROOT = HERE.parents[2]  # scripts/ -> breadth_examples/ -> verification/ -> root
sys.path.insert(0, str(HERE))
from mcp_recorder import Recorder  # noqa: E402

IAN_SESSION = REPO_ROOT / "verification" / "ian_cross_server" / "session_record.json"
IAN_SESSION_SHA256 = "cc8b52830f23ca98be0ea932e196accc2775490cb6c55542608f9f6ee4fcf1bd"

B1_BUOYS = ["44097", "44025", "41002"]
B2_PAIRS = [("8574680", "cbofs"), ("8545240", "dbofs"), ("8771450", "ngofs2")]
B3_LAT, B3_LON, B3_Z = "26.647778", "-81.87111", "2.613"
B4_LINE = {"lat_start": 35.55, "lon_start": -75.25, "lat_end": 33.95, "lon_end": -73.30}
B4_N = 20


def as_json(text: str):
    """Parse JSON or return None."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def station_position(markdown: str) -> tuple[float, float] | None:
    """Latitude and longitude from ndbc_get_station's markdown."""
    la = re.search(r"\*\*Latitude\*\*:\s*(-?\d+(?:\.\d+)?)", markdown)
    lo = re.search(r"\*\*Longitude\*\*:\s*(-?\d+(?:\.\d+)?)", markdown)
    return (float(la.group(1)), float(lo.group(1))) if la and lo else None


async def b1(rec: Recorder) -> None:
    """GFS-Wave forecast and the tool's own comparison for the first buoy with data."""
    for sid in B1_BUOYS:
        pos = station_position(
            await rec.call("S1.1", "ndbc-mcp", "ndbc_get_station", {"station_id": sid})
        )
        if pos is None:
            rec.note(f"B1: {sid} has no position in ndbc_get_station; next buoy")
            continue
        lat, lon = pos
        cmp_text = await rec.call(
            "S1.2",
            "ww3-mcp",
            "ww3_compare_forecast_with_buoy",
            {
                "station_id": sid,
                "buoy_lat": lat,
                "buoy_lon": lon,
                "grid": "global.0p25",
                "hours_to_compare": 24,
                "response_format": "json",
            },
        )
        cmp = as_json(cmp_text)
        if not cmp or cmp.get("observation_window", {}).get("rows_with_wvht", 0) < 1:
            rec.note(f"B1: {sid} comparison has no WVHT rows; next buoy")
            continue
        fc_args = {
            "latitude": lat,
            "longitude": lon,
            "grid": "global.0p25",
            "variables": ["HTSGW"],
            "max_hours": 72,
            "step_hours": 3,
            "response_format": "json",
        }
        fc = as_json(
            await rec.call("S1.3", "ww3-mcp", "ww3_get_forecast_at_point", fc_args)
        )
        if not fc or fc.get("n_points") != 25:
            rec.note(
                "B1: forecast has fewer than 25 valid times; repeating once after 30 min",
                n_points=(fc or {}).get("n_points"),
            )
            await asyncio.sleep(1800)
            fc = as_json(
                await rec.call("S1.3r", "ww3-mcp", "ww3_get_forecast_at_point", fc_args)
            )
        if fc and cmp.get("cycle") != fc.get("cycle"):
            rec.note(
                "B1: comparison and forecast report different cycles",
                compare_cycle=cmp.get("cycle"),
                forecast_cycle=fc.get("cycle"),
            )
        rec.note(f"B1: buoy {sid} selected", station_id=sid, lat=lat, lon=lon)
        return
    rec.note("B1: no buoy in the order has data")


async def b2(rec: Recorder) -> None:
    """OFS model against a CO-OPS gauge, first pair with data."""
    for sid, model in B2_PAIRS:
        text = await rec.call(
            "C1",
            "ofs-mcp",
            "ofs_compare_with_coops",
            {
                "station_id": sid,
                "model": model,
                "hours_to_compare": 24,
                "response_format": "json",
            },
        )
        d = as_json(text)
        if not d or d.get("stats", {}).get("n", 0) < 1:
            rec.note(f"B2: {model}/{sid} returned no pairs; next pair")
            continue
        await rec.call(
            "C2",
            "coops-mcp",
            "coops_get_datums",
            {"station_id": sid, "units": "metric"},
        )
        rec.note(f"B2: {model}/{sid} selected", station_id=sid, model=model)
        return
    rec.note("B2: no pair in the order returned data")


async def b3(rec: Recorder) -> None:
    """vdatum conversions at the Fort Myers gauge and the CO-OPS station datums."""
    raw = IAN_SESSION.read_bytes()
    if hashlib.sha256(raw).hexdigest() != IAN_SESSION_SHA256:
        raise SystemExit("Ian session record checksum mismatch")
    station_text = json.loads(raw)["calls"][1]["result"]["content"][0]["text"]
    if (
        f"**Latitude**: {B3_LAT}" not in station_text
        or f"**Longitude**: {B3_LON}" not in station_text
    ):
        raise SystemExit(
            "Fort Myers position differs from the archived coops_get_station"
        )
    for key, target in (("V1", "mhhw"), ("V2", "navd88")):
        await rec.call(
            key,
            "vdatum-mcp",
            "vdatum_convert",
            {
                "datum_from": "mllw",
                "datum_to": target,
                "lat": B3_LAT,
                "lon": B3_LON,
                "z": B3_Z,
                "online": True,
            },
        )
    await rec.call(
        "V3",
        "coops-mcp",
        "coops_get_datums",
        {"station_id": "8725520", "units": "metric"},
    )


async def b4(rec: Recorder) -> None:
    """RTOFS temperature section off Cape Hatteras."""
    t1 = as_json(
        await rec.call(
            "T1",
            "rtofs-mcp",
            "rtofs_get_latest_time",
            {"dataset": "sst", "response_format": "json"},
        )
    )
    now = datetime.now(timezone.utc)
    step = now.replace(minute=0, second=0, microsecond=0)
    step -= timedelta(hours=step.hour % 3)
    t_iso = step.strftime("%Y-%m-%dT%H:00:00Z")
    if not t1 or not (t1["first_time"] <= t_iso <= t1["last_time"]):
        rec.note("B4: requested time outside the dataset axis; B4 skipped", time=t_iso)
        return
    rec.note("B4: requested time fixed by rule", time=t_iso)
    await rec.call(
        "T2",
        "rtofs-mcp",
        "rtofs_get_transect",
        {
            **B4_LINE,
            "variable": "temperature",
            "time": t_iso,
            "n_points": B4_N,
            "response_format": "json",
        },
    )
    frac = 10 / (B4_N - 1)  # the tool's point 10
    mid_lat = round(
        B4_LINE["lat_start"] + frac * (B4_LINE["lat_end"] - B4_LINE["lat_start"]), 4
    )
    mid_lon = round(
        B4_LINE["lon_start"] + frac * (B4_LINE["lon_end"] - B4_LINE["lon_start"]), 4
    )
    await rec.call(
        "T3",
        "rtofs-mcp",
        "rtofs_get_profile_forecast",
        {
            "latitude": mid_lat,
            "longitude": mid_lon,
            "variable": "temperature",
            "time": t_iso,
            "response_format": "json",
        },
    )


async def main() -> None:
    servers = ["ndbc-mcp", "ww3-mcp", "ofs-mcp", "coops-mcp", "vdatum-mcp", "rtofs-mcp"]
    out = PACKAGE / "archive" / "session1_record.json"
    if out.exists():
        raise SystemExit(f"{out} exists; a live run never overwrites the archive")
    async with Recorder(servers, PACKAGE / "archive" / "logs", "session1") as rec:
        for part in (b1, b2, b3, b4):
            await part(rec)
    out.write_text(
        json.dumps(
            rec.record("Part B session 1: B1 (forecast, tool comparison), B2, B3, B4"),
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {out.relative_to(REPO_ROOT)}: {len(rec.calls)} calls")


if __name__ == "__main__":
    asyncio.run(main())
