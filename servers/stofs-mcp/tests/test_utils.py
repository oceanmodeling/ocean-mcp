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
    resolve_cycle,
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
