"""Parsers, formatters, and helper utilities for reconnaissance data."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Directory listing parser
# ---------------------------------------------------------------------------


def parse_directory_listing(html: str) -> list[dict]:
    """Parse an Apache-style HTML directory listing into file entries.

    Args:
        html: Raw HTML from an Apache directory index page.

    Returns:
        List of dicts with 'filename' and 'href' keys.
    """
    entries: list[dict] = []
    # Match <a href="...">...</a> links, skip parent directory and sorting links
    for match in re.finditer(
        r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', html, re.IGNORECASE
    ):
        href = match.group(1)
        text = match.group(2).strip()

        # Skip parent dir, Apache sorting links, and header artifacts
        if href in ("../", "/", "?") or text in (
            "Parent Directory",
            "Name",
            "Last modified",
            "Size",
            "Description",
        ):
            continue
        if href.startswith("?") or href.startswith("/"):
            continue

        entries.append({"filename": text, "href": href})

    return entries


# ---------------------------------------------------------------------------
# HDOB parser
# ---------------------------------------------------------------------------


# HD/HA data line (NHC HDOB spec, https://www.nhc.noaa.gov/abouthdobs_2007.shtml):
#   hhmmss LLLLH NNNNNW PPPP GGGGG XXXX sTTT sddd wwwSSS MMM KKK ppp FF
# 13 fields. A missing value is slashes ('///'); the spec also allows 999.
_HDOB_DATA_LINE = re.compile(r"^\d{6}\s+\d{4}[NS]\s+\d{5}[EW]\s")
# Mission/ob identifier line: '<mission id> HDOB <ob number> <YYYYMMDD>'.
_HDOB_MISSION_LINE = re.compile(r"^(.+?)\s+HDOB\s+(\d+)\s+(\d{8})\s*$")


def parse_hdob_message(text: str) -> dict:
    """Parse an HDOB (High Density Observation) bulletin.

    A bulletin is a WMO header (URNT15/URPN15/URPA15), a mission line ending
    in ``HDOB <ob number> <YYYYMMDD>`` and up to 20 data lines. YYYYMMDD is
    the date of the first data line; it advances when the time of day wraps
    past midnight within the bulletin.

    Args:
        text: Raw HDOB bulletin text.

    Returns:
        Dict with 'header' info and 'observations' list.
    """
    header: dict = {}
    observations: list[dict] = []
    day: date | None = None
    prev_time = ""

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("$$", "NNNN")):
            break
        if re.match(r"^UR(NT|PN|PA)15\b", stripped):
            header["wmo_header"] = stripped
            continue
        mission = _HDOB_MISSION_LINE.match(stripped)
        if mission:
            mission_id = " ".join(mission.group(1).split())
            header["mission"] = mission_id
            header["aircraft"] = mission_id.split()[0]
            header["ob_number"] = int(mission.group(2))
            header["date"] = mission.group(3)
            try:
                day = datetime.strptime(mission.group(3), "%Y%m%d").date()
            except ValueError:
                day = None
            continue

        fields = stripped.split()
        if day is None or len(fields) != 13 or not _HDOB_DATA_LINE.match(stripped):
            continue
        if fields[0] < prev_time:
            day += timedelta(days=1)
        prev_time = fields[0]
        observations.append(_parse_hdob_record(fields, day))

    return {"header": header, "observations": observations}


def _parse_hdob_record(fields: list[str], day: date) -> dict:
    """Decode one 13-field HD/HA data line.

    Values are 30-s averages except peak_fl_wind_kt and sfmr_sfc_wind_kt,
    which are the highest 10-s means in the encoding interval;
    sfmr_rain_rate_mmhr is the SFMR rain rate over that same 10 s.
    """
    static = _decode_hdob_pressure(fields[3])
    # XXXX is the extrapolated surface pressure when flying at or below the
    # 550 mb level and the D-value (m) above it.
    extrapolated_slp = d_value = None
    if static is not None and static >= 550.0:
        extrapolated_slp = _decode_hdob_pressure(fields[5])
    elif static is not None:
        d_value = _decode_hdob_d_value(fields[5])

    wind = fields[8] if len(fields[8]) == 6 else "//////"
    return {
        "date": day.strftime("%Y%m%d"),
        "time": fields[0],
        "lat": _parse_hdob_latlon(fields[1], is_lat=True),
        "lon": _parse_hdob_latlon(fields[2], is_lat=False),
        "static_pressure_mb": static,
        "geopotential_alt_m": _hdob_int(fields[4]),
        "extrapolated_slp_mb": extrapolated_slp,
        "d_value_m": d_value,
        "temp_c": _hdob_tenths(fields[6]),
        "dewpoint_c": _hdob_tenths(fields[7]),
        "fl_wind_dir_deg": _hdob_int(wind[:3], missing=999),
        "fl_wind_speed_kt": _hdob_int(wind[3:], missing=999),
        "peak_fl_wind_kt": _hdob_int(fields[9], missing=999),
        "sfmr_sfc_wind_kt": _hdob_int(fields[10], missing=999),
        "sfmr_rain_rate_mmhr": _hdob_int(fields[11], missing=999),
        "qc_flags": fields[12],
    }


def _parse_hdob_latlon(value: str, is_lat: bool) -> float | None:
    """Parse HDOB lat/lon in DDMM or DDDMM format (degrees + minutes).

    Examples:
        '2606N' → 26.1  (26 degrees, 06 minutes)
        '08015W' → -80.25  (80 degrees, 15 minutes)
    """
    if not value or value.startswith("///"):
        return None

    try:
        hemi = value[-1].upper()
        numeric = value[:-1]

        # HDOB lat is exactly DDMM (4 digits); lon is exactly DDDMM (5 digits).
        # Reject off-spec lengths so wrong-column data parses to None instead of
        # silently producing bogus coordinates.
        expected_len = 4 if is_lat else 5
        if len(numeric) != expected_len or not numeric.isdigit():
            return None

        degrees = int(numeric[:-2])
        minutes = int(numeric[-2:])
        if minutes >= 60:
            return None

        result = degrees + minutes / 60.0
        if hemi in ("S", "W"):
            result = -result
        return round(result, 4)
    except (ValueError, IndexError):
        return None


def _hdob_int(value: str, missing: int | None = None) -> int | None:
    """Parse an integer HDOB field; slashes, or the ``missing`` code, mean None."""
    if not value or "/" in value:
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return None if number == missing else number


def _hdob_tenths(value: str) -> float | None:
    """Parse a signed tenths field such as '+213' -> 21.3 or '-045' -> -4.5."""
    number = _hdob_int(value)
    return None if number is None else round(number / 10.0, 1)


def _decode_hdob_pressure(value: str) -> float | None:
    """Decode an HDOB pressure: tenths of mb, leading 1 dropped at >= 1000 mb.

    Examples: '6965' -> 696.5, '9892' -> 989.2, '0015' -> 1001.5
    """
    tenths = _hdob_int(value)
    if tenths is None:
        return None
    # Below 1000 tenths (100.0 mb) is above any recon aircraft's ceiling, so
    # such a value can only be 1000.0 mb or more with its leading 1 dropped.
    if tenths < 1000:
        tenths += 10000
    return round(tenths / 10.0, 1)


def _decode_hdob_d_value(value: str) -> int | None:
    """Decode an HDOB D-value (m). Negative values come in two encodings.

    The spec's D + 5000 ('4825' -> -175) and 5000 + |D| ('5002' -> -2) both
    occur in archived bulletins; each matched the standard-atmosphere D-value
    from that line's own pressure and height. Real D-values stay within
    about +-1500 m, so the 4xxx and 5xxx ranges cannot be confused.
    """
    raw = _hdob_int(value)
    if raw is None:
        return None
    if raw >= 5000:
        return 5000 - raw
    if raw >= 4000:
        return raw - 5000
    return raw


# ---------------------------------------------------------------------------
# VDM parser
# ---------------------------------------------------------------------------

# A VDM is a list of lettered items. The NHC archive (2006 onward) has two
# layouts: A-U since 2018 and A-P before. Both give the fix time in A, the
# center in B and the standard-level height in C; the rest moved.
_VDM_ITEMS = {
    "2018": {
        "min_slp": "D",
        "center_sfc_wind": "E",
        "eye_character": "F",
        "eye_shape": "G",
        "max_sfc_wind_inbound": "H",
        "max_fl_wind_inbound": "J",
        "max_sfc_wind_outbound": "L",
        "max_fl_wind_outbound": "N",
        "temp_outside": "P",
        "temp_inside": "Q",
        "mission": "U",
    },
    "pre-2018": {
        "max_sfc_wind_inbound": "D",
        "max_fl_wind_inbound": "F",
        "min_slp": "H",
        "temp_outside": "I",
        "temp_inside": "J",
        "eye_character": "L",
        "eye_shape": "M",
        "mission": "P",
    },
}


def parse_vdm_message(text: str, issued: datetime | None = None) -> dict:
    """Parse a Vortex Data Message (VDM) in the 2018+ or the earlier layout.

    Args:
        text: Raw VDM bulletin text.
        issued: When the bulletin was issued (e.g. from the archive file
            name). Item A has only day and time, so the year and month come
            from here; without it fix_time_utc is item A's raw text.

    Returns:
        Dict of decoded items. Items the message gives as NA are None.
    """
    result: dict = {"raw_text": text, "storm_id": None}
    items: dict[str, str] = {}
    continuation: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in ("$$", ";"):
            continue
        item = re.match(r"^([A-U])\.\s*(.*)$", stripped)
        if item:
            current = item.group(1)
            items[current] = item.group(2).strip()
        elif current is not None:
            continuation.setdefault(current, []).append(stripped)
        else:
            if re.match(r"^UR(NT|PN)12\b", stripped):
                result["wmo_header"] = stripped
            storm = re.search(r"VORTEX\s+DATA\s+MESSAGE\s+(\w+)", stripped, re.I)
            if storm:
                result["storm_id"] = storm.group(1).upper()

    layout = "2018" if "U" in items else "pre-2018"
    letters = _VDM_ITEMS[layout]
    # Lines after the last item (the mission line) are free-text remarks;
    # elsewhere a line continues its item, e.g. the older layout's longitude.
    remarks = continuation.pop(letters["mission"], [])
    for letter, extra in continuation.items():
        items[letter] = " ".join([items[letter], *extra])

    def item_text(name: str) -> str | None:
        letter = letters.get(name)
        return items.get(letter) if letter else None

    lat, lon = _vdm_center(items.get("B"))
    slp_text = item_text("min_slp")
    min_slp = _vdm_number(slp_text, "mb")
    sfc_dir, sfc_kt = _vdm_dir_speed(item_text("center_sfc_wind"))
    in_dir, in_kt = _vdm_dir_speed(item_text("max_fl_wind_inbound"))
    out_dir, out_kt = _vdm_dir_speed(item_text("max_fl_wind_outbound"))
    eye_shape = _vdm_text(item_text("eye_shape"))

    result.update(
        {
            "vdm_format": layout,
            "fix_time_utc": _vdm_fix_time(items.get("A"), issued),
            "center_lat": lat,
            "center_lon": lon,
            "std_level_mb": _vdm_number(items.get("C"), "mb"),
            "min_height_m": _vdm_number(items.get("C"), "m"),
            "min_slp_mb": min_slp,
            "min_slp_extrapolated": (
                "EXTRAP" in slp_text.upper() if min_slp is not None else None
            ),
            "center_sfc_wind_dir_deg": sfc_dir,
            "center_sfc_wind_kt": sfc_kt,
            "eye_character": _vdm_text(item_text("eye_character")),
            "eye_shape": eye_shape,
            "eye_diameter_nm": _vdm_eye_diameter(eye_shape),
            "max_sfc_wind_inbound_kt": _vdm_number(
                item_text("max_sfc_wind_inbound"), "kt"
            ),
            "max_fl_wind_inbound_dir_deg": in_dir,
            "max_fl_wind_inbound_kt": in_kt,
            "max_sfc_wind_outbound_kt": _vdm_number(
                item_text("max_sfc_wind_outbound"), "kt"
            ),
            "max_fl_wind_outbound_dir_deg": out_dir,
            "max_fl_wind_outbound_kt": out_kt,
            "max_fl_temp_outside_c": _vdm_number(item_text("temp_outside"), "C"),
            "max_fl_temp_inside_c": _vdm_number(item_text("temp_inside"), "C"),
            "observation_line": _vdm_text(item_text("mission")),
            "remarks": " / ".join(remarks) or None,
        }
    )
    return result


def _vdm_text(value: str | None) -> str | None:
    """Collapse whitespace; None for an empty or NA item."""
    if not value or value.strip().upper() == "NA":
        return None
    return " ".join(value.split())


def _vdm_number(value: str | None, unit: str) -> int | None:
    """First integer followed by ``unit``: '943 mb', 'EXTRAP 1011 MB', '14 C'."""
    if not value:
        return None
    match = re.search(rf"(-?\d+)\s*{unit}\b", value, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _vdm_dir_speed(value: str | None) -> tuple[int | None, int | None]:
    """Direction and speed from an item such as '122 deg 101 kt'."""
    match = re.search(r"(\d+)\s*deg\s+(\d+)\s*kt", value or "", re.IGNORECASE)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _vdm_center(value: str | None) -> tuple[float | None, float | None]:
    """Decode item B, the center fix, to signed decimal degrees.

    2018+: '21.74 deg N 092.07 deg W'. Before: '36 deg 26 min N 071 deg 47
    min W' (the longitude line already joined on).
    """
    if not value:
        return None, None
    decimal = re.search(
        r"([\d.]+)\s*deg\s*([NS])\s+([\d.]+)\s*deg\s*([EW])", value, re.IGNORECASE
    )
    if decimal:
        lat, lon = float(decimal.group(1)), float(decimal.group(3))
        lat_hemi, lon_hemi = decimal.group(2), decimal.group(4)
    else:
        dm = re.search(
            r"(\d+)\s*deg\s*(\d+)\s*min\s*([NS])\s+(\d+)\s*deg\s*(\d+)\s*min\s*([EW])",
            value,
            re.IGNORECASE,
        )
        if not dm or int(dm.group(2)) >= 60 or int(dm.group(5)) >= 60:
            return None, None
        lat = int(dm.group(1)) + int(dm.group(2)) / 60.0
        lon = int(dm.group(4)) + int(dm.group(5)) / 60.0
        lat_hemi, lon_hemi = dm.group(3), dm.group(6)
    if lat > 90.0 or lon > 180.0:
        return None, None
    if lat_hemi.upper() == "S":
        lat = -lat
    if lon_hemi.upper() == "W":
        lon = -lon
    return round(lat, 4), round(lon, 4)


def _vdm_fix_time(value: str | None, issued: datetime | None) -> str | None:
    """Item A ('07/12:44:10Z', or older '10/1131Z') as an ISO UTC time.

    The year and month come from ``issued``; a fix day later in the month
    than the issue day belongs to the previous month.
    """
    if not value:
        return None
    match = re.match(r"(\d{1,2})/(\d{2}):?(\d{2}):?(\d{2})?Z", value.strip())
    if not match or issued is None:
        return value.strip()
    day, hour, minute = (int(match.group(i)) for i in (1, 2, 3))
    second = int(match.group(4) or 0)
    year, month = issued.year, issued.month
    if day > issued.day:
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    try:
        fix = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return value.strip()
    return fix.strftime("%Y-%m-%dT%H:%M:%SZ")


def _vdm_eye_diameter(shape: str | None) -> int | None:
    """Eye diameter (nm) from the eye-shape item: 'C10' -> 10, or the inner
    eye of a concentric 'CO15-30' -> 15. An elliptical 'E04/33/23' gives
    orientation and axes, not one diameter, so it returns None."""
    match = re.match(r"^CO?(\d+)", shape or "", re.IGNORECASE)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# ATCF f-deck parser
# ---------------------------------------------------------------------------

# Leading f-deck columns shared by every fix format (checked against NHC
# f-decks from 2005 to 2026):
#   0 basin, 1 cyclone number, 2 YYYYMMDDHHMM, 3 fix format code
#   (10/20 Dvorak, 30/31 microwave/scatterometer, 40 radar, 50 aircraft,
#   60 dropsonde, 70 analysis), 4 fix type (DVTS, AIRC, DRPS, ANAL, ...),
#   5 center/intensity flags, 6 'F' if flagged as bad, 7 lat, 8 lon,
#   9 height of ob, 10 position confidence, 11 wind (kt), 12 its confidence,
#   13 pressure (mb), 14 its confidence, ... 30 fix site (CIMS, KNHC, ...).
_FDECK_MIN_FIELDS = 14


def _parse_atcf_fix_latlon(value: str, is_lat: bool) -> float | None:
    """Parse an ATCF f-deck (fix) lat/lon in hundredths of a degree.

    F-deck records encode position in HUNDREDTHS of a degree with a trailing
    hemisphere character — distinct from b-deck/a-deck best-track records,
    which use TENTHS (see ``parse_atcf_latlon``). The number is not zero
    padded: 94.90 W is '9490W' and 105.12 W is '10512W'.

    Non-digit bodies, a missing or wrong hemisphere, out-of-range
    magnitudes, or a bare 0 (a placeholder: one radar fix reads '0E' at
    29.46 N) return None.

    Examples:
        '2557N'  -> 25.57
        '9490W'  -> -94.90
    """
    if not value:
        return None
    hemi = value[-1].upper()
    numeric = value[:-1]
    if hemi not in (("N", "S") if is_lat else ("E", "W")):
        return None
    if not numeric.isdigit() or len(numeric) > (4 if is_lat else 5):
        return None

    result = int(numeric) / 100.0
    if result == 0.0 or result > (90.0 if is_lat else 180.0):
        return None
    if hemi in ("S", "W"):
        result = -result
    return round(result, 4)


def _fdeck_int(value: str) -> int | None:
    """Integer f-deck field, None when blank."""
    try:
        return int(value)
    except ValueError:
        return None


def parse_atcf_fix_record(line: str) -> dict | None:
    """Parse one ATCF f-deck (fix) record.

    Aircraft, dropsonde, satellite, radar and analysis fixes share the
    leading columns decoded here. Intensity-only fixes carry no position, so
    their lat/lon are None.

    Args:
        line: Single line from an f-deck file.

    Returns:
        Parsed record dict, or None if the line is blank or malformed.
    """
    fields = [f.strip() for f in line.split(",")]
    if len(fields) < _FDECK_MIN_FIELDS:
        return None
    cyclone_num = _fdeck_int(fields[1])
    if cyclone_num is None:
        return None

    return {
        "basin": fields[0],
        "cyclone_num": cyclone_num,
        "datetime": fields[2],  # YYYYMMDDHHMM
        "fix_format": _fdeck_int(fields[3]),
        "fix_type": fields[4],
        "center_intensity": fields[5] or None,
        "flagged": fields[6].upper() == "F",
        "lat": _parse_atcf_fix_latlon(fields[7], is_lat=True),
        "lon": _parse_atcf_fix_latlon(fields[8], is_lat=False),
        "max_wind_kt": _fdeck_int(fields[11]),
        "min_pressure_mb": _fdeck_int(fields[13]),
        "fix_site": fields[30] if len(fields) > 30 and fields[30] else None,
    }


def parse_atcf_latlon(lat_str: str, lon_str: str) -> tuple[float, float]:
    """Parse ATCF latitude/longitude strings (tenths of degree with hemisphere).

    Examples:
        '281N', '0940W' -> (28.1, -94.0)
        '125S', '1700E' -> (-12.5, 170.0)

    Args:
        lat_str: Latitude string (e.g., '281N').
        lon_str: Longitude string (e.g., '0940W').

    Returns:
        (latitude, longitude) tuple in decimal degrees.
    """
    lat_str = lat_str.strip()
    lon_str = lon_str.strip()

    lat_hemi = lat_str[-1].upper()
    lat_val = float(lat_str[:-1]) / 10.0
    if lat_hemi == "S":
        lat_val = -lat_val

    lon_hemi = lon_str[-1].upper()
    lon_val = float(lon_str[:-1]) / 10.0
    if lon_hemi == "W":
        lon_val = -lon_val

    return lat_val, lon_val


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_tabular_data(
    data: list[dict],
    columns: list[tuple[str, str]],
    title: str = "",
    metadata_lines: list[str] | None = None,
    count_label: str = "records",
    source: str = "NOAA NHC Reconnaissance Archive",
    max_rows: int = 2000,
    keep: str = "head",
) -> str:
    """Format a list of dicts as a markdown table.

    Args:
        data: List of row dicts.
        columns: List of (dict_key, display_header) pairs.
        title: Optional markdown heading.
        metadata_lines: Optional lines shown below the title.
        count_label: Label for the count footer.
        source: Data source attribution.
        max_rows: Cap on rows rendered (default 2000). A wide date range or
            a high ``limit`` can pull in far more observations/bulletins
            than are useful to render; rendering them all floods the
            model's context.
        keep: Which end of ``data`` to keep when truncating — "head"
            (default) for sources already ordered newest-first (or with
            unspecified order — the NHC archive tools sort their file
            listing newest-filename-first before this is ever called), or
            "tail" for oldest-first sources (e.g. ATCF f-deck fixes, which
            the upstream archive serves chronologically ascending) so the
            most recent rows survive truncation.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        lines.append(" | ".join(f"**{m}**" for m in metadata_lines))
        lines.append("")

    total = len(data)
    truncated = total > max_rows
    if truncated:
        rows = data[-max_rows:] if keep == "tail" else data[:max_rows]
    else:
        rows = data

    # Header
    headers = [col[1] for col in columns]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    # Rows
    for row in rows:
        values = (row.get(col[0], "") for col in columns)
        cells = ["—" if v is None else str(v) for v in values]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    if truncated:
        which = "most recent" if keep == "tail" else "first"
        lines.append(
            f"*Showing the {which} {len(rows)} of {total} {count_label} "
            f"(truncated). Narrow your query (a smaller limit, or a "
            f"specific month/day) or call with response_format='json' and "
            f"a higher max_records for more. Data from {source}.*"
        )
    else:
        lines.append(f"*{len(rows)} {count_label} returned. Data from {source}.*")

    return "\n".join(lines)


