"""Unit tests for STOFS MCP tool functions with mocked HTTP.

Tests tool functions from discovery.py, forecast.py, and validation.py using
respx to mock httpx calls. Covers cycle listing, system info, station listing,
URL building, CO-OPS observation fetching, OPeNDAP availability checking, and
error handling paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from stofs_mcp.client import (
    COOPS_API_BASE,
    RetryTransport,
    S3_BASE_2D,
    S3_BASE_3D,
    STOFSClient,
)
from stofs_mcp.models import STOFSModel, STOFSProduct
from stofs_mcp.utils import (
    align_timeseries,
    compute_validation_stats,
    format_timeseries_table,
    get_opendap_region,
    handle_stofs_error,
    resolve_latest_cycle,
)

# ---------------------------------------------------------------------------
# Paths and helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file from the fixtures directory."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def make_ctx(client: STOFSClient) -> MagicMock:
    """Create a mock MCP Context that provides the STOFS client via lifespan_context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"stofs_client": client}
    return ctx


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = STOFSClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


# ---------------------------------------------------------------------------
# Test: stofs_list_cycles — mock S3 HEAD requests
# ---------------------------------------------------------------------------


class TestListCycles:
    """Tests for the stofs_list_cycles tool function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_cycles_finds_available_cycles(self):
        """stofs_list_cycles should report cycles as available when S3 HEAD returns 200."""
        from stofs_mcp.tools.discovery import stofs_list_cycles

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        # Mock: 2d_global, date 2026-03-03, cycle 18z exists (200), cycle 12z exists (200),
        # cycle 06z not found (404), cycle 00z not found (404)
        # We need to intercept HEAD requests to the S3 bucket.
        # The URLs follow the pattern from build_station_url.
        base = S3_BASE_2D
        date_str = "20260303"

        respx.head(
            f"{base}/stofs_2d_glo.{date_str}/stofs_2d_glo.t18z.points.cwl.nc"
        ).mock(return_value=httpx.Response(200))
        respx.head(
            f"{base}/stofs_2d_glo.{date_str}/stofs_2d_glo.t12z.points.cwl.nc"
        ).mock(return_value=httpx.Response(200))
        respx.head(
            f"{base}/stofs_2d_glo.{date_str}/stofs_2d_glo.t06z.points.cwl.nc"
        ).mock(return_value=httpx.Response(404))
        respx.head(
            f"{base}/stofs_2d_glo.{date_str}/stofs_2d_glo.t00z.points.cwl.nc"
        ).mock(return_value=httpx.Response(404))
        # Also mock yesterday's cycles as all 404
        respx.head(url__regex=r".*stofs_2d_glo\.20260302.*").mock(
            return_value=httpx.Response(404)
        )

        result = await stofs_list_cycles(
            ctx,
            model=STOFSModel.GLOBAL_2D,
            date="2026-03-03",
            num_days=2,
        )

        assert "Available" in result
        assert "18z" in result
        assert "12z" in result
        # 06z and 00z should show as not available
        assert "Not available" in result

        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_cycles_no_cycles_found(self):
        """stofs_list_cycles should report no cycles when all S3 HEADs return 404."""
        from stofs_mcp.tools.discovery import stofs_list_cycles

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        # All HEAD requests return 404
        respx.head(url__regex=r".*noaa-gestofs-pds.*").mock(
            return_value=httpx.Response(404)
        )

        result = await stofs_list_cycles(
            ctx,
            model=STOFSModel.GLOBAL_2D,
            date="2026-03-03",
            num_days=1,
        )

        assert "No cycles found" in result
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_cycles_3d_atlantic_single_cycle(self):
        """stofs_list_cycles for 3d_atlantic should only check the 12z cycle."""
        from stofs_mcp.tools.discovery import stofs_list_cycles

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        date_str = "20260303"
        base = S3_BASE_3D

        respx.head(
            f"{base}/STOFS-3D-Atl/stofs_3d_atl.{date_str}/stofs_3d_atl.t12z.points.cwl.nc"
        ).mock(return_value=httpx.Response(200))
        # Mock yesterday too
        respx.head(url__regex=r".*stofs_3d_atl\.20260302.*").mock(
            return_value=httpx.Response(404)
        )

        result = await stofs_list_cycles(
            ctx,
            model=STOFSModel.ATLANTIC_3D,
            date="2026-03-03",
            num_days=2,
        )

        assert "STOFS-3D-Atlantic" in result
        assert "12z" in result
        assert "Available" in result

        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_cycles_invalid_date_format(self):
        """stofs_list_cycles should return an error for an invalid date string."""
        from stofs_mcp.tools.discovery import stofs_list_cycles

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_list_cycles(
            ctx,
            model=STOFSModel.GLOBAL_2D,
            date="not-a-date",
            num_days=1,
        )

        assert "Invalid date format" in result
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_cycles_clamps_num_days(self):
        """stofs_list_cycles should clamp num_days to the range [1, 7]."""
        from stofs_mcp.tools.discovery import stofs_list_cycles

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        # Mock all HEAD requests as 404
        respx.head(url__regex=r".*noaa-gestofs-pds.*").mock(
            return_value=httpx.Response(404)
        )

        # Provide num_days = 100, it should be clamped to 7
        result = await stofs_list_cycles(
            ctx,
            model=STOFSModel.GLOBAL_2D,
            date="2026-03-03",
            num_days=100,
        )

        assert "last 7 day(s)" in result
        await client.close()


# ---------------------------------------------------------------------------
# Test: stofs_get_system_info — pure data, no HTTP needed
# ---------------------------------------------------------------------------


class TestGetSystemInfo:
    """Tests for the stofs_get_system_info tool function."""

    @pytest.mark.asyncio
    async def test_system_info_returns_both_models(self):
        """stofs_get_system_info with model=None should return info for both models."""
        from stofs_mcp.tools.discovery import stofs_get_system_info

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_system_info(ctx, model=None, include_stations=False)

        assert "STOFS-2D-Global" in result
        assert "STOFS-3D-Atlantic" in result
        assert "ADCIRC" in result
        assert "SCHISM" in result

        await client.close()

    @pytest.mark.asyncio
    async def test_system_info_single_model(self):
        """stofs_get_system_info with a specific model should only return that model."""
        from stofs_mcp.tools.discovery import stofs_get_system_info

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_system_info(
            ctx, model=STOFSModel.GLOBAL_2D, include_stations=False
        )

        assert "STOFS-2D-Global" in result
        assert "STOFS-3D-Atlantic" not in result

        await client.close()

    @pytest.mark.asyncio
    async def test_system_info_with_stations(self):
        """stofs_get_system_info with include_stations=True should list stations."""
        from stofs_mcp.tools.discovery import stofs_get_system_info

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_system_info(ctx, model=None, include_stations=True)

        assert "Station Registry" in result
        assert "8518750" in result  # The Battery
        assert "The Battery" in result

        await client.close()

    @pytest.mark.asyncio
    async def test_system_info_contains_opendap_urls(self):
        """stofs_get_system_info should include OPeNDAP URLs in the output."""
        from stofs_mcp.tools.discovery import stofs_get_system_info

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_system_info(ctx, model=None)

        assert "nomads.ncep.noaa.gov/dods/stofs_2d_glo" in result
        assert "nomads.ncep.noaa.gov/dods/stofs_3d_atl" in result

        await client.close()

    @pytest.mark.asyncio
    async def test_system_info_contains_datum_note(self):
        """stofs_get_system_info should include the datum warning note."""
        from stofs_mcp.tools.discovery import stofs_get_system_info

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_system_info(ctx, model=None)

        assert "Datum note" in result
        assert "LMSL" in result
        assert "NAVD88" in result

        await client.close()


# ---------------------------------------------------------------------------
# Test: stofs_list_stations — uses hardcoded station registry
# ---------------------------------------------------------------------------


class TestListStations:
    """Tests for the stofs_list_stations tool function."""

    @pytest.mark.asyncio
    async def test_list_stations_default(self):
        """stofs_list_stations with no filters should return up to 20 stations."""
        from stofs_mcp.tools.discovery import stofs_list_stations

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_list_stations(ctx, model=STOFSModel.GLOBAL_2D)

        assert "STOFS Output Stations" in result
        assert "8518750" in result  # The Battery should be in default list

        await client.close()

    @pytest.mark.asyncio
    async def test_list_stations_filter_by_state(self):
        """stofs_list_stations should filter stations by state abbreviation."""
        from stofs_mcp.tools.discovery import stofs_list_stations

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_list_stations(ctx, model=STOFSModel.GLOBAL_2D, state="FL")

        assert "FL" in result
        assert "Key West" in result
        # Should not include non-FL stations like The Battery
        assert "The Battery" not in result

        await client.close()

    @pytest.mark.asyncio
    async def test_list_stations_filter_by_region(self):
        """stofs_list_stations should filter stations by region."""
        from stofs_mcp.tools.discovery import stofs_list_stations
        from stofs_mcp.models import Region

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_list_stations(
            ctx, model=STOFSModel.GLOBAL_2D, region=Region.GULF
        )

        assert "Galveston" in result or "Grand Isle" in result
        # Non-Gulf stations should not appear
        assert "The Battery" not in result

        await client.close()

    @pytest.mark.asyncio
    async def test_list_stations_proximity(self):
        """stofs_list_stations should filter stations by proximity to a point."""
        from stofs_mcp.tools.discovery import stofs_list_stations

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        # Near NYC
        result = await stofs_list_stations(
            ctx,
            model=STOFSModel.GLOBAL_2D,
            near_lat=40.7,
            near_lon=-74.0,
            radius_km=50.0,
        )

        assert "Distance (km)" in result
        assert "The Battery" in result

        await client.close()

    @pytest.mark.asyncio
    async def test_list_stations_no_match(self):
        """stofs_list_stations should handle the case when no stations match."""
        from stofs_mcp.tools.discovery import stofs_list_stations

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        # A point in the middle of the Atlantic Ocean, far from any station
        result = await stofs_list_stations(
            ctx,
            model=STOFSModel.GLOBAL_2D,
            near_lat=35.0,
            near_lon=-40.0,
            radius_km=10.0,
        )

        assert "No STOFS stations found" in result

        await client.close()

    @pytest.mark.asyncio
    async def test_list_stations_limit(self):
        """stofs_list_stations should respect the limit parameter."""
        from stofs_mcp.tools.discovery import stofs_list_stations

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_list_stations(ctx, model=STOFSModel.GLOBAL_2D, limit=3)

        assert "Showing 3 of" in result

        await client.close()


# ---------------------------------------------------------------------------
# Test: build_station_url and build_opendap_url — pure functions
# ---------------------------------------------------------------------------


class TestBuildUrls:
    """Tests for the STOFSClient URL builder methods."""

    def test_build_station_url_2d_global_cwl(self):
        """build_station_url for 2d_global/cwl should point to the correct S3 path."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_station_url("2d_global", "20260303", "12", "cwl")
        assert url == (
            "https://noaa-gestofs-pds.s3.amazonaws.com/"
            "stofs_2d_glo.20260303/stofs_2d_glo.t12z.points.cwl.nc"
        )

    def test_build_station_url_2d_global_swl(self):
        """build_station_url for 2d_global/swl should use the swl product name."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_station_url("2d_global", "20260303", "06", "swl")
        assert "t06z.points.swl.nc" in url

    def test_build_station_url_2d_global_htp(self):
        """build_station_url for 2d_global/htp should use the htp product name."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_station_url("2d_global", "20260303", "00", "htp")
        assert "t00z.points.htp.nc" in url

    def test_build_station_url_3d_atlantic(self):
        """build_station_url for 3d_atlantic should always use cwl product."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_station_url("3d_atlantic", "20260303", "12", "cwl")
        assert "noaa-nos-stofs3d-pds.s3.amazonaws.com" in url
        assert "STOFS-3D-Atl/stofs_3d_atl.20260303" in url
        assert "t12z.points.cwl.nc" in url

    def test_build_station_url_invalid_model(self):
        """build_station_url should raise ValueError for an unrecognized model."""
        client = STOFSClient(backoff_factor=0)
        with pytest.raises(ValueError, match="Unknown model"):
            client.build_station_url("invalid", "20260303", "12", "cwl")

    def test_build_opendap_url_2d_global_default_region(self):
        """build_opendap_url for 2d_global should default to conus.east region."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_opendap_url("2d_global", "20260303", "12")
        assert "nomads.ncep.noaa.gov/dods/stofs_2d_glo" in url
        assert "stofs_2d_glo_conus.east_12z" in url

    def test_build_opendap_url_2d_global_custom_region(self):
        """build_opendap_url should accept a custom region parameter."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_opendap_url("2d_global", "20260303", "06", "hawaii")
        assert "stofs_2d_glo_hawaii_06z" in url

    def test_build_opendap_url_3d_atlantic(self):
        """build_opendap_url for 3d_atlantic should use the stofs_3d_atl path."""
        client = STOFSClient(backoff_factor=0)
        url = client.build_opendap_url("3d_atlantic", "20260303", "12")
        assert "nomads.ncep.noaa.gov/dods/stofs_3d_atl" in url
        assert "stofs_3d_atl_conus.east_12z" in url

    def test_build_opendap_url_invalid_model(self):
        """build_opendap_url should raise ValueError for an unrecognized model."""
        client = STOFSClient(backoff_factor=0)
        with pytest.raises(ValueError, match="Unknown model"):
            client.build_opendap_url("invalid", "20260303", "12")


# ---------------------------------------------------------------------------
# Test: CO-OPS observation fetching — mock HTTP responses
# ---------------------------------------------------------------------------


class TestFetchCoopsObservations:
    """Tests for the STOFSClient.fetch_coops_observations method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_observations_success(self):
        """fetch_coops_observations should parse a valid CO-OPS JSON response."""
        fixture = load_fixture("coops_observations.json")

        respx.get(COOPS_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        client = STOFSClient(backoff_factor=0)
        result = await client.fetch_coops_observations(
            "8518750", "20250301", "20250302", datum="MSL"
        )

        assert "data" in result
        assert len(result["data"]) == 5
        assert result["data"][0]["t"] == "2025-03-01 00:00"
        assert result["data"][0]["v"] == "0.612"

        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_observations_api_error(self):
        """fetch_coops_observations should raise ValueError when CO-OPS returns an error."""
        fixture = load_fixture("coops_error.json")

        respx.get(COOPS_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        client = STOFSClient(backoff_factor=0)
        with pytest.raises(ValueError, match="CO-OPS API error"):
            await client.fetch_coops_observations(
                "0000000", "20250301", "20250302", datum="MSL"
            )

        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_observations_http_error(self):
        """fetch_coops_observations should raise on HTTP 500 error."""
        respx.get(COOPS_API_BASE).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        client = STOFSClient(backoff_factor=0)
        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch_coops_observations(
                "8518750", "20250301", "20250302", datum="MSL"
            )

        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_observations_sends_correct_params(self):
        """fetch_coops_observations should send the correct query parameters."""
        fixture = load_fixture("coops_observations.json")

        route = respx.get(COOPS_API_BASE).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        client = STOFSClient(backoff_factor=0)
        await client.fetch_coops_observations(
            "8518750", "20250301 00:00", "20250302 00:00", datum="NAVD"
        )

        assert route.called
        request = route.calls.last.request
        params = dict(request.url.params)
        assert params["station"] == "8518750"
        assert params["product"] == "water_level"
        assert params["datum"] == "NAVD"
        assert params["units"] == "metric"
        assert params["format"] == "json"
        assert params["application"] == "stofs_mcp"

        await client.close()


# ---------------------------------------------------------------------------
# Test: check_file_exists — mock S3 HEAD requests
# ---------------------------------------------------------------------------


class TestCheckFileExists:
    """Tests for the STOFSClient.check_file_exists method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_file_exists_returns_true_on_200(self):
        """check_file_exists should return True when S3 returns HTTP 200."""
        test_url = "https://noaa-gestofs-pds.s3.amazonaws.com/test.nc"
        respx.head(test_url).mock(return_value=httpx.Response(200))

        client = STOFSClient(backoff_factor=0)
        result = await client.check_file_exists(test_url)
        assert result is True
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_file_exists_returns_false_on_404(self):
        """check_file_exists should return False when S3 returns HTTP 404."""
        test_url = "https://noaa-gestofs-pds.s3.amazonaws.com/test.nc"
        respx.head(test_url).mock(return_value=httpx.Response(404))

        client = STOFSClient(backoff_factor=0)
        result = await client.check_file_exists(test_url)
        assert result is False
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_file_exists_returns_false_on_connection_error(self):
        """check_file_exists should return False on connection errors."""
        test_url = "https://noaa-gestofs-pds.s3.amazonaws.com/test.nc"
        respx.head(test_url).mock(side_effect=httpx.ConnectError("Connection refused"))

        client = STOFSClient(backoff_factor=0)
        result = await client.check_file_exists(test_url)
        assert result is False
        await client.close()


# ---------------------------------------------------------------------------
# Test: check_opendap_available — mock NOMADS .das requests
# ---------------------------------------------------------------------------


class TestCheckOpendapAvailable:
    """Tests for the STOFSClient.check_opendap_available method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_opendap_available_returns_true_on_valid_response(self):
        """check_opendap_available should return (True, 'ok') for valid .das content."""
        base_url = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/20260303/stofs_2d_glo_conus.east_12z"
        respx.get(f"{base_url}.das").mock(
            return_value=httpx.Response(
                200, text="Attributes {\n    NC_GLOBAL {\n    }\n}"
            )
        )

        client = STOFSClient(backoff_factor=0)
        available, reason = await client.check_opendap_available(base_url)
        assert available is True
        assert reason == "ok"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_opendap_available_returns_false_on_error_body(self):
        """check_opendap_available should return (False, 'missing') when .das body starts with 'Error {'."""
        base_url = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/20260303/stofs_2d_glo_conus.east_12z"
        respx.get(f"{base_url}.das").mock(
            return_value=httpx.Response(
                200, text='Error {\n    code = 404;\n    message = "Not Found";\n}'
            )
        )

        client = STOFSClient(backoff_factor=0)
        available, reason = await client.check_opendap_available(base_url)
        assert available is False
        assert reason == "missing"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_opendap_available_returns_false_on_http_error(self):
        """check_opendap_available should return (False, 'http_error') on HTTP 500."""
        base_url = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/20260303/stofs_2d_glo_conus.east_12z"
        respx.get(f"{base_url}.das").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        client = STOFSClient(backoff_factor=0)
        available, reason = await client.check_opendap_available(base_url)
        assert available is False
        assert reason == "http_error"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_opendap_available_returns_false_on_connection_error(self):
        """check_opendap_available should return (False, 'network_error') on connection failure."""
        base_url = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/20260303/stofs_2d_glo_conus.east_12z"
        respx.get(f"{base_url}.das").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        client = STOFSClient(backoff_factor=0)
        available, reason = await client.check_opendap_available(base_url)
        assert available is False
        assert reason == "network_error"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_opendap_available_detects_nomads_retirement(self):
        """check_opendap_available should flag NOMADS retirement HTML as (False, 'retired')."""
        base_url = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo/20260303/stofs_2d_glo_conus.east_12z"
        html = "<!doctype html><html><head><title>Request for OpenDAP Data</title>"
        respx.get(f"{base_url}.das").mock(return_value=httpx.Response(200, text=html))

        client = STOFSClient(backoff_factor=0)
        available, reason = await client.check_opendap_available(base_url)
        assert available is False
        assert reason == "retired"
        await client.close()


# ---------------------------------------------------------------------------
# Test: resolve_latest_cycle — mock S3 HEAD for cycle resolution
# ---------------------------------------------------------------------------


class TestResolveLatestCycle:
    """Tests for the resolve_latest_cycle utility function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_finds_latest_cycle(self):
        """resolve_latest_cycle should return the first cycle with a 200 response."""
        # Today's 18z and 12z are available
        respx.head(url__regex=r".*t18z\.points\.cwl\.nc$").mock(
            return_value=httpx.Response(200)
        )
        respx.head(url__regex=r".*t12z\.points\.cwl\.nc$").mock(
            return_value=httpx.Response(200)
        )
        respx.head(url__regex=r".*t06z\.points\.cwl\.nc$").mock(
            return_value=httpx.Response(404)
        )
        respx.head(url__regex=r".*t00z\.points\.cwl\.nc$").mock(
            return_value=httpx.Response(404)
        )

        client = STOFSClient(backoff_factor=0)
        result = await resolve_latest_cycle(client, "2d_global", num_days=1)

        assert result is not None
        date_str, cycle_str = result
        # MODEL_CYCLES for 2d_global checks 18, 12, 06, 00 in order — 18z should be found first
        assert cycle_str == "18"

        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_returns_none_when_nothing_available(self):
        """resolve_latest_cycle should return None when no cycles exist."""
        respx.head(url__regex=r".*noaa-gestofs-pds.*").mock(
            return_value=httpx.Response(404)
        )

        client = STOFSClient(backoff_factor=0)
        result = await resolve_latest_cycle(client, "2d_global", num_days=2)
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_3d_atlantic_only_checks_12z(self):
        """resolve_latest_cycle for 3d_atlantic should only check the 12z cycle."""
        respx.head(url__regex=r".*t12z\.points\.cwl\.nc$").mock(
            return_value=httpx.Response(200)
        )

        client = STOFSClient(backoff_factor=0)
        result = await resolve_latest_cycle(client, "3d_atlantic", num_days=1)

        assert result is not None
        _, cycle_str = result
        assert cycle_str == "12"

        await client.close()


# ---------------------------------------------------------------------------
# Test: resolve_cycle (centralized in utils.py) — explicit date/hour path.
# The per-tool _resolve_cycle copies were removed; both forecast and
# validation now share stofs_mcp.utils.resolve_cycle.
# ---------------------------------------------------------------------------


class TestResolveCycleExplicit:
    """Tests for the shared resolve_cycle helper (explicit date/hour inputs)."""

    @pytest.mark.asyncio
    async def test_explicit_date_and_hour(self):
        """resolve_cycle should return the parsed date and hour when both are provided."""
        from stofs_mcp.utils import resolve_cycle

        client = STOFSClient(backoff_factor=0)
        result = await resolve_cycle(client, "2d_global", "2026-03-03", "12")

        assert result == ("20260303", "12")
        await client.close()

    @pytest.mark.asyncio
    async def test_explicit_date_yyyymmdd_format(self):
        """resolve_cycle should accept YYYYMMDD format for the date."""
        from stofs_mcp.utils import resolve_cycle

        client = STOFSClient(backoff_factor=0)
        result = await resolve_cycle(client, "2d_global", "20260303", "06")

        assert result == ("20260303", "06")
        await client.close()

    @pytest.mark.asyncio
    async def test_explicit_date_zero_pads_hour(self):
        """resolve_cycle should zero-pad a single-digit hour string."""
        from stofs_mcp.utils import resolve_cycle

        client = STOFSClient(backoff_factor=0)
        result = await resolve_cycle(client, "2d_global", "2026-03-03", "6")

        assert result == ("20260303", "06")
        await client.close()

    @pytest.mark.asyncio
    async def test_invalid_date_returns_none(self):
        """resolve_cycle should return None for an unparseable date."""
        from stofs_mcp.utils import resolve_cycle

        client = STOFSClient(backoff_factor=0)
        result = await resolve_cycle(client, "2d_global", "bad-date", "12")

        assert result is None
        await client.close()


# ---------------------------------------------------------------------------
# Test: stofs_get_station_forecast — no-cycle-found path
# ---------------------------------------------------------------------------


class TestGetStationForecastNoCycle:
    """Tests for stofs_get_station_forecast when no cycle is available."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_error_when_no_cycle_found(self):
        """stofs_get_station_forecast should return an informative message when no cycle exists."""
        from stofs_mcp.tools.forecast import stofs_get_station_forecast

        # All HEAD requests 404
        respx.head(url__regex=r".*").mock(return_value=httpx.Response(404))

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_station_forecast(
            ctx,
            station_id="8518750",
            model=STOFSModel.GLOBAL_2D,
        )

        assert "cycles found" in result.lower() or "stofs_list_cycles" in result.lower()
        await client.close()

    @pytest.mark.asyncio
    async def test_3d_atlantic_rejects_htp_product(self):
        """stofs_get_station_forecast should reject non-cwl products for 3d_atlantic."""
        from stofs_mcp.tools.forecast import stofs_get_station_forecast

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_station_forecast(
            ctx,
            station_id="8518750",
            model=STOFSModel.ATLANTIC_3D,
            product=STOFSProduct.HTP,
        )

        assert "only provides" in result.lower() or "cwl" in result.lower()
        await client.close()


# ---------------------------------------------------------------------------
# Test: stofs_get_gridded_forecast — OPeNDAP not available path
# ---------------------------------------------------------------------------


class TestGetGriddedForecastErrors:
    """Tests for stofs_get_gridded_forecast error paths."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_error_when_no_cycle_found(self):
        """stofs_get_gridded_forecast should return an error when no cycle is available."""
        from stofs_mcp.tools.forecast import stofs_get_gridded_forecast

        # All HEAD requests 404 (no cycle)
        respx.head(url__regex=r".*").mock(return_value=httpx.Response(404))

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_gridded_forecast(ctx, latitude=40.7, longitude=-74.0)

        assert "No STOFS cycles found" in result
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_error_when_opendap_unavailable(self):
        """stofs_get_gridded_forecast should return a message when NOMADS is down."""
        from stofs_mcp.tools.forecast import stofs_get_gridded_forecast

        # Cycle exists on S3
        respx.head(url__regex=r".*noaa-gestofs-pds.*t18z.*").mock(
            return_value=httpx.Response(200)
        )
        respx.head(url__regex=r".*noaa-gestofs-pds.*t12z.*").mock(
            return_value=httpx.Response(404)
        )
        respx.head(url__regex=r".*noaa-gestofs-pds.*t06z.*").mock(
            return_value=httpx.Response(404)
        )
        respx.head(url__regex=r".*noaa-gestofs-pds.*t00z.*").mock(
            return_value=httpx.Response(404)
        )

        # OPeNDAP .das returns "Error {" body
        respx.get(url__regex=r".*nomads.*\.das").mock(
            return_value=httpx.Response(
                200, text='Error {\n    code = 404;\n    message = "Not Found";\n}'
            )
        )

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_get_gridded_forecast(ctx, latitude=40.7, longitude=-74.0)

        assert "OPeNDAP" in result
        assert "not available" in result.lower() or "unavailable" in result.lower()
        await client.close()


# ---------------------------------------------------------------------------
# Test: stofs_compare_with_observations — CO-OPS fetch error path
# ---------------------------------------------------------------------------


class TestCompareWithObservationsErrors:
    """Tests for stofs_compare_with_observations error handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_error_when_no_cycle_found(self):
        """stofs_compare_with_observations should return an error when no cycle exists."""
        from stofs_mcp.tools.validation import stofs_compare_with_observations

        respx.head(url__regex=r".*").mock(return_value=httpx.Response(404))

        client = STOFSClient(backoff_factor=0)
        ctx = make_ctx(client)

        result = await stofs_compare_with_observations(ctx, station_id="8518750")

        assert "No STOFS cycles found" in result
        await client.close()


# ---------------------------------------------------------------------------
# Test: stofs_compare_with_observations — summary-first, hourly-capped output
# ---------------------------------------------------------------------------


def _six_minute_times(start: str, hours: int) -> list[str]:
    """Consecutive 6-minute timestamps covering ``hours`` from ``start``."""
    from datetime import datetime, timedelta

    t0 = datetime.strptime(start, "%Y-%m-%d %H:%M")
    return [
        (t0 + timedelta(minutes=6 * i)).strftime("%Y-%m-%d %H:%M")
        for i in range(hours * 10 + 1)
    ]


class TestCompareWithObservationsOutput:
    """stofs_compare_with_observations leads with a summary and caps the series."""

    # 30 h of 6-minute data starting at the 2022-09-27 18z file's first step.
    TIMES = _six_minute_times("2022-09-27 18:06", 30)
    # Observed peaks 1.0 m at index 200; forecast peaks 0.8 m 2 h later.
    OBSERVED = [1.0 - abs(i - 200) / 200 for i in range(len(TIMES))]
    FORECAST = [0.8 - abs(i - 220) / 250 for i in range(len(TIMES))]

    def _ctx(self, monkeypatch):
        """Mock ctx whose station file and CO-OPS fetch return the series above."""
        from unittest.mock import AsyncMock

        from stofs_mcp.tools import validation

        client = STOFSClient(backoff_factor=0)
        client.download_netcdf = AsyncMock(return_value=None)
        client.fetch_coops_observations = AsyncMock(
            return_value={
                "data": [
                    {"t": t, "v": f"{v:.3f}"} for t, v in zip(self.TIMES, self.OBSERVED)
                ]
            }
        )
        monkeypatch.setattr(
            validation,
            "parse_station_netcdf",
            lambda path, station_id: {"times": self.TIMES, "values": self.FORECAST},
        )
        return make_ctx(client)

    async def _run(self, monkeypatch, **kwargs):
        from stofs_mcp.tools.validation import stofs_compare_with_observations

        return await stofs_compare_with_observations(
            self._ctx(monkeypatch),
            station_id="8725520",
            cycle_date="2022-09-27",
            cycle_hour="18",
            hours_to_compare=30,
            **kwargs,
        )

    @pytest.mark.asyncio
    async def test_json_defaults_to_hourly_with_summary_first(self, monkeypatch):
        """JSON returns hourly points after the summary; stats use every point."""
        parsed = json.loads(await self._run(monkeypatch, response_format="json"))

        keys = list(parsed)
        assert keys.index("summary") < keys.index("comparison")
        assert keys.index("statistics") < keys.index("comparison")
        assert parsed["model_label"] == "ESTOFS-Global (STOFS-2D predecessor)"
        assert parsed["resolution"] == "hourly"
        assert parsed["n_points"] == parsed["total_points"] == 31
        assert parsed["truncated"] is False
        assert parsed["statistics"]["n"] == 301
        assert all(c["time"].endswith(":00") for c in parsed["comparison"][1:])

        summary = parsed["summary"]
        assert summary["observed_peak_m"] == pytest.approx(1.0)
        assert summary["observed_peak_time"] == "2022-09-28 14:06"
        assert summary["forecast_peak_time"] == "2022-09-28 16:06"
        assert summary["peak_error_m"] == pytest.approx(-0.2)
        assert summary["peak_timing_error_hours"] == pytest.approx(2.0)
        assert "bias_m" in summary and "rmse_m" in summary
        assert "resolution_note" in parsed and "retrieved_at" in parsed

    @pytest.mark.asyncio
    async def test_full_resolution_returns_every_point(self, monkeypatch):
        """full_resolution=True opts in to all 6-minute points."""
        parsed = json.loads(
            await self._run(monkeypatch, response_format="json", full_resolution=True)
        )
        assert parsed["resolution"] == "6-minute"
        assert parsed["n_points"] == 301
        assert "resolution_note" not in parsed

    @pytest.mark.asyncio
    async def test_max_points_truncates_with_hint(self, monkeypatch):
        """max_points caps the series and stamps the truncation envelope."""
        parsed = json.loads(
            await self._run(
                monkeypatch,
                response_format="json",
                full_resolution=True,
                max_points=50,
            )
        )
        assert parsed["truncated"] is True
        assert parsed["n_points"] == 50
        assert parsed["total_points"] == 301
        assert "first 50 of 301" in parsed["hint"]
        assert parsed["comparison"][0]["time"] == "2022-09-27 18:06"

    @pytest.mark.asyncio
    async def test_markdown_summary_precedes_series(self, monkeypatch):
        """Markdown puts the peak table and statistics before the hourly rows."""
        result = await self._run(monkeypatch)
        assert result.index("Observed peak") < result.index("Time Series Comparison")
        assert result.index("RMSE") < result.index("Time Series Comparison (hourly)")
        assert "Showing 31 of 31 hourly points" in result
        assert "full_resolution=true" in result


# ---------------------------------------------------------------------------
# Test: get_opendap_region — coverage mapping
# ---------------------------------------------------------------------------


class TestGetOpendapRegion:
    """Tests for the get_opendap_region geographic mapper."""

    def test_nyc_maps_to_conus_east(self):
        """New York City should map to conus.east."""
        assert get_opendap_region(40.7, -74.0) == "conus.east"

    def test_miami_maps_to_conus_east(self):
        """Miami should map to conus.east."""
        assert get_opendap_region(25.8, -80.2) == "conus.east"

    def test_galveston_maps_to_conus_east(self):
        """Galveston, TX should map to conus.east (east of -100W)."""
        assert get_opendap_region(29.3, -94.8) == "conus.east"

    def test_san_francisco_maps_to_conus_west(self):
        """San Francisco should map to conus.west."""
        assert get_opendap_region(37.8, -122.4) == "conus.west"

    def test_seattle_maps_to_conus_west(self):
        """Seattle should map to conus.west."""
        assert get_opendap_region(47.6, -122.3) == "conus.west"

    def test_honolulu_maps_to_hawaii(self):
        """Honolulu should map to hawaii."""
        assert get_opendap_region(21.3, -157.9) == "hawaii"

    def test_san_juan_maps_to_puertori(self):
        """San Juan, Puerto Rico should map to puertori."""
        assert get_opendap_region(18.5, -66.1) == "puertori"

    def test_guam_maps_to_guam(self):
        """Guam should map to guam."""
        assert get_opendap_region(13.5, 144.8) == "guam"

    def test_anchorage_maps_to_alaska(self):
        """Anchorage should map to alaska."""
        assert get_opendap_region(61.2, -149.9) == "alaska"

    def test_open_ocean_maps_to_northpacific(self):
        """A point in the open Pacific should fall back to northpacific."""
        assert get_opendap_region(10.0, -150.0) == "northpacific"


# ---------------------------------------------------------------------------
# Test: error handler — handle_stofs_error
# ---------------------------------------------------------------------------


class TestHandleStofsError:
    """Tests for the handle_stofs_error utility."""

    def test_404_mentions_stofs_list_cycles(self):
        """handle_stofs_error for HTTP 404 should suggest using stofs_list_cycles."""
        response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        err = httpx.HTTPStatusError(
            "not found", request=response.request, response=response
        )
        result = handle_stofs_error(err, model="2d_global")
        assert "404" in result
        assert "stofs_list_cycles" in result

    def test_403_mentions_archived(self):
        """handle_stofs_error for HTTP 403 should mention archived data."""
        response = httpx.Response(403, request=httpx.Request("GET", "http://test"))
        err = httpx.HTTPStatusError(
            "forbidden", request=response.request, response=response
        )
        result = handle_stofs_error(err)
        assert "403" in result
        assert "archived" in result.lower()

    def test_timeout_mentions_retry(self):
        """handle_stofs_error for timeout should suggest retrying."""
        err = httpx.ReadTimeout("timed out")
        result = handle_stofs_error(err)
        assert "timed out" in result.lower()
        assert "try again" in result.lower()

    def test_value_error_passes_through(self):
        """handle_stofs_error for ValueError should return the message as-is."""
        err = ValueError("Station 'XYZ' not found")
        result = handle_stofs_error(err)
        assert "Station 'XYZ' not found" in result

    def test_includes_model_label(self):
        """handle_stofs_error should include the model name in the message."""
        err = httpx.ReadTimeout("timed out")
        result = handle_stofs_error(err, model="3d_atlantic")
        assert "3d_atlantic" in result

    def test_generic_error_includes_type_name(self):
        """handle_stofs_error for an unexpected error should include the exception type."""
        err = RuntimeError("something went wrong")
        result = handle_stofs_error(err)
        assert "RuntimeError" in result
        assert "something went wrong" in result


# ---------------------------------------------------------------------------
# Test: format_timeseries_table — output formatting
# ---------------------------------------------------------------------------


class TestFormatTimeseriesTable:
    """Tests for the format_timeseries_table formatter."""

    def test_basic_output_has_table_headers(self):
        """format_timeseries_table should produce a markdown table with headers."""
        times = ["2026-03-03 00:00", "2026-03-03 01:00"]
        values = [0.5, 0.6]
        result = format_timeseries_table(times, values, title="Test Forecast")
        assert "## Test Forecast" in result
        assert "| Time (UTC) | Water Level (m) |" in result
        assert "0.500" in result
        assert "0.600" in result

    def test_empty_data_shows_no_data_message(self):
        """format_timeseries_table with empty data should show a 'no data' message."""
        result = format_timeseries_table([], [], title="Empty")
        assert "No data" in result

    def test_includes_summary_stats(self):
        """format_timeseries_table should include min/max/mean summary."""
        times = ["2026-03-03 00:00", "2026-03-03 01:00", "2026-03-03 02:00"]
        values = [0.1, 0.5, 0.3]
        result = format_timeseries_table(times, values)
        assert "Min" in result
        assert "Max" in result
        assert "Mean" in result
        assert "0.100" in result  # min
        assert "0.500" in result  # max

    def test_subsamples_large_datasets(self):
        """format_timeseries_table should subsample when data exceeds max_rows."""
        times = [f"2026-03-03 {h:02d}:00" for h in range(24)] * 10  # 240 rows
        values = [0.5] * 240
        result = format_timeseries_table(times, values, max_rows=50)
        assert "every" in result.lower()

    def test_includes_metadata_lines(self):
        """format_timeseries_table should show metadata lines below the title."""
        times = ["2026-03-03 00:00"]
        values = [0.5]
        result = format_timeseries_table(
            times,
            values,
            title="Test",
            metadata_lines=["Model: STOFS-2D-Global", "Datum: LMSL"],
        )
        assert "Model: STOFS-2D-Global" in result
        assert "Datum: LMSL" in result

    def test_custom_source_attribution(self):
        """format_timeseries_table should include the custom source string."""
        times = ["2026-03-03 00:00"]
        values = [0.5]
        result = format_timeseries_table(
            times, values, source="Custom Source Attribution"
        )
        assert "Custom Source Attribution" in result


# ---------------------------------------------------------------------------
# Test: compute_validation_stats used by comparison tool
# ---------------------------------------------------------------------------


class TestComputeValidationStatsForComparison:
    """Tests for compute_validation_stats as used by the comparison tool."""

    def test_identical_series_gives_zero_error(self):
        """Identical forecast and observation arrays should give zero error metrics."""
        f = [0.5, 0.6, 0.7, 0.8]
        o = [0.5, 0.6, 0.7, 0.8]
        stats = compute_validation_stats(f, o)
        assert stats["bias"] == pytest.approx(0.0)
        assert stats["rmse"] == pytest.approx(0.0)
        assert stats["mae"] == pytest.approx(0.0)
        assert stats["peak_error"] == pytest.approx(0.0)
        assert stats["correlation"] == pytest.approx(1.0)
        assert stats["n"] == 4

    def test_known_bias(self):
        """A constant 0.05m offset should produce a 0.05m bias."""
        f = [0.55, 0.65, 0.75]
        o = [0.50, 0.60, 0.70]
        stats = compute_validation_stats(f, o)
        assert stats["bias"] == pytest.approx(0.05, abs=1e-4)

    def test_empty_arrays_return_none_stats(self):
        """Empty forecast/observation arrays should return None for all metrics."""
        stats = compute_validation_stats([], [])
        assert stats["bias"] is None
        assert stats["rmse"] is None
        assert stats["n"] == 0


# ---------------------------------------------------------------------------
# Test: align_timeseries used by comparison tool
# ---------------------------------------------------------------------------


class TestAlignTimeseriesForComparison:
    """Tests for align_timeseries as used by the comparison tool."""

    def test_exact_timestamps_align_fully(self):
        """Identical timestamp arrays should produce full alignment."""
        times = ["2026-03-03 00:00", "2026-03-03 00:06", "2026-03-03 00:12"]
        f_vals = [1.0, 2.0, 3.0]
        o_vals = [1.1, 2.1, 3.1]
        ct, af, ao = align_timeseries(times, f_vals, times, o_vals)
        assert len(ct) == 3
        assert af == f_vals
        assert ao == o_vals

    def test_offset_beyond_tolerance_drops_points(self):
        """Points with timestamps beyond the tolerance should be dropped."""
        f_times = ["2026-03-03 00:00"]
        f_vals = [1.0]
        o_times = ["2026-03-03 00:30"]
        o_vals = [1.1]
        ct, af, ao = align_timeseries(
            f_times, f_vals, o_times, o_vals, tolerance_minutes=3
        )
        assert len(ct) == 0

    def test_partial_overlap(self):
        """Only overlapping timestamps should be aligned."""
        f_times = ["2026-03-03 00:00", "2026-03-03 01:00", "2026-03-03 02:00"]
        f_vals = [1.0, 2.0, 3.0]
        o_times = ["2026-03-03 01:00", "2026-03-03 02:00"]
        o_vals = [2.1, 3.1]
        ct, af, ao = align_timeseries(f_times, f_vals, o_times, o_vals)
        assert len(ct) == 2
        assert af == [2.0, 3.0]
        assert ao == [2.1, 3.1]


def test_cap_series_json_caps_and_signals():
    """_cap_series_json caps the times/values series, signals it, stamps retrieved_at."""
    import json

    from stofs_mcp.tools.forecast import _cap_series_json

    parsed = json.loads(
        _cap_series_json(
            {"times": list(range(2500)), "values": list(range(2500))}, max_points=2000
        )
    )
    assert parsed["truncated"] is True
    assert parsed["n_points"] == 2000
    assert parsed["total_points"] == 2500
    assert len(parsed["times"]) == 2000
    assert parsed["times"][0] == 0  # near-term head kept
    assert "retrieved_at" in parsed
    assert "first 2000 of 2500" in parsed["hint"]

    whole = json.loads(_cap_series_json({"times": [1, 2], "values": [3, 4]}))
    assert whole["truncated"] is False
    assert whole["total_points"] == 2
    assert "retrieved_at" in whole
    assert "hint" not in whole


@respx.mock
async def test_resolve_latest_cycle_is_cached():
    """A second resolve for the same model is served from cache (no new HEADs)."""
    route = respx.head(url__regex=r".*noaa-gestofs-pds.*").mock(
        return_value=httpx.Response(200)
    )
    c = STOFSClient()
    try:
        first = await resolve_latest_cycle(c, "2d_global")
        second = await resolve_latest_cycle(c, "2d_global")
    finally:
        await c.close()
    assert first is not None and first == second
    assert route.call_count == 1  # second resolve hit the cache


@respx.mock
async def test_resolve_latest_cycle_ttl_zero_disables_cache():
    """cycle_cache_ttl=0 disables the cache — each resolve re-sweeps S3."""
    route = respx.head(url__regex=r".*noaa-gestofs-pds.*").mock(
        return_value=httpx.Response(200)
    )
    c = STOFSClient(cycle_cache_ttl=0)
    try:
        await resolve_latest_cycle(c, "2d_global")
        await resolve_latest_cycle(c, "2d_global")
    finally:
        await c.close()
    assert route.call_count == 2
