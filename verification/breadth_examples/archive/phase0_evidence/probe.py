"""WP9 Phase 0 probe: one MCP stdio session to one installed server.

    <env>/bin/python probe.py <server> --list
    <env>/bin/python probe.py <server> <tool> '<json args>' --out <name>

Writes the full CallToolResult (and timing) to ../probes/<name>.json and prints
only a short status line (isError, text length, first chars unless --quiet).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROBES = Path(__file__).resolve().parents[1] / "probes"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("server")
    ap.add_argument("tool", nargs="?")
    ap.add_argument("args", nargs="?", default="{}")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--show", type=int, default=600)
    a = ap.parse_args()
    mod = a.server.replace("-", "_")
    cwd = tempfile.mkdtemp(prefix="wp9probe-")
    params = StdioServerParameters(command=sys.executable, args=["-m", mod], cwd=cwd)
    errlog = open(PROBES / f"{a.out or a.server}.stderr.log", "w")
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            tools = await s.list_tools()
            if a.list:
                out = [t.model_dump(mode="json") for t in tools.tools]
                (PROBES / f"tools_{a.server}.json").write_text(json.dumps(out, indent=2))
                for t in tools.tools:
                    props = t.inputSchema.get("properties", {})
                    req = t.inputSchema.get("required", [])
                    print(f"- {t.name}  required={req}")
                    for k, v in props.items():
                        d = {x: v[x] for x in ("type", "default", "enum") if x in v}
                        if "anyOf" in v:
                            d["anyOf"] = [x.get("type") for x in v["anyOf"]]
                        print(f"    {k}: {d}")
                return
            args = json.loads(a.args)
            t0 = time.time()
            started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            res = await s.call_tool(a.tool, args)
            el = time.time() - t0
            rec = {
                "server": a.server,
                "tool": a.tool,
                "arguments": args,
                "started_at": started,
                "elapsed_s": round(el, 3),
                "result": res.model_dump(mode="json"),
            }
            (PROBES / f"{a.out}.json").write_text(json.dumps(rec, indent=2))
            kinds = [c.type for c in res.content]
            text = next((c.text for c in res.content if c.type == "text"), "")
            print(f"isError={res.isError} elapsed={el:.1f}s content={kinds} textlen={len(text)}")
            if a.show:
                print(text[: a.show])


asyncio.run(main())
