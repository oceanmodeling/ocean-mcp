"""Unit tests for STOFS MCP utilities."""

import math
import pytest

from stofs_mcp.client import STOFSClient
from stofs_mcp.models import get_model_label
from stofs_mcp.stations import (
    STOFS_STATIONS,
    filter_by_proximity,
    filter_by_region,
    filter_by_state,
    get_station_by_id,
)
from stofs_mcp.utils import (
    align_timeseries,
    compute_peak_stats,
    compute_validation_stats,
    find_nearest_station,
    format_station_table,
    format_timeseries_table,
    get_opendap_region,
    handle_stofs_error,
    parse_station_netcdf,
    resolve_cycle,
    resolve_station_datum,
    classify_datum_label,
    combine_datum_attributes,
    datum_from_label,
    dumps_strict,
    unswap_station_coords,
)

from .conftest import (
    GLOBAL_2D,
    GLOBAL_3D_V31,
    GLOBAL_ESTOFS,
    ZETA_2D,
    ZETA_3D_V21,
    ZETA_3D_V31,
)


# ---------------------------------------------------------------------------
# Haversine / nearest station
# ---------------------------------------------------------------------------


class TestFindNearestStation:
    def test_finds_nearest(self):
        lats = [40.0, 41.0, 42.0]
        lons = [-74.0, -74.0, -74.0]
        names = ["A", "B", "C"]
        result = find_nearest_station(
            40.1, -74.0, lats, lons, names, max_distance_km=200
        )
        assert result is not None
        idx, name, dist = result
        assert name == "A"
        assert dist < 15

    def test_returns_none_when_too_far(self):
        lats = [40.0]
        lons = [-74.0]
        names = ["A"]
        result = find_nearest_station(
            50.0, -74.0, lats, lons, names, max_distance_km=10
        )
        assert result is None

    def test_known_distance(self):
        # NYC to Boston ≈ 307 km
        result = find_nearest_station(
            42.36, -71.06, [40.71], [-74.01], ["NYC"], max_distance_km=400
        )
        assert result is not None
        _, _, dist = result
        assert 290 < dist < 325


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------


class TestComputeValidationStats:
    def test_perfect_forecast(self):
        f = [1.0, 2.0, 3.0]
        o = [1.0, 2.0, 3.0]
        stats = compute_validation_stats(f, o)
        assert stats["bias"] == pytest.approx(0.0)
        assert stats["rmse"] == pytest.approx(0.0)
        assert stats["mae"] == pytest.approx(0.0)
        assert stats["peak_error"] == pytest.approx(0.0)
        assert stats["correlation"] == pytest.approx(1.0)
        assert stats["n"] == 3

    def test_constant_bias(self):
        f = [1.1, 2.1, 3.1]
        o = [1.0, 2.0, 3.0]
        stats = compute_validation_stats(f, o)
        assert stats["bias"] == pytest.approx(0.1, abs=1e-4)
        assert stats["rmse"] == pytest.approx(0.1, abs=1e-4)
        assert stats["correlation"] == pytest.approx(1.0, abs=1e-4)

    def test_known_rmse(self):
        # errors = [0, 0, 1, -1] → RMSE = sqrt(2/4) = sqrt(0.5) ≈ 0.7071
        f = [0.0, 1.0, 2.0, 0.0]
        o = [0.0, 1.0, 1.0, 1.0]
        stats = compute_validation_stats(f, o)
        assert stats["rmse"] == pytest.approx(math.sqrt(0.5), abs=1e-4)

    def test_empty_returns_none(self):
        stats = compute_validation_stats([], [])
        assert stats["bias"] is None
        assert stats["n"] == 0

    def test_mismatched_length_returns_none(self):
        stats = compute_validation_stats([1.0, 2.0], [1.0])
        assert stats["n"] == 0


