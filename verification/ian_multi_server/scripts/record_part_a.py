"""Part A (live): the new recording, as fixed in DESIGN.md section 4.

One client process holds three MCP stdio sessions at once (recon-mcp,
ww3-mcp, ndbc-mcp) and makes calls R1-R4, N1 and W1 in a fixed order. The
buoy is the one selected by scripts/select_buoy.py (results/buoy_selection.json).
Writes archive/part_a_record.json and archive/logs/part_a_<server>.stderr.log.
The nhc-mcp and coops-mcp responses are reused from verification/ian_cross_server/
and are not called again.

    <env>/bin/python scripts/record_part_a.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path.insert(0, str(HERE))
from mcp_recorder import Recorder  # noqa: E402

EXPECTED_BUOY = "42097"  # DESIGN.md 6.1


def hdob_args(day: int) -> dict:
    """Arguments of R1 (day 28) and R2 (day 29)."""
    return {
        "year": 2022,
        "basin": "al",
        "month": 9,
        "day": day,
        "limit": 1000,
        "max_records": 20000,
        "response_format": "json",
    }


async def call_with_one_repeat(rec: Recorder, key, server, tool, args, ok) -> str:
    """Call once; if ``ok(text)`` is false, repeat once after 60 s (DESIGN.md 4)."""
    text = await rec.call(key, server, tool, args)
    if not ok(text):
        rec.note(f"{key} failed; repeating once after 60 s")
        await asyncio.sleep(60)
        text = await rec.call(key + "r", server, tool, args)
    return text


def json_ok(text: str) -> bool:
    """True if the text is a JSON object."""
    try:
        return isinstance(json.loads(text), dict)
    except json.JSONDecodeError:
        return False


async def main() -> None:
    out = PACKAGE / "archive" / "part_a_record.json"
    if out.exists():
        raise SystemExit(f"{out} exists; a live run never overwrites the archive")
    buoy = json.loads((PACKAGE / "results" / "buoy_selection.json").read_text())[
        "selected"
    ]
    if buoy != EXPECTED_BUOY:
        raise SystemExit(f"selection gives {buoy}, DESIGN.md states {EXPECTED_BUOY}")
    servers = ["recon-mcp", "ww3-mcp", "ndbc-mcp"]
    async with Recorder(servers, PACKAGE / "archive" / "logs", "part_a") as rec:
        await call_with_one_repeat(
            rec, "R1", "recon-mcp", "recon_get_hdobs", hdob_args(28), json_ok
        )
        await call_with_one_repeat(
            rec, "R2", "recon-mcp", "recon_get_hdobs", hdob_args(29), json_ok
        )
        await rec.call(
            "R3",
            "recon-mcp",
            "recon_list_sfmr",
            {"year": 2022, "storm_name": "ian", "response_format": "json"},
        )
        await rec.call(
            "R4",
            "recon-mcp",
            "recon_get_sfmr",
            {
                "year": 2022,
                "storm_name": "ian",
                "storm_number": 9,
                "filename": "NOAA_SFMR20220928H1.nc",
                "response_format": "json",
            },
        )
        await call_with_one_repeat(
            rec,
            "N1",
            "ndbc-mcp",
            "ndbc_get_station",
            {"station_id": buoy},
            lambda t: "**Latitude**" in t,
        )
        await call_with_one_repeat(
            rec,
            "W1",
            "ww3-mcp",
            "ww3_get_buoy_history",
            {
                "station_id": buoy,
                "year": 2022,
                "max_records": 5000,
                "response_format": "json",
            },
            json_ok,
        )
    out.write_text(
        json.dumps(
            rec.record(
                "Part A: HDOB (28 and 29 Sep 2022), SFMR tools, buoy metadata and 2022 history"
            ),
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {out.relative_to(PACKAGE)}: {len(rec.calls)} calls")


if __name__ == "__main__":
    asyncio.run(main())
