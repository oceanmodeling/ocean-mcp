# Phase 0 documentation findings (STOFS v3.1 bias corrections, start date, epochs)

Compiled 2026-11-10 UTC by a documentation-research subagent of this session; written to disk by
the main session (the subagent could not write files). Sources were only read or fetched.

- **NOAA requests:** 25, all through `phase0/noaa_fetch.py`, tags `doc_*`, first attempts, no
  retry; 24 returned HTTP 200, one 404. Each is in `run_log/noaa_requests.jsonl`.
- **Non-NOAA downloads:** 3, in `phase0/docs/nonnoaa/sources.jsonl`.
- **Saved copies** are named by their SHA-256 under `phase0/docs/`. "LM" is the HTTP
  Last-Modified header.
- **Verified by the main session** (grep on the saved bytes, 2026-11-10): the station list in
  `derive_bias.py` and in the dynamic-adjust script; the 11 rows of the constants file; the
  portal sentence "Operational implementation of the STOFS-3D-Atlantic [and STOFS-2D-Global]
  upgrade to v3.1 occurred at the 12 UTC cycle on August 17 2026"; the `noanomaly` lines of the
  2D anomaly script. The other quotes are the subagent's and were not re-checked line by line.
- **Main caveat:** the NCO code browser serves only `stofs.v3.1.7` (files dated 2026-10-23);
  `stofs.v3.1.6/` returned 404. All code quotes are v3.1.7; the sampled files name v3.1.4 and
  v3.1.6. The only change notice after go-live, SCN 26-98 (2 Nov 2026), concerns 3D-Pacific SHEF
  units, which suggests but does not prove that this is the only difference.

Labels: [DOC-NOAA], [DOC-code], [DOC-paper], [inference], [not found].

## 1. STOFS-3D-Atlantic v3.1 open-boundary bias adjustment

### 1a. The 11 stations [DOC-code]

8670870 Fort Pulaski GA · 8665530 Charleston SC · 8661070 Springmaid Pier SC · 8658163
Wrightsville Beach NC · 8651370 Duck NC · 8632200 Kiptopeke VA · 8557380 Lewes DE · 8536110 Cape
May NJ · 8534720 Atlantic City NJ · 8531680 Sandy Hook NJ · 8452660 Newport RI.

- **Source A**, `derive_bias.py`,
  https://www.nco.ncep.noaa.gov/pmb/codes/nwprod/stofs.v3.1.7/ush/stofs_3d_atl/pysh/derive_bias.py
  (retrieved 2026-11-10T03:44:35Z, LM 23 Oct 2026; `f51cb9d6….bin`), lines 236–243:
  ```
      # Station List (Starts from Fort Pulaski to Newport 11 stations - number of stations will be able to change)
      # Exclude the bad quality stations (ex. Beaufort: 8656483, Wachapreague: 8631044 etc.)
      # Exclude the stations with zero value at difference between xGEOID and NAVD88
      # (ex. Cape Henry: 8638999, Nantucket Island: 8449130 etc.)
      STA_LIST = ['8670870', '8665530', '8661070',
                  '8658163', '8651370', '8632200',
                  '8557380', '8536110', '8534720',
                  '8531680', '8452660']
  ```
- **Source B**, `stofs_3d_atl_create_obc_3d_th_dynamic_adjust.sh`, same tree under
  `ush/stofs_3d_atl/` (retrieved 03:43:43Z; `20487efb….bin`), line 98:
  `list_staID=(8670870 8665530 8661070 8658163 8651370 8632200 8557380 8536110 8534720 8531680 8452660)`.
- **Source C**, `fix/stofs_3d_atl/stofs_3d_atl_obc_adjust_msl_geoid.bp` (retrieved 03:45:41Z;
  `d0c4e3c2….bin`): the same 11 IDs with one constant each (−0.294 … −0.524 m).
- Secondary, not independent: a pull request in the author's own `nos-utils` repository (#63),
  which ports this code (`phase0/docs/nonnoaa/`).
- **File versus notice:** SCN 26-51 says Duck and Springmaid Pier are removed from the station
  output, but both are in the archived v3.1 station NetCDF files (166 records) of 2026-08-17 and
  2026-10-30 [P0, main session].

### 1b. Datum of the adjustment [DOC-code + inference]

