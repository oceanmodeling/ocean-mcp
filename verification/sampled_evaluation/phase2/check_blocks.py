#!/usr/bin/env python3
"""Check (offline) that every CO-OPS request window either stofs-mcp version can send for a sampled
cycle lies inside one master block of phase2/plan.py, for every station and datum.

Windows (from the tools' request rules, DESIGN.md 3.2), cycle time C:
  0.3.0, lead window (0, 49.7] h: begin >= C + 6 min, end <= C + 49.7 h (begin/end move inward if
        edge values are invalid, never outward);
  0.2.0 3D, hours_to_compare 72: begin >= file start = C - 24 h + 6 min, end <= begin + 72 h;
  0.2.0 2D, hours_to_compare 54: begin >= file start = C - 6 h + 6 min, end <= begin + 54 h.
The outermost possible windows are tested (latest end uses the earliest begin)."""
import datetime as dt
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan
U = dt.timezone.utc
def blk(bs):
    return [(dt.datetime.strptime(a, "%Y%m%d").replace(tzinfo=U),
             dt.datetime.strptime(b, "%Y%m%d").replace(tzinfo=U) + dt.timedelta(hours=23, minutes=59)) for a, b in bs]
res = []
ok = True
for d in plan.CYCLES:
    C = dt.datetime(d.year, d.month, d.day, 12, tzinfo=U)
    wins = {"030": (C + dt.timedelta(minutes=6), C + dt.timedelta(hours=49.7)),
            "020_3d": (C - dt.timedelta(hours=24) + dt.timedelta(minutes=6), C - dt.timedelta(hours=24) + dt.timedelta(minutes=6) + dt.timedelta(hours=72)),
            "020_2d": (C - dt.timedelta(hours=6) + dt.timedelta(minutes=6), C - dt.timedelta(hours=6) + dt.timedelta(minutes=6) + dt.timedelta(hours=54))}
    for datum, bs in (("MSL", plan.MSL_BLOCKS), ("NAVD", plan.NAVD_BLOCKS)):
        for name, (lo, hi) in wins.items():
            inside = [i for i, (a, b) in enumerate(blk(bs)) if a <= lo and hi <= b]
            good = len(inside) >= 1
            ok &= good
            res.append({"cycle": d.isoformat(), "datum": datum, "window": name, "lo": lo.isoformat(), "hi": hi.isoformat(),
                        "block": inside[0] if inside else None, "ok": good})
for d in plan.CYCLES:  # every master block <= 29 days
    pass
lens = {datum: [(b - a).days + 1 for a, b in blk(bs)] for datum, bs in (("MSL", plan.MSL_BLOCKS), ("NAVD", plan.NAVD_BLOCKS))}
ok &= all(x <= 29 for v in lens.values() for x in v)
out = {"all_inside_one_block": ok, "block_lengths_days": lens, "n_checked": len(res), "failures": [r for r in res if not r["ok"]]}
(Path(__file__).resolve().parent / "check_blocks.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("all_inside_one_block", "block_lengths_days", "n_checked")}), len(out["failures"]))