class TestComputePeakStats:
    def test_peak_values_times_and_errors(self):
        """Peaks, peak error and timing error come from the aligned series."""
        times = [
            "2022-09-28 20:00",
            "2022-09-28 21:00",
            "2022-09-28 22:00",
            "2022-09-28 23:00",
        ]
        peak = compute_peak_stats(times, [1.0, 1.5, 2.0, 2.5], [1.0, 2.0, 3.0, 2.0])
        assert peak["observed_peak_m"] == pytest.approx(3.0)
        assert peak["observed_peak_time"] == "2022-09-28 22:00"
        assert peak["forecast_peak_m"] == pytest.approx(2.5)
        assert peak["forecast_peak_time"] == "2022-09-28 23:00"
        assert peak["peak_error_m"] == pytest.approx(-0.5)
        assert peak["peak_timing_error_hours"] == pytest.approx(1.0)
        assert peak["observed_peak_at_series_end"] is False

    def test_flags_observed_peak_at_series_end(self):
        """A still-rising observed record (e.g. a gauge outage) is flagged."""
        times = ["2022-09-28 15:00", "2022-09-28 16:00", "2022-09-28 17:00"]
        peak = compute_peak_stats(times, [1.0, 1.2, 1.1], [1.0, 1.8, 2.3])
        assert peak["observed_peak_at_series_end"] is True
        assert peak["peak_timing_error_hours"] == pytest.approx(-1.0)

    def test_empty_or_mismatched_returns_none(self):
        """Empty or mismatched input yields None fields instead of raising."""
        assert compute_peak_stats([], [], [])["observed_peak_m"] is None
        mismatched = compute_peak_stats(["2022-09-28 15:00"], [1.0], [])
        assert mismatched["peak_error_m"] is None


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------


class TestAlignTimeseries:
    def test_exact_match(self):
        times = ["2026-02-19 00:00", "2026-02-19 00:06", "2026-02-19 00:12"]
        vals_f = [1.0, 2.0, 3.0]
        vals_o = [1.1, 2.1, 3.1]
        ct, af, ao = align_timeseries(times, vals_f, times, vals_o)
        assert len(ct) == 3
        assert af == vals_f
        assert ao == vals_o

    def test_offset_within_tolerance(self):
        # Forecast at :00, observed at :02 (2-min offset, within 3-min tolerance)
        ft = ["2026-02-19 00:00"]
        fv = [1.0]
        ot = ["2026-02-19 00:02"]
        ov = [1.1]
        ct, af, ao = align_timeseries(ft, fv, ot, ov, tolerance_minutes=3)
        assert len(ct) == 1

    def test_outside_tolerance_not_matched(self):
        ft = ["2026-02-19 00:00"]
        fv = [1.0]
        ot = ["2026-02-19 00:10"]
        ov = [1.1]
        ct, af, ao = align_timeseries(ft, fv, ot, ov, tolerance_minutes=3)
        assert len(ct) == 0

    def test_empty_input(self):
        ct, af, ao = align_timeseries([], [], [], [])
        assert ct == []


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


class TestBuildStationUrl:
    def setup_method(self):
        self.client = STOFSClient()

    def test_2d_global_cwl(self):
        url = self.client.build_station_url("2d_global", "20260219", "12", "cwl")
        assert "noaa-gestofs-pds.s3.amazonaws.com" in url
        assert "stofs_2d_glo.20260219" in url
        assert "t12z.points.cwl.nc" in url

    def test_2d_global_swl(self):
        url = self.client.build_station_url("2d_global", "20260219", "00", "swl")
        assert "t00z.points.swl.nc" in url

    def test_3d_atlantic(self):
        url = self.client.build_station_url("3d_atlantic", "20260219", "12", "cwl")
        assert "noaa-nos-stofs3d-pds.s3.amazonaws.com" in url
        assert "STOFS-3D-Atl/stofs_3d_atl.20260219" in url
        assert "t12z.points.cwl.nc" in url

    def test_invalid_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            self.client.build_station_url("invalid_model", "20260219", "12", "cwl")

    def test_2d_global_pre_cutover_uses_estofs_archive(self):
        """Cycles before 2023-01-08 resolve to the estofs.* archive prefix."""
        url = self.client.build_station_url("2d_global", "20220927", "00", "cwl")
        assert url == (
            "https://noaa-gestofs-pds.s3.amazonaws.com/estofs.20220927/"
            "estofs.t00z.points.cwl.nc"
        )

    def test_2d_global_cutover_day_uses_stofs_prefix(self):
        """The cutover date itself is the first stofs_2d_glo.* directory."""
        url = self.client.build_station_url("2d_global", "20230108", "00", "cwl")
        assert "/stofs_2d_glo.20230108/stofs_2d_glo.t00z.points.cwl.nc" in url

    def test_3d_atlantic_ignores_cutover(self):
        """The ESTOFS fallback applies only to the 2D-Global model."""
        url = self.client.build_station_url("3d_atlantic", "20220927", "12", "cwl")
        assert "STOFS-3D-Atl/stofs_3d_atl.20220927" in url


