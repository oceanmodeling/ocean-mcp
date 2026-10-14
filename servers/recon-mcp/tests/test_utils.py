"""Unit tests for recon_mcp.utils parsers — no network access needed."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from recon_mcp.utils import (
    _decode_hdob_d_value,
    _decode_hdob_pressure,
    _parse_atcf_fix_latlon,
    _parse_hdob_latlon,
    _vdm_eye_diameter,
    _vdm_fix_time,
    format_json_response,
    format_tabular_data,
    parse_atcf_fix_record,
    parse_atcf_latlon,
    parse_directory_listing,
    parse_hdob_message,
    parse_vdm_message,
)


def _fixture(name: str) -> str:
    """Load a text fixture (real archived bulletins) from tests/fixtures."""
    return (Path(__file__).parent / "fixtures" / name).read_text()


# ---------------------------------------------------------------------------
# Directory listing parser
# ---------------------------------------------------------------------------

SAMPLE_DIRECTORY_HTML = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html><head><title>Index of /archive/recon/2024/AHONT1</title></head>
<body><h1>Index of /archive/recon/2024/AHONT1</h1>
<table>
<tr><th><a href="?C=N;O=D">Name</a></th></tr>
<tr><td><a href="../">Parent Directory</a></td></tr>
<tr><td><a href="AHONT1-KNHC.202410071200.txt">AHONT1-KNHC.202410071200.txt</a></td><td>2024-10-07 12:05</td><td>2.1K</td></tr>
<tr><td><a href="AHONT1-KNHC.202410071230.txt">AHONT1-KNHC.202410071230.txt</a></td><td>2024-10-07 12:35</td><td>1.8K</td></tr>
<tr><td><a href="AHONT1-KNHC.202410071300.txt">AHONT1-KNHC.202410071300.txt</a></td><td>2024-10-07 13:05</td><td>2.3K</td></tr>
</table></body></html>
"""


def test_parse_directory_listing():
    entries = parse_directory_listing(SAMPLE_DIRECTORY_HTML)
    assert len(entries) == 3
    assert entries[0]["filename"] == "AHONT1-KNHC.202410071200.txt"
    assert entries[0]["href"] == "AHONT1-KNHC.202410071200.txt"
    assert entries[2]["filename"] == "AHONT1-KNHC.202410071300.txt"


def test_parse_directory_listing_skips_parent():
    entries = parse_directory_listing(SAMPLE_DIRECTORY_HTML)
    filenames = [e["filename"] for e in entries]
    assert "Parent Directory" not in filenames


def test_parse_directory_listing_empty():
    html = "<html><body>No files</body></html>"
    entries = parse_directory_listing(html)
    assert entries == []


# ---------------------------------------------------------------------------
# HDOB parser
# ---------------------------------------------------------------------------

# Data lines from real archived bulletins, one per D-value encoding: a plain
# positive D-value (2026 G-IV), the spec's D + 5000 (4825 -> -175) and
# 5000 + |D| (5002 -> -2), each consistent with the standard-atmosphere
# D-value from that line's pressure and height.
HIGH_ALTITUDE_HDOB = """URPN15 KNHC 021855
AF309 WXWXE 260902173510309    HDOB 08 20260902
184600 3716N 12455W 3598 08288 0364 -230 //// 286050 051 /// /// 05
235100 4349N 14925W 2980 09038 4825 -503 //// 266051 052 002 000 01
215700 3354N 09730W 4099 07009 5002 -315 -491 345092 093 /// /// 03
$$
"""


