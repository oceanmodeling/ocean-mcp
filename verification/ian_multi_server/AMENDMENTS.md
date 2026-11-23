# Amendments

Changes to the brief's rules, or to `DESIGN.md` after it was frozen, in the order they were made. Times are UTC.

**Basis for A1–A4.** All four come from the author's reply to the feasibility report, received on 2026-11-21 before 17:28. They were written into `DESIGN.md` before it was first committed and before any Part A recording.

**What had been seen when they were made.** Only what `DESIGN.md` §1 lists:
- counts per aircraft call sign, without distances;
- counts per buoy, without values;
- three SFMR radial bins in the head of a July example file.

## A1. Buoy selection rule (made before any value was seen)

**Brief.** The buoy with significant wave height that passes closest to the best track in the window (27 September 00:00 to 30 September 00:00 UTC), ties broken by the most valid records.

**Amended.** The buoy with significant wave height whose closest approach to the best track **between 00:00 UTC 27 September and landfall (19:05 UTC 28 September 2022)** is smallest; ties by valid count.

**Reason.** Under the brief's rule the selection was 41113 (Cape Canaveral Nearshore), which lies on the Atlantic side, where the storm left the coast. That outcome was known from positions and counts only.

**Outcome.** 42097 (Pulley Ridge, FL), 86.1 km at 08:30 UTC on 28 September. The author asked to be told of it before Part A was recorded.

## A2. Reconnaissance source and rule (made before any value was seen)

**Brief.** SFMR surface wind and flight-level wind for the mission with the most SFMR records within 150 km of the best-track centre.

**Amended.**
- **Source.** The data come from `recon_get_hdobs`, because both tools that read the AOML SFMR archive failed with HTTP 403 in the feasibility step. `recon_get_sfmr` would in any case return only radius-binned SFMR statistics, without flight-level wind.
- **Rule.** The aircraft with the most HDOB records carrying an SFMR wind within 150 km of the best-track centre on 28 September 2022.
- **Labelling.** By call sign; no mission number is asserted.
- **QC flags.** Decoded from the NHC HDOB format document, which is cited. The number of records each flag removed is reported.
- **The two SFMR tools.** Recorded as not working, with the 403 evidence.

## A3. No river gauge (made before any value was seen)

usgs-mcp is not part of Part A. The feasibility step found only daily values for 2022. The gauge the brief's rule selected (02292900, Caloosahatchee River at S-79) is a regulated structure.

## A4. Buoy values from ww3-mcp (made before any value was seen)

**Change.**
- The wave heights come from `ww3_get_buoy_history` (ww3-mcp), which reads NDBC's 2022 annual file.
- ndbc-mcp supplies station metadata only (`ndbc_get_station`), because it cannot return data older than 45 days.
- The caption and the report name ww3-mcp as the source.

**Effect on the server count.** The figure draws on five servers: nhc-mcp, coops-mcp, recon-mcp, ww3-mcp and ndbc-mcp. ndbc-mcp contributes only the buoy position.

## A5. Figure layout and line breaks (2026-11-21 about 18:10 UTC, after the values were seen; no number changes)

Made after the recording, while drawing the figures. `DESIGN.md` §8 did not fix these details.

**Layout.**
- Panel (a) sits on the left at full height, with (b), (c) and (d) stacked on the right, instead of a 2 × 2 grid. The map spans 15° of latitude; in a 2 × 2 cell it would have been about 35 mm wide.
- The map extent is 89.5°W–79.0°W, 16°N–31°N. AF301's first record is at 30.4°N 88.9°W.
- The map items carry direct labels and a compact key in the empty south-west corner. A full legend covered best-track points: the legend check reported 6 points inside it.

**Line breaks.** In panel (b), the lines break at a missing or QC-removed value, and where consecutive records are more than 60 s apart. HDOB records are 30 s apart.

**Panel (d) legend.** Colour marks the station and line style marks observed or residual, so the legend fits within the panel width.

## A6. Panel (b) best-track line (2026-11-22, after the values were seen)

**Change.** The best-track reference was a step line taking, for each HDOB record, the best-track record nearest in time. It is now:
- markers at the 6-hourly best-track times inside the axis: 06:00 UTC 120 kt and 12:00 UTC 140 kt;
- joined by a thin line interpolated linearly in time;
- the line continues toward the 18:00 UTC value (135 kt) and is clipped at the axis edge.

The three values are returned by `nhc_get_best_track` (reused call 1). The legend reads "Best track, 1-min max wind (6-hourly, linear between)".

**Reason.** The step at 09:00 UTC was an artifact of nearest-record matching, not a feature of the best track.

**Files changed.**
- `results/panel_b.json` no longer carries the per-record nearest-record fields. It now holds the three bracketing 6-hourly records and the drawing rule.
- In `results/part_a_numbers.json`, the computed entry `best_track_vmax_levels_kt` is replaced by the three returned values.
- No other number changed.

