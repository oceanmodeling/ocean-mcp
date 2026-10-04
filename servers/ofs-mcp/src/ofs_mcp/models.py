"""Model registry and enums for OFS MCP server."""

from __future__ import annotations

from enum import Enum


class OFSModel(str, Enum):
    """Supported NOAA Operational Forecast System models."""

    CBOFS = "cbofs"  # Chesapeake Bay — ROMS
    DBOFS = "dbofs"  # Delaware Bay — ROMS
    GOMOFS = "gomofs"  # Gulf of Maine — ROMS
    NGOFS2 = "ngofs2"  # Northern Gulf of Mexico — FVCOM
    NYOFS = "nyofs"  # New York / New Jersey Harbor — POM
    SFBOFS = "sfbofs"  # San Francisco Bay — FVCOM
    TBOFS = "tbofs"  # Tampa Bay — ROMS
    WCOFS = "wcofs"  # West Coast — ROMS
    CIOFS = "ciofs"  # Cook Inlet, Alaska — ROMS


class OFSVariable(str, Enum):
    """Surface variables available from OFS models."""

    WATER_LEVEL = "water_level"  # Surface elevation (zeta)
    TEMPERATURE = "temperature"  # Water temperature (surface)
    SALINITY = "salinity"  # Salinity (surface)


class GridType(str, Enum):
    """OFS model grid types."""

    ROMS = "roms"  # Structured curvilinear (ROMS)
    FVCOM = "fvcom"  # Unstructured triangular (FVCOM)
    POM = "pom"  # Structured curvilinear, sigma levels (POM)


# S3 bucket base URL
S3_BASE = "https://noaa-nos-ofs-pds.s3.amazonaws.com"

# NOAA CO-OPS THREDDS OPeNDAP base (for lazy remote access)
THREDDS_BASE = "https://opendap.co-ops.nos.noaa.gov/thredds/dodsC"

