"""Parsers, formatters, and helper utilities for STOFS data."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Strict JSON
# ---------------------------------------------------------------------------


def _json_safe(obj: Any) -> Any:
    """Recursively convert NaN/±Inf (Python or NumPy) to None and NumPy
    scalars to Python types, so the result serializes as standard JSON."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            obj = obj.item()  # NumPy scalar -> Python scalar
        except (ValueError, TypeError):
            return obj
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def dumps_strict(obj: Any, indent: int | None = 2) -> str:
    """json.dumps that never emits NaN/Infinity: non-finite numbers become
    null, and allow_nan=False guards against anything left over."""
    return json.dumps(_json_safe(obj), indent=indent, allow_nan=False)


def is_finite_number(value: Any) -> bool:
    """True for a real, finite number (False for None, NaN, ±Inf, non-numbers)."""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# NetCDF parsing
# ---------------------------------------------------------------------------


def _detect_variable(nc, candidates: list[str]):
    """Return the first variable name found in the NetCDF dataset."""
    for name in candidates:
        if name in nc.variables:
            return name
    return None


def _decode_station_names(var) -> list[str]:
    """Decode station names from a NetCDF character or byte array variable."""
    import numpy as np

    data = var[:]
    if hasattr(data, "data"):
        data = data.data

    names = []
    # 2D char array: shape (n_stations, str_len)
    if data.ndim == 2:
        for row in data:
            chars = []
            for c in row:
                if isinstance(c, (bytes, np.bytes_)):
                    ch = c.decode("utf-8", errors="replace")
                else:
                    ch = str(c) if c else ""
                chars.append(ch)
            name = "".join(chars).strip("\x00").strip()
            names.append(name)
    # 1D array of bytes or strings
    elif data.ndim == 1:
        for item in data:
            if isinstance(item, (bytes, np.bytes_)):
                name = item.decode("utf-8", errors="replace").strip("\x00").strip()
            else:
                name = str(item).strip("\x00").strip()
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Vertical datum: classify file metadata, never guess an unfamiliar reference
# ---------------------------------------------------------------------------

# Known datum tokens in a CF standard_name / long_name. Separators are '_',
# ' ' or punctuation, so tokens are delimited by non-alphanumerics. Digits
# count as part of a token: "navd2022" is not NAVD88, "gmsl" is not LMSL.
_KNOWN_DATUM_PATTERNS = (
    (re.compile(r"(?<![a-z0-9])navd(?:[ _]?88)?(?![ _]?\d)(?![a-z0-9])"), "NAVD88"),
    (
        re.compile(r"(?<![a-z0-9])mllw(?![a-z0-9])|mean[_ ]lower[_ ]low[_ ]water"),
        "MLLW",
    ),
    (
        re.compile(r"(?<![a-z0-9])l?msl(?![a-z0-9])|(?<![a-z])mean[_ ]sea[_ ]level"),
        "LMSL",
    ),
    (re.compile(r"(?<![a-z0-9])xgeoid[ _]?(\d+[a-z]?)?(?![a-z0-9])"), "xGEOID"),
)

# The reference a label names explicitly: "..._above_<ref>", "relative to <ref>".
_REFERENCE_PHRASE = re.compile(
    r"(?:above|relative[_ ]to|referenced[_ ]to|with[_ ]respect[_ ]to)[_ ]+([a-z0-9][a-z0-9_ ]*)"
)

# References that name no specific vertical datum. ADCIRC writes
# "sea_surface_height_above_geoid" whatever the actual reference.
_GENERIC_REFERENCES = {"geoid"}


def classify_datum_label(
    label: str | None, explicit_reference: bool = False
) -> dict[str, str | None]:
    """Classify one water-level label by the vertical datum it names.

    ``explicit_reference=True`` is for attributes whose whole value is a datum
    name (global ``datum`` / ``vertical_datum``): an unknown value there is
    'unsupported', not 'generic'.

    Returns {'status', 'datum', 'reference'} where status is one of:

    - 'absent': no label;
    - 'generic': names no specific datum (no reference, or ADCIRC's "geoid");
    - 'recognized': names exactly one known datum ('datum' is set);
    - 'unsupported': names an explicit reference this server does not know,
      e.g. NGVD29 or NAVD2022 ('reference' is set);
    - 'conflicting': names more than one known datum.
    """
    text = (label or "").strip().lower()
    if not text:
        return {"status": "absent", "datum": None, "reference": None}

    found: list[str] = []
    for pattern, name in _KNOWN_DATUM_PATTERNS:
        for match in pattern.finditer(text):
            datum = name
            if name == "xGEOID":  # keep the model version, e.g. xGEOID20b
                datum = "xGEOID" + (match.group(1) or "")
            if datum not in found:
                found.append(datum)
    phrase = _REFERENCE_PHRASE.search(text)
    reference = phrase.group(1).strip(" _") if phrase else None
    if explicit_reference and reference is None:
        reference = text

    if len(found) > 1:
        return {"status": "conflicting", "datum": None, "reference": ", ".join(found)}
    if found:
        return {"status": "recognized", "datum": found[0], "reference": reference}
    if reference and reference not in _GENERIC_REFERENCES:
        return {"status": "unsupported", "datum": None, "reference": reference}
    return {"status": "generic", "datum": None, "reference": reference}


def datum_from_label(label: str | None) -> str | None:
    """The single known datum a label names, else None (see classify_datum_label)."""
    return classify_datum_label(label)["datum"]


def _product_signature(nc) -> dict[str, str]:
    """Identify the producing system from global attributes (model, title,
    version, and the STOFS package version in ``history``)."""
    sig: dict[str, str] = {}
    for attr in ("model", "title", "version", "source"):
        value = getattr(nc, attr, None)
        if value is not None:
            sig[attr] = str(value).split("!")[0].strip()
    history = str(getattr(nc, "history", "") or "")
    match = re.search(r"stofs\.v(\d+(?:\.\d+)*)", history)
    if match:
        sig["package"] = f"stofs.v{match.group(1)}"
    title = sig.get("title", "")
    match = re.search(
        r"(STOFS_2D_GLOBAL|ESTOFS GLOBAL)[ ._]*V?(\d+(?:\.\d+)*)", title, re.I
    )
    if match:
        sig["product_version"] = f"{match.group(1).upper()} V{match.group(2)}"
    elif "package" in sig:
        sig["product_version"] = sig["package"]
    return sig


