"""Enums and constants for STOFS MCP server."""

from enum import Enum


class STOFSModel(str, Enum):
    """STOFS operational model components."""

    GLOBAL_2D = "2d_global"  # STOFS-2D-Global (ADCIRC), 4x daily, global
    ATLANTIC_3D = "3d_atlantic"  # STOFS-3D-Atlantic (SCHISM), 1x daily, US East/Gulf


class STOFSProduct(str, Enum):
    """STOFS station output products (2D-Global only; 3D only has CWL)."""

    CWL = "cwl"  # Combined Water Level (tide + surge)
    HTP = "htp"  # Harmonic Tidal Prediction only
    SWL = "swl"  # Surge Water Level (non-tidal residual)


class Region(str, Enum):
    """Geographic regions for station filtering."""

    EAST_COAST = "east_coast"
    GULF = "gulf"
    WEST_COAST = "west_coast"
    ALASKA = "alaska"
    HAWAII = "hawaii"
    PUERTO_RICO = "puerto_rico"


# Cycles available per model
MODEL_CYCLES = {
    "2d_global": ["18", "12", "06", "00"],  # Check newest first
    "3d_atlantic": ["12"],
}

# STOFS-2D-Global ran as ESTOFS-Global before this date. The S3 archive files
# earlier cycles under estofs.YYYYMMDD/ (from 20201230); stofs_2d_glo.YYYYMMDD/
# starts here. Station-file layout is identical across the rename.
ESTOFS_CUTOVER_DATE = "20230108"


def get_model_label(model: str, date: str | None = None) -> str:
    """Human-readable model name, naming ESTOFS for pre-cutover 2D cycles.

    Args:
        model: '2d_global' or '3d_atlantic'.
        date: Cycle date in YYYYMMDD format, if known.
    """
    if model != "2d_global":
        return "STOFS-3D-Atlantic"
    if date and date < ESTOFS_CUTOVER_DATE:
        return "ESTOFS-Global (STOFS-2D predecessor)"
    return "STOFS-2D-Global"


# --- Vertical datums -------------------------------------------------------
#
# The station-file datum is not a fixed property of the model. STOFS v3.1 went
# operational at the 12 UTC cycle on 2026-08-17 (NOAA STOFS portal; NWS SCN
# 26-51 announced it for 2026-07-07). From that cycle STOFS-3D-Atlantic station
# NetCDF is referenced to LMSL instead of NAVD88: the files' zeta attributes
# change from sea_surface_height_above_navd88 to sea_surface_height_above_msl.
# STOFS-2D-Global station and gridded output is documented as LMSL throughout;
# its files carry ADCIRC's generic "above geoid" label, which is not a datum.
# Tools read the datum from the file first (utils.resolve_station_datum) and
# fall back to documented_station_datum() only when the label is ambiguous.

# First STOFS v3.1 cycle, YYYYMMDDHH.
STOFS_V31_FIRST_CYCLE = "2026081712"


def documented_station_datum(model: str, date: str, hour: str) -> str:
    """Station-file datum NOAA documents for a model cycle.

    Args:
        model: '2d_global' or '3d_atlantic'.
        date: Cycle date, YYYYMMDD.
        hour: Cycle hour, HH.
    """
    if model == "3d_atlantic":
        return "LMSL" if f"{date}{hour}" >= STOFS_V31_FIRST_CYCLE else "NAVD88"
    return "LMSL"


# Gridded (GRIB2 / NOMADS) output datum. NOAA: STOFS-3D-Atlantic gridded output
# "will remain referenced to xGEOID20b"; STOFS-2D-Global gridded output is LMSL.
GRIDDED_DATUMS = {
    "2d_global": "LMSL",
    "3d_atlantic": "xGEOID20b",
}

# CO-OPS API request identifier for each model datum. "NAVD" is CO-OPS's name
# for NAVD88. LMSL maps to the station's tidal MSL: same label, but not
# necessarily the same realization or epoch. Datums absent here (e.g.
# xGEOID20b) have no CO-OPS equivalent, so no comparison is attempted.
COOPS_DATUM_FOR_MODEL_DATUM = {
    "LMSL": "MSL",
    "NAVD88": "NAVD",
    "MLLW": "MLLW",
}

# Approximate product availability lag after cycle time (hours)
MODEL_LAG_HOURS = {
    "2d_global": 3,
    "3d_atlantic": 5,
}