class TestParseHdob:
    """parse_hdob_message against real bulletins (NHC HDOB spec, 13 fields)."""

    def test_header(self):
        """The mission line gives the aircraft, ob number and date."""
        header = parse_hdob_message(_fixture("hdob_bulletin.txt"))["header"]
        assert header["wmo_header"] == "URNT15 KNHC 090710"
        assert header["mission"] == "AF300 1814A MILTON"
        assert header["aircraft"] == "AF300"
        assert header["ob_number"] == 23
        assert header["date"] == "20241009"

    def test_every_data_line_is_an_observation(self):
        """All 20 data lines of the Milton bulletin decode."""
        obs = parse_hdob_message(_fixture("hdob_bulletin.txt"))["observations"]
        assert len(obs) == 20
        assert [o["time"] for o in obs[:2]] == ["070200", "070230"]

    def test_eye_record(self):
        """070200: Milton's eye, 907.0 mb extrapolated (the VDM fix says 910)."""
        o = parse_hdob_message(_fixture("hdob_bulletin.txt"))["observations"][0]
        assert o["date"] == "20241009"
        assert o["lat"] == pytest.approx(24.0)
        assert o["lon"] == pytest.approx(-85.7)
        assert o["static_pressure_mb"] == pytest.approx(697.8)
        assert o["geopotential_alt_m"] == 2308
        assert o["extrapolated_slp_mb"] == pytest.approx(907.0)
        assert o["d_value_m"] is None
        assert o["temp_c"] == pytest.approx(19.7)
        assert o["dewpoint_c"] == pytest.approx(4.2)
        assert (o["fl_wind_dir_deg"], o["fl_wind_speed_kt"]) == (198, 6)
        assert o["qc_flags"] == "00"

    def test_eyewall_record(self):
        """070400: 152 kt SFMR peak and 53 mm/h rain in the eyewall."""
        o = parse_hdob_message(_fixture("hdob_bulletin.txt"))["observations"][4]
        assert (o["fl_wind_dir_deg"], o["fl_wind_speed_kt"]) == (322, 129)
        assert o["peak_fl_wind_kt"] == 135
        assert o["sfmr_sfc_wind_kt"] == 152
        assert o["sfmr_rain_rate_mmhr"] == 53
        assert o["extrapolated_slp_mb"] == pytest.approx(939.2)

    def test_date_advances_past_midnight(self):
        """Beryl 2012: the header date is the first line's; 000000 is the next day."""
        obs = parse_hdob_message(_fixture("hdob_midnight.txt"))["observations"]
        assert (obs[0]["date"], obs[0]["time"]) == ("20120527", "235530")
        assert (obs[8]["date"], obs[8]["time"]) == ("20120527", "235930")
        assert (obs[9]["date"], obs[9]["time"]) == ("20120528", "000000")
        assert obs[-1]["date"] == "20120528"

    def test_leading_one_dropped_pressures(self):
        """Pressures of 1000 mb and up drop their leading 1 ('0078' -> 1007.8)."""
        o = parse_hdob_message(_fixture("hdob_midnight.txt"))["observations"][0]
        assert o["static_pressure_mb"] == pytest.approx(843.4)
        assert o["extrapolated_slp_mb"] == pytest.approx(1007.8)

    def test_slash_missing_values(self):
        """'///' fields decode to None; the QC flags are kept."""
        o = parse_hdob_message(_fixture("hdob_midnight.txt"))["observations"][14]
        assert o["time"] == "000230"
        assert o["sfmr_sfc_wind_kt"] is None
        assert o["sfmr_rain_rate_mmhr"] is None
        assert o["qc_flags"] == "03"

    def test_999_missing_code(self):
        """The spec's own sample line codes a missing rain rate as 999."""
        text = (
            "URNT15 KNHC 281426\n"
            "AF302 1712A KATRINA            HDOB 41 20050928\n"
            "142030 2608N 08756W 7093 03047 9333 +192 +134 133083 089 080 999 00\n"
        )
        o = parse_hdob_message(text)["observations"][0]
        assert o["sfmr_sfc_wind_kt"] == 80
        assert o["sfmr_rain_rate_mmhr"] is None
        assert o["extrapolated_slp_mb"] == pytest.approx(933.3)

    def test_d_values_above_550_mb(self):
        """Above 550 mb the fifth field is a D-value, in either negative encoding."""
        obs = parse_hdob_message(HIGH_ALTITUDE_HDOB)["observations"]
        assert [o["d_value_m"] for o in obs] == [364, -175, -2]
        assert all(o["extrapolated_slp_mb"] is None for o in obs)
        assert obs[1]["static_pressure_mb"] == pytest.approx(298.0)
        assert obs[1]["dewpoint_c"] is None
        assert obs[2]["temp_c"] == pytest.approx(-31.5)

    def test_lines_without_mission_date_are_skipped(self):
        """Without the mission line there is no date, so no observations."""
        text = "URNT15 KNHC 090710\n070200 2400N 08542W 6978 02308 9070 +197 +042 198006 030 053 001 00\n"
        assert parse_hdob_message(text)["observations"] == []