def read_datum_metadata(nc, zeta_var_name: str | None) -> dict[str, Any]:
    """Collect and classify every datum-bearing attribute of a station file.

    Inspects zeta's ``standard_name`` and ``long_name`` and the legacy global
    ``datum`` / ``vertical_datum``, never ``history`` (it names conversion
    scripts, not the result). All raw attribute values are kept.

    Returns a dict with 'status' (absent / generic / recognized / unsupported
    / conflicting, combined over all attributes), 'datum' ('' unless
    recognized), 'label' (the deciding attribute), 'reference', 'attributes'
    ({name: raw value}) and 'product' (global-attribute signature).
    """
    attributes: dict[str, str] = {}
    if zeta_var_name and zeta_var_name in nc.variables:
        var = nc.variables[zeta_var_name]
        for attr in ("standard_name", "long_name"):
            value = getattr(var, attr, None)
            if value:
                attributes[f"{zeta_var_name}:{attr}"] = str(value)
    for attr in ("datum", "vertical_datum"):
        value = getattr(nc, attr, None)
        if value:
            attributes[f":{attr}"] = str(value)

    combined = combine_datum_attributes(attributes)
    combined["product"] = _product_signature(nc)
    return combined


def combine_datum_attributes(attributes: dict[str, str]) -> dict[str, Any]:
    """Combine per-attribute classifications into one file-level verdict.

    An unsupported reference or two different known datums make the file
    'unsupported' / 'conflicting'; generic labels never conflict with a
    specific one.
    """
    classified = {
        k: classify_datum_label(v, explicit_reference=k.startswith(":"))
        for k, v in attributes.items()
    }
    unsupported = [k for k, c in classified.items() if c["status"] == "unsupported"]
    recognized = {
        k: c["datum"] for k, c in classified.items() if c["status"] == "recognized"
    }
    conflicting = [k for k, c in classified.items() if c["status"] == "conflicting"]
    distinct = sorted(set(recognized.values()))

    def fmt(keys):
        return "; ".join(f"{k}={attributes[k]}" for k in keys)

    if unsupported:
        k = unsupported[0]
        status, datum, label, ref = (
            "unsupported",
            "",
            fmt(unsupported),
            classified[k]["reference"],
        )
    elif conflicting or len(distinct) > 1:
        keys = conflicting + [k for k in recognized if k not in conflicting]
        status, datum, label, ref = "conflicting", "", fmt(keys), None
    elif distinct:
        k = next(iter(recognized))
        status, datum, label, ref = "recognized", distinct[0], fmt([k]), None
    elif attributes:
        status, datum, label, ref = "generic", "", fmt(list(attributes)[:1]), None
    else:
        status, datum, label, ref = "absent", "", "", None
    return {
        "status": status,
        "datum": datum,
        "label": label,
        "reference": ref,
        "attributes": attributes,
    }


def _documented_fallback_applies(model: str, product: dict[str, str]) -> bool:
    """Whether NOAA's documented datum may stand in for a generic/absent label.

    Only for the recognized legacy case: STOFS-2D-Global (and its predecessor
    ESTOFS-Global) station files are ADCIRC output whose zeta always carries
    the generic "above geoid" label, while NOAA documents the product as LMSL.
    No fallback for STOFS-3D (its files name the datum explicitly) or for an
    unrecognized producer, so an unfamiliar future file is never silently
    assigned a datum.
    """
    if model != "2d_global":
        return False
    title = product.get("title", "").upper()
    return product.get("model", "").upper() == "ADCIRC" and (
        "STOFS_2D_GLOBAL" in title or "ESTOFS GLOBAL" in title
    )


