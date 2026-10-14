# NOAA HRD tropical cyclone reconnaissance data access guide

**Every major NOAA reconnaissance data product — SFMR, flight-level, dropsonde, and Vortex Data Messages — is accessible via HTTP file-based access with predictable URL patterns, but no REST API exists for any of them.** The primary archives live on two servers: AOML's HRD FTP-over-HTTP server (`www.aoml.noaa.gov/ftp/hrd/data/`) for post-processed science data, and NHC's reconnaissance archive (`www.nhc.noaa.gov/archive/recon/`) for real-time operational bulletins. Building an MCP server requires parsing Apache-style HTML directory listings and constructing URLs from known patterns. The only machine-readable structured dataset with a proper API is the SHIPS developmental data on AOML's ERDDAP server. Everything else demands URL construction, HTTP GET, and file parsing.

---

## The two-server architecture and how data flows

Reconnaissance data follows a clear pipeline: aircraft instruments → satellite uplink → NWS/GTS dissemination → NHC archive (within **15–30 minutes**) → HRD post-processing → AOML archive (weeks to months later). This creates two distinct access points with different tradeoffs.

**NHC Reconnaissance Archive** serves raw operational bulletins in real-time:
- **Base URL**: `https://www.nhc.noaa.gov/archive/recon/`
- **Coverage**: 1989–present, continuous yearly directories
- **Organization**: `/{YYYY}/{PRODUCT_TYPE}/{AGENCY}/{WMO_HEADER}/`
- **Format**: Plain ASCII WMO text bulletins
- **Latency**: 0–5 minutes for HDOB; ~30 minutes for VDMs
- **Readme**: `https://www.nhc.noaa.gov/archive/recon/readme.txt`

**AOML HRD FTP Archive** serves post-processed, quality-controlled science data:
- **Base URL**: `https://www.aoml.noaa.gov/ftp/hrd/data/`
- **Coverage**: 1976–present (varies by product)
- **Organization**: `/{product}/{YYYY}/{stormname}/` (modern) or `/{product}/{STORMNAMEYY}/` (historical)
- **Formats**: NetCDF, ASCII text, gzipped tar archives
- **Latency**: Weeks to months after flight (QC processing)