class TestHdobFieldDecoders:
    """The small HDOB field decoders."""

    def test_pressure(self):
        """Tenths of mb with the leading 1 dropped at 1000 mb and above."""
        assert _decode_hdob_pressure("6965") == pytest.approx(696.5)
        assert _decode_hdob_pressure("9892") == pytest.approx(989.2)
        assert _decode_hdob_pressure("0015") == pytest.approx(1001.5)
        assert _decode_hdob_pressure("1484") == pytest.approx(148.4)  # G-IV
        assert _decode_hdob_pressure("////") is None

    def test_d_value(self):
        """Plain positive, D + 5000 and 5000 + |D| encodings."""
        assert _decode_hdob_d_value("0364") == 364
        assert _decode_hdob_d_value("4825") == -175
        assert _decode_hdob_d_value("5002") == -2
        assert _decode_hdob_d_value("////") is None

    def test_latlon(self):
        """DDMM / DDDMM with hemisphere; off-spec lengths or minutes are None."""
        assert _parse_hdob_latlon("2606N", is_lat=True) == pytest.approx(26.1)
        assert _parse_hdob_latlon("08015W", is_lat=False) == pytest.approx(-80.25)
        assert _parse_hdob_latlon("12345N", is_lat=True) is None
        assert _parse_hdob_latlon("0801W", is_lat=False) is None
        assert _parse_hdob_latlon("2660N", is_lat=True) is None
        assert _parse_hdob_latlon("AB12N", is_lat=True) is None


# ---------------------------------------------------------------------------
# VDM parser
# ---------------------------------------------------------------------------

# Real 2009 training VDM: no storm ID, and the short DD/HHMMZ fix time.
TRAINING_VDM = """URNT12 KWBC 101129
VORTEX DATA MESSAGE
A. 10/1131Z
B. 26 DEG 29 MIN N
   85 DEG 0 MIN W
C. 850 MB 1594 M
D. 5 KT
E. 045 DEG  10 NM
F. 290 DEG   8 KT
G. 045 DEG  12 NM
H. 1019 MB
I. 25 C/1550 M
J. 25 C/1533 M
K. 22 C/NA
L. NA
M. NA
N. 12345/8
O. 1/1 NM
P. NOAA3 WXWXA TRAIN OB 02
   TEST TEST TEST
"""


