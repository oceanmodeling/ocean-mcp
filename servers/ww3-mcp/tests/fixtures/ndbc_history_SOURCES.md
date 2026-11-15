# Sources of the NDBC historical-file fixtures

Each `ndbc_history_41009h<year>_excerpt.txt` is a verbatim excerpt: whole
lines copied byte for byte, including trailing spaces and the 1998 file's CRLF
line endings, from NDBC's historical standard meteorological file for buoy
41009. The source files came from

    https://www.ndbc.noaa.gov/view_text_file.php?filename=41009h<year>.txt.gz&dir=data/historical/stdmet/

| Fixture | Source file (as served, decompressed) | Bytes | SHA-256 of the source file | Retrieved (UTC) | Source lines kept |
|---|---|---:|---|---|---|
| `ndbc_history_41009h2024_excerpt.txt` | `41009h2024.txt` | 4,742,458 | `f149d373877f4892f75092a969a0b12c27da7c8d54e0db9827a8fbcaef0bc648` | 2026-11-06T05:11:00Z; identical on 2026-11-09T01:25:12Z | 1-4, 71, 181, 242, 697, 808, 1569, 2067, 5154, 40758, 40759, 40795, 52692-52694 |
| `ndbc_history_41009h1998_excerpt.txt` | `41009h1998.txt` | 1,391,742 | `1e371260fbc3646576211a38cdb24067efed6412c7500e6bc84d2aea8ef8d437` | 2026-11-09T01:29:06Z | 1-3, 8, 1606, 1684 |
| `ndbc_history_41009h2003_excerpt.txt` | `41009h2003.txt` | 708,296 | `86766b864196cb533c8a22d48744fdc3599609453d5e151cfe99cdcdaf1a8da0` | 2026-11-09T01:29:09Z | 1-2, 269 |
| `ndbc_history_41009h2006_excerpt.txt` | `41009h2006.txt` | 1,555,809 | `c03309c84b505fa311d82338c8f8dbabd673b81a56656c02ce074f030f642e26` | 2026-11-09T01:29:13Z | 1-2, 693 |

What the 2024 lines exercise:

- **Every missing-value code.** Line 2067 has WDIR 999, WSPD/GST 99.0, WVHT/DPD/APD 99.00, MWD 999, PRES 9999.0, ATMP/DEWP 999.0, VIS 99.0, TIDE 99.00. Line 71 has WTMP 999.0.
- **Genuine values next to a code**, which must be kept:
  - PRES 999.9 hPa (line 5154) and 999.0 hPa (lines 40758-40759, Hurricane Milton);
  - WDIR 99 and 9 degT (697, 1569) and MWD 99 degT (808);
  - WSPD 9.9 m/s (181) and DEWP 9.0 degC (242);
  - DPD 9.09 s (697, 40795).
- **The annual WVHT maximum**, 6.32 m at 2024-10-10 08:10 (line 40795), the only row with that value in the whole file.
- **The last three rows of the year** (lines 52692-52694), for the record cap that keeps the most recent rows.

The older excerpts cover the header variants:

- **1998:** one header line, two-digit `YY`, `WD`/`BAR`, no minute column, two rows per hour, CRLF line endings.
- **2003:** `YYYY`, no minute column.
- **2006:** `YYYY` with a minute column.

The missing-value rule is documented at https://www.ndbc.noaa.gov/faq/measdes.shtml (see `NDBC_HISTORICAL_MISSING_CODES` in `src/ww3_mcp/models.py`).
