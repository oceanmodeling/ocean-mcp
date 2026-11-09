"""Model registry, enums, and constants for WW3 MCP server."""

from __future__ import annotations

from enum import Enum


class WaveGrid(str, Enum):
    """GFS-Wave output grids."""

    GLOBAL_0P16 = "global.0p16"
    GLOBAL_0P25 = "global.0p25"
    ATLOCN_0P16 = "atlocn.0p16"
    WCOAST_0P16 = "wcoast.0p16"
    EPACIF_0P16 = "epacif.0p16"
    ARCTIC_9KM = "arctic.9km"


class WaveVariable(str, Enum):
    """GFS-Wave GRIB2 variable short names."""

    HTSGW = "HTSGW"  # Significant height of combined wind waves and swell
    PERPW = "PERPW"  # Primary wave mean period
    DIRPW = "DIRPW"  # Primary wave direction
    WVHGT = "WVHGT"  # Significant height of wind waves
    WVPER = "WVPER"  # Mean period of wind waves
    WVDIR = "WVDIR"  # Direction of wind waves
    SWELL = "SWELL"  # Significant height of swell waves
    SWPER = "SWPER"  # Mean period of swell waves
    SWDIR = "SWDIR"  # Direction of swell waves
    WIND = "WIND"  # Wind speed at surface
    WDIR = "WDIR"  # Wind direction at surface


# NOMADS grib filter variable name mapping (GRIB2 shortName → filter parameter)
GRIB_VAR_FILTER = {
    "HTSGW": "var_HTSGW",
    "PERPW": "var_PERPW",
    "DIRPW": "var_DIRPW",
    "WVHGT": "var_WVHGT",
    "WVPER": "var_WVPER",
    "WVDIR": "var_WVDIR",
    "SWELL": "var_SWELL",
    "SWPER": "var_SWPER",
    "SWDIR": "var_SWDIR",
    "WIND": "var_WIND",
    "WDIR": "var_WDIR",
}

# Variable descriptions for display
VARIABLE_INFO: dict[str, dict[str, str]] = {
    "HTSGW": {"name": "Significant Wave Height (combined)", "units": "m"},
    "PERPW": {"name": "Primary Wave Mean Period", "units": "s"},
    "DIRPW": {"name": "Primary Wave Direction", "units": "deg"},
    "WVHGT": {"name": "Wind Wave Height", "units": "m"},
    "WVPER": {"name": "Wind Wave Period", "units": "s"},
    "WVDIR": {"name": "Wind Wave Direction", "units": "deg"},
    "SWELL": {"name": "Swell Height", "units": "m"},
    "SWPER": {"name": "Swell Period", "units": "s"},
    "SWDIR": {"name": "Swell Direction", "units": "deg"},
    "WIND": {"name": "Wind Speed (10m)", "units": "m/s"},
    "WDIR": {"name": "Wind Direction (10m)", "units": "deg"},
}


# NOMADS Grib Filter base URL
NOMADS_GRIB_FILTER_BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl"

# AWS S3 GFS bucket (for cycle availability checks)
GFS_S3_BASE = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"

# NDBC base URLs
NDBC_REALTIME_BASE = "https://www.ndbc.noaa.gov/data/realtime2"
NDBC_STATIONS_URL = "https://www.ndbc.noaa.gov/activestations.xml"
NDBC_HISTORY_BASE = "https://www.ndbc.noaa.gov/view_text_file.php"

# NDBC standard meteorological column names (realtime2 .txt format)
NDBC_COLUMNS = [
    "YY",
    "MM",
    "DD",
    "hh",
    "mm",
    "WDIR",
    "WSPD",
    "GST",
    "WVHT",
    "DPD",
    "APD",
    "MWD",
    "PRES",
    "ATMP",
    "WTMP",
    "DEWP",
    "VIS",
    "PTDY",
    "TIDE",
]

# Wave-relevant NDBC columns for our tools
NDBC_WAVE_COLUMNS = ["WVHT", "DPD", "APD", "MWD", "WDIR", "WSPD"]

# NDBC historical (annual) standard meteorological files mark missing values
# differently from realtime2 files. NDBC, "Measurement Descriptions and Units",
# https://www.ndbc.noaa.gov/faq/measdes.shtml (retrieved 2026-11-09):
#   "Missing data in the Realtime files are denoted by "MM" while a variable
#   number of 9's are used to denote missing data in the Historical files,
#   depending on the data type (for example: 999.0 99.0)."
# The page gives examples, not a per-column list. Each column's code below is
# the all-9 value in that column's field format, as it appears in NDBC's own
# files (checked column by column in the 41009 files for 1998, 2003, 2006 and
# 2024). The field text is compared exactly, so genuine values that merely
# look similar are kept: PRES 999.0 hPa, MWD 99 degT, DPD 9.09 s, WSPD 9.9 m/s.
NDBC_HISTORICAL_MISSING_CODES: dict[str, str] = {
    "WDIR": "999",
    "WSPD": "99.0",
    "GST": "99.0",
    "WVHT": "99.00",
    "DPD": "99.00",
    "APD": "99.00",
    "MWD": "999",
    "PRES": "9999.0",
    "ATMP": "999.0",
    "WTMP": "999.0",
    "DEWP": "999.0",
    "VIS": "99.0",
    "TIDE": "99.00",
}