class TestParseVdm:
    """parse_vdm_message for both archive layouts (2018+ A-U, earlier A-P)."""

    def test_2018_layout(self):
        """Milton 2024-10-09 07:02Z: center, pressure and eye."""
        v = parse_vdm_message(
            _fixture("vdm_bulletin.txt"), issued=datetime(2024, 10, 9, 7, 24)
        )
        assert v["vdm_format"] == "2018"
        assert v["storm_id"] == "AL142024"
        assert v["wmo_header"] == "URNT12 KNHC 090724"
        assert v["fix_time_utc"] == "2024-10-09T07:02:10Z"
        assert (v["center_lat"], v["center_lon"]) == (24.0, -85.71)
        assert (v["std_level_mb"], v["min_height_m"]) == (700, 2285)
        assert v["min_slp_mb"] == 910
        assert v["min_slp_extrapolated"] is False
        assert (v["center_sfc_wind_dir_deg"], v["center_sfc_wind_kt"]) == (160, 24)
        assert v["eye_character"] == "CLOSED"
        assert (v["eye_shape"], v["eye_diameter_nm"]) == ("C8", 8)

    def test_2018_layout_winds_and_remarks(self):
        """Inbound/outbound surface and flight-level winds, temps, remarks."""
        v = parse_vdm_message(_fixture("vdm_bulletin.txt"))
        assert v["max_sfc_wind_inbound_kt"] == 158
        assert (v["max_fl_wind_inbound_dir_deg"], v["max_fl_wind_inbound_kt"]) == (
            132,
            140,
        )
        assert v["max_sfc_wind_outbound_kt"] == 152
        assert (v["max_fl_wind_outbound_dir_deg"], v["max_fl_wind_outbound_kt"]) == (
            322,
            135,
        )
        assert (v["max_fl_temp_outside_c"], v["max_fl_temp_inside_c"]) == (13, 21)
        assert v["observation_line"] == "AF300 1814A MILTON OB 11"
        assert v["remarks"] == "MAX FL WIND 145 KT 121 / 6 NM 05:41:30Z"

    def test_pre_2018_layout(self):
        """Harvey 2017: degree/minute center over two lines, SLP in H, eye in L/M."""
        v = parse_vdm_message(
            _fixture("vdm_bulletin_pre2018.txt"),
            issued=datetime(2017, 8, 25, 10, 17),
        )
        assert v["vdm_format"] == "pre-2018"
        assert v["storm_id"] == "AL092017"
        assert v["fix_time_utc"] == "2017-08-25T09:56:10Z"
        assert v["center_lat"] == pytest.approx(26.1)
        assert v["center_lon"] == pytest.approx(-95.5833, abs=1e-4)
        assert v["min_slp_mb"] == 953
        assert v["max_sfc_wind_inbound_kt"] == 86
        assert (v["max_fl_wind_inbound_dir_deg"], v["max_fl_wind_inbound_kt"]) == (
            232,
            92,
        )
        assert v["eye_character"] == "CLOSED"
        assert v["eye_diameter_nm"] == 11
        assert (v["max_fl_temp_outside_c"], v["max_fl_temp_inside_c"]) == (13, 17)
        # Items this layout does not have.
        assert v["max_sfc_wind_outbound_kt"] is None
        assert v["center_sfc_wind_kt"] is None
        assert v["observation_line"] == "AF305 1709A HARVEY OB 12"
        assert v["remarks"].startswith("MAX FL WIND 96 KT")
        assert "CNTR DROPSONDE SFC WIND 155 / 16 KT" in v["remarks"]

    def test_extrapolated_pressure(self):
        """'EXTRAP 1011 mb' (Bonnie 2010) is 1011 mb, flagged as extrapolated."""
        text = _fixture("vdm_bulletin_pre2018.txt").replace(
            "H. 953 mb", "H. EXTRAP 1011 mb"
        )
        v = parse_vdm_message(text)
        assert v["min_slp_mb"] == 1011
        assert v["min_slp_extrapolated"] is True

    def test_short_time_no_storm_id_and_na(self):
        """2009 training VDM: DD/HHMMZ time, no storm ID, NA items as None."""
        v = parse_vdm_message(TRAINING_VDM, issued=datetime(2009, 7, 10, 11, 29))
        assert v["storm_id"] is None
        assert v["fix_time_utc"] == "2009-07-10T11:31:00Z"
        assert (v["center_lat"], v["center_lon"]) == (
            pytest.approx(26.4833, abs=1e-4),
            -85.0,
        )
        assert v["min_slp_mb"] == 1019
        assert v["eye_character"] is None
        assert v["eye_diameter_nm"] is None
        assert v["remarks"] == "TEST TEST TEST"

    def test_fix_time_without_issue_time_is_raw(self):
        """With no issue time the year and month are unknown: keep item A."""
        assert parse_vdm_message(_fixture("vdm_bulletin.txt"))["fix_time_utc"] == (
            "09/07:02:10Z"
        )

    def test_fix_time_month_and_year_rollover(self):
        """A fix day after the issue day belongs to the previous month."""
        assert _vdm_fix_time("31/23:50:00Z", datetime(2024, 11, 1, 0, 30)) == (
            "2024-10-31T23:50:00Z"
        )
        assert _vdm_fix_time("31/23:50:00Z", datetime(2025, 1, 1, 0, 30)) == (
            "2024-12-31T23:50:00Z"
        )

    def test_eye_diameter(self):
        """Circular and concentric eyes give a diameter; elliptical does not."""
        assert _vdm_eye_diameter("C8") == 8
        assert _vdm_eye_diameter("CO15-30") == 15
        assert _vdm_eye_diameter("E04/33/23") is None
        assert _vdm_eye_diameter(None) is None


# ---------------------------------------------------------------------------
# ATCF f-deck parser
# ---------------------------------------------------------------------------


