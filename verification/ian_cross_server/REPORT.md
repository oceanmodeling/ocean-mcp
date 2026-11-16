# WP2: scripted two-server MCP workflow, Hurricane Ian (2022)

Run date: 2026-11-06 (UTC). Branch `docs/ian-cross-server`, created from the local `origin/main` ref (`53fe506`) and not fetched. Live session: 2026-11-06 05:29:54.680Z to 05:30:15.615Z.

This is a **scripted two-server MCP workflow**. The tool sequence and every argument are fixed in `run_workflow.py`. No language model selected or invoked the tools.

## 1. Summary

1. **Both manuscript values were reproduced exactly** from the new live session.
   - Fort Myers (8725520): residual maximum **+2.209 m**, reached at **22:18 and again at 22:30 UTC**, 28 September 2022. The two times tie exactly.
   - St. Petersburg (8726520): residual minimum **−1.755 m** at **23:00 UTC**, 28 September. No tie.
2. **Setup.** One client process held two MCP stdio sessions at the same time, to two separate server processes:
   - `nhc-mcp` 0.1.1 (PID 1292133);
   - `coops-mcp` 0.1.1 (PID 1292137).

   Both were installed from their PyPI wheels, and the wheel SHA-256 values match PyPI. The installed source is identical, file for file, to `origin/main` `53fe506`. The client made seven sequential tool calls, with a 3 s pause before each call after the first.
3. **Inputs agree with the earlier saved responses** in `examples/`, value by value. The only differences are the four `retrieved_at` stamps. The best-track text is byte-identical to `examples/ian_besttrack_AL092022.json`: the same SHA-256, `32b21ee2…`.
4. **Data quality.** Each station has 720 of 720 six-minute observations and 720 predictions. There are no gaps, no missing values and no truncation. All observations are quality level `v` (verified), and none has a data flag set. Datum is MLLW, units metric, time zone GMT.
5. **Landfall record.** The best-track response contains a record at 19:05 UTC on 28 September (26.7°N, 82.2°W, 130 kt, 941 mb). It carries no landfall label and no record identifier. The landfall time and place are therefore cited from the NHC Tropical Cyclone Report. The version now online is revised 12 March 2026; the original is dated 2 April 2023.
6. **Offline replay.** `replay_offline.py` recomputes every number from the archived session with network access disabled. It passes 58 of 58 checks under both Python 3.13.2 and Python 3.12.3. In tamper tests it exited 1, once for an altered result and once for an altered observation.

## 2. What was run

| Step | Script | Python | Network |
|---|---|---|---|
| Fresh environment from PyPI wheels, hashes checked | `make_env.py` | `python3` on PATH (miniconda 3.13.2), stdlib only | PyPI |
| List tools and schemas over stdio | `inspect_tools.py` | env 3.13.12 | none |
| Live session, 7 tool calls | `run_workflow.py` | env 3.13.12 | NOAA, through the servers |
| Analysis | `analyze.py` | `python3 -I` (miniconda 3.13.2), stdlib only | none |
| Cited documents: checksum and quotation check | `record_references.py` | `python3 -I` (miniconda 3.13.2) with pypdf 6.12.0 | none (files fetched beforehand with curl) |
| Manifest | `build_manifest.py` | `python3` on PATH (miniconda 3.13.2), stdlib only | none |
| Offline replay | `replay_offline.py` | `python3 -I` (miniconda 3.13.2), and again with `/usr/bin/python3.12 -I` (3.12.3); stdlib only | blocked |

**Formatting after the run.** After the live run, all seven scripts were reformatted with `ruff format` (ruff 0.15.2). Lint passes with `ruff check --select E,F,W --ignore E501`. For every script, the Python AST before and after formatting is identical, so the code that produced `session_record.json` and `env_provenance.json` is the code archived here. The comparison was against a copy taken before formatting.

**Environment.** Python 3.13.12 (uv-managed) and uv 0.10.4, on Linux 6.6.87.2-microsoft-standard-WSL2 (Ubuntu 24.04 under WSL2).

**Packages.**

