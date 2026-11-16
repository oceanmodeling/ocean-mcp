# Rules implemented by arm B

These rules were written for this comparison from NOAA documentation, CF conventions and physical
reasoning. Each identifier appears in `arm_b.py` next to its source and in the answers' texts. None
is imported, copied or paraphrased from Ocean-MCP.

The author had read Ocean-MCP's source and reports before writing these rules (see DESIGN.md §6).
Where a choice existed, arm B uses its own:

- a 30 m physical bound (Ocean-MCP uses 50 m and 10⁴ m);
- a product-domain test for reversed coordinates (Ocean-MCP uses a sign pattern);
- refusal when a STOFS-3D file has no datum label.

| Rule | What it does | Source |
|---|---|---|
| B-D1 | Product version is read from the file: STOFS-2D global `title` (`STOFS_2D_GLOBAL.Vx.y.z`); STOFS-3D `history` (`stofs.vx.y.z`). The documented station datum is then: 3D v2.1 NAVD88, 3D v3.1 LMSL, 2D v3.1 LMSL. Other versions are undocumented | SCN 26-51 ("no longer NAVD88"); STOFS-3D portal (v3.1 from 2026-08-17 12z); NOMADS STOFS-Global description (station output LMSL) |
| B-D3 | Labels: `standard_name` and `long_name` are classified by token (NAVD88; LMSL/MSL/mean sea level; MLLW; generic "geoid"; any other datum name).<br>• Two specific datums: refuse (conflict).<br>• Another datum name: refuse.<br>• A label that disagrees with the documented datum for the version: refuse.<br>• STOFS-3D without a label: refuse (datum undetermined).<br>• STOFS-2D generic label: datum from documentation if the version is documented, otherwise refuse | CF standard name table (`sea_surface_height_above_mean_sea_level`, `…_above_geoid`); SCN 26-51 |
| B-D2 | CO-OPS observation datum: LMSL → `MSL`, NAVD88 → `NAVD` | CO-OPS Data API, datum options |
| B-D4 | LMSL against CO-OPS MSL: proceeds with the caveat that the labels are compatible, but equivalence (epoch, realization) is not established | CO-OPS datums (MSL of the 1983–2001 NTDE); SCN 26-51 and NOMADS do not state the model LMSL's epoch |
| B-Q1 | Model values excluded and counted by reason: `_FillValue` / non-finite; equal to the file's declared `dry_Value`; \|v\| > 30 m (values ≥ 9,999 m are described as no-data codes). A station with no valid value is excluded and named | Physical bound: largest tidal range about 16 m (Bay of Fundy), largest surges about 8–13 m; ADCIRC `dry_Value` global attribute |
| B-Q2 | CO-OPS observations: blank `v` is missing; non-numeric, non-finite or \|v\| > 30 m is invalid. Each is excluded and counted. Flags `f` and status `q` are kept and counted, not used to drop data. Preliminary data are stated | CO-OPS response help (fields v, s, f, q) |
| B-T1 to B-T3 | Times are UTC (`time_zone=gmt`). Model times must be strictly increasing, and duplicates are an error. Window: 0 < lead ≤ 48 h from the requested cycle. Pairing: one-to-one on exact UTC timestamps (both series on the 6-minute grid). Unmatched records are counted | CO-OPS Data API (time_zone); CF time coordinate |
| B-C1 | STOFS-3D coordinates: a station must lie in the product domain (15–47 N, 100–60 W). A pair outside it as labelled but inside it when exchanged is stored reversed: it is swapped and reported. A pair outside it either way is excluded | STOFS-3D-Atlantic portal (Atlantic basin: U.S. East and Gulf coasts, Puerto Rico, USVI); CF x/y attributes |
| B-W1 | NDBC historical files: values written as the documented 9-fill codes (`99.00`, `99.0`, `999`, …) are missing; WVHT > 30 m is excluded. Both are counted | NDBC measurement descriptions (historical files use 9s for missing data) |
| B-E1 | ERDDAP `.json` null is missing, never zero; units are taken from `columnUnits` | ERDDAP documentation |
| B-R1 | A residual requires observations and predictions on the same datum, units and time zone. It is observed minus predicted on exact times; ties are reported | CO-OPS Data API |
