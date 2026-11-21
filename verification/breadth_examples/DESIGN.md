# Design: three short examples for servers the paper does not yet show, and a fourth

Frozen on 2026-11-21 (UTC), before any Part B recording. Later changes go in `AMENDMENTS.md`, each with its time, its reason, and whether it was made before or after values were seen.

These are **scripted MCP workflows**. Tools and arguments are fixed here and in `scripts/record_session1.py` and `scripts/record_b1_session2.py`. No language model is involved. Nothing here tests a safeguard, and none of it is an evaluation.

## 1. What had been seen before this design was written

The feasibility step (Phase 0, 2026-11-21 02:11–02:45 UTC) made one probe per example with the same wheels.

| Example | Seen in Phase 0 |
|---|---|
| B1 | For 44097, the tool's own comparison returned 3 pairs from the 2026-11-20 18z cycle and 48 observation rows with WVHT. Its statistics were not printed. |
| B2 | For CBOFS at Baltimore, 24 pairs and the datum fields: model `NAVD88`, observations `NAVD`. The statistics were not printed. |
| B3 | Both `vdatum_convert` results at Fort Myers were seen: MLLW→MHHW −0.4009 m, MLLW→NAVD88 −0.3208 m. The `coops_get_datums` values were masked. The conversion involves no selection, so no rule below depends on what was seen. |
| B4 | One 2×2 SST area call. HYCOM's newest run was 2026-11-16 12Z. |

## 2. Servers

Released PyPI wheels, one process per server, neutral working directory.

| Server | Version | Wheel SHA-256 |
|---|---|---|
| ww3-mcp | 0.1.3 | `8825e2ce75b1f102f1561c68ac03de12de93e98cbc90090d68a2d3a60b1c942d` |
| ndbc-mcp | 0.1.2 | `0ad49f38aa4822bdfa03be5fe3be381d28b6998c417ac475f5f2184af35c6817` |
| ofs-mcp | 0.1.3 | `f2f4943b0bf0594f2480c93831f0604aa2816365b2c5415e8cc42f5de162de6c` |
| coops-mcp | 0.1.1 | `f9630bc8bf7e024aff0ade1ec2e9a696487e3fdccc1e2b9860a6c5e64846f210` |
| vdatum-mcp | 0.1.1 | `80f3f4ec22f331f37aa341300ea69a7722c7e840ec6d8efc5f45da4d7973fa40` |
| rtofs-mcp | 0.1.4 | `f943d3db9d28c61a8126c99ed569c64bb79e6d9f92338477e75e090839aac033` |

**Session 1.** One client process holds sessions to all six servers and runs B1 (first part), B2, B3 and B4 in that order. There is a 3 s pause before each call after the first, and every server's stderr log is archived.

**Session 2.** A second client process runs B1 (second part) at least 72 h later (section 3.2).

## 3. B1: GFS-Wave forecast against an NDBC buoy (ww3-mcp, ndbc-mcp), two sessions

**Buoy order:** 44097 (Block Island); then 44025; then 41002.

A buoy **has data** if both hold:
- `ndbc_get_station` returns a latitude and a longitude;
- the tool's own comparison (S1.2) reports `observation_window.rows_with_wvht` ≥ 1.

Otherwise the next buoy in the order is tried.

### 3.1 Session 1 (2026-11-21)

| # | Server | Tool | Arguments |
|---|---|---|---|
| S1.1 | ndbc-mcp | `ndbc_get_station` | `station_id` |
| S1.2 | ww3-mcp | `ww3_compare_forecast_with_buoy` | `station_id`, `buoy_lat`, `buoy_lon` (from S1.1), `grid="global.0p25"`, `hours_to_compare=24`, `response_format="json"` |
| S1.3 | ww3-mcp | `ww3_get_forecast_at_point` | `latitude`, `longitude` (from S1.1), `grid="global.0p25"`, `variables=["HTSGW"]`, `max_hours=72`, `step_hours=3`, `response_format="json"` |

