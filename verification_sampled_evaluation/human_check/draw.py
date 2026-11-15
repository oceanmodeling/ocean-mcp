#!/usr/bin/env python3
"""Draw the 30 human-check station-cycles (DESIGN.md 9). Frozen sampling rule:

* frame: every case in reference/results/w49_7/cases.jsonl, sorted by case_id;
* 20 cases by simple random sampling from the whole frame, then 10 more from the cases the
  reference marks as non-routine (expected outcome refuse or not_eligible, any invalid model
  value in the station series, a label/documentation mismatch, or a duplicated station ID),
  excluding the first 20; if fewer than 10 non-routine cases exist, all are taken and the
  remainder is filled from the frame;
* random.Random(SEED).sample, SEED = 20261109; the 30 are then shuffled with the same generator
  so the stratum is not visible from the order.

Per case it writes cases/<k>.png (raw model series of the whole file with the window shaded,
observed series on MSL and on NAVD where CO-OPS has them, no statistics, < 1600 px) and
cases/<k>.txt (the file's zeta and global datum attributes, the CO-OPS datum list and epoch for
the station). The tool's and the reference's outcomes go to SEALED_outcomes.json, whose SHA-256
is written to SEALED_outcomes.sha256. Run in Phase 3 (.envs/ref).
"""
import datetime as dt
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

SEED = 20261109
N_RANDOM, N_NONROUTINE = 20, 10
PKG = Path(__file__).resolve().parent.parent
HC = PKG / "human_check"


def non_routine(c: dict) -> bool:
    inv = sum(v for k, v in c["model_counts_all"].items() if k != "valid")
    return (c["expected"]["expected"] != "compare" or inv > 0
            or c["reference_datum_status"] not in ("label_matches_documentation", "documented_generic_label")
            or c["duplicate_id"] is not None)


def draw(cases: list[dict]) -> list[dict]:
    frame = sorted(cases, key=lambda c: c["case_id"])
    rng = random.Random(SEED)
    first = rng.sample(frame, N_RANDOM)
    ids = {c["case_id"] for c in first}
    pool = [c for c in frame if non_routine(c) and c["case_id"] not in ids]
    k = min(N_NONROUTINE, len(pool))
    second = rng.sample(pool, k)
    if k < N_NONROUTINE:
        rest = [c for c in frame if c["case_id"] not in ids | {x["case_id"] for x in second}]
        second += rng.sample(rest, N_NONROUTINE - k)
    chosen = [dict(c, _stratum="random") for c in first] + [dict(c, _stratum="non_routine") for c in second]
    rng.shuffle(chosen)
    return chosen


