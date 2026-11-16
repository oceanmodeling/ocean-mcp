"""Scripted two-server MCP workflow for Hurricane Ian (2022): live run.

One client process opens two MCP stdio sessions at the same time, one to
``nhc-mcp`` and one to ``coops-mcp``. Each server runs as its own process
(``python -m nhc_mcp`` and ``python -m coops_mcp``) from the released PyPI
wheels installed by ``make_env.py``. The client lists each server's tools,
checks every argument against the listed input schema, then makes seven tool
calls one after another with a pause between them, and writes everything to
``session_record.json``: server, tool, arguments, the complete
``CallToolResult``, timestamps, package versions and SHA-256 checksums.

No language model is involved: the tool sequence and arguments are fixed in
this file. No Ocean-MCP Python function is imported; only the MCP client SDK.

    <env>/bin/python run_workflow.py [--out session_record.json]

The analysis is separate (``analyze.py``, standard library only).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata as md
import importlib.util
import json
import os
import platform
import sys
import tempfile
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
PAUSE_S = 3.0

SERVERS = {
    "nhc-mcp": {"module": "nhc_mcp", "distribution": "nhc-mcp"},
    "coops-mcp": {"module": "coops_mcp", "distribution": "coops-mcp"},
}

STORM_ID = "AL092022"
STATIONS = ["8725520", "8726520"]  # Fort Myers, St. Petersburg

# Fixed arguments, as in manuscript-final-runs-2026-07-27.md section 1a.
WINDOW = {
    "begin_date": "2022-09-27",
    "end_date": "2022-09-29",
    "datum": "MLLW",
    "units": "metric",
    "time_zone": "gmt",
    "interval": "6",
    "response_format": "json",
    "max_records": 2000,
}


def planned_calls() -> list[tuple[str, str, dict]]:
    """The fixed call sequence: (server, tool, arguments)."""
    calls = [
        (
            "nhc-mcp",
            "nhc_get_best_track",
            {"storm_id": STORM_ID, "response_format": "json"},
        )
    ]
    for sid in STATIONS:
        calls.append(
            (
                "coops-mcp",
                "coops_get_station",
                {"station_id": sid, "expand": ["details", "datums"], "units": "metric"},
            )
        )
        calls.append(
            ("coops-mcp", "coops_get_water_levels", {"station_id": sid, **WINDOW})
        )
        calls.append(
            ("coops-mcp", "coops_get_tide_predictions", {"station_id": sid, **WINDOW})
        )
    return calls


def utcnow() -> str:
    """Current UTC time, ISO 8601 with milliseconds."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(text: str) -> str:
    """SHA-256 of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj) -> str:
    """Canonical JSON used for checksums of structured objects."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def child_processes() -> list[dict]:
    """Direct child processes of this client (Linux /proc), with command lines."""
    me = os.getpid()
    out = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
            if ppid != me:
                continue
            cmd = (entry / "cmdline").read_bytes().split(b"\0")
            out.append(
                {"pid": int(entry.name), "cmdline": [c.decode() for c in cmd if c]}
            )
        except (OSError, ValueError, IndexError):
            continue
    return sorted(out, key=lambda p: p["pid"])


def package_info() -> dict:
    """Versions of every installed distribution, plus where the two server modules live."""
    versions = {d.metadata["Name"].lower(): d.version for d in md.distributions()}
    servers = {}
    for name, cfg in SERVERS.items():
        dist = md.distribution(cfg["distribution"])
        spec = importlib.util.find_spec(cfg["module"])  # locates, does not import
        direct_url = dist.read_text("direct_url.json")
        servers[name] = {
            "distribution": cfg["distribution"],
            "version": dist.version,
            "module": cfg["module"],
            "module_origin": spec.origin if spec else None,
            "direct_url": json.loads(direct_url) if direct_url else None,
        }
    return {"distributions": dict(sorted(versions.items())), "servers": servers}


def check_arguments(tool_index: dict, server: str, tool: str, arguments: dict) -> dict:
    """Validate arguments against the tool's listed input schema; raise on any problem."""
    if tool not in tool_index[server]:
        raise SystemExit(f"{server} does not list a tool named {tool!r}")
    schema = tool_index[server][tool]["inputSchema"]
    unknown = sorted(set(arguments) - set(schema.get("properties", {})))
    if unknown:
        raise SystemExit(f"{tool}: arguments not in schema: {unknown}")
    jsonschema.validate(arguments, schema)
    return {"schema_valid": True, "unknown_arguments": unknown}


def response_problems(tool: str, arguments: dict, text: str) -> list[str]:
    """Reasons a response cannot be used; empty if it looks complete."""
    problems = []
    if text.lstrip().startswith(("Error", "Validation Error", "No ")):
        problems.append(f"error-like text: {text[:120]!r}")
    if arguments.get("response_format") == "json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return problems + [f"not JSON: {exc}"]
        if doc.get("truncated"):
            problems.append(
                f"truncated: record_count={doc.get('record_count')} total_count={doc.get('total_count')}; raise max_records"
            )
    return problems


