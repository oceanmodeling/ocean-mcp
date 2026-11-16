#!/usr/bin/env python3
"""Run arm C-post (Ocean-MCP 0.3.0 post-fix): all 18 tasks, real MCP stdio, replay, no network.

WP1b. The arm is the same as arm C except for the packages:
  stofs-mcp 0.3.0 post-fix (fix/stofs-post-wp1), erddap-mcp 0.1.3 (fix/erddap-griddap-units),
  ww3-mcp 0.1.3 (WP0b), coops-mcp 0.1.1 (as arm C), all in one environment whose other
  dependencies are pinned to arm C's versions.

The calls are arm C's frozen calls (tasks/tasks.json mcp_calls["C"]), unchanged. Sessions use
the same archive stacks as Phase 2, inside `unshare -rn`; an unarchived request fails the
session and is reported, and nothing is added to the archive. Answers are produced by the
frozen adapters (grader/adapters.py) under the label "Cpost"; arms A to D are not touched.

Usage: python run_c_post.py <verification_dir> <cpost_env_dir>    (harness Python: needs mcp)
Writes run_log/sessions/Cpost/<task>/, results/answers/Cpost/<task>.json, run_log/mcp_arm_Cpost.json.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARM = "Cpost"
MODULE = {"stofs": "stofs_mcp", "coops": "coops_mcp", "erddap": "erddap_mcp", "ww3": "ww3_mcp"}
DISTS = ["stofs-mcp", "coops-mcp", "erddap-mcp", "ww3-mcp", "mcp", "httpx", "numpy", "netCDF4", "xarray"]


def main() -> int:
    vdir, env = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    spec = importlib.util.spec_from_file_location("adapters", vdir / "grader/adapters.py")
    adapters = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapters)
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    wheels = json.loads((vdir / "arms/C_post/wheels.json").read_text())
    for w in wheels["wheels"]:
        got = hashlib.sha256(Path(w["path"]).read_bytes()).hexdigest()
        if got != w["sha256"]:
            print(f"wheel checksum mismatch: {w['path']}", file=sys.stderr)
            return 2
    log = {"arm": "C-post (0.3.0 post-fix)", "label": ARM,
           "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "environment": str(env), "wheels": wheels["wheels"], "sessions": []}
    for t in tasks:
        out = vdir / "run_log/sessions" / ARM / t["id"]
        out.mkdir(parents=True, exist_ok=True)
        calls = t["mcp_calls"]["C"]
        sspec = {"session_id": f"wp1b_{ARM}_{t['id']}", "arm": ARM,
                 "server": {"python": str(env / "bin/python"), "module": MODULE[t["server"]], "mode": "replay",
                            "archives": [str(vdir / "data/archive" / a) for a in t["archives"]], "dists": DISTS},
                 "calls": [{"call_id": c["call_id"], "tool": c["tool"], "arguments": c["arguments"]} for c in calls]}
        (out / "spec.json").write_text(json.dumps(sspec, indent=1) + "\n")
        res = subprocess.run(["unshare", "-rn", sys.executable, str(vdir / "replay/run_session.py"),
                              str(out / "spec.json"), str(out)], capture_output=True, text=True)
        (out / "harness_stdout.txt").write_text(res.stdout + res.stderr)
        tr = json.loads((out / "transcript.json").read_text()) if (out / "transcript.json").exists() else {
            "valid": False, "calls": [], "session_id": sspec["session_id"]}
        task = copy.deepcopy(t)
        task["mcp_calls"][ARM] = task["mcp_calls"]["C"]  # the frozen adapters look calls up by arm label
        ans = adapters.adapt(task, ARM, tr)
        p = vdir / "results/answers" / ARM / f"{t['id']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ans, indent=1, default=str) + "\n")
        misses = []
        if (out / "http_log.jsonl").exists():
            misses = [json.loads(line) for line in (out / "http_log.jsonl").read_text().splitlines()
                      if '"replay_miss"' in line or '"network_blocked"' in line]
        log["sessions"].append({"task": t["id"], "exit": res.returncode, "valid": tr.get("valid"),
                                "http": tr.get("http"), "packages": tr.get("packages"),
                                "status": ans["status"], "action": ans["action"],
                                "violations": [{"event": m["event"], "url": m.get("url") or m.get("host")} for m in misses]})
        print(t["id"], ARM, "exit", res.returncode, "valid", tr.get("valid"), tr.get("http"), ans["status"])
    log["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (vdir / "run_log/mcp_arm_Cpost.json").write_text(json.dumps(log, indent=1) + "\n")
    return 3 if any(s["valid"] is False for s in log["sessions"]) else 0


if __name__ == "__main__":
    sys.exit(main())