class TestGetModelLabel:
    def test_2d_global_current(self):
        """Post-cutover 2D cycles are labelled STOFS-2D-Global."""
        assert get_model_label("2d_global", "20260219") == "STOFS-2D-Global"

    def test_2d_global_pre_cutover(self):
        """Pre-cutover 2D cycles are labelled as ESTOFS-Global."""
        assert get_model_label("2d_global", "20220927") == (
            "ESTOFS-Global (STOFS-2D predecessor)"
        )

    def test_2d_global_without_date(self):
        """No date falls back to the current model name."""
        assert get_model_label("2d_global") == "STOFS-2D-Global"

    def test_3d_atlantic(self):
        """3D-Atlantic is never relabelled."""
        assert get_model_label("3d_atlantic", "20220927") == "STOFS-3D-Atlantic"


# ---------------------------------------------------------------------------
# OPeNDAP URL construction
# ---------------------------------------------------------------------------


class TestBuildOpendapUrl:
    def setup_method(self):
        self.client = STOFSClient()

    def test_2d_global(self):
        url = self.client.build_opendap_url("2d_global", "20260219", "12")
        assert "nomads.ncep.noaa.gov/dods/stofs_2d_glo" in url
        assert "/20260219/" in url
        assert "stofs_2d_glo_conus.east_12z" in url

    def test_2d_global_region(self):
        url = self.client.build_opendap_url("2d_global", "20260219", "06", "hawaii")
        assert "/20260219/" in url
        assert "stofs_2d_glo_hawaii_06z" in url

    def test_2d_global_all_cycles(self):
        for cycle in ("00", "06", "12", "18"):
            url = self.client.build_opendap_url("2d_global", "20260219", cycle)
            assert f"stofs_2d_glo_conus.east_{cycle}z" in url

    def test_3d_atlantic(self):
        url = self.client.build_opendap_url("3d_atlantic", "20260219", "12")
        assert "nomads.ncep.noaa.gov/dods/stofs_3d_atl" in url
        assert "/20260219/" in url
        assert "stofs_3d_atl_conus.east_12z" in url

    def test_invalid_model_raises(self):
        with pytest.raises(ValueError):
            self.client.build_opendap_url("invalid", "20260219", "12")

    def test_url_is_string(self):
        url = self.client.build_opendap_url("2d_global", "20260219", "06")
        assert isinstance(url, str)
        assert url.startswith("https://")


class TestGetOpendapRegion:
    def test_nyc_conus_east(self):
        assert get_opendap_region(40.7, -74.0) == "conus.east"

    def test_miami_conus_east(self):
        assert get_opendap_region(25.8, -80.2) == "conus.east"

    def test_san_francisco_conus_west(self):
        assert get_opendap_region(37.8, -122.4) == "conus.west"

    def test_honolulu_hawaii(self):
        assert get_opendap_region(21.3, -157.8) == "hawaii"

    def test_puerto_rico(self):
        assert get_opendap_region(18.5, -66.1) == "puertori"

    def test_guam(self):
        assert get_opendap_region(13.5, 144.8) == "guam"

    def test_anchorage_alaska(self):
        assert get_opendap_region(61.2, -149.9) == "alaska"


# ---------------------------------------------------------------------------
# Station registry
# ---------------------------------------------------------------------------


class TestStationRegistry:
    def test_battery_found(self):
        s = get_station_by_id("8518750")
        assert s is not None
        assert s["name"] == "The Battery"
        assert s["state"] == "NY"

    def test_unknown_station_returns_none(self):
        assert get_station_by_id("0000000") is None

    def test_filter_by_state_ny(self):
        ny = filter_by_state(STOFS_STATIONS, "NY")
        assert len(ny) >= 1
        assert all(s["state"] == "NY" for s in ny)

    def test_filter_by_state_case_insensitive(self):
        fl_lower = filter_by_state(STOFS_STATIONS, "fl")
        fl_upper = filter_by_state(STOFS_STATIONS, "FL")
        assert len(fl_lower) == len(fl_upper)

    def test_filter_by_region_gulf(self):
        gulf = filter_by_region(STOFS_STATIONS, "gulf")
        assert len(gulf) >= 5
        for s in gulf:
            assert 24.0 <= s["lat"] <= 31.0
            assert -98.0 <= s["lon"] <= -82.0

    def test_filter_by_proximity(self):
        # Near NYC
        nearby = filter_by_proximity(STOFS_STATIONS, 40.7, -74.0, 50.0)
        assert len(nearby) >= 1
        names = [s["name"] for _, s in nearby]
        assert "The Battery" in names


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_timeseries_table_basic(self):
        times = ["2026-02-19 00:00", "2026-02-19 00:06"]
        values = [0.5, 0.6]
        result = format_timeseries_table(times, values, title="Test")
        assert "## Test" in result
        assert "| Time (UTC)" in result
        assert "0.500" in result

    def test_timeseries_table_empty(self):
        result = format_timeseries_table([], [], title="Empty")
        assert "No data" in result

    def test_station_table_basic(self):
        stations = [
            {
                "id": "8518750",
                "name": "The Battery",
                "state": "NY",
                "lat": 40.7,
                "lon": -74.0,
            }
        ]
        result = format_station_table(stations, title="Stations")
        assert "## Stations" in result
        assert "8518750" in result
        assert "The Battery" in result

    def test_station_table_with_extra_col(self):
        stations = [
            {
                "id": "8518750",
                "name": "The Battery",
                "state": "NY",
                "lat": 40.7,
                "lon": -74.0,
                "distance_km": 5.2,
            }
        ]
        result = format_station_table(
            stations, extra_col=("distance_km", "Distance (km)")
        )
        assert "Distance (km)" in result
        assert "5.2" in result


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


