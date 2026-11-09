"""Unit tests for usgs-mcp tools with mocked HTTP responses."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from usgs_mcp.client import USGSClient
from usgs_mcp.models import NWPS_GAUGE_URL, USGS_BASE_URL, USGS_PEAK_URL
from usgs_mcp.tools.flood import usgs_get_flood_status, usgs_get_peak_streamflow
from usgs_mcp.tools.sites import (
    usgs_find_nearest_sites,
    usgs_find_sites,
    usgs_get_site_info,
)
from usgs_mcp.tools.statistics import usgs_get_daily_stats, usgs_get_monthly_stats
from usgs_mcp.tools.streamflow import (
    usgs_get_daily_values,
    usgs_get_hydrograph,
    usgs_get_instantaneous_values,
)

from .conftest import load_fixture, load_json_fixture


@pytest.fixture
def usgs_client():
    """Create a fresh USGSClient for each test.

    backoff_factor=0 so the retry transport replays transient failures with
    no real delay, keeping the error-path tests fast.
    """
    return USGSClient(backoff_factor=0)


@pytest.fixture
def ctx(usgs_client):
    """Create a mock MCP Context."""
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context = {"usgs_client": usgs_client}
    return mock_ctx


# --- Site Tools ---


class TestFindSites:
    """Tests for usgs_find_sites tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_sites_by_state(self, ctx):
        """Find sites in Maryland returns tabular output."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_sites(ctx, state_code="MD")
        assert "USGS Sites" in result
        assert "01646500" in result or "Site ID" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_sites_json_format(self, ctx):
        """Find sites in JSON format returns valid JSON."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_sites(ctx, state_code="MD", response_format="json")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_find_sites_no_criteria(self, ctx):
        """Find sites with no state or bbox returns validation error."""
        result = await usgs_find_sites(ctx)
        assert "Validation Error" in result

    @pytest.mark.asyncio
    async def test_find_sites_invalid_state(self, ctx):
        """Find sites with invalid state code returns validation error."""
        result = await usgs_find_sites(ctx, state_code="ZZ")
        assert "Validation Error" in result


class TestGetSiteInfo:
    """Tests for usgs_get_site_info tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_site_info_markdown(self, ctx):
        """Get site info returns metadata in markdown."""
        rdb_text = load_fixture("site_info.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_get_site_info(ctx, site_number="01646500")
        assert "USGS Site" in result
        assert "Latitude" in result or "Name" in result

    @pytest.mark.asyncio
    async def test_get_site_info_invalid_number(self, ctx):
        """Get site info with short site number returns validation error."""
        result = await usgs_get_site_info(ctx, site_number="123")
        assert "Validation Error" in result


class TestFindNearestSites:
    """Tests for usgs_find_nearest_sites tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_sites(self, ctx):
        """Find nearest sites returns sorted results."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_nearest_sites(ctx, latitude=38.9, longitude=-77.1)
        assert "Nearest USGS Sites" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_sites_geojson(self, ctx):
        """GeoJSON output is a Point FeatureCollection with [lon, lat] coords."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_nearest_sites(
            ctx, latitude=38.9, longitude=-77.1, response_format="geojson"
        )
        gj = json.loads(result)
        assert gj["type"] == "FeatureCollection"
        assert gj["features"], "expected at least one site feature"
        feat = gj["features"][0]
        assert feat["geometry"]["type"] == "Point"
        assert "site_no" in feat["properties"]

    @pytest.mark.asyncio
    async def test_find_nearest_sites_invalid_lat(self, ctx):
        """Find nearest sites with out-of-range latitude returns validation error."""
        result = await usgs_find_nearest_sites(ctx, latitude=200.0, longitude=-77.0)
        assert "Validation Error" in result


# --- Streamflow Tools ---