async def run_session(python: str, server_cwd: str, logdir: Path) -> dict:
    """Open both sessions, list tools, make the fixed calls, return the record."""
    record: dict = {"session_started_at": utcnow(), "servers": [], "calls": []}
    async with AsyncExitStack() as stack:
        sessions: dict[str, ClientSession] = {}
        tool_index: dict[str, dict] = {}
        for name, cfg in SERVERS.items():
            params = StdioServerParameters(
                command=python, args=["-m", cfg["module"]], cwd=server_cwd
            )
            errlog = stack.enter_context(open(logdir / f"{name}.stderr.log", "w"))
            read, write = await stack.enter_async_context(
                stdio_client(params, errlog=errlog)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            init = await session.initialize()
            listed = await session.list_tools()
            tools = [
                t.model_dump(mode="json", by_alias=True, exclude_none=True)
                for t in listed.tools
            ]
            sessions[name] = session
            tool_index[name] = {t["name"]: t for t in tools}
            record["servers"].append(
                {
                    "name": name,
                    "command": [python, "-m", cfg["module"]],
                    "cwd": server_cwd,
                    "transport": "stdio",
                    "initialize_result": init.model_dump(
                        mode="json", by_alias=True, exclude_none=True
                    ),
                    "tools_list": tools,
                    "tools_list_sha256": sha256_text(canonical(tools)),
                }
            )

        procs_before = child_processes()
        record["server_processes_before_first_call"] = procs_before

        for seq, (server, tool, arguments) in enumerate(planned_calls(), start=1):
            validation = check_arguments(tool_index, server, tool, arguments)
            pause = PAUSE_S if seq > 1 else 0.0
            await asyncio.sleep(pause)
            started = utcnow()
            t0 = time.monotonic()
            result = await sessions[server].call_tool(tool, arguments)
            elapsed = time.monotonic() - t0
            finished = utcnow()
            dumped = result.model_dump(mode="json", by_alias=True, exclude_none=True)
            texts = [
                c["text"] for c in dumped.get("content", []) if c.get("type") == "text"
            ]
            text = texts[0] if len(texts) == 1 else None
            problems = (
                response_problems(tool, arguments, text)
                if text is not None
                else [f"expected one text content item, got {len(texts)}"]
            )
            if dumped.get("isError"):
                problems.append("isError is true")
            record["calls"].append(
                {
                    "seq": seq,
                    "server": server,
                    "tool": tool,
                    "arguments": arguments,
                    "argument_check": validation,
                    "pause_before_s": pause,
                    "started_at": started,
                    "finished_at": finished,
                    "elapsed_s": round(elapsed, 3),
                    "result": dumped,
                    "text_sha256": sha256_text(text) if text is not None else None,
                    "result_sha256": sha256_text(canonical(dumped)),
                    "problems": problems,
                }
            )
            status = "ok" if not problems else "PROBLEM: " + "; ".join(problems)
            print(
                f"[{seq}] {server} {tool} {arguments.get('station_id', arguments.get('storm_id'))}: {elapsed:.1f} s, {status}"
            )

        record["server_processes_after_last_call"] = child_processes()
    record["session_finished_at"] = utcnow()
    for srv in record["servers"]:
        srv["stderr"] = (logdir / f"{srv['name']}.stderr.log").read_text()
    return record


def main() -> None:
    """Run the live session and write the record."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(HERE / "session_record.json"))
    ap.add_argument("--env-provenance", default=str(HERE / "env_provenance.json"))
    args = ap.parse_args()

    python = sys.executable
    with tempfile.TemporaryDirectory(prefix="wp2_servers_") as server_cwd:
        # Neutral working directory, so the servers can only import their installed wheels.
        record = asyncio.run(run_session(python, server_cwd, Path(server_cwd)))

    prov_path = Path(args.env_provenance)
    record = {
        "record_type": "Ocean-MCP scripted two-server MCP workflow (Hurricane Ian 2022)",
        "note": (
            "One client process held two MCP stdio sessions, one per server process. "
            "The tool sequence and arguments were fixed in run_workflow.py; no language model selected or invoked the tools."
        ),
        "created_by": "run_workflow.py",
        "client": {
            "pid": os.getpid(),
            "python_version": sys.version.split()[0],
            "executable": python,
            "platform": platform.platform(),
            "mcp_sdk_version": md.version("mcp"),
            "pause_between_calls_s": PAUSE_S,
        },
        "packages": package_info(),
        "env_provenance": json.loads(prov_path.read_text())
        if prov_path.exists()
        else None,
        **record,
    }
    Path(args.out).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    bad = [c for c in record["calls"] if c["problems"]]
    print(f"wrote {args.out}: {len(record['calls'])} calls, {len(bad)} with problems")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
