#!/usr/bin/env python3
"""Run one real MCP stdio session against a server started by the replay launcher.

The client is the MCP Python SDK. The server is the unmodified package,
started as ``<server python> -I ocean_replay_launcher.py --mode ... -m <module>``.
Every tool call, the initialize result, the tool list (with schemas) and the
server's stderr are archived; the launcher writes the HTTP log.

A session is valid only if the launcher log shows zero replay misses and zero
blocked network attempts. Run it inside a network namespace without network
(``unshare -rn``), so a real request cannot succeed even if a guard failed;
the script records whether outbound connections are possible.

Usage: python run_session.py SPEC.json OUT_DIR
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
LAUNCHER = HERE / "ocean_replay_launcher.py"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def network_probe() -> dict:
    """Try one outbound TCP connection (no data sent). Inside ``unshare -rn``
    this must fail."""
    out = {}
    for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        t0 = time.monotonic()
        try:
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            out[f"{host}:{port}"] = "CONNECTED"
        except OSError as exc:
            out[f"{host}:{port}"] = f"refused: {type(exc).__name__}: {exc}"
        out[f"{host}:{port}_seconds"] = round(time.monotonic() - t0, 3)
    return out


def package_versions(python: str, dists: list[str]) -> dict:
    code = (
        "import importlib.metadata as m, json, sys\n"
        "out={'python': sys.version.split()[0]}\n"
        f"for d in {dists!r}:\n"
        "    try: out[d]=m.version(d)\n"
        "    except m.PackageNotFoundError: out[d]=None\n"
        "print(json.dumps(out))\n"
    )
    res = subprocess.run([python, "-I", "-c", code], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def dump_content(result) -> list:
    items = []
    for c in result.content:
        d = c.model_dump(mode="json")
        items.append(d)
    return items


async def run(spec: dict, out: Path) -> int:
    srv = spec["server"]
    out.mkdir(parents=True, exist_ok=True)
    http_log = out / "http_log.jsonl"
    if http_log.exists():
        http_log.unlink()
    args = ["-I", str(LAUNCHER), "--mode", srv["mode"], "--log", str(http_log)]
    for a in srv["archives"]:
        args += ["--archive", a]
    args += ["-m", srv["module"]]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(out), "TZ": "UTC", "LANG": "C.UTF-8"}
    params = StdioServerParameters(command=srv["python"], args=args, env=env)

    transcript = {
        "session_id": spec["session_id"],
        "arm": spec.get("arm"),
        "started_at": utcnow(),
        "network_probe": network_probe(),
        "server_command": [srv["python"], *args],
        "server_env": env,
        "packages": package_versions(srv["python"], srv.get("dists", [])),
        "calls": [],
    }
    errlog = open(out / "server_stderr.txt", "w")
    try:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                transcript["initialize"] = init.model_dump(mode="json")
                tools = await session.list_tools()
                transcript["tools"] = [t.model_dump(mode="json") for t in tools.tools]
                for call in spec["calls"]:
                    t0 = utcnow()
                    res = await session.call_tool(call["tool"], call["arguments"])
                    transcript["calls"].append(
                        {
                            "call_id": call["call_id"],
                            "tool": call["tool"],
                            "arguments": call["arguments"],
                            "sent_at": t0,
                            "received_at": utcnow(),
                            "is_error": bool(res.isError),
                            "content": dump_content(res),
                            "structured_content": res.structuredContent,
                        }
                    )
    finally:
        errlog.close()
    transcript["finished_at"] = utcnow()

    # validity: the launcher's own log
    events = [json.loads(line) for line in http_log.read_text().splitlines()] if http_log.exists() else []
    misses = [e for e in events if e["event"] == "replay_miss"]
    blocked = [e for e in events if e["event"] == "network_blocked"]
    served = [e for e in events if e["event"] in ("served", "recorded")]
    transcript["http"] = {
        "requests": len(served),
        "replay_misses": len(misses),
        "network_blocked": len(blocked),
        "log": str(http_log.name),
    }
    connected = [k for k, v in transcript["network_probe"].items() if v == "CONNECTED"]
    valid = not misses and not blocked and (srv["mode"] == "record" or not connected)
    transcript["valid"] = valid
    (out / "transcript.json").write_text(json.dumps(transcript, indent=1) + "\n")
    print(json.dumps({"session": spec["session_id"], "valid": valid, **transcript["http"],
                      "network_probe_connected": connected}))
    return 0 if valid else 3


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text())
    return asyncio.run(run(spec, Path(sys.argv[2])))


if __name__ == "__main__":
    sys.exit(main())