class TestGetInstantaneousValues:
    """Tests for usgs_get_instantaneous_values tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_iv_markdown(self, ctx):
        """Get instantaneous values returns formatted output."""
        iv_json = load_json_fixture("iv_response.json")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        result = await usgs_get_instantaneous_values(ctx, site_number="01646500")
        assert "Instantaneous Values" in result
        assert "Current" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_iv_json_format(self, ctx):
        """Get instantaneous values in JSON format."""
        iv_json = load_json_fixture("iv_response.json")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        result = await usgs_get_instantaneous_values(
            ctx, site_number="01646500", response_format="json"
        )
        parsed = json.loads(result)
        # JSON is now wrapped in a truncation envelope; raw WaterML under "data".
        assert {"truncated", "returned", "total", "data"} <= parsed.keys()
        assert "retrieved_at" in parsed
        assert "value" in parsed["data"]

    @pytest.mark.asyncio
    async def test_get_iv_invalid_site(self, ctx):
        """Get IV with invalid site number returns validation error."""
        result = await usgs_get_instantaneous_values(ctx, site_number="abc")
        assert "Validation Error" in result


class TestGetDailyValues:
    """Tests for usgs_get_daily_values tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_dv_markdown(self, ctx):
        """Get daily values returns formatted table."""
        dv_json = load_json_fixture("dv_response.json")
        respx.get(f"{USGS_BASE_URL}/dv/").mock(
            return_value=httpx.Response(200, json=dv_json)
        )
        result = await usgs_get_daily_values(
            ctx, site_number="01646500", start_date="2025-01-01", end_date="2025-01-07"
        )
        assert "Daily Values" in result
        assert "2025-01" in result

    @pytest.mark.asyncio
    async def test_get_dv_bad_date_format(self, ctx):
        """Get daily values with bad date format returns validation error."""
        result = await usgs_get_daily_values(
            ctx, site_number="01646500", start_date="01-01-2025", end_date="01-07-2025"
        )
        assert "Validation Error" in result

    @pytest.mark.asyncio
    async def test_get_dv_end_before_start(self, ctx):
        """Get daily values with end before start returns validation error."""
        result = await usgs_get_daily_values(
            ctx, site_number="01646500", start_date="2025-01-07", end_date="2025-01-01"
        )
        assert "Validation Error" in result


class TestGetHydrograph:
    """Tests for usgs_get_hydrograph tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hydrograph(self, ctx):
        """Get hydrograph returns summary with trend."""
        iv_json = load_json_fixture("iv_response.json")
        stat_rdb = load_fixture("daily_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=stat_rdb)
        )
        result = await usgs_get_hydrograph(ctx, site_number="01646500")
        assert "Hydrograph Summary" in result
        assert "Current" in result
        assert "Trend" in result

    @pytest.mark.asyncio
    async def test_get_hydrograph_invalid_days(self, ctx):
        """Get hydrograph with days > 120 returns validation error."""
        result = await usgs_get_hydrograph(ctx, site_number="01646500", days=200)
        assert "Validation Error" in result


# --- Flood Tools ---


class TestGetPeakStreamflow:
    """Tests for usgs_get_peak_streamflow tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_peak_markdown(self, ctx):
        """Get peak streamflow returns table with MAX marker."""
        rdb_text = load_fixture("peak_streamflow.rdb")
        respx.get(USGS_PEAK_URL).mock(return_value=httpx.Response(200, text=rdb_text))
        result = await usgs_get_peak_streamflow(ctx, site_number="01646500")
        assert "Peak Streamflow" in result
        assert "MAX" in result

    @pytest.mark.asyncio
    async def test_get_peak_invalid_site(self, ctx):
        """Get peak with invalid site returns validation error."""
        result = await usgs_get_peak_streamflow(ctx, site_number="short")
        assert "Validation Error" in result


def _nwps_gauge(observed_stage, observed_cat, *, lid="BRKM2"):
    """Minimal NWPS gauge record with real (stage) flood thresholds."""
    return {
        "lid": lid,
        "name": "Potomac River near Washington",
        "flood": {
            "stageUnits": "ft",
            "flowUnits": "cfs",
            "categories": {
                "action": {"stage": 7.0, "flow": -9999},
                "minor": {"stage": 10.0, "flow": -9999},
                "moderate": {"stage": 14.0, "flow": 22000},
                "major": {"stage": 18.0, "flow": -9999},
            },
        },
        "status": {"observed": {"primary": observed_stage, "primaryUnit": "ft"}},
        "ObservedFloodCategory": observed_cat,
        "ForecastFloodCategory": "",
    }


