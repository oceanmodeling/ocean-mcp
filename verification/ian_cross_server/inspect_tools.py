"""List the tools and input schemas of nhc-mcp and coops-mcp over MCP stdio.

Run with the Python of the environment that has the released packages
installed (see make_env.sh):

    <env>/bin/python inspect_tools.py [--out tool_schemas.json]

Each server is started as its own process (``python -m nhc_mcp`` and
``python -m coops_mcp``) and queried with ``tools/list``. Listing tools makes
no upstream data request. No Ocean-MCP Python function is imported here; only
the MCP client SDK is used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVERS = {"nhc-mcp": "nhc_mcp", "coops-mcp": "coops_mcp"}


async def list_all(python: str, cwd: str) -> dict:
    """Open one stdio session per server and return their tool listings."""
    out: dict = {}
    async with AsyncExitStack() as stack:
        sessions = {}
        for name, module in SERVERS.items():
            params = StdioServerParameters(command=python, args=["-m", module], cwd=cwd)
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            init = await session.initialize()
            sessions[name] = (session, init)
        for name, (session, init) in sessions.items():
            listed = await session.list_tools()
            out[name] = {
                "server_info": init.serverInfo.model_dump(mode="json"),
                "protocol_version": init.protocolVersion,
                "tools": [
                    t.model_dump(mode="json", exclude_none=True) for t in listed.tools
                ],
            }
    return out


def main() -> None:
    """Write the tool listing of both servers to a JSON file."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path(__file__).with_name("tool_schemas.json")))
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()
    result = asyncio.run(list_all(args.python, str(Path(args.out).resolve().parent)))
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=False) + "\n")
    for name, info in result.items():
        print(
            f"{name}: serverInfo={info['server_info']} protocol={info['protocol_version']}"
        )
        for t in info["tools"]:
            props = ", ".join(t["inputSchema"].get("properties", {}))
            print(f"  {t['name']}({props})")


if __name__ == "__main__":
    main()