class TestHandleStofsError:
    def test_404_error(self):
        import httpx

        response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        err = httpx.HTTPStatusError(
            "not found", request=response.request, response=response
        )
        result = handle_stofs_error(err, model="2d_global")
        assert "404" in result
        assert "stofs_list_cycles" in result

    def test_403_error(self):
        import httpx

        response = httpx.Response(403, request=httpx.Request("GET", "http://test"))
        err = httpx.HTTPStatusError(
            "forbidden", request=response.request, response=response
        )
        result = handle_stofs_error(err)
        assert "403" in result

    def test_timeout(self):
        import httpx

        result = handle_stofs_error(httpx.ReadTimeout("timeout"))
        assert "timed out" in result.lower()

    def test_value_error(self):
        result = handle_stofs_error(ValueError("station not found"))
        assert "station not found" in result

    def test_generic_error(self):
        result = handle_stofs_error(RuntimeError("unexpected"))
        assert "RuntimeError" in result


# ---------------------------------------------------------------------------
# Centralized cycle resolution (regression: validation.py used to silently
# ignore a provided cycle_date when cycle_hour was omitted and compare the
# WRONG, latest cycle. The shared resolver must honour a date alone.)
# ---------------------------------------------------------------------------


class TestResolveCycle:
    @pytest.mark.asyncio
    async def test_date_only_honours_date_not_latest(self):
        """A date with no hour must keep the date (regression for the
        validation tool's old silent fallback to the latest cycle)."""
        # client=None proves these branches never touch S3 / resolve_latest.
        out = await resolve_cycle(None, "2d_global", "2026-05-15", None)
        assert out == ("20260515", "18")  # first MODEL_CYCLES["2d_global"] hour

    @pytest.mark.asyncio
    async def test_date_and_hour(self):
        """Both provided → that exact cycle, hour zero-padded."""
        out = await resolve_cycle(None, "2d_global", "2026-05-15", "6")
        assert out == ("20260515", "06")

    @pytest.mark.asyncio
    async def test_yyyymmdd_form_accepted(self):
        """Compact YYYYMMDD dates resolve the same as YYYY-MM-DD."""
        out = await resolve_cycle(None, "2d_global", "20260515", "12")
        assert out == ("20260515", "12")

    @pytest.mark.asyncio
    async def test_3d_atlantic_default_hour(self):
        """Date-only uses the model's own first cycle (3D-Atlantic = 12z)."""
        out = await resolve_cycle(None, "3d_atlantic", "2026-05-15", None)
        assert out == ("20260515", "12")

    @pytest.mark.asyncio
    async def test_unparseable_date_returns_none(self):
        """A bad date returns None rather than silently using another cycle."""
        out = await resolve_cycle(None, "2d_global", "not-a-date", "00")
        assert out is None


# ---------------------------------------------------------------------------
# Vertical datum: read from the file, version-aware fallback
# ---------------------------------------------------------------------------


