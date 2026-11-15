"""WP5 reference rules, written from NOAA documentation, CF conventions and stated physical bounds.

This module imports no Ocean-MCP package and was not derived from Ocean-MCP code. Every rule
cites its source. The sources are archived under ``phase0/docs`` and in the Boston package
(``verification_stofs_v31_boston/data/docs``); see DESIGN.md section 4 for the list.

Frozen with DESIGN.md. Changing anything here after the freeze is an amendment.
"""

from __future__ import annotations

import datetime as dt
import math
import re

# --------------------------------------------------------------------------------------------
# Window (DESIGN.md 2.4). Lead is measured from the cycle time; the window is
# lead_start < lead <= lead_end. 49.7 h is the smallest multiple of the 6-minute output
# interval that is not shorter than two lunar days (2 x 24.84 h = 49.68 h).
# --------------------------------------------------------------------------------------------
LEAD_START_H = 0.0
LEAD_END_H = 49.7
STEP_MIN = 6  # STOFS station output and CO-OPS water_level are both 6-minute series

# --------------------------------------------------------------------------------------------
# Physical bound (DESIGN.md 4.3). |water level| above the station's tidal or geodetic
# reference cannot exceed ~22 m anywhere on Earth: the largest tidal half-range is ~8.5 m
# (Bay of Fundy, ~17 m range) and the largest storm surges are ~8-13 m (Katrina 2005 ~8.5 m;
# Bathurst Bay 1899 ~13 m). At the US stations sampled here the envelope is far smaller
# (Cook Inlet half-range ~5 m). 30 m adds a margin for datum-offset errors of a few metres and
# keeps continuity with the WP1 validated workflow (arm B). A value beyond it is not water level.
# Values of |v| >= 1000 m are additionally labelled "code-like" (a no-data code, possibly
# shifted by a constant); the label is descriptive and does not change the classification.
# --------------------------------------------------------------------------------------------
PLAUSIBLE_BOUND_M = 30.0
CODE_LIKE_M = 1000.0
REPORT_BAND_M = (20.0, 100.0)  # every model value in this |v| band is listed (brief)

# --------------------------------------------------------------------------------------------
# Documented station-file datum by product and version (DESIGN.md 4.1).
# * NWS SCN 26-51 (3 Jun 2026): "Station netCDF output will now be referenced to local mean
#   sea level (LMSL) (no longer NAVD88)" for STOFS-3D-Atlantic v3.1 -> v2.1 station netCDF is
#   NAVD88 and v3.1 is LMSL. The SCN lists no change of the STOFS-2D-Global station datum.
# * NOMADS STOFS-Global description (archived 2026-11-04 in the Boston package): STOFS-2D-Global
#   station and gridded output is referenced to LMSL.
# The version is read from the file: 3D global `history` ("packages/stofs.vX.Y.Z/"), 2D global
# `title` ("STOFS_2D_GLOBAL.VX.Y.Z"). A version that the documentation does not cover has no
# documented datum.
# --------------------------------------------------------------------------------------------
DOC_DATUM = {
    ("3d", "2.1"): ("NAVD88", "SCN 26-51: v3.1 station netCDF 'no longer NAVD88' (v2.1 = NAVD88)"),
    ("3d", "3.1"): ("LMSL", "SCN 26-51: v3.1 station netCDF referenced to LMSL"),
    ("2d", "2.1"): ("LMSL", "NOMADS STOFS-Global description (LMSL); SCN 26-51 lists no 2D station datum change"),
    ("2d", "3.1"): ("LMSL", "NOMADS STOFS-Global description: station output referenced to LMSL"),
}
# Dates of v3.1. NOAA STOFS portal (polar.ncep.noaa.gov/estofs/atl.htm and glo.htm, LM 18 Aug
# 2026): "Operational implementation of the STOFS-3D-Atlantic [STOFS-2D-Global] upgrade to v3.1
# occurred at the 12 UTC cycle on August 17 2026" (the documented date used here). SCN 26-51
# (3 Jun 2026) announced 7 July; SCN 26-51 Updated (8 Jul 2026) announced 11 August.
PORTAL_V31_FIRST_CYCLE = dt.datetime(2026, 8, 17, 12, tzinfo=dt.timezone.utc)
SCN_26_51_EFFECTIVE = dt.datetime(2026, 7, 7, 12, tzinfo=dt.timezone.utc)
SCN_26_51_UPDATED_EFFECTIVE = dt.datetime(2026, 8, 11, 12, tzinfo=dt.timezone.utc)

