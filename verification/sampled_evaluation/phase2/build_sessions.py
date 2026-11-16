#!/usr/bin/env python3
"""Session specs from the reference case list and the frozen call templates (DESIGN.md 5.3).

One spec per (version, product, cycle) for stofs-mcp 0.3.0 post-fix and 0.2.0, and one coops-mcp
spec. Calls are in case_id order. Writes run_log/specs/<version>/<product>_<YYYYMMDD>.json.
Usage: python -I build_sessions.py CASES.jsonl
"""
import json, sys
from pathlib import Path
PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "analysis"))
import study1_outcomes as g  # noqa: E402  (call templates only)

ENVS = PKG / ".envs"
ARCH = [str(PKG / "data/archive" / a) for a in ("models", "coops", "meta", "templates")]
SERVERS = {
    "stofs030": {"python": str(ENVS / "stofs030post/bin/python"), "module": "stofs_mcp", "archives": ARCH,
                 "dists": ["stofs-mcp", "mcp", "httpx", "netCDF4", "numpy"], "template": g.call_030},
    "stofs020": {"python": str(ENVS / "stofs020/bin/python"), "module": "stofs_mcp", "archives": ARCH,
                 "dists": ["stofs-mcp", "mcp", "httpx", "netCDF4", "numpy"], "template": g.call_020},
}


def main() -> int:
    cases = [json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines()]
    groups = {}
    for c in sorted(cases, key=lambda c: c["case_id"]):
        groups.setdefault((c["product"], c["cycle"][:10].replace("-", "")), []).append(c)
    n = 0
    for ver, srv in SERVERS.items():
        od = PKG / "run_log/specs" / ver
        od.mkdir(parents=True, exist_ok=True)
        for (prod, day), cs in sorted(groups.items()):
            spec = {"session_id": f"{ver}_{prod}_{day}",
                    "server": {k: v for k, v in srv.items() if k != "template"},
                    "calls": [srv["template"](c) for c in cs]}
            (od / f"{prod}_{day}.json").write_text(json.dumps(spec, indent=1) + "\n")
            n += 1
    ids = sorted({c["station_id"] for c in cases})
    od = PKG / "run_log/specs/coops011"
    od.mkdir(parents=True, exist_ok=True)
    (od / "datums.json").write_text(json.dumps({
        "session_id": "coops011_datums",
        "server": {"python": str(ENVS / "coops/bin/python"), "module": "coops_mcp",
                   "archives": [str(PKG / "data/archive/meta")], "dists": ["coops-mcp", "mcp", "httpx"]},
        "calls": [g.call_coops(s) for s in ids]}, indent=1) + "\n")
    print(json.dumps({"stofs_specs": n, "cases": len(cases), "coops_calls": len(ids)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