class TestDatumFromLabel:
    """datum_from_label maps CF labels to datums and refuses ambiguous ones."""

    @pytest.mark.parametrize(
        "label,expected",
        [
            ("sea_surface_height_above_navd88", "NAVD88"),
            ("water surface elevation above navd88", "NAVD88"),
            ("sea_surface_height_above_msl", "LMSL"),
            ("water surface elevation above msl", "LMSL"),
            ("sea_surface_height_above_mean_sea_level", "LMSL"),
            ("water level above LMSL", "LMSL"),
            ("height above MLLW", "MLLW"),
            ("water surface elevation above xgeoid20b", "xGEOID20b"),
        ],
    )
    def test_specific_labels(self, label, expected):
        """Labels that name a datum map to it."""
        assert datum_from_label(label) == expected

    @pytest.mark.parametrize(
        "label",
        ["sea_surface_height_above_geoid", "water surface elevation", "", None],
    )
    def test_ambiguous_labels_return_none(self, label):
        """ADCIRC's generic 'above geoid' and empty labels name no datum."""
        assert datum_from_label(label) is None

    def test_msl_inside_another_word_is_not_a_datum(self):
        """'mslp' (pressure) must not be read as MSL."""
        assert datum_from_label("air_pressure_at_mslp") is None


class TestParseStationNetcdfDatum:
    """parse_station_netcdf reports the datum named by the zeta metadata."""

    def test_v21_3d_file_reads_navd88(self, station_nc):
        """A pre-v3.1 STOFS-3D file is NAVD88 per its zeta:standard_name."""
        path = station_nc(ZETA_3D_V21, "2026-02-17 12:00", [0.1, 0.2])
        meta = parse_station_netcdf(path)
        assert meta["datum"] == "NAVD88"
        assert meta["datum_label"] == (
            "zeta:standard_name=sea_surface_height_above_navd88"
        )

    def test_v31_3d_file_reads_lmsl(self, station_nc):
        """A v3.1 STOFS-3D file is LMSL per its zeta:standard_name."""
        path = station_nc(ZETA_3D_V31, "2026-08-16 12:00", [0.1, 0.2])
        assert parse_station_netcdf(path, "8443970")["datum"] == "LMSL"

    def test_2d_geoid_label_is_ambiguous(self, station_nc):
        """The 2D 'above geoid' label yields no datum, but keeps the label."""
        path = station_nc(ZETA_2D, "2026-02-18 12:00", [0.1, 0.2])
        meta = parse_station_netcdf(path)
        assert meta["datum"] == ""
        assert "sea_surface_height_above_geoid" in meta["datum_label"]


class TestClassifyDatumLabel:
    """Labels are classified; unfamiliar explicit references are not guessed."""

    @pytest.mark.parametrize(
        "label,status,datum",
        [
            ("sea_surface_height_above_navd88", "recognized", "NAVD88"),
            ("water level above NAVD", "recognized", "NAVD88"),
            ("sea_surface_height_above_msl", "recognized", "LMSL"),
            ("sea_surface_height_above_mean_sea_level", "recognized", "LMSL"),
            ("height above MLLW", "recognized", "MLLW"),
            ("water surface elevation above xgeoid20b", "recognized", "xGEOID20b"),
            ("sea_surface_height_above_geoid", "generic", None),
            ("water surface elevation", "generic", None),
            ("", "absent", None),
            (None, "absent", None),
        ],
    )
    def test_known_generic_and_absent(self, label, status, datum):
        """Known datums are recognized; generic and absent labels name none."""
        c = classify_datum_label(label)
        assert (c["status"], c["datum"]) == (status, datum)

    @pytest.mark.parametrize(
        "label,reference",
        [
            ("sea_surface_height_above_ngvd29", "ngvd29"),
            ("sea_surface_height_above_NAVD2022", "navd2022"),
            ("water level above navd 2022", "navd 2022"),
            ("sea_surface_height_above_reference_ellipsoid", "reference_ellipsoid"),
            ("water level above GMSL", "gmsl"),
        ],
    )
    def test_unfamiliar_explicit_reference_is_unsupported(self, label, reference):
        """NGVD29, NAVD2022, ellipsoid and global MSL are not mapped to a known datum."""
        c = classify_datum_label(label)
        assert c["status"] == "unsupported"
        assert c["reference"] == reference
        assert datum_from_label(label) is None

    def test_two_datums_in_one_label_conflict(self):
        """A label naming two different datums is conflicting, not first-match."""
        c = classify_datum_label("water level relative to MLLW and NAVD88")
        assert c["status"] == "conflicting"
        assert datum_from_label("water level relative to MLLW and NAVD88") is None