# CO-OPS Data API datum identifiers (api.tidesandcurrents.noaa.gov/api/prod/, archived WP1
# e0020): "MSL" = mean sea level, "NAVD" = North American Vertical Datum. LMSL (local mean sea
# level, the tidal datum) is compared with the station's MSL tidal datum; NAVD88 with NAVD.
PAIRED_COOPS_DATUM = {"LMSL": "MSL", "NAVD88": "NAVD"}
# Name of the same datum in the CO-OPS metadata API datums list (mdapi datums.json).
MDAPI_DATUM_NAME = {"MSL": "MSL", "NAVD": "NAVD88"}

# Separators between the product name and the version vary between products and may vary
# between versions; any run of space, dot, underscore or hyphen is accepted, "V" optional.
# A file whose version cannot be read stops the classification (classify.py), so a pattern
# that is too strict cannot silently turn a whole file into refusals.
_VER_3D = re.compile(r"stofs[ ._-]*v?(\d+)\.(\d+)\.(\d+)", re.I)
_VER_2D = re.compile(r"STOFS[ ._-]*2D[ ._-]*GLOBAL[ ._-]*V?(\d+)\.(\d+)\.(\d+)", re.I)


def product_version(product: str, gattrs: dict) -> str | None:
    """'X.Y.Z' read from the file's own global attributes, or None."""
    if product == "3d":
        m = _VER_3D.search(str(gattrs.get("history", "")))
    else:
        m = _VER_2D.search(str(gattrs.get("title", "")))
    return ".".join(m.groups()) if m else None


def documented_datum(product: str, version: str | None) -> dict:
    if version is None:
        return {"datum": None, "source": "version not stated in the file", "documented": False}
    key = (product, ".".join(version.split(".")[:2]))
    if key in DOC_DATUM:
        d, src = DOC_DATUM[key]
        return {"datum": d, "source": src, "documented": True}
    return {"datum": None, "source": f"version {version} not covered by the documentation", "documented": False}


def date_expectation(product: str, cycle: dt.datetime) -> dict:
    """Version family the documented dates imply for a cycle; compared with the file's own
    version and reported (a disagreement is a documentation defect, not a datum one)."""
    def fam(first):
        return "3.1" if cycle >= first else "2.1"
    return {"portal": fam(PORTAL_V31_FIRST_CYCLE), "scn_26_51": fam(SCN_26_51_EFFECTIVE),
            "scn_26_51_updated": fam(SCN_26_51_UPDATED_EFFECTIVE)}


# --------------------------------------------------------------------------------------------
# Datum label in the file (DESIGN.md 4.1). CF standard names (CF standard-name table):
# sea_surface_height_above_mean_sea_level, sea_surface_height_above_geoid,
# sea_surface_height_above_geopotential_datum, sea_surface_height_above_reference_ellipsoid.
# The STOFS files use non-CF names built the same way ("..._above_navd88", "..._above_msl").
# A "geoid" label names no realised datum (ADCIRC writes it generically; the 2D datum comes from
# documentation). Tokens are matched on word boundaries in standard_name and long_name.
# --------------------------------------------------------------------------------------------
# Boundaries are "not a letter or digit" (an underscore separates tokens in the STOFS names,
# so \b, which treats "_" as a word character, would miss "..._above_mllw").
_B0, _B1 = r"(?<![a-z0-9])", r"(?![a-z0-9])"
_TOKENS = [
    ("NAVD88", re.compile(_B0 + r"navd(?:[\s_-]*88)?" + _B1, re.I)),
    ("LMSL", re.compile(_B0 + r"l?msl" + _B1 + r"|mean[\s_]+sea[\s_]+level", re.I)),
    ("XGEOID20B", re.compile(r"xgeoid", re.I)),
    ("MLLW", re.compile(_B0 + r"mllw" + _B1, re.I)),
    ("IGLD85", re.compile(_B0 + r"igld", re.I)),
]
_GENERIC = re.compile(r"geoid(?!\s*\d)|geopotential|reference[\s_]+ellipsoid", re.I)


