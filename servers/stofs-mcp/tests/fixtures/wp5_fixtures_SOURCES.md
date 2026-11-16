# Sources of the WP5-derived test fixtures

All four are verbatim bytes of real NOAA answers archived by the WP5 sampled evaluation
(`eval/sampled-evaluation`, `verification/sampled_evaluation/data/archive/`, retrieved
2026-11-09/10 through a logged fetcher).

| Fixture | What it is | SHA-256 |
|---|---|---|
| `coops_http400_unsupported_datum.json` | CO-OPS Data API, HTTP 400, `datum=NAVD` at 8413320 Bar Harbor (MSL only): " The supported Datum values are: MHHW, MHW, MTL, MSL, MLW, MLLW, LWI, HWI" | `d93e3df070d03c6b509d11f476cb2019b7e2d6cca789ccc4fca11a96219a6a75` |
| `coops_http400_no_msl.json` | CO-OPS Data API, HTTP 400, `datum=MSL` at 8531232: "There is no MSL for the station: 8531232" | `cbc5dcd23ad587b249a90b0f9e7881c7014009d11cae8b4d5c737b3ebc7fef56` |
| `coops_no_data.json` | CO-OPS Data API, HTTP 200, a range without data: "No data was found. This product may not be offered at this station at the requested time." | `500bdf8b7540e3b178fa94711e95e7bd7633578dac4778da5faed9dc45cbfb0f` |
| `stofs2d_20261026_t12z_dup_excerpt.json` | Raw stored values of three records of the real STOFS-2D-Global 2026-10-26 12z station file (`source_sha256` inside): 'STKM1 SOUS41 8414721 ME Fort Point' (563), 'FRAM1 SOUS41 8414721 ME Frankfort' (823), 'CASM1 SOUS41 8418150 ME Portland' (3); first 180 time records (cycle − 6 h + 6 min to cycle + 12 h) | see the file |

The excerpt was written by `verification/regression_stofs_0.3.0/scripts/extract_dup_excerpt.py`
(`verification_post_wp5/` when it ran; the fixture's `extracted_by` keeps that path).
