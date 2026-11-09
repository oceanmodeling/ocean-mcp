"""Unit tests for ww3_mcp.utils — parsers, helpers, and formatters."""

from __future__ import annotations

from pathlib import Path

import pytest

from ww3_mcp.models import NDBC_HISTORICAL_MISSING_CODES
from ww3_mcp.utils import (
    denormalize_lon,
    format_wave_observation_table,
    handle_ww3_error,
    haversine,
    normalize_lon,
    parse_ndbc_historical,
    parse_ndbc_realtime,
    parse_ndbc_stations_xml,
    compute_validation_stats,
    summarize_values,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture_exact(name: str) -> str:
    """Read a fixture without newline translation (keeps CRLF line endings)."""
    with open(FIXTURES_DIR / name, encoding="ascii", newline="") as f:
        return f.read()


def by_time(records: list[dict]) -> dict[str, dict]:
    """Index parsed records by timestamp (last row wins on duplicates)."""
    return {r["timestamp"]: r for r in records}


# ============================================================================
# Haversine
# ============================================================================


class TestHaversine:
    """Tests for the haversine distance function."""

    def test_same_point_returns_zero(self):
        """Haversine distance between identical points should be zero."""
        assert haversine(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance_nyc_to_london(self):
        """NYC to London should be approximately 5570 km."""
        dist = haversine(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5550 < dist < 5600

    def test_equator_one_degree(self):
        """One degree of longitude on the equator is about 111 km."""
        dist = haversine(0.0, 0.0, 0.0, 1.0)
        assert 110 < dist < 112

    def test_symmetry(self):
        """Haversine should be symmetric."""
        d1 = haversine(35.0, -75.0, 40.0, -74.0)
        d2 = haversine(40.0, -74.0, 35.0, -75.0)
        assert abs(d1 - d2) < 0.001


# ============================================================================
# Longitude normalization
# ============================================================================


class TestLonNormalization:
    """Tests for longitude conversion between -180..180 and 0..360."""

    def test_normalize_negative_longitude(self):
        """Negative longitude should be converted to 0-360 range."""
        assert normalize_lon(-75.0) == 285.0

    def test_normalize_positive_longitude(self):
        """Positive longitude in 0-180 range should stay the same."""
        assert normalize_lon(120.0) == 120.0

    def test_normalize_zero(self):
        """Zero longitude should stay zero."""
        assert normalize_lon(0.0) == 0.0

    def test_normalize_minus_180(self):
        """Longitude -180 should become 180."""
        assert normalize_lon(-180.0) == 180.0

    def test_denormalize_above_180(self):
        """Longitude above 180 in 0-360 should be converted to negative."""
        assert denormalize_lon(285.0) == -75.0

    def test_denormalize_below_180(self):
        """Longitude below 180 should stay the same."""
        assert denormalize_lon(120.0) == 120.0

    def test_roundtrip(self):
        """Normalize then denormalize should return the original value."""
        original = -75.5
        assert abs(denormalize_lon(normalize_lon(original)) - original) < 0.001


# ============================================================================
# NDBC realtime text parser
# ============================================================================


class TestParseNdbcRealtime:
    """Tests for NDBC realtime2 text file parsing."""

    def test_parse_fixture_file(self):
        """Parsing the fixture file should return 5 records."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        assert len(records) == 5

    def test_parse_extracts_wave_height(self):
        """Each record should have a numeric WVHT field."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        for r in records:
            assert r["WVHT"] is not None
            assert isinstance(r["WVHT"], float)

    def test_parse_missing_values_become_none(self):
        """Values of 'MM' in NDBC data should become None."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        # VIS, PTDY, TIDE are all MM in fixture
        for r in records:
            assert r.get("VIS") is None
            assert r.get("PTDY") is None

    def test_parse_builds_timestamps(self):
        """Parser should create timestamp strings from date components."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        assert records[0]["timestamp"] == "2026-03-04 12:00"

    def test_parse_empty_text_returns_empty(self):
        """Parsing empty text should return an empty list."""
        assert parse_ndbc_realtime("") == []

    def test_parse_header_only_returns_empty(self):
        """Parsing text with only headers and no data should return empty."""
        text = "#YY  MM DD hh mm WDIR\n#yr  mo dy hr mn deg\n"
        assert parse_ndbc_realtime(text) == []


# ============================================================================
# NDBC historical (annual) text parser — real excerpts, see
# fixtures/ndbc_history_SOURCES.md for the source files and their SHA-256
# ============================================================================


class TestParseNdbcHistorical:
    """Tests for the historical-file parser and its missing-value codes."""

    def test_every_missing_code_becomes_none(self):
        """Each column's 9-filled code (real 41009h2024 lines) parses to None."""
        records, _ = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h2024_excerpt.txt")
        )
        rows = by_time(records)
        all_missing = rows["2024-01-15 08:00"]  # source line 2067
        for col in NDBC_HISTORICAL_MISSING_CODES:
            if col == "WTMP":
                continue  # WTMP is valid (22.5) on this line
            assert all_missing[col] is None, col
        assert all_missing["WTMP"] == 22.5
        assert rows["2024-01-01 11:20"]["WTMP"] is None  # source line 71: 999.0

    def test_genuine_values_near_a_code_are_kept(self):
        """Real values that look like codes (999.0 hPa, 99 degT, 9.09 s) are kept."""
        records, _ = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h2024_excerpt.txt")
        )
        rows = by_time(records)
        assert rows["2024-02-05 18:40"]["PRES"] == 999.9
        assert rows["2024-10-10 02:00"]["PRES"] == 999.0
        assert rows["2024-10-10 02:10"]["PRES"] == 999.0
        assert rows["2024-01-05 19:40"]["WDIR"] == 99
        assert rows["2024-01-11 21:00"]["WDIR"] == 9
        assert rows["2024-01-06 14:10"]["MWD"] == 99
        assert rows["2024-01-02 05:40"]["WSPD"] == 9.9
        assert rows["2024-01-02 15:50"]["DEWP"] == 9.0
        assert rows["2024-10-10 08:10"]["DPD"] == 9.09
        assert rows["2024-10-10 08:10"]["WVHT"] == 6.32

    def test_no_code_survives_as_a_number(self):
        """No parsed WVHT equals 99.0 and no PRES equals 9999.0."""
        records, _ = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h2024_excerpt.txt")
        )
        assert all(r["WVHT"] != 99.0 for r in records)
        assert all(r["PRES"] != 9999.0 for r in records)

    def test_missing_counts_and_units_from_the_file(self):
        """Missing values are counted per column; units come from the units line."""
        records, info = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h2024_excerpt.txt")
        )
        assert info["data_rows"] == len(records) == 16
        assert info["malformed_rows_skipped"] == 0
        assert info["missing_counts"]["WVHT"] == 8
        assert info["missing_counts"]["PRES"] == 1
        assert info["missing_counts"]["WTMP"] == 1
        assert info["missing_counts"]["VIS"] == 16
        assert info["units"]["WVHT"] == "m"
        assert info["units"]["PRES"] == "hPa"
        assert info["units_source"] == "the file's units line"

    def test_first_data_row_is_kept(self):
        """The first data row is data, not a second header line."""
        records, info = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h2024_excerpt.txt")
        )
        assert info["header_lines"] == 2
        assert records[0]["timestamp"] == "2024-01-01 00:00"

    def test_1998_format_two_digit_year_old_names_crlf(self):
        """1998: one header line, YY=98, WD/BAR, no minute column, CRLF endings."""
        records, info = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h1998_excerpt.txt")
        )
        assert info["header_lines"] == 1
        assert info["two_digit_year"] is True
        assert info["minute_column"] is False
        assert info["renamed"] == {"WD": "WDIR", "BAR": "PRES"}
        assert len(records) == 5
        assert records[0]["timestamp"] == "1998-01-01 00:00"
        assert records[0]["WVHT"] == 1.76  # first data row kept
        assert records[1]["timestamp"] == "1998-01-01 00:00"  # two rows per hour
        missing = records[2]
        assert missing["WVHT"] is None and missing["PRES"] is None
        assert missing["WDIR"] is None and missing["WSPD"] is None
        assert records[4]["PRES"] == 999.9  # genuine pressure kept
        assert info["units_source"].startswith("NDBC units line")

    @pytest.mark.parametrize(
        ("fixture", "minute_column", "first", "second"),
        [
            (
                "ndbc_history_41009h2003_excerpt.txt",
                False,
                "2003-01-01 00:00",
                "2003-01-12 03:00",
            ),
            (
                "ndbc_history_41009h2006_excerpt.txt",
                True,
                "2006-01-01 00:00",
                "2006-01-15 10:00",
            ),
        ],
    )
    def test_yyyy_header_formats(self, fixture, minute_column, first, second):
        """2003 and 2006: YYYY header, with and without a minute column."""
        records, info = parse_ndbc_historical(read_fixture_exact(fixture))
        assert info["renamed"]["YYYY"] == "YY"
        assert info["minute_column"] is minute_column
        assert [r["timestamp"] for r in records] == [first, second]
        assert records[1]["WVHT"] is None
        assert records[0]["WVHT"] is not None

    def test_realtime_mm_is_still_missing(self):
        """An 'MM' field (realtime convention) is also treated as missing."""
        records, info = parse_ndbc_historical(
            (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        )
        assert len(records) == 5
        assert all(r["VIS"] is None for r in records)
        assert info["missing_counts"]["VIS"] == 5

    def test_unrecognised_header_raises(self):
        """A header without the date columns or WVHT is a clear ValueError."""
        with pytest.raises(ValueError, match="Unrecognised NDBC historical file"):
            parse_ndbc_historical("STN DATE VALUE\n41009 20240101 1.2\n")

    def test_malformed_rows_are_counted_and_skipped(self):
        """A row with the wrong number of fields is skipped and counted."""
        text = read_fixture_exact("ndbc_history_41009h2006_excerpt.txt")
        records, info = parse_ndbc_historical(text + "2006 01 15 10\n")
        assert len(records) == 2
        assert info["malformed_rows_skipped"] == 1


class TestSummarizeValues:
    """Tests for summarize_values."""

    def test_summary_over_all_valid_rows(self):
        """Max, its time, count at max, and mean are taken over every valid row."""
        records, _ = parse_ndbc_historical(
            read_fixture_exact("ndbc_history_41009h2024_excerpt.txt")
        )
        s = summarize_values(records, "WVHT")
        valid = [0.47, 0.94, 1.39, 2.08, 1.35, 3.69, 6.32, 0.68]  # fixture WVHT
        assert s["valid"] == len(valid) == 8
        assert s["max"] == 6.32
        assert s["max_time"] == "2024-10-10 08:10"
        assert s["max_count"] == 1
        assert s["min"] == 0.47
        assert s["mean"] == round(sum(valid) / len(valid), 3)

    def test_no_valid_values(self):
        """With no valid value every statistic is None and the count is 0."""
        s = summarize_values([{"WVHT": None, "timestamp": "2024-01-01 00:00"}], "WVHT")
        assert s["valid"] == 0
        assert s["max"] is None and s["mean"] is None and s["max_time"] is None


# ============================================================================
# NDBC stations XML parser
# ============================================================================


class TestParseNdbcStationsXml:
    """Tests for NDBC active stations XML parsing."""

    def test_parse_fixture_file(self):
        """Parsing the fixture XML should return 5 stations."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        assert len(stations) == 5

    def test_parse_extracts_station_ids(self):
        """Each station should have an 'id' field."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        ids = {s["id"] for s in stations}
        assert "41025" in ids
        assert "46042" in ids

    def test_parse_extracts_coordinates(self):
        """Each station should have numeric lat/lon fields."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        for s in stations:
            assert isinstance(s["lat"], float)
            assert isinstance(s["lon"], float)

    def test_parse_invalid_xml_returns_empty(self):
        """Invalid XML should return an empty list."""
        assert parse_ndbc_stations_xml("not xml") == []

    def test_parse_extracts_name(self):
        """Stations should have name attributes."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        diamond = next(s for s in stations if s["id"] == "41025")
        assert "Diamond Shoals" in diamond["name"]


# ============================================================================
# Validation statistics
# ============================================================================


class TestComputeValidationStats:
    """Tests for the compute_validation_stats function."""

    def test_perfect_forecast(self):
        """Identical forecast and observed should give zero error metrics."""
        stats = compute_validation_stats([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert stats["bias"] == 0.0
        assert stats["rmse"] == 0.0
        assert stats["mae"] == 0.0
        assert stats["n"] == 3

    def test_constant_bias(self):
        """A constant offset should be reflected in bias."""
        stats = compute_validation_stats([2.0, 3.0, 4.0], [1.0, 2.0, 3.0])
        assert abs(stats["bias"] - 1.0) < 0.001

    def test_empty_arrays_return_none(self):
        """Empty input should return None metrics and n=0."""
        stats = compute_validation_stats([], [])
        assert stats["n"] == 0
        assert stats["bias"] is None

    def test_correlation_for_perfect_linear(self):
        """Perfect linear correlation should give R close to 1."""
        stats = compute_validation_stats([2.0, 4.0, 6.0], [1.0, 2.0, 3.0])
        assert stats["correlation"] is not None
        assert stats["correlation"] > 0.99


# ============================================================================
# Formatters
# ============================================================================


class TestFormatWaveObservationTable:
    """Tests for the wave observation table formatter."""

    def test_format_returns_markdown_table(self):
        """Formatter should produce a markdown table with headers."""
        records = [
            {
                "timestamp": "2026-03-04 12:00",
                "WVHT": 1.5,
                "DPD": 8.0,
                "APD": 5.5,
                "MWD": 200,
                "WSPD": 5.1,
                "WDIR": 210,
            },
        ]
        result = format_wave_observation_table(records, station_id="41025")
        assert "| Time (UTC) |" in result
        assert "41025" in result

    def test_format_empty_records(self):
        """Formatter with no records should show a 'no data' message."""
        result = format_wave_observation_table([], station_id="41025")
        assert "No observation data" in result

    def test_format_handles_none_values(self):
        """Formatter should show '—' for None values."""
        records = [
            {
                "timestamp": "2026-03-04 12:00",
                "WVHT": None,
                "DPD": None,
                "APD": None,
                "MWD": None,
                "WSPD": None,
                "WDIR": None,
            },
        ]
        result = format_wave_observation_table(records)
        assert "—" in result


class TestHandleWw3ErrorGrib:
    """handle_ww3_error turns the opaque ecCodes failure into setup guidance."""

    def test_eccodes_error_gives_install_guidance(self):
        msg = handle_ww3_error(RuntimeError("Cannot find the ecCodes library"))
        assert "ecCodes" in msg
        assert "conda" in msg
        # points the user at the GRIB-free fallback tools
        assert "ww3_get_buoy" in msg

    def test_non_grib_error_is_unaffected(self):
        msg = handle_ww3_error(ValueError("bad latitude"))
        assert "ecCodes" not in msg
        assert "bad latitude" in msg
