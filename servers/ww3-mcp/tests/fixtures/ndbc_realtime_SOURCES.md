# Sources of the NDBC realtime-file fixtures

Each `ndbc_realtime_<station>_excerpt.txt` is a verbatim excerpt: the first lines of NDBC's realtime2 standard meteorological file, copied byte for byte (two `#` header lines, then rows newest-first). The source files came from

    https://www.ndbc.noaa.gov/data/realtime2/<station>.txt

| Fixture | Source file | Bytes | SHA-256 of the source file | Retrieved (UTC) | Lines kept | Rows | Interval in the data |
|---|---|---:|---|---|---|---|---|
| `ndbc_realtime_41009_excerpt.txt` | `41009.txt` | 595,678 | `dd3317a3898c5cf0142891256f7eb802ce715cc4f5d86d4a35c1be0c5ccfba96` | 2026-11-09T02:22:25Z | 1-44 | 2026-11-09 02:00 back to 2026-11-08 19:10 | 10 min |
| `ndbc_realtime_44025_excerpt.txt` | `44025.txt` | 158,014 | `bbb28ae0290892c2e77969151d0fbde788416fa0a52de1885daad159e941b107` | 2026-11-09T02:21:47Z | 1-26 | 2026-11-09 01:40 back to 2026-11-08 13:10 | 30 min, with 60-min gaps at 19:40-20:40 and 17:40-18:40 |

How the files were obtained:

- **41009:** recorded by an instrumented ww3-mcp 0.1.3 MCP session, as the exact text `WW3Client.fetch_ndbc_realtime` received.
- **44025:** fetched directly.

In the 41009 file, the first 24 rows cover only 3 h 50 min (the 0.1.3 rule `records[:hours]`). In the 44025 file they cover 12.5 h. The interval is a property of the station, not of the format. NDBC says "Most stations report hourly" and that the reporting frequency can be checked on each station page (https://www.ndbc.noaa.gov/faq/rt_data_access.shtml).

## Changeover fixtures (pairing under host time zones)

Two more verbatim excerpts, from the same 41009 file (`41009.txt`, 595,678 bytes, SHA-256 `dd3317a3898c5cf0142891256f7eb802ce715cc4f5d86d4a35c1be0c5ccfba96`, retrieved 2026-11-09T02:22:25Z): the two `#` header lines plus contiguous rows. Each is the file as it stood just before a forecast valid time, so the latest buoy row with a WVHT lies 10 minutes before it, across a local clock change for some host time zones.

| Fixture | Source lines | Rows | Changeover it covers |
|---|---|---|---|
| `ndbc_realtime_41009_us_changeover_excerpt.txt` | 1-2, 1054-1068 | 2026-11-01 01:50 back to 2026-10-31 23:00 | US fall-back, 2026-11-01 06:00 UTC. On an America/New_York host, naive "01:50" reads as EDT and "02:00" as EST |
| `ndbc_realtime_41009_eu_changeover_excerpt.txt` | 1-2, 2040-2051 | 2026-10-25 02:50 back to 01:00 | EU fall-back, 2026-10-25 01:00 UTC. On a Europe/Berlin host, naive "02:50" reads as CEST and "03:00" (a GFS-Wave 3-hourly valid time) as CET |
