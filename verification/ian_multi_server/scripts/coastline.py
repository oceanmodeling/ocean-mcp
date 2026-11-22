"""Coastline for panel (a) from the archived Natural Earth 1:50m shapefile (standard library only).

Natural Earth is the package's one non-MCP input (archive/non_mcp/natural_earth/SOURCE.md).
This reads the .shp (ESRI shapefile, polyline records) directly, checks its SHA-256, and
writes every part with at least one vertex inside the map extent plus a 1 degree margin to
results/coastline_subset.json, as [lon, lat] vertices rounded to 1e-4 degree. Nothing is
simplified or smoothed.

    python3 -I scripts/coastline.py
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SHP = PACKAGE / "archive" / "non_mcp" / "natural_earth" / "ne_50m_coastline.shp"
SHP_SHA256 = "797d675af9613f80b51ab6049fa32e589974d7a97c6497ca56772965f179ed26"
EXTENT = (-89.5, -79.0, 16.0, 31.0)  # lon min, lon max, lat min, lat max (the map, DESIGN/A5)
MARGIN = 1.0


def polylines(raw: bytes):
    """Yield the parts of every polyline record as lists of (lon, lat)."""
    if struct.unpack(">i", raw[0:4])[0] != 9994 or struct.unpack("<i", raw[32:36])[0] != 3:
        raise SystemExit("not a polyline shapefile")
    pos = 100
    while pos < len(raw):
        _num, length = struct.unpack(">2i", raw[pos : pos + 8])
        content = raw[pos + 8 : pos + 8 + 2 * length]
        pos += 8 + 2 * length
        if struct.unpack("<i", content[0:4])[0] == 0:
            continue  # null shape
        nparts, npoints = struct.unpack("<2i", content[36:44])
        parts = list(struct.unpack(f"<{nparts}i", content[44 : 44 + 4 * nparts]))
        off = 44 + 4 * nparts
        pts = struct.unpack(f"<{2 * npoints}d", content[off : off + 16 * npoints])
        xy = list(zip(pts[0::2], pts[1::2]))
        for a, b in zip(parts, parts[1:] + [npoints]):
            yield xy[a:b]


def main() -> None:
    raw = SHP.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != SHP_SHA256:
        raise SystemExit(f"{SHP}: SHA-256 {sha} != {SHP_SHA256}")
    x0, x1, y0, y1 = EXTENT
    keep = []
    n_parts = 0
    for part in polylines(raw):
        n_parts += 1
        if any(x0 - MARGIN <= x <= x1 + MARGIN and y0 - MARGIN <= y <= y1 + MARGIN for x, y in part):
            keep.append([[round(x, 4), round(y, 4)] for x, y in part])
    out = {
        "source": "Natural Earth 1:50m coastline, archive/non_mcp/natural_earth/ne_50m_coastline.shp",
        "shp_sha256": sha,
        "extent_lon_lat": EXTENT,
        "margin_deg": MARGIN,
        "parts_in_file": n_parts,
        "parts_kept": len(keep),
        "vertices_kept": sum(len(p) for p in keep),
        "polylines": keep,
    }
    path = PACKAGE / "results" / "coastline_subset.json"
    path.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"coastline: {len(keep)} of {n_parts} parts, {out['vertices_kept']} vertices")


if __name__ == "__main__":
    main()