def label_datum(zattrs: dict) -> dict:
    found = {}
    for attr in ("standard_name", "long_name"):
        text = str(zattrs.get(attr, "") or "")
        toks = [name for name, rx in _TOKENS if rx.search(text)]
        generic = bool(_GENERIC.search(text)) and not toks
        found[attr] = {"text": text, "datums": toks, "generic": generic}
    datums = sorted({d for v in found.values() for d in v["datums"]})
    if len(datums) > 1 or any(len(v["datums"]) > 1 for v in found.values()):
        status = "conflict"
    elif datums:
        status = "labelled"
    elif any(v["generic"] for v in found.values()):
        status = "generic"
    else:
        status = "absent"
    return {"status": status, "datum": datums[0] if status == "labelled" else None, "attributes": found}


def reference_datum(product: str, doc: dict, lab: dict) -> dict:
    """The datum the reference pairs with, or why there is none.

    3D: the label must name the documented datum. A label that names another datum, or labels
    that conflict, leave the datum undeterminable. A missing label with a documented version is
    'unlabelled': the documented datum is used and the case is flagged (WP1 S1 rule).
    2D: the label is generic by documentation, so the documented datum is used.
    """
    if lab["status"] == "conflict":
        return {"datum": None, "status": "conflicting_labels"}
    if not doc["documented"]:
        return {"datum": None, "status": "undocumented_version"}
    if lab["status"] == "labelled":
        if lab["datum"] != doc["datum"]:
            return {"datum": None, "status": "label_contradicts_documentation"}
        return {"datum": doc["datum"], "status": "label_matches_documentation"}
    if lab["status"] in ("absent", "generic") and product == "3d":
        # a 3D file whose label names no datum: the documented datum is used and the case is
        # flagged; a refusal that names the missing datum label is also accepted (WP1 S1 rule)
        return {"datum": doc["datum"], "status": "unlabelled_documented"}
    return {"datum": doc["datum"], "status": "documented_generic_label"}


# --------------------------------------------------------------------------------------------
# Model value screening (DESIGN.md 4.3). CF: values equal to _FillValue or missing_value are
# missing; values outside valid_min/valid_max/valid_range are invalid. ADCIRC global attribute
# dry_Value marks dry nodes (stated in the 2D files: dry_Value = -99999.0).
# Classes in precedence order: fill, dry, nonfinite, implausible (|v| > PLAUSIBLE_BOUND_M),
# else valid. "code_like" is a sub-label of implausible (|v| >= CODE_LIKE_M).
# --------------------------------------------------------------------------------------------
MODEL_CLASSES = ("fill", "dry", "outside_valid_range", "nonfinite", "implausible", "valid")


def classify_model_value(v: float, fill: list[float], dry: list[float], vrange: tuple | None) -> str:
    if v is None:
        return "fill"
    if any(v == f for f in fill):
        return "fill"
    if any(v == d for d in dry):
        return "dry"
    if not math.isfinite(v):
        return "nonfinite"
    if vrange is not None and not (vrange[0] <= v <= vrange[1]):
        return "outside_valid_range"
    if abs(v) > PLAUSIBLE_BOUND_M:
        return "implausible"
    return "valid"


# --------------------------------------------------------------------------------------------
# Observation screening (DESIGN.md 4.4), CO-OPS Data API response help (archived WP1 e0022):
# each record has t (time), v (value), s (sigma), f (flags O,F,R,L), q (p = preliminary,
# v = verified). An empty or non-numeric v is missing. Flags are counted, never used to filter
# in Study 1 (limit flags trip on genuine extremes). Same physical bound as the model.
# --------------------------------------------------------------------------------------------
FLAG_NAMES = ("O", "F", "R", "L")


def classify_obs_value(v_str) -> tuple[str, float | None]:
    if v_str is None or str(v_str).strip() == "":
        return "missing", None
    try:
        v = float(v_str)
    except (TypeError, ValueError):
        return "missing", None
    if not math.isfinite(v):
        return "nonfinite", None
    if abs(v) > PLAUSIBLE_BOUND_M:
        return "implausible", None
    return "valid", v


def obs_flags(f_str) -> dict:
    parts = [p.strip() for p in str(f_str or "").split(",")]
    out = {}
    for name, p in zip(FLAG_NAMES, parts + [""] * 4):
        try:
            out[name] = int(p) if p else 0
        except ValueError:
            out[name] = 0
    return out