class TestGetFloodStatus:
    """Tests for usgs_get_flood_status tool (NWS/NWPS flood stage)."""

    def _mock_usgs(self):
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=load_json_fixture("iv_response.json"))
        )
        respx.get(USGS_PEAK_URL).mock(
            return_value=httpx.Response(200, text=load_fixture("peak_streamflow.rdb"))
        )
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=load_fixture("daily_stats.rdb"))
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_nws_no_flooding(self, ctx):
        """Below action stage → NWS 'No Flooding', never a flow-ratio label."""
        self._mock_usgs()
        respx.get(f"{NWPS_GAUGE_URL}/01646500").mock(
            return_value=httpx.Response(200, json=_nwps_gauge(2.92, "no_flooding"))
        )
        result = await usgs_get_flood_status(ctx, site_number="01646500")
        assert "**Status**: **No Flooding**" in result
        assert "NWS BRKM2 flood category" in result
        assert "NWS Flood Categories" in result
        # Took the NWS path, not the flow-anomaly fallback.
        assert "not an NWS flood-forecast point" not in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_nws_moderate_flood_json(self, ctx):
        """At/over the moderate stage threshold → real NWS 'Moderate Flood'."""
        self._mock_usgs()
        respx.get(f"{NWPS_GAUGE_URL}/01646500").mock(
            return_value=httpx.Response(200, json=_nwps_gauge(15.2, "moderate"))
        )
        result = await usgs_get_flood_status(
            ctx, site_number="01646500", response_format="json"
        )
        data = json.loads(result)
        assert data["status"] == "Moderate Flood"
        assert data["flood_source"] == "NWS/NWPS"
        assert data["nws_flood_category"] == "moderate"
        assert data["nws_lid"] == "BRKM2"
        assert data["observed_stage"] == 15.2

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_nws_mapping_falls_back_honestly(self, ctx):
        """Not an NWS forecast point → flow anomaly, explicitly NOT flood stage."""
        self._mock_usgs()
        respx.get(f"{NWPS_GAUGE_URL}/01646500").mock(return_value=httpx.Response(404))
        result = await usgs_get_flood_status(ctx, site_number="01646500")
        assert "not an nws flood-forecast point" in result.lower()
        assert "streamflow anomaly" in result.lower()
        # No NWS thresholds → no flood-category table at all.
        assert "NWS Flood Categories" not in result
        assert "Moderate Flood" not in result

        as_json = json.loads(
            await usgs_get_flood_status(
                ctx, site_number="01646500", response_format="json"
            )
        )
        assert "flow anomaly" in as_json["flood_source"]
        assert "note" in as_json
        assert "nws_flood_category" not in as_json

    @pytest.mark.asyncio
    async def test_get_flood_status_invalid_site(self, ctx):
        """Get flood status with invalid site returns validation error."""
        result = await usgs_get_flood_status(ctx, site_number="bad")
        assert "Validation Error" in result


# --- Statistics Tools ---


class TestGetMonthlyStats:
    """Tests for usgs_get_monthly_stats tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_monthly_stats(self, ctx):
        """Get monthly stats returns table by month."""
        rdb_text = load_fixture("monthly_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_get_monthly_stats(ctx, site_number="01646500")
        assert "Monthly Statistics" in result

    @pytest.mark.asyncio
    async def test_get_monthly_stats_invalid_site(self, ctx):
        """Get monthly stats with invalid site returns validation error."""
        result = await usgs_get_monthly_stats(ctx, site_number="12")
        assert "Validation Error" in result


class TestGetDailyStats:
    """Tests for usgs_get_daily_stats tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_daily_stats(self, ctx):
        """Get daily stats returns percentile table."""
        rdb_text = load_fixture("daily_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_get_daily_stats(ctx, site_number="01646500")
        assert "Daily Statistics" in result

    @pytest.mark.asyncio
    async def test_get_daily_stats_invalid_month(self, ctx):
        """Get daily stats with invalid month returns validation error."""
        result = await usgs_get_daily_stats(ctx, site_number="01646500", month=13)
        assert "Validation Error" in result


# --- Error Handling ---


class TestErrorHandling:
    """Tests for error handling across tools."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error(self, ctx):
        """Timeout errors return user-friendly message."""
        respx.get(f"{USGS_BASE_URL}/iv/").mock(side_effect=httpx.ReadTimeout("timeout"))
        result = await usgs_get_instantaneous_values(ctx, site_number="01646500")
        assert "timed out" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_500_error(self, ctx):
        """HTTP 500 errors return user-friendly message."""
        respx.get(f"{USGS_BASE_URL}/iv/").mock(return_value=httpx.Response(500))
        result = await usgs_get_instantaneous_values(ctx, site_number="01646500")
        assert "Error" in result


class TestCapWaterml:
    """Tests for the WaterML JSON truncation envelope (_cap_waterml)."""

    @staticmethod
    def _waterml(n):
        vals = [{"value": str(i), "dateTime": f"t{i}"} for i in range(n)]
        return {"value": {"timeSeries": [{"values": [{"value": vals}]}]}}

    def test_truncates_over_cap_keeping_most_recent(self):
        from usgs_mcp.tools.streamflow import _cap_waterml

        env = _cap_waterml(self._waterml(10), max_points=3)
        assert env["truncated"] is True
        assert env["total"] == 10
        assert env["returned"] == 3
        assert "hint" in env
        kept = env["data"]["value"]["timeSeries"][0]["values"][0]["value"]
        assert [v["value"] for v in kept] == ["7", "8", "9"]

    def test_under_cap_untouched(self):
        from usgs_mcp.tools.streamflow import _cap_waterml

        env = _cap_waterml(self._waterml(2), max_points=5)
        assert env["truncated"] is False
        assert env["total"] == 2
        assert env["returned"] == 2
        assert "hint" not in env


class TestRetryTransport:
    """The RetryTransport replays transient GET failures (backoff_factor=0)."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_transient_503_then_succeeds(self):
        """A 503 followed by a 200 is retried through to success."""
        route = respx.get(f"{USGS_BASE_URL}/iv/").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"value": {"timeSeries": []}}),
            ]
        )
        c = USGSClient(backoff_factor=0)
        try:
            data = await c.get_json("iv", {"sites": "01646500"})
        finally:
            await c.close()
        assert route.call_count == 2
        assert data == {"value": {"timeSeries": []}}

    @respx.mock
    @pytest.mark.asyncio
    async def test_exhausts_retries_on_persistent_500(self):
        """A persistent 500 is retried max_retries times, then surfaces."""
        route = respx.get(f"{USGS_BASE_URL}/iv/").mock(return_value=httpx.Response(500))
        c = USGSClient(max_retries=2, backoff_factor=0)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await c.get_json("iv", {"sites": "01646500"})
        finally:
            await c.close()
        assert route.call_count == 3  # initial + 2 retries

    @respx.mock
    @pytest.mark.asyncio
    async def test_does_not_retry_404(self):
        """A non-transient 4xx is returned on the first attempt, not retried."""
        route = respx.get(f"{USGS_BASE_URL}/iv/").mock(return_value=httpx.Response(404))
        c = USGSClient(backoff_factor=0)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await c.get_json("iv", {"sites": "01646500"})
        finally:
            await c.close()
        assert route.call_count == 1


