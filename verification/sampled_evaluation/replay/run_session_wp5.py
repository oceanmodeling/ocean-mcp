#!/usr/bin/env python3
"""Run one real MCP stdio session with many tool calls against a replayed server (WP5).

Derived from WP1 ``run_session.py`` (copied unchanged beside this file). Differences, all for
scale: the server is started through ``wp5_launcher.py`` (WP1 launcher + CO-OPS rules 4a/4b/5);
every call is attributed the HTTP-log lines written while it ran (the server writes its log
line before it returns the response, so the line count after each response closes the call);
the transcript is written gzip-compressed; a call with a replay miss or network attempt is
marked invalid, and the session is invalid if any call is.

Run inside ``unshare -rn``. Usage: python run_session_wp5.py SPEC.json OUT_DIR
SPEC: {"session_id", "server": {"python", "module", "archives": [...], "dists": [...]},
       "calls": [{"call_id", "tool", "arguments"}, ...]}
"""

from __future__ import annotations

import asyncio
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_session as wp1  # noqa: E402  (network_probe, package_versions, dump_content, utcnow)

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

LAUNCHER = HERE / "wp5_launcher.py"


def _lines(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


async def run(spec: dict, out: Path) -> int:
    srv = spec["server"]
    out.mkdir(parents=True, exist_ok=True)
    http_log = out / "http_log.jsonl"
    if http_log.exists():
        http_log.unlink()
    args = ["-I", str(LAUNCHER), "--mode", "replay", "--log", str(http_log)]
    for a in srv["archives"]:
        args += ["--archive", a]
    args += ["-m", srv["module"]]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(out), "TZ": "UTC", "LANG": "C.UTF-8"}
    params = StdioServerParameters(command=srv["python"], args=args, env=env)
    tr = {"session_id": spec["session_id"], "started_at": wp1.utcnow(), "network_probe": wp1.network_probe(),
          "server_command": [srv["python"], *args], "server_env": env,
          "packages": wp1.package_versions(srv["python"], srv.get("dists", [])), "calls": []}
    errlog = open(out / "server_stderr.txt", "w")
    try:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                tr["initialize"] = (await session.initialize()).model_dump(mode="json")
                tr["tools"] = [t.model_dump(mode="json") for t in (await session.list_tools()).tools]
                seen = len(_lines(http_log))
                for call in spec["calls"]:
                    t0 = wp1.utcnow()
                    res = await session.call_tool(call["tool"], call["arguments"])
                    t1 = wp1.utcnow()
                    ev = _lines(http_log)
                    mine, seen = ev[seen:], len(ev)
                    bad = [e for e in mine if e["event"] in ("replay_miss", "network_blocked")]
                    tr["calls"].append({**call, "sent_at": t0, "received_at": t1, "is_error": bool(res.isError),
                                        "content": wp1.dump_content(res), "http": mine, "valid": not bad})
    finally:
        errlog.close()
    tr["finished_at"] = wp1.utcnow()
    ev = _lines(http_log)
    misses = sum(e["event"] == "replay_miss" for e in ev)
    blocked = sum(e["event"] == "network_blocked" for e in ev)
    connected = [k for k, v in tr["network_probe"].items() if v == "CONNECTED"]
    tr["http"] = {"requests": sum(e["event"] == "served" for e in ev), "replay_misses": misses,
                  "network_blocked": blocked}
    tr["valid"] = misses == 0 and blocked == 0 and not connected and all(c["valid"] for c in tr["calls"])
    with gzip.open(out / "transcript.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(tr, fh)
    print(json.dumps({"session": spec["session_id"], "valid": tr["valid"], "calls": len(tr["calls"]),
                      **tr["http"], "network_probe_connected": connected}))
    return 0 if tr["valid"] else 3


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text())
    return asyncio.run(run(spec, Path(sys.argv[2])))


if __name__ == "__main__":
    sys.exit(main())