class TestCombineDatumAttributes:
    """File-level verdicts across standard_name, long_name and global attrs."""

    def test_specific_attributes_that_disagree_conflict(self):
        """NAVD88 standard_name vs MSL long_name is a conflict (review C1)."""
        out = combine_datum_attributes(
            {
                "zeta:standard_name": "sea_surface_height_above_navd88",
                "zeta:long_name": "water surface elevation above msl",
            }
        )
        assert out["status"] == "conflicting"
        assert "above_navd88" in out["label"] and "above msl" in out["label"]

    def test_generic_does_not_conflict_with_specific(self):
        """A generic 'geoid' long_name does not override a specific standard_name."""
        out = combine_datum_attributes(
            {
                "zeta:standard_name": "sea_surface_height_above_msl",
                "zeta:long_name": "water surface elevation above geoid",
            }
        )
        assert (out["status"], out["datum"]) == ("recognized", "LMSL")

    def test_unsupported_wins_over_recognized(self):
        """Any unsupported explicit reference blocks interpretation."""
        out = combine_datum_attributes(
            {
                "zeta:standard_name": "sea_surface_height_above_navd88",
                ":vertical_datum": "NGVD29",
            }
        )
        assert out["status"] == "unsupported"

    def test_raw_attributes_are_preserved(self):
        """Every inspected attribute is returned verbatim."""
        attrs = {"zeta:standard_name": "sea_surface_height_above_geoid"}
        assert combine_datum_attributes(attrs)["attributes"] == attrs


class TestProductSignature:
    """parse_station_netcdf identifies the producing system and version."""

    def test_3d_v31_package_version(self, station_nc):
        """The STOFS package version is read from the 3D history attribute."""
        path = station_nc(
            ZETA_3D_V31, "2026-10-29 12:00", [0.1], global_attrs=GLOBAL_3D_V31
        )
        assert (
            parse_station_netcdf(path)["product"]["product_version"] == "stofs.v3.1.4"
        )

    def test_2d_title_version(self, station_nc):
        """The 2D product version is read from ADCIRC's padded title."""
        path = station_nc(ZETA_2D, "2026-10-30 06:00", [0.1], global_attrs=GLOBAL_2D)
        product = parse_station_netcdf(path)["product"]
        assert product["model"] == "ADCIRC"
        assert product["product_version"] == "STOFS_2D_GLOBAL V3.1.0"

    def test_estofs_title_version(self, station_nc):
        """The pre-2023 ESTOFS archive title is recognized too."""
        path = station_nc(
            ZETA_2D, "2022-12-01 00:00", [0.1], global_attrs=GLOBAL_ESTOFS
        )
        assert parse_station_netcdf(path)["product"]["product_version"] == (
            "ESTOFS GLOBAL V2.1.0"
        )


def _meta(status, datum="", label="", reference=None, product=None):
    return {
        "datum": datum,
        "datum_status": status,
        "datum_label": label,
        "datum_reference": reference,
        "datum_attributes": {},
        "product": product or {},
    }


ADCIRC_2D = {"model": "ADCIRC", "title": "STOFS_2D_GLOBAL.V3.1.0"}


