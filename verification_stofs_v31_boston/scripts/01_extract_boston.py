"""Step 1: extract the Boston (8443970) series and all metadata from the raw files.

Independent of Ocean-MCP: reads the NetCDF with netCDF4 directly. Writes
data/derived/boston_<model>.json (small, archived) so later steps can replay
offline. Every record is kept, with a validity flag and the reason when it
is not usable; no value is altered or replaced.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/01_extract_boston.py
"""

from __future__ import annotations

import math
import sys

import netCDF4
import numpy as np

import _common as c


def attrs(obj) -> dict:
    out = {}
    for k in obj.ncattrs():
        v = obj.getncattr(k)
        if isinstance(v, (np.floating, float)):
            v = float(v) if math.isfinite(float(v)) else str(v)
        elif isinstance(v, np.integer):
            v = int(v)
        elif isinstance(v, np.ndarray):
            v = v.tolist()
        out[k] = v
    return out


def station_names(var) -> list[str]:
    data = np.ma.getdata(var[:])
    return ["".join(ch.decode() for ch in row if ch).strip() for row in data]


def extract(model: str, spec: dict) -> dict:
    path = c.RAW / spec["file"]
    nc = netCDF4.Dataset(str(path))
    try:
        names = station_names(nc["station_name"])
        matches = [i for i, n in enumerate(names) if c.STATION in n.split()]
        if len(matches) != 1:
            sys.exit(f"{model}: expected one record for {c.STATION}, found {matches}")
        i = matches[0]

        tvar = nc["time"]
        units = tvar.units.split("!")[0].strip()  # ADCIRC pads units with "! NCDASE…"
        times = netCDF4.num2date(tvar[:], units, only_use_cftime_datetimes=False)
        iso = [t.strftime("%Y-%m-%d %H:%M:%S") for t in times]
        # timedelta arithmetic only: naive .timestamp() would apply local DST
        # (US DST ended 2026-11-01, inside this window).
        steps = [(b - a).total_seconds() for a, b in zip(times[:-1], times[1:])]

        zvar = nc["zeta"]
        raw = zvar[:, i]
        mask = np.ma.getmaskarray(raw)
        data = np.asarray(np.ma.getdata(raw), dtype=float)
        fill = getattr(zvar, "_FillValue", None)
        records = []
        reasons = {"masked": 0, "fill": 0, "nonfinite": 0}
        for t, v, m in zip(iso, data.tolist(), mask.tolist()):
            if m:
                reason = "masked"
            elif not math.isfinite(v):
                reason = "nonfinite"
            elif (fill is not None and v == float(fill)) or abs(v) > 1e10:
                reason = "fill"
            else:
                reason = None
            if reason:
                reasons[reason] += 1
            records.append(
                {
                    "time": t,
                    "value_m": v if math.isfinite(v) else None,
                    "excluded": reason,
                }
            )
        return {
            "model": model,
            "label": spec["label"],
            "source_url": spec["url"],
            "source_file": spec["file"],
            "source_sha256": c.sha256(path),
            "station_index": i,
            "station_name": names[i],
            "x_raw": float(nc["x"][i]),
            "y_raw": float(nc["y"][i]),
            "global_attributes": attrs(nc),
            "zeta_attributes": attrs(zvar),
            "time_units": tvar.units,
            "time_units_used": units,
            "n_records": len(records),
            "time_step_seconds": sorted({int(s) for s in steps}),
            "first_time": iso[0],
            "last_time": iso[-1],
            "excluded_counts": reasons,
            "records": records,
        }
    finally:
        nc.close()


def main() -> int:
    for model, spec in c.STOFS_FILES.items():
        out = extract(model, spec)
        c.dump_json(out, c.DERIVED / f"boston_{model}.json")
        print(
            f"{model}: {out['station_name']} idx={out['station_index']} "
            f"x={out['x_raw']:.5f} y={out['y_raw']:.5f} n={out['n_records']} "
            f"{out['first_time']} .. {out['last_time']} step={out['time_step_seconds']} "
            f"excluded={out['excluded_counts']}"
        )
        print(f"   zeta: {out['zeta_attributes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
