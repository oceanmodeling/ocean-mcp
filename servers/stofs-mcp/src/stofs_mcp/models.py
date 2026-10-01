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


# Datum used by each model in station files
MODEL_DATUMS = {
    "2d_global": "LMSL",  # Local Mean Sea Level
    "3d_atlantic": "NAVD88",
}

# Corresponding CO-OPS datum for validation
COOPS_VALIDATION_DATUMS = {
    "2d_global": "MSL",
    "3d_atlantic": "NAVD",
}

# Approximate product availability lag after cycle time (hours)
MODEL_LAG_HOURS = {
    "2d_global": 3,
    "3d_atlantic": 5,
}