class TestResolveStationDatum:
    """resolve_station_datum: file metadata first, fallback only when safe."""

    def test_file_metadata_wins(self):
        """An unambiguous file label is used and cited as the source."""
        out = resolve_station_datum(
            "3d_atlantic", "20260818", "12", _meta("recognized", "LMSL", "zeta:..._msl")
        )
        assert out["datum"] == "LMSL"
        assert out["comparable"] is True
        assert out["resolution"] == "file_metadata"
        assert out["datum_source"].startswith("file metadata")
        assert out["datum_warning"] == ""

    def test_2d_generic_label_with_adcirc_signature_falls_back(self):
        """2D 'geoid' label from an ADCIRC STOFS-2D file -> documented LMSL."""
        out = resolve_station_datum(
            "2d_global",
            "20260218",
            "18",
            _meta("generic", label="zeta:..._geoid", product=ADCIRC_2D),
        )
        assert (out["datum"], out["resolution"]) == ("LMSL", "documented_fallback")
        assert out["comparable"] is True
        assert "names no specific datum" in out["datum_source"]

    def test_2d_generic_label_from_unknown_producer_is_undetermined(self):
        """Without the ADCIRC STOFS-2D signature there is no fallback."""
        out = resolve_station_datum(
            "2d_global", "20260218", "18", _meta("generic", label="zeta:..._geoid")
        )
        assert out["datum"] == "undetermined"
        assert out["comparable"] is False
        assert out["datum_warning"]

    @pytest.mark.parametrize("date", ["20260816", "20260817", "20270101"])
    def test_3d_without_label_is_undetermined(self, date):
        """No date-based guess for a 3D file that names no datum."""
        out = resolve_station_datum("3d_atlantic", date, "12", {})
        assert out["datum"] == "undetermined"
        assert out["comparable"] is False

    def test_unsupported_reference_is_undetermined(self):
        """An NGVD29 label is reported, not replaced by LMSL (review C1)."""
        out = resolve_station_datum(
            "3d_atlantic",
            "20260902",
            "12",
            _meta("unsupported", label="zeta:..._ngvd29", reference="ngvd29"),
        )
        assert out["datum"] == "undetermined"
        assert out["comparable"] is False
        assert "ngvd29" in out["datum_warning"]
        assert "names no specific datum" not in out["datum_source"]

    def test_conflicting_attributes_are_undetermined(self):
        """Contradictory attributes block interpretation and are named."""
        out = resolve_station_datum(
            "3d_atlantic",
            "20260902",
            "12",
            _meta("conflicting", label="a=navd88; b=msl"),
        )
        assert out["comparable"] is False
        assert "contradict" in out["datum_warning"]

    def test_unclassified_caller_label_is_classified(self):
        """A caller passing only a label still gets the unsupported verdict."""
        out = resolve_station_datum(
            "3d_atlantic",
            "20260902",
            "12",
            {
                "datum": "",
                "datum_label": "zeta:standard_name=sea_surface_height_above_ngvd29",
            },
        )
        assert out["comparable"] is False
        assert "ngvd29" in out["datum_warning"]

    def test_file_contradicting_documentation_is_flagged(self):
        """A NAVD88 label on a post-v3.1 cycle is used but warned about."""
        out = resolve_station_datum(
            "3d_atlantic",
            "20260901",
            "12",
            _meta("recognized", "NAVD88", "zeta:..._navd88"),
        )
        assert out["datum"] == "NAVD88"
        assert out["comparable"] is True
        assert "NOAA documents LMSL" in out["datum_warning"]


class TestValidationStatsDefinitions:
    """max_abs_error is the largest pointwise error, not the peak-level error."""

    def test_max_abs_error_differs_from_peak_error_m(self):
        """Boston-like case: max |F-O| and (max F - max O) are different numbers."""
        times = ["2026-02-18 12:00", "2026-02-18 12:06", "2026-02-18 12:12"]
        forecast = [0.0, 1.0, 0.5]
        observed = [0.2, 1.1, 0.4]
        stats = compute_validation_stats(forecast, observed)
        peak = compute_peak_stats(times, forecast, observed)
        assert stats["max_abs_error"] == pytest.approx(0.2)
        assert stats["peak_error"] == stats["max_abs_error"]  # legacy alias
        assert peak["peak_error_m"] == pytest.approx(-0.1)

    def test_constant_series_correlation_is_none_and_json_safe(self):
        """A constant series has undefined correlation: None, not NaN."""
        import json

        stats = compute_validation_stats([0.2, 0.2, 0.2], [0.1, 0.3, 0.2])
        assert stats["correlation"] is None

        def reject(name):
            raise ValueError(name)

        json.loads(json.dumps(stats), parse_constant=reject)  # no NaN emitted


class TestUnswapStationCoords:
    """STOFS-3D v2.1 station files store latitude in x for most rows."""

    def test_swapped_3d_row_is_repaired(self):
        """Boston as stored in the 2026-02-18 file (x=42.354, y=-71.050)."""
        lats, lons = unswap_station_coords("3d_atlantic", [-71.0503], [42.3539])
        assert lats == [42.3539] and lons == [-71.0503]

    def test_correct_3d_row_is_untouched(self):
        """Rows already stored correctly (3 of 108 in v2.1, all in v3.1) stay."""
        lats, lons = unswap_station_coords("3d_atlantic", [28.4157], [-80.5934])
        assert lats == [28.4157] and lons == [-80.5934]

    def test_2d_southern_hemisphere_station_is_not_swapped(self):
        """2D-Global has real stations with latitude < 0 < longitude (Sydney)."""
        lats, lons = unswap_station_coords("2d_global", [-33.85], [151.23])
        assert lats == [-33.85] and lons == [151.23]

    def test_unknown_model_is_untouched(self):
        """Without a model the repair is not applied."""
        assert unswap_station_coords(None, [-71.0], [42.3]) == ([-71.0], [42.3])

    def test_parse_station_netcdf_repairs_3d_file(self, station_nc):
        """parse_station_netcdf(model='3d_atlantic') returns real coordinates."""
        path = station_nc(
            ZETA_3D_V21, "2026-02-17 12:00", [0.1, 0.2], xy=[(42.3539, -71.0503)]
        )
        data = parse_station_netcdf(path, "8443970", model="3d_atlantic")
        assert (data["lat"], data["lon"]) == (42.3539, -71.0503)
        raw = parse_station_netcdf(path, "8443970")
        assert (raw["lat"], raw["lon"]) == (-71.0503, 42.3539)  # as stored


