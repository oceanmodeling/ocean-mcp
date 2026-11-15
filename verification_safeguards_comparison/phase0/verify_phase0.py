#!/usr/bin/env python3
"""Phase 0 check: the replayed Boston session reproduces the archived live MCP results.

Compares every field of the four stofs_compare_with_observations responses in
phase0/sessions/boston_stofs030_replay/transcript.json (stofs-mcp 0.3.0 wheel,
replay mode, no network) with the archived live responses of the Boston package
(results/mcp/*.json, produced live on 2026-11-04 by commit 31e7f6a).

Allowed differences, and only these:
  * retrieved_at (time of the call);
  * keys added after 31e7f6a by 0e07048 and 1240d98 (counters for sentinel,
    implausible and duplicate_model_times);
  * the 2D datum source wording, which 52f5ae6 extended with the name and
    archive date of the NOAA document.
Every statistic, every series point and every count must be identical.

Also checks the other Phase 0 sessions: the 0.2.0 smoke session is valid, and
the fail-loud sessions are invalid for the expected reason.

Usage: python -I verify_phase0.py <verification_dir> <boston_package_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ADDED_KEYS = {"/alignment/duplicate_model_times", "/observation_quality/implausible",
              "/observation_quality/sentinel", "/window/excluded_model_records/implausible",
              "/window/excluded_model_records/sentinel"}
WORDING = {"/datum_note", "/datum_provenance/source", "/stofs_datum_source"}


def diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}/{k}"
            if k not in a or k not in b:
                out.append((p, "added" if k in b else "removed"))
            else:
                out += diff(a[k], b[k], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"length {len(a)} vs {len(b)}"))
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
    elif a != b:
        out.append((path, f"{a!r} -> {b!r}"))
    return out


def main() -> int:
    vdir, boston = Path(sys.argv[1]), Path(sys.argv[2])
    sess = vdir / "phase0/sessions"
    t = json.loads((sess / "boston_stofs030_replay/transcript.json").read_text())
    report = {"session_valid": t["valid"], "http": t["http"], "network_probe": t["network_probe"],
              "packages": t["packages"], "calls": {}}
    ok = t["valid"] and t["http"]["replay_misses"] == 0 and t["http"]["network_blocked"] == 0
    for c in t["calls"]:
        live = json.loads((boston / "results/mcp" / f"{c['call_id']}.json").read_text())
        new = json.loads(c["content"][0]["text"])
        d = diff(live["response"], new)
        allowed, unexpected = [], []
        for p, what in d:
            if p == "/retrieved_at" or (p in ADDED_KEYS and what == "added") or (
                    p in WORDING and c["call_id"].startswith("2d")):
                allowed.append(p)
            else:
                unexpected.append((p, what))
        st = new["statistics"]
        report["calls"][c["call_id"]] = {
            "live_commit": live["server"]["git_commit"], "n": st["n"], "bias": st["bias"], "rmse": st["rmse"],
            "series_points": len(new["comparison"]), "series_identical": live["response"]["comparison"] == new["comparison"],
            "statistics_identical": live["response"]["statistics"] == {k: v for k, v in st.items()},
            "allowed_differences": allowed, "unexpected_differences": unexpected}
        ok &= not unexpected and report["calls"][c["call_id"]]["series_identical"]
    # other sessions
    # (expected validity, counter that must be >= 1 for the expected reason)
    exp = {"stofs020_smoke": (True, None), "stofs030_failloud": (False, "replay_misses"),
           "ww3_012_failloud": (False, "replay_misses"), "erddap_dnsguard": (False, "network_blocked")}
    for name, (valid, reason) in exp.items():
        tr = json.loads((sess / name / "transcript.json").read_text())
        reason_ok = reason is None or tr["http"].get(reason, 0) >= 1
        report[name] = {"valid": tr["valid"], "http": tr["http"], "expected_valid": valid,
                        "expected_reason": reason, "reason_observed": reason_ok,
                        "first_response": tr["calls"][0]["content"][0]["text"][:160]}
        ok &= tr["valid"] == valid and reason_ok
    report["phase0_passed"] = bool(ok)
    (vdir / "phase0/phase0_check.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