def resolve_station_datum(
    model: str,
    date: str,
    hour: str,
    parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide which datum a station file's values are referenced to, if any.

    - A recognized datum in the file metadata is used; a warning is added when
      it differs from what NOAA documents for that model and cycle.
    - An unsupported explicit reference or conflicting attributes give datum
      'undetermined' and comparable=False, with the reason in the warning.
    - A generic/absent label falls back to the documented datum only for the
      recognized STOFS-2D/ESTOFS ADCIRC signature; otherwise 'undetermined'.

    Args:
        model: '2d_global' or '3d_atlantic'.
        date: Cycle date, YYYYMMDD.
        hour: Cycle hour, HH.
        parsed: Result of parse_station_netcdf ('datum_status', 'datum',
            'datum_label', 'datum_attributes', 'product').

    Returns:
        Dict with 'datum', 'resolution' (file_metadata / documented_fallback /
        undetermined), 'comparable', 'datum_source', 'datum_warning' ('' if
        none), 'documented_datum', 'attributes' and 'product_version'.
    """
    from .models import documented_station_datum

    parsed = dict(parsed or {})
    documented = documented_station_datum(model, date, hour)
    label = parsed.get("datum_label") or ""
    if not parsed.get("datum_status"):
        # Caller without a classification: classify the "name=value" label(s)
        # rather than trusting a bare datum or assuming absence.
        attrs = dict(part.split("=", 1) for part in label.split("; ") if "=" in part)
        combined = combine_datum_attributes(attrs)
        if parsed.get("datum") and combined["status"] in ("absent", "generic"):
            combined = combined | {"status": "recognized", "datum": parsed["datum"]}
        parsed.setdefault("datum_attributes", attrs)
        parsed["datum"] = combined["datum"] or parsed.get("datum") or ""
        parsed["datum_reference"] = combined["reference"]
        parsed["datum_status"] = combined["status"]
    status = parsed["datum_status"]
    product = parsed.get("product") or {}
    base = {
        "documented_datum": documented,
        "attributes": parsed.get("datum_attributes") or {},
        "product_version": product.get("product_version", ""),
    }

    if status == "recognized":
        datum = parsed.get("datum") or ""
        warning = ""
        if datum != documented:
            warning = (
                f"File metadata says {datum}, but NOAA documents {documented} for "
                f"this model and cycle; using the file's {datum}."
            )
        return base | {
            "datum": datum,
            "resolution": "file_metadata",
            "comparable": True,
            "datum_source": f"file metadata: {label}",
            "datum_warning": warning,
        }
    if status == "unsupported":
        return base | {
            "datum": "undetermined",
            "resolution": "undetermined",
            "comparable": False,
            "datum_source": f"file metadata: {label}",
            "datum_warning": (
                f"The file references '{parsed.get('datum_reference')}', a vertical "
                "datum this server does not recognize; values are not paired with "
                "any CO-OPS datum."
            ),
        }
    if status == "conflicting":
        return base | {
            "datum": "undetermined",
            "resolution": "undetermined",
            "comparable": False,
            "datum_source": f"file metadata: {label}",
            "datum_warning": (
                "The file's datum attributes contradict each other "
                f"({label}); values are not paired with any CO-OPS datum."
            ),
        }
    if _documented_fallback_applies(model, product):
        why = (
            f"file label {label} names no specific datum" if label else "no file label"
        )
        return base | {
            "datum": documented,
            "resolution": "documented_fallback",
            "comparable": True,
            "datum_source": (
                f"NOAA documentation for {product.get('product_version') or 'this product'}; {why}"
            ),
            "datum_warning": "",
        }
    return base | {
        "datum": "undetermined",
        "resolution": "undetermined",
        "comparable": False,
        "datum_source": f"file metadata: {label}"
        if label
        else "no datum metadata in file",
        "datum_warning": (
            "The file names no specific vertical datum and is not a product with a "
            "documented default; values are not paired with any CO-OPS datum."
        ),
    }


def datum_provenance(datum_info: dict[str, Any]) -> dict[str, Any]:
    """JSON-ready provenance for a resolved station datum (every tool emits it).

    'warning' is None when there is nothing to report, so consumers can rely
    on the key being present.
    """
    return {
        "datum": datum_info.get("datum"),
        "resolution": datum_info.get("resolution"),
        "comparable": datum_info.get("comparable"),
        "source": datum_info.get("datum_source"),
        "warning": datum_info.get("datum_warning") or None,
        "documented_datum": datum_info.get("documented_datum"),
        "product_version": datum_info.get("product_version") or None,
        "attributes": datum_info.get("attributes") or {},
    }


def datum_markdown_lines(datum_info: dict[str, Any]) -> list[str]:
    """Markdown metadata lines: the datum with its source, then any warning."""
    lines = [f"Datum: {datum_info.get('datum')} ({datum_info.get('datum_source')})"]
    if datum_info.get("datum_warning"):
        lines.append(f"⚠️ Datum warning: {datum_info['datum_warning']}")
    return lines


def unswap_station_coords(
    model: str | None,
    lats: list[float],
    lons: list[float],
) -> tuple[list[float], list[float]]:
    """Repair STOFS-3D-Atlantic rows whose latitude and longitude are swapped.

    STOFS-3D-Atlantic v2.1 station files (cycles before 2026-08-17 12z) store
    latitude in ``x`` and longitude in ``y`` for most rows (105 of 108),
    although the attributes say the opposite; v3.1 files are correct. The 3D
    domain lies entirely north of the equator and west of Greenwich, so a row
    reading as latitude < 0 < longitude must be swapped. The rule applies only
    to 3d_atlantic: for 2D-Global such a row can be a real station (e.g.
    Australia).
    """
    if model != "3d_atlantic":
        return lats, lons
    fixed_lats, fixed_lons = [], []
    for lat, lon in zip(lats, lons):
        if lat < 0 < lon:
            lat, lon = lon, lat
        fixed_lats.append(lat)
        fixed_lons.append(lon)
    return fixed_lats, fixed_lons


def valid_values(var, raw) -> tuple[Any, Any, dict[str, int]]:
    """Separate usable values from masked, fill and non-finite ones.

    Honours the netCDF4 mask (auto-masked _FillValue/missing_value), the
    variable's _FillValue and missing_value even when unmasked, the legacy
    |v| > 1e10 sentinel, and NaN/±Inf. Nothing is replaced by zero.

    Returns:
        (data, invalid, excluded): float array, boolean array of rejected
        entries, and counts {'masked_or_fill': n, 'nonfinite': n}.
    """
    import numpy as np

    mask = np.ma.getmaskarray(raw)
    data = np.asarray(np.ma.getdata(raw), dtype=float)
    nonfinite = ~np.isfinite(data) & ~mask
    with np.errstate(invalid="ignore"):
        fill = mask | (np.abs(data) > 1e10)
        for attr in ("_FillValue", "missing_value"):
            value = getattr(var, attr, None)
            if value is not None:
                fill |= np.isin(data, np.atleast_1d(np.asarray(value, dtype=float)))
    fill &= ~nonfinite
    invalid = fill | nonfinite
    return (
        data,
        invalid,
        {"masked_or_fill": int(fill.sum()), "nonfinite": int(nonfinite.sum())},
    )


def parse_station_netcdf(
    filepath: Path | str,
    station_id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Open a STOFS station NetCDF file and extract water level time series.

    Args:
        filepath: Path to the downloaded NetCDF file.
        station_id: CO-OPS station ID to extract. If None, returns metadata
                    about all stations without time series data.
        model: '2d_global' or '3d_atlantic', if known. Enables the 3D
               coordinate repair (see unswap_station_coords).

    Returns:
        Dict with keys:
            - 'station_names': list of all station ID strings
            - 'lats': list of latitudes
            - 'lons': list of longitudes
            - 'n_stations': total station count
            - 'n_times': total time steps
            - 'datum': datum named by the zeta metadata ('NAVD88', 'LMSL',
              ...) or '' unless recognized
            - 'datum_status': absent / generic / recognized / unsupported /
              conflicting (see read_datum_metadata)
            - 'datum_label', 'datum_reference', 'datum_attributes' (all raw
              datum-bearing attributes), 'product' (global-attribute signature)
            If station_id provided, also:
            - 'station_id': the matched station ID
            - 'station_idx': index in the array
            - 'times': list of ISO 8601 datetime strings
            - 'values': list of water level values (m), NaN filtered
            - 'lat': station latitude
            - 'lon': station longitude
            - 'model_start': first time string
            - 'model_end': last time string

    Raises:
        ValueError: If station_id is not found in the file.
        RuntimeError: If required variables are missing.
    """
    import netCDF4
    import numpy as np

    nc = netCDF4.Dataset(str(filepath), "r")
    try:
        # --- Detect variable names ---
        time_var_name = _detect_variable(nc, ["time", "ocean_time"])
        zeta_var_name = _detect_variable(
            nc, ["zeta", "elevation", "water_level", "ssh"]
        )
        sname_var_name = _detect_variable(nc, ["station_name", "station", "stationid"])
        lat_var_name = _detect_variable(nc, ["y", "lat", "latitude"])
        lon_var_name = _detect_variable(nc, ["x", "lon", "longitude"])

        if not time_var_name:
            raise RuntimeError("Could not find time variable in NetCDF file.")
        if not zeta_var_name:
            raise RuntimeError("Could not find water level variable in NetCDF file.")

        # --- Station names ---
        station_names: list[str] = []
        if sname_var_name:
            station_names = _decode_station_names(nc.variables[sname_var_name])

        # --- Coordinates ---
        lats: list[float] = []
        lons: list[float] = []
        if lat_var_name:
            lats = list(
                float(v) for v in np.array(nc.variables[lat_var_name][:]).ravel()
            )
        if lon_var_name:
            lons = list(
                float(v) for v in np.array(nc.variables[lon_var_name][:]).ravel()
            )

        if lats and lons:
            lats, lons = unswap_station_coords(model, lats, lons)

        n_stations = len(station_names) or (len(lats) if lats else 0)
        n_times = len(nc.variables[time_var_name])

        # --- Datum, from the water-level variable's own metadata ---
        dm = read_datum_metadata(nc, zeta_var_name)

        result: dict[str, Any] = {
            "station_names": station_names,
            "lats": lats,
            "lons": lons,
            "n_stations": n_stations,
            "n_times": n_times,
            "datum": dm["datum"],
            "datum_status": dm["status"],
            "datum_label": dm["label"],
            "datum_reference": dm["reference"],
            "datum_attributes": dm["attributes"],
            "product": dm["product"],
        }

        if station_id is None:
            return result

        # --- Find station index ---
        station_idx = None
        for i, name in enumerate(station_names):
            if station_id in name or name.strip() == station_id:
                station_idx = i
                break

        if station_idx is None:
            raise ValueError(
                f"Station '{station_id}' not found in this STOFS file. "
                f"Available station IDs (first 20): "
                f"{', '.join(station_names[:20])}"
            )

        # --- Time array ---
        time_var = nc.variables[time_var_name]
        units = getattr(time_var, "units", "seconds since 1970-01-01 00:00:00")
        calendar = getattr(time_var, "calendar", "standard")
        raw_times = time_var[:]
        if hasattr(raw_times, "data"):
            raw_times = raw_times.data

        datetimes = netCDF4.num2date(raw_times, units=units, calendar=calendar)
        time_strings = [dt.strftime("%Y-%m-%d %H:%M") for dt in datetimes]

        # --- Water level time series (zeta shape: (time, station)) ---
        zeta = nc.variables[zeta_var_name]
        data, invalid, excluded = valid_values(zeta, zeta[:, station_idx])

        times_out = []
        values_out = []
        for t_str, v, bad in zip(time_strings, data.tolist(), invalid.tolist()):
            if not bad:
                times_out.append(t_str)
                values_out.append(round(float(v), 4))

        station_lat = lats[station_idx] if station_idx < len(lats) else None
        station_lon = lons[station_idx] if station_idx < len(lons) else None

        result.update(
            {
                "station_id": station_id,
                "station_idx": station_idx,
                "times": times_out,
                "values": values_out,
                "lat": station_lat,
                "lon": station_lon,
                "model_start": time_strings[0] if time_strings else "",
                "model_end": time_strings[-1] if time_strings else "",
                "n_records": len(time_strings),
                "excluded_model_records": excluded,
            }
        )
        return result

    finally:
        nc.close()


# ---------------------------------------------------------------------------
# Nearest station finder
# ---------------------------------------------------------------------------


def find_nearest_station(
    target_lat: float,
    target_lon: float,
    station_lats: list[float],
    station_lons: list[float],
    station_names: list[str],
    max_distance_km: float = 50.0,
) -> tuple[int, str, float] | None:
    """Find the nearest station within max_distance_km.

    Returns:
        (index, station_name, distance_km) or None if none within range.
    """
    best_idx = None
    best_dist = float("inf")

    for i, (lat, lon) in enumerate(zip(station_lats, station_lons)):
        dist = _haversine(target_lat, target_lon, lat, lon)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    if best_idx is None or best_dist > max_distance_km:
        return None

    return best_idx, station_names[best_idx], best_dist


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------


def compute_validation_stats(
    forecast: list[float],
    observed: list[float],
) -> dict[str, float]:
    """Compute bias, RMSE, MAE, max absolute error and correlation.

    Pairs where either value is missing or non-finite are excluded and
    counted in ``n_excluded_nonfinite``; nothing is replaced by zero.

    ``max_abs_error`` is max_t |forecast(t) - observed(t)|, the largest
    pointwise discrepancy. It is not the error in the peak water level; that
    is ``compute_peak_stats``'s ``peak_error_m``. ``peak_error`` is kept as a
    legacy alias of ``max_abs_error`` for existing callers.

    Args:
        forecast: List of STOFS forecast values (m).
        observed: List of CO-OPS observed values (m), same length as forecast.

    Returns:
        Dict with keys: bias, rmse, mae, max_abs_error, peak_error (alias),
        correlation, n, n_excluded_nonfinite.
    """
    import numpy as np

    empty = {
        "bias": None,
        "rmse": None,
        "mae": None,
        "max_abs_error": None,
        "peak_error": None,
        "correlation": None,
        "n": 0,
        "n_excluded_nonfinite": 0,
    }
    if len(forecast) != len(observed):
        return empty
    f = np.array([v if is_finite_number(v) else np.nan for v in forecast], dtype=float)
    o = np.array([v if is_finite_number(v) else np.nan for v in observed], dtype=float)
    keep = np.isfinite(f) & np.isfinite(o)
    n_excluded = int((~keep).sum())
    f, o = f[keep], o[keep]
    if len(f) == 0:
        return empty | {"n_excluded_nonfinite": n_excluded}

    diff = f - o
    bias = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff**2)))
    mae = float(np.mean(np.abs(diff)))
    max_abs_error = float(np.max(np.abs(diff)))

    # Correlation: undefined for a constant series (np.std of identical floats
    # can be ~1e-17, so test the range). None rather than NaN, which is not
    # valid JSON.
    correlation = None
    if np.ptp(f) > 0 and np.ptp(o) > 0:
        r = float(np.corrcoef(f, o)[0, 1])
        correlation = r if math.isfinite(r) else None

    return {
        "bias": round(bias, 4),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "max_abs_error": round(max_abs_error, 4),
        "peak_error": round(max_abs_error, 4),
        "correlation": None if correlation is None else round(correlation, 4),
        "n": int(len(f)),
        "n_excluded_nonfinite": n_excluded,
    }


