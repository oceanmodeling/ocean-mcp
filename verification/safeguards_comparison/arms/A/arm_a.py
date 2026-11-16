#!/usr/bin/env python3
"""Arm A, basic Python: ordinary scientific libraries used as documented.

What this arm does, deliberately and only:
  * NetCDF: ``xarray.open_dataset`` with default decoding (CF time decoding;
    ``_FillValue`` masked to NaN). Station names decoded from the char array.
  * CO-OPS JSON: ``pandas.DataFrame`` of the records, ``pd.to_numeric(errors="coerce")``
    for values, ``pd.to_datetime`` for times; an inner join on time; statistics
    with pandas defaults (NaN skipped).
  * Datum: one fixed pairing taken from current product documentation, the same
    for every file: STOFS-2D-Global and STOFS-3D-Atlantic station output are
    LMSL (NOMADS STOFS-Global description; SCN 26-51), compared with CO-OPS
    datum MSL. The file's own labels are not read.
  * No domain rules: no plausibility bounds, no datum checks, no quality or
    coordinate checks, no caveats.

Usage: python -I arm_a.py <verification_dir>
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from archive_io import Stack, importable_check, write_answer  # noqa: E402

FIXED_PAIRING = {
    "2d_global": ("LMSL", "fixed pairing from current product documentation (NOMADS STOFS-Global product description)"),
    "3d_atlantic": ("LMSL", "fixed pairing from current product documentation (NWS SCN 26-51, STOFS v3.1)"),
}
COOPS_DATUM = "MSL"


def answer(task, **kw):
    a = {"task_id": task["id"], "arm": "A", "status": "answered", "action": "proceed", "values": {},
         "nearest_equivalent": False, "nearest_equivalent_note": None, "metadata": {}, "texts": [],
         "exclusions": [], "evidence": {}}
    a.update(kw)
    return a


def open_station_file(stack, url):
    ds = xr.open_dataset(stack.path_for_url(url))
    raw = ds["station_name"].values  # xarray joins the char array into one bytes string per station
    names = [(r.decode() if isinstance(r, bytes) else b"".join(r).decode()).strip() for r in raw]
    return ds, names


def find_station(names, sid):
    return next(i for i, n in enumerate(names) if sid in n)


def cycle_time(task):
    return pd.Timestamp(task["cycle"]) + pd.Timedelta(hours=12)


def coops_frame(path):
    doc = json.loads(Path(path).read_text())
    df = pd.DataFrame(doc["data"])
    df["time"] = pd.to_datetime(df["t"])
    df["obs"] = pd.to_numeric(df["v"], errors="coerce")
    return df[["time", "obs"]]


def stats_of(merged):
    err = merged["model"] - merged["obs"]
    return {"n": int(len(merged)), "bias_m": float(err.mean()), "rmse_m": float(np.sqrt((err ** 2).mean())),
            "mae_m": float(err.abs().mean()), "r": float(merged["model"].corr(merged["obs"]))}


def version_attr(ds):
    return ds.attrs.get("title")


# --------------------------------------------------------------- tasks ---
def t_compare(task, stack):
    url = next(i["url"] for i in task["inputs"] if i["url"].endswith(".nc"))
    ds, names = open_station_file(stack, url)
    i = find_station(names, task["station"])
    cyc = cycle_time(task)
    z = ds["zeta"].isel(station=i).to_series()
    lead = (z.index - cyc) / pd.Timedelta(hours=1)
    model = z[(lead > 0) & (lead <= 48)].rename("model").reset_index()
    obs_path, _ = stack.coops_master(task["station"], COOPS_DATUM, cyc.to_pydatetime() + timedelta(minutes=6),
                                     cyc.to_pydatetime() + timedelta(hours=48))
    obs = coops_frame(obs_path)
    merged = model.merge(obs, on="time", how="inner")
    datum, src = FIXED_PAIRING[task["model"]]
    return answer(task, values=stats_of(merged), metadata={
        "model_datum": {"value": datum, "source": src},
        "obs_datum": {"value": COOPS_DATUM, "source": "CO-OPS request parameter datum=MSL (fixed pairing)"},
        "units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"},
        "product_version": {"value": version_attr(ds), "source": "global attribute title"}},
        evidence={"pairs": int(len(merged)), "inputs": stack.used})


def t_max(task, stack):
    url = task["inputs"][0]["url"]
    ds, names = open_station_file(stack, url)
    mx = ds["zeta"].max(dim="time").values
    order = np.argsort(-np.nan_to_num(mx, nan=-np.inf))
    top = [{"station": names[k], "max_m": float(mx[k])} for k in order[:5]]
    datum, src = FIXED_PAIRING[task["model"]]
    return answer(task, values={"top": top, "station": top[0]["station"], "max_m": top[0]["max_m"]}, metadata={
        "model_datum": {"value": datum, "source": src},
        "units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"}},
        evidence={"inputs": stack.used})


def t_station_min(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    i = find_station(names, task["station"])
    z = ds["zeta"].isel(station=i)
    datum, src = FIXED_PAIRING[task["model"]]
    return answer(task, values={"min_m": float(z.min())}, metadata={
        "model_datum": {"value": datum, "source": src},
        "units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"}},
        evidence={"inputs": stack.used})


def t_station_datum(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    datum, src = FIXED_PAIRING[task["model"]]
    return answer(task, values={}, metadata={
        "model_datum": {"value": datum, "source": src},
        "units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"},
        "product_version": {"value": version_attr(ds), "source": "global attribute title"}},
        evidence={"zeta_standard_name": ds["zeta"].attrs.get("standard_name"), "inputs": stack.used})


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def t_nearest(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    lat, lon = 42.3539, -71.0503
    # x is longitude and y is latitude, as the variables' attributes say
    d = haversine_km(lat, lon, ds["y"].values, ds["x"].values)
    k = int(np.nanargmin(d))
    return answer(task, values={"station": names[k], "distance_km": float(d[k])},
                  evidence={"x": float(ds["x"].values[k]), "y": float(ds["y"].values[k]), "inputs": stack.used})


def t_buoy_max(task, stack):
    p = stack.path_for_url(task["inputs"][0]["url"])
    df = pd.read_csv(p, sep=r"\s+", skiprows=[1])
    df.columns = [c.lstrip("#") for c in df.columns]
    k = df["WVHT"].idxmax()
    row = df.loc[k]
    t = f"{int(row['YY']):04d}-{int(row['MM']):02d}-{int(row['DD']):02d} {int(row['hh']):02d}:{int(row['mm']):02d}"
    return answer(task, values={"max_wvht_m": float(row["WVHT"]), "time": t},
                  metadata={"units": {"value": "m", "source": "units header row of the file (#yr mo ... m)"}},
                  evidence={"rows": int(len(df)), "inputs": stack.used})


def t_residual(task, stack):
    wl = json.loads(stack.path_for_input("coops_8725520_water_level_MLLW_20220927_29").read_text())
    pr = json.loads(stack.path_for_input("coops_8725520_predictions_MLLW_20220927_29").read_text())
    o = pd.DataFrame(wl["data"])
    p = pd.DataFrame(pr["predictions"])
    o["obs"] = pd.to_numeric(o["v"], errors="coerce")
    p["pred"] = pd.to_numeric(p["v"], errors="coerce")
    m = o[["t", "obs"]].merge(p[["t", "pred"]], on="t", how="inner")
    m["resid"] = (m["obs"] - m["pred"]).round(3)
    top = float(m["resid"].max())
    q_o = stack.request_params("coops_8725520_water_level_MLLW_20220927_29")
    q_p = stack.request_params("coops_8725520_predictions_MLLW_20220927_29")
    return answer(task, values={"residual_max_m": top, "times_utc": m.loc[m["resid"] == top, "t"].tolist()},
                  metadata={"obs_datum": {"value": q_o["datum"], "source": "CO-OPS request parameter datum"},
                            "pred_datum": {"value": q_p["datum"], "source": "CO-OPS request parameter datum"},
                            "units": {"value": "m", "source": "CO-OPS request parameter units=metric"}},
                  evidence={"pairs": int(len(m)), "inputs": stack.used})


def t_griddap(task, stack):
    doc = json.loads(stack.path_for_input("erddap_jplMURSST41_subset").read_text())
    tab = doc["table"]
    df = pd.DataFrame(tab["rows"], columns=tab["columnNames"])
    s = pd.to_numeric(df["analysed_sst"])
    units = tab["columnUnits"][tab["columnNames"].index("analysed_sst")]
    return answer(task, values={"cells": int(len(s)), "finite": int(s.count()), "min": float(s.min()),
                                "max": float(s.max())},
                  metadata={"units": {"value": units, "source": "ERDDAP response columnUnits"}},
                  evidence={"inputs": stack.used})


DISPATCH = {"compare": t_compare, "max": t_max, "station_min": t_station_min, "station_datum": t_station_datum,
            "nearest": t_nearest, "buoy_max": t_buoy_max, "residual": t_residual, "griddap": t_griddap}


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    log = {"arm": "A", "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python": sys.version.split()[0], "importable": importable_check(),
           "versions": {"numpy": np.__version__, "pandas": pd.__version__, "xarray": xr.__version__}, "tasks": {}}
    if any(log["importable"].values()):
        print("ABORT: an Ocean-MCP package, mcp or httpx is importable", log["importable"], file=sys.stderr)
        return 2
    for t in tasks:
        stack = Stack(vdir, t["archives"])
        try:
            a = DISPATCH[t["kind"]](t, stack)
        except Exception as exc:  # recorded, not hidden
            a = answer(t, status="error", action=None, texts=[f"{type(exc).__name__}: {exc}"])
        p = write_answer(vdir, "A", a)
        log["tasks"][t["id"]] = {"status": a["status"], "action": a["action"],
                                 "values": {k: (v if not isinstance(v, float) or math.isfinite(v) else str(v))
                                            for k, v in a["values"].items() if k != "top"},
                                 "answer": str(p.relative_to(vdir))}
    (vdir / "run_log/arm_A.json").write_text(json.dumps(log, indent=1, default=str) + "\n")
    print(json.dumps(log["tasks"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
