"""Record MCP tool calls: one client process, one stdio session per server.

Each server runs as its own process (``<env python> -m <module>``) from a
neutral temporary working directory, so it imports only the installed wheel.
Every call is stored with its server, tool, arguments, the pause before it,
start and finish times, the complete ``CallToolResult`` and the SHA-256 of
its text. Each server's stderr goes to its own log file; the logs show the
upstream HTTP requests and status codes.

Only the MCP client SDK is imported; no Ocean-MCP function is called directly.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata as md
import json
import os
import platform
import sys
import tempfile
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PAUSE_S = 3.0


def utcnow() -> str:
    """Current UTC time, ISO 8601 with milliseconds."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(text: str) -> str:
    """SHA-256 of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def child_processes() -> list[dict]:
    """Direct child processes of this client (Linux /proc), with command lines."""
    me = os.getpid()
    out = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            if int(stat.rsplit(")", 1)[1].split()[1]) != me:
                continue
            cmd = (entry / "cmdline").read_bytes().split(b"\0")
            out.append(
                {"pid": int(entry.name), "cmdline": [c.decode() for c in cmd if c]}
            )
        except (OSError, ValueError, IndexError):
            continue
    return sorted(out, key=lambda p: p["pid"])


def text_of(result) -> str:
    """The first text content of a CallToolResult ('' if none)."""
    return next((c.text for c in result.content if c.type == "text"), "")


class Recorder:
    """Holds the sessions and the call log."""

    def __init__(self, servers: list[str], log_dir: Path, label: str):
        self.servers = servers
        self.log_dir = log_dir
        self.label = label
        self.calls: list[dict] = []
        self.events: list[dict] = []
        self.sessions: dict[str, ClientSession] = {}
        self.server_info: dict[str, dict] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "Recorder":
        self.started_at = utcnow()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        for name in self.servers:
            module = name.replace("-", "_")
            errlog = self._stack.enter_context(
                open(self.log_dir / f"{self.label}_{name}.stderr.log", "w")
            )
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", module],
                cwd=tempfile.mkdtemp(prefix=f"wp9-{name}-"),
            )
            read, write = await self._stack.enter_async_context(
                stdio_client(params, errlog=errlog)
            )
            session = await self._stack.enter_async_context(ClientSession(read, write))
            init = await session.initialize()
            tools = await session.list_tools()
            self.sessions[name] = session
            self.server_info[name] = {
                "module": module,
                "distribution_version": md.version(name),
                "initialize_result": init.model_dump(mode="json"),
                "tool_names": [t.name for t in tools.tools],
                "tools": [t.model_dump(mode="json") for t in tools.tools],
            }
        self.processes_before = child_processes()
        return self

    async def __aexit__(self, *exc) -> None:
        self.processes_after = child_processes()
        self.finished_at = utcnow()
        await self._stack.aclose()

    def note(self, text: str, **data) -> None:
        """Record a decision taken by the script (fallback, repeat, skip)."""
        self.events.append({"at": utcnow(), "note": text, **data})
        print(f"  [note] {text}", flush=True)

    async def call(self, key: str, server: str, tool: str, arguments: dict) -> str:
        """Call one tool, store the full record, return the text content."""
        if tool not in self.server_info[server]["tool_names"]:
            raise SystemExit(f"{server} lists no tool named {tool!r}")
        pause = PAUSE_S if self.calls else 0.0
        await asyncio.sleep(pause)
        started = utcnow()
        result = await self.sessions[server].call_tool(tool, arguments)
        finished = utcnow()
        text = text_of(result)
        dumped = result.model_dump(mode="json")
        self.calls.append(
            {
                "key": key,
                "seq": len(self.calls) + 1,
                "server": server,
                "tool": tool,
                "arguments": arguments,
                "pause_before_s": pause,
                "started_at": started,
                "finished_at": finished,
                "is_error": result.isError,
                "text_sha256": sha256_text(text),
                "result_sha256": sha256_text(
                    json.dumps(dumped, sort_keys=True, separators=(",", ":"))
                ),
                "result": dumped,
            }
        )
        print(
            f"{key:6s} {server:11s} {tool:34s} isError={result.isError} "
            f"len={len(text)}",
            flush=True,
        )
        return text

    def record(self, note: str) -> dict:
        """The complete session record."""
        return {
            "record_type": "mcp_session",
            "label": self.label,
            "note": note,
            "client": {
                "pid": os.getpid(),
                "python": sys.version.split()[0],
                "executable": sys.executable,
                "platform": platform.platform(),
                "mcp_sdk": md.version("mcp"),
            },
            "session_started_at": self.started_at,
            "session_finished_at": self.finished_at,
            "servers": self.server_info,
            "server_processes_before_first_call": self.processes_before,
            "server_processes_after_last_call": self.processes_after,
            "events": self.events,
            "calls": self.calls,
        }