# --------------------------------------------------------------------------------------------
# Time (CF: "<unit> since <reference>", UTC unless stated). The STOFS-2D units string carries a
# trailing ADCIRC comment ("! NCDASE - BASE_DAT"), so the reference time is parsed by regex.
# --------------------------------------------------------------------------------------------
_TUNITS = re.compile(r"^\s*(seconds|minutes|hours|days)\s+since\s+(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?", re.I)
_FACT = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}


def decode_times(values, units: str) -> list[dt.datetime]:
    m = _TUNITS.match(units)
    if not m:
        raise ValueError(f"unparseable time units {units!r}")
    unit, day, hh, mm, ss = m.groups()
    ref = dt.datetime.fromisoformat(f"{day}T{hh}:{mm}:{ss or '00'}").replace(tzinfo=dt.timezone.utc)
    f = _FACT[unit.lower()]
    return [ref + dt.timedelta(seconds=round(float(v) * f, 3)) for v in values]


def in_window(t: dt.datetime, cycle: dt.datetime, lo_h: float = LEAD_START_H, hi_h: float = LEAD_END_H) -> bool:
    lead_s = (t - cycle).total_seconds()
    return lo_h * 3600 < lead_s <= hi_h * 3600 + 1e-6


def window_grid(cycle: dt.datetime, lo_h: float = LEAD_START_H, hi_h: float = LEAD_END_H) -> list[dt.datetime]:
    n = int(round((hi_h - lo_h) * 60 / STEP_MIN))
    start = cycle + dt.timedelta(hours=lo_h)
    return [start + dt.timedelta(minutes=STEP_MIN * (k + 1)) for k in range(n)]


def stats(model: list[float], obs: list[float]) -> dict:
    n = len(model)
    if n == 0:
        return {"n": 0}
    e = [m - o for m, o in zip(model, obs)]
    mm, mo = sum(model) / n, sum(obs) / n
    out = {
        "n": n,
        "bias": sum(e) / n,
        "rmse": math.sqrt(sum(x * x for x in e) / n),
        "mae": sum(abs(x) for x in e) / n,
        "max_abs_error": max(abs(x) for x in e),
        "model_mean": mm,
        "obs_mean": mo,
    }
    if n >= 3:
        sm = math.sqrt(sum((m - mm) ** 2 for m in model) / n)
        so = math.sqrt(sum((o - mo) ** 2 for o in obs) / n)
        out["model_sd"], out["obs_sd"] = sm, so
        out["r"] = (sum((m - mm) * (o - mo) for m, o in zip(model, obs)) / n) / (sm * so) if sm > 0 and so > 0 else None
    return out


# --------------------------------------------------------------------------------------------
# Expected outcome (DESIGN.md 4.5).
# * refuse: no comparison is valid for model-side reasons (datum undeterminable; no valid model
#   value in the window).
# * not_eligible: the comparison cannot be made for observation-side reasons (paired datum not
#   published at the station; no valid paired observation in the window).
# * compare: otherwise.
# All applicable reasons are recorded; a tool refusal "matches" if its reason is among them.
# --------------------------------------------------------------------------------------------


def expected_outcome(ref_datum: dict, n_model_valid_window: int, datum_published: bool | None,
                     n_obs_valid_window: int, n_pairs: int | None = None) -> dict:
    """datum_published is what CO-OPS *served* for the paired datum (False only when it answered
    that the datum is not supported), not the metadata API's list; disagreements between the two
    are reported separately (classify.py)."""
    refuse = []
    if ref_datum["datum"] is None:
        refuse.append("datum_undeterminable")
    if n_model_valid_window == 0:
        refuse.append("no_valid_model_in_window")
    not_elig = []
    if ref_datum["datum"] is not None and datum_published is False:
        not_elig.append("paired_datum_not_published")
    if ref_datum["datum"] is not None and n_obs_valid_window == 0:
        not_elig.append("no_valid_obs_in_window")
    elif (ref_datum["datum"] is not None and n_model_valid_window > 0 and n_obs_valid_window > 0
          and n_pairs == 0):
        not_elig.append("no_common_valid_times")
    if refuse:
        return {"expected": "refuse", "reasons": refuse + not_elig}
    if not_elig:
        return {"expected": "not_eligible", "reasons": not_elig}
    acceptable_refusal = ref_datum.get("status") == "unlabelled_documented"
    return {"expected": "compare", "reasons": [], "refusal_also_acceptable": acceptable_refusal}