| Package | Version | Wheel SHA-256 (matches PyPI) |
|---|---|---|
| nhc-mcp | 0.1.1 | `34bd7bb5b2b1dc6995d20572acff5afc47b198d69570b93bfd5e037035811c25` |
| coops-mcp | 0.1.1 | `f9630bc8bf7e024aff0ade1ec2e9a696487e3fdccc1e2b9860a6c5e64846f210` |

- MCP SDK 1.30.0, httpx 0.28.1, pydantic 2.14.3. The full freeze is in `env_provenance.json`.
- Both servers report `serverInfo.version` = 1.30.0, which is the SDK version. Package versions therefore come from distribution metadata (`importlib.metadata`), not from the server.

**WP0 manifest.**
- `verification_release_readiness/manifest.json` sits in the main checkout and is untracked. SHA-256: `09e1f8e9…6479e`. Generated 2026-11-06T05:22:38Z.
- It is archived here as `wp0_manifest_snapshot.json`.
- The archived snapshot differs from the original by one renamed label, which is why its checksum differs from the one above; no value or count changed.
- For both packages it records the same versions, wheel SHA-256 values and tool names as this run (checked in `manifest.json` → `wp0_manifest.agreement_with_wp2_environment`).

**WP1 record/replay launcher.** None was found in the repository, so none was used.

## 3. Tool schemas used

All four tools named in the brief exist under those names; I confirmed this from `tools/list`. Every argument was checked against the listed `inputSchema` (with `jsonschema`) before the call, and every one was a listed property. Each tool declares an output schema `{"result": string}`. Every response carried the same string in `content[0].text` and `structuredContent.result`.

| Server | Tool | Required | Arguments passed |
|---|---|---|---|
| nhc-mcp | `nhc_get_best_track` | `storm_id` | `storm_id="AL092022"`, `response_format="json"` (enum: markdown, json, geojson) |
| coops-mcp | `coops_get_station` | `station_id` | `station_id`, `expand=["details","datums"]`, `units="metric"`. This tool has no `response_format`; it returns markdown only |
| coops-mcp | `coops_get_water_levels` | `station_id` | `station_id`, `begin_date="2022-09-27"`, `end_date="2022-09-29"`, `datum="MLLW"`, `units="metric"`, `time_zone="gmt"`, `interval="6"`, `response_format="json"`, `max_records=2000` |
| coops-mcp | `coops_get_tide_predictions` | `station_id`, `begin_date`, `end_date` | same arguments as `coops_get_water_levels` |

The window and the arguments are those of `manuscript-final-runs-2026-07-27.md` §1a. The default `max_records=2000` exceeds the 720 records in the window, and every response reports `truncated: false` with `record_count` = `total_count` = 720, so it did not need raising. Full listings of both servers (5 and 12 tools) are in `tool_schemas.json` and in `session_record.json`. The two listings are identical.

## 4. The session

| # | Server | Tool | Station | Started (UTC) | s | Text SHA-256 (first 16) |
|---|---|---|---|---|---|---|
| 1 | nhc-mcp | nhc_get_best_track | AL092022 | 05:29:55.795 | 0.61 | `32b21ee2b7793dbd` |
| 2 | coops-mcp | coops_get_station | 8725520 | 05:29:59.406 | 0.29 | `80a7335c70615c96` |
| 3 | coops-mcp | coops_get_water_levels | 8725520 | 05:30:02.704 | 0.10 | `f2b285a4ec9a7916` |
| 4 | coops-mcp | coops_get_tide_predictions | 8725520 | 05:30:05.812 | 0.09 | `eccf1e1ce47e0243` |
| 5 | coops-mcp | coops_get_station | 8726520 | 05:30:08.905 | 0.05 | `d64e0a48410aa7c3` |
| 6 | coops-mcp | coops_get_water_levels | 8726520 | 05:30:11.964 | 0.13 | `1bb40c28227f6312` |
| 7 | coops-mcp | coops_get_tide_predictions | 8726520 | 05:30:15.106 | 0.31 | `ca8184420cfbd037` |

