#!/usr/bin/env python3
"""Pre-freeze self-test of the reference code on PREVIOUSLY SEEN files only (WP1 archive:
2026-10-30, 2026-08-16, 2026-08-17). Checks that classify.py reproduces the WP1 reference values.
No sampled file is read. Usage: python -I selftest_wp1.py WP1_BASE_ARCHIVE OUT_DIR"""
import json
import subprocess
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
PKG = HERE.parent
wp1, out = sys.argv[1], Path(sys.argv[2])
EXPECT = {  # WP1 references.json / Boston Table 3 (window (0, 48] h)
    "2d_20261030_8443970": {"n": 480, "bias": -0.00050, "rmse": 0.12300, "mae": 0.09999, "r": 0.99338},
    "3d_20261030_8443970": {"n": 480, "bias": -0.14300, "rmse": 0.24555, "mae": 0.20861, "r": 0.99132},
    "3d_20260816_8443970": {"n": 480, "bias": -0.1235, "rmse": 0.2676, "mae": 0.2141, "r": 0.99713},
    "3d_20260817_8443970": {"n": 480, "bias": -0.0354, "rmse": 0.2111, "mae": 0.1852, "r": 0.99590},
}
res = {"checks": [], "passed": True}
for lead_end in (48.0, 49.7):
    od = out / f"w{lead_end:g}"
    subprocess.run([sys.executable, "-I", str(HERE / "classify.py"), "--models", wp1, "--coops", wp1,
                    "--meta", str(PKG / "data/archive/meta"), "--lists", str(PKG / "phase0/coops"),
                    "--out", str(od), "--lead-start", "0", "--lead-end", str(lead_end),
                    "--cycles", "20261030", "20260816", "20260817", "--allow-gaps"], check=True, capture_output=True)
    cases = {json.loads(l)["case_id"]: json.loads(l) for l in (od / "cases.jsonl").read_text().splitlines()}
    files = [json.loads(l) for l in (od / "files.jsonl").read_text().splitlines()]
    if lead_end == 48.0:
        for cid, exp in EXPECT.items():
            st = cases[cid]["statistics"]
            ok = st["n"] == exp["n"] and all(abs(st[k] - exp[k]) <= 5e-5 for k in ("bias", "rmse", "mae", "r"))
            res["checks"].append({"check": cid, "expected": exp, "got": {k: st[k] for k in exp}, "ok": ok})
        c = cases["3d_20261030_9751381"]
        ok = c["model_counts_all"]["implausible"] == 1200 and c["model_code_like_all"] == 1200 and c["expected"]["expected"] == "refuse"
        res["checks"].append({"check": "3d_20261030_9751381 all 1200 code-like, expected refuse", "ok": ok})
        c = cases["2d_20261030_8571421"]
        ok = c["model_counts_all"]["implausible"] == 47 and c["model_code_like_all"] == 47
        res["checks"].append({"check": "2d_20261030_8571421 47 code-like (-99998.6)", "ok": ok})
        c = cases["3d_20261030_8443970"]
        ok = c["observations"]["counts"]["flagged_any"] == 110 and c["observations"]["counts"]["flag_O"] == 110
        res["checks"].append({"check": "Boston 110 flagged observations, all O", "ok": ok})
    else:
        ok = all(f["window_records"] == 497 and f["window_grid_n"] == 497 and f["window_covered_by_file"] for f in files)
        res["checks"].append({"check": "window (0, 49.7] h holds 497 records in every file", "ok": ok,
                              "got": [f["window_records"] for f in files]})
res["passed"] = all(c["ok"] for c in res["checks"])
(HERE / "selftest_wp1.json").write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps({"passed": res["passed"], "n_checks": len(res["checks"])}))
sys.exit(0 if res["passed"] else 1)
