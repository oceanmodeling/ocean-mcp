#!/usr/bin/env python3
"""Extract a verbatim excerpt of a real STOFS-2D-Global station file with station ID 8414721 on
two records (WP7 Task C, D-2 tests). Raw stored values (netCDF4 masking and scaling off).

Source: the WP5 archive (eval/sampled-evaluation, data/archive/models), 2026-10-26 12z 2D file.
Writes servers/stofs-mcp/tests/fixtures/stofs2d_20261026_t12z_dup_excerpt.json.
Usage: python -I extract_dup_excerpt.py WP5_PACKAGE OUT_JSON
"""
import hashlib, json, sys
from pathlib import Path
import netCDF4
import numpy as np

pkg, out = Path(sys.argv[1]), Path(sys.argv[2])
URL = "https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.20261026/stofs_2d_glo.t12z.points.cwl.nc"
idx = json.loads((pkg / "data/archive/models/index.json").read_text())
e = next(x for x in idx["entries"] if x["url"] == URL)
src = pkg / "data/archive/models" / e["response"]["body_file"]
data = src.read_bytes()
assert hashlib.sha256(data).hexdigest() == e["response"]["body_sha256"]
ds = netCDF4.Dataset(str(src))
ds.set_auto_maskandscale(False)
names = [str(s).strip() for s in netCDF4.chartostring(ds.variables["station_name"][:])]
dup = [i for i, n in enumerate(names) if "8414721" in n]
other = next(i for i, n in enumerate(names) if "8418150" in n)
N_T = 180  # cycle - 6 h + 6 min .. cycle + 12 h
sel = dup + [other]
t = ds.variables["time"]
z = ds.variables["zeta"]
doc = {
    "description": "Verbatim excerpt of a real NOAA STOFS-2D-Global station file (raw stored values): "
                   "station ID 8414721 occurs on two records.",
    "source_url": URL, "source_sha256": e["response"]["body_sha256"], "source_bytes": len(data),
    "source_note": "Retrieved 2026-11-10 (WP5 Phase 2, data/archive/models). STOFS_2D_GLOBAL.V3.1.0.",
    "extracted_by": "verification_post_wp5/scripts/extract_dup_excerpt.py",
    "station_indices_in_source": sel,
    "global_attributes": {k: str(ds.getncattr(k)) for k in ds.ncattrs()},
    "time": {"units": str(t.units), "values": [float(v) for v in np.asarray(t[:N_T])]},
    "zeta_attributes": {k: (float(z.getncattr(k)) if k == "_FillValue" else str(z.getncattr(k))) for k in z.ncattrs()},
    "stations": [{"name": names[i], "x": float(ds.variables["x"][i]), "y": float(ds.variables["y"][i]),
                  "zeta": [float(v) for v in np.asarray(z[:N_T, i])]} for i in sel],
}
ds.close()
out.write_text(json.dumps(doc, indent=1) + "\n")
d = np.array(doc["stations"][0]["zeta"]) - np.array(doc["stations"][1]["zeta"])
print("records", sel, [names[i] for i in sel], "max |diff| over excerpt", float(np.max(np.abs(d))))