**Process evidence.** Before the first call and after the last, the client (PID 1292126) had exactly two child processes: `…/wp2_env/bin/python -m nhc_mcp` and `…/wp2_env/bin/python -m coops_mcp`. The PIDs were the same at both points. The servers ran from a neutral temporary working directory, so they could import only their installed wheels.

**What each call record holds.** `session_record.json` stores, for each call:
- the server, tool and arguments;
- the argument check;
- the pause before the call, start and finish timestamps, and elapsed time;
- the complete `CallToolResult`;
- the text and result SHA-256.

It also stores, for each server, the initialize result, the tool listing and the server's stderr log. The stderr logs show the upstream requests. nhc-mcp resolved `https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt` from the NHC data index at call time. coops-mcp called the CO-OPS `mdapi` stations endpoint and the `datagetter`.

## 5. Input verification

| | Fort Myers 8725520 | St. Petersburg 8726520 |
|---|---|---|
| Observations: `record_count` / `total_count` / `truncated` | 720 / 720 / false | 720 / 720 / false |
| 6-min grid 2022-09-27 00:00 to 09-29 23:54 | 720 of 720 slots, 0 missing, 0 duplicates, sorted | same |
| Missing values | 0 | 0 |
| Quality level `q` | 720 × `v` (verified) | 720 × `v` |
| Data flags `f` (I, F, R, T) | 0 records with any flag set | 0 |
| Predictions: count / grid / missing | 720 / complete / 0 | 720 / complete / 0 |
| Datum, units, time zone, interval (echoed in `request_params`) | MLLW, metric, gmt, 6 | same |
| Observed maximum, MLLW | 2.613 m at 28 Sep 22:30 | 1.013 m at 27 Sep 07:12 |
| Observed minimum, MLLW | 0.067 m at 28 Sep 13:00 | −1.201 m at 28 Sep 23:12 |
| Coordinates, `coops_get_station` | 26.647778, −81.87111 | 27.7606, −82.6269 |
| Coordinates, observation envelope | 26.6478, −81.8711 (2.6 m apart) | 27.7606, −82.6269 (identical) |
| Affiliation as returned | NWLON | NWLORTS |

**Flag order.** The order is from the CO-OPS Data API response help, quoted and checksummed in `references.json`. For verified water level it is I (inferred), F (flat tolerance), R (rate of change), T (expected maximum/minimum exceeded). Preliminary data uses O, F, R, L; no record here is preliminary.

**Tidal epoch.** No epoch reaches the client through MCP. `coops_get_station` with `expand=["details","datums"]` returned `origyear` under details, plus 15 datum values above station datum (STND). The prediction envelope does not name an epoch either. The 1983–2001 epoch stated in July (`manuscript-final-runs-2026-07-27.md` §1e) came from outside MCP and was not rechecked in this run.

**Comparison with the saved responses** (`analyze.compare_saved`: a recursive comparison of every key and list element):

| Saved file (SHA-256) | Compared with | Differences |
|---|---|---|
| `examples/ian_besttrack_AL092022.json` (`32b21ee2…60e0`) | call 1 | none. The new text has the same SHA-256 as the file |
| `examples/ian_coops_water_levels.json` (`bdb8e503…0048`), key 8725520 | call 3 | `retrieved_at` only: 2026-07-27T05:35:50 → 2026-11-06T05:30:02 |
| same file, key 8726520 | call 6 | `retrieved_at` only: 05:36:03 → 2026-11-06T05:30:12 |
| `examples/ian_coops_tide_predictions.json` (`2914d94a…f658`), key 8725520 | call 4 | `retrieved_at` only: 2026-07-27T06:25:32 → 2026-11-06T05:30:05 |
| same file, key 8726520 | call 7 | `retrieved_at` only: 06:25:32 → 2026-11-06T05:30:15 |

All 720 × 4 values (`t`, `v`, plus `s`, `f`, `q` for observations), the request parameters, metadata and counts are unchanged since July. The saved CO-OPS files are dictionaries keyed by station that hold the two tool responses; the best-track file is the tool's text response itself.