# CO-OPS API base
COOPS_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# Model registry: metadata for each OFS model
OFS_MODELS: dict[str, dict] = {
    "cbofs": {
        "name": "Chesapeake Bay OFS",
        "short_name": "CBOFS",
        "grid_type": "roms",
        "domain_desc": "Chesapeake Bay and adjacent shelf waters",
        "domain": {
            "lat_min": 36.5,
            "lat_max": 39.8,
            "lon_min": -77.4,
            "lon_max": -74.5,
        },
        "states": ["MD", "VA", "DE", "DC"],
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "~291×397 rho-points",
        "vertical_layers": 20,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "ocean_time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salt",
            "lon": "lon_rho",
            "lat": "lat_rho",
        },
        "thredds_id": "CBOFS",
        "has_fmrc": True,
        "s3_file_type": "fields",
    },
    "dbofs": {
        "name": "Delaware Bay OFS",
        "short_name": "DBOFS",
        "grid_type": "roms",
        "domain_desc": "Delaware Bay, Delaware River, and adjacent shelf",
        "domain": {
            "lat_min": 38.5,
            "lat_max": 40.2,
            "lon_min": -75.8,
            "lon_max": -73.5,
        },
        "states": ["DE", "NJ", "PA"],
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "~77×193 rho-points",
        "vertical_layers": 10,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "ocean_time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salt",
            "lon": "lon_rho",
            "lat": "lat_rho",
        },
        "thredds_id": "DBOFS",
        "has_fmrc": True,
        "s3_file_type": "fields",
    },
    "gomofs": {
        "name": "Gulf of Maine OFS",
        "short_name": "GOMOFS",
        "grid_type": "roms",
        "domain_desc": "Gulf of Maine, Georges Bank, and adjacent shelf",
        "domain": {
            "lat_min": 39.0,
            "lat_max": 48.0,
            "lon_min": -72.0,
            "lon_max": -63.0,
        },
        "states": ["ME", "NH", "MA", "RI", "CT"],
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 72,
        "nowcast_hours": 6,
        "grid_size": "~602×420 rho-points",
        "vertical_layers": 30,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "ocean_time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salt",
            "lon": "lon_rho",
            "lat": "lat_rho",
        },
        "thredds_id": "GOMOFS",
        "has_fmrc": True,
        "s3_file_type": "2ds",
    },
    "ngofs2": {
        "name": "Northern Gulf of Mexico OFS v2",
        "short_name": "NGOFS2",
        "grid_type": "fvcom",
        "domain_desc": "Northern Gulf of Mexico including Mississippi River delta",
        "domain": {
            "lat_min": 25.5,
            "lat_max": 31.0,
            "lon_min": -98.0,
            "lon_max": -85.0,
        },
        "states": ["LA", "MS", "AL", "FL", "TX"],
        # NGOFS2 runs at 03/09/15/21 UTC (verified on S3), not 00/06/12/18.
        "cycles": ["03", "09", "15", "21"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "~700k nodes",
        "vertical_layers": 10,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salinity",
            "lon": "lon",
            "lat": "lat",
        },
        "thredds_id": "NGOFS2",
        "has_fmrc": False,
        "s3_file_type": "2ds",
    },
    "nyofs": {
        "name": "New York / NJ Harbor OFS",
        "short_name": "NYOFS",
        "grid_type": "pom",
        "domain_desc": "New York Harbor, Hudson River, and surrounding estuary",
        "domain": {
            "lat_min": 40.3,
            "lat_max": 41.3,
            "lon_min": -74.4,
            "lon_max": -73.5,
        },
        "states": ["NY", "NJ"],
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "134 x 73 points",
        "vertical_layers": 7,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salinity",
            "lon": "lon",
            "lat": "lat",
        },
        "thredds_id": "NYOFS",
        "has_fmrc": True,
        # NOTE: NYOFS publishes a single non-hourly forecast/nowcast file
        # (nyofs.t{cc}z.{date}.fields.forecast.nc), not per-hour files. The
        # standard hourly S3 scheme below does not apply to it; NYOFS S3
        # retrieval remains a separate, unsolved case.
        "s3_file_type": "fields",
    },
    "sfbofs": {
        "name": "San Francisco Bay OFS",
        "short_name": "SFBOFS",
        "grid_type": "fvcom",
        "domain_desc": "San Francisco Bay, San Pablo Bay, Suisun Bay",
        "domain": {
            "lat_min": 37.0,
            "lat_max": 38.9,
            "lon_min": -123.0,
            "lon_max": -121.5,
        },
        "states": ["CA"],
        # SFBOFS runs at 03/09/15/21 UTC (verified on S3), not 00/06/12/18.
        "cycles": ["03", "09", "15", "21"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "~52k nodes",
        "vertical_layers": 10,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salinity",
            "lon": "lon",
            "lat": "lat",
        },
        "thredds_id": "SFBOFS",
        "has_fmrc": False,
        "s3_file_type": "fields",
    },
    "tbofs": {
        "name": "Tampa Bay OFS",
        "short_name": "TBOFS",
        "grid_type": "roms",
        "domain_desc": "Tampa Bay and Charlotte Harbor, Florida",
        "domain": {
            "lat_min": 26.5,
            "lat_max": 28.2,
            "lon_min": -83.0,
            "lon_max": -82.0,
        },
        "states": ["FL"],
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "290 x 176 rho points",
        "vertical_layers": 11,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "ocean_time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salt",
            "lon": "lon_rho",
            "lat": "lat_rho",
        },
        "thredds_id": "TBOFS",
        "has_fmrc": True,
        "s3_file_type": "fields",
    },
    "wcofs": {
        "name": "West Coast OFS",
        "short_name": "WCOFS",
        "grid_type": "roms",
        "domain_desc": "US West Coast from Baja California to the Canadian border",
        "domain": {
            "lat_min": 30.0,
            "lat_max": 50.0,
            "lon_min": -135.0,
            "lon_max": -115.0,
        },
        "states": ["CA", "OR", "WA"],
        "cycles": ["03", "09"],
        "forecast_hours": 72,
        "nowcast_hours": 24,
        "grid_size": "~572×602 rho-points",
        "vertical_layers": 40,
        "datum": "MSL",
        "nc_vars": {
            "time": "ocean_time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salt",
            "lon": "lon_rho",
            "lat": "lat_rho",
        },
        "thredds_id": "WCOFS",
        "has_fmrc": False,
        "s3_file_type": "2ds",
    },
    "ciofs": {
        "name": "Cook Inlet OFS",
        "short_name": "CIOFS",
        "grid_type": "roms",
        "domain_desc": "Cook Inlet, Kachemak Bay, and Kenai Peninsula coast, Alaska",
        "domain": {
            "lat_min": 59.0,
            "lat_max": 61.5,
            "lon_min": -154.0,
            "lon_max": -149.0,
        },
        "states": ["AK"],
        "cycles": ["00", "06", "12", "18"],
        "forecast_hours": 48,
        "nowcast_hours": 6,
        "grid_size": "1044 x 724 rho points",
        "vertical_layers": 30,
        "datum": "NAVD88",
        "nc_vars": {
            "time": "ocean_time",
            "water_level": "zeta",
            "temperature": "temp",
            "salinity": "salt",
            "lon": "lon_rho",
            "lat": "lat_rho",
        },
        "thredds_id": "CIOFS",
        "has_fmrc": True,
        "s3_file_type": "fields",
    },
}
