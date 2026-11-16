"""Step 2: run the comparisons through Ocean-MCP over the MCP stdio protocol.

Spawns the stofs-mcp server from this checkout (python -m stofs_mcp in the
server's environment), calls stofs_compare_with_observations four times
(forecast and nowcast windows for each model), and archives every exact
request and raw response in results/mcp/. The server downloads the station
files and the CO-OPS observations itself (4 + 4 requests).

Usage (from the repository root):
  uv run --project servers/stofs-mcp python verification/stofs_v31_boston/scripts/02_run_ocean_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import _common as c


def requests() -> list[tuple[str, dict]]:
    out = []
    for model in c.STOFS_FILES:
        windows = {"forecast": c.FORECAST_WINDOW, "nowcast": c.NOWCAST_WINDOWS[model]}
        for name, (lo, hi) in windows.items():
            out.append(
                (
                    f"{model}_{name}",
                    {
                        "station_id": c.STATION,
                        "model": model,
                        "cycle_date": "2026-10-30",
                        "cycle_hour": c.CYCLE_HOUR,
                        "lead_start_hours": lo,
                        "lead_end_hours": hi,
                        "full_resolution": True,
                        "max_points": 2000,
                        "response_format": "json",
                    },
                )
            )
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
    server_info = {
        "package": "stofs-mcp",
        "version": metadata.version("stofs-mcp"),
        "mcp_sdk": metadata.version("mcp"),
        "python": sys.version.split()[0],
        "git_commit": git_commit(),
        "command": [sys.executable, "-m", "stofs_mcp"],
    }
    params = StdioServerParameters(command=sys.executable, args=["-m", "stofs_mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            server_info["server_name"] = init.serverInfo.name
            for name, args in requests():
                called_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                result = await session.call_tool(
                    "stofs_compare_with_observations", args
                )
                text = result.content[0].text
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                c.dump_json(
                    {
                        "called_at": called_at,
                        "server": server_info
                        | {"command": ["python", "-m", "stofs_mcp"]},
                        "request": {
                            "tool": "stofs_compare_with_observations",
                            "arguments": args,
                        },
                        "is_error": bool(result.isError),
                        "response_text": text,
                        "response": parsed,
                    },
                    c.RESULTS / "mcp" / f"{name}.json",
                )
                st = (parsed or {}).get("statistics", {})
                print(
                    f"{name}: n={st.get('n')} bias={st.get('bias')} rmse={st.get('rmse')} "
                    f"datum={(parsed or {}).get('stofs_datum')}/{(parsed or {}).get('coops_datum')}"
                    if parsed
                    else f"{name}: NON-JSON RESPONSE: {text[:300]}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
