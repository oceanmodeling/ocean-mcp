# Changelog: ofs-mcp

## 0.1.3 (unreleased)

Changes since 0.1.2 (`ofs-mcp-v0.1.2`, commit `167c474`). One function changes: `utils.align_timeseries`, used by `ofs_compare_with_coops`. Tool signatures and response schemas are unchanged.

### Scientific corrections

- **Model-observation pairing no longer depends on the host time zone.**
  - **What it did.** `align_timeseries` parsed the UTC model times and CO-OPS observation times (requested with `time_zone=gmt`) as naive datetimes and called `.timestamp()`, which reads them as host-local time.
  - **The effect.** On a host with daylight saving, two times on either side of the local clock change came out an hour apart, so pairs within the 10-minute tolerance were lost. Seen on real CO-OPS 8574680 (Baltimore) rows:
    - **America/New_York host:** the model hour 2026-11-01 02:00 against the latest observation, 01:54 (0.632 m). The gap was computed as 66 minutes instead of 6, so there was no pair.
    - **Europe/Berlin host:** the model hour 2026-10-25 03:00 against 02:54 (0.611 m), so there was no pair.
  - **When it bites.** With an exact on-the-hour observation the pair was exact and unaffected. The loss needs the nearest observation to lie across the change, as at the newest edge of the observation window, which ends at `min(now, model end)`, or at a gap in the 6-minute series.
  - **The fix.** Parsed times are now UTC-aware before any arithmetic, as in stofs-mcp 0.3.0 and ww3-mcp 0.1.3. On a UTC host the results are unchanged.

### Known limitations

- Other naive-time code in ofs-mcp was checked and is host-independent: `utils.py`'s series analysis only sorts and subtracts naive times, and the forecast and discovery tools already attach `timezone.utc`.