- **S1.2** is the tool's own comparison. It is archived, and its pair count and pairing behaviour are reported.
- **S1.3** is the forecast that session 2 pairs against. The cycle is the newest one the tool resolves at call time; no cycle argument exists.
- **Acceptance.** S1.3 must return all 25 valid times from 0 to 72 h. The tool silently skips forecast hours it cannot fetch. If fewer come back, S1.3 is repeated once after 30 minutes and the repeat is logged.
- **Cycle check.** If S1.2 and S1.3 report different cycles, this is reported; S1.3's cycle is the one used.

### 3.2 Session 2 (no earlier than the S1.3 cycle time + 73 h)

| # | Server | Tool | Arguments |
|---|---|---|---|
| S2.1 | ndbc-mcp | `ndbc_get_observations` | `station_id`, `hours=H`, `variables=["WVHT"]`, `response_format="json"`, `max_records=2000` |

`H` is the whole number of hours from the cycle time to the call time, rounded up, plus 6. It must be at most 1080.

### 3.3 Pairing and statistics (client, fixed now)

**Pairing.** For each forecast valid time `t_f` in S1.3, take the observation in S2.1 with non-null WVHT whose time is nearest to `t_f`.
- It must be within 30 minutes (inclusive).
- Equidistant observations: the earlier one.
- A valid time with no observation in that range gets no pair.

**Statistics.** Over the `n` pairs (F = forecast HTSGW, O = observed WVHT, both in m):
- bias = mean(F − O);
- RMSE = sqrt(mean((F − O)²));
- MAE = mean(|F − O|);
- Pearson r, if n ≥ 3;
- the largest |F − O| and its time.

All are computed in `scripts/analyze_b1.py`, on the full stored values, and rounded to 3 decimals only when reported.

### 3.4 Figure

One panel, 90 mm wide:
- the forecast as a line with markers at the 3-hourly valid times;
- the observations as a line, broken at gaps longer than 1.5 times the median interval;
- the client statistics in a box labelled as computed by the client;
- the pair count of the tool's own comparison (S1.2) in the caption.

## 4. B2: regional model against a gauge (ofs-mcp, coops-mcp)

**Order:** CBOFS at Baltimore (8574680); then DBOFS at Philadelphia (8545240); then NGOFS2 at Galveston Pier 21 (8771450).

A pair **has data** if `ofs_compare_with_coops` returns JSON with `stats.n` ≥ 1. Otherwise the next pair is tried.

| # | Server | Tool | Arguments |
|---|---|---|---|
| C1 | ofs-mcp | `ofs_compare_with_coops` | `station_id`, `model`, `hours_to_compare=24`, `response_format="json"` |
| C2 | coops-mcp | `coops_get_datums` | `station_id`, `units="metric"` |

**Behaviour of C1.**
- The window is the 24 h ending at call time.
- The model series comes from the THREDDS FMRC "best" aggregation, not from one cycle, so the brief's "12:00 UTC cycle" rule cannot apply here (`AMENDMENTS.md` B1).
- The datum is whatever the tool states: `model_datum` comes from the server's fixed model table, and `obs_datum` is the CO-OPS datum the tool requested.
- C2 shows which datums CO-OPS publishes for the station.

**Figure.** One panel, 90 mm wide:
- observed and model water level against time;
- each legend entry carrying its datum as the tool states it;
- the statistics the tool returned (bias, RMSE, MAE, peak error, correlation, n) in a box labelled as returned by the tool.

The report notes that the tool pairs a fixed, documented datum: it neither resolves the datum per file nor declines.

## 5. B3: vertical-datum conversion checked against published datums (vdatum-mcp, coops-mcp)

**Position.** Fort Myers (CO-OPS 8725520), latitude `26.647778`, longitude `-81.87111`. This is the position `coops_get_station` returned in `verification/ian_cross_server/session_record.json` (call 2). The recording script checks it against that text before calling.

