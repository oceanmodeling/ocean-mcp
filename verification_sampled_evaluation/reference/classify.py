#!/usr/bin/env python3
"""WP5 reference classification and separate-code statistics, one record per case.

A case is (product, cycle, CO-OPS station ID) for every station record of a sampled station
file whose name maps to a CO-OPS water-level station (DESIGN.md 2.3). For each case this script
records, from the archived bytes only:

* the datum the file should carry by documentation, the label it carries, and the datum the
  reference pairs with (rules.reference_datum);
* model values in the whole station series and in the window, by class (fill, dry, nonfinite,
  implausible, valid), and every value with 20 m <= |v| <= 100 m;
* whether the station publishes the paired datum (CO-OPS metadata API datums.json) and its
  tidal-datum epoch;
* observations in the window on the paired datum, by class, with status and flags;
* exact-timestamp pairs and the statistics (bias, RMSE, MAE, max |e|, means, SDs, r);
* the expected outcome (compare / refuse / not_eligible) with all applicable reasons.

It imports no Ocean-MCP package (checked at start-up) and uses netCDF4 with auto-masking off,
so every stored value is seen as stored.

Usage:
  python -I classify.py --models DIR [--models DIR] --coops DIR [--coops DIR] --meta DIR \
      --lists DIR --out OUT_DIR [--lead-start 0 --lead-end 49.7] [--only-variant cwl]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import archive_io as aio  # noqa: E402
import rules  # noqa: E402

for _forbidden in ("stofs_mcp", "coops_mcp", "mcp", "httpx"):
    if _forbidden in sys.modules:
        raise SystemExit(f"reference code must not import {_forbidden}")

import netCDF4  # noqa: E402
import numpy as np  # noqa: E402

TOK = re.compile(r"(?<!\d)\d{7}(?!\d)")
UTC = dt.timezone.utc


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M")


def load_coops_station_lists(lists_dir: Path) -> tuple[dict, dict]:
    """CO-OPS metadata API station lists (type=waterlevels, type=historicwl), archived."""
    act = his = None
    for p in sorted(Path(lists_dir).glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict) or "stations" not in d:
            continue
        if d.get("count") and d["count"] < 1000:
            act = {s["id"]: s for s in d["stations"]}
        else:
            his = {s["id"]: s for s in d["stations"]}
    if act is None or his is None:
        raise SystemExit("both CO-OPS station lists (waterlevels, historicwl) are required")
    return act, his


def load_datums(meta_arcs: list[aio.Archive]) -> dict:
    """station id -> datums.json summary (from the CO-OPS metadata API)."""
    out = {}
    rx = re.compile(r"/mdapi/prod/webapi/stations/(\d{7})/datums\.json")
    for a in meta_arcs:
        for e in a.entries:
            m = rx.search(e["url"])
            if not m:
                continue
            sid = m.group(1)
            try:
                d = json.loads(a.body(e))
            except Exception as exc:  # pragma: no cover
                out[sid] = {"error": f"unreadable: {exc}"}
                continue
            vals = {x.get("name"): x.get("value") for x in (d.get("datums") or [])}
            out[sid] = {
                "epoch": d.get("epoch"),
                "analysis_period": d.get("DatumAnalysisPeriod"),
                "accepted": d.get("accepted"),
                "superseded": d.get("superseded"),
                "orthometric": d.get("OrthometricDatum"),
                "published": sorted(k for k, v in vals.items() if v is not None),
                "values": vals,
                "max": d.get("max"), "min": d.get("min"),
                "entry": e["id"], "sha256": e["response"]["body_sha256"],
            }
    return out


def epoch_class(epoch: str | None) -> str:
    if not epoch:
        return "none"
    m = re.match(r"\s*(\d{4})\s*-\s*(\d{4})", str(epoch))
    if not m:
        return "other"
    a, b = int(m.group(1)), int(m.group(2))
    if a == 0 or b == 0:
        return "unknown"
    if (a, b) == (1983, 2001):
        return "NTDE_1983_2001"
    if b - a + 1 <= 6:
        return "modified_5yr"
    return f"other_{a}_{b}"


def model_series(nc, idx: int):
    z = nc.variables["zeta"]
    return z[:, idx]


def classify_file(f: dict, act: dict, his: dict, datums: dict, obs: aio.CoopsObs,
                  lead_lo: float, lead_hi: float) -> tuple[list[dict], list[dict], dict]:
    path = f["archive"].path(f["entry"])
    nc = netCDF4.Dataset(str(path))
    nc.set_auto_mask(False)
    nc.set_auto_scale(True)
    try:
        g = {k: str(nc.getncattr(k)) for k in nc.ncattrs()}
        z = nc.variables["zeta"]
        zattrs = {k: z.getncattr(k) for k in z.ncattrs()}
        names = [str(s).strip() for s in netCDF4.chartostring(nc.variables["station_name"][:])]
        tvar = nc.variables["time"]
        times = rules.decode_times(np.asarray(tvar[:]).tolist(), str(tvar.units))
        Z = np.asarray(z[:], dtype=float)  # (time, station), raw stored values
        xs = np.asarray(nc.variables["x"][:], dtype=float) if "x" in nc.variables else None
        ys = np.asarray(nc.variables["y"][:], dtype=float) if "y" in nc.variables else None
    finally:
        nc.close()

    product, cycle = f["product"], f["cycle"]
    version = rules.product_version(product, g)
    if version is None:
        # frozen stop rule (DESIGN.md 4.1): a file whose version the reference cannot read halts
        # the classification for an amendment instead of turning the file into refusals
        raise SystemExit(f"STOP: version not readable in {f['entry']['url']} "
                         f"(title={g.get('title')!r}, history={g.get('history', '')[:200]!r})")
    doc = rules.documented_datum(product, version)
    lab = rules.label_datum(zattrs)
    refd = rules.reference_datum(product, doc, lab)
    fill = [float(np.asarray(zattrs[k]).ravel()[0]) for k in ("_FillValue", "missing_value") if k in zattrs]
    dry = [float(g["dry_Value"])] if "dry_Value" in g else []
    vrange = None
    if "valid_range" in zattrs:
        vr = np.asarray(zattrs["valid_range"]).ravel()
        vrange = (float(vr[0]), float(vr[1]))
    elif "valid_min" in zattrs or "valid_max" in zattrs:
        vrange = (float(zattrs.get("valid_min", -np.inf)), float(zattrs.get("valid_max", np.inf)))

    win = np.array([rules.in_window(t, cycle, lead_lo, lead_hi) for t in times])
    grid = rules.window_grid(cycle, lead_lo, lead_hi)
    on_grid = all((t - cycle).total_seconds() % (rules.STEP_MIN * 60) == 0 for t in times)
    file_info = {
        "product": product, "cycle": iso(cycle), "variant": f["variant"], "url": f["entry"]["url"],
        "sha256": f["entry"]["response"]["body_sha256"], "version": version,
        "documented": doc, "label": lab, "reference_datum": refd,
        "date_expectation": rules.date_expectation(product, cycle),
        "version_disagrees_with_portal_date": (version is not None and
            ".".join(version.split(".")[:2]) != rules.date_expectation(product, cycle)["portal"]),
        "fill_values": fill, "dry_values": dry, "valid_range": vrange,
        "n_records_time": len(times), "n_stations": len(names),
        "file_start": iso(times[0]), "file_end": iso(times[-1]),
        "times_on_6min_grid": on_grid,
        "window": [lead_lo, lead_hi], "window_records": int(win.sum()), "window_grid_n": len(grid),
        "window_covered_by_file": times[0] <= grid[0] and times[-1] >= grid[-1],
    }

    # every |v| in the report band, for all records of the file (mapped or not)
    band = []
    lo_b, hi_b = rules.REPORT_BAND_M
    with np.errstate(invalid="ignore"):
        hit = np.isfinite(Z) & (np.abs(Z) >= lo_b) & (np.abs(Z) <= hi_b)
    for ti, si in zip(*np.nonzero(hit)):
        band.append({"product": product, "cycle": iso(cycle), "station_index": int(si),
                     "station_name": names[si], "time": iso(times[ti]), "value_m": float(Z[ti, si]),
                     "in_window": bool(win[ti])})

    # station identity
    tokens = [TOK.findall(n) for n in names]
    first_rec: dict[str, int] = {}
    dup: dict[str, list[int]] = {}
    for i, toks in enumerate(tokens):
        m = [t for t in toks if t in act or t in his]
        if len(m) != 1:
            continue
        sid = m[0]
        dup.setdefault(sid, []).append(i)
        first_rec.setdefault(sid, i)

    cases = []
    for sid, idx in first_rec.items():
        col = Z[:, idx]
        cls = [rules.classify_model_value(float(v), fill, dry, vrange) for v in col]
        cls_arr = np.array(cls)
        counts_all = {c: int((cls_arr == c).sum()) for c in rules.MODEL_CLASSES}
        counts_win = {c: int(((cls_arr == c) & win).sum()) for c in rules.MODEL_CLASSES}
        code_like_all = int(((cls_arr == "implausible") & (np.abs(col) >= rules.CODE_LIKE_M)).sum())
        code_like_win = int(((cls_arr == "implausible") & (np.abs(col) >= rules.CODE_LIKE_M) & win).sum())
        valid_win = {times[i]: float(col[i]) for i in np.nonzero(win & (cls_arr == "valid"))[0]}

        recs = dup[sid]
        dup_info = None
        if len(recs) > 1:
            other = recs[1:]
            diffs = []
            for j in other:
                a, b = Z[win, idx], Z[win, j]
                ok = np.isfinite(a) & np.isfinite(b) & (np.abs(a) <= rules.PLAUSIBLE_BOUND_M) & (np.abs(b) <= rules.PLAUSIBLE_BOUND_M)
                diffs.append({"record": j, "name": names[j],
                              "max_abs_diff_in_window_m": float(np.max(np.abs(a[ok] - b[ok]))) if ok.any() else None,
                              "mean_diff_in_window_m": float(np.mean(a[ok] - b[ok])) if ok.any() else None})
            dup_info = {"records": recs, "names": [names[j] for j in recs], "others": diffs}
        substr_first = next((i for i, n in enumerate(names) if sid in n), None)

        meta = datums.get(sid)
        paired = rules.PAIRED_COOPS_DATUM.get(refd["datum"]) if refd["datum"] else None
        meta_published = None  # what the metadata API lists; reported, not used to decide
        if paired and meta and "published" in meta:
            meta_published = rules.MDAPI_DATUM_NAME[paired] in meta["published"]
        published = None  # what CO-OPS served for the paired datum (decides eligibility)

        # observations on the paired datum, window only
        obs_info = {"paired_datum": paired}
        pairs_m, pairs_o, pair_t = [], [], []
        if paired:
            got = obs.records(sid, paired, grid[0], grid[-1])
            published = got["served"] != "unsupported_datum" if got["served"] != "missing_master" else None
            oc = {"records": 0, "missing": 0, "nonfinite": 0, "implausible": 0, "valid": 0,
                  "verified": 0, "preliminary": 0, "other_status": 0, "flagged_any": 0,
                  "flag_O": 0, "flag_F": 0, "flag_R": 0, "flag_L": 0, "off_grid_times": 0}
            ovalid = {}
            for t, r in got["records"]:
                oc["records"] += 1
                c, v = rules.classify_obs_value(r.get("v"))
                oc[c] += 1
                if c != "valid":
                    continue
                if (t - cycle).total_seconds() % (rules.STEP_MIN * 60) != 0:
                    oc["off_grid_times"] += 1
                ovalid[t] = (v, r)
            for t in sorted(set(valid_win) & set(ovalid)):
                v, r = ovalid[t]
                pairs_m.append(valid_win[t])
                pairs_o.append(v)
                pair_t.append(t)
                q = r.get("q")
                oc["verified" if q == "v" else "preliminary" if q == "p" else "other_status"] += 1
                fl = rules.obs_flags(r.get("f"))
                for k, n in fl.items():
                    oc[f"flag_{k}"] += int(n > 0)
                oc["flagged_any"] += int(any(n > 0 for n in fl.values()))
            obs_info.update({"masters": got["masters"], "served": got["served"],
                             "fully_covered_by_masters": got["fully_covered"], "counts": oc,
                             "n_valid": oc["valid"]})
        st = rules.stats(pairs_m, pairs_o)
        exp = rules.expected_outcome(refd, len(valid_win), published, obs_info.get("n_valid", 0), len(pairs_m))

        sus = None  # report-only: model values beyond the station's recorded extremes by > 1 m
        if meta and meta.get("values", {}).get("MSL") is not None and meta.get("max") is not None:
            msl = meta["values"]["MSL"]
            hi_lim, lo_lim = meta["max"] - msl + 1.0, (meta["min"] - msl - 1.0) if meta.get("min") is not None else None
            if refd["datum"] == "LMSL":
                vv = np.array(list(valid_win.values()))
                if vv.size:
                    sus = {"above_record_plus_1m": int((vv > hi_lim).sum()),
                           "below_record_minus_1m": int((vv < lo_lim).sum()) if lo_lim is not None else None}

        cases.append({
            "case_id": f"{product}_{cycle:%Y%m%d}_{sid}", "product": product, "cycle": iso(cycle),
            "station_id": sid, "record_index": idx, "station_name": names[idx],
            "coops_list": "active" if sid in act else "historic",
            "great_lakes": bool((act.get(sid) or his.get(sid) or {}).get("greatlakes")),
            "duplicate_id": dup_info, "substring_first_record": substr_first,
            "substring_collision": substr_first is not None and substr_first != idx,
            "stored_x": float(xs[idx]) if xs is not None else None,
            "stored_y": float(ys[idx]) if ys is not None else None,
            "version": version, "documented_datum": doc["datum"], "label_status": lab["status"],
            "label_datum": lab["datum"], "reference_datum": refd["datum"],
            "reference_datum_status": refd["status"],
            "model_counts_all": counts_all, "model_counts_window": counts_win,
            "model_code_like_all": code_like_all, "model_code_like_window": code_like_win,
            "n_model_valid_window": len(valid_win),
            "coops_epoch": meta.get("epoch") if meta else None,
            "coops_epoch_class": epoch_class(meta.get("epoch")) if meta else "no_metadata",
            "paired_datum_published": published, "paired_datum_in_metadata": meta_published,
            "metadata_disagrees_with_served": (published is not None and meta_published is not None
                                               and published != meta_published),
            "acquisition_gap": bool(paired) and obs_info.get("served") == "missing_master",
            "observations": obs_info, "pairs_first_last": [iso(pair_t[0]), iso(pair_t[-1])] if pair_t else None,
            "statistics": st, "expected": exp, "suspicious_beyond_record": sus,
        })
    return cases, band, file_info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", action="append", required=True)
    ap.add_argument("--coops", action="append", required=True)
    ap.add_argument("--meta", action="append", default=[])
    ap.add_argument("--lists", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lead-start", type=float, default=rules.LEAD_START_H)
    ap.add_argument("--lead-end", type=float, default=rules.LEAD_END_H)
    ap.add_argument("--only-variant", default="cwl")
    ap.add_argument("--cycles", nargs="*", help="restrict to YYYYMMDD cycles")
    ap.add_argument("--allow-gaps", action="store_true",
                    help="self-test only: do not stop on cases whose observation masters are missing")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    act, his = load_coops_station_lists(Path(a.lists))
    datums = load_datums([aio.Archive(Path(p)) for p in a.meta])
    obs = aio.CoopsObs([aio.Archive(Path(p)) for p in a.coops])
    files = [f for f in aio.model_files([aio.Archive(Path(p)) for p in a.models]) if f["variant"] == a.only_variant]
    if a.cycles:
        files = [f for f in files if f["cycle"].strftime("%Y%m%d") in set(a.cycles)]
    files.sort(key=lambda f: (f["product"], f["cycle"]))
    n = 0
    with open(out / "cases.jsonl", "w") as fc, open(out / "band_20_100m.jsonl", "w") as fb, \
            open(out / "files.jsonl", "w") as ff:
        for f in files:
            cases, band, info = classify_file(f, act, his, datums, obs, a.lead_start, a.lead_end)
            for c in cases:
                fc.write(json.dumps(c, sort_keys=True) + "\n")
            for b in band:
                fb.write(json.dumps(b, sort_keys=True) + "\n")
            ff.write(json.dumps(info, sort_keys=True, default=str) + "\n")
            n += len(cases)
            gaps = [c["case_id"] for c in cases if c["acquisition_gap"]]
            if gaps and not a.allow_gaps:
                # frozen stop rule: a missing master is an acquisition gap, never "not eligible"
                raise SystemExit(f"STOP: {len(gaps)} cases without observation masters, e.g. {gaps[:5]}")
            print(f"{info['product']} {info['cycle']} v{info['version']} {info['reference_datum']['status']} "
                  f"cases={len(cases)} band={len(band)}", flush=True)
    print(json.dumps({"files": len(files), "cases": n, "window": [a.lead_start, a.lead_end]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