**Extra consistency check, outside the requested pipeline.** The Fort Myers observed peak is 2.613 m MLLW. `coops_get_station` returns MHHW − MLLW = 1.730 − 1.329 = 0.401 m. The peak is therefore 2.212 m above MHHW, which is 7.26 ft. That equals the TCR statement on p. 9: "The NOS tide gauge near downtown Fort Myers measured 7.26 ft above MHHW".

## 6. Residuals

`analyze.residuals` computes residual = observed − predicted on exact matches of the CO-OPS timestamp string. It uses decimal arithmetic, so a tie is a tie and not a floating-point accident, and it does no interpolation. All 720 timestamps match at both stations. `replay_offline.py` repeats the extremes with a separate implementation in integer millimetres.

| Station | Extreme | Value | Time (UTC, 28 Sep 2022) | Observed (m, MLLW) | Predicted (m, MLLW) | Ties |
|---|---|---|---|---|---|---|
| Fort Myers 8725520 | maximum | **+2.209 m** | 22:18 | 2.611 | 0.402 | 2 |
| | | **+2.209 m** | 22:30 | 2.613 | 0.404 | |
| St. Petersburg 8726520 | minimum | **−1.755 m** | 23:00 | −1.195 | 0.560 | 1 |

The other two extremes match the July values:
- Fort Myers minimum: −0.439 m at 09:18 UTC on 28 September (observed 0.072, predicted 0.511).
- St. Petersburg maximum: +0.299 m at 10:00 UTC on 27 September (observed 0.798, predicted 0.499).

The St. Petersburg minimum residual (23:00) and its observed minimum (−1.201 m at 23:12) fall at different times. At Fort Myers, the second tied maximum (22:30) coincides with the observed peak.

**Timing against the cited landfall (19:05 UTC):**
- Fort Myers first maximum: 193 min later (3 h 13 min).
- St. Petersburg minimum: 235 min later (3 h 55 min).
- The St. Petersburg minimum follows the first Fort Myers maximum by 42 min.

The residual contains every non-tidal signal, not storm surge alone.

## 7. Storm-centre geometry

**Method.**
- **Gauge coordinates:** from `coops_get_station`.
- **Storm centre:** from the `nhc_get_best_track` response. The best track is discrete. At each event time the centre is interpolated **linearly in time** between the bracketing fixes, 20:35 UTC on 28 September and 00:00 UTC on 29 September, with latitude and longitude each interpolated linearly in degrees. The interpolation fractions are 0.502 (22:18), 0.561 (22:30) and 0.707 (23:00).
- **Distance:** the haversine great-circle distance on a sphere of radius **6371.0088 km** (IUGG mean radius).
- **Bearing:** the initial great-circle bearing **from the storm centre to the gauge**, in degrees clockwise from true north.
- **Cross-check:** a WGS84 ellipsoidal distance (Vincenty inverse) differs from the spherical one by at most 0.27 km in any row. That is far below the 0.1° (about 11 km) precision of the best-track positions.
- **Sensitivity:** the bracketing-fix rows show it. The Fort Myers distance is 21.2 km at 20:35 and 63.7 km at 00:00; the St. Petersburg distance is 123.5 km and 110.7 km.

| Time (UTC) | Event | Storm centre (°N, °W) | Fort Myers (8725520) | St. Petersburg (8726520) |
|---|---|---|---|---|
| 28 Sep 22:18 | Fort Myers residual maximum, +2.209 m | 27.001, 81.849 (interpolated) | 39.3 km, 183° | 114.1 km, 318° |
| 28 Sep 22:30 | Fort Myers residual maximum, +2.209 m | 27.024, 81.832 (interpolated) | 42.1 km, 185° | 113.4 km, 316° |
| 28 Sep 23:00 | St. Petersburg residual minimum, -1.755 m | 27.083, 81.788 (interpolated) | 49.1 km, 190° | 112.0 km, 312° |
| 28 Sep 20:35 | Best-track fix (brackets the events) | 26.8, 82.0 | 21.2 km, 143° | 123.5 km, 330° |
| 29 Sep 00:00 | Best-track fix (brackets the events) | 27.2, 81.7 | 63.7 km, 195° | 110.7 km, 304° |

