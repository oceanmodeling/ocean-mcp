"""Shared helpers for the Part A scripts (standard library only).

The package sits in verification/ian_multi_server/; scripts are one level
deeper, so the repository root is three folders up from this file (the Ian
package's convention, with one more level for scripts/).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO_ROOT = HERE.parents[2]

IAN_SESSION = REPO_ROOT / "verification" / "ian_cross_server" / "session_record.json"
IAN_SESSION_SHA256 = "cc8b52830f23ca98be0ea932e196accc2775490cb6c55542608f9f6ee4fcf1bd"

# NHC Tropical Cyclone Report, Hurricane Ian (revised 12 March 2026), p. 4 and
# Table 1, as quoted in verification/ian_cross_server/references.json.
LANDFALL_UTC = datetime(2022, 9, 28, 19, 5, tzinfo=timezone.utc)
LANDFALL_LATLON = (26.7, -82.2)

EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius, as in the Ian package
TRACK_STEP = timedelta(minutes=5)


def sha256_bytes(b: bytes) -> str:
    """SHA-256 of bytes."""
    return hashlib.sha256(b).hexdigest()


def ian_session() -> dict:
    """The reused Ian session, read in place after its checksum is verified."""
    raw = IAN_SESSION.read_bytes()
    got = sha256_bytes(raw)
    if got != IAN_SESSION_SHA256:
        raise SystemExit(f"{IAN_SESSION}: SHA-256 {got} != {IAN_SESSION_SHA256}")
    return json.loads(raw)


def ian_call_text(index: int) -> str:
    """Text of call ``index`` (1-based) of the reused Ian session."""
    return ian_session()["calls"][index - 1]["result"]["content"][0]["text"]


def parse_utc(s: str) -> datetime:
    """'YYYY-MM-DD HH:MM' (UTC) to an aware datetime."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def best_track() -> list[dict]:
    """Best-track records (call 1) with an aware 'time' added."""
    bt = json.loads(ian_call_text(1))
    out = []
    for p in bt["track_points"]:
        t = datetime.strptime(p["datetime"], "%Y%m%d %H%M UTC").replace(
            tzinfo=timezone.utc
        )
        out.append({**p, "time": t})
    return out


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance on a sphere of radius 6371.0088 km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def centre_at(track: list[dict], t: datetime) -> tuple[float, float] | None:
    """Storm centre at t: linear in time between bracketing records, lat/lon in degrees."""
    for a, b in zip(track, track[1:]):
        if a["time"] <= t <= b["time"]:
            span = (b["time"] - a["time"]).total_seconds()
            f = (t - a["time"]).total_seconds() / span if span else 0.0
            return a["lat"] + f * (b["lat"] - a["lat"]), a["lon"] + f * (
                b["lon"] - a["lon"]
            )
    return None


def sample_track(track: list[dict], t0: datetime, t1: datetime) -> list[tuple]:
    """(time, lat, lon) every 5 minutes from t0 to t1, both included."""
    out, t = [], t0
    while t <= t1:
        c = centre_at(track, t)
        if c is not None:
            out.append((t, c[0], c[1]))
        t += TRACK_STEP
    return out


def nearest_record(track: list[dict], t: datetime) -> dict:
    """Best-track record nearest in time to t (equidistant: the earlier one)."""
    return min(track, key=lambda r: (abs((r["time"] - t).total_seconds()), r["time"]))


def dump(path: Path, obj) -> None:
    """Deterministic JSON file (UTF-8, indent 1, trailing newline)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
