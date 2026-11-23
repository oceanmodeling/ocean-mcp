# Natural Earth 1:50m coastline (non-MCP input)

This is the only input of the package that does not come from an MCP tool. It draws the
coastline in panel (a) of the figures and is used for nothing else.

- **Dataset:** Natural Earth, "Coastline", 1:50m physical vectors.
  - Page: https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-coastline/
  - Terms: public domain (https://www.naturalearthdata.com/about/terms-of-use/).
- **Source of these files.** The cartopy 0.25.0 cache on the machine that made the figures (`~/.local/share/cartopy/shapefiles/natural_earth/physical/`), extracted on 2026-01-07.
  - cartopy fetches the archive from `https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_coastline.zip` (its `_NE_URL_TEMPLATE`).
  - The zip itself was not kept, so its checksum is unknown; the extracted files are archived here unchanged.
- **Version.** The DBF header is dated 2017-09-21. It holds 1428 records with fields `scalerank`, `featurecla`, `min_zoom`. The CRS is WGS 84 geographic (`.prj`).
- **Use.** `scripts/coastline.py` reads `.shp` with the standard library and writes the polylines that touch the map extent, plus a 1° margin, to `results/coastline_subset.json`. The figures draw that file. Nothing is simplified or smoothed.

| File | SHA-256 |
|---|---|
| ne_50m_coastline.shp | `797d675af9613f80b51ab6049fa32e589974d7a97c6497ca56772965f179ed26` |
| ne_50m_coastline.shx | `0ff1792f2d16b58246d074215edd9d12fa280880ecaad61a91b9382fee854065` |
| ne_50m_coastline.dbf | `f100fa5a99786c63ec9eb2cd430e389bc6235b8e26d2712d33f9bfd6cb6aadfc` |
| ne_50m_coastline.prj | `98aaf3d1c0ecadf1a424a4536de261c3daf4e373697cb86c40c43b989daf52eb` |
| ne_50m_coastline.cpg | `3ad3031f5503a4404af825262ee8232cc04d4ea6683d42c5dd0a2f2a27ac9824` |