def format_json_response(
    data: dict | list,
    context: str = "",
    max_records: int = 2000,
    keep: str = "head",
) -> str:
    """Format data as a JSON string with a truncation envelope.

    Args:
        data: Either a bare list of records, or a dict payload (already
            carrying its own metadata) to merge in as-is — capping only
            applies to list ``data``; a dict is passed through unchanged
            aside from ``retrieved_at``.
        context: Optional human-readable context string.
        max_records: Cap on the number of records embedded (default 2000,
            matching the repo-wide convention) when ``data`` is a list. A
            long archive listing or multi-bulletin pull can otherwise
            flood the model's context.
        keep: Which end of a list ``data`` to keep when truncating —
            "head" (default) for sources already ordered newest-first (or
            order-unspecified, matching how each tool's own ``limit``
            already truncates), or "tail" for oldest-first sources (e.g.
            ATCF f-deck fixes) so the most recent records survive
            truncation.
    """
    wrapper: dict = {}
    if context:
        wrapper["context"] = context

    if isinstance(data, list):
        total = len(data)
        truncated = total > max_records
        if truncated:
            records = data[-max_records:] if keep == "tail" else data[:max_records]
        else:
            records = data
        wrapper["truncated"] = truncated
        wrapper["record_count"] = len(records)
        wrapper["total_count"] = total
        if truncated:
            which = "most recent" if keep == "tail" else "first"
            wrapper["hint"] = (
                f"Showing the {which} {len(records)} of {total} records. "
                "Narrow your query (a smaller limit, a specific month/day, "
                "or a storm_id filter) or increase max_records for more."
            )
        wrapper["data"] = records
    else:
        wrapper.update(data)

    wrapper["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return json.dumps(wrapper, indent=2)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def handle_recon_error(e: Exception, context: str = "") -> str:
    """Format an exception into a user-friendly error message.

    Args:
        e: The exception to handle.
        context: Optional context about what operation was being attempted.

    Returns:
        User-friendly error message string.
    """
    import httpx

    prefix = f"Error during {context}: " if context else "Error: "

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"{prefix}Resource not found (HTTP 404). "
                "The requested data may not exist for the specified "
                "year, basin, or storm. Check that the year has "
                "reconnaissance data available."
            )
        return (
            f"{prefix}HTTP {status}: {e.response.reason_phrase}. "
            "The NHC server may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"{prefix}Request timed out. The NHC archive server can be slow. "
            "Please try again."
        )

    if isinstance(e, ValueError):
        return f"{prefix}{e}"

    return f"{prefix}{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# SFMR utilities — haversine, NetCDF parsing, radial wind profile
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine(
    lat1: float,
    lon1: float,
    lat2: float | list | object,
    lon2: float | list | object,
) -> float | object:
    """Compute great-circle distance(s) in km using the haversine formula.

    Accepts scalars or numpy arrays for lat2/lon2 (vectorized).
    lat1/lon1 are the reference point (scalar).

    Args:
        lat1: Reference latitude (degrees).
        lon1: Reference longitude (degrees).
        lat2: Target latitude(s) (degrees).
        lon2: Target longitude(s) (degrees).

    Returns:
        Distance(s) in km. Scalar if inputs are scalar, array otherwise.
    """
    rlat1 = math.radians(lat1)
    rlon1 = math.radians(lon1)

    # Check if numpy arrays
    try:
        import numpy as np

        if isinstance(lat2, np.ndarray):
            rlat2 = np.radians(lat2)
            rlon2 = np.radians(lon2)
            dlat = rlat2 - rlat1
            dlon = rlon2 - rlon1
            a = (
                np.sin(dlat / 2) ** 2
                + math.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
            )
            return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(a))
    except ImportError:
        pass

    # Scalar path
    rlat2 = math.radians(float(lat2))
    rlon2 = math.radians(float(lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def parse_sfmr_netcdf(filepath: str | Path) -> dict:
    """Parse an AOML SFMR NetCDF file and extract key variables.

    Args:
        filepath: Path to the .nc file.

    Returns:
        Dict with keys: 'datetime' (array of datetime objects),
        'lat', 'lon', 'sws' (surface wind speed, m/s),
        'srr' (surface rain rate, mm/hr) — all as numpy arrays,
        plus 'metadata' dict with global attributes.
    """
    import numpy as np
    from netCDF4 import Dataset

    ds = Dataset(str(filepath), "r")
    try:
        # Variable names can vary — try common names
        def _find_var(ds, candidates):
            for name in candidates:
                if name in ds.variables:
                    return ds.variables[name][:]
            return None

        date_var = _find_var(ds, ["DATE", "date", "Date"])
        time_var = _find_var(ds, ["TIME", "time", "Time"])
        lat = _find_var(ds, ["LAT", "lat", "Lat", "latitude"])
        lon = _find_var(ds, ["LON", "lon", "Lon", "longitude"])
        sws = _find_var(ds, ["SWS", "sws", "SurfaceWindSpeed", "surface_wind_speed"])
        srr = _find_var(ds, ["SRR", "srr", "SurfaceRainRate", "surface_rain_rate"])

        if lat is None or lon is None or sws is None:
            raise ValueError(
                f"Required variables not found. Available: {list(ds.variables.keys())}"
            )

        # Build datetime array from DATE (YYYYMMDD int) and TIME (HHMMSS float/int)
        datetimes = []
        if date_var is not None and time_var is not None:
            for d, t in zip(date_var, time_var):
                d_int = int(d)
                t_int = int(round(float(t)))
                year = d_int // 10000
                month = (d_int % 10000) // 100
                day = d_int % 100
                hour = t_int // 10000
                minute = (t_int % 10000) // 100
                second = t_int % 100
                try:
                    dt = datetime(
                        year, month, day, hour, minute, second, tzinfo=timezone.utc
                    )
                    datetimes.append(dt)
                except ValueError:
                    datetimes.append(None)
        else:
            datetimes = [None] * len(lat)

        # Extract metadata
        metadata = {}
        for attr in ds.ncattrs():
            try:
                metadata[attr] = str(ds.getncattr(attr))
            except Exception:
                pass

        # Convert masked arrays to regular arrays, filling masked with NaN
        lat_arr = np.ma.filled(lat, np.nan).astype(float)
        lon_arr = np.ma.filled(lon, np.nan).astype(float)
        sws_arr = np.ma.filled(sws, np.nan).astype(float)
        srr_arr = (
            np.ma.filled(srr, np.nan).astype(float)
            if srr is not None
            else np.full(len(lat_arr), np.nan)
        )

        return {
            "datetime": datetimes,
            "lat": lat_arr,
            "lon": lon_arr,
            "sws": sws_arr,
            "srr": srr_arr,
            "metadata": metadata,
            "n_obs": len(lat_arr),
        }
    finally:
        ds.close()


def parse_atcf_best_track(text: str) -> list[dict]:
    """Parse ATCF b-deck best track text into a list of track points.

    Args:
        text: Raw b-deck file content.

    Returns:
        List of dicts with 'datetime' (datetime obj), 'lat', 'lon',
        'max_wind_kt', 'min_slp_mb'.
    """
    track = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        fields = [f.strip() for f in line.split(",")]
        if len(fields) < 8:
            continue

        # Field 2: YYYYMMDDHH
        date_str = fields[2].strip()
        if len(date_str) < 10:
            continue
        try:
            dt = datetime.strptime(date_str[:10], "%Y%m%d%H")
            dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        # Fields 6,7: lat/lon in tenths with hemisphere
        try:
            lat, lon = parse_atcf_latlon(fields[6], fields[7])
        except (ValueError, IndexError):
            continue

        # Field 8: max sustained wind (kt)
        max_wind = None
        if len(fields) > 8 and fields[8]:
            try:
                max_wind = int(fields[8])
            except ValueError:
                pass

        # Field 9: min SLP (mb)
        min_slp = None
        if len(fields) > 9 and fields[9]:
            try:
                min_slp = int(fields[9])
            except ValueError:
                pass

        track.append(
            {
                "datetime": dt,
                "lat": lat,
                "lon": lon,
                "max_wind_kt": max_wind,
                "min_slp_mb": min_slp,
            }
        )

    # Sort by datetime
    track.sort(key=lambda p: p["datetime"])
    return track


def interpolate_track_position(
    track: list[dict], target_time: datetime
) -> tuple[float, float] | None:
    """Linearly interpolate a best track to a target time.

    Args:
        track: Sorted list of track dicts (from parse_atcf_best_track).
        target_time: Target datetime (UTC).

    Returns:
        (lat, lon) tuple, or None if target_time is outside track range.
    """
    if not track:
        return None

    # Ensure target_time is tz-aware
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)

    # Clamp to track bounds
    if target_time <= track[0]["datetime"]:
        return track[0]["lat"], track[0]["lon"]
    if target_time >= track[-1]["datetime"]:
        return track[-1]["lat"], track[-1]["lon"]

    # Find bracketing points
    for i in range(len(track) - 1):
        t0 = track[i]["datetime"]
        t1 = track[i + 1]["datetime"]
        if t0 <= target_time <= t1:
            dt_total = (t1 - t0).total_seconds()
            if dt_total == 0:
                return track[i]["lat"], track[i]["lon"]
            frac = (target_time - t0).total_seconds() / dt_total
            lat = track[i]["lat"] + frac * (track[i + 1]["lat"] - track[i]["lat"])
            lon = track[i]["lon"] + frac * (track[i + 1]["lon"] - track[i]["lon"])
            return lat, lon

    return None


def compute_radial_wind_profile(
    sfmr_data: dict,
    track: list[dict],
    bin_size_km: float = 5.0,
    max_radius_km: float = 500.0,
) -> list[dict]:
    """Bin SFMR surface wind speed by radial distance from storm center.

    For each valid SFMR observation, interpolates the best track to get
    the storm center position, computes haversine distance, and bins
    by radius.

    Args:
        sfmr_data: Output of parse_sfmr_netcdf().
        track: Output of parse_atcf_best_track().
        bin_size_km: Radial bin width in km (default 5).
        max_radius_km: Maximum radius to include (default 500).

    Returns:
        List of dicts, one per bin, with keys: 'radius_min_km',
        'radius_max_km', 'mean_wind_ms', 'max_wind_ms', 'min_wind_ms',
        'samples'.
    """
    import numpy as np

    datetimes = sfmr_data["datetime"]
    lats = sfmr_data["lat"]
    lons = sfmr_data["lon"]
    sws = sfmr_data["sws"]

    # Build arrays of (radius, wind_speed) for valid observations
    radii = []
    winds = []

    for i in range(len(lats)):
        # Skip invalid observations
        if np.isnan(lats[i]) or np.isnan(lons[i]) or np.isnan(sws[i]):
            continue
        if sws[i] < 0:
            continue
        if datetimes[i] is None:
            continue

        center = interpolate_track_position(track, datetimes[i])
        if center is None:
            continue

        clat, clon = center
        dist = haversine(clat, clon, lats[i], lons[i])

        if dist <= max_radius_km:
            radii.append(dist)
            winds.append(sws[i])

    if not radii:
        return []

    radii = np.array(radii)
    winds = np.array(winds)

    # Bin by radius
    n_bins = int(max_radius_km / bin_size_km)
    bins: list[dict] = []

    for b in range(n_bins):
        r_min = b * bin_size_km
        r_max = (b + 1) * bin_size_km
        mask = (radii >= r_min) & (radii < r_max)
        count = int(np.sum(mask))

        if count == 0:
            continue

        bin_winds = winds[mask]
        bins.append(
            {
                "radius_min_km": r_min,
                "radius_max_km": r_max,
                "mean_wind_ms": round(float(np.mean(bin_winds)), 1),
                "max_wind_ms": round(float(np.max(bin_winds)), 1),
                "min_wind_ms": round(float(np.min(bin_winds)), 1),
                "samples": count,
            }
        )

    return bins


def cleanup_temp_file(filepath: Path | str | None) -> None:
    """Remove a temporary file. Safe to call with None."""
    if filepath is None:
        return
    try:
        os.unlink(str(filepath))
    except OSError:
        pass
