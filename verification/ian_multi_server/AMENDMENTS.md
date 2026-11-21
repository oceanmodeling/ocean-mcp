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