def compute_peak_stats(
    times: list[str],
    forecast: list[float],
    observed: list[float],
) -> dict[str, Any]:
    """Compare forecast and observed peaks over the same aligned timestamps.

    Both maxima come from the aligned series, so they cover the same period.
    ``observed_peak_at_series_end`` flags an observed maximum on the last
    aligned point: the water was still rising when the record (or the gauge)
    ended, so the true observed peak may be higher.

    Args:
        times: Aligned timestamps, 'YYYY-MM-DD HH:MM' (UTC).
        forecast: Forecast values (m), same length as times.
        observed: Observed values (m), same length as times.

    Returns:
        Dict with observed/forecast peak value and time, peak_error_m
        (forecast peak minus observed peak) and peak_timing_error_hours
        (positive means the forecast peak came later).
    """
    if times and len(times) == len(forecast) == len(observed):
        keep = [
            i
            for i in range(len(times))
            if is_finite_number(forecast[i]) and is_finite_number(observed[i])
        ]
        times = [times[i] for i in keep]
        forecast = [float(forecast[i]) for i in keep]
        observed = [float(observed[i]) for i in keep]
    if not times or not (len(times) == len(forecast) == len(observed)):
        return {
            "observed_peak_m": None,
            "observed_peak_time": None,
            "forecast_peak_m": None,
            "forecast_peak_time": None,
            "peak_error_m": None,
            "peak_timing_error_hours": None,
            "observed_peak_at_series_end": None,
        }

    i_obs = max(range(len(observed)), key=observed.__getitem__)
    i_fc = max(range(len(forecast)), key=forecast.__getitem__)
    t_obs = datetime.strptime(times[i_obs], "%Y-%m-%d %H:%M")
    t_fc = datetime.strptime(times[i_fc], "%Y-%m-%d %H:%M")

    return {
        "observed_peak_m": round(observed[i_obs], 4),
        "observed_peak_time": times[i_obs],
        "forecast_peak_m": round(forecast[i_fc], 4),
        "forecast_peak_time": times[i_fc],
        "peak_error_m": round(forecast[i_fc] - observed[i_obs], 4),
        "peak_timing_error_hours": round((t_fc - t_obs).total_seconds() / 3600, 2),
        "observed_peak_at_series_end": i_obs == len(observed) - 1,
    }


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------


_TIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%m/%d/%Y %H:%M")


def utc_seconds(s: str) -> int | None:
    """Seconds since 1970 for a 'YYYY-MM-DD HH:MM' UTC string, None if malformed.

    Uses calendar.timegm, so the result does not depend on the host's local
    timezone or DST (naive datetime.timestamp() does).
    """
    import calendar

    for fmt in _TIME_FORMATS:
        try:
            return calendar.timegm(datetime.strptime(s, fmt).timetuple())
        except (ValueError, TypeError):
            continue
    return None


def match_timeseries(
    forecast_times: list[str],
    observed_times: list[str],
    tolerance_minutes: int = 3,
) -> dict[str, Any]:
    """Pair forecast and observation timestamps one-to-one, deterministically.

    1. Exact timestamp matches are paired first.
    2. Each remaining forecast time, in time order, takes the nearest unused
       observation within ``tolerance_minutes``; on a tie the earlier
       observation wins. No observation is used twice.

    Times are UTC strings. Malformed times are skipped and counted; for a
    repeated observation timestamp only the first record is used.

    Returns:
        Dict with 'pairs' (sorted (forecast_index, observed_index)), 'exact',
        'nearest', 'bad_forecast_times', 'bad_observed_times',
        'duplicate_observed_times' and 'tolerance_minutes'.
    """
    import bisect

    tol = tolerance_minutes * 60
    obs_by_sec: dict[int, int] = {}
    bad_obs = dup_obs = 0
    for i, t in enumerate(observed_times):
        sec = utc_seconds(t)
        if sec is None:
            bad_obs += 1
        elif sec in obs_by_sec:
            dup_obs += 1
        else:
            obs_by_sec[sec] = i
    obs_secs = sorted(obs_by_sec)

    fc: list[tuple[int, int]] = []
    bad_fc = 0
    for i, t in enumerate(forecast_times):
        sec = utc_seconds(t)
        if sec is None:
            bad_fc += 1
        else:
            fc.append((sec, i))
    fc.sort()

    used: set[int] = set()
    pairs: dict[int, int] = {}
    for sec, fi in fc:  # pass 1: exact
        if sec in obs_by_sec and sec not in used:
            used.add(sec)
            pairs[fi] = obs_by_sec[sec]
    n_exact = len(pairs)
    for sec, fi in fc:  # pass 2: nearest unused within tolerance
        if fi in pairs:
            continue
        best = None
        k = bisect.bisect_left(obs_secs, sec - tol)
        while k < len(obs_secs) and obs_secs[k] <= sec + tol:
            cand = obs_secs[k]
            if cand not in used:
                d = abs(cand - sec)
                if best is None or d < abs(best - sec):  # ties keep the earlier
                    best = cand
            k += 1
        if best is not None:
            used.add(best)
            pairs[fi] = obs_by_sec[best]
    return {
        "pairs": sorted(pairs.items()),
        "exact": n_exact,
        "nearest": len(pairs) - n_exact,
        "bad_forecast_times": bad_fc,
        "bad_observed_times": bad_obs,
        "duplicate_observed_times": dup_obs,
        "tolerance_minutes": tolerance_minutes,
    }