HRD classifies data into three types: **Type 1** (freely available online), **Type 2** (QC'd, available online or upon request), and **Type 3** (derived products, upon request). The field program data pages follow the pattern `https://www.aoml.noaa.gov/{YYYY}-hurricane-field-program-data/` for years 2020 onward.

---

## SFMR data: surface winds and rain rate from the archive

SFMR data exists in two forms: standalone SFMR files (pre-2007 storms) and embedded within flight-level NetCDF files (2007 onward). Since 2007, **SFMR surface wind speed and rain rate are included as variables in the standard 1-second flight-level data files** from both NOAA and USAF aircraft.

**Standalone SFMR archive**:
- **Landing page**: `https://www.aoml.noaa.gov/hrd/data_sub/sfmr.html`
- **Format specification**: `https://www.aoml.noaa.gov/hrd/format/sfmr.html`
- **FTP base**: `https://www.aoml.noaa.gov/ftp/hrd/data/sfmr/{YEAR}/{stormname}/`
- **File naming**: `AFRC_SFMR{YYYYMMDD}{AircraftSeq}.nc`

**Storm pages** (legacy per-storm access, mainly pre-2019):
- **Pattern**: `https://www.aoml.noaa.gov/hrd/Storm_pages/{stormname}{YYYY}/sfmr.html`
- **Examples**: `https://www.aoml.noaa.gov/hrd/Storm_pages/dorian2019/sfmr.html`, `https://www.aoml.noaa.gov/hrd/Storm_pages/michael2018/sfmr.html`

**Aircraft codes in filenames**: `U` = USAF WC-130J, `H` = NOAA N42RF (P-3), `I` = NOAA N43RF (P-3), `N` = NOAA N49RF (G-IV). The sequence number (U1, U2, H1) indicates the mission number for that aircraft on that date.

Three format versions exist for standalone SFMR files:

| Version | Format | Columns | Key addition |
|---------|--------|---------|-------------|
| V1 (ASCII) | Gzipped text | 11 columns, 1 Hz | Date, time, lon, lat, alt, pressure, radial distance, azimuth, surface wind speed, FL wind speed, FL wind direction |
| V2 (ASCII) | Gzipped text | 12 columns, 1 Hz | Adds rain rate (mm/hr) |
| V3 (NetCDF) | `.nc` | All above + raw brightness temperatures | Current standard; includes per-channel SFMR Tb |

**Example URLs for specific storms**:
- Milton 2024 SFMR: `https://www.aoml.noaa.gov/ftp/hrd/data/sfmr/2024/milton/`
- Ian 2022 SFMR: `https://www.aoml.noaa.gov/ftp/hrd/data/sfmr/2022/ian/`
- Individual file: `https://www.aoml.noaa.gov/ftp/hrd/data/sfmr/2020/marco/AFRC_SFMR20200820U2.nc`

**Real-time SFMR data** is available through HDOB messages at NHC (see Real-time section below), where the 30-second averaged SFMR surface wind and rain rate are encoded in each HDOB record. Post-processed SFMR data on AOML appears weeks to months later.

---

## Flight-level reconnaissance data spans two archival eras

The flight-level archive at `https://www.aoml.noaa.gov/ftp/hrd/data/flightlevel/` contains two fundamentally different data organizations split around 2005.

**Modern era (2005–present)**: Raw 1-second data organized by year and storm name.
- **URL pattern**: `https://www.aoml.noaa.gov/ftp/hrd/data/flightlevel/{YYYY}/{stormname}/`
- **Data files**: `{YYYYMMDD}{AircraftCode}{MissionNum}.{SegmentNum}.txt` (ASCII ARWO export)
- **Summaries**: `{YYYYMMDD}{AircraftCode}{MissionNum}.SUM.txt`
- **Storm fixes**: `{stormname}.fixs` (wind center fixes), `{stormname}.trak` (track)
- **Manifests**: `{YYYYMMDD}{AircraftCode}{MissionNum}_Manifest.pdf`

The 1-second ARWO ASCII files contain **~40 variables** per record:

| Variable | Description |
|----------|-------------|
| `LAT`, `LON` | GPS latitude/longitude |
| `WSpd`, `WDir` | Flight-level wind speed (kt) and direction (°) |
| `TA` | Air temperature (°C) |
| `DPR` | Dewpoint temperature (°C) |
| `PA`, `GPSA`, `RA`, `GA` | Pressure, GPS, radar, geopotential altitudes |
| `DVAL` | D-value (departure from standard atmosphere, m) |
| `ISP`, `SLP` | In-situ static pressure, sea-level pressure |
| `TAS`, `GS` | True airspeed, ground speed |
| `THD`, `TRK` | True heading, track |
| `PITCH`, `ROLL`, `AOA` | Aircraft attitude |
| `VE`, `VN`, `VV` | East, north, vertical velocity components |
| `SWS` | SFMR surface wind speed (post-2007) |
| `RR` | SFMR rain rate (mm/hr, post-2007) |

**Historical era (1976–2002)**: Quality-controlled radial pass data organized by storm.
- **URL pattern**: `https://www.aoml.noaa.gov/ftp/hrd/data/flightlevel/{STORMNAME}{YY}/`
- **Examples**: `ALLEN80/`, `HUGO89/`, `ANDREW92/`
- **Pass files**: `{STORM}{YY}_{MissionNum}_{PassNum}-APF.TXT` (10 columns: time, pressure, lat, lon, radar alt, radial wind, tangential wind, vertical wind, temperature, wind speed/D-value)
- **Index files**: `{STORM}{YY}_{M}-IDX.TXT`, `{STORM}{YY}_{M}-NDX.TXT`
- **FORTRAN reader**: `https://www.aoml.noaa.gov/ftp/hrd/FLIGHTLEVEL/code/goodstuff.for.txt`

Additionally, NCEI maintains a formal archive as **Dataset DSI-6420**: `https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00581`. Format documentation pages are at `https://www.aoml.noaa.gov/hrd/data_sub/data_format.html`, `https://www.aoml.noaa.gov/hrd/format/slow.html` (AOC standard tape), and `https://www.aoml.noaa.gov/hrd/format/usaf.html` (USAF format).

---

## Dropsonde data has three access tiers

**Tier 1 — AOML/HRD operational archive (1996–present)**:
- **Base URL**: `https://www.aoml.noaa.gov/ftp/pub/hrd/data/dropsonde/`
- **Directory pattern**: `HURR{YY}/` (e.g., `HURR24/` for 2024 season)
- **Subdirectories per season**: `transmit/` (TEMP-DROP .xmt files), `operproc/` (operationally processed), `raw/` (.avp.tar.gz AVAPS files), `skewt/` (diagrams), `synmap/` (station maps)
- **File naming**: `{YYYYMMDD}{AircraftLetter}{Seq}` with extensions `.xmt`, `.hsa`, `.frd`, `.avp.tar.gz`
- **NetCDF bundles**: `https://www.aoml.noaa.gov/ftp/pub/hrd/data/dropsonde/HURR{YY}/operproc/{FlightID}_NETCDF.tar.gz`
- **Format docs**: `https://www.aoml.noaa.gov/hrd/format/tempdrop_format.html` (TEMP-DROP), `https://www.aoml.noaa.gov/hrd/format/hsa_format.html` (HSA)

**Tier 2 — NHC recon archive raw TEMP-DROP messages (1989–present)**:
- **Atlantic**: `https://www.nhc.noaa.gov/archive/recon/{YYYY}/REPNT3/`
- **Pacific**: `https://www.nhc.noaa.gov/archive/recon/{YYYY}/REPPP3/`
- **Format**: Raw WMO TEMP-DROP code (mandatory + significant levels only)
- **Resolution**: Limited to standard pressure levels (SFC, 1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100 mb) plus significant levels

**Tier 3 — NCAR/EOL QC'd long-term archive (1996–2012)**:
- **Dataset page**: `https://data.eol.ucar.edu/dataset/542.001`
- **DOI**: `https://doi.org/10.5065/D6XG9PJ0`
- **Format**: EOL columnar ASCII sounding format, consistently QC'd
- **Version 2.0** adds vertical air velocity, radius, and azimuth angle
- **Inventory spreadsheet**: `https://data.eol.ucar.edu/file/download/52DED533220FC/AllSoundings.lonlatalt.NOAA.1996-2012.v2.xlsx`
- **Access method**: Order-based system (not direct download)
- **Processing software**: Raw AVAPS data can be reprocessed using NCAR's ASPEN: `https://www.eol.ucar.edu/software/aspen`

Variables across all dropsonde formats include **pressure (hPa), temperature (°C), dewpoint (°C), relative humidity (%), wind speed (m/s or kt), wind direction (°), geopotential height (m), GPS lat/lon, and UTC time**.

---

## Vortex Data Messages: raw text and the VDM+ NetCDF goldmine

VDMs are the most operationally critical product — each one contains a center fix with the storm's position, intensity, and structure.

**Raw VDM archive at NHC (1989–present)**:
- **Atlantic**: `https://www.nhc.noaa.gov/archive/recon/{YYYY}/REPNT2/`
- **Pacific**: `https://www.nhc.noaa.gov/archive/recon/{YYYY}/REPPN2/`
- **WMO header**: `URNT12 KNHC` (Atlantic DOD), `URPN12 KNHC` (Pacific)
- **Live current VDM**: `https://www.nhc.noaa.gov/text/MIAREPNT2.shtml`
- **Format**: Plain text requiring custom parsing; major format overhaul in 2018 changed field assignments

Key VDM fields (post-2018 format, items A-U): **A** = fix day/time (`DD/HH:MM:SSZ`; year and month come from the bulletin time), **B** = center in decimal degrees, **C** = standard level and its minimum height, **D** = minimum SLP (may read `EXTRAP 923 mb`), **E** = dropsonde surface wind at the center, **F** = eye character, **G** = eye shape/diameter (`C8`, `CO15-30`, `E04/33/23`), **H**/**L** = estimated max surface wind inbound/outbound, **J**/**N** = max flight-level wind inbound/outbound (direction and speed), **P**/**Q** = max flight-level temperature outside/inside the eye, **S** = fix method / fix level, **U** = mission and OB number; free-text remarks follow U. Pre-2018 VDMs (items A-P, archive 2006-2017) give the center in degrees and minutes with the longitude on the next line, inbound winds in **D**/**F**, SLP in **H**, eye in **L**/**M**, and the mission in **P**.

**VDM+ structured NetCDF dataset (1989–2022)** — this is the key machine-readable resource:
- **Landing page**: `https://verif.rap.ucar.edu/tcdata/vortex/`
- **Download**: `https://verif.rap.ucar.edu/tcdata/vortex/dataset/`
- **DOI**: `https://doi.org/10.5065/D61Z42GH`
- **Format**: Single NetCDF file (~592 MB) containing **~355 parsed parameters** from every VDM, cross-referenced with HURDAT2 best track, Extended Best Track, and SHIPS environmental data
- **Version 2.0.0**: Atlantic, East Pacific, and Central Pacific TCs through 2022
- **Browse interface**: `https://hurricanes.ral.ucar.edu/structure/vortex/`

---

## Real-time data flow and the HDOB message as the primary feed

During active storms, the **HDOB (High Density Observation) bulletin is the real-time reconnaissance data workhorse**. It contains 30-second averaged observations including flight-level winds, SFMR surface winds, and rain rate — essentially a near-real-time stream of everything an MCP server would need.

**HDOB archive location**:
- **Atlantic (NOAA)**: `https://www.nhc.noaa.gov/archive/recon/{YYYY}/HDOB/NOAA/URNT15/`  
- **Atlantic (USAF)**: `https://www.nhc.noaa.gov/archive/recon/{YYYY}/HDOB/USAF/URNT15/`
- **File naming**: `URNT15-KNHC.{YYYYMMDDHHmm}.txt`
- **Format spec**: `https://www.nhc.noaa.gov/abouthdobs_2007.shtml` and PDF at `https://www.nhc.noaa.gov/pdf/HDOB-specification.pdf`

Each HDOB data line has 13 fields per 30-second observation (`hhmmss LLLLH NNNNNW PPPP GGGGG XXXX sTTT sddd wwwSSS MMM KKK ppp FF`); the date is not on the line but in the mission line (`... HDOB NN YYYYMMDD`, the date of the first data line):

- Time (UTC), latitude and longitude (degrees and minutes), static pressure (tenths mb, leading 1 dropped at 1000 mb and up), geopotential height (m), extrapolated surface pressure (same encoding) or, above 550 mb, the D-value in m (negative values appear as both D + 5000 and 5000 + |D|), temperature and dewpoint (tenths °C), flight-level wind direction and speed as one field (°, kt), peak 10-second FL wind (kt), **peak 10-second SFMR surface wind (kt)**, **SFMR rain rate (mm/h)**, and two QC flags. Missing values are slashes or 999.

**Latency by product type**:
- HDOB: **0–5 minutes** (automatic satellite uplink)
- Dropsonde TEMP-DROP: **0–5 minutes** (automatic)  
- Vortex Data Messages: **~30 minutes** (requires crew analysis + CARCAH QC)
- NHC archive posting: **15–30 minutes** from measurement

**No streaming/WebSocket API exists.** All real-time access is HTTP polling. Recommended polling interval is **10 minutes** (matching Tropical Tidbits' approach). The ATCF f-deck at `https://ftp.nhc.noaa.gov/atcf/fix/` provides structured aircraft fix data during active storms with the pattern `f{basin}{num}{year}.dat`.

---

## ATCF f-decks, best tracks, and complementary structured data

The **ATCF (Automated Tropical Cyclone Forecast System)** at `https://ftp.nhc.noaa.gov/atcf/` provides the most machine-friendly structured data for reconnaissance fixes:

- **F-decks** (aircraft/satellite fixes): `https://ftp.nhc.noaa.gov/atcf/fix/f{basin}{num}{year}.dat`
- **B-decks** (best track): `https://ftp.nhc.noaa.gov/atcf/btk/b{basin}{num}{year}.dat`
- **A-decks** (model guidance): `https://ftp.nhc.noaa.gov/atcf/aid_public/a{basin}{num}{year}.dat.gz`
- **Archive**: `https://ftp.nhc.noaa.gov/atcf/archive/`
- **Storm table**: `https://ftp.nhc.noaa.gov/atcf/archive/storm.table`
- **Format spec**: `https://www.nrlmry.navy.mil/atcf_web/docs/database/new/database.html`

**HURDAT2** (post-season best track, 1851–2024): `https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2024-040425.txt`. Format spec: `https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-atlantic.pdf`. HURDAT2 is **derived from** reconnaissance data but does not contain raw observations.

**IBTrACS** (global best track in NetCDF/CSV): `https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/netcdf/` — includes an `active` subset updated within 7 days.

**ERDDAP endpoints** (the only true REST APIs in this ecosystem):
- SHIPS Atlantic 7-day: `https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/ships_atlantic_7days.csv?{query}`
- SHIPS Atlantic 5-day: `https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/ships_atlantic_5days.csv?{query}`
- TCHP gridded: `https://erddap.aoml.noaa.gov/hdb/erddap/griddap/TCHP.nc?{query}`
- Extended Best Track NetCDF: `https://rammb.cira.colostate.edu/research/tropical_cyclones/tc_extended_best_track_dataset/`

---

## Existing Python libraries and programmatic tools

Two Python libraries already parse these data sources and demonstrate viable access patterns:

**`tropycal`** (`https://tropycal.github.io/tropycal/`) reads directly from NHC's archive:
```python
from tropycal import tracks
basin = tracks.TrackDataset()
storm = basin.get_storm(('milton', 2024))
storm.recon.get_vdms()       # Parses NHC raw VDMs
storm.recon.get_dropsondes() # Parses dropsondes (2006+)
storm.recon.get_hdobs()      # Parses HDOBs (1989+)
```

**`atcf-data-parser`** (`https://palewi.re/docs/atcf-data-parser/`) parses ATCF a/b/f-deck files into pandas DataFrames. These libraries validate that the NHC archive URL patterns are stable and machine-parseable.

---

## Comprehensive URL reference for MCP server implementation

| Data Product | Base URL | File Pattern | Format |
|-------------|----------|-------------|--------|
| SFMR (standalone) | `https://www.aoml.noaa.gov/ftp/hrd/data/sfmr/{YYYY}/{storm}/` | `AFRC_SFMR{YYYYMMDD}{AC}.nc` | NetCDF |
| Flight-level (modern) | `https://www.aoml.noaa.gov/ftp/hrd/data/flightlevel/{YYYY}/{storm}/` | `{YYYYMMDD}{AC}.{SS}.txt` | ASCII |
| Flight-level (historical) | `https://www.aoml.noaa.gov/ftp/hrd/data/flightlevel/{STORM}{YY}/` | `{STORM}{YY}_{M}_{P}-APF.TXT` | ASCII |
| Dropsonde (HRD) | `https://www.aoml.noaa.gov/ftp/pub/hrd/data/dropsonde/HURR{YY}/` | Various by subdir | Mixed |
| HDOB (real-time) | `https://www.nhc.noaa.gov/archive/recon/{YYYY}/HDOB/` | `URNT15-K*.{timestamp}.txt` | ASCII |
| VDM (real-time) | `https://www.nhc.noaa.gov/archive/recon/{YYYY}/REPNT2/` | Text bulletins | ASCII |
| Dropsonde TEMP-DROP | `https://www.nhc.noaa.gov/archive/recon/{YYYY}/REPNT3/` | Text bulletins | ASCII |
| ATCF fixes | `https://ftp.nhc.noaa.gov/atcf/fix/` | `f{basin}{num}{year}.dat` | CSV-like |
| ATCF best track | `https://ftp.nhc.noaa.gov/atcf/btk/` | `b{basin}{num}{year}.dat` | CSV-like |
| VDM+ (structured) | `https://verif.rap.ucar.edu/tcdata/vortex/dataset/` | Single NetCDF | NetCDF |
| HURDAT2 | `https://www.nhc.noaa.gov/data/hurdat/` | `hurdat2-*.txt` | CSV-like |
| IBTrACS | `https://www.ncei.noaa.gov/data/.../v04r01/access/` | `IBTrACS.*.nc` | NetCDF/CSV |
| Radar (Level 3) | `https://www.aoml.noaa.gov/ftp/pub/hrd/data/radar/level3` | NetCDF archives | NetCDF |
| Field program index | `https://www.aoml.noaa.gov/{YYYY}-hurricane-field-program-data/` | HTML page | HTML |
| Storm page (legacy) | `https://www.aoml.noaa.gov/hrd/Storm_pages/{storm}{YYYY}/` | HTML page | HTML |

## Conclusion

The NOAA reconnaissance data landscape is **file-centric with no REST APIs for core products**. An MCP server must implement three access strategies: (1) poll and parse NHC's `archive/recon/` directory for real-time HDOB, VDM, and dropsonde bulletins during active storms; (2) construct URLs against AOML's `ftp/hrd/data/` hierarchy for post-processed SFMR, flight-level, and dropsonde NetCDF/ASCII files; and (3) leverage ATCF f-decks as the most structured machine-readable source for aircraft position fixes. The VDM+ NetCDF from NCAR eliminates the need to parse raw VDM text for historical analysis. The HDOB format — documented at `nhc.noaa.gov/abouthdobs_2007.shtml` — is the single most valuable real-time feed, delivering SFMR surface winds, flight-level data, and position at 30-second intervals with under 5 minutes of latency. The `tropycal` Python library's source code provides a proven reference implementation for parsing all NHC archive formats.