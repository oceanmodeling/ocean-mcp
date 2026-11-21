# Amendments

Changes to the brief's rules, or to `DESIGN.md` after it was frozen, in the order they were made. Times are UTC.

**Basis for B1–B4.** All four come from the feasibility report and the author's reply, received on 2026-11-21 before 17:28. They were written into `DESIGN.md` before it was first committed and before any Part B recording.

**What had been seen.** `DESIGN.md` §1 lists everything seen when these were made. The only values seen are B3's two conversions; B3's design is unchanged from the brief.

## B1. Model cycle for B1 and B2 (made before any value was seen)

**Brief.** The 12:00 UTC cycle of the recording day.

**Amended.**
- **B1:** the newest GFS-Wave cycle that `ww3_get_forecast_at_point` resolves at call time, to at least 72 h. The tool has no cycle argument.
- **B2:** the series `ofs_compare_with_coops` returns. It is the THREDDS FMRC "best" aggregation, not one cycle, and the tool has no cycle argument.

## B2. B1 recorded in two sessions (made before any value was seen)

**Brief.** One panel with the forecast, the observations and the statistics the tool returned.

**Amended.**
- **Session 1 (today):** the forecast to 72 h, plus the tool's own comparison, archived with its pair count reported.
- **Session 2 (three days later):** the buoy observations from ndbc-mcp.
- **Pairing:** done by the client with the rule fixed in `DESIGN.md` §3.3 (nearest observation within 30 minutes).

**Reason.** The tool's comparison pairs only the hours between the cycle time and the latest buoy row: 3 pairs in the feasibility probe.

## B3. B4 as a section off Cape Hatteras (made before any value was seen)

**Brief.** A sea-surface-temperature section or map from rtofs-mcp for the same day.

**Amended.**
- A temperature section across the Gulf Stream off Cape Hatteras, from `rtofs_get_transect`.
- Endpoints and depth range are fixed in `DESIGN.md` §6.
- The model run time is stated in the caption.
- If the section tool fails, B4 is skipped and the report says so.

## B4. B3 recorded online (made after B3's values were seen in the feasibility step)

**Change.** `vdatum_convert` is called with `online=true`, because it cannot run offline. `run_all.sh` replays the archived responses, and the report says that the conversion itself cannot be rerun offline.

**Effect.** This changes no argument that affects the value.

## B5. Figure details (2026-11-21 about 18:15 UTC, after the values were seen; no number changes)

Made while drawing the figures. `DESIGN.md` did not fix these details.

- **B4 colours.** The colour scale runs from the lowest to the highest temperature at depths down to 1000 m. Small triangles above the section mark the 20 profile positions.
- **B2 statistics.** The statistics the tool returned are printed below the axes rather than in a box over the data.