def align_timeseries(
    forecast_times: list[str],
    forecast_values: list[float],
    observed_times: list[str],
    observed_values: list[float],
    tolerance_minutes: int = 3,
) -> tuple[list[str], list[float], list[float]]:
    """Align two time series with match_timeseries (one-to-one, exact first).

    Returns:
        (common_times, aligned_forecast, aligned_observed), in forecast order.
    """
    m = match_timeseries(forecast_times, observed_times, tolerance_minutes)
    common_times = [forecast_times[fi] for fi, _ in m["pairs"]]
    aligned_forecast = [forecast_values[fi] for fi, _ in m["pairs"]]
    aligned_observed = [observed_values[oi] for _, oi in m["pairs"]]
    return common_times, aligned_forecast, aligned_observed


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_timeseries_table(
    times: list[str],
    values: list[float],
    title: str = "",
    metadata_lines: list[str] | None = None,
    max_rows: int = 100,
    source: str = "NOAA STOFS",
) -> str:
    """Format a water level time series as a markdown table.

    Subsamples to max_rows if longer. Includes min/max/mean summary.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    total = len(times)
    if total == 0:
        lines.append("*No data available.*")
        return "\n".join(lines)

    # Compute summary
    import numpy as np

    vals = [v for v in values if v is not None]
    if vals:
        v_min = min(vals)
        v_max = max(vals)
        v_mean = float(np.mean(vals))
        lines.append(
            f"**Min**: {v_min:.3f} m | **Max**: {v_max:.3f} m | "
            f"**Mean**: {v_mean:.3f} m | **Total points**: {total}"
        )
        lines.append("")

    # Subsample
    if total > max_rows:
        step = max(1, total // max_rows)
        indices = list(range(0, total, step))
        times_show = [times[i] for i in indices]
        values_show = [values[i] for i in indices]
        lines.append(f"*Showing every {step}th point ({len(indices)} of {total} rows)*")
        lines.append("")
    else:
        times_show = times
        values_show = values

    lines.append("| Time (UTC) | Water Level (m) |")
    lines.append("| --- | --- |")
    for t, v in zip(times_show, values_show):
        lines.append(f"| {t} | {v:.3f} |")

    lines.append("")
    lines.append(f"*Data from {source}.*")
    return "\n".join(lines)


def format_station_table(
    stations: list[dict],
    title: str = "",
    metadata_lines: list[str] | None = None,
    extra_col: tuple[str, str] | None = None,
    source: str = "NOAA STOFS",
) -> str:
    """Format a list of station dicts as a markdown table.

    Args:
        stations: List of station dicts with id, name, state, lat, lon.
        title: Optional heading.
        metadata_lines: Optional lines shown below title.
        extra_col: Optional (key, header) tuple for an extra column.
        source: Attribution string.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    if extra_col:
        key, header = extra_col
        lines.append(f"| Station ID | Name | State | Lat | Lon | {header} |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for s in stations:
            lines.append(
                f"| {s.get('id', '')} | {s.get('name', '')} | {s.get('state', '')} "
                f"| {s.get('lat', '')} | {s.get('lon', '')} | {s.get(key, '')} |"
            )
    else:
        lines.append("| Station ID | Name | State | Lat | Lon |")
        lines.append("| --- | --- | --- | --- | --- |")
        for s in stations:
            lines.append(
                f"| {s.get('id', '')} | {s.get('name', '')} | {s.get('state', '')} "
                f"| {s.get('lat', '')} | {s.get('lon', '')} |"
            )

    lines.append("")
    lines.append(f"*{len(stations)} stations. Data from {source}.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cycle resolution
# ---------------------------------------------------------------------------


async def resolve_latest_cycle(
    client,
    model: str,
    num_days: int = 2,
) -> tuple[str, str] | None:
    """Find the latest available STOFS cycle on AWS S3.

    Checks today and yesterday (or more days), newest cycle first.

    Args:
        client: STOFSClient instance.
        model: '2d_global' or '3d_atlantic'.
        num_days: Number of past days to check.

    Returns:
        (date_str, cycle_str) tuple (e.g., ('20260219', '12')), or None.
    """
    import time
    from datetime import timedelta
    from .models import MODEL_CYCLES

    # Short-TTL cache on the client: resolving sweeps several S3 HEADs and every
    # forecast tool resolves on each call. Cache positive results only.
    cache = getattr(client, "_cycle_cache", None)
    ttl = getattr(client, "_cycle_cache_ttl", 0.0)
    now = time.monotonic()
    if cache is not None:
        hit = cache.get(model)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]

    cycles = MODEL_CYCLES.get(model, ["12"])
    today = datetime.now(timezone.utc)

    for day_offset in range(num_days):
        date = today - timedelta(days=day_offset)
        date_str = date.strftime("%Y%m%d")
        for cycle in cycles:
            url = client.build_station_url(model, date_str, cycle)
            if await client.check_file_exists(url):
                if cache is not None:
                    cache[model] = (now, (date_str, cycle))
                return date_str, cycle

    return None


async def resolve_cycle(
    client,
    model: str,
    cycle_date: str | None,
    cycle_hour: str | None,
) -> tuple[str, str] | None:
    """Resolve a STOFS cycle (date, hour), finding the latest if unspecified.

    Single source of truth shared by every STOFS tool. If only one of
    ``cycle_date`` / ``cycle_hour`` is given, the other defaults sensibly
    (date → today; hour → the model's first configured cycle) **and the
    provided value is honoured**. The validation tool previously had its own
    copy that required *both* and silently fell back to the latest cycle when
    only a date was given — so a historical ``cycle_date`` was ignored and the
    comparison ran against the wrong (latest) cycle with no error. Centralized
    here to keep that from happening again.

    Returns:
        (YYYYMMDD, HH) or None if a provided ``cycle_date`` is unparseable.

    Raises:
        ValueError: if ``cycle_hour`` is not one of the model's cycle hours
            (checked before any network access).
    """
    from .models import MODEL_CYCLES

    if cycle_date or cycle_hour:
        if cycle_date:
            date_str: str | None = None
            for fmt in ("%Y-%m-%d", "%Y%m%d"):
                try:
                    date_str = datetime.strptime(cycle_date, fmt).strftime("%Y%m%d")
                    break
                except ValueError:
                    continue
            if date_str is None:
                return None
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

        if cycle_hour:
            hour_str = str(cycle_hour).strip().zfill(2)
            valid = MODEL_CYCLES.get(model) or []
            if valid and hour_str not in valid:
                raise ValueError(
                    f"Cycle hour '{cycle_hour}' is not a cycle of {model}; "
                    f"valid hours: {', '.join(sorted(valid))}."
                )
        else:
            # Default to the model's first listed cycle hour.
            hour_str = (MODEL_CYCLES.get(model) or ["12"])[0]
        return date_str, hour_str

    return await resolve_latest_cycle(client, model)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def handle_stofs_error(e: Exception, model: str = "", url: str = "") -> str:
    """Format an exception into a user-friendly STOFS error message.

    Args:
        e: The exception.
        model: Model name for context.
        url: URL that was being accessed.

    Returns:
        User-friendly error string.
    """
    import httpx

    model_label = f" ({model})" if model else ""

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"STOFS file not found{model_label} (HTTP 404). "
                "The cycle may not be available yet or has been archived. "
                "Use stofs_list_cycles to check available forecast cycles."
            )
        if status == 403:
            return (
                f"AWS S3 access denied{model_label} (HTTP 403). "
                "The data may have been archived. Try a more recent date."
            )
        return (
            f"HTTP {status} error{model_label}. "
            "The STOFS S3 bucket may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"Download timed out{model_label}. "
            "STOFS NetCDF files can be 2-10 MB and may be slow. "
            "Try again or use a different cycle."
        )

    if isinstance(e, ValueError):
        return str(e)

    if "NetCDF" in type(e).__name__ or "netCDF" in str(e):
        return (
            f"Error reading STOFS NetCDF file{model_label}. "
            "The file may be corrupted or the format may have changed. "
            "Try a different cycle using stofs_list_cycles."
        )

    return f"Unexpected error{model_label}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# OPeNDAP region selection
