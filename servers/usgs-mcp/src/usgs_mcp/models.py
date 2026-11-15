"""Constants and helpers for usgs-mcp."""

USGS_BASE_URL = "https://waterservices.usgs.gov/nwis"
USGS_PEAK_URL = "https://nwis.waterdata.usgs.gov/nwis/peak"
# NWS National Water Prediction Service — its gauges endpoint accepts a USGS
# site number directly and returns official flood-stage thresholds.
NWPS_GAUGE_URL = "https://api.water.noaa.gov/nwps/v1/gauges"

USER_AGENT = "usgs-mcp/0.1.0 (https://github.com/oceanmodeling/ocean-mcp)"

# Well-known USGS parameter codes
PARAMETER_CODES: dict[str, dict] = {
    "00060": {
        "name": "Discharge",
        "units": "ft³/s (cfs)",
        "description": "Streamflow discharge",
    },
    "00065": {
        "name": "Gage height",
        "units": "ft",
        "description": "Water surface elevation above datum",
    },
    "00010": {"name": "Temperature", "units": "°C", "description": "Water temperature"},
    "00045": {
        "name": "Precipitation",
        "units": "in",
        "description": "Accumulated precipitation",
    },
    "00095": {
        "name": "Specific conductance",
        "units": "µS/cm",
        "description": "Specific conductance at 25°C",
    },
    "00300": {
        "name": "Dissolved oxygen",
        "units": "mg/L",
        "description": "Dissolved oxygen",
    },
    "00400": {"name": "pH", "units": "standard units", "description": "pH of water"},
    "63680": {"name": "Turbidity", "units": "FNU", "description": "Turbidity"},
}

# Well-known reference sites for testing and examples
REFERENCE_SITES: dict[str, dict] = {
    "01646500": {"name": "Potomac River at Little Falls, MD", "state": "MD"},
    "02037500": {"name": "James River at Richmond, VA", "state": "VA"},
    "07010000": {"name": "Mississippi River at St. Louis, MO", "state": "MO"},
    "08066500": {"name": "Trinity River at Romayor, TX", "state": "TX"},
    "02146000": {"name": "Catawba River near Pleasant Garden, NC", "state": "NC"},
}

# US state codes for site queries
US_STATE_CODES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "VI": "Virgin Islands",
    "GU": "Guam",
    "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

# NWS flood stage categories
FLOOD_CATEGORIES: dict[str, str] = {
    "action": "Water is approaching bankfull; begin monitoring",
    "flood": "Minor flooding is occurring or imminent",
    "moderate": "Moderate flooding; some inundation of structures/roads",
    "major": "Major flooding; extensive inundation, significant threat to life/property",
}

# Stat report types
STAT_REPORT_TYPES: dict[str, str] = {
    "daily": "Daily statistics",
    "monthly": "Monthly statistics",
    "annual": "Annual statistics",
}

# USGS data qualification codes
QUALIFICATION_CODES: dict[str, str] = {
    "A": "Approved for publication",
    "P": "Provisional, subject to revision",
    "e": "Estimated",
    "Eqp": "Equipment malfunction",
    "Mnt": "Maintenance",
    "Dry": "Dry conditions",
    "Ssn": "Parameter monitored seasonally",
}


def format_parameter(code: str) -> str:
    """Return a human-readable name for a USGS parameter code."""
    info = PARAMETER_CODES.get(code)
    if info:
        return f"{info['name']} ({info['units']})"
    return f"Parameter {code}"


# USGS Water Services JSON is WaterML 1.1 rendered as JSON
# (https://waterservices.usgs.gov/docs/instantaneous-values/instantaneous-values-details/).
# Each time series declares its missing-data marker in variable.noDataValue
# (-999999.0 in every response seen), and a reading equal to it is not a
# measurement: it carries a qualifier saying why, e.g. "Ice" ("Value is
# affected by ice at the measurement site."), "Eqp" or "Ssn". USGS's guide to
# its new APIs (https://api.waterdata.usgs.gov/docs/ogcapi/migration/,
# retrieved 2026-11-09) maps the legacy field the same way: "noDataValue: No
# longer provided. Missing data is now represented with null values."
def screen_series_values(ts: dict) -> tuple[list[dict], dict]:
    """Split one WaterML time series into valid readings and excluded ones.

    A reading is excluded, and counted by reason, when its value equals the
    series' declared ``noDataValue`` ("no_data_value"), does not parse as a
    number ("non_numeric"), or is NaN/infinite ("non_finite"). Excluded
    readings are never replaced by a number.

    Returns:
        (valid, info). ``valid`` lists ``{"datetime", "value" (float),
        "qualifiers"}`` in source order. ``info`` holds ``no_data_value``,
        ``readings`` (all), ``valid``, ``excluded`` (counts by reason),
        ``excluded_qualifiers`` (counts of the qualifier sets of excluded
        readings) and ``latest`` (the last reading: datetime, raw value,
        qualifiers, and the exclusion reason or None).
    """
    import math

    no_data = ts.get("variable", {}).get("noDataValue")
    excluded = {"no_data_value": 0, "non_numeric": 0, "non_finite": 0}
    excluded_qualifiers: dict[str, int] = {}
    valid: list[dict] = []
    readings = 0
    latest = None
    for val_set in ts.get("values", []):
        for v in val_set.get("value", []):
            readings += 1
            quals = ",".join(
                q.get("qualifierCode", "") if isinstance(q, dict) else str(q)
                for q in v.get("qualifiers", [])
            )
            raw = v.get("value", "")
            reason = None
            try:
                x = float(raw)
            except (TypeError, ValueError):
                reason = "non_numeric"
            else:
                if not math.isfinite(x):
                    reason = "non_finite"
                elif no_data is not None and x == float(no_data):
                    reason = "no_data_value"
            latest = {
                "datetime": v.get("dateTime", ""),
                "value": raw,
                "qualifiers": quals,
                "excluded_reason": reason,
            }
            if reason:
                excluded[reason] += 1
                excluded_qualifiers[quals] = excluded_qualifiers.get(quals, 0) + 1
            else:
                valid.append(
                    {"datetime": v.get("dateTime", ""), "value": x, "qualifiers": quals}
                )
    info = {
        "no_data_value": no_data,
        "readings": readings,
        "valid": len(valid),
        "excluded": excluded,
        "excluded_qualifiers": excluded_qualifiers,
        "latest": latest,
    }
    return valid, info


def describe_exclusions(info: dict) -> str:
    """One-line description of the readings screen_series_values excluded."""
    parts = []
    n = info["excluded"]
    if n["no_data_value"]:
        parts.append(
            f"{n['no_data_value']:,} USGS no-data value ({info['no_data_value']})"
        )
    if n["non_numeric"]:
        parts.append(f"{n['non_numeric']:,} non-numeric")
    if n["non_finite"]:
        parts.append(f"{n['non_finite']:,} non-finite")
    if not parts:
        return "none excluded"
    quals = ", ".join(
        f"{q or 'none'} x{c:,}" for q, c in info["excluded_qualifiers"].items()
    )
    return "; ".join(parts) + (f" (qualifiers: {quals})" if quals else "")