**Value.** The Fort Myers observed peak, 2.613 m above MLLW, from the same package.

| # | Server | Tool | Arguments |
|---|---|---|---|
| V1 | vdatum-mcp | `vdatum_convert` | `datum_from="mllw"`, `datum_to="mhhw"`, `lat="26.647778"`, `lon="-81.87111"`, `z="2.613"`, `online=true` |
| V2 | vdatum-mcp | `vdatum_convert` | same, `datum_to="navd88"` |
| V3 | coops-mcp | `coops_get_datums` | `station_id="8725520"`, `units="metric"` |

**From the station datums (V3, metres above station datum STND):**
- z_MHHW = 2.613 − (MHHW − MLLW);
- z_NAVD88 = 2.613 − (NAVD88 − MLLW).

**Arithmetic.** Integer millimetres for the CO-OPS values, which are given to 1 mm. vdatum's output is given to 0.1 mm and is converted to tenths of a millimetre.

**Result.** A table (no figure) with:
- both results from each source;
- the vdatum − CO-OPS difference in mm;
- the uncertainty each source states (from the responses alone).

**Offline limit.** The conversion needs the network: vdatum-mcp fetches its grids over HTTPS (Phase 0). `run_all.sh` replays the archived responses; it cannot rerun the conversion offline, and the report says so.

## 6. B4: temperature section across the Gulf Stream off Cape Hatteras (rtofs-mcp)

| # | Server | Tool | Arguments |
|---|---|---|---|
| T1 | rtofs-mcp | `rtofs_get_latest_time` | `dataset="sst"`, `response_format="json"` (the 3D temperature dataset) |
| T2 | rtofs-mcp | `rtofs_get_transect` | `lat_start=35.55, lon_start=-75.25, lat_end=33.95, lon_end=-73.30, variable="temperature", time=<T>, n_points=20, response_format="json"` |
| T3 | rtofs-mcp | `rtofs_get_profile_forecast` | at the T2 midpoint along the line (the tool's point 10, computed the same way as the tool does), `variable="temperature"`, `time=<T>`, `response_format="json"` |

**Line.**
- It starts on the shelf about 20 km off the Outer Banks and runs about 250 km to the south-east, at a bearing of roughly 135°, across the Gulf Stream where it leaves the shelf.
- The tool spaces its 20 points linearly in latitude and longitude.

**Time `T`.** The most recent 3-hourly step at or before the call time (00, 03, …, 21 UTC), formatted `YYYY-MM-DDTHH:00:00Z`.
- It must lie between T1's `first_time` and `last_time`.
- T2's JSON carries no time, so T3 echoes the time step THREDDS returned for the same request.

**Model run.**
- The caption states T1's `latest_run`.
- If `T` is not earlier than `latest_run`, the FMRC "best" aggregation serves `T` from that run. This is an inference from how a best aggregation is built, stated as such.
- If `T` is earlier than `latest_run`, the run cannot be named from the responses, and the caption says so.

**Depth range shown.** 0–1000 m.

**Plot.** The section is drawn as cells:
- x is the tool's `distance_km`, y the tool's depth levels;
- cell edges lie midway between neighbouring points and levels;
- there is no interpolation.

**Failure.** If T2 returns no JSON, or fewer than 10 of its 20 profiles have at least one level, B4 is skipped and the report says so.

**Figure.** One panel, 190 mm wide.

## 7. Offline replay

`run_all.sh` needs no network. It:
1. checks the SHA-256 of every archived file against `archive/MANIFEST.sha256`;
2. re-runs every analysis and figure script;
3. compares every result and figure file with `results/SHA256SUMS`;
4. exits non-zero on any mismatch.

**Environment.**
- Analysis: standard library.
- Figures: the pinned plotting set in `scripts/requirements-figures.txt`, from the uv cache with `--offline`.

**B1 before session 2.** Until session 2 is archived, B1's pairing, statistics and figure do not exist yet. `run_all.sh` then checks session 1 only and says so.
