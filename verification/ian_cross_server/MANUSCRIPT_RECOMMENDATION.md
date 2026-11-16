# Manuscript recommendation: Section 3.2

Every number below comes from `results.json` (see `REPORT.md`). The 328-word Section 3.2 that the improvement plan counts was not available to me. Both local `.docx` files still show 3.2 as "[TO DRAFT]". So this text replaces that section as a whole rather than editing it.

## Proposed text (221 words, counted as whitespace-separated tokens)

> **3.2 Cross-server example: Hurricane Ian (2022)**
>
> A scripted two-server MCP workflow combined Hurricane Ian's best track with tide-gauge records. One client process held two MCP stdio sessions, each to a separate server process installed from PyPI (nhc-mcp 0.1.1, coops-mcp 0.1.1). The tool sequence and arguments were fixed in a script; no language model was involved. The client called nhc_get_best_track for AL092022 and, for Fort Myers (8725520) and St. Petersburg (8726520), coops_get_station, coops_get_water_levels and coops_get_tide_predictions for 27–29 September 2022 (MLLW, metric, UTC, 6-min). Each station returned 720 verified observations and 720 predictions without gaps or flags, identical apart from retrieval time to responses saved in July 2026.
>
> The non-tidal residual, observed minus predicted, peaked at +2.209 m at Fort Myers (22:18 and again 22:30 UTC, 28 September) and reached −1.755 m at St. Petersburg at 23:00 UTC (Fig. 4). It contains all non-tidal signals, not storm surge alone. With the best track interpolated linearly in time between fixes, Fort Myers lay 39 km south of the storm centre at its first maximum, and St. Petersburg 112 km north-west of it at its minimum (Table S1). Landfall at Cayo Costa at 19:05 UTC is cited from the NHC Tropical Cyclone Report [Bucci et al., 2023]; the best-track response contains a 19:05 record but does not label it. The session record, checksums and an offline replay script are archived [ref].

## Contribution statement (one sentence)

> Two independently released Ocean-MCP servers were called from one MCP client in a single recorded session, and the combined result, the residual extremes and their position relative to the storm track, is recomputed offline from the archived responses.

## Figure and caption

- **Figure 4 (two-panel residual figure).** Keep it unchanged; no revised caption is needed for this work. The new information is five rows of geometry, which belong in a table: `geometry_table.md`, proposed as Table S1 in the supplement. A track map would add a coastline from a non-MCP source.
- **If the caption names a source for the landfall line,** it should be the TCR, not "HURDAT2 'L'". The MCP response carries no landfall identifier. Suggested clause: "Dashed line: landfall at Cayo Costa, 19:05 UTC 28 September 2022 (Bucci et al., 2023)."
- **The figure's own footer text** (drawn by `examples/ian_water_levels_residuals.py`) states the "1983-2001 National Tidal Datum Epoch". No MCP response in this run carries an epoch. Either verify that statement again or remove it from the figure.

## Reference entry

Bucci, L., Alaka, L., Hagen, A., Delgado, S., Beven, J., 2023. Tropical Cyclone Report: Hurricane Ian (AL092022), 23–30 September 2022. National Hurricane Center. Revised 12 March 2026. https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf

The online PDF is the 12 March 2026 revision. Its title page gives the original date as 2 April 2023. The values cited (19:05 UTC, Cayo Costa, 130 kt) are quoted from the revision (p. 4 and Table 1, p. 21). The 2023 original was not checked.

## Wording to keep

- Say "scripted two-server MCP workflow". Do not write "agent", "autonomous" or "the assistant decided".
- Say "non-tidal residual". Do not label the residual as storm surge alone.
- Use distances and bearings for timing and geometry only. Do not use them to explain residual size.
- Do not call the 19:05 best-track record a landfall record "in the tool response"; the response does not label it.
