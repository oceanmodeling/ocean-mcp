"""Step 5b: Boston station value minus the native xGEOID20b grid (a grid proxy).

STOFS-3D computes on xGEOID20b; its gridded GRIB2 output stays on xGEOID20b
while the station NetCDF is converted to LMSL. For the same cycle, station
value minus the gridded value at the nearest wet grid cell, compared with
VDatum's xGEOID20b->LMSL (step 5a), gives a residual. At a single site this
residual mixes any datum-conversion difference with station-versus-cell
differences (cell placement, regridding, local mean-level gradients). Step 5e
shows that across 115 stations it is centred on zero (median +0.0001 m), and
NOAA's own conversion constants equal VDatum at three of five sentinel sites
to within 1 mm: Boston's +0.041 m is a station-versus-grid-cell residual, NOT a
datum difference. Diagnostic only; nothing is applied to the comparison.

Needs pygrib and the GRIB2 files from `00_fetch_inputs.py --grib`.
Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/05b_lmsl_realization_check.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import numpy as np
import pygrib

import _common as c


def hav_km(lat1, lon1, lat2, lon2):
    p1, p2, l1, l2 = map(np.radians, (lat1, lat2, lon1, lon2))
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin((l2 - l1) / 2) ** 2
    )
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def main() -> int:
    ex = c.load_json(c.DERIVED / "boston_3d_atlantic.json")
    series = {
        datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S"): r["value_m"]
        for r in ex["records"]
        if not r["excluded"]
    }
    lat0, lon0 = ex["y_raw"], ex["x_raw"]
    cycle = datetime.strptime(c.CYCLE_ISO, "%Y-%m-%d %H:%M")
    files = sorted((c.RAW / "grib").glob("stofs_3d_atl.t12z.conus.east.f0*.grib2"))
    if len(files) != 49:
        sys.exit(
            f"expected 49 GRIB2 files, found {len(files)}; run 00_fetch_inputs.py --grib"
        )

    fields = []
    for f in files:
        msg = pygrib.open(str(f)).message(1)
        vals = msg.values
        vals = (
            np.ma.filled(vals.astype(float), np.nan)
            if np.ma.isMaskedArray(vals)
            else vals
        )
        vals = np.where(np.abs(vals) > 9000, np.nan, vals)
        fields.append((cycle + timedelta(hours=int(msg.forecastTime)), vals))
        if len(fields) == 1:
            lats, lons = msg.latlons()
            meta = {
                "discipline": msg.discipline,
                "parameterCategory": msg.parameterCategory,
                "parameterNumber": msg.parameterNumber,
                "grid": msg.gridType,
                "shape": list(vals.shape),
            }
    wet = np.all([np.isfinite(v) for _, v in fields], axis=0)
    dist = np.where(wet, hav_km(lat0, lon0, lats, lons), np.inf)
    order = np.argsort(dist, axis=None)[:3]
    cells = [np.unravel_index(k, dist.shape) for k in order]

    rows = []
    for cell in cells:
        diffs = np.array([series[t] - v[cell] for t, v in fields if t in series])
        rows.append(
            {
                "cell_index": [int(cell[0]), int(cell[1])],
                "cell_lat": float(lats[cell]),
                "cell_lon": float(lons[cell]),
                "distance_km": round(float(dist[cell]), 3),
                "n_hours": int(len(diffs)),
                "station_minus_grid_mean_m": round(float(diffs.mean()), 4),
                "station_minus_grid_sd_m": round(float(diffs.std()), 4),
            }
        )
    vd = c.load_json(c.RESULTS / "vdatum_boston.json")["offsets_m"]
    vd_lmsl = vd["xgeoid20b->lmsl"]["3d_atlantic_output_point"]
    nearest = rows[0]
    out = {
        "grib_message": meta,
        "station_point": {"lat": lat0, "lon": lon0},
        "nearest_wet_cells": rows,
        "vdatum_xgeoid20b_to_lmsl_m": vd_lmsl,
        "station_minus_grid_minus_vdatum_m": round(
            nearest["station_minus_grid_mean_m"] - vd_lmsl, 4
        ),
        "interpretation": (
            "Grid-proxy residual at one site: station (native mesh point) versus a "
            "2.5 km GRIB2 cell, minus VDatum. It mixes datum-conversion differences "
            "with station-versus-cell differences and cannot by itself be read as a "
            "datum difference. Across 115 STOFS-3D stations the same residual has a "
            "median of +0.0001 m (step 5e), so the Boston value is a station-versus-"
            "cell residual (inner harbour; one wet cell within 3 km), not a datum "
            "difference. The 5.3 and 5.5 km cells are compared with the same Boston "
            "series, so they do not corroborate it independently."
        ),
    }
    c.dump_json(out, c.RESULTS / "lmsl_realization_check.json")
    for r in rows:
        print(r)
    print(
        "VDatum xGEOID20b->LMSL:",
        round(vd_lmsl, 4),
        "| station - grid - VDatum (grid-proxy residual):",
        out["station_minus_grid_minus_vdatum_m"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