Distance: haversine great circle, sphere of radius 6371.0088 km. Bearing: initial bearing from the storm centre to the gauge, degrees clockwise from true north. Storm centre at event times: linear interpolation in time between the bracketing best-track fixes (20:35 and 00:00 UTC). Best-track positions are given to 0.1°.

At its first maximum (22:18), Fort Myers lay 39.3 km south (183°) of the interpolated centre. At its minimum (23:00), St. Petersburg lay 112.0 km north-west (312°) of it. By then the centre was inland: the TCR places landfalls at 19:05 and 20:35 UTC. The table describes timing and geometry only. It is not evidence about what set the size of either residual.

## 8. Landfall provenance

**Cited.** The NHC Tropical Cyclone Report, Hurricane Ian (AL092022), by L. Bucci, L. Alaka, A. Hagen, S. Delgado and J. Beven.
- The PDF at `https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf` (retrieved 2026-11-06 05:24:07 GMT; SHA-256 `804d2a86…5fce`) is dated **12 March 2026**. Its footnote reads: "Original report dated 2 April 2023. This version removes WeatherStem data…".
- p. 4: "…made landfall on the barrier island of Cayo Costa, Florida, at 1905 UTC 28 September with an intensity of 130 kt."
- Table 1, p. 21: "28 / 1905 26.7 82.2 941 130 Landfall near Cayo Costa, Florida".

`record_references.py` checks each quotation against the extracted page text.

**In the tool response.** There is a record `{"datetime": "20220928 1905 UTC", "lat": 26.7, "lon": -82.2, "max_wind": 130, "min_pressure": 941, "status": "HU", "category": "Category 4"}`.
- Its values equal the TCR Table 1 row.
- Every record has the same seven fields, and none of them is a landfall label or a record identifier. nhc-mcp derives `category` from `max_wind` (`classify_wind_speed`, `tools/history.py:114`).
- The response's top-level keys are `storm_id`, `source` ("HURDAT2"), `track_points` and `count`. It does not name the HURDAT2 file; only the server log does (§4).
- The HURDAT2 parser in nhc-mcp reads the record identifier (`utils.py:274`). `nhc_get_best_track` does not copy it into its output (`tools/history.py:81-91`), and nhc-mcp was not changed.

The response holds five records at non-synoptic times: 27 Sep 08:30, 28 Sep 02:00, 28 Sep 19:05, 28 Sep 20:35 and 30 Sep 18:05. TCR Table 1 lists all five as landfalls; the tool response does not say why they exist. **No record is labelled landfall in this work on the basis of the tool response.**

## 9. Differences from the earlier saved responses

None in the data. The only change is `retrieved_at` in the four CO-OPS responses (§5); the nhc-mcp JSON has no `retrieved_at`. Three points differ from earlier descriptions:
- **The 19:05 landfall marker.** The docstring of `examples/ian_water_levels_residuals.py` attributes it to "HURDAT2 'L'". That identifier is not in the MCP response, so the marker should be attributed to the TCR.
- **The tidal epoch.** It is not in any MCP response, as already noted in July (§5).
- **The TCR version.** The version online is now the 12 March 2026 revision. The values used here (19:05 UTC, Cayo Costa, 130 kt, 941 mb) are as quoted from it. The 2023 original was not retrieved, so the two versions were not compared.

## 10. Figure decision

No figure was changed or added. The existing two-panel figure (`examples/ian_water_levels_residuals.png`) already shows both series, both extremes and the landfall line. The new information is geometry: five rows of distance and bearing, which a table carries. A track map would need a coastline from a non-MCP source, a second unarchived input. `geometry_table.md` is the proposed supplement table.

## 11. Limitations

