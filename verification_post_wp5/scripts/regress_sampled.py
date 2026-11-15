#!/usr/bin/env python3
"""WP7 Task C regression 1: rerun the 60 stofs-mcp 0.3.0 sessions of the WP5 sampled evaluation
against the post-WP5 wheel, in a scratch copy, serially; regrade with the frozen grader.

Usage (in the scratch copy V, after building V/.envs/stofs030wp5 with the new wheel):
  python -I regress_sampled.py V            # runs sessions, then grades
  python -I regress_sampled.py V --grade    # grade only
Writes V/run_log/sessions/stofs030wp5/*, V/results/wp7_regression/{summary.json,changed_cases.json}.
"""
import gzip
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

V = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(V / "analysis"))
import study1_outcomes as g  # noqa: E402  (frozen grader and call template)

ENV = V / ".envs/stofs030wp5/bin/python"
HARNESS = V / ".envs/harness/bin/python"
RUNNER = V / "replay/run_session_wp5.py"
ARCH = [str(V / "data/archive" / a) for a in ("models", "coops", "meta", "templates")]
OUT = V / "run_log/sessions/stofs030wp5"
RES = V / "results/wp7_regression"


def run_sessions(cases):
    groups = {}
    for c in sorted(cases, key=lambda c: c["case_id"]):
        groups.setdefault((c["product"], c["cycle"][:10].replace("-", "")), []).append(c)
    spec_dir = V / "run_log/specs/stofs030wp5"
    spec_dir.mkdir(parents=True, exist_ok=True)
    log = V / "run_log/sessions_run_wp7.jsonl"
    done = set()
    if log.exists():
        done = {json.loads(x)["session"] for x in log.read_text().splitlines() if json.loads(x).get("valid")}
    for (prod, day), cs in sorted(groups.items()):
        sid = f"stofs030wp5_{prod}_{day}"
        if sid in done:
            continue
        spec = {"session_id": sid, "server": {"python": str(ENV), "module": "stofs_mcp", "archives": ARCH,
                                              "dists": ["stofs-mcp", "mcp", "httpx", "netCDF4", "numpy"]},
                "calls": [g.call_030(c) for c in cs]}
        sp = spec_dir / f"{prod}_{day}.json"
        sp.write_text(json.dumps(spec, indent=1) + "\n")
        t0 = time.time()
        r = subprocess.run(["unshare", "-rn", str(HARNESS), str(RUNNER), str(sp), str(OUT / f"{prod}_{day}")],
                           capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or ["{}"])[-1]
        try:
            info = json.loads(last)
        except ValueError:
            info = {"raw": last, "stderr": r.stderr[-1500:]}
        info.update({"exit": r.returncode, "seconds": round(time.time() - t0, 1)})
        with open(log, "a") as fh:
            fh.write(json.dumps(info) + "\n")
        print(json.dumps({k: info.get(k) for k in ("session", "valid", "calls", "replay_misses", "seconds")}), flush=True)
        if r.returncode != 0:
            sys.exit(f"STOP: invalid session {sid}")


def grade(cases):
    old = {json.loads(x)["case_id"]: json.loads(x) for x in gzip.open(V / "results/study1/outcomes.jsonl.gz", "rt")}
    new_t = g.load_transcripts(OUT)
    rows, changed = [], []
    counts = Counter()
    warn, coops_msg, misattr_before = 0, 0, 0
    for c in cases:
        cid = c["case_id"]
        call = new_t.get(cid)
        r = g.grade(c, call)
        counts[r["class"]] += 1
        o = old[cid]
        if o["sub"].startswith("declined, other reason (http_error)"):
            misattr_before += 1
            if call and call["text"].startswith("Could not fetch CO-OPS observations: CO-OPS API error:"):
                coops_msg += 1
        js = call["json"] if call else None
        has_warn = bool(js and js.get("station_warning"))
        warn += has_warn
        rows.append({"case_id": cid, "class": r["class"], "sub": r["sub"], "station_warning": has_warn,
                     "duplicate_id_in_reference": c["duplicate_id"] is not None})
        if (r["class"], r["sub"]) != (o["class"], o["sub"]):
            changed.append({"case_id": cid, "before": [o["class"], o["sub"]], "after": [r["class"], r["sub"]],
                            "text_after": (call["text"][:400] if call and not js else None),
                            "stat_diffs_after": r.get("stat_diffs")})
    dup = [x for x in rows if x["duplicate_id_in_reference"]]
    summary = {
        "wheel": "post-WP5 stofs-mcp 0.3.0",
        "class_counts": dict(counts),
        "class_counts_order_9948_105_0_0_0_5143_1": [counts.get(k, 0) for k in (
            "correct_comparison", "correct_refusal", "refusal_reason_differs", "false_refusal",
            "undetected_problem", "not_eligible", "other_discrepancy")],
        "misattributed_before": misattr_before, "now_carry_coops_message": coops_msg,
        "cases_with_station_warning": warn,
        "duplicate_id_cases": len(dup), "duplicate_id_cases_with_warning": sum(x["station_warning"] for x in dup),
        "duplicate_id_cases_by_class": dict(Counter(x["class"] for x in dup)),
        "warnings_outside_duplicate_cases": sum(x["station_warning"] for x in rows if not x["duplicate_id_in_reference"]),
        "class_or_sublabel_changes": len(changed),
        "class_changes": sum(1 for x in changed if x["before"][0] != x["after"][0]),
    }
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (RES / "changed_cases.json").write_text(json.dumps(changed, indent=1) + "\n")
    with open(RES / "outcomes_wp7.jsonl", "w") as fh:
        for x in rows:
            fh.write(json.dumps(x) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    cases = [json.loads(x) for x in gzip.open(V / "reference/results/w49_7/cases.jsonl.gz", "rt")]
    if "--grade" not in sys.argv:
        run_sessions(cases)
    grade(cases)