- Source B lines 158–166 link the `…_msl_geoid.bp` constants as `diff.bp`; source A adds a
  per-station difference to the observations (`oyi_d = oyi + di`) and forms
  `bias = mtyi - soyi`.
- The 11 constants of `…_msl_geoid.bp` are identical, row for row, to the xGEOID20b→MSL station
  constants of `stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco` (§5; checked by script by the
  subagent). Variable names say "navd" (`noaa_navd.npz`, `navd_PR/`), which look like legacy
  names.
- Observations come from `$DCOMROOT/<YYYYMMDD>/coops_waterlvlobs/<id>.xml`; the 2D anomaly code
  treats the same feed as MSL-referenced (§2c).
- **[inference]** The bias is the 2-day mean, over the 11 stations, of (station output on LMSL)
  − (CO-OPS observation on MSL), formed in the model's xGEOID20b frame. The epoch of the MSL
  constants and the datum of the DCOM feed are not stated [not found].

### 1c. Window and application [DOC-code]

- `derive_bias.py … --duration 2`; model series from the previous cycle's `staout_1`.
  The secondary PR text gives the window as PDY−2 12:00 to PDY 12:00 [inference for the exact
  bounds]. Whether day 2 of that series is nowcast or the previous forecast is unverified.
- Hourly means (`resample('h').mean()`), a station is dropped above 20% NaN, rounded to 3
  decimals; no adjustment when observations are missing ("No adjustment is applied" / "Backup
  plan implemented.").
- Applied uniformly: `time_series(0,…) − adj0`, `time_series(1,…) − (adj0+adj1)/2`,
  `time_series(2:,…) − adj1` on the open-boundary elevation time series.

### 1d. Tidal filter [DOC-code]

None: `lpfilt` is imported but not called. 48 h ≈ 3.86 M2 periods [inference: tidal error enters
through incomplete cycles only].

## 2. STOFS-2D-Global station anomaly (bias) correction

- **Start [DOC-NOAA]:** v2.1.7, 12 UTC 14 May 2024. SCN 23-124 Updated (22 Apr 2024),
  https://weather.gov/media/notification/pdf_2023_24/scn23-124_stofs_upgrade_v2.1.4_aaf.pdf
  (`778f4525….pdf`): "Inclusion of bias correction at station locations where … CO-OPS
  observations are available. This bias correction a) computes the bias … by subtracting the
  combined (storm surge + tide) water level forecast guidance from the observed water level; b)
  removes this hourly bias from the current cycle's 6-hour nowcast; c) averages the bias over 5
  days using the most recent five (5) days of nowcasts and observations; and d) removes this
  average bias from the future forecast guidance (with a 12-hour linear interpolation from
  current bias to average bias)."
- **`points.cwl.nc` is the corrected file [DOC-code]:** `scripts/stofs_2d_glo/exstofs_2d_glo_post_anomaly.sh`
  (v3.1.7; `ceadcba0….bin`) builds `acwl.fort.61.nc` from model + anomaly and copies it to
  `$COMOUT/${RUN}.${cycle}.points.cwl.nc`; `points.cwl.noanomaly.nc` is the uncorrected copy.
  In v2.1 the corrected file is probably also `points.cwl.nc` [inference; v2.1 code not read].
  The `noanomaly` files are on S3 for every sampled date, including June–August [P0].
- **Datum [DOC-code + inference]:** observations from the same DCOM feed; `etweb_extract.py`
  (`a65956ee….bin`) forms obs − cwl on MSL (`--datum` default `msl`). Epoch of the constants
  [not found].
- **Method [DOC-code]:** `DaysToRead = 5`; anomaly "needs at least 12 values over the 5 day
  period"; range limit 3 ft (Gulf) or 5 ft (elsewhere); plain mean, no tidal filter. Exact
  station set [not found]; `stofs_2d_glo_station.ctl` (`3f53495c….bin`) lists 1,687 points.

## 3. Actual v3.1 start [DOC-NOAA]

- SCN 26-51 Updated (8 Jul 2026),
  https://www.weather.gov/media/notification/pdf_2026/SCN26-51_STOFS.v3.1_Updated.aaa.pdf
  (`68bd4ca6….pdf`): "Updated to reflect a new date of Aug 11, 2026".
