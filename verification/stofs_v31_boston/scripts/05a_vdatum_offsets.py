"""Step 5a: VDatum vertical offsets at the Boston gauge and the two model points.

Runs in the vdatum-mcp environment (vendored NOAA coastalmodeling-vdatum; it
downloads its transformation grids on first use). Converts z = 0 from the
source to the target datum, i.e. reports where the target surface's zero lies.
Writes results/vdatum_boston.json.

Usage (from the repository root):
  uv run --project servers/vdatum-mcp python verification_stofs_v31_boston/scripts/05a_vdatum_offsets.py
"""

from __future__ import annotations

import sys

import numpy as np
from vdatum_mcp._vendor.coastalmodeling_vdatum import _path, vdatum

import _common as c

PAIRS = [("xgeoid20b", "lmsl"), ("xgeoid20b", "navd88"), ("navd88", "lmsl")]


def main() -> int:
    points = {"coops_gauge": (42.3539, -71.05028)}
    for model in c.STOFS_FILES:
        ex = c.load_json(c.DERIVED / f"boston_{model}.json")
        points[f"{model}_output_point"] = (ex["y_raw"], ex["x_raw"])
    names = list(points)
    lat = np.array([points[n][0] for n in names])
    lon = np.array([points[n][1] for n in names])
    out = {
        "points": {n: {"lat": points[n][0], "lon": points[n][1]} for n in names},
        "grids": {k: getattr(_path, k) for k in dir(_path) if k.isupper()},
        "method": "vdatum.convert(src, dst, lat, lon, z=0, online=True)",
        "offsets_m": {},
    }
    for src, dst in PAIRS:
        _, _, z = vdatum.convert(
            src, dst, lat.copy(), lon.copy(), np.zeros(len(names)), online=True
        )
        out["offsets_m"][f"{src}->{dst}"] = {
            n: (float(v) if np.isfinite(v) else None) for n, v in zip(names, z)
        }
        print(f"{src}->{dst}:", {n: round(float(v), 4) for n, v in zip(names, z)})
    c.dump_json(out, c.RESULTS / "vdatum_boston.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
