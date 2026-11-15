# WP5 design freeze: sampled evaluation of the STOFS safeguards, and a multi-station test of the mean-level bias

Branch `eval/sampled-evaluation` (from `fix/stofs-post-wp1` `52c7f46`), worktree
`.claude/worktrees/sampled-evaluation`. Local only.

This document, `reference/` (the reference classification), `analysis/` (the outcome grader,
the Study 2 and Study 3 analyses), `human_check/draw.py`, `replay/` and `phase2/plan.py` are
frozen together in one commit **before any sampled model file is downloaded**. Anything changed
after that commit is an amendment, recorded in `AMENDMENTS.md` with its evidence; both results
are kept.

Evidence labels: **[P0]** measured in Phase 0 (this package, `phase0/`); **[DOC]** NOAA
documentation; **[WP1]**/**[BOS]** the WP1 package or the Boston package; **[A]** assumption.

---

## 1. Phase 0 results (feasibility)

All Phase 0 requests went through `phase0/noaa_fetch.py` (one at a time across processes,
≥ 1.2 s apart, at most one retry, budget-checked), and every attempt is in
`run_log/noaa_requests.jsonl` with URL, UTC start and end, status, size and SHA-256.

### 1.1 Station files on the NOAA open-data buckets [P0]

`phase0/probe_s3.py`, one S3 ListObjectsV2 request per product and date (60 requests),
results in `phase0/s3_probe.json` and `phase0/s3_sizes_summary.json`.

- **Every sampled 12z cycle exists for both products.** All 30 dates (§2.1) have
  `stofs_3d_atl.t12z.points.cwl.nc` and `stofs_2d_glo.t12z.points.cwl.nc`. No fallback day is
  needed at present.
- **Sizes:**

  | File | Size | Dates |
  |---|---:|---|
  | 3D `points.cwl.nc` | 5,509,661 B | 2026-06-01 to 2026-08-16 (15 files) |
  | 3D `points.cwl.nc` | 8,297,477 B | 2026-08-17 to 2026-11-02 (15 files) |
  | 2D `points.cwl.nc` | 25,246,800 B | 2026-06-01 to 2026-08-15 (14 files) |
  | 2D `points.cwl.nc` | 25,231,796 B | 2026-08-16 to 2026-11-02 (16 files) |
  | 2D `points.cwl.noanomaly.nc` | 23.26–23.32 MB, then 25,231,828 B | all 30 dates |

  The 2D size changes one cycle before the 3D size (2026-08-16 against 2026-08-17). Whether the
  2D upgrade to v3.1 happened at 2026-08-16 12z is read from each file's `title` in Phase 2; it
  does not change the 2D datum (§4.1).
- **Other station files present:** `points.autoval.cwl.nc` (both products, some dates),
  `points.cwl.temp.salt.vel.nc` (3D), `points.htp.nc`, `points.swl.nc`, `points.cwl.vel.nc`
  (2D), SHEF text. Only `points.cwl.nc` is in the sample (§2.2); `points.cwl.noanomaly.nc` is a
  supplementary control for Study 2 only (§7.3, open question Q1).
- **The 3D files of 2026-08-16 and 2026-08-17 are already archived in WP1** (sha256 `f78e84ef…`,
  `f47962fa…`). S3 reports them last modified on 2026-08-16 19:47 and 2026-08-17 19:55 UTC,
  before WP1 downloaded them (2026-11-06), so they are seeded by copy with their checksums.

### 1.2 Station identifiers and the CO-OPS mapping [P0]

Read offline from the five station files already archived (WP1 and the Boston package; no new
model download): 3D 2026-02-18, 2026-08-16 (v2.1.18), 2026-08-17 (v3.1.4), 2026-10-30 (v3.1.6);
2D 2026-10-30 (V3.1.0). `phase0/station_inventory.py` → `phase0/station_inventory.json`.

- **Station names carry the identifier**, e.g. `BHBM3 SOUS41 8443970 MA Boston` (NWS ID, SHEF
  product code, 7-digit number, state, name). 2D files also hold non-US points (`SA852`) and
  records whose 7-digit token is not a CO-OPS ID (`0000010`).
- **Mapping rule (frozen):** a record maps to a CO-OPS water-level station when its name contains
  exactly one 7-digit token (not part of a longer number) that is the `id` of a station in the
  CO-OPS metadata API list `stations.json?type=waterlevels` (302 active) or `type=historicwl`
  (2,924), both archived in Phase 0. A case uses the first such record in file order; any
  further record with the same ID is reported as a duplicate (§4.6).
- **Counts in the archived files:**

  | File | Records | Mapped | Distinct IDs | IDs on two records | Historic-only IDs |
  |---|---:|---:|---:|---|---:|
  | 3D v2.1 (2026-08-16) | 108 | 108 | 106 | 8651370 Duck, 8661070 Springmaid Pier | 5 |
  | 3D v3.1 (2026-08-17, 2026-10-30) | 166 | 163 | 163 | none | 21 |
  | 2D V3.1 (2026-10-30) | 1,687 | 375 | 373 | 8414721, 8416731 | 149 |

  Unmapped 7-digit tokens are PORTS or other non-water-level IDs (e.g. `9414311 San Francisco
  Pier 1`, `8590111 Bellevue`). The union over these files is **389 CO-OPS IDs**: 164 occur in a
  3D file and 225 only in the 2D file. The 2D v2.1 station list is not archived; SCN 26-51 lists
  its differences (4 added, 5 removed, one renamed ID). IDs found in downloaded files that are
  not in the union are handled from the reserve (§6).

### 1.3 Datums and tidal-datum epochs at the 389 stations [P0]

One CO-OPS metadata API request per station, `stations/<id>/datums.json?units=metric` (389
requests; archived as `data/archive/meta`; summary `phase0/datums_summary.json`).
`expand=datums` on the station list is not supported (the response is byte-identical to the
plain list).

| Station set | n | MSL and NAVD88 | MSL only | neither |
|---|---:|---:|---:|---:|
| all | 389 | 217 | 157 | 15 |
| in a 3D file | 164 | 121 | 42 | 1 |
| 2D only | 225 | 96 | 115 | 14 |

- **No station publishes NAVD88 without MSL.**
- **All 106 IDs of the 3D v2.1 file publish NAVD88;** the 42 MSL-only 3D stations entered at v3.1.
- **Epochs:** 354 on the National Tidal Datum Epoch 1983–2001; 20 on a modified five-year epoch
  (2012–2016 at four Louisiana stations, e.g. 8761724 Grand Isle, and seven Alaska stations;
  2002–2006 at nine Texas stations, e.g. 8775244); 14 with no datums; one (1770000 Pago Pago)
  with epoch "0000-0000" (classed unknown).
- **Approximate eligibility** (paired datum published and the station in the active list, a
  proxy for observations in 2026): 3D v2.1 101 of 106 (97 NTDE); 3D v3.1 142 of 163 (133 NTDE);
  2D 217 of 373 (198 NTDE). The real counts come from the observations (§4.4).

### 1.4 CO-OPS behaviour that the replay must reproduce [P0]

Five water-level probes (`phase0/coops/shapes/`):

- **No data:** CO-OPS answers HTTP 200 with
  `{"error": {"message":"No data was found. This product may not be offered at this station at the requested time."}}`
  (115 bytes, sha256 `500bdf8b…`), byte-identical for an inactive station (8725110, October
  2026) and for an active station outside its data (8443970, 20–21 November 2026).
- **Unpublished datum:** NAVD at 8413320 (Bar Harbor, MSL only) is answered with **HTTP 400**,
  `{"error": {"message":" The supported Datum values are: MHHW, MHW, MTL, MSL, MLW, MLLW, LWI, HWI"}}`
  (sha256 `d93e3df0…`), byte-identical for two different date ranges.
- **Data length:** the archived API help (WP1 e0020) limits 6-minute data to "1 month" per
  request. All masters here are ≤ 29 days.
- **Monthly means:** `product=monthly_mean&datum=MSL` returns verified months only; at Boston
  the latest is 2026-09 (16 months returned for 2025-06 to 2026-10).

### 1.5 Documentation [P0]

- **SCN 26-51** (archived in the Boston package; text in `phase0/docs/`): STOFS v3.1 "on or
  about July 7, 2026, beginning with the 1200 UTC cycle"; 3D station netCDF "referenced to local
  mean sea level (LMSL) (no longer NAVD88), while gridded output will remain referenced to
  xGEOID20b"; the 3D "dynamic adjustment (bias correction) of open boundary conditions … by
  averaging the model's nowcast bias for the past two days over 11 U.S. East Coast open coast
  NOS/CO-OPS stations … uniformly applied to the open boundary conditions"; the 2D station bias
  correction of v2.1 ("removing the bias between the observed water levels at NOS/CO-OPS
  stations and most recent 5 days of nowcast water levels"), extended to the grid in v3.1; new
  2D file `points.cwl.noanomaly.nc`.
- **Start of v3.1 [DOC]:** SCN 26-51 Updated (8 Jul 2026) moved the date to 11 August; the NOAA
  STOFS portal pages for both products say "Operational implementation … upgrade to v3.1
  occurred at the 12 UTC cycle on August 17 2026". No notice for the slip from 11 to 17 August
  was found. The 3D file sizes change at 2026-08-17 [P0]; the 2D size changes at 2026-08-16,
  which Phase 2 checks against each file's `title`.
- **The 11 boundary-adjustment stations [DOC-code]** (`phase0/docs/FINDINGS_docs.md`,
  `reference/boundary_stations.json`), from NOAA's operational code (`derive_bias.py`
  `STA_LIST` and the dynamic-adjust script; NCO serves only v3.1.7, not the v3.1.4/v3.1.6 named
  in the files): 8670870 Fort Pulaski, 8665530 Charleston, 8661070 Springmaid Pier, 8658163
  Wrightsville Beach, 8651370 Duck, 8632200 Kiptopeke, 8557380 Lewes, 8536110 Cape May, 8534720
  Atlantic City, 8531680 Sandy Hook, 8452660 Newport. All 11 are in the v3.1 station files
  (Duck and Springmaid Pier too, although SCN 26-51 says they were removed from the output).
  The observations are put into the model's xGEOID20b frame with the same per-station
  MSL−xGEOID20b constants as the station output, so the bias is in effect the 2-day mean over
  the 11 stations of (station output on LMSL) − (observation on MSL) [inference from the code];
  hourly means, no tidal filter, applied as one uniform shift of the open-boundary elevation.
- **2D correction [DOC]:** since v2.1.7 (14 May 2024, SCN 23-124): the 5-day mean of
  observed − model (on MSL) is removed from the forecast with a 12-hour ramp; the code writes the
  corrected series to `points.cwl.nc` and keeps the uncorrected one as `points.cwl.noanomaly.nc`.
- **Epochs [DOC]:** CO-OPS still uses the 1983–2001 NTDE (next NTDE, 2002–2020, proposed for
  2029); the current modified five-year update (2012–2016) covers Louisiana and Alaska stations.
- **Not found:** the epoch of NOAA's MSL−xGEOID20b constants, and any statement that either
  model's mean level is tied by construction to epoch MSL, present-day MSL or a geoid.

### 1.6 Masters and request count

The brief proposed one master per station, datum and calendar month. **Changed, with reason:**
a calendar-month master cannot serve a request that crosses a month boundary (the replay rule
needs one master covering the whole request), and four sampled windows do (2026-06-29 → 07-01,
2026-08-31 → 09-02, and the 0.2.0 windows of 2026-06-01 and 2026-11-02, which start the day
before). The blocks of §3.2 have the same count (seven for MSL) and put every boundary in a gap
between cycle windows. The total is in §6.

---

## 2. Sampling rule

### 2.1 Cycles

- The 12:00 UTC cycle on every seventh day from 2026-06-01 to 2026-11-02 (23 dates: 06-01,
  06-08, …, 11-02), plus every day from 2026-08-13 to 2026-08-20 (8 dates). 2026-08-17 is in
  both, so there are **30 dates**, for each product.
- **Missing file:** take the next day with the file, and record it. None is missing (§1.1).
- **Previously seen:** 2026-08-16 and 2026-08-17 (WP1 R4a/R4b) are in the sample and are flagged
  "previously seen" for both products; their cases are reported separately (§4.8). 2026-02-18
  and 2026-10-30 are not in the sample.

### 2.2 Products

`stofs_3d_atl.t12z.points.cwl.nc` (STOFS-3D-Atlantic) and `stofs_2d_glo.t12z.points.cwl.nc`
(STOFS-2D-Global, the bias-corrected station output by SCN 26-51), 60 files. The 2D
`points.cwl.noanomaly.nc` (30 files) is read only by the reference code, for Study 2 (§7.3).

### 2.3 Stations

Every record of each file that maps to a CO-OPS water-level station (§1.2), with no subset and
no exclusion by hand. One case is (product, cycle, CO-OPS ID). Cases that fail an eligibility
rule stay in the tables with the reason (§4.5).

### 2.4 Window

**0 < lead ≤ 49.7 h** from the cycle time, for every case in Study 1 and Study 2. 49.7 h is the
smallest multiple of the 6-minute output interval that is at least two lunar days (2 × 24.84 h
= 49.68 h), so window means average over four semidiurnal and two diurnal cycles and depend
less on tidal phase. The window holds 497 six-minute times. Both products cover it (3D files run
to +96 h, 2D to +180 h). The tool is called with `lead_start_hours=0`, `lead_end_hours=49.7`.

---

## 3. Data to acquire in Phase 2

### 3.1 Model files

The 58 station files not yet archived, by exact S3 URL (the URL stofs-mcp builds), plus the 2
seeded WP1 files and, for Study 2 only, the 30 `noanomaly` files (Q1). Archived in
`data/archive/models` in the replay launcher's format, with the S3 `Last-Modified` and `ETag`.

### 3.2 CO-OPS water-level masters

Parameters exactly as both stofs-mcp versions send them (`station, product=water_level, datum,
units=metric, time_zone=gmt, format=json, begin_date, end_date, application`), with
`application=ocean_mcp_wp5` (ignored in matching, as in WP1). Whole UTC days, each ≤ 29 days:

| Block | MSL | NAVD | Cycles whose windows it holds |
|---|---|---|---|
| B0 | 2026-05-18 to 05-30 | — | none (29-day offsets of 06-01 only) |
| B1 | 05-31 to 06-27 | yes | 06-01, 06-08, 06-15, 06-22 |
| B2 | 06-28 to 07-25 | yes | 06-29, 07-06, 07-13, 07-20 |
| B3 | 07-26 to 08-22 | yes | 07-27, 08-03, 08-10, 08-13 … 08-20 |
| B4 | 08-23 to 09-19 | yes | 08-24, 08-31, 09-07, 09-14 |
| B5 | 09-20 to 10-17 | yes | 09-21, 09-28, 10-05, 10-12 |
| B6 | 10-18 to 11-15 | yes | 10-19, 10-26, 11-02 |

The union of all requests any tool makes for cycle D is [D − 1 d 12:06, D + 2 d 13:42] (0.3.0:
[D 12:06, D + 49.7 h]; 0.2.0 3D: [D − 24 h + 6 min, D + 48 h + 6 min]; 0.2.0 2D:
[D − 6 h + 6 min, D + 48 h + 6 min]); each lies inside one block (`phase2/check_blocks.py`:
180 of 180 window–datum combinations). One edge case: 0.2.0 starts its window at the first
*valid* model value, so a station whose leading values are missing could push its end past a
block boundary; the replay would miss, and §5.3 treats that as an acquisition gap.

- **MSL** for every station; **NAVD** for every station that occurs in a 3D file (pre-transition
  3D comparisons, and stofs-mcp 0.2.0, which requests NAVD for every 3D cycle).
- **A datum the station does not publish** (§1.3) gets one request (B1). If CO-OPS answers with
  the HTTP 400 unsupported-datum document, that answers every range (§5.2, rule 4a); otherwise
  the remaining blocks are fetched from the reserve.
- **Pre-flight:** every data master must round-trip byte-exactly through the WP1 serializer
  before any session (otherwise the replay refuses to slice it); failures are reported.
- B6 ends in the future at freeze time; it holds the data published when it is fetched.
- **Pre-session request scan (acquisition only):** before any session, the CO-OPS range each
  version will request for each case is computed from the files (0.3.0: first and last valid
  model time in the window; 0.2.0: from its first non-fill model value, 72 h for 3D or 54 h for
  2D, capped at the file end). Any range not inside one block gets its own master with exactly
  that range, from the reserve. This scan decides only what to download; it never enters the
  reference or the grading.

### 3.3 Reference-only inputs

- **Verified monthly mean sea level**, `product=monthly_mean&datum=MSL`, 2016-01-01 to
  2026-10-31 (the API allows 200 years per request), one request per station that publishes
  MSL. It gives both the 12-month means and a 2016–2025 seasonal climatology (§7.3).
- **Datums** (done in Phase 0). IDs new in the downloaded files get one request each (reserve).
- **Documentation:** as archived in Phase 0.

---

## 4. Study 1: behaviour of the safeguards on sampled data

### 4.1 Datum the file should carry, and the label it carries (`reference/rules.py`)

- **Version from the file:** 3D global `history` (`packages/stofs.vX.Y.Z/`), 2D global `title`
  (`STOFS_2D_GLOBAL.VX.Y.Z`; any run of space, dot, underscore or hyphen accepted between the
  parts, "V" optional). **Stop rule:** a sampled file whose version the reference cannot read
  halts the classification for an amendment; no 2D v2.1 file has been read yet.
- **Documented datum by version [DOC]:** 3D v2.1 → NAVD88 and v3.1 → LMSL (SCN 26-51); 2D v2.1
  and v3.1 → LMSL (NOMADS STOFS-Global description; SCN 26-51 lists no 2D change). Any other
  version: no documented datum.
- **Documented date:** the portal's 2026-08-17 12z for both products. Every file whose version
  disagrees with that date is listed (a documentation defect, not a datum one); the dates of
  SCN 26-51 (7 July) and its update (11 August) are reported for comparison.
- **Label:** tokens in zeta `standard_name` and `long_name` (word-boundary matches for NAVD88,
  MSL/mean sea level, xGEOID, MLLW, IGLD); "geoid" alone names no datum (CF
  `sea_surface_height_above_geoid`; ADCIRC writes it generically).
- **Reference datum:** 3D: the label must name the documented datum; a label that names another
  datum, conflicting labels or an undocumented version leave the datum undeterminable; a missing
  or generic label with a documented version is "unlabelled" and the documented datum is used
  (WP1 S1 rule; a refusal naming the missing datum is then also accepted). 2D: the documented
  datum. Tokens are matched between non-alphanumeric boundaries (an underscore separates them).
- **Paired CO-OPS datum:** LMSL ↔ `MSL`, NAVD88 ↔ `NAVD` (CO-OPS API documentation).

### 4.2 Statistics recalculated by separate code

`reference/classify.py`, netCDF4 with auto-masking off (every value as stored), pure Python
statistics. Exact-timestamp pairs only (both series are on the 6-minute grid by documentation;
off-grid times are counted). n, bias = mean(model − observed), RMSE, MAE, max |e|, model and
observed means and SDs, r.

**Self-test before the freeze, on previously seen files only** (WP1 archive; no sampled file):
the code reproduces every WP1 reference value it can address: Boston 2D 2026-10-30 (n 480,
bias −0.00050, RMSE 0.12300, MAE 0.09999, r 0.99338), Boston 3D 2026-10-30 (bias −0.14300,
RMSE 0.24555, MAE 0.20861), 3D 2026-08-16 against NAVD (bias −0.12354, RMSE 0.2676), 3D
2026-08-17 against MSL (bias −0.03544, RMSE 0.2111), 9751381 (1,200 code-like values, expected
refusal), 8571421 2D (47 values of −99998.6), and the 110 flagged Boston observations.

### 4.3 Model value screening and the physical bound

Classes, in precedence order: **fill** (equal to `_FillValue` or `missing_value`), **dry**
(equal to the ADCIRC global `dry_Value`), **outside valid range** (CF `valid_min`/`valid_max`/
`valid_range`, if present), **nonfinite**, **implausible** (|v| > 30 m), else **valid**.
"Code-like" (|v| ≥ 1,000 m) is a descriptive sub-label of implausible.

**Bound: 30 m.** Water level relative to a coastal tidal or geodetic datum cannot exceed about
22 m anywhere (largest tidal half-range ≈ 8.5 m, Bay of Fundy; largest surges ≈ 8–13 m); at the
US stations sampled the envelope is smaller (Cook Inlet half-range ≈ 5 m). 30 m adds a margin
for datum offsets of a few metres and keeps continuity with WP1's validated workflow. The tool
uses 50 m. **Every model value with 20 m ≤ |v| ≤ 100 m in any sampled file, mapped or not, is
listed** (`band_20_100m.jsonl`: product, cycle, station, time, value, in window). A sensitivity
table gives the case classes under bounds of 20, 30, 50 and 100 m.

Report-only diagnostic: valid model values beyond the station's recorded extremes (datums.json
`max`/`min`, relative to MSL) by more than 1 m.

### 4.4 Observations on the paired datum

In the window, from the masters: records, missing (empty or non-numeric `v`), nonfinite,
implausible (same bound), valid; verified (`q = v`) and preliminary (`q = p`); flags `O, F, R, L`
counted per type and as "any" (CO-OPS response help), never used to filter in Study 1.
**Whether the paired datum is published is what CO-OPS served:** "not published" only when it
answered with the HTTP 400 unsupported-datum document. The metadata API's datum list is reported
beside it, and every disagreement is listed. A case whose window has no archived master is an
acquisition gap: classification stops (never "not eligible").

### 4.5 Expected outcome and outcome classes

**Expected outcome** (`rules.expected_outcome`), with all applicable reasons recorded:

| Expected | When |
|---|---|
| refuse | the datum is undeterminable, or there is no valid model value in the window |
| not eligible | the paired datum is not published, or there is no valid paired observation in the window, or valid model and valid observed values share no time |
| compare | otherwise |

**Outcome class of the tool** (`analysis/study1_outcomes.py`; one per case):

| Class | Rule |
|---|---|
| correct comparison | expected compare; the tool proceeded; its model datum is the reference datum, and the CO-OPS datum it *requested* (from the HTTP log) and reports is the paired datum; n equals the reference n; bias, RMSE and MAE are each within 0.01 m; its model-exclusion total over the station series equals the reference count |
| correct refusal | expected refuse; the tool declined with a matching reason |
| refusal, reason differs | expected refuse; the tool declined for another reason (e.g. an HTTP or unexpected error) |
| false refusal | expected compare; the tool declined |
| undetected problem | the tool proceeded and the pairing is wrong, or a value the reference excludes entered a statistic (tool n > reference n), or the reference rules the case out (refuse or not eligible) |
| not eligible | expected not eligible (a reference property); the tool declined. Sub-label: reason matches / other reason, both counted |
| other discrepancy | expected compare, the tool proceeded with the right pairing, but n or a statistic differs without a reference-excluded value as cause (e.g. the tool's nearest-time pairing within 3 min, `alignment.nearest > 0`, or a station-identity collision), or only the exclusion count differs (sub-label says which, and whether the differing values lie outside the window) |

"Reason matches" uses a fixed table (`MATCHES`): e.g. a tool message "Could not fetch CO-OPS
observations" matches "no valid paired observation" and "paired datum not published"; an HTTP
error message that blames the S3 bucket matches neither.

### 4.6 Defect classes (reference properties of a case)

Model: fill, dry, nonfinite, implausible, code-like, any value in the 20–100 m band, each in
the window and in the whole series. Datum: label contradicts documentation, conflicting labels,
unlabelled, undocumented version, version contradicts the SCN date. Identity: ID on more than
one record (with the largest in-window difference between the records), the ID occurs as a
substring of an earlier record's name. Coordinates (informational; the compare tool selects by
ID): stored x/y reversed. Observations: missing, nonfinite, implausible, any flag, paired datum
not published, no valid observation, fewer than 80% of the window paired.

### 4.7 Version contrast and coops-mcp

- **stofs-mcp 0.2.0 (PyPI), decision and pairing only.** Same cases, same replay archives,
  `stofs_compare_with_observations` with `hours_to_compare` 72 (3D) or 54 (2D), as WP1 arm D
  (0.2.0 has no lead window). Recorded: proceed or decline, the reason, and the CO-OPS datum it
  requested. Reported as a contrast, not as a result.
- **coops-mcp 0.1.1 (PyPI):** one session, `coops_get_datums(station_id, units="metric")` for
  every station, answered from the Phase 0 datums bytes. Recorded: whether the response lets a
  client see that MSL and NAVD88 are published, and whether it states the epoch.

### 4.8 Reporting

Counts by outcome class per product (3D pre-transition, 3D post-transition, 2D); by station;
by cycle; by defect class. For each class: the number of distinct stations and distinct files
(product, cycle) that account for it. Previously seen cycles separately. Every false refusal,
undetected problem and other discrepancy listed individually with its evidence (tool text or
JSON fields, the request it made, the reference record). The 20–100 m values. The 0.2.0
contrast. How many paired observations were preliminary.

---

## 5. MCP sessions in replay mode

### 5.1 Software under test

| Role | Package | Identity |
|---|---|---|
| main | stofs-mcp 0.3.0 post-fix | `verification_post_wp1/dist/stofs_mcp-0.3.0-py3-none-any.whl`, sha256 `ba4edc2e05a527f33785bc9fcabd0d313bc57ccabed8373e50376462d297be9a` (checked before install) |
| contrast | stofs-mcp 0.2.0 | PyPI |
| datums | coops-mcp 0.1.1 | PyPI |
| client | mcp 1.30.0, CPython 3.13.12 | pinned from WP1 `environment/*.freeze.txt` |

### 5.2 Launcher and matching

`replay/ocean_replay_launcher.py` is a byte-identical copy of the WP1 launcher (sha256
`203398c3…aba87`). `replay/wp5_launcher.py` checks that hash, imports it, replaces only
`Engine.coops_slice`, and runs the WP1 `main()`. Rules, in order:

1. exact match (WP1); 2. HEAD from GET (WP1); 3. CO-OPS slice of a covering data master (WP1);
5. **empty slice** → CO-OPS's generic no-data document (§1.4) instead of an empty list;
4b. **no-data master** → the generic no-data document (sha256 `500bdf8b…` only), for any
sub-range of its range. Any other error body (rate limit, maintenance) is an acquisition gap,
archived as `coops_error_other`, never served and never read by the reference;
4a. **unsupported datum** (HTTP 400 "The supported Datum values are …") → that document, for any
range of the same station and datum.

Rules 4a, 4b and 5 are new; each reproduces a CO-OPS behaviour measured in Phase 0. **Live
validation in Phase 2** (4 requests): one tool-shaped request for each of rules 3, 4a and 4b, and
for rule 5 if any session needs it, compared byte for byte with what the replay serves.

### 5.3 Sessions

- One session per (version, product, cycle): 60 for 0.3.0, 60 for 0.2.0; one coops-mcp session.
  About 15,200 calls per stofs version.
- **Frozen call templates** (`analysis/study1_outcomes.py`: `call_030`, `call_020`,
  `call_coops`): `call_id` = case id `<product>_<YYYYMMDD>_<station>`; 0.3.0:
  `station_id, model, cycle_date=YYYY-MM-DD, cycle_hour="12", lead_start_hours=0,
  lead_end_hours=49.7, response_format="json"`; 0.2.0: the same without the lead window, with
  `hours_to_compare` 72 (3D) or 54 (2D); coops-mcp: `station_id, units="metric"`. The grader
  raises if a non-JSON response reads as a comparison, so a wrong template cannot be graded as
  a refusal.
- Every session runs inside `unshare -rn`; `replay/run_session_wp5.py` attributes each call's
  HTTP-log lines to it; a call with a replay miss or network attempt is invalid, and so is its
  session. Phase 2 stops on the first invalid session, fills the archive gap from the reserve if
  it is an acquisition gap, and reruns that session; any such rerun is reported.
- **Pre-freeze dry run on previously seen files only** (`phase0/dryrun_wp1/`): one real stdio
  session of the post-fix 0.3.0 wheel inside `unshare -rn`, WP1 archive, 2026-10-30, window
  (0, 48] h, four calls. Graded by the frozen grader against the reference: Boston 3D and 2D
  "correct comparison" (statistics within 5×10⁻⁵ m), 9751381 3D "correct refusal, reason
  matches", and 8571421 2D, whose observations are not in that archive, a replay miss that marked
  that call and the session invalid, as designed.
- Transcripts (initialize, tool list, every call and response, per-call HTTP events) are saved
  gzip-compressed; their SHA-256 values are committed. Bodies and transcripts larger than a few
  MB are kept out of git (`.gitignore`) and identified by checksum.

---

## 6. Request budget (NOAA)

`phase2/plan.py` → `phase2/fetch_plan.json` lists every URL.

### 6.1 Planned requests

| Group | Requests |
|---|---:|
| 3D station files (2 more seeded from WP1) | 28 |
| 2D station files | 30 |
| 2D `noanomaly` files (Q1) | 30 |
| CO-OPS MSL masters (374 stations × 7) | 2,618 |
| CO-OPS MSL, unpublished datum (15 stations × 1) | 15 |
| CO-OPS NAVD masters (121 stations × 6) | 726 |
| CO-OPS NAVD, unpublished datum (43 stations × 1) | 43 |
| CO-OPS verified monthly means (374 stations) | 374 |
| **Planned** | **3,864** |

### 6.2 Reserve

| Item | Requests |
|---|---:|
| IDs in the downloaded files not in the Phase 0 union (datums, masters, monthly mean) | 150 |
| escalation of unpublished-datum probes that CO-OPS does not answer with HTTP 400 | 120 |
| live validation of replay rules 3, 4a, 4b, 5 | 4 |
| retries (at most one per request) | 160 |

**Budget cap: 4,298 requests.** I will not exceed it without telling you. Phase 0 used 483
requests of its own 700 cap (S3 listings 60, CO-OPS station lists 4, CO-OPS behaviour probes 5,
datums 389, documentation 25), all logged. Expected volume about 2.7 GB (1.7 GB model files, about 1 GB CO-OPS);
at ≥ 1.2 s spacing the downloads take about two hours.

---

## 7. Study 2: does the STOFS-3D-Atlantic mean bias track the rise in sea level since the epoch?

### 7.1 Hypotheses (stated before any sampled file is read)

Let, for station s, **B_s** = mean over cycles of the window-mean error (model − observed) and
**X_s** = recent mean sea level above the station's CO-OPS MSL datum (observations only, §7.3).

- **H-epoch:** the model's zero is epoch MSL by construction and the model does not carry the
  rise in relative sea level since the epoch: **B_s ≈ −X_s** (slope ≈ −1, intercept ≈ 0).
- **H-carried:** the model carries present-day mean level through boundary forcing or
  corrections: B_s does not depend on X_s (slope ≈ 0).
- **H-uniform (pre-specified intermediate, motivated by the documented adjustment, §1.5):** the
  v3.1 boundary adjustment carries one spatially uniform level L, but not the station-to-station
  pattern of the rise: **B_s ≈ L − X_s**. Slope ≈ −1 and intercept = L > 0. The adjustment is a
  feedback loop (each cycle's bias is measured on the previous, already adjusted run), so L need
  not reach the 11-station mean offset X̄_B: with a coastal response k to a boundary shift it
  settles near X̄_B·k/(1 + k) if each adjustment replaces the last, or near X̄_B if they
  accumulate. The design therefore tests L itself through the **carried fraction f = L / X̄_B**
  (0 under H-epoch, 1 for a full carry), and checks consistency through the boundary stations'
  own mean bias B̄_B ≈ L − X̄_B.
- **Partial:** −1 < slope < 0.

For the 2D control (bias-corrected station output, 5-day nowcast bias removed per station),
H-carried is expected by construction. For the pre-transition 3D check (v2.1, NAVD88 against
NAVD; no boundary adjustment), the same hypotheses apply with the same X_s.

### 7.2 The boundary-adjustment stations

The 11 IDs of §1.5, frozen in `reference/boundary_stations.json` with their sources. They are
marked in every table. Two direct checks use them: the mean bias over the boundary stations
(H-uniform predicts about 0, H-epoch about −X̄_B), and S3, the regression without them. The code
list is v3.1.7; if v3.1.4/v3.1.6 used another list, this is a limitation, not a reason to change
the list after seeing results.

### 7.3 Quantities

- **Bias per station (B_s):** for each cycle in the period, the window mean of model − observed
  over exact pairs (LMSL against MSL after the transition; NAVD88 against NAVD before), from the
  reference recalculation. A case enters if its expected outcome is compare and ≥ 80% of the
  497 window times are paired. A station enters if ≥ 5 cycles of the period do. Reported: B_s
  (mean), its SD across cycles, the model window mean and the observed window mean.
- **Offset per station, observations only.** The brief's two estimates are both computed and
  reported:
  - **O12:** mean of the CO-OPS verified monthly MSL (datum MSL) over the 12 calendar months
    before each cycle's month (≥ 10 months required), averaged over the station's entering
    cycles.
  - **O29:** mean valid observed level (datum MSL, 6-minute masters, preliminary included) over
    [cycle − 14.5 d, cycle + 14.5 d), ≥ 80% coverage required, averaged over cycles.

  **The regressor X_s (primary) is changed, with reason.** The bias windows fall in June–August
  (pre-transition) and August–November (post-transition), when US East and Gulf coast MSL sits
  several centimetres above its annual mean, most in the Gulf. An annual mean (O12) would then
  put H-epoch's intercept and level test at about minus the seasonal anomaly rather than 0, and,
  because the anomaly is largest where the rise is largest, steepen the slope. O12 per cycle also
  includes August–September 2026 months, which contain other cycles' windows. O29 contains the
  window itself (about 7% of its records), so if the model misses subtidal anomalies it pulls the
  slope toward −1 and cannot corroborate H-epoch. Hence:
  **X_s = O12_pre + S_s**, where O12_pre is the mean verified monthly MSL over the 12 months
  before the period's first cycle month (no overlap with any window of the period) and S_s is
  the mean, over the station's entering cycles, of the calendar-month seasonal anomaly from the
  2016–2025 verified monthly means (each year's months minus that year's mean; years with ≥ 10
  months, months with ≥ 5 years). O12, O12 + S and O29 are sensitivities (§7.6).
- **Epoch:** from datums.json. Primary analysis: stations on the NTDE 1983–2001. Modified-epoch
  stations are analysed separately (their MSL datum is recent, so X_s is not the rise since
  1983–2001).
- **Periods:** 3D post-transition: the 15 cycles 2026-08-17 to 2026-11-02. 3D pre-transition:
  the 15 cycles 2026-06-01 to 2026-08-16. 2D control: the same 15 post-transition cycles (primary)
  and all 30 (sensitivity), on (i) the stations of the 3D post-transition analysis and (ii) all
  eligible 2D stations. Supplementary (Q1): 2D `noanomaly` output, same cycles and stations,
  reference code only.

### 7.4 Analysis (`analysis/study2_regression.py`)

- OLS of B_s on X_s across stations. 95% percentile intervals for slope and intercept from
  10,000 bootstrap resamples of stations (seed 20261109). Also: a cluster bootstrap that
  resamples coastal regions (`region()`: 2° latitude bands on the Atlantic coast, three Gulf
  sectors, Caribbean, US West Coast, Pacific/Alaska/islands), because neighbouring stations are
  not independent; and the Theil–Sen slope.
- **Level test:** mean over stations of B_s + X_s with a bootstrap interval. H-epoch predicts
  about 0, H-carried about the mean offset, H-uniform about L. A spatially uniform model bias of the same size is
  indistinguishable here, which is why the slope is primary.
- **Precision expected [A]:** slope SE ≈ σ / (SD(X) √n). With n ≈ 130 stations, residual scatter
  σ ≈ 0.07 m and SD(X) ≈ 0.05 m, the 95% interval is about ±0.24. If SD(X) is below about 0.02 m,
  the slope is expected to be inconclusive by construction. SD(X) is reported with the result.

### 7.5 What counts as a result (fixed now; `slope_reading()` and `verdict()`)

With the primary bootstrap interval [L, U] for the slope, a target value is **supported only if
it is inside [L, U] and the midpoint −0.5 is outside**:

| Slope reading | Rule |
|---|---|
| −1 | −1 inside, 0 and −0.5 outside |
| 0 | 0 inside, −1 and −0.5 outside |
| intermediate | −1 < L and U < 0, and neither of the above |
| outside both | U < −1 or L > 0 |
| inconclusive | anything else (e.g. [−0.9, 0.05], [−1.9, −0.05]), or fewer than 15 stations |

| Verdict | Rule |
|---|---|
| supports H-carried | slope reading 0 |
| supports H-epoch | slope reading −1, and the carried-fraction interval contains 0 and excludes 0.5 |
| supports H-uniform | slope reading −1, and the carried-fraction interval lies above 0 (f and its interval reported; "full carry" if it contains 1) |
| H-epoch and H-uniform not separable | slope reading −1, carried-fraction interval contains 0 and 0.5 |
| slope ≈ −1 with a negative uniform offset (unexplained) | slope reading −1, carried-fraction interval below 0 |
| intermediate / outside both / inconclusive | the slope reading |

The carried fraction is computed in each bootstrap resample as intercept / mean X over the
boundary stations in that resample; the boundary stations' mean bias, mean offset and their sum
(≈ L) are reported with intervals.

The primary reading is **3D post-transition, NTDE stations, X = O12_pre + S, window
(0, 49.7] h**. It is called **robust** only if the cluster-bootstrap interval gives the same
verdict; otherwise it is reported as fragile. The 2D control and the pre-transition 3D check get
the same rule. On synthetic stations built under each hypothesis (B = −X; B = L − X with full and
half carry; B = 0; 120 stations, 5 cm noise) the rule returned the hypothesis used.

### 7.6 Sensitivity runs (all reported, none replaces the primary)

S1 window (0, 24.8] h and (0, 48] h (the 80% pairing threshold scales with the window) · S2
offset O12 + S, O12 alone, and O29 (O29 cannot corroborate H-epoch, §7.3) · S3 without the 11
boundary-adjustment stations · S4 weekly cycles only (without 08-18, 08-19, 08-20) · S5 without
the previously seen cycles · S6 modified-epoch stations pooled in · S7 only cases with ≥ 90% of
paired observations verified · S8 2D control over all 30 cycles · S9 the case classes under
bounds of 20, 50 and 100 m (Study 1).

### 7.7 Independence of the references

- **What establishes the model's vertical reference:**
  - the files' own labels (`…above navd88` for v2.1, `…above msl` for v3.1);
  - SCN 26-51's statement of the station datum;
  - the Boston package's check of NOAA's conversion: the five Caribbean no-data codes give
    NOAA's per-station constants, four within 1 mm of VDatum xGEOID20b→LMSL; over 115 stations
    the station-minus-grid-minus-VDatum median is +0.1 mm [BOS]. So the 3D station output is
    the model's xGEOID20b level plus VDatum's xGEOID20b→LMSL constant.
- **What does not:**
  - none of these shows where the model's own mean surface sits relative to present-day sea
    level, which is what Study 2 measures;
  - VDatum LMSL equals the CO-OPS MSL datum at Boston (0.0917 against 0.092 m via NAVD88 [BOS]);
    at other stations this is not checked here, and at modified-epoch stations the two need not
    agree;
  - VDatum's tidal datums are assumed to be on the 1983–2001 NTDE [A];
  - the 2D realization of LMSL is not verifiable from these files.
- **The regressor is independent of the model:** X_s comes from CO-OPS observations on the
  station's own MSL datum, never from STOFS files.

---

## 8. Study 3 (small): decomposition of the Boston error

From the archived Boston files of the 2026-10-30 12z cycle only (3D `46608194…`, CO-OPS MSL
response `c207c801…`), window (0, 48] h as Table 3 (`analysis/study3_boston.py`):

- best lag at sub-sample resolution: model shifted by τ (cubic spline of the 6-minute series),
  τ minimising the centred RMSE on a 0.1-minute grid in [−60, 60] min; also the 6-minute-grid
  optimum and the parabolic vertex;
- RMSE after removing the mean, the best lag and a best-fit amplitude scale, each alone and
  cumulatively (mean → lag → amplitude);
- the types of the 110 flags (O, F, R, L);
- Table 3's statistics with flagged observations removed.

---

## 9. human_check

`human_check/draw.py`: 20 cases by simple random sampling from all cases, plus 10 from the
non-routine cases (expected refuse or not eligible, any invalid model value, a datum-label
issue, or a duplicated ID), seed 20261109, then shuffled. Each case gets a plot of the raw model
series (whole file, window shaded) and the observed series, and a text file with the file's
datum attributes and the station's CO-OPS datums and epoch. No statistic is shown. The tool's
and the reference's outcomes go to `SEALED_outcomes.json`, whose SHA-256 is written first.

---

## 10. Phase 2 and Phase 3 outputs

As the brief lists: `REPORT.md` (Study 1 counts and lists, Study 2 table, regressions,
sensitivities, figure, verdict; Study 3 table; limitations), `human_check/`, proposed
manuscript text (≤ 200 words, one table, one figure), and one command, `./run_all.sh`, that
repeats everything offline from the archives.

## 11. Known limits of this design

- One author and assistant wrote the tool's fixes, the reference rules, the grader and this
  design. The reference rules come from the same reading of the documentation as the tool's.
  The designer has read the tool's source, including its 50 m bound and its refusal messages;
  the grader's reason patterns use those messages.
- The reference's 30 m bound differs from the tool's 50 m on purpose; §4.3 lists every value
  that the difference could touch.
- Recent observations are preliminary; how many is reported. Stations are not independent of
  one another (shared weather, shared boundary forcing); the cluster bootstrap addresses part of
  this.
- Not sampled: other products (gridded, SHEF, `autoval`, `htp`, `swl`), other months, 2D cycles
  other than 12z, nowcast segments, STOFS-3D-Pacific.
- Replay serves archived bodies with minimal synthetic headers; latency, timeouts and retries
  are not exercised.

## 12. Open questions for you

- **Q1. 2D `noanomaly` control.** Include the 30 `points.cwl.noanomaly.nc` files as a
  supplementary Study 2 control (reference code only; 30 requests, about 0.7 GB, inside the
  budget)? It shows how the 2D model behaves without its station bias correction. **Default if
  you only say "proceed": included.**
- **Q2. Preliminary observations.** Cycles from about September onward will be compared with
  preliminary observations (counted, not excluded; S7 restricts to verified). Default: proceed.

## 13. Pre-freeze independent review

Before the freeze, a separate reviewer (a fresh assistant session given only the files) read the
design and the code. All 13 points were accepted and fixed before this commit; none required
data:

| # | Point | Resolution |
|---|---|---|
| 1 | H-uniform assumed a full carry; the adjustment is a feedback loop | §7.1: B ≈ L − X, tested through the carried fraction f = L / X̄_B |
| 2 | O12 is an annual mean against seasonal windows; O29 shares the window | §7.3: X = O12_pre + seasonal anomaly; O12, O12 + S, O29 as sensitivities |
| 3 | The verdict rule read too much | §7.5: a target counts only with −0.5 outside the interval; "outside both" and "not separable" added |
| 4 | 497 pairs hard-coded | the 80% threshold scales with the window |
| 5 | Call arguments not frozen | §5.3 call templates; the grader raises on a non-JSON comparison |
| 6 | 2D v2.1 version string never seen | §4.1 broader pattern and a stop rule |
| 7 | No common times; missing masters | `no_common_valid_times`; a missing master stops classification |
| 8 | Any decline counted as correct | §4.5 "refusal, reason differs" class |
| 9 | 0.2.0 requests can leave a block | §3.2 pre-session request scan |
| 10 | Metadata overrode what CO-OPS served | §4.4 served datum decides; disagreements listed |
| 11 | Rule 4b accepted any error body | §5.2 only the no-data body; other errors are gaps |
| 12 | Label regex after "_"; 3D generic label | non-alphanumeric boundaries; 3D generic = unlabelled |
| 13 | Nearest-time pairing read as an excluded value | §4.5 "other discrepancy" with the pairing count |

The self-test (8/8) and the dry run (same responses, same grades) were repeated after the fixes.
