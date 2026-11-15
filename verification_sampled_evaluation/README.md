# WP5: sampled evaluation of the STOFS safeguards, and the mean-level bias across stations

**Status: complete (Phases 0 to 2 and the analysis).** The results are in `REPORT.md`;
`run_all.sh` repeats the analysis offline from the archives.

| Path | What |
|---|---|
| `DESIGN.md` | the frozen design: sampling rule, Study 1 reference and outcome classes, replay, budget, Study 2 hypotheses and decision rule, Study 3, human check |
| `phase0/` | feasibility probes: S3 listings, station inventory and CO-OPS mapping, datums/epochs, CO-OPS behaviour, documentation findings (`docs/FINDINGS_docs.md`), the rate-limited fetcher `noaa_fetch.py` |
| `reference/` | independent reference classification and statistics (no Ocean-MCP import); `selftest_wp1.py` and its result on previously seen WP1 files |
| `analysis/` | Study 1 grader, Study 2 regression and decision rule, Study 3 Boston decomposition |
| `replay/` | WP1 launcher (byte-identical copy), `wp5_launcher.py` (three added CO-OPS rules), session runners |
| `phase2/` | `plan.py` (the request plan and budget, `fetch_plan.json`), `index_from_fetchlog.py` |
| `human_check/draw.py` | the frozen 30-case sampling rule |
| `environment/` | package pins (from WP1) for the reference and MCP environments |
| `run_log/noaa_requests.jsonl` | every NOAA request: URL, UTC times, status, size, SHA-256 |
