# Amendments

Changes to the brief's rules, or to `DESIGN.md` after it was frozen, in the order they were made. Times are UTC.

## Labels

The amendments are labelled AM1, AM2, … so that none shares a name with the examples B1–B4. Until 2026-11-22 they were labelled B1–B5. `DESIGN.md` is frozen and still cites "`AMENDMENTS.md` B1" in §4; that is AM1.

| Old label | New label |
|---|---|
| B1 | AM1 |
| B2 | AM2 |
| B3 | AM3 |
| B4 | AM4 |
| B5 | AM5 |

Each amendment is listed once.

**Basis for AM1–AM4.** All four come from the feasibility report and the author's reply, received on 2026-11-21 before 17:28. They were written into `DESIGN.md` before it was first committed and before any Part B recording.

**What had been seen.** `DESIGN.md` §1 lists everything seen when these were made. The only values seen are example B3's two conversions; B3's design is unchanged from the brief.

## AM1. Model cycle for examples B1 and B2 (made before any value was seen)

**Brief.** The 12:00 UTC cycle of the recording day.

**Amended.**
- **Example B1:** the newest GFS-Wave cycle that `ww3_get_forecast_at_point` resolves at call time, to at least 72 h. The tool has no cycle argument.
- **Example B2:** the series `ofs_compare_with_coops` returns. It is the THREDDS FMRC "best" aggregation, not one cycle, and the tool has no cycle argument.

## AM2. Example B1 recorded in two sessions (made before any value was seen)

**Brief.** One panel with the forecast, the observations and the statistics the tool returned.

**Amended.**
- **Session 1 (2026-11-21):** the forecast to 72 h, plus the tool's own comparison, archived with its pair count reported.
- **Session 2 (three days later):** the buoy observations from ndbc-mcp.
- **Pairing:** done by the client with the rule fixed in `DESIGN.md` §3.3 (nearest observation within 30 minutes).

**Reason.** The tool's comparison pairs only the hours between the cycle time and the latest buoy row: 3 pairs in the feasibility probe.

## AM3. Example B4 as a section off Cape Hatteras (made before any value was seen)

**Brief.** A sea-surface-temperature section or map from rtofs-mcp for the same day.

**Amended.**
- A temperature section across the Gulf Stream off Cape Hatteras, from `rtofs_get_transect`.
- Endpoints and depth range are fixed in `DESIGN.md` §6.
- The model run time is stated in the caption.
- If the section tool fails, B4 is skipped and the report says so.

## AM4. Example B3 recorded online (made after B3's values were seen in the feasibility step)

**Change.** `vdatum_convert` is called with `online=true`, because it cannot run offline. `run_all.sh` replays the archived responses, and the report says that the conversion itself cannot be rerun offline.

**Effect.** This changes no argument that affects the value.

## AM5. Figure details (2026-11-21 about 18:15 UTC, after the values were seen; no number changes)

Made while drawing the figures. `DESIGN.md` did not fix these details.

- **B4 colour range.** The colour scale runs from the lowest to the highest temperature at depths down to 1000 m. Small triangles above the section mark the 20 profile positions.
- **B2 statistics.** The statistics the tool returned are printed below the axes rather than in a box over the data.

## AM6. Example B4 colour scale and sea bed (2026-11-22, layout; no number changes)

**Colour scale.** Temperature has no meaningful midpoint, so the diverging blue-white-orange scale is replaced by the sequential, perceptually uniform `viridis`. cmocean is not in the pinned plotting environment, so its "thermal" scale was not available. The range is unchanged (AM5).

**Sea bed.** Below the model sea bed the profile tool returns no values. The plot area there was white and is now light grey (`#d9d8d4`). The caption says so.

## AM7. Time-axis label of example B2 (2026-11-22, layout; no number changes)

The time axis of the B2 figure is labelled "Time (UTC), 2026". The B1 figure, drawn after session 2, will carry the same label.
