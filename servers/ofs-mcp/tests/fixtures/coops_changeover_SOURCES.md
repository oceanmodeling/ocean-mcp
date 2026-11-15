# Sources of the CO-OPS changeover fixtures

Two excerpts of one real CO-OPS water-level response for station 8574680 (Baltimore, MD; CBOFS domain). It is the same product, units and time zone that `ofs_compare_with_coops` requests:

    https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&application=ocean-mcp&begin_date=20261025%2000:00&end_date=20261101%2003:00&datum=MLLW&station=8574680&time_zone=gmt&units=metric&format=json

| | |
|---|---|
| Retrieved | 2026-11-09T06:17:29Z |
| Bytes | 128,205 |
| SHA-256 of the response | `b47ab8d761ade4eebc9e21917105b00c012cebd5c52ae14202a0c02634f8ee15` |
| Rows | 1,711 six-minute readings |

Each fixture keeps the response's `metadata` and a contiguous run of its `data` rows, copied verbatim. It is the series as it stood just before a model output hour, so the latest observation lies 6 minutes before that hour. This is the newest-edge case of `ofs_compare_with_coops`, whose observation window ends at `min(now, model end)`. On some host time zones that edge lies across the local clock change.

| Fixture | `data` rows kept (0-based) | Times (UTC) | Changeover |
|---|---|---|---|
| `coops_8574680_us_changeover_excerpt.json` | 1680-1699 | 2026-11-01 00:00 to 01:54 | US fall-back, 2026-11-01 06:00 UTC. On an America/New_York host, naive "01:54" reads as EDT and "02:00" as EST |
| `coops_8574680_eu_changeover_excerpt.json` | 20-29 | 2026-10-25 02:00 to 02:54 | EU fall-back, 2026-10-25 01:00 UTC. On a Europe/Berlin host, naive "02:54" reads as CEST and "03:00" as CET |
