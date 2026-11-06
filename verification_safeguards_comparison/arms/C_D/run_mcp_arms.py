#!/usr/bin/env python3
"""Run arms C and D: one real MCP stdio session per task and arm, replay mode, no network.

For each task in tasks/tasks.json and each requested arm, the frozen calls
(tasks.json mcp_calls) are sent through replay/run_session.py inside
`unshare -rn`. The transcript (every MCP request and response, tool list,
package versions, network probe) and the launcher's HTTP log (every upstream
request, the archive entry that answered it and the SHA-256 of the bytes
served) are kept under run_log/sessions/<arm>/<task>/. The frozen adapters then
write results/answers/<arm>/<task>.json.

Arm C for R7 is the ww3-mcp 0.1.3 wheel in verification_ww3_history_fix/dist/
if it exists when this runs; otherwise the answer is 'candidate not available'
and no session is started.

Usage: python run_mcp_arms.py <verification_dir> <repo_root> <envs_dir> [--arms C,D] [--tasks N1,...]
(run with the harness environment's Python; it needs the mcp package)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ENV_FOR = {
    ("C", "stofs"): "stofs030", ("D", "stofs"): "stofs020",
    ("C", "coops"): "coops", ("D", "coops"): "coops",
    ("C", "erddap"): "erddap", ("D", "erddap"): "erddap",
    ("C", "ww3"): "ww3_013", ("D", "ww3"): "ww3_012",
}
MODULE = {"stofs": "stofs_mcp", "coops": "coops_mcp", "erddap": "erddap_mcp", "ww3": "ww3_mcp"}
DISTS = {"stofs": ["stofs-mcp"], "coops": ["coops-mcp"], "erddap": ["erddap-mcp"], "ww3": ["ww3-mcp"]}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    vdir, repo, envs = (Path(a).resolve() for a in sys.argv[1:4])
    arms = sys.argv[sys.argv.index("--arms") + 1].split(",") if "--arms" in sys.argv else ["C", "D"]
    only = set(sys.argv[sys.argv.index("--tasks") + 1].split(",")) if "--tasks" in sys.argv else None
    spec = importlib.util.spec_from_file_location("adapters", vdir / "grader/adapters.py")
    adapters = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapters)
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    ww3_c = sorted((repo / "verification_ww3_history_fix/dist").glob("ww3_mcp-0.1.3-*.whl"))
    log = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "arms": arms,
           "ww3_candidate_wheel": [{"path": str(w), "sha256": sha256(w)} for w in ww3_c], "sessions": []}
    for t in tasks:
        if only and t["id"] not in only:
            continue
        for arm in arms:
            out = vdir / "run_log/sessions" / arm / t["id"]
            if t["server"] == "ww3" and arm == "C" and not (envs / "ww3_013").exists():
                ans = {"task_id": t["id"], "arm": "C", "status": "candidate_not_available", "action": None,
                       "values": {}, "nearest_equivalent": False, "metadata": {}, "texts": [
                           "ww3-mcp 0.1.3 candidate not available: no wheel in verification_ww3_history_fix/dist/ "
                           f"(found {[str(w) for w in ww3_c]}) or no ww3_013 environment"],
                       "exclusions": [], "evidence": {}}
                p = vdir / "results/answers/C" / f"{t['id']}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(ans, indent=1) + "\n")
                log["sessions"].append({"task": t["id"], "arm": arm, "status": "candidate_not_available"})
                continue
            env = envs / ENV_FOR[(arm, t["server"])]
            sspec = {"session_id": f"wp1_{arm}_{t['id']}", "arm": arm,
                     "server": {"python": str(env / "bin/python"), "module": MODULE[t["server"]], "mode": "replay",
                                "archives": [str(vdir / "data/archive" / a) for a in t["archives"]],
                                "dists": DISTS[t["server"]] + ["mcp", "httpx"]},
                     "calls": [{"call_id": c["call_id"], "tool": c["tool"], "arguments": c["arguments"]}
                               for c in t["mcp_calls"][arm]]}
            out.mkdir(parents=True, exist_ok=True)
            (out / "spec.json").write_text(json.dumps(sspec, indent=1) + "\n")
            res = subprocess.run(["unshare", "-rn", sys.executable, str(vdir / "replay/run_session.py"),
                                  str(out / "spec.json"), str(out)], capture_output=True, text=True)
            (out / "harness_stdout.txt").write_text(res.stdout + res.stderr)
            tr = json.loads((out / "transcript.json").read_text()) if (out / "transcript.json").exists() else {
                "valid": False, "calls": [], "session_id": sspec["session_id"]}
            ans = adapters.adapt(t, arm, tr)
            p = vdir / "results/answers" / arm / f"{t['id']}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(ans, indent=1, default=str) + "\n")
            log["sessions"].append({"task": t["id"], "arm": arm, "exit": res.returncode, "valid": tr.get("valid"),
                                    "http": tr.get("http"), "packages": tr.get("packages"),
                                    "status": ans["status"], "action": ans["action"]})
            print(t["id"], arm, "exit", res.returncode, "valid", tr.get("valid"), tr.get("http"), ans["status"])
    log["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (vdir / f"run_log/mcp_arms_{'_'.join(arms)}.json").write_text(json.dumps(log, indent=1) + "\n")
    bad = [s for s in log["sessions"] if s.get("valid") is False]
    return 3 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