class TestParseAtcfFix:
    """parse_atcf_fix_record against real NHC f-deck lines (Milton 2024)."""

    def _records(self):
        """Parse the fixture: Milton fixes around the 07Z 9 Oct eye pass."""
        lines = _fixture("fdeck_sample.txt").splitlines()
        return [parse_atcf_fix_record(line) for line in lines]

    def test_aircraft_fix(self):
        """The 0702Z aircraft fix matches the VDM: 24.00N 85.71W, 158 kt, 910 mb."""
        r = self._records()[0]
        assert r["basin"] == "AL"
        assert r["cyclone_num"] == 14
        assert r["datetime"] == "202410090702"
        assert (r["fix_format"], r["fix_type"]) == (50, "AIRC")
        assert r["center_intensity"] == "CI"
        assert r["flagged"] is False
        assert (r["lat"], r["lon"]) == (24.0, -85.71)
        assert (r["max_wind_kt"], r["min_pressure_mb"]) == (158, 910)
        assert r["fix_site"] == "KNHC"

    def test_intensity_only_fix_has_no_position(self):
        """Dropsonde intensity fix: wind only, no lat/lon or pressure."""
        r = self._records()[2]
        assert (r["fix_type"], r["center_intensity"]) == ("DRPS", "I")
        assert (r["lat"], r["lon"]) == (None, None)
        assert (r["max_wind_kt"], r["min_pressure_mb"]) == (116, None)

    def test_all_fixture_records_parse(self):
        """Every line parses; the radar fix carries its site."""
        records = self._records()
        assert all(records)
        assert records[-1]["fix_type"] == "RDRD"
        assert records[-1]["fix_site"] == "KBYX"
        assert (records[-1]["lat"], records[-1]["lon"]) == (24.91, -84.9)

    def test_east_pacific_five_digit_longitude(self):
        """Longitudes of 100 and up have five digits (EP05 2026: 10100W)."""
        line = (
            "EP, 05, 202607131200,  70, ANAL,         CI,  , 1220N, 10100W,"
            "    10, 2,  30, 2, 1009, 2, MEAS,    ,     ,"
        )
        r = parse_atcf_fix_record(line)
        assert (r["lat"], r["lon"]) == (12.2, -101.0)
        assert (r["max_wind_kt"], r["min_pressure_mb"]) == (30, 1009)

    def test_flagged_fix(self):
        """Column 6 'F' marks a fix flagged as bad."""
        line = _fixture("fdeck_sample.txt").splitlines()[0]
        flagged = line.replace("CI,  ,", "CI, F,", 1)
        assert parse_atcf_fix_record(flagged)["flagged"] is True

    def test_blank_or_short_lines(self):
        """Blank and truncated lines are not records."""
        assert parse_atcf_fix_record("") is None
        assert parse_atcf_fix_record("   ") is None
        assert parse_atcf_fix_record("AL, 14, 2024") is None


class TestAtcfFixLatLon:
    """_parse_atcf_fix_latlon: hundredths of a degree, not zero padded."""

    def test_valid(self):
        """Real widths: '800N' (EP21 2026), '9490W', '10512W'."""
        assert _parse_atcf_fix_latlon("800N", is_lat=True) == pytest.approx(8.0)
        assert _parse_atcf_fix_latlon("2557N", is_lat=True) == pytest.approx(25.57)
        assert _parse_atcf_fix_latlon("1250S", is_lat=True) == pytest.approx(-12.5)
        assert _parse_atcf_fix_latlon("9490W", is_lat=False) == pytest.approx(-94.9)
        assert _parse_atcf_fix_latlon("10512W", is_lat=False) == pytest.approx(-105.12)
        assert _parse_atcf_fix_latlon("17000E", is_lat=False) == pytest.approx(170.0)

    def test_rejected(self):
        """Placeholders, wrong hemispheres, garbage and out-of-range values."""
        assert _parse_atcf_fix_latlon("0E", is_lat=False) is None  # placeholder
        assert _parse_atcf_fix_latlon("2557W", is_lat=True) is None
        assert _parse_atcf_fix_latlon("9490N", is_lat=False) is None
        assert _parse_atcf_fix_latlon("9500N", is_lat=True) is None  # > 90
        assert _parse_atcf_fix_latlon("18500W", is_lat=False) is None  # > 180
        assert _parse_atcf_fix_latlon("123456W", is_lat=False) is None
        assert _parse_atcf_fix_latlon("202308061200", is_lat=False) is None
        assert _parse_atcf_fix_latlon("AB12N", is_lat=True) is None
        assert _parse_atcf_fix_latlon("", is_lat=True) is None


# ---------------------------------------------------------------------------
# ATCF lat/lon parser
# ---------------------------------------------------------------------------


def test_parse_atcf_latlon_basic():
    lat, lon = parse_atcf_latlon("281N", "0940W")
    assert lat == pytest.approx(28.1)
    assert lon == pytest.approx(-94.0)


def test_parse_atcf_latlon_southern():
    lat, lon = parse_atcf_latlon("125S", "1700E")
    assert lat == pytest.approx(-12.5)
    assert lon == pytest.approx(170.0)