# ============================================================================
# USGS no-data value (-999999) is excluded from statistics — real excerpt,
# see fixtures/iv_15290000_ice_SOURCE.md for the source and its SHA-256
# ============================================================================

ICE_FIXTURE = "iv_15290000_ice_excerpt.json"
ICE_VALID = [140.0, 138.0, 138.0, 140.0, 99.9, 99.9, 99.9, 98.5]


def _ice_iv(n_values: int | None = None) -> dict:
    """The real 15290000 excerpt; optionally only its first n readings."""
    data = load_json_fixture(ICE_FIXTURE)
    if n_values is not None:
        vs = data["value"]["timeSeries"][0]["values"][0]
        vs["value"] = vs["value"][:n_values]
    return data


class TestScreenSeriesValues:
    """screen_series_values splits valid readings from no-data ones."""

    def test_no_data_readings_are_excluded_and_counted(self):
        """The six -999999 readings (qualifier Ice) are excluded and counted."""
        from usgs_mcp.models import screen_series_values

        ts = _ice_iv()["value"]["timeSeries"][0]
        valid, info = screen_series_values(ts)
        assert [v["value"] for v in valid] == ICE_VALID
        assert info["no_data_value"] == -999999.0
        assert info["readings"] == 14
        assert info["valid"] == 8
        assert info["excluded"] == {
            "no_data_value": 6,
            "non_numeric": 0,
            "non_finite": 0,
        }
        assert info["excluded_qualifiers"] == {"P,Ice": 6}
        assert info["latest"]["excluded_reason"] == "no_data_value"
        assert info["latest"]["datetime"] == "2026-11-08T17:15:00.000-09:00"

    def test_non_numeric_and_non_finite_are_counted(self):
        """Blank and NaN readings are excluded with their own reasons."""
        from usgs_mcp.models import screen_series_values

        ts = _ice_iv(4)["value"]["timeSeries"][0]
        ts["values"][0]["value"] += [
            {"value": "", "qualifiers": ["P"], "dateTime": "x1"},
            {"value": "NaN", "qualifiers": ["P"], "dateTime": "x2"},
        ]
        valid, info = screen_series_values(ts)
        assert len(valid) == 4
        assert info["excluded"]["non_numeric"] == 1
        assert info["excluded"]["non_finite"] == 1


