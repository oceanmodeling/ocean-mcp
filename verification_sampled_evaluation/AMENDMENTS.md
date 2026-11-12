# Amendments to the WP5 design

Any change to DESIGN.md, `reference/`, `analysis/`, `human_check/draw.py`, `replay/` or
`phase2/plan.py` after the freeze commit (`2ea1e00`) is recorded here with its evidence, and
both results are kept.

## Amendments A1–A4 (requested by the author with "proceed", 2026-11-10)

**Recorded before any sampled model file was downloaded.** At the time of this record, the
only NOAA requests made are the 483 Phase 0 probes in `run_log/noaa_requests.jsonl`; no
`points.cwl.nc` or `points.cwl.noanomaly.nc` file of the sample and no CO-OPS observation
master has been fetched. None of A1–A4 changes the sampling rule, the outcome classes, the
primary slope reading or the request budget (cap 4,298).

The author's answers to the open questions: **Q1 = include** (the 30 `noanomaly` files, reference
code only); **Q2 = default** (preliminary observations counted, S7 restricts to verified).

### A1. Per-station datum consistency (new; offline; reference code only)

For every station that publishes both MSL and NAVD88 (datums.json, Phase 0; 217 of the 389),
compute

**d_s = Δ_V(s) − C_s**, with the sign convention fixed here before any computation:

- **Δ_V(s)** = the value VDatum returns when a height of 0.000 m on NAVD88 at the station's
  coordinates is converted to LMSL (`convert("navd88", "lmsl", lat, lon, z=0)`): the elevation of
  the NAVD88 zero surface above VDatum's LMSL surface, positive when NAVD88 lies above LMSL.
- **C_s** = `NAVD88` − `MSL` from the station's CO-OPS datums.json (both relative to station
  datum): the elevation of the NAVD88 zero above the CO-OPS MSL tidal datum, same sign sense.
- Hence **d_s = (CO-OPS MSL) − (VDatum LMSL)** as surfaces: **d_s > 0 means the CO-OPS MSL datum
  lies above VDatum's LMSL** at the station (relative to NAVD88). At Boston the Boston package
  found Δ_V = 0.0917 m and C_s = 2.752 − 2.660 = 0.092 m, so d ≈ −0.0003 m.

**Same library and grids as the Boston package:**
- **Library.** NOAA's `coastalmodeling_vdatum` as vendored in vdatum-mcp (upstream commit
  `0d63b2bbc0b0634e20a0ec55023a53354fab1b47`, CC0).
  - Its five files are copied unchanged into `reference/vendor_coastalmodeling_vdatum/`, with
    their SHA-256 recorded.
  - They are loaded as a stand-alone module, so no Ocean-MCP package is imported.
  - pyproj is 3.8.0 and numpy 2.5.4, as in the Boston package's vdatum environment freeze.
- **Pipeline.** `navd88 → lmsl` uses the grid `us_noaa_g2018u0.tif` (GEOID18), the NAD83(2011)
  epoch 2010 → ITRF2020 epoch 2020 Helmert steps of `_geoid_tr.py`, and the grid
  `us_noaa_nos_LMSL-ITRF2020_2020.0_nwldatum_4.7.0_20240621_3.tif`.
- **Grids, fetched in full.** The Boston package read these grids by HTTP range requests
  (`online=True`). Here each grid is downloaded once, through `phase0/noaa_fetch.py`:
  - the LMSL grid from `noaa-nos-stofs2d-pds.s3.amazonaws.com/_archive/coastalmodeling-vdatum/`;
  - GEOID18 from the PROJ CDN, `cdn.proj.org`, which the library's `online=True` mode uses.

  Both are logged with URL, time and SHA-256, and the transformation then runs with network
  access disabled and local grid paths (`_path` constants patched). The two requests come from
  the retry reserve, so the cap stays 4,298.
- **Check of sameness:** the offline result at the Boston gauge (42.3539, −71.05028) must equal
  the Boston package's `navd88->lmsl` value 0.09173215948229796 m within 1×10⁻⁶ m. If it does
  not, A1 is reported as not reproducing the Boston setup and its table is not used for S10.

**Coordinates:** the station coordinates of the CO-OPS metadata API station lists (archived in
Phase 0).

**Report:** the table of Δ_V, C_s, d_s, epoch and boundary flag for every station; the median,
SD and largest |d_s|; and the stations that could not be evaluated, with the reason (outside the
grids, NaN, or no coordinates).

**New sensitivity S10:** the primary Study 2 regression restricted to stations with
|d_s| ≤ 0.03 m.

### A2. Seasonal assumption in the carried fraction and the level test

- **Primary slope reading:** unchanged, on X = O12_pre + S.
- **Level test and carried fraction:** each is computed under both X = O12_pre + S and
  X = O12_pre, and the verdict of DESIGN.md §7.5 is formed under each.
- **When the slope reading is −1:**
  - H-epoch and H-uniform are called separable only if both offset definitions give the same
    verdict.
  - Otherwise the verdict is **"not separable: depends on whether the model carries the
    seasonal cycle"**.