# The two tests above guard the b-deck best-track parser, which is TENTHS of
# a degree. The f-deck fix parser must not reuse it: f-deck is hundredths.


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


def test_format_tabular_data():
    data = [
        {"name": "Milton", "wind": 150},
        {"name": "Helene", "wind": 120},
    ]
    columns = [("name", "Name"), ("wind", "Wind (kt)")]
    result = format_tabular_data(data, columns, title="Test")

    assert "## Test" in result
    assert "| Name | Wind (kt) |" in result
    assert "| Milton | 150 |" in result
    assert "2 records returned" in result


def test_format_tabular_data_missing_value_is_dash():
    """A None cell (e.g. a '///' SFMR wind) renders as an em dash, not 'None'."""
    data = [{"name": "Milton", "wind": None}]
    columns = [("name", "Name"), ("wind", "Wind (kt)")]
    result = format_tabular_data(data, columns, title="Test")

    assert "| Milton | — |" in result
    assert "None" not in result


def test_format_tabular_data_empty():
    result = format_tabular_data([], [("a", "A")], title="Empty")
    assert "0 records returned" in result


def test_format_tabular_data_under_cap_not_truncated():
    """When data fits under max_rows, no truncation footer is added."""
    data = [{"name": f"Storm{i}"} for i in range(5)]
    result = format_tabular_data(data, [("name", "Name")], max_rows=10)
    assert "5 records returned" in result
    assert "truncated" not in result.lower()


def test_format_tabular_data_max_rows_keeps_head_by_default():
    """keep='head' (the default) keeps the first max_rows rows."""
    data = [{"name": f"Storm{i}"} for i in range(10)]
    result = format_tabular_data(data, [("name", "Name")], max_rows=3)
    assert "Storm0" in result
    assert "Storm1" in result
    assert "Storm2" in result
    assert "Storm9" not in result
    assert "Showing the first 3 of 10 records" in result
    assert "(truncated)" in result


def test_format_tabular_data_max_rows_keeps_tail_when_requested():
    """keep='tail' keeps the most recent (last) max_rows rows."""
    data = [{"name": f"Storm{i}"} for i in range(10)]
    result = format_tabular_data(data, [("name", "Name")], max_rows=3, keep="tail")
    assert "Storm7" in result
    assert "Storm8" in result
    assert "Storm9" in result
    assert "Storm0" not in result
    assert "Showing the most recent 3 of 10 records" in result


# ---------------------------------------------------------------------------
# format_json_response — truncation envelope
# ---------------------------------------------------------------------------


def test_format_json_response_list_not_truncated():
    """A list under max_records carries truncated=False and matching counts."""
    data = [{"i": i} for i in range(3)]
    result = json.loads(format_json_response(data, max_records=10))

    assert result["truncated"] is False
    assert result["record_count"] == 3
    assert result["total_count"] == 3
    assert "hint" not in result
    assert len(result["data"]) == 3
    assert "retrieved_at" in result


def test_format_json_response_list_truncated_head():
    """keep='head' (default) keeps the first max_records records and hints."""
    data = [{"i": i} for i in range(10)]
    result = json.loads(format_json_response(data, max_records=3))

    assert result["truncated"] is True
    assert result["record_count"] == 3
    assert result["total_count"] == 10
    assert [d["i"] for d in result["data"]] == [0, 1, 2]
    assert "hint" in result
    assert "first" in result["hint"].lower()


def test_format_json_response_list_truncated_tail():
    """keep='tail' keeps the most recent (last) max_records records."""
    data = [{"i": i} for i in range(10)]
    result = json.loads(format_json_response(data, max_records=3, keep="tail"))

    assert result["truncated"] is True
    assert result["record_count"] == 3
    assert result["total_count"] == 10
    assert [d["i"] for d in result["data"]] == [7, 8, 9]
    assert "most recent" in result["hint"].lower()


def test_format_json_response_dict_passthrough():
    """Dict payloads are merged in as-is (no list-shaped truncation applied)."""
    payload = {"storm": "Milton", "missions": [1, 2, 3]}
    result = json.loads(format_json_response(payload, context="test context"))

    assert result["storm"] == "Milton"
    assert result["missions"] == [1, 2, 3]
    assert result["context"] == "test context"
    assert "retrieved_at" in result


def test_format_json_response_context_included():
    result = json.loads(format_json_response([], context="some context"))
    assert result["context"] == "some context"
