# Source of `stofs3d_20260218_t12z_excerpt.json`

This is a verbatim excerpt of a real NOAA file. The excerpt holds raw stored values (netCDF4
masking and scaling off) for 5 of the 108 stations, and the first 5 time records.

| | |
|---|---|
| File | `https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/stofs_3d_atl.20260218/stofs_3d_atl.t12z.points.cwl.nc` |
| SHA-256 | `d13345a36695ac69ff463f52f6f5dc187639e65a068a33626d9ab2090ca633b5` (5,509,661 bytes) |
| Product | STOFS-3D-Atlantic v2.1.18 (from the `history` attribute); `zeta` above NAVD88 |
| Retrieved | 2026-11-06. The second manuscript review recorded the same SHA-256 |

**Stations, with their indices in the source file:**

- **Stored reversed** (`x` holds the latitude): 0 Eastport and 3 Boston. In the whole file, 105 of
  the 108 records are like this.
- **Stored as their attributes say:** 53 Trident Pier, 82 Lake Charles and 95 San Luis Pass. These
  are the file's only three such records.

**How it was extracted:**

```python
ds = netCDF4.Dataset(src); ds.set_auto_maskandscale(False)
for i in (0, 3, 53, 82, 95):
    name, x, y = station_name[i], ds["x"][i], ds["y"][i]
    zeta = ds["zeta"][:5, i]
```

The excerpt also copies the time units and values, the `zeta` attributes, and the global `title`,
`source` and `history`.
