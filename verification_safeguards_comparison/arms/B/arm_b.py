#!/usr/bin/env python3
"""Arm B, validated Python: arm A's libraries plus explicit, cited domain rules.

The rules were written for this comparison from NOAA documentation, CF
conventions and physical reasoning. Every rule carries the identifier used in
the answers' texts (e.g. [B-D1]) and its source in a comment. This file does not
import, copy or paraphrase Ocean-MCP code.

Documents cited (archived copies are listed in data/manifest.json):
  SCN26-51  NWS Service Change Notice 26-51, STOFS v3.1 (weather.gov/media/notification/pdf_2026/scn26-51_STOFS.v3.1.pdf)
  PORTAL3D  polar.ncep.noaa.gov/estofs/atl.htm (STOFS-3D-Atlantic)
  NOMADS2D  nomads.ncep.noaa.gov/txt_descriptions/STOFS_Global_txt.html
  COOPSAPI  api.tidesandcurrents.noaa.gov/api/prod/ (datum, time_zone, units)
  COOPSRESP api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html (v, s, f, q fields)
  COOPSDAT  tidesandcurrents.noaa.gov datums page for a station (MSL is a tidal datum of the
            National Tidal Datum Epoch 1983-2001)
  NDBC      www.ndbc.noaa.gov/faq/measdes.shtml (missing-value codes)
  CF        CF Conventions 1.x, section 4 (coordinate attributes) and the CF standard name table
  ERDDAP    ERDDAP documentation: missing values are written as null in .json tables

Usage: python -I arm_b.py <verification_dir>
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from archive_io import Stack, importable_check, write_answer  # noqa: E402

# ---------------------------------------------------------------- rules ---
# [B-Q1] Physical bound for coastal water level relative to a tidal or geodetic
# datum. Source: the largest astronomical tidal range is about 16 m (Bay of Fundy,
# NOAA Ocean Service "Where is the highest tide?"), i.e. amplitude about 8 m, and the
# largest recorded storm surges are about 8 to 13 m. A value more than 30 m from
# the datum cannot be a water level. Values of 9,999 m or more are additionally
# described as no-data codes (they are orders of magnitude beyond any water level).
WL_BOUND_M = 30.0
NO_DATA_MAGNITUDE = 9999.0

# [B-W1] NDBC historical files mark missing data with a variable number of 9s
# (NDBC: "a variable number of 9's are used to denote missing data in the
# Historical files, depending on the data type (for example: 999.0 99.0)").
# For WVHT the code in these files is 99.00. A significant wave height above
# 30 m is also physically impossible (the largest buoy-measured Hs is about 19 m).
NDBC_MISSING_STRINGS = {"99", "99.0", "99.00", "999", "999.0", "9999", "9999.0"}
WVHT_BOUND_M = 30.0

# [B-D1] Documented station datum by product and version.
#   STOFS-3D-Atlantic v3.1: station netCDF output referenced to LMSL "(no longer NAVD88)" [SCN26-51];
#   implemented at the 12 UTC cycle of 2026-08-17 [PORTAL3D]. Before v3.1 (v2.1): NAVD88 [SCN26-51].
#   STOFS-2D-Global: "referenced to Local Mean Sea Level (LMSL) for gridded and station output"
#   [NOMADS2D], the description of the operational v3.1 product. SCN26-51 lists no datum change
#   for STOFS-2D-Global in the v3.1 upgrade; only v3.1 is treated as documented here.
DOCUMENTED = {("3d_atlantic", "2.1"): "NAVD88", ("3d_atlantic", "3.1"): "LMSL", ("2d_global", "3.1"): "LMSL"}
DOC_NAME = {("3d_atlantic", "2.1"): "SCN 26-51 (station output was NAVD88 before v3.1)",
            ("3d_atlantic", "3.1"): "SCN 26-51 (v3.1 station output referenced to LMSL)",
            ("2d_global", "3.1"): "NOMADS STOFS-Global product description (station output referenced to LMSL)"}

# [B-D2] Observation datum for a model datum, in CO-OPS API datum names [COOPSAPI].
COOPS_FOR = {"LMSL": "MSL", "NAVD88": "NAVD"}

# [B-D3] Label classifier for the zeta standard_name/long_name. Tokens are matched
# on word boundaries after replacing '_' by ' '. CF standard names include
# sea_surface_height_above_mean_sea_level and sea_surface_height_above_geoid [CF];
# 'geoid' names a geopotential surface, not a vertical datum of the station output.
LABEL_PATTERNS = [
    ("NAVD88", re.compile(r"\bnavd ?88\b|\bnorth american vertical datum of 1988\b")),
    ("LMSL", re.compile(r"\b(l?msl|(local )?mean sea level)\b")),
    ("MLLW", re.compile(r"\bmllw\b|\bmean lower low water\b")),
    ("GENERIC", re.compile(r"\bgeoid\b")),
]
OTHER_DATUM = re.compile(r"\b(ngvd|navd ?20\d\d|igld|xgeoid\w*|nad ?83|itrf\w*|wgs ?84|stnd|mhhw|mhw|mlw|mtl)\b")

# [B-C1] STOFS-3D-Atlantic is the Atlantic-basin model for the U.S. East and Gulf coasts,
# Puerto Rico and the U.S. Virgin Islands [PORTAL3D]: every station lies north of the
# equator and west of Greenwich, roughly 15-47 N and 100-60 W. The x/y attributes say
# longitude/latitude [CF]; a pair that falls outside the domain as labelled but inside
# it when exchanged is stored reversed.
DOMAIN_3D = {"lat": (15.0, 47.0), "lon": (-100.0, -60.0)}

EARTH_RADIUS_KM = 6371.0088


def answer(task, **kw):
    a = {"task_id": task["id"], "arm": "B", "status": "answered", "action": "proceed", "values": {},
         "nearest_equivalent": False, "nearest_equivalent_note": None, "metadata": {}, "texts": [],
         "exclusions": [], "evidence": {}}
    a.update(kw)
    return a


def refuse(task, reason, **kw):
    return answer(task, status="refused", action="refuse", texts=[reason], **kw)


# ------------------------------------------------------------- helpers ---
def open_station_file(stack, url):
    ds = xr.open_dataset(stack.path_for_url(url))
    raw = ds["station_name"].values
    names = [(r.decode() if isinstance(r, bytes) else b"".join(r).decode()).strip() for r in raw]
    return ds, names


def find_station(names, sid):
    hits = [i for i, n in enumerate(names) if sid in n.split()]
    if len(hits) != 1:
        raise LookupError(f"station {sid}: {len(hits)} records")
    return hits[0]


def product_version(model, ds):
    """[B-D1] Version from the file: 2D global title 'STOFS_2D_GLOBAL.Vx.y.z'; 3D history 'stofs.vx.y.z'."""
    if model == "2d_global":
        m = re.search(r"STOFS_2D_GLOBAL\.V(\d+)\.(\d+)\.(\d+)", ds.attrs.get("title", ""))
        src = "global attribute title"
    else:
        m = re.search(r"stofs\.v(\d+)\.(\d+)\.(\d+)", ds.attrs.get("history", ""))
        src = "global attribute history (package path)"
    if not m:
        return None, None, src
    return ".".join(m.groups()), f"{m.group(1)}.{m.group(2)}", src


def classify_label(text):
    t = (text or "").lower().replace("_", " ")
    found = {name for name, rx in LABEL_PATTERNS if rx.search(t)}
    if OTHER_DATUM.search(t):
        found.add("OTHER")
    return found


def resolve_datum(model, ds):
    """[B-D1]/[B-D3]: return dict(datum|None, source, caveats, refusal)."""
    z = ds["zeta"]
    labels = {k: z.attrs.get(k) for k in ("standard_name", "long_name") if z.attrs.get(k) is not None}
    classes = {k: classify_label(v) for k, v in labels.items()}
    version, major_minor, vsrc = product_version(model, ds)
    doc = DOCUMENTED.get((model, major_minor))
    specific = set().union(*classes.values()) - {"GENERIC"} if classes else set()
    out = {"labels": labels, "version": version, "version_source": vsrc, "documented": doc, "caveats": []}
    if "OTHER" in specific:
        out["refusal"] = (f"[B-D3] The datum label {labels} names a datum other than LMSL or NAVD88; "
                          "no like-for-like CO-OPS comparison is defined. Not compared.")
        return out
    if len(specific) > 1:
        out["refusal"] = (f"[B-D3] Conflicting datum labels on zeta: {labels} name {sorted(specific)}. "
                          "Neither can be trusted; not compared.")
        return out
    if len(specific) == 1:
        label_datum = specific.pop()
        if doc and doc != label_datum:
            out["refusal"] = (f"[B-D1] The file label says {label_datum} but NOAA documentation for version "
                              f"{version} says {doc} ({DOC_NAME[(model, major_minor)]}). Not compared.")
            return out
        out["datum"] = label_datum
        out["source"] = (f"file label zeta {labels}" + (f"; consistent with {DOC_NAME[(model, major_minor)]}"
                                                         if doc else ""))
        if not doc:
            out["caveats"].append(f"[B-D1] Version {version} is not covered by the documentation consulted; the "
                                  "datum is taken from the file label alone.")
        return out
    # no specific label: generic ('geoid') or absent
    if model == "3d_atlantic":
        out["refusal"] = (f"[B-D3] The zeta variable carries no datum label ({labels or 'no standard_name or '
                          'long_name'}). STOFS-3D station output is labelled in NOAA files and its datum changed "
                          f"at v3.1; documentation for {version} alone does not establish the datum of this file. "
                          "Datum undetermined; not compared.")
        return out
    if doc:
        out["datum"] = doc
        out["source"] = f"NOAA documentation: {DOC_NAME[(model, major_minor)]}"
        out["caveats"].append(f"[B-D1] The file label {labels} names no datum ('geoid' is a generic surface); the "
                              f"datum {doc} is taken from NOAA documentation for version {version}.")
        return out
    out["refusal"] = (f"[B-D1] The file label {labels} names no datum, and product version {version or 'unknown'} "
                      "is not documented (documented: STOFS_2D_GLOBAL V3.1). Datum undetermined; not compared.")
    return out


def valid_model_mask(values, ds):
    """[B-Q1] plus declared no-data: returns (valid mask, counts by reason)."""
    v = np.asarray(values, dtype=float)
    counts = {}
    nonfinite = ~np.isfinite(v)  # includes _FillValue, masked to NaN by default CF decoding
    counts["fill_or_nonfinite"] = int(nonfinite.sum())
    dry = np.zeros_like(nonfinite)
    dry_value = ds.attrs.get("dry_Value")  # ADCIRC global attribute declaring the dry flag
    if dry_value is not None:
        dry = np.isfinite(v) & (v == float(dry_value))
    counts["declared_dry_value"] = int(dry.sum())
    with np.errstate(invalid="ignore"):
        beyond = np.isfinite(v) & ~dry & (np.abs(v) > WL_BOUND_M)
    counts["beyond_physical_bound"] = int(beyond.sum())
    counts["of_which_no_data_magnitude"] = int((beyond & (np.abs(v) >= NO_DATA_MAGNITUDE)).sum())
    return ~(nonfinite | dry | beyond), counts


def model_exclusion_entries(counts, what="model_records"):
    out = []
    for k in ("fill_or_nonfinite", "declared_dry_value", "beyond_physical_bound"):
        if counts.get(k):
            out.append({"what": what, "count": counts[k], "names": [], "reason": k})
    return out


def coops_observations(path):
    """[B-Q2] CO-OPS records: blank v is missing; non-numeric or non-finite v is invalid;
    |v| > bound is invalid [B-Q1]. Flags f and status q are kept and counted, not used to
    drop data (they are QC indicators [COOPSRESP])."""
    doc = json.loads(Path(path).read_text())
    rows, counts = [], {"blank": 0, "non_numeric": 0, "non_finite": 0, "beyond_bound": 0}
    q_status, flagged = {}, 0
    for r in doc["data"]:
        v = r.get("v")
        if v is None or str(v).strip() == "":
            counts["blank"] += 1
            continue
        try:
            x = float(v)
        except ValueError:
            counts["non_numeric"] += 1
            continue
        if not math.isfinite(x):
            counts["non_finite"] += 1
            continue
        if abs(x) > WL_BOUND_M:
            counts["beyond_bound"] += 1
            continue
        q_status[r.get("q")] = q_status.get(r.get("q"), 0) + 1
        if any(f not in ("0", "") for f in str(r.get("f", "")).split(",")[1:]):
            flagged += 1
        # [B-T1] time_zone=gmt was requested, so record times are UTC [COOPSAPI]
        rows.append((pd.Timestamp(r["t"]), x, r.get("q")))
    df = pd.DataFrame(rows, columns=["time", "obs", "q"])
    if df["time"].duplicated().any():
        raise ValueError("[B-T2] duplicate observation times")
    return df, counts, q_status, flagged


def compare(task, stack, model_key, station, cycle_date):
    url = next(i["url"] for i in task["inputs"] if i["url"].endswith(".nc"))
    ds, names = open_station_file(stack, url)
    i = find_station(names, station)
    res = resolve_datum(model_key, ds)
    meta = {"units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"},
            "product_version": {"value": res["version"], "source": res["version_source"]}}
    if "refusal" in res:
        meta["model_datum"] = {"value": "undetermined", "source": f"file labels {res['labels']}"}
        return refuse(task, res["refusal"], metadata=meta, evidence={"inputs": stack.used})
    datum = res["datum"]
    meta["model_datum"] = {"value": datum, "source": res["source"]}
    coops_datum = COOPS_FOR[datum]
    meta["obs_datum"] = {"value": coops_datum, "source": f"[B-D2] CO-OPS datum for {datum} (CO-OPS API datum names)"}
    # [B-T3] window from the cycle time, 0 < lead <= 48 h; the cycle is the one requested
    cyc = pd.Timestamp(cycle_date) + pd.Timedelta(hours=12)
    z = ds["zeta"].isel(station=i).to_series()
    t = z.index
    if t.has_duplicates or not t.is_monotonic_increasing:
        raise ValueError("[B-T2] model times not strictly increasing")
    lead = (t - cyc) / pd.Timedelta(hours=1)
    in_win = (lead > 0) & (lead <= 48)
    zwin = z[in_win]
    ok, counts = valid_model_mask(zwin.values, ds)
    texts = list(res["caveats"])
    excl = model_exclusion_entries(counts)
    if not ok.any():
        return refuse(task, (f"[B-Q1] No valid model value for {names[i]} in 0 < lead <= 48 h: all {len(zwin)} records "
                             f"excluded ({counts}); values such as {float(zwin.iloc[0]):.4f} m are no-data codes or "
                             "beyond any physical water level. Not compared."),
                      metadata=meta, exclusions=excl, evidence={"inputs": stack.used})
    model = zwin[ok].rename("model").reset_index()
    obs_path, _ = stack.coops_master(station, coops_datum, cyc.to_pydatetime() + timedelta(minutes=6),
                                     cyc.to_pydatetime() + timedelta(hours=48))
    obs, ocounts, q_status, flagged = coops_observations(obs_path)
    # [B-T2] one-to-one pairing on exact UTC timestamps (both series are on the 6-minute grid)
    merged = model.merge(obs, on="time", how="inner")
    ow = obs[(obs["time"] > cyc) & (obs["time"] <= cyc + pd.Timedelta(hours=48))]
    excl += [{"what": "obs_values", "count": c, "names": [], "reason": k} for k, c in ocounts.items() if c]
    err = merged["model"] - merged["obs"]
    values = {"n": int(len(merged)), "bias_m": float(err.mean()), "rmse_m": float(np.sqrt((err ** 2).mean())),
              "mae_m": float(err.abs().mean()), "r": float(np.corrcoef(merged["model"], merged["obs"])[0, 1])}
    if datum == "LMSL":
        # [B-D4] LMSL vs CO-OPS MSL: compatible labels, realizations not shown equivalent.
        texts.append("[B-D4] Model LMSL and CO-OPS MSL are both mean-sea-level datums and are treated as compatible, "
                     "but their equivalence is not established: CO-OPS MSL is the tidal datum of the 1983-2001 "
                     "National Tidal Datum Epoch [COOPSDAT], and NOAA does not state the epoch or realization of the "
                     "model's LMSL [SCN26-51, NOMADS2D]. A mean offset (bias) can therefore include a reference "
                     "difference; no vertical transformation was applied.")
    if q_status.get("p"):
        texts.append(f"[B-Q2] {int(merged['q'].eq('p').sum())} of {len(merged)} matched observations are CO-OPS "
                     "preliminary (q=p) and may be revised.")
    unmatched = int(len(model) - len(merged))
    if unmatched:
        texts.append(f"[B-T2] {unmatched} model records in the window had no observation at the same time.")
    if any(ocounts.values()):
        texts.append(f"[B-Q2] Observations excluded before pairing: {ocounts}.")
    if any(counts[k] for k in ("fill_or_nonfinite", "declared_dry_value", "beyond_physical_bound")):
        texts.append(f"[B-Q1] Model records excluded in the window: {counts}.")
    return answer(task, values=values, metadata=meta, texts=texts, exclusions=excl,
                  evidence={"pairs": int(len(merged)), "obs_in_window": int(len(ow)), "flagged_pairs_kept": flagged,
                            "q_status": q_status, "inputs": stack.used})


# --------------------------------------------------------------- tasks ---
def t_compare(task, stack):
    return compare(task, stack, task["model"], task["station"], task["cycle"])


def station_values(ds, i):
    return ds["zeta"].isel(station=i).values


def t_max(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    res = resolve_datum(task["model"], ds)
    z = ds["zeta"].values  # (time, station)
    ok, counts = valid_model_mask(z, ds)
    zz = np.where(ok, z, np.nan)
    have = ok.any(axis=0)
    mx = np.full(z.shape[1], np.nan)
    mx[have] = np.nanmax(zz[:, have], axis=0)
    order = [k for k in np.argsort(-np.nan_to_num(mx, nan=-np.inf)) if have[k]]
    top = [{"station": names[k], "max_m": float(mx[k])} for k in order[:5]]
    # stations whose records were removed by [B-Q1] (not those that are only dry or fill)
    beyond = np.isfinite(z) & (np.abs(z) > WL_BOUND_M)
    gone = [k for k in range(z.shape[1]) if beyond[:, k].any() and not have[k]]
    excl = [{"what": "stations", "count": 1, "names": [names[k]],
             "reason": f"all records excluded; {int(beyond[:, k].sum())} beyond the {WL_BOUND_M:g} m bound "
                       f"(e.g. {float(z[np.argmax(beyond[:, k]), k]):.4f} m)"} for k in gone]
    texts = [f"[B-Q1] Stations with no valid value, excluded from the ranking: {[names[k] for k in gone]}."] if gone else []
    texts += res.get("caveats", [])
    meta = {"units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"}}
    if "refusal" in res:
        meta["model_datum"] = {"value": "undetermined", "source": f"file labels {res['labels']}"}
        texts.append(res["refusal"].replace("not compared", "values reported without an established datum"))
    else:
        meta["model_datum"] = {"value": res["datum"], "source": res["source"]}
    return answer(task, values={"top": top, "station": top[0]["station"], "max_m": top[0]["max_m"]},
                  metadata=meta, texts=texts, exclusions=excl + model_exclusion_entries(counts, "model_values"),
                  evidence={"inputs": stack.used})


def t_station_min(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    i = find_station(names, task["station"])
    res = resolve_datum(task["model"], ds)
    v = station_values(ds, i)
    ok, counts = valid_model_mask(v, ds)
    excl = model_exclusion_entries(counts)
    texts = ([f"[B-Q1] Excluded records at {names[i]}: {counts}; distinct excluded values "
              f"{sorted(set(np.round(v[~ok & np.isfinite(v)], 4).tolist()))[:5]}."] if (~ok).any() else [])
    texts += res.get("caveats", [])
    return answer(task, values={"min_m": float(np.min(v[ok]))},
                  metadata={"model_datum": {"value": res.get("datum", "undetermined"), "source": res.get("source")},
                            "units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"}},
                  texts=texts, exclusions=excl, evidence={"valid": int(ok.sum()), "inputs": stack.used})


def t_station_datum(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    res = resolve_datum(task["model"], ds)
    meta = {"units": {"value": ds["zeta"].attrs.get("units"), "source": "zeta:units attribute"},
            "product_version": {"value": res["version"], "source": res["version_source"]}}
    if "refusal" in res:
        meta["model_datum"] = {"value": "undetermined", "source": f"file labels {res['labels']}"}
        return refuse(task, res["refusal"], metadata=meta)
    meta["model_datum"] = {"value": res["datum"], "source": res["source"]}
    return answer(task, metadata=meta, texts=res["caveats"], evidence={"labels": res["labels"], "inputs": stack.used})


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def in_domain(lat, lon):
    return DOMAIN_3D["lat"][0] <= lat <= DOMAIN_3D["lat"][1] and DOMAIN_3D["lon"][0] <= lon <= DOMAIN_3D["lon"][1]


def t_nearest(task, stack):
    ds, names = open_station_file(stack, task["inputs"][0]["url"])
    gauge = (42.3539, -71.0503)
    lats, lons, status = [], [], {"as_labelled": 0, "reversed_corrected": 0, "outside_domain_excluded": 0}
    for x, y in zip(ds["x"].values.tolist(), ds["y"].values.tolist()):
        if in_domain(y, x):  # [B-C1] as labelled: y latitude, x longitude
            lats.append(y), lons.append(x)
            status["as_labelled"] += 1
        elif in_domain(x, y):  # [B-C1] stored reversed
            lats.append(x), lons.append(y)
            status["reversed_corrected"] += 1
        else:
            lats.append(np.nan), lons.append(np.nan)
            status["outside_domain_excluded"] += 1
    d = haversine_km(gauge[0], gauge[1], np.array(lats), np.array(lons))
    k = int(np.nanargmin(d))
    texts = []
    if status["reversed_corrected"]:
        texts.append(f"[B-C1] {status['reversed_corrected']} of {len(names)} station records store latitude in x and "
                     "longitude in y (reversed relative to their attributes); they were swapped before the "
                     f"distance search. {status['outside_domain_excluded']} records outside the product domain "
                     "either way were excluded.")
    return answer(task, values={"station": names[k], "distance_km": float(d[k])}, texts=texts,
                  exclusions=[{"what": "station_coordinates", "count": status["outside_domain_excluded"], "names": [],
                               "reason": "outside the STOFS-3D-Atlantic domain"}] if status["outside_domain_excluded"] else [],
                  evidence={"coordinate_status": status, "inputs": stack.used})


def t_buoy_max(task, stack):
    p = stack.path_for_url(task["inputs"][0]["url"])
    df = pd.read_csv(p, sep=r"\s+", skiprows=[1], dtype=str)
    df.columns = [c.lstrip("#") for c in df.columns]
    w = df["WVHT"]
    missing = w.isin(NDBC_MISSING_STRINGS)  # [B-W1]
    x = pd.to_numeric(w.where(~missing), errors="coerce")
    beyond = x > WVHT_BOUND_M
    x = x.where(~beyond)
    k = x.idxmax()
    row = df.loc[k]
    t = f"{row['YY']}-{row['MM']}-{row['DD']} {row['hh']}:{row['mm']}"
    excl = [{"what": "records", "count": int(missing.sum()), "names": [], "reason": "NDBC historical missing code (99.00)"}]
    if beyond.any():
        excl.append({"what": "records", "count": int(beyond.sum()), "names": [], "reason": "WVHT beyond 30 m"})
    return answer(task, values={"max_wvht_m": float(x.max()), "time": t},
                  metadata={"units": {"value": "m", "source": "units header row of the file"}},
                  texts=[f"[B-W1] {int(missing.sum())} of {len(df)} rows hold the NDBC historical missing code "
                         "for WVHT (99.00) and were excluded."],
                  exclusions=excl, evidence={"valid": int(x.count()), "inputs": stack.used})


def t_residual(task, stack):
    names = ("coops_8725520_water_level_MLLW_20220927_29", "coops_8725520_predictions_MLLW_20220927_29")
    q_o, q_p = (stack.request_params(n) for n in names)
    # [B-R1] a residual needs both series on the same datum, units and time zone [COOPSAPI]
    for k in ("datum", "units", "time_zone"):
        if q_o[k] != q_p[k]:
            return refuse(task, f"[B-R1] observations and predictions differ in {k}: {q_o[k]} vs {q_p[k]}")
    wl = json.loads(stack.path_for_input(names[0]).read_text())
    pr = json.loads(stack.path_for_input(names[1]).read_text())
    o = pd.DataFrame(wl["data"])
    p = pd.DataFrame(pr["predictions"])
    o = o[o["v"].astype(str).str.strip() != ""]  # [B-Q2] blank = missing
    o["obs"] = o["v"].astype(float)
    p["pred"] = p["v"].astype(float)
    if o["t"].duplicated().any() or p["t"].duplicated().any():
        raise ValueError("[B-T2] duplicate times")
    m = o[["t", "obs", "q"]].merge(p[["t", "pred"]], on="t", how="inner")
    m["resid"] = (m["obs"] - m["pred"]).round(3)
    top = float(m["resid"].max())
    times = m.loc[m["resid"] == top, "t"].tolist()
    texts = [f"[B-R1] Residual = observed minus predicted on {q_o['datum']}, {len(m)} matched 6-minute times; "
             f"quality {m['q'].value_counts().to_dict()}."]
    if len(times) > 1:
        texts.append(f"[B-R1] The maximum is attained at {len(times)} times: {times}.")
    return answer(task, values={"residual_max_m": top, "times_utc": times},
                  metadata={"obs_datum": {"value": q_o["datum"], "source": "CO-OPS request parameter datum"},
                            "pred_datum": {"value": q_p["datum"], "source": "CO-OPS request parameter datum"},
                            "units": {"value": "m", "source": "CO-OPS request parameter units=metric"}},
                  texts=texts, evidence={"inputs": stack.used})


def t_griddap(task, stack):
    doc = json.loads(stack.path_for_input("erddap_jplMURSST41_subset").read_text())
    tab = doc["table"]
    j = tab["columnNames"].index("analysed_sst")
    vals = [r[j] for r in tab["rows"]]
    nulls = sum(1 for v in vals if v is None)  # [ERDDAP] null = missing value, never zero
    fin = [float(v) for v in vals if v is not None and math.isfinite(float(v))]
    units = tab["columnUnits"][j]
    return answer(task, values={"cells": len(vals), "finite": len(fin), "min": min(fin), "max": max(fin)},
                  metadata={"units": {"value": units, "source": "ERDDAP response columnUnits"}},
                  texts=[f"[B-E1] {nulls} of {len(vals)} cells are null (missing; land or masked) and are not "
                         "counted as values."],
                  exclusions=[{"what": "cells", "count": nulls, "names": [], "reason": "null (missing)"}],
                  evidence={"inputs": stack.used})


DISPATCH = {"compare": t_compare, "max": t_max, "station_min": t_station_min, "station_datum": t_station_datum,
            "nearest": t_nearest, "buoy_max": t_buoy_max, "residual": t_residual, "griddap": t_griddap}


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    tasks = json.loads((vdir / "tasks/tasks.json").read_text())["tasks"]
    log = {"arm": "B", "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python": sys.version.split()[0], "importable": importable_check(),
           "versions": {"numpy": np.__version__, "pandas": pd.__version__, "xarray": xr.__version__}, "tasks": {}}
    if any(log["importable"].values()):
        print("ABORT: an Ocean-MCP package, mcp or httpx is importable", log["importable"], file=sys.stderr)
        return 2
    for t in tasks:
        stack = Stack(vdir, t["archives"])
        try:
            a = DISPATCH[t["kind"]](t, stack)
        except Exception as exc:
            a = answer(t, status="error", action=None, texts=[f"{type(exc).__name__}: {exc}"])
        p = write_answer(vdir, "B", a)
        log["tasks"][t["id"]] = {"status": a["status"], "action": a["action"],
                                 "values": {k: v for k, v in a["values"].items() if k != "top"},
                                 "texts": [x[:200] for x in a["texts"]], "answer": str(p.relative_to(vdir))}
    (vdir / "run_log/arm_B.json").write_text(json.dumps(log, indent=1, default=str) + "\n")
    for k, v in log["tasks"].items():
        print(k, v["status"], v["action"], v["values"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
