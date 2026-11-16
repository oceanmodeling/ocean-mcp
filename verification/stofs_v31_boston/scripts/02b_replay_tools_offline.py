"""Step 2b: replay the Ocean-MCP tools offline on the archived inputs.

Calls the stofs-mcp tool functions of this checkout directly (not over stdio),
with the station NetCDF downloads answered from copies of data/raw (the tools
delete their download afterwards, so the archive is never handed to them) and
the CO-OPS requests answered from the archived response. No network access.

1. Replays the four Boston comparisons and checks them point by point against
   the archived MCP responses in results/mcp (produced live by step 02).
2. Runs the station, point, max-water-level and compare tools on the STOFS-3D
   stations of this cycle whose values are shifted no-data sentinels (1e7 + c),
   and the max tool on the STOFS-2D file.
Writes results/replay_offline.json; exits 1 if a replay differs.

Usage (from the repository root):
  uv run --project servers/stofs-mcp python verification/stofs_v31_boston/scripts/02b_replay_tools_offline.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from importlib import metadata
from pathlib import Path
from unittest.mock import MagicMock

from stofs_mcp.client import STOFSClient
from stofs_mcp.models import STOFSModel
from stofs_mcp.tools.forecast import (
    stofs_get_max_water_level,
    stofs_get_point_forecast,
    stofs_get_station_forecast,
)
from stofs_mcp.tools.validation import stofs_compare_with_observations

import _common as c

CYCLE = {"cycle_date": "2026-10-30", "cycle_hour": c.CYCLE_HOUR}
OBS = c.load_json(c.COOPS / "water_level_8443970_MSL.json")
SENTINEL_STATIONS = ["9751364", "9751401", "9751381", "9752695", "9752235"]


class Archive:
    def __init__(self) -> None:
        self.coops_requests: list[tuple] = []

    def ctx(self, model: str):
        client = STOFSClient(backoff_factor=0)
        source = c.RAW / c.STOFS_FILES[model]["file"]

        async def download(url):
            tmp = Path(tempfile.mkdtemp()) / "station.nc"
            shutil.copy(source, tmp)
            return tmp

        async def fetch(station, begin, end, datum="MSL"):
            self.coops_requests.append((station, begin, end, datum))
            if station != c.STATION or datum != "MSL":
                return {"data": []}
            b = datetime.strptime(begin, "%Y%m%d %H:%M")
            e = datetime.strptime(end, "%Y%m%d %H:%M")
            rows = [
                r
                for r in OBS["data"]
                if b <= datetime.strptime(r["t"], "%Y-%m-%d %H:%M") <= e
            ]
            return {"metadata": OBS["metadata"], "data": rows}

        client.download_netcdf = download
        client.fetch_coops_observations = fetch
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"stofs_client": client}
        return ctx


async def replay_boston(arc: Archive) -> dict:
    out = {}
    for f in sorted((c.RESULTS / "mcp").glob("*.json")):
        archived = c.load_json(f)
        args = dict(archived["request"]["arguments"])
        model = args.pop("model")
        new = json.loads(
            await stofs_compare_with_observations(
                arc.ctx(model), model=STOFSModel(model), **args
            )
        )
        old = archived["response"]
        series_old = [(p["time"], p["stofs_m"], p["obs_m"]) for p in old["comparison"]]
        series_new = [(p["time"], p["stofs_m"], p["obs_m"]) for p in new["comparison"]]
        shared = {
            k: (old["statistics"][k], new["statistics"].get(k))
            for k in old["statistics"]
        }
        out[f.stem] = {
            "archived_server_commit": archived["server"]["git_commit"],
            "series_identical": series_old == series_new,
            "statistics_identical": all(a == b for a, b in shared.values()),
            "peak_error_m_identical": old["summary"]["peak_error_m"]
            == new["summary"]["peak_error_m"],
            "datum_provenance": new["datum_provenance"],
            "excluded_model_records": new["window"]["excluded_model_records"],
            "statistics": new["statistics"],
        }
    return out


async def sentinel_checks(arc: Archive) -> dict:
    out = {}
    for model in c.STOFS_FILES:
        j = json.loads(
            await stofs_get_max_water_level(
                arc.ctx(model),
                model=STOFSModel(model),
                top_n=10,
                response_format="json",
                **CYCLE,
            )
        )
        out[f"max_water_level_{model}"] = {
            "top_10": [[r["station"], r["max_wl"]] for r in j["top_stations"]],
            "largest_ranked_value_m": max(r["max_wl"] for r in j["top_stations"]),
            "excluded_values": j["excluded_values"],
            "excluded_stations": j["excluded_stations"],
        }
    m3 = STOFSModel("3d_atlantic")
    for sid in SENTINEL_STATIONS:
        station = await stofs_get_station_forecast(
            arc.ctx("3d_atlantic"), station_id=sid, model=m3, **CYCLE
        )
        n0 = len(arc.coops_requests)
        compare = await stofs_compare_with_observations(
            arc.ctx("3d_atlantic"), station_id=sid, model=m3, **CYCLE
        )
        out[f"station_{sid}"] = {
            "station_tool": station.split("\n")[0],
            "compare_tool": compare.split("\n")[0],
            "coops_requests_made_by_compare": len(arc.coops_requests) - n0,
        }
    out["point_tool_at_9751381"] = (
        await stofs_get_point_forecast(
            arc.ctx("3d_atlantic"),
            latitude=18.3182,
            longitude=-64.7242,
            model=m3,
            **CYCLE,
        )
    ).split("\n")[0]
    return out


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=c.REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return None


async def main() -> int:
    before = {k: c.sha256(c.RAW / v["file"]) for k, v in c.STOFS_FILES.items()}
    arc = Archive()
    boston = await replay_boston(arc)
    sentinels = await sentinel_checks(arc)
    after = {k: c.sha256(c.RAW / v["file"]) for k, v in c.STOFS_FILES.items()}
    ok = all(
        v["series_identical"]
        and v["statistics_identical"]
        and v["peak_error_m_identical"]
        for v in boston.values()
    )
    c.dump_json(
        {
            "code": {
                "package": "stofs-mcp",
                "version": metadata.version("stofs-mcp"),
                "git_commit": git_commit(),
            },
            "archive_unchanged": before == after,
            "boston_replay_matches_archived_mcp": ok,
            "boston_replay": boston,
            "sentinel_and_plausibility_checks": sentinels,
        },
        c.RESULTS / "replay_offline.json",
    )
    for k, v in boston.items():
        print(
            f"{k}: series {v['series_identical']} stats {v['statistics_identical']} "
            f"n={v['statistics']['n']} bias={v['statistics']['bias']}"
        )
    for k, v in sentinels.items():
        print(k, "->", json.dumps(v)[:260])
    print("archive unchanged:", before == after, "| replay matches:", ok)
    return 0 if ok and before == after else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
