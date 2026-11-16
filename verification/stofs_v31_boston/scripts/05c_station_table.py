"""Step 5c: every STOFS-3D station of the 2026-10-30 12z file, for the all-station
reference check (steps 5d, 5e).

For each station: ID, name, coordinates, the hourly values at lead 0..48 h,
and whether its values are no-data sentinels (|v| >= 1e4 m). For sentinel
stations whose every value is 1e7 + c, c is recorded: it is the constant
NOAA's xGEOID20b->LMSL post-processing added to a 1e7 no-data value, so it
exposes NOAA's own conversion constant without involving any grid.
Writes data/derived/stations_3d_20261030.json.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/05c_station_table.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import netCDF4
import numpy as np

import _common as c


def main() -> int:
    path = c.RAW / c.STOFS_FILES["3d_atlantic"]["file"]
    nc = netCDF4.Dataset(str(path))
    try:
        names = [
            "".join(ch.decode() for ch in r if ch).strip()
            for r in np.ma.getdata(nc["station_name"][:])
        ]
        x = np.asarray(nc["x"][:], dtype=float)
        y = np.asarray(nc["y"][:], dtype=float)
        tvar = nc["time"]
        times = netCDF4.num2date(tvar[:], tvar.units, only_use_cftime_datetimes=False)
        zraw = nc["zeta"][:]
        zeta = np.asarray(np.ma.getdata(zraw), dtype=float)
        mask = np.ma.getmaskarray(zraw)
    finally:
        nc.close()
    cycle = datetime.strptime(c.CYCLE_ISO, "%Y-%m-%d %H:%M")
    hours = [cycle + timedelta(hours=h) for h in range(49)]
    index = {
        datetime(t.year, t.month, t.day, t.hour, t.minute): i
        for i, t in enumerate(times)
    }
    rows = []
    for k, name in enumerate(names):
        ids = [tok for tok in name.split() if tok.isdigit() and len(tok) == 7]
        col = zeta[:, k]
        sentinel = bool(np.all(np.abs(col) >= 1e4))
        row = {
            "index": k,
            "station_id": ids[0] if ids else None,
            "name": name,
            "lat": float(y[k]),
            "lon": float(x[k]),
            "masked_records": int(mask[:, k].sum()),
            "sentinel": sentinel,
        }
        if sentinel and np.allclose(col, col[0]) and abs(col[0] - 1e7) < 10:
            row["sentinel_constant_c_m"] = float(col[0] - 1e7)
        if not sentinel and not mask[:, k].any():
            row["hourly_lead_0_48_m"] = [float(col[index[h]]) for h in hours]
        rows.append(row)
    assert all(r["lat"] > 0 and r["lon"] < 0 for r in rows), "v3.1 file: x is longitude"
    c.dump_json(
        {
            "source_file": c.STOFS_FILES["3d_atlantic"]["file"],
            "source_sha256": c.sha256(path),
            "hours": [h.strftime("%Y-%m-%d %H:%M") for h in hours],
            "stations": rows,
        },
        c.DERIVED / "stations_3d_20261030.json",
    )
    n_sent = sum(r["sentinel"] for r in rows)
    print(
        f"{len(rows)} stations; {n_sent} sentinel; with c: "
        f"{[(r['station_id'], round(r['sentinel_constant_c_m'], 4)) for r in rows if 'sentinel_constant_c_m' in r]}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
