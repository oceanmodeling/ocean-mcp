"""Step 5e: is NOAA's STOFS-3D station LMSL the VDatum LMSL? All-station check.

Two independent lines of evidence, for the 2026-10-30 12z cycle:

(a) Sentinel constants. Five stations hold 1e7 + c for every record; c is the
    constant NOAA's xGEOID20b->LMSL post-processing added (step 5c). Compare c
    with VDatum xGEOID20b->LMSL at the same point. No grid is involved.

(b) Station minus grid. For each valid station with a wet GRIB2 cell (finite in
    all 49 hourly fields) within 4 km, residual = mean over lead 0..48 h of
    (station value - xGEOID20b grid value at that cell) - VDatum
    xGEOID20b->LMSL at the station. Only stations whose hourly station-minus-grid
    SD is below 5 cm are kept (the cell tracks the station's tide); these are
    the criteria of the 2026-11-04 independent audit (which reported n = 115).

A residual mixes any datum-conversion difference with station-versus-cell
differences (cell placement, regridding, local mean-level gradients). A
distribution centred on zero says NOAA's conversion matches VDatum; the
spread bounds how well a single site can be judged with this proxy.
Writes results/allstations_grid_vs_vdatum.json.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/05e_grid_vs_vdatum_allstations.py
"""

from __future__ import annotations

import sys

import numpy as np
import pygrib

import _common as c

MAX_KM = 4.0
MAX_SD_M = 0.05


def hav_km(lat1, lon1, lat2, lon2):
    p1, p2, l1, l2 = map(np.radians, (lat1, lat2, lon1, lon2))
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin((l2 - l1) / 2) ** 2
    )
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def main() -> int:
    table = c.load_json(c.DERIVED / "stations_3d_20261030.json")
    stations = table["stations"]
    vd = c.load_json(c.RESULTS / "vdatum_allstations.json")["xgeoid20b_to_lmsl_m"]

    files = sorted((c.RAW / "grib").glob("stofs_3d_atl.t12z.conus.east.f0*.grib2"))
    if len(files) != 49:
        sys.exit(
            f"expected 49 GRIB2 files, found {len(files)}; run 00_fetch_inputs.py --grib"
        )
    fields = []
    for f in files:
        msg = pygrib.open(str(f)).message(1)
        v = msg.values
        v = np.ma.filled(v.astype(float), np.nan) if np.ma.isMaskedArray(v) else v
        fields.append(np.where(np.abs(v) > 9000, np.nan, v))
        if len(fields) == 1:
            lats, lons = msg.latlons()
    stack = np.stack(fields)  # (49, ny, nx); lead 0..48 h in file order
    wet = np.all(np.isfinite(stack), axis=0)

    # (a) sentinel constants vs VDatum
    sentinel_rows = []
    for s in stations:
        if "sentinel_constant_c_m" in s:
            v = vd[str(s["index"])]
            sentinel_rows.append(
                {
                    "station_id": s["station_id"],
                    "name": s["name"],
                    "noaa_c_m": round(s["sentinel_constant_c_m"], 4),
                    "vdatum_xgeoid20b_to_lmsl_m": None if v is None else round(v, 4),
                    "noaa_minus_vdatum_m": None
                    if v is None
                    else round(s["sentinel_constant_c_m"] - v, 4),
                }
            )

    # (b) station minus grid vs VDatum
    rows = []
    for s in stations:
        series = s.get("hourly_lead_0_48_m")
        v = vd[str(s["index"])]
        if series is None or v is None:
            continue
        dist = np.where(wet, hav_km(s["lat"], s["lon"], lats, lons), np.inf)
        cell = np.unravel_index(np.argmin(dist), dist.shape)
        if dist[cell] > MAX_KM:
            continue
        diff = np.array(series) - stack[:, cell[0], cell[1]]
        rows.append(
            {
                "station_id": s["station_id"],
                "name": s["name"],
                "lat": s["lat"],
                "cell_km": round(float(dist[cell]), 3),
                "station_minus_grid_mean_m": round(float(diff.mean()), 4),
                "station_minus_grid_sd_m": round(float(diff.std()), 4),
                "vdatum_m": round(v, 4),
                "residual_m": round(float(diff.mean()) - v, 4),
            }
        )
    kept = [r for r in rows if r["station_minus_grid_sd_m"] < MAX_SD_M]
    res = np.array([r["residual_m"] for r in kept])
    ne = np.array([r["residual_m"] for r in kept if r["lat"] > 40])
    boston = next(r for r in kept if r["station_id"] == c.STATION)
    rank = int((np.abs(res) < abs(boston["residual_m"])).sum())
    summary = {
        "criteria": f"wet cell within {MAX_KM} km and station-minus-grid SD < {MAX_SD_M} m",
        "stations_with_wet_cell_within_4km": len(rows),
        "n": int(res.size),
        "median_m": round(float(np.median(res)), 4),
        "mean_m": round(float(res.mean()), 4),
        "sd_m": round(float(res.std(ddof=1)), 4),
        "sd_population_m": round(float(res.std(ddof=0)), 4),
        "p10_p90_m": [
            round(float(np.percentile(res, 10)), 4),
            round(float(np.percentile(res, 90)), 4),
        ],
        "northeast_lat_gt_40": {
            "n": int(ne.size),
            "median_m": round(float(np.median(ne)), 4),
            "sd_m": round(float(ne.std(ddof=1)), 4),
            "sd_population_m": round(float(ne.std(ddof=0)), 4),
            "boston_rank_by_abs_residual": 1
            + sum(
                1
                for r in kept
                if r["lat"] > 40 and abs(r["residual_m"]) > abs(boston["residual_m"])
            ),
        },
        "boston": boston,
        "boston_abs_residual_percentile": round(100.0 * rank / res.size, 1),
        "largest_abs_residuals": sorted(kept, key=lambda r: -abs(r["residual_m"]))[:6],
    }
    c.dump_json(
        {"sentinel_constants": sentinel_rows, "summary": summary, "stations": kept},
        c.RESULTS / "allstations_grid_vs_vdatum.json",
    )
    for r in sentinel_rows:
        print("sentinel", r)
    print(
        {k: summary[k] for k in summary if k not in ("largest_abs_residuals", "boston")}
    )
    print(
        "boston",
        boston,
        "abs-residual percentile",
        summary["boston_abs_residual_percentile"],
    )
    for r in summary["largest_abs_residuals"]:
        print(
            "  largest", r["station_id"], r["name"][-28:], r["residual_m"], r["cell_km"]
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