## A7. Panel (a) coastline, markers and labels (2026-11-22, layout; adds one non-MCP input)

**Coastline.** Panel (a) of both figures now draws the Natural Earth 1:50m coastline (public domain).
- It is archived in `archive/non_mcp/natural_earth/` with its source URL and SHA-256 (`SOURCE.md`).
- It is extracted by `scripts/coastline.py` into `results/coastline_subset.json`.
- It is named in the key, the caption and the report.
- It is the package's only input that does not come from an MCP tool.

**Key and colorbar.** These moved from inside the map to below it, because the coastline now fills the map's south-west corner.

**Markers and labels.**
- The landfall star went from 8 to 5.5 pt and the tide-gauge triangles from 5 to 4.5 pt. The star and the Fort Myers triangle are 33 km apart, about 1.9 mm on the map; at the old sizes they overlapped.
- The Fort Myers and St. Petersburg labels moved further from their markers.
- New checks report that the star and the Fort Myers triangle do not overlap, and that no label overlaps a marker.

**Fallback page.** It is 125 mm tall instead of 110 mm, to hold the key below the map.

## A8. Panel labels and spacing (2026-11-22, layout)

**Labels.** "a"–"d" became "(a)"–"(d)", bold, 10 pt, top left.

**Spacing.**
- Panels (b), (c) and (d) are 24.5, 22.5 and 25 mm tall; they were 27, 24 and 27 mm.
- The legend of (d) now clears the axis and tick marks of (c). A new check found no legend touching another panel's axes, ticks included.

**Panel (b) legend.** It is a single column of three entries.

**Checks.** The figure checks also report:
- overlapping text pairs;
- the map-marker checks;
- legend overlap counting only points that lie inside the axes. Coastline vertices outside the map are clipped and never drawn.

## A9. Caption and report text (2026-11-22; no number change)

The caption and `REPORT.md` now say:
- **Buoy position.** It is the position `ndbc_get_station` returns today, not a 2022 position. The 86.1 km closest approach depends on it.
- **Peak flight-level wind.** AF301's 142 kt (30-s mean) is from one Air Force aircraft. The NHC report, p. 5, reads: “During the missions, the maximum 10-second averaged flight-level winds reported in the hurricane’s core were 160 kt from a NOAA aircraft at 750 mb (an altitude of about 6800 ft) at 1013 UTC 28 September.” The 160 kt is a 10-second average; AF301's 142 kt is a 30-second mean. The quotation was verified against the PDF on 2026-11-23 (A10).
- **Averaging periods.** The best-track wind is a 1-minute value, the SFMR wind a 10-second maximum and the flight-level wind a 30-second mean.

## A10. NHC report quotation verified (2026-11-23; text only)

**Source.** The author downloaded the NHC Tropical Cyclone Report for Ian (`https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf`, retrieved 2026-11-23 01:47:01 GMT).
- 7,049,210 bytes, 72 pages, revised 12 March 2026.
- SHA-256 `804d2a867917d4ab157e5b2b1e444d21d306379a08d07ffd7059d157a4b15fce`: the same file `verification/ian_cross_server` verified on 2026-11-06.

**Check.** `scripts/record_tcr_quote.py` checked three passages on p. 5 the way `ian_cross_server/record_references.py` does (pypdf 6.12.0; all whitespace removed; curly quotation marks read as straight):
- the author's quotation;
- "1013 UTC 28 September";
- the full sentence: “During the missions, the maximum 10-second averaged flight-level winds reported in the hurricane’s core were 160 kt from a NOAA aircraft at 750 mb (an altitude of about 6800 ft) at 1013 UTC 28 September.”

All three were found on p. 5. The record, with the PDF's SHA-256, is `archive/references/tcr_quote_check.json`. The PDF is not archived.

**Effect.** The "not checked against the report" wording in A9 and in `REPORT.md` is replaced by the verified quotation, with the note that the 160 kt is a 10-second average and AF301's 142 kt a 30-second mean.

## A11. AF301's 10-second peak flight-level wind added (2026-11-23; after the values were seen; descriptive only)

**What.** At the author's request, `scripts/analyze_part_a.py` now also reports AF301's highest `peak_fl_wind_kt` on 28 September. That field is the highest 10-second mean flight-level wind in each 30-second HDOB record, returned by `recon_get_hdobs` (R1). It is reported next to the NHC report's 160 kt.

**QC.** The same removal as for the 30-second flight-level wind: FF second digit 2, 4, 6 or 9, or an unrecognised code.

**Result.** 144 kt at 12:43:00 UTC. 907 values remain; QC removed 33. QC removal does not change the maximum.

**Not changed.** The number is not plotted, and no figure or figure input changed. It is added to `results/part_a_numbers.json` after every existing entry; no other result changed.
