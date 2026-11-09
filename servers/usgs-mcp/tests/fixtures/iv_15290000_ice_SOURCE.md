# Source of `iv_15290000_ice_excerpt.json`

A structural excerpt of a real USGS Water Services instantaneous-values response for site 15290000 (Little Susitna River near Palmer, AK), discharge (00060):

    https://waterservices.usgs.gov/nwis/iv/?format=json&sites=15290000&parameterCd=00060&period=P30D

| | |
|---|---|
| Retrieved | 2026-11-09T02:40:18Z |
| Bytes | 227,999 |
| SHA-256 of the response | `63f56e689b7b55c4165f28e13417e246a67a83ca9e1adedba4998c6c3c346556` |

**What was kept.** Every field of the response is unchanged, including `variable.noDataValue` = `-999999.0` and the in-band qualifier definitions ("Ice": "Value is affected by ice at the measurement site."). Only the `values[0].value` list is cut to 14 of its 2,863 readings, copied verbatim:

| Source indices | Readings | What they are |
|---|---|---|
| 0-3 | 2026-10-09 17:45 to 18:30 AKDT | the first readings (140, 138, 138, 140 cfs, `P`) |
| 2642-2645 | 2026-11-06 10:15 to 11:00 AKST | the last valid readings before freeze-up (99.9, 99.9, 99.9, 98.5 cfs, `P`) |
| 2646-2649 | from 2026-11-06 11:15 AKST | the first four `-999999`, qualifiers `P,Ice` |
| 2861-2862 | 2026-11-08 17:00 and 17:15 AKST | the last two readings, `-999999`, `P,Ice` |

In the full response, 217 readings (all from 2026-11-06 11:15 onward) equal `noDataValue`, and every one carries `Ice`.
