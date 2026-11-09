# Changelog: usgs-mcp

## 0.1.2 (unreleased)

Changes since 0.1.1 (`usgs-mcp-v0.1.1`, commit `5e45c62`). Two tools change: `usgs_get_hydrograph` and `usgs_get_flood_status`. Their JSON responses keep every 0.1.1 key, and some values that were wrong numbers are now `null`; see "Output schema" below.

### Scientific corrections

- **The USGS no-data value is no longer treated as a measurement.**
  - **How USGS marks missing data.** In the legacy Water Services JSON (WaterML 1.1), each time series declares its missing-data marker in `variable.noDataValue`, which is `-999999.0`. A reading with that value carries a qualifier saying why, e.g. `Ice` ("Value is affected by ice at the measurement site."), `Eqp` or `Ssn`. USGS's migration guide maps the field the same way (https://api.waterdata.usgs.gov/docs/ogcapi/migration/): "noDataValue: No longer provided. Missing data is now represented with null values."
  - **What 0.1.1 did with it.** It read these readings as flows.
  - **Example.** For site 15290000 (Little Susitna R near Palmer, AK) on 2026-11-09, 217 of 2,863 readings over 30 days were `-999999` with `Ice`. Over its 2,646 valid readings the mean is 137.6 cfs and the minimum 98.5 cfs. `usgs_get_hydrograph` reported:
    - `current_cfs` −999999.0;
    - `min_cfs` −999999.0;
    - `mean_cfs` −75,667.4;
    - `pct_of_median` −1,538,560.
  - **The same site in `usgs_get_flood_status`.** It reported `current_flow_cfs` −999999.0, `pct_of_median` −1,538,460 and `pct_of_peak` −12,755.1.
  - **The fix.** Readings equal to the series' `noDataValue`, non-numeric readings and non-finite readings are now excluded from every statistic and counted by reason, with the qualifiers of the excluded readings. They are never replaced by a number.

### Changed behaviour

- **`usgs_get_hydrograph`.** min, max, mean, trend and `num_readings` use valid readings only.
  - If the latest reading is not a measurement, `current_cfs` is `null`, with a `current_note`, plus `last_valid_cfs` and `last_valid_time`, and `pct_of_median` is `null`.
  - Markdown states "N valid of M" and what was excluded, and shows "no data" for Current.
- **`usgs_get_flood_status`.** If the latest reading is not a measurement, `current_flow_cfs` and every flow ratio (`pct_of_median`, `pct_of_peak`, `flow_vs_median_ratio`) are `null`, with a `current_flow_note`.
  - At a site that is not an NWS forecast point, the status is then "Unknown". 0.1.1 derived a flow-anomaly label from −999999, e.g. "Below Normal".
  - The NWS stage-based status is unchanged.
  - A non-numeric latest reading with valid readings before it no longer returns an error. It is reported like a no-data reading.

### Output schema (JSON)

- **`usgs_get_hydrograph`.**
  - Added: `readings_total`, `excluded_readings` (`no_data_value`, `non_numeric`, `non_finite`), `no_data_value`; `excluded_qualifiers` when any; `current_note`, `last_valid_cfs`, `last_valid_time` when the latest reading is excluded.
  - Changed: `current_cfs` and `pct_of_median` can be `null`. `num_readings` now counts valid readings only.
- **`usgs_get_flood_status`.**
  - Added, when the latest reading is excluded: `current_flow_note` and `readings_excluded_last_24h`.
  - Changed: `current_flow_cfs`, `pct_of_median` and `pct_of_peak` can be `null`.

### Python API

- New in `models.py`: `screen_series_values(ts) -> (valid, info)` and `describe_exclusions(info)`.

### Known limitations

- `usgs_get_instantaneous_values` and `usgs_get_daily_values` compute no statistics and are unchanged. They still list `-999999` readings as returned by USGS, with their qualifiers, and the IV markdown "Current" line can show `-999999`.
- Readings whose qualifier marks them as estimated, provisional or otherwise flagged, but which carry a real number, are kept.