- NOAA STOFS portal, https://polar.ncep.noaa.gov/estofs/atl.htm (`40a2a7de….htm`, LM 18 Aug
  2026) and https://polar.ncep.noaa.gov/estofs/glo.htm (`5c2b5aeb….htm`): "Operational
  implementation of the STOFS-3D-Atlantic [STOFS-2D-Global] upgrade to v3.1 occurred at the 12
  UTC cycle on August 17 2026."
- No notice for the 11 → 17 August slip was found [not found].
- SCN 26-98 (2 Nov 2026, `795a6b2f….pdf`): v3.1 bug fix, 3D-Pacific SHEF units only.

## 4. CO-OPS tidal-datum epochs [DOC-NOAA]

- https://tidesandcurrents.noaa.gov/datum-updates/ntde/ (`4fa508e4….html`): "NOAA currently
  utilizes the 1983-2001 National Tidal Datum Epoch. … will be replaced by the fifth iteration
  of the NTDE … 2002-2020. … The current proposed release date for new NTDE products is in 2029."
- https://tidesandcurrents.noaa.gov/press/tidaldatum.html (`85f46336….html`): "tidal datums at
  stations exhibiting anomalous trends are computed from MSL observations for the most recent 5
  year time period … The current modified procedure datum update for 2012-2016, will affect …
  Control Stations 8761724 Grand Isle, LA 9452210 Juneau, AK 9452400 Skagway, AK 9455500
  Seldovia, AK 9457292 Kodiak, AK 9453220 Yakutat, AK" (plus subordinate LA and AK stations).
  None of the 11 boundary stations is listed [inference].

## 5. xGEOID20b → LMSL station conversion [DOC-code]

`fix/stofs_3d_atl/stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco` (`f6a183d8….bin`): 166 lines
`zeta(:,k)=zeta(:,k)-float(c_k);`, c_k from about −0.52 to +0.59 m. Source and epoch of the
constants not stated; VDatum is not named [not found]. (The Boston package matched NOAA's
constants to VDatum xGEOID20b→LMSL within millimetres at four of five checked stations [BOS].)

## 6. Mean-level reference of the models (only what was found)

- atl.htm: "Copernicus gridded Absolute Dynamic Topography (ADT) satellite altimetry in
  combination with G-RTOFS for subtidal water level"; SCN 23-124: "xGEOID20b is used instead of
  … NAVD88"; `stofs_3d_atl_adt_cvtz.nco` (`51e9c7d4….bin`): `surf_el=float(adt-0.45);` — what
  this offset ties ADT to is not stated [not found].
- Cui et al. preprint (VIMS, `nonnoaa/twl_part1_vims_preprint.docx`): "a uniform adjustment of
  -0.42 m is sufficient … -0.32 m was found to give even better results" [DOC-paper].
- No source states that either model's mean level is tied to an epoch MSL, present-day MSL or a
  geoid by construction [not found]. [inference] The v3.1 daily adjustment pulls the boundary
  level toward the 11-station mean observed level of the previous two days.

## URLs consulted

NOAA (25, all through the fetcher): the NCO `nwprod/` listing and `stofs.v3.1.6/` (404); the
v3.1.7 `ush/`, `ush/stofs_3d_atl/`, `pysh/`, `fix/stofs_3d_atl/`, `ush/stofs_2d_glo/`,
`scripts/stofs_2d_glo/` listings; `stofs_3d_atl_create_obc_3d_th_dynamic_adjust.sh`,
`derive_bias.py`, `create_npz_NOAA.py`, `stofs_3d_atl_obc_adjust_msl_geoid.bp`,
`stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco`, `stofs_3d_atl_adt_cvtz.nco`, `etweb_extract.py`,
`stofs_2d_glo_anomaly.f`, `exstofs_2d_glo_post_anomaly.sh`, `stofs_2d_glo_station.ctl`;
polar.ncep.noaa.gov `estofs/glo.htm`, `estofs/atl.htm`; SCN 26-51 Updated, SCN 26-98, SCN 23-124
Updated; CO-OPS `datum-updates/ntde/`, `press/tidaldatum.html`.
Non-NOAA (downloaded): the VIMS preprint; `nos-utils` PR #63 (API JSON and HTML).
Tried, HTTP 403: ScienceDirect S1463500325001453.