# Older historical files use other column headings. The same NDBC page lists
# them ("Discontinued Measurement Abbreviations"; PRES is "labeled BAR in
# Historical files"). Older files also head the year column YYYY (seen in the
# 2003 and 2006 files) or write a two-digit year under YY (the 1998 file).
NDBC_HISTORICAL_RENAMES: dict[str, str] = {
    "YYYY": "YY",
    "WD": "WDIR",
    "DIR": "WDIR",
    "SPD": "WSPD",
    "GSP": "GST",
    "BAR": "PRES",
    "BARO": "PRES",
    "H0": "WVHT",
    "DOMPD": "DPD",
    "AVP": "APD",
}

# Units as written in the units line of current historical files (e.g. 2024).
# Used only when a file has no units line (the 1998, 2003 and 2006 files have
# none).
NDBC_STDMET_UNITS: dict[str, str] = {
    "WDIR": "degT",
    "WSPD": "m/s",
    "GST": "m/s",
    "WVHT": "m",
    "DPD": "sec",
    "APD": "sec",
    "MWD": "degT",
    "PRES": "hPa",
    "ATMP": "degC",
    "WTMP": "degC",
    "DEWP": "degC",
    "VIS": "mi",
    "TIDE": "ft",
}

# GFS-Wave grid registry
WAVE_GRIDS: dict[str, dict] = {
    "global.0p16": {
        "name": "Global 0.16-degree",
        "short_name": "Global Hi-Res",
        "resolution": "0.16° (~18 km)",
        "domain_desc": "Global ocean coverage",
        "domain": {
            "lat_min": -90.0,
            "lat_max": 90.0,
            "lon_min": 0.0,
            "lon_max": 359.84,
        },
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 384,
        "file_template": "gfswave.t{cycle}z.global.0p16.f{fhour:03d}.grib2",
        "dir_template": "gfs.{date}/{cycle}/wave/gridded",
    },
    "global.0p25": {
        "name": "Global 0.25-degree",
        "short_name": "Global Std",
        "resolution": "0.25° (~28 km)",
        "domain_desc": "Global ocean coverage (standard resolution)",
        "domain": {
            "lat_min": -90.0,
            "lat_max": 90.0,
            "lon_min": 0.0,
            "lon_max": 359.75,
        },
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 384,
        "file_template": "gfswave.t{cycle}z.global.0p25.f{fhour:03d}.grib2",
        "dir_template": "gfs.{date}/{cycle}/wave/gridded",
    },
    "atlocn.0p16": {
        "name": "Atlantic Ocean 0.16-degree",
        "short_name": "Atlantic",
        "resolution": "0.16° (~18 km)",
        "domain_desc": "Atlantic Ocean basin",
        "domain": {
            "lat_min": -20.0,
            "lat_max": 55.0,
            "lon_min": 260.0,
            "lon_max": 360.0,
        },
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 384,
        "file_template": "gfswave.t{cycle}z.atlocn.0p16.f{fhour:03d}.grib2",
        "dir_template": "gfs.{date}/{cycle}/wave/gridded",
    },
    "wcoast.0p16": {
        "name": "US West Coast 0.16-degree",
        "short_name": "West Coast",
        "resolution": "0.16° (~18 km)",
        "domain_desc": "US West Coast and Eastern Pacific",
        "domain": {
            "lat_min": 25.0,
            "lat_max": 55.0,
            "lon_min": 210.0,
            "lon_max": 250.0,
        },
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 384,
        "file_template": "gfswave.t{cycle}z.wcoast.0p16.f{fhour:03d}.grib2",
        "dir_template": "gfs.{date}/{cycle}/wave/gridded",
    },
    "epacif.0p16": {
        "name": "East Pacific 0.16-degree",
        "short_name": "East Pacific",
        "resolution": "0.16° (~18 km)",
        "domain_desc": "Eastern Pacific Ocean",
        "domain": {
            "lat_min": -20.0,
            "lat_max": 55.0,
            "lon_min": 130.0,
            "lon_max": 260.0,
        },
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 384,
        "file_template": "gfswave.t{cycle}z.epacif.0p16.f{fhour:03d}.grib2",
        "dir_template": "gfs.{date}/{cycle}/wave/gridded",
    },
    "arctic.9km": {
        "name": "Arctic 9-km",
        "short_name": "Arctic",
        "resolution": "9 km",
        "domain_desc": "Arctic Ocean and sub-arctic seas",
        "domain": {
            "lat_min": 55.0,
            "lat_max": 90.0,
            "lon_min": 0.0,
            "lon_max": 360.0,
        },
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 384,
        "file_template": "gfswave.t{cycle}z.arctic.9km.f{fhour:03d}.grib2",
        "dir_template": "gfs.{date}/{cycle}/wave/gridded",
    },
}
