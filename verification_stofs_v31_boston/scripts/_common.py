"""Fixed case definition and portable paths for the STOFS v3.1 Boston case study.

Every path is derived from this file's location, so the package runs from any
checkout. Set STOFS_V31_DATA to keep the (large) raw inputs elsewhere.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
DATA = Path(os.environ.get("STOFS_V31_DATA", PACKAGE / "data"))
RAW = DATA / "raw"
COOPS = DATA / "coops"
DERIVED = DATA / "derived"
DOCS = DATA / "docs"
RESULTS = PACKAGE / "results"
FIGURES = PACKAGE / "figures"
MANIFEST = DATA / "manifest.json"

# --- The case: one fixed, archived cycle (not "latest") ----------------------
CYCLE_DATE = "20261030"
CYCLE_HOUR = "12"
CYCLE_ISO = "2026-10-30 12:00"  # UTC
STATION = "8443970"  # Boston, MA
STATION_NAME = "Boston, MA"

STOFS_FILES = {
    "2d_global": {
        "label": "STOFS-2D-Global",
        "url": "https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.20261030/"
        "stofs_2d_glo.t12z.points.cwl.nc",
        "file": "stofs_2d_glo.20261030.t12z.points.cwl.nc",
    },
    "3d_atlantic": {
        "label": "STOFS-3D-Atlantic",
        "url": "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/"
        "stofs_3d_atl.20261030/stofs_3d_atl.t12z.points.cwl.nc",
        "file": "stofs_3d_atl.20261030.t12z.points.cwl.nc",
    },
}

# Lead windows (hours from the cycle time), half-open: start < lead <= end.
FORECAST_WINDOW = (0.0, 48.0)
NOWCAST_WINDOWS = {"2d_global": (-6.0, 0.0), "3d_atlantic": (-24.0, 0.0)}

# One CO-OPS request covers both nowcasts and the forecast window.
COOPS_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
COOPS_MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations"
COOPS_OBS_PARAMS = {
    "station": STATION,
    "product": "water_level",
    "datum": "MSL",
    "units": "metric",
    "time_zone": "gmt",
    "format": "json",
    "begin_date": "20261029 12:00",
    "end_date": "20261101 12:00",
    "application": "ocean_mcp_verification",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    with open(path) as fh:
        return json.load(fh)


def dump_json(obj, path: Path) -> None:
    """Write standard JSON (never NaN/Infinity)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, allow_nan=False)
        fh.write("\n")


def rel(path: Path) -> str:
    """Path relative to the package, for manifests (no machine-specific roots)."""
    try:
        return str(Path(path).resolve().relative_to(PACKAGE))
    except ValueError:
        return str(path)