def render(chosen: list[dict]) -> None:
    sys.path.insert(0, str(PKG / "reference"))
    import archive_io as aio
    import rules
    from classify import load_datums
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import netCDF4
    import numpy as np
    models = {(f["product"], f["cycle"]): f for f in aio.model_files([aio.Archive(PKG / "data/archive/models")]) if f["variant"] == "cwl"}
    obs = aio.CoopsObs([aio.Archive(PKG / "data/archive/coops")])
    datums = load_datums([aio.Archive(PKG / "data/archive/meta")])
    out = HC / "cases"
    out.mkdir(parents=True, exist_ok=True)
    sealed = []
    t030 = {}
    for p in (PKG / "run_log/sessions/stofs030").glob("*/transcript.json.gz"):
        for call in json.load(gzip.open(p, "rt"))["calls"]:
            t030[call["call_id"]] = "".join(x.get("text", "") for x in call["content"] if x.get("type") == "text")
    outcomes = {}
    op = PKG / "results/study1/outcomes.jsonl"
    if op.exists():
        outcomes = {json.loads(x)["case_id"]: json.loads(x) for x in op.read_text().splitlines()}
    for k, c in enumerate(chosen, 1):
        cyc = dt.datetime.strptime(c["cycle"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        f = models[(c["product"], cyc)]
        nc = netCDF4.Dataset(str(f["archive"].path(f["entry"])))
        nc.set_auto_mask(False)
        tv = nc.variables["time"]
        t = rules.decode_times(np.asarray(tv[:]).tolist(), str(tv.units))
        zv = nc.variables["zeta"]
        z = np.asarray(zv[:, c["record_index"]], dtype=float)
        zat = {a: str(zv.getncattr(a)) for a in zv.ncattrs()}
        gat = {a: str(nc.getncattr(a))[:300] for a in nc.ncattrs()}
        nc.close()
        fig, axes = plt.subplots(2, 1, figsize=(12, 7))
        for ax, (lo, hi), title in ((axes[0], (t[0], t[-1]), "whole station file"),
                                    (axes[1], (cyc, cyc + dt.timedelta(hours=49.7)), "lead 0 to 49.7 h")):
            sel = [i for i, x in enumerate(t) if lo <= x <= hi]
            ax.plot([t[i] for i in sel], [z[i] for i in sel], lw=1, label="model, raw stored values")
            for dname, col in (("MSL", "#DD8452"), ("NAVD", "#55A868")):
                if (c["station_id"], dname) in obs.masters:
                    got = obs.records(c["station_id"], dname, lo, hi)
                    pts = [(tt, float(r["v"])) for tt, r in got["records"] if str(r.get("v", "")).strip() not in ("",)]
                    if pts:
                        ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=0.8, color=col,
                                label=f"CO-OPS observed, datum {dname}")
            ax.axvspan(cyc, cyc + dt.timedelta(hours=49.7), color="0.9", zorder=0)
            ax.axvline(cyc, color="0.4", lw=0.8)
            ax.set_title(f"case {k}: {c['product'].upper()} cycle {c['cycle']} UTC, station {c['station_id']} ({title})", fontsize=9)
            ax.set_ylabel("m")
            ax.legend(fontsize=7)
            ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / f"{k:02d}.png", dpi=100)
        plt.close(fig)
        m = datums.get(c["station_id"], {})
        (out / f"{k:02d}.txt").write_text(
            f"case {k}\nproduct {c['product']}  cycle {c['cycle']} UTC  station {c['station_id']}  record '{c['station_name']}'\n"
            f"file {f['entry']['url']}\nsha256 {f['entry']['response']['body_sha256']}\n\n"
            f"zeta attributes: {json.dumps(zat)}\nglobal attributes: {json.dumps(gat)}\n\n"
            f"CO-OPS datums (metadata API): epoch {m.get('epoch')}, values (m above station datum): {json.dumps(m.get('values'))}\n")
        o = outcomes.get(c["case_id"], {})
        sealed.append({"k": k, "case_id": c["case_id"], "stratum": c["_stratum"],
                       "reference_expected": c["expected"], "reference_datum": c["reference_datum"],
                       "reference_statistics": c["statistics"], "tool_class": o.get("class"), "tool_sub": o.get("sub"),
                       "tool_response_head": t030.get(c["case_id"], "")[:800]})
    sp = HC / "SEALED_outcomes.json"
    sp.write_text(json.dumps(sealed, indent=1) + "\n")
    (HC / "SEALED_outcomes.sha256").write_text(hashlib.sha256(sp.read_bytes()).hexdigest() + "  SEALED_outcomes.json\n")
    with open(HC / "classification_form.csv", "w") as fh:
        fh.write("case,model datum you would assume,CO-OPS datum to compare with,invalid model values (y/n and which),"
                 "your decision (compare / decline / cannot be compared),reason,notes\n")
        for k in range(1, len(chosen) + 1):
            fh.write(f"{k},,,,,,\n")


if __name__ == "__main__":
    cases = [json.loads(x) for x in (PKG / "reference/results/w49_7/cases.jsonl").read_text().splitlines()]
    chosen = draw(cases)
    render(chosen)
    print(json.dumps([c["case_id"] for c in chosen]))
