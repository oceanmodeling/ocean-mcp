#!/usr/bin/env python3
"""Run the WP5 MCP sessions offline (DESIGN.md 5.3), each inside `unshare -rn`.

Order: stofs030 2D cycles, stofs030 3D, stofs020 2D, stofs020 3D, coops011. Up to --jobs
sessions run at once (no network is involved). After the first stofs030 2D session finishes,
its elapsed time and a projection of the total are written to run_log/runtime_projection.json
(amendment run-time log). Stops at the first invalid session unless --keep-going.
Usage: python -I run_sessions.py [--jobs N] [--only stofs030 ...] [--keep-going]
"""
import argparse, concurrent.futures as cf, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
PKG = Path(__file__).resolve().parent.parent
HARNESS = PKG / ".envs/harness/bin/python"
RUNNER = PKG / "replay/run_session_wp5.py"


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def one(spec: Path) -> dict:
    ver = spec.parent.name
    out = PKG / "run_log/sessions" / ver / spec.stem
    t0 = time.time()
    r = subprocess.run(["unshare", "-rn", str(HARNESS), str(RUNNER), str(spec), str(out)],
                       capture_output=True, text=True)
    el = time.time() - t0
    last = (r.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        info = json.loads(last)
    except ValueError:
        info = {"raw": last, "stderr": r.stderr[-2000:]}
    return {"spec": str(spec.relative_to(PKG)), "exit": r.returncode, "seconds": round(el, 1), "finished": utc(), **info}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--keep-going", action="store_true")
    a = ap.parse_args()
    order = []
    for ver in ("stofs030", "stofs020"):
        for prod in ("2d", "3d"):
            order += sorted((PKG / "run_log/specs" / ver).glob(f"{prod}_*.json"))
    order.append(PKG / "run_log/specs/coops011/datums.json")
    if a.only:
        order = [s for s in order if s.parent.name in a.only]
    log = PKG / "run_log/sessions_run.jsonl"
    started = time.time()
    first = order[0]
    res0 = one(first)  # the first session alone, for the run-time projection
    with open(log, "a") as fh:
        fh.write(json.dumps(res0) + "\n")
    calls = {s: len(json.loads(s.read_text())["calls"]) for s in order}
    per_call = res0["seconds"] / max(1, calls[first])
    total_calls = sum(calls.values())
    proj = {"written_utc": utc(), "first_session": res0["spec"], "first_session_seconds": res0["seconds"],
            "first_session_calls": calls[first], "seconds_per_call": round(per_call, 3),
            "sessions": len(order), "total_calls": total_calls, "jobs": a.jobs,
            "projected_total_seconds_serial": round(per_call * total_calls),
            "projected_wall_seconds": round(per_call * total_calls / a.jobs),
            "assumption": "every call costs as much as a 2D 0.3.0 call (3D files are smaller, so this is an upper bound for them)"}
    (PKG / "run_log/runtime_projection.json").write_text(json.dumps(proj, indent=1) + "\n")
    print(json.dumps(proj), flush=True)
    if res0["exit"] != 0 and not a.keep_going:
        print("STOP: first session invalid", flush=True)
        return 3
    bad = 0
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for res in ex.map(one, order[1:]):
            with open(log, "a") as fh:
                fh.write(json.dumps(res) + "\n")
            print(json.dumps({k: res.get(k) for k in ("spec", "exit", "seconds", "valid", "calls", "replay_misses")}), flush=True)
            if res["exit"] != 0:
                bad += 1
                if not a.keep_going:
                    print("STOP: invalid session", res["spec"], flush=True)
                    ex.shutdown(cancel_futures=True)
                    return 3
    (PKG / "run_log/sessions_done.json").write_text(json.dumps({"finished": utc(), "wall_seconds": round(time.time() - started),
                                                                "invalid_sessions": bad}, indent=1) + "\n")
    return 0 if bad == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