- **Reporting:** both level tests and both carried fractions are reported.

### A3. Spin-up

- **S11:** the primary analysis restricted to post-transition cycles from 2026-08-24 onward.
- **Report-only table, per cycle and per product** (3D, 2D, 2D `noanomaly`):
  - the mean bias over all entering stations;
  - the mean bias over the 11 boundary-adjustment stations that enter that cycle.

### A4. Boston, report only

For station 8443970, every sampled cycle, both products and the 2D `noanomaly` output, report:

- the window-mean bias;
- the model mean and the observed mean;
- n;
- the paired datum.

### Run-time log

After the first 2D session of stofs-mcp 0.3.0, the elapsed time and the projected total run
time are written to `run_log/`.

## Implementation notes during Phase 2 (no rule, threshold or result changes)

- **N1. Human-check plots.** They show the observed series on both MSL and NAVD wherever CO-OPS
  has them, not only on the reference's paired datum, so the plot does not reveal the reference
  pairing. The frozen sampling functions (`non_routine`, `draw`) are unchanged.
- **N2. Memory.** `archive_io.CoopsObs.release()` drops parsed master documents between files
  (classify) and between stations (Study 2 O29). Results do not depend on it; the WP1 self-test
  was rerun after the change (8/8).
- **N3. Study 3 lag sign.** The output gains `lag_convention` and
  `model_lags_observations_by_min` (= −τ); the computation is unchanged.
- **N4. A1 grids.**
  - The two grids were fetched in full through the logged fetcher (2 requests, from the retry
    reserve): GEOID18 at 16,742,155 B, sha256 `fa9a407a…`; LMSL ITRF2020 at 55,534,954 B,
    sha256 `345ac0f7…`.
  - They are hard-linked under their `.tif` names for PROJ.
  - The offline Boston value equals the Boston package's bit for bit (0.09173215948229796 m).
- **N5. Report parser for coops-mcp.** A datum counts as "listed" only when it has a numeric
  value in the tool's table.

## Amendment A5: a second CO-OPS wording for an unpublished datum (2026-11-10)

**When:** after the CO-OPS download finished, before any reference classification, MCP session
or grading of sampled data.

**Evidence** (`run_log/a5_evidence.json`):
- For 14 stations, CO-OPS answered `datum=MSL` with HTTP 400
  `{"error": {"message":"There is no MSL for the station: <id>"}}`, and for 8531232 also
  `datum=NAVD` with "There is no NAVD for the station: 8531232". These are 2D-only stations
  that publish no datums.
- The body was byte-identical across every requested date range: 7 ranges for each MSL case, 6
  for the NAVD case.
- Phase 0 had seen only the other wording, " The supported Datum values are: …", for which
  DESIGN.md §5.2 rule 4a and `archive_io.CoopsObs` were written.

**Effect under the frozen rules:** these answers were archived as `coops_error_other` (an
acquisition gap). Classification would stop at the first such station, and no Study 1 result
could be produced for the 15 station–datum combinations.

**Change:**
- An HTTP 400 answer whose message starts with "There is no " followed by a datum name and " for
  the station" is treated as an unpublished-datum answer, like rule 4a. This applies in the
  reference (`archive_io.CoopsObs`, so the case is "not eligible: paired datum not published"),
  in the replay (`wp5_launcher.py` rule 4a) and in the archive indexing.
- **Effect:** these cases now stop being acquisition gaps. No other case is affected.
- **The frozen result for them is "classification stopped"**, and it is kept by being reported:
  REPORT.md lists these cases.

## Amendment A6: CO-OPS masters with a trailing "disclaimers" key (2026-11-10)

**When:** after the CO-OPS download, before any classification, session or grading.

**Evidence:**
- Three Louisiana stations on the modified 2012–2016 epoch (8760721, 8760922, 8762075) have a
  newest MSL block (B6, 2026-10-18 onward) that ends `],"disclaimers": [{ "name": "Provisional
  Datum","content": "These datums and any data referred to said datum are provisional …"}]}`
  instead of `]}`.
- The WP1 serializer cannot reproduce this tail, so WP1 rule 3 refused to slice these masters:
  3 of 2,293 failed the pre-flight round trip (`run_log/archives_check.json`, first run).
- Their requests (cycles 2026-10-19, 10-26 and 11-02, both products) would have been replay
  misses.

**Change** (`replay/wp5_launcher.py`):
- A master is also accepted when the WP1 serialization of its metadata and records, followed by
  its own raw tail from the `]` that closes `data`, equals its bytes exactly (the same byte-exact
  proof as WP1).
- Its slices are the WP1 serialization of the kept records followed by that same raw tail.
- Masters without extra keys are handled exactly as before.
- After the change, all 2,293 data masters pass.

**Validation:** one live tool-shaped request for 8762075 is compared byte for byte
(`run_log/rule_validation.json`).

**Also reported:** a "provisional datum" disclaimer in the observations for these stations and
dates. The reference reads only `data`, so its records are unaffected.