class TestHydrographNoData:
    """usgs_get_hydrograph statistics use valid readings only."""

    def _mock(self, iv):
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv)
        )
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=load_fixture("daily_stats.rdb"))
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_statistics_exclude_the_no_data_value(self, ctx):
        """min/max/mean over the 8 valid readings; current is null, not -999999."""
        self._mock(_ice_iv())
        data = json.loads(
            await usgs_get_hydrograph(
                ctx, site_number="15290000", response_format="json"
            )
        )
        assert data["current_cfs"] is None
        assert data["min_cfs"] == 98.5
        assert data["max_cfs"] == 140.0
        assert data["mean_cfs"] == round(sum(ICE_VALID) / len(ICE_VALID), 1)
        assert data["num_readings"] == 8
        assert data["readings_total"] == 14
        assert data["excluded_readings"]["no_data_value"] == 6
        assert data["excluded_qualifiers"] == {"P,Ice": 6}
        assert data["last_valid_cfs"] == 98.5
        assert data["last_valid_time"] == "2026-11-06T11:00:00.000-09:00"
        assert "not a measurement" in data["current_note"]
        assert data.get("pct_of_median") is None
        assert -999999.0 not in (data["min_cfs"], data["max_cfs"], data["mean_cfs"])

    @respx.mock
    @pytest.mark.asyncio
    async def test_markdown_states_the_exclusion(self, ctx):
        """Markdown reports valid/total readings and that current is no data."""
        self._mock(_ice_iv())
        result = await usgs_get_hydrograph(ctx, site_number="15290000")
        assert "8 valid of 14" in result
        assert "6 USGS no-data value (-999999.0)" in result
        assert "P,Ice x6" in result
        assert "| Current | no data" in result
        assert "| Last valid | 98.5" in result
        assert "-999999.0 ft3/s" not in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_valid_reading_is_current(self, ctx):
        """Before freeze-up (first 8 readings) current is the latest reading."""
        self._mock(_ice_iv(8))
        data = json.loads(
            await usgs_get_hydrograph(
                ctx, site_number="15290000", response_format="json"
            )
        )
        assert data["current_cfs"] == 98.5
        assert data["excluded_readings"]["no_data_value"] == 0
        assert "current_note" not in data


class TestFloodStatusNoData:
    """usgs_get_flood_status never treats -999999 as the current flow."""

    def _mock_usgs(self):
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=_ice_iv())
        )
        respx.get(USGS_PEAK_URL).mock(
            return_value=httpx.Response(200, text=load_fixture("peak_streamflow.rdb"))
        )
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=load_fixture("daily_stats.rdb"))
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_nws_point_current_flow_is_null(self, ctx):
        """NWS status stands; current flow and its ratios are null with a note."""
        self._mock_usgs()
        respx.get(f"{NWPS_GAUGE_URL}/15290000").mock(
            return_value=httpx.Response(200, json=_nwps_gauge(2.45, "no_flooding"))
        )
        data = json.loads(
            await usgs_get_flood_status(
                ctx, site_number="15290000", response_format="json"
            )
        )
        assert data["status"] == "No Flooding"
        assert data["current_flow_cfs"] is None
        assert data.get("pct_of_median") is None
        assert data.get("pct_of_peak") is None
        assert "not a measurement" in data["current_flow_note"]
        assert data["readings_excluded_last_24h"]["no_data_value"] == 6

    @respx.mock
    @pytest.mark.asyncio
    async def test_non_nws_point_is_unknown_not_below_normal(self, ctx):
        """Without NWS stage, a no-data reading gives 'Unknown', not a flow label."""
        self._mock_usgs()
        respx.get(f"{NWPS_GAUGE_URL}/15290000").mock(return_value=httpx.Response(404))
        data = json.loads(
            await usgs_get_flood_status(
                ctx, site_number="15290000", response_format="json"
            )
        )
        assert data["status"] == "Unknown"
        assert data["current_flow_cfs"] is None
        assert "flow_vs_median_ratio" not in data

    @respx.mock
    @pytest.mark.asyncio
    async def test_markdown_current_flow_says_no_data(self, ctx):
        """Markdown shows 'no data' instead of -999,999.0 cfs."""
        self._mock_usgs()
        respx.get(f"{NWPS_GAUGE_URL}/15290000").mock(
            return_value=httpx.Response(200, json=_nwps_gauge(2.45, "no_flooding"))
        )
        result = await usgs_get_flood_status(ctx, site_number="15290000")
        assert "**Current Flow**: no data" in result
        assert "-999,999" not in result