- **One live run.** Upstream data can change: CO-OPS verified data are re-verified rarely, and NHC reissues HURDAT2 each year. A rerun may resolve a different HURDAT2 file, and the response does not record which file was used.
- **One environment.** Client and servers share one virtual environment. The servers are separate processes, not separate installations.
- **Coordinates come from markdown.** `coops_get_station` returns markdown only, so `analyze.py` parses the coordinates and datums with regular expressions. The observation envelope gives the same coordinates to 4 decimals, 2.6 m apart at most.
- **Geometry precision.** Best-track positions are rounded to 0.1° and interpolated linearly between fixes 3 h 25 min apart. After 19:05 UTC the centre is over land. Distances are reported to 0.1 km in the table; that is the precision of the arithmetic, not of the storm position.
- **Cited documents.** The TCR and the CO-OPS help page were retrieved with curl outside the MCP session. They are identified by URL and SHA-256 and are not archived here (the PDF is 7 MB).
- **Linux-specific evidence.** The process evidence uses `/proc`.
- **What the replay checks.** `replay_offline.py` checks the geometry table inside this report verbatim. It does not check the numbers quoted in this report's prose or in `MANUSCRIPT_RECOMMENDATION.md`; those were copied from `results.json` by hand.

## 12. What was not run

- No language model or agent, and no natural-language prompt.
- No change to `nhc-mcp`, `coops-mcp` or any other server, no server test suite (WP0 covers these), and no markdown or GeoJSON response formats.
- No figure regenerated. `examples/ian_water_levels_residuals.py` was not run.
- No tidal-epoch retrieval, and no call to `coops_get_datums`.
- Python 3.11 and 3.12 were not tried. Only 3.13.12 was used for the session.
- The 2023 original of the TCR was not retrieved.
- No push, pull, fetch, merge, rebase, tag, publish or upload. The manuscript was not edited; both local `.docx` files still have SHA-256 `d42bdbac…9dfa57`.

## 13. Reproduce

```bash
cd verification/ian_cross_server
python3 make_env.py /path/to/new-env                  # PyPI wheels, hashes checked
/path/to/new-env/bin/python inspect_tools.py          # tools/list for both servers
/path/to/new-env/bin/python run_workflow.py           # live: overwrites session_record.json
python3 -I analyze.py                                 # results.json, geometry_table.md
curl -sSfL -D tcr.headers -o AL092022_Ian.pdf https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf
curl -sSfL -D help.headers -o responseHelp.html https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html
python record_references.py --tcr AL092022_Ian.pdf --tcr-headers tcr.headers \
    --coops-help responseHelp.html --coops-help-headers help.headers   # needs pypdf
python3 -I build_manifest.py                          # manifest.json
python3 -I replay_offline.py                          # offline; exit 1 on any difference
```

To check the archive, run only the last command. A live rerun produces a new session record with new timestamps and `retrieved_at` values, so its `results.json` differs from the archived one in those fields.

**Package location.** The package was first committed as `verification_ian_cross_server/` at the repository root and later moved to `verification/ian_cross_server/`. `analyze.py`, `make_env.py` and `build_manifest.py` now take the repository root two folders up instead of one; nothing else in them changed. `manifest.json` records their new SHA-256 values and is otherwise unchanged. The manifest before the move had SHA-256 `9541aea606758f39d01e7878cf409a28b9cb9d50a5bf01e55f33ecba58f0a92f`.

## 14. Files

| File | Content |
|---|---|
| `session_record.json` | The complete session, in call order |
| `results.json` | Every computed number |
| `geometry_table.md` | The table in §7, generated |
| `manifest.json` | Versions, wheel hashes, per-call and per-file SHA-256, WP0 agreement |
| `env_provenance.json` | Wheel URLs and hashes, freeze, comparison of installed source with the repository |
| `references.json` | TCR and CO-OPS help: URL, retrieval time, SHA-256, verified quotations |
| `tool_schemas.json` | `tools/list` of both servers |
| `wp0_manifest_snapshot.json` | Copy of the WP0 manifest |
| `make_env.py`, `inspect_tools.py`, `run_workflow.py`, `analyze.py`, `record_references.py`, `build_manifest.py`, `replay_offline.py` | Scripts |
| `MANUSCRIPT_RECOMMENDATION.md` | Proposed Section 3.2 text |
