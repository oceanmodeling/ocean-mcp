"""Part B, B1 session 2 (live): the buoy observations, DESIGN.md 3.2.

Run no earlier than the session-1 forecast cycle + 73 h. One client process,
one MCP stdio session (ndbc-mcp), one call:

    ndbc_get_observations(station_id, hours=H, variables=["WVHT"],
                          response_format="json", max_records=2000)

with H = whole hours from the cycle time to the call time, rounded up, + 6
(at most 1080). Writes archive/session2_record.json and
archive/logs/session2_ndbc-mcp.stderr.log.

    <env>/bin/python scripts/record_b1_session2.py
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path.insert(0, str(HERE))
from mcp_recorder import Recorder  # noqa: E402


def session1() -> tuple[str, datetime]:
    """Selected buoy and forecast cycle time from session 1."""
    rec = json.loads((PACKAGE / "archive" / "session1_record.json").read_text())
    sid = next(
        e["station_id"] for e in rec["events"] if e["note"].startswith("B1: buoy")
    )
    fc = next(c for c in reversed(rec["calls"]) if c["key"] in ("S1.3", "S1.3r"))
    cycle = json.loads(fc["result"]["content"][0]["text"])["cycle"]  # "YYYY-MM-DD HHz"
    t = datetime.strptime(cycle, "%Y-%m-%d %Hz").replace(tzinfo=timezone.utc)
    return sid, t


async def main() -> None:
    out = PACKAGE / "archive" / "session2_record.json"
    if out.exists():
        raise SystemExit(f"{out} exists; a live run never overwrites the archive")
    sid, cycle = session1()
    now = datetime.now(timezone.utc)
    earliest = cycle + timedelta(hours=73)
    if now < earliest:
        raise SystemExit(
            f"too early: run no earlier than {earliest:%Y-%m-%d %H:%M} UTC"
        )
    hours = math.ceil((now - cycle).total_seconds() / 3600) + 6
    if hours > 1080:
        raise SystemExit(
            f"H = {hours} exceeds 1080; the realtime file no longer covers the forecast"
        )
    async with Recorder(["ndbc-mcp"], PACKAGE / "archive" / "logs", "session2") as rec:
        rec.note(
            "B1 session 2: H fixed by rule",
            station_id=sid,
            cycle=cycle.isoformat(),
            hours=hours,
        )
        await rec.call(
            "S2.1",
            "ndbc-mcp",
            "ndbc_get_observations",
            {
                "station_id": sid,
                "hours": hours,
                "variables": ["WVHT"],
                "response_format": "json",
                "max_records": 2000,
            },
        )
    out.write_text(
        json.dumps(rec.record("Part B session 2: B1 buoy observations"), indent=1)
        + "\n"
    )
    print(f"wrote {out.relative_to(PACKAGE)}")


if __name__ == "__main__":
    asyncio.run(main())