class TestNonFiniteValues:
    """NaN, Inf, masked and fill values never reach statistics or JSON (review C3)."""

    def _strict_loads(self, text):
        import json

        def reject(name):
            raise ValueError(name)

        return json.loads(text, parse_constant=reject)

    def test_dumps_strict_nulls_nonfinite_values(self):
        """NaN/±Inf, including NumPy scalars, become null; output is standard JSON."""
        import numpy as np

        out = self._strict_loads(
            dumps_strict(
                {
                    "a": float("nan"),
                    "b": [float("inf"), -float("inf"), 1.5],
                    "c": np.float64("nan"),
                }
            )
        )
        assert out == {"a": None, "b": [None, None, 1.5], "c": None}

    def test_stats_exclude_nonfinite_pairs_and_count_them(self):
        """Non-finite pairs are dropped and counted, never treated as zero."""
        stats = compute_validation_stats(
            [0.1, float("nan"), 0.3, 0.4], [0.0, 0.2, float("inf"), 0.4]
        )
        assert stats["n"] == 2
        assert stats["n_excluded_nonfinite"] == 2
        assert stats["bias"] == pytest.approx(0.05)

    def test_stats_all_invalid_returns_nulls(self):
        """All-invalid input gives n=0 and null metrics."""
        stats = compute_validation_stats([float("nan")], [0.1])
        assert stats["n"] == 0 and stats["bias"] is None
        assert stats["n_excluded_nonfinite"] == 1

    def test_peak_stats_ignore_nonfinite(self):
        """A NaN cannot become the peak."""
        times = ["2026-10-30 12:00", "2026-10-30 12:06", "2026-10-30 12:12"]
        peak = compute_peak_stats(
            times, [0.1, float("nan"), 0.3], [0.2, 0.9, float("inf")]
        )
        assert peak["forecast_peak_m"] == pytest.approx(0.1)
        assert peak["observed_peak_m"] == pytest.approx(0.2)

    def test_parser_excludes_nan_inf_fill_and_masked(self, station_nc):
        """NaN, +Inf, the -99999 fill and masked entries are excluded and counted."""
        import netCDF4
        import numpy as np

        path = station_nc(
            ZETA_3D_V31, "2026-10-29 12:00", [0.1, np.nan, np.inf, -99999.0, 0.2, 0.3]
        )
        nc = netCDF4.Dataset(str(path), "a")
        z = nc["zeta"][:]
        z[5, 0] = np.ma.masked
        nc["zeta"][:] = z
        nc.close()
        data = parse_station_netcdf(path, "8443970")
        assert data["values"] == [0.1, 0.2]
        assert data["n_records"] == 6
        assert data["excluded_model_records"] == {"masked_or_fill": 2, "nonfinite": 2}

    def test_parser_honours_in_range_fill_value(self, tmp_path):
        """A _FillValue inside the physical range (-9.99) is still excluded."""
        import netCDF4
        import numpy as np

        path = tmp_path / "fill.nc"
        nc = netCDF4.Dataset(str(path), "w")
        nc.createDimension("time", 3)
        nc.createDimension("station", 1)
        nc.createDimension("namelen", 8)
        t = nc.createVariable("time", "f8", ("time",))
        t.units = "seconds since 2026-10-30 12:00:00"
        t[:] = [360, 720, 1080]
        n = nc.createVariable("station_name", "S1", ("station", "namelen"))
        c = np.full((1, 8), b"", dtype="S1")
        c[0, :7] = [bytes([x]) for x in b"8443970"]
        n[:] = c
        z = nc.createVariable("zeta", "f8", ("time", "station"), fill_value=-9.99)
        z.standard_name = "sea_surface_height_above_msl"
        z.set_auto_mask(False)
        z[:] = np.array([[0.5], [-9.99], [0.7]])
        nc.close()
        assert parse_station_netcdf(path, "8443970")["values"] == [0.5, 0.7]
