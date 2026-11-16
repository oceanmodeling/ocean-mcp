"""Step 5d: VDatum xGEOID20b->LMSL at every STOFS-3D station (vdatum-mcp environment).

Reads data/derived/stations_3d_20261030.json (step 5c); writes
results/vdatum_allstations.json. The vendored NOAA coastalmodeling-vdatum reads
its grids by HTTP range requests on first use.

Usage (from the repository root):
  uv run --project servers/vdatum-mcp python verification/stofs_v31_boston/scripts/05d_vdatum_allstations.py
"""

from __future__ import annotations

import sys

import numpy as np
from vdatum_mcp._vendor.coastalmodeling_vdatum import _path, vdatum

import _common as c


def main() -> int:
    table = c.load_json(c.DERIVED / "stations_3d_20261030.json")["stations"]
    lat = np.array([s["lat"] for s in table])
    lon = np.array([s["lon"] for s in table])
    _, _, z = vdatum.convert(
        "xgeoid20b", "lmsl", lat.copy(), lon.copy(), np.zeros(len(table)), online=True
    )
    out = {
        "method": "vdatum.convert('xgeoid20b', 'lmsl', lat, lon, z=0, online=True)",
        "grids": {k: getattr(_path, k) for k in dir(_path) if k.isupper()},
        "xgeoid20b_to_lmsl_m": {
            str(s["index"]): (float(v) if np.isfinite(v) else None)
            for s, v in zip(table, z)
        },
    }
    c.dump_json(out, c.RESULTS / "vdatum_allstations.json")
    finite = np.isfinite(z)
    print(f"{finite.sum()} of {len(z)} stations inside the VDatum domain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