# ---------------------------------------------------------------------------


def get_opendap_region(latitude: float, longitude: float) -> str:
    """Return the NOMADS STOFS-2D regional product name for a lat/lon.

    NOMADS serves STOFS as separate per-region datasets. This helper maps
    any lat/lon to the correct region name to use in the OPeNDAP URL.

    Region boundaries are approximate; they are checked in priority order
    (small/specific regions first, broad CONUS regions last).

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees (-180 to 180).

    Returns:
        NOMADS region string: one of 'conus.east', 'conus.west', 'alaska',
        'hawaii', 'puertori', 'guam', 'northpacific'.
    """
    # Guam (positive longitude, western Pacific)
    if 12.0 <= latitude <= 17.0 and 143.0 <= longitude <= 149.0:
        return "guam"

    # Hawaii (~-163W to -153W)
    if 17.5 <= latitude <= 23.5 and -163.0 <= longitude <= -153.0:
        return "hawaii"

    # Puerto Rico / USVI (~-69W to -63W)
    if 16.5 <= latitude <= 20.5 and -69.0 <= longitude <= -63.0:
        return "puertori"

    # Alaska: high latitudes, western hemisphere (west of -130W) or far east Pacific
    if latitude >= 50.0 and (longitude <= -130.0 or longitude >= 150.0):
        return "alaska"

    # CONUS West coast (Pacific): roughly west of -115W
    if 20.0 <= latitude <= 53.0 and -131.0 <= longitude <= -115.0:
        return "conus.west"

    # CONUS East + Gulf: roughly east of -100W (Atlantic + Gulf of Mexico)
    if 20.0 <= latitude <= 53.0 and -100.0 <= longitude <= -60.0:
        return "conus.east"

    # North Pacific / global fallback
    return "northpacific"


# ---------------------------------------------------------------------------
# OPeNDAP point extraction (regular-grid NOMADS datasets)
# ---------------------------------------------------------------------------


def extract_point_from_opendap(
    opendap_url: str,
    latitude: float,
    longitude: float,
    variable: str | None = None,
) -> dict[str, Any]:
    """Extract a time series at a single lat/lon from a NOMADS OPeNDAP dataset.

    Opens the remote dataset with xarray and selects the nearest grid point.
    Only the requested slice is transferred over the network via OPeNDAP —
    the full gridded field is never downloaded.

    **Important**: This function uses blocking I/O (xarray's netCDF4 engine
    for OPeNDAP is synchronous). Always call it via ``asyncio.to_thread()``
    from async tool handlers to avoid blocking the MCP event loop.

    Args:
        opendap_url: Full NOMADS OPeNDAP URL
            (e.g., ``https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/...``).
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        variable: Specific variable name to extract. If None, auto-detects
            the combined water level variable.

    Returns:
        Dict with keys:
            - ``times``: list of 'YYYY-MM-DD HH:MM' strings
            - ``values``: list of water level values (m), NaN filtered
            - ``actual_lat``: float — latitude of nearest grid point
            - ``actual_lon``: float — longitude of nearest grid point
            - ``variable``: str — variable name used
            - ``n_times``: int — number of valid time steps
            - ``grid_resolution_deg``: float — approximate grid spacing (°)

    Raises:
        RuntimeError: If the OPeNDAP endpoint is unreachable.
        ValueError: If no suitable water level variable is found.
    """
    import numpy as np
    import xarray as xr

    try:
        ds = xr.open_dataset(opendap_url, engine="netcdf4")
    except Exception as e:
        raise RuntimeError(
            f"Cannot open OPeNDAP dataset at {opendap_url}. "
            f"NOMADS may be temporarily unavailable. Error: {e}"
        )

    try:
        # --- Auto-detect water level variable if not specified ---
        if variable is None:
            candidates = [
                "etcwlsfc",  # combined water level (NOMADS STOFS OPeNDAP name)
                "etsrgsfc",  # storm surge (NOMADS STOFS OPeNDAP name)
                "etwlswlc",  # alternative name seen in some products
                "etsurgetsrg",  # alternative surge name
                "zeta",  # native NetCDF name (not typical on NOMADS)
                "water_level",
            ]
            for name in candidates:
                if name in ds.data_vars:
                    variable = name
                    break

            if variable is None:
                available = list(ds.data_vars)
                ds.close()
                raise ValueError(
                    f"No known water level variable found in OPeNDAP dataset. "
                    f"Available variables: {available}. "
                    "Specify the variable name explicitly using the 'variable' parameter."
                )

        if variable not in ds.data_vars:
            available = list(ds.data_vars)
            ds.close()
            raise ValueError(
                f"Variable '{variable}' not found in OPeNDAP dataset. "
                f"Available: {available}"
            )

        # --- Resolve longitude convention (NOMADS may use 0-360 instead of -180-180) ---
        lon_vals = ds["lon"].values if "lon" in ds.coords else ds["longitude"].values
        lon_name = "lon" if "lon" in ds.coords else "longitude"
        lat_name = "lat" if "lat" in ds.coords else "latitude"

        query_lon = longitude
        if float(lon_vals.min()) >= 0 and longitude < 0:
            # Dataset uses 0-360, convert target
            query_lon = longitude % 360

        # --- Select nearest grid point ---
        point = ds[variable].sel(
            {lat_name: latitude, lon_name: query_lon},
            method="nearest",
        )

        actual_lat = float(point[lat_name].values)
        actual_lon_raw = float(point[lon_name].values)

        # --- If nearest cell is all NaN (land), find nearest wet ocean cell ---
        # The regular grid has NaN over land; coastal points often snap to a land cell.
        # Load a ±0.5° area at the first time step to find valid ocean cells.
        check_vals = point.values
        time_dim = list(point.dims)[0] if point.dims else "time"
        if np.all(np.isnan(check_vals) | (np.abs(check_vals) > 1e10)):
            search_radius = 0.5
            lat_slice = slice(latitude - search_radius, latitude + search_radius)
            lon_slice = slice(query_lon - search_radius, query_lon + search_radius)
            area = ds[variable].sel({lat_name: lat_slice, lon_name: lon_slice})
            t0_vals = area.isel({time_dim: 0}).values  # (lat, lon)
            lats_area = area[lat_name].values
            lons_area = area[lon_name].values

            valid_mask = ~np.isnan(t0_vals) & (np.abs(t0_vals) < 1e10)
            if valid_mask.sum() > 0:
                lat_grid, lon_grid = np.meshgrid(lats_area, lons_area, indexing="ij")
                dist_grid = (lat_grid - latitude) ** 2 + (lon_grid - query_lon) ** 2
                dist_grid[~valid_mask] = 1e9
                idx = np.unravel_index(np.argmin(dist_grid), dist_grid.shape)
                best_lat = float(lats_area[idx[0]])
                best_lon = float(lons_area[idx[1]])
                # Re-select the full time series at the nearest wet cell
                point = ds[variable].sel(
                    {lat_name: best_lat, lon_name: best_lon}, method="nearest"
                )
                actual_lat = float(point[lat_name].values)
                actual_lon_raw = float(point[lon_name].values)

        # Convert back to -180-180 if needed
        actual_lon = actual_lon_raw if actual_lon_raw <= 180 else actual_lon_raw - 360

        # --- Extract time series ---
        times_raw = point[time_dim].values if time_dim in point.coords else None

        values_raw = point.values  # shape: (time,)

        # Convert numpy datetime64 to strings
        times_out: list[str] = []
        if times_raw is not None:
            for t in times_raw:
                try:
                    if hasattr(t, "isoformat"):
                        times_out.append(t.isoformat()[:16].replace("T", " "))
                    else:
                        # numpy datetime64
                        ts = (
                            t - np.datetime64("1970-01-01T00:00:00")
                        ) / np.timedelta64(1, "s")
                        from datetime import datetime, timezone

                        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                        times_out.append(dt.strftime("%Y-%m-%d %H:%M"))
                except Exception:
                    times_out.append("")

        # Filter NaN / fill values
        times_filtered: list[str] = []
        values_filtered: list[float] = []
        for t_str, v in zip(times_out, values_raw.tolist()):
            try:
                fv = float(v)
                if not (fv is None or (fv != fv) or abs(fv) > 1e10):  # NaN check
                    times_filtered.append(t_str)
                    values_filtered.append(round(fv, 4))
            except (TypeError, ValueError):
                continue

        # Estimate grid resolution
        lat_arr = ds[lat_name].values
        grid_res = abs(float(lat_arr[1] - lat_arr[0])) if len(lat_arr) > 1 else 0.0

        return {
            "times": times_filtered,
            "values": values_filtered,
            "actual_lat": round(actual_lat, 4),
            "actual_lon": round(actual_lon, 4),
            "variable": variable,
            "n_times": len(times_filtered),
            "grid_resolution_deg": round(grid_res, 4),
        }

    finally:
        ds.close()


# ---------------------------------------------------------------------------
# Temp file cleanup
# ---------------------------------------------------------------------------


def cleanup_temp_file(filepath: Path | str | None) -> None:
    """Remove a temporary NetCDF file. Safe to call with None."""
    if filepath is None:
        return
    try:
        os.unlink(str(filepath))
    except OSError:
        pass
