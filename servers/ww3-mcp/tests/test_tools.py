"""Unit tests for WW3 MCP tool functions with mocked HTTP.

Tests the tool functions in ww3_mcp.tools.discovery, ww3_mcp.tools.buoy,
and ww3_mcp.tools.forecast using respx to mock all outbound HTTP requests
and fixture files for realistic responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from ww3_mcp.client import RetryTransport, WW3Client
from ww3_mcp.models import WAVE_GRIDS, WaveGrid

# ---------------------------------------------------------------------------
# Fixtures directory
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Load a fixture file and return its content as text."""
    return (FIXTURES_DIR / name).read_text()


def load_json_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Context helper
# ---------------------------------------------------------------------------


def make_ctx(client: WW3Client) -> MagicMock:
    """Create a mock MCP Context wired to the given WW3Client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"ww3_client": client}
    return ctx


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = WW3Client()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Create a WW3Client and close it after the test.

    backoff_factor=0 so the retry transport replays transient failures with
    no real delay, keeping the error-path tests fast.
    """
    c = WW3Client(backoff_factor=0)
    yield c
    await c.close()


# ============================================================================
# Test: ww3_list_grids (pure data, no HTTP)
# ============================================================================


class TestWw3ListGrids:
    """Tests for the ww3_list_grids tool function."""

    async def test_list_grids_markdown_returns_all_grids(self, client):
        """ww3_list_grids in markdown mode should mention every grid ID."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="markdown")

        assert "# GFS-Wave" in result
        for grid_id in WAVE_GRIDS:
            assert grid_id in result, f"Grid '{grid_id}' not found in output"

    async def test_list_grids_markdown_contains_table(self, client):
        """ww3_list_grids markdown output should include a table."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="markdown")

        assert "| Grid ID |" in result
        assert "| --- |" in result

    async def test_list_grids_json_returns_valid_json(self, client):
        """ww3_list_grids JSON mode should return parseable JSON with all grids."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="json")

        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == len(WAVE_GRIDS)

    async def test_list_grids_json_has_expected_keys(self, client):
        """Each grid in JSON output should have standard metadata keys."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="json")

        data = json.loads(result)
        expected = {
            "name",
            "short_name",
            "resolution",
            "domain_desc",
            "domain",
            "cycles",
            "forecast_hours",
            "variables",
        }
        for grid_id, info in data.items():
            missing = expected - set(info.keys())
            assert not missing, f"Grid '{grid_id}' JSON missing keys: {missing}"

    async def test_list_grids_includes_variables_section(self, client):
        """ww3_list_grids markdown should include wave variables table."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="markdown")

        assert "### Wave Variables" in result
        assert "HTSGW" in result


# ============================================================================
# Test: ww3_list_cycles (mocked S3 HEAD)
# ============================================================================


class TestWw3ListCycles:
    """Tests for the ww3_list_cycles tool, mocking AWS S3 HEAD requests."""

    @respx.mock
    async def test_list_cycles_all_available(self, client):
        """ww3_list_cycles should report 'Available' for cycles with 200 HEAD."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(
            ctx, grid=WaveGrid.GLOBAL_0P25, date="2026-03-01", num_days=1
        )

        assert "Available" in result
        assert "Not available" not in result

    @respx.mock
    async def test_list_cycles_none_available(self, client):
        """ww3_list_cycles should report 'Not available' when S3 returns 404."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(
            ctx, grid=WaveGrid.GLOBAL_0P25, date="2026-03-01", num_days=1
        )

        assert "Not available" in result
        assert "No cycles found" in result

    @respx.mock
    async def test_list_cycles_invalid_date_format(self, client):
        """ww3_list_cycles should return error for invalid date."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        ctx = make_ctx(client)
        result = await ww3_list_cycles(ctx, date="not-a-date")

        assert "Invalid date format" in result

    @respx.mock
    async def test_list_cycles_clamps_num_days(self, client):
        """ww3_list_cycles should clamp num_days to 1-7 range."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(ctx, date="2026-03-01", num_days=0)

        assert "1 day" in result

    @respx.mock
    async def test_list_cycles_connection_error_treated_as_unavailable(self, client):
        """ww3_list_cycles should treat connection errors as not available."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            side_effect=httpx.ConnectError("refused")
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(ctx, date="2026-03-01", num_days=1)

        assert "Not available" in result


# ============================================================================
# Test: ww3_find_buoys (mocked NDBC stations XML)
# ============================================================================


class TestWw3FindBuoys:
    """Tests for the ww3_find_buoys tool with mocked NDBC XML."""

    @respx.mock
    async def test_find_buoys_returns_nearby_stations(self, client):
        """ww3_find_buoys should return stations within radius."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        # Near Diamond Shoals (41025 at 35.006, -75.402)
        result = await ww3_find_buoys(
            ctx, latitude=35.0, longitude=-75.5, radius_km=100
        )

        assert "41025" in result

    @respx.mock
    async def test_find_buoys_no_results(self, client):
        """ww3_find_buoys should report no buoys when none are within radius."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        # Middle of nowhere
        result = await ww3_find_buoys(ctx, latitude=0.0, longitude=0.0, radius_km=10)

        assert "No NDBC buoys found" in result

    @respx.mock
    async def test_find_buoys_json_format(self, client):
        """ww3_find_buoys JSON output should be valid JSON with station list."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        result = await ww3_find_buoys(
            ctx, latitude=35.0, longitude=-75.5, radius_km=100, response_format="json"
        )

        data = json.loads(result)
        assert "stations" in data
        assert data["count"] >= 1

    @respx.mock
    async def test_find_buoys_sorted_by_distance(self, client):
        """ww3_find_buoys results should be sorted by distance (nearest first)."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        result = await ww3_find_buoys(
            ctx, latitude=35.0, longitude=-75.5, radius_km=10000, response_format="json"
        )

        data = json.loads(result)
        distances = [s["distance_km"] for s in data["stations"]]
        assert distances == sorted(distances)


# ============================================================================
# Test: ww3_get_buoy_observations (mocked NDBC realtime)
# ============================================================================


class TestWw3GetBuoyObservations:
    """Tests for the ww3_get_buoy_observations tool with mocked NDBC data."""

    @respx.mock
    async def test_get_buoy_observations_returns_data(self, client):
        """ww3_get_buoy_observations should return wave data from NDBC."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        text = load_fixture("ndbc_realtime.txt")
        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_observations(ctx, station_id="41025")

        assert "41025" in result
        assert "WVHT" in result

    @respx.mock
    async def test_get_buoy_observations_json(self, client):
        """ww3_get_buoy_observations JSON should return valid JSON."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        text = load_fixture("ndbc_realtime.txt")
        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_observations(
            ctx, station_id="41025", response_format="json"
        )

        data = json.loads(result)
        assert data["station_id"] == "41025"
        assert data["records"] > 0

    @respx.mock
    async def test_get_buoy_observations_404(self, client):
        """ww3_get_buoy_observations should handle 404 errors gracefully."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_observations(ctx, station_id="INVALID")

        assert "404" in result or "not found" in result.lower()

    @respx.mock
    async def test_get_buoy_observations_clamps_hours(self, client):
        """ww3_get_buoy_observations should clamp hours parameter."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        text = load_fixture("ndbc_realtime.txt")
        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        # hours=0 should be clamped to 1 (not rejected) and still render data
        result = await ww3_get_buoy_observations(ctx, station_id="41025", hours=0)
        assert "41025" in result  # clamped, parsed, and rendered observations
        assert "No observation data" not in result


# ============================================================================
# Test: ww3_get_buoy_history (mocked NDBC history)
# ============================================================================


class TestWw3GetBuoyHistory:
    """Tests for the ww3_get_buoy_history tool with mocked NDBC data."""

    @respx.mock
    async def test_get_buoy_history_returns_data(self, client):
        """ww3_get_buoy_history should return historical wave data."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        text = load_fixture("ndbc_realtime.txt")  # Reuse same format
        respx.get(url__startswith="https://www.ndbc.noaa.gov/view_text_file.php").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_history(ctx, station_id="41025", year=2023)

        assert "Historical Data" in result

    @respx.mock
    async def test_get_buoy_history_404(self, client):
        """ww3_get_buoy_history should handle missing year gracefully."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        respx.get(url__startswith="https://www.ndbc.noaa.gov/view_text_file.php").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_history(ctx, station_id="41025", year=1900)

        assert "404" in result or "not found" in result.lower()


NDBC_HISTORY_URL = "https://www.ndbc.noaa.gov/view_text_file.php"


def mock_history(fixture: str) -> None:
    """Serve a real-file excerpt (bytes as stored, CRLF kept) for the history URL."""
    respx.get(url__startswith=NDBC_HISTORY_URL).mock(
        return_value=httpx.Response(200, content=(FIXTURES_DIR / fixture).read_bytes())
    )


class TestWw3GetBuoyHistoryMissingCodesAndSummary:
    """ww3_get_buoy_history on real 41009 excerpts (fixtures/ndbc_history_SOURCES.md)."""

    @respx.mock
    async def test_summary_covers_every_row_not_the_returned_rows(self, client):
        """The WVHT summary is over all valid rows, even when few rows are returned."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        mock_history("ndbc_history_41009h2024_excerpt.txt")
        result = await ww3_get_buoy_history(
            make_ctx(client), "41009", 2024, max_records=3, response_format="json"
        )
        data = json.loads(result)
        assert [o["timestamp"] for o in data["observations"]] == [
            "2024-12-31 23:30",
            "2024-12-31 23:40",
            "2024-12-31 23:50",
        ]
        returned_max = max(
            o["WVHT"] for o in data["observations"] if o["WVHT"] is not None
        )
        assert returned_max == 0.68
        summary = data["summary"]
        assert summary["max"] == 6.32
        assert summary["max_time"] == "2024-10-10 08:10"
        assert summary["valid"] == 8
        assert summary["missing"] == 8
        assert summary["units"] == "m"
        assert summary["covers"] == "all 16 rows of the file"
        assert data["rows_in_file"] == 16

    @respx.mock
    async def test_record_cap_and_truncation_envelope(self, client):
        """At most max_records rows come back, with truncated/returned/total/hint."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        mock_history("ndbc_history_41009h2024_excerpt.txt")
        ctx = make_ctx(client)
        capped = json.loads(
            await ww3_get_buoy_history(
                ctx, "41009", 2024, max_records=3, response_format="json"
            )
        )
        assert len(capped["observations"]) == capped["returned"] == 3
        assert capped["records"] == 3
        assert capped["truncated"] is True
        assert capped["total"] == 16
        assert "hint" in capped
        assert "most recent 3 of 16 rows" in capped["row_selection"]

        full = json.loads(
            await ww3_get_buoy_history(
                ctx, "41009", 2024, max_records=100, response_format="json"
            )
        )
        assert full["truncated"] is False
        assert full["returned"] == full["total"] == len(full["observations"]) == 16
        assert "hint" not in full

    @respx.mock
    async def test_missing_codes_are_null_and_counted(self, client):
        """No 9-filled code reaches the caller as a value; each one is counted."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        mock_history("ndbc_history_41009h2024_excerpt.txt")
        data = json.loads(
            await ww3_get_buoy_history(
                make_ctx(client), "41009", 2024, max_records=100, response_format="json"
            )
        )
        obs = data["observations"]
        assert all(o["WVHT"] != 99.0 for o in obs)
        assert all(o["PRES"] != 9999.0 for o in obs)
        assert sum(o["WVHT"] is None for o in obs) == 8
        mv = data["missing_values"]
        assert mv["excluded_counts"]["WVHT"] == 8
        assert mv["codes"]["WVHT"] == "99.00"
        assert mv["documentation"] == "https://www.ndbc.noaa.gov/faq/measdes.shtml"
        assert data["units"]["WVHT"] == "m"
        assert data["timezone"] == "UTC"
        assert "retrieved_at" in data

    @respx.mock
    async def test_markdown_summary_over_whole_file(self, client):
        """Markdown states the whole-file maximum and which rows the table shows."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        mock_history("ndbc_history_41009h2024_excerpt.txt")
        result = await ww3_get_buoy_history(
            make_ctx(client), "41009", 2024, max_records=3
        )
        assert "max 6.32 m at 2024-10-10 08:10 UTC" in result
        assert "8 of 16 rows valid" in result
        assert "WVHT 8" in result  # missing values excluded, with counts
        assert "Showing the most recent 3 of 16 rows" in result
        assert "| 99.0 |" not in result

    @respx.mock
    async def test_older_file_format_through_the_tool(self, client):
        """A 1998 file (YY, WD/BAR, no minutes, CRLF) gives real timestamps."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        mock_history("ndbc_history_41009h1998_excerpt.txt")
        data = json.loads(
            await ww3_get_buoy_history(
                make_ctx(client), "41009", 1998, max_records=100, response_format="json"
            )
        )
        assert data["observations"][0]["timestamp"] == "1998-01-01 00:00"
        assert data["file_format"]["two_digit_year"] is True
        assert data["file_format"]["renamed"] == {"WD": "WDIR", "BAR": "PRES"}
        assert "no minute column" in data["time_note"]
        assert data["summary"]["max"] == 5.05
        assert data["summary"]["max_time"] == "1998-02-03 10:00"

    @respx.mock
    async def test_404_names_the_missing_annual_file(self, client):
        """HTTP 404 explains that the annual file does not exist (yet)."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        respx.get(url__startswith=NDBC_HISTORY_URL).mock(
            return_value=httpx.Response(404, text="Unable to access data file")
        )
        result = await ww3_get_buoy_history(make_ctx(client), "41009", 2026)
        assert "No NDBC historical annual file" in result
        assert "41009h2026.txt.gz" in result
        assert "404" in result


# ============================================================================
# Test: client methods
# ============================================================================


class TestWW3Client:
    """Tests for WW3Client utility methods."""

    def test_build_grib_filter_url_basic(self):
        """build_grib_filter_url should produce correct NOMADS URL."""
        c = WW3Client()
        url = c.build_grib_filter_url("global.0p25", "20260301", "00", 6)

        assert "nomads.ncep.noaa.gov" in url
        assert "gfswave.t00z.global.0p25.f006.grib2" in url

    def test_build_grib_filter_url_with_variables(self):
        """build_grib_filter_url should include variable filter parameters."""
        c = WW3Client()
        url = c.build_grib_filter_url(
            "global.0p25", "20260301", "00", 0, variables=["HTSGW", "PERPW"]
        )

        assert "var_HTSGW=on" in url
        assert "var_PERPW=on" in url

    def test_build_grib_filter_url_with_subsetting(self):
        """build_grib_filter_url should include lat/lon subsetting."""
        c = WW3Client()
        url = c.build_grib_filter_url(
            "global.0p25",
            "20260301",
            "00",
            0,
            lat_range=(34.0, 36.0),
            lon_range=(284.0, 286.0),
        )

        assert "toplat=36.0" in url
        assert "bottomlat=34.0" in url
        assert "leftlon=284.0" in url
        assert "rightlon=286.0" in url

    def test_build_s3_grib_url(self):
        """build_s3_grib_url should produce correct S3 URL."""
        c = WW3Client()
        url = c.build_s3_grib_url("global.0p25", "20260301", "00", 0)

        assert "noaa-gfs-bdp-pds.s3.amazonaws.com" in url
        assert "gfswave.t00z.global.0p25.f000.grib2" in url

    @respx.mock
    async def test_check_grib_exists_true(self, client):
        """check_grib_exists should return True for 200 HEAD."""
        url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/test.grib2"
        respx.head(url).mock(return_value=httpx.Response(200))

        assert await client.check_grib_exists(url) is True

    @respx.mock
    async def test_check_grib_exists_false(self, client):
        """check_grib_exists should return False for 404 HEAD."""
        url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/missing.grib2"
        respx.head(url).mock(return_value=httpx.Response(404))

        assert await client.check_grib_exists(url) is False

    @respx.mock
    async def test_check_grib_exists_connection_error(self, client):
        """check_grib_exists should return False on connection error."""
        url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/error.grib2"
        respx.head(url).mock(side_effect=httpx.ConnectError("refused"))

        assert await client.check_grib_exists(url) is False


# ============================================================================
# Test: resolve_latest_cycle (mocked S3 HEAD)
# ============================================================================


class TestResolveLatestCycle:
    """Tests for WW3Client.resolve_latest_cycle with mocked HEAD."""

    @respx.mock
    async def test_resolve_returns_none_when_nothing_available(self, client):
        """resolve_latest_cycle should return None if all checks fail."""
        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        result = await client.resolve_latest_cycle("global.0p25", num_days=1)
        assert result is None

    @respx.mock
    async def test_resolve_finds_available_cycle(self, client):
        """resolve_latest_cycle should return the first available cycle."""
        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        result = await client.resolve_latest_cycle("global.0p25", num_days=1)
        assert result is not None
        date_str, cycle_str = result
        assert len(date_str) == 8
        assert cycle_str in {"00", "06", "12", "18"}


# ============================================================================
# Test: error handling
# ============================================================================


class TestHandleWw3Error:
    """Tests for the handle_ww3_error utility."""

    def test_handle_http_404(self):
        """handle_ww3_error should return a descriptive message for 404."""
        from ww3_mcp.utils import handle_ww3_error

        response = httpx.Response(
            404, request=httpx.Request("GET", "https://example.com")
        )
        err = httpx.HTTPStatusError(
            "Not Found", request=response.request, response=response
        )
        msg = handle_ww3_error(err, "global.0p25")
        assert "404" in msg

    def test_handle_timeout(self):
        """handle_ww3_error should return a timeout message."""
        from ww3_mcp.utils import handle_ww3_error

        err = httpx.TimeoutException("timed out")
        msg = handle_ww3_error(err)
        assert "timed out" in msg.lower()

    def test_handle_value_error(self):
        """handle_ww3_error should pass through ValueError messages."""
        from ww3_mcp.utils import handle_ww3_error

        err = ValueError("bad input")
        msg = handle_ww3_error(err)
        assert msg == "bad input"

    def test_handle_generic_error(self):
        """handle_ww3_error should format unexpected errors."""
        from ww3_mcp.utils import handle_ww3_error

        err = TypeError("unexpected")
        msg = handle_ww3_error(err, "test")
        assert "TypeError" in msg
        assert "test" in msg


# ============================================================================
# Test: forecast tools with mocked extract_grib_point
# ============================================================================


class TestWw3GetPointSnapshot:
    """Tests for ww3_get_point_snapshot with mocked GRIB extraction."""

    @respx.mock
    async def test_snapshot_no_cycles_returns_error(self, client):
        """ww3_get_point_snapshot should return error when no cycles found."""
        from ww3_mcp.tools.forecast import ww3_get_point_snapshot

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_point_snapshot(ctx, latitude=35.0, longitude=-75.0)

        assert "No GFS-Wave cycles found" in result

    @respx.mock
    async def test_snapshot_with_mocked_grib(self, client):
        """ww3_get_point_snapshot with mocked download and extraction."""
        from ww3_mcp.tools.forecast import ww3_get_point_snapshot

        grib_data = load_json_fixture("grib_sample.json")

        # Mock S3 HEAD for cycle resolution
        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        # Mock NOMADS GRIB download
        respx.get(url__startswith="https://nomads.ncep.noaa.gov/").mock(
            return_value=httpx.Response(200, content=b"fake grib data")
        )

        ctx = make_ctx(client)

        with patch("ww3_mcp.tools.forecast.extract_grib_point", return_value=grib_data):
            result = await ww3_get_point_snapshot(
                ctx, latitude=35.0, longitude=-75.0, response_format="json"
            )

        data = json.loads(result)
        assert "variables" in data
        assert data["variables"]["HTSGW"] == 1.85


class TestWw3GetForecastAtPoint:
    """Tests for ww3_get_forecast_at_point with mocked GRIB extraction."""

    @respx.mock
    async def test_forecast_no_cycles_returns_error(self, client):
        """ww3_get_forecast_at_point should return error when no cycles found."""
        from ww3_mcp.tools.forecast import ww3_get_forecast_at_point

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_forecast_at_point(ctx, latitude=35.0, longitude=-75.0)

        assert "No GFS-Wave cycles found" in result


# ============================================================================
# Test: ww3_get_regional_summary antimeridian / seam handling (regression)
#
# normalize_lon maps each bound independently into 0-360, so a box that wraps
# the 0/360 seam (Greenwich or the dateline) yields west>east — and NOMADS
# grib-filter returns an EMPTY body for an inverted subregion (verified
# live), which then fails opaquely in cfgrib. The tool must split a
# seam-crossing box into [west,360] + [0,east] and combine the two pieces.
# ============================================================================


class _FakeDataset:
    """Minimal stand-in for an xarray Dataset (avoids real GRIB in tests)."""

    def __init__(self, arrays):
        self._arrays = arrays  # {var_name: np.ndarray}

    @property
    def data_vars(self):
        return list(self._arrays)

    def __getitem__(self, name):
        m = MagicMock()
        m.values = self._arrays[name]
        return m

    def close(self):
        pass


def _patch_regional(monkeypatch, client):
    """Stub the cycle resolve, GRIB download (recording lon ranges), and
    xarray open so ww3_get_regional_summary runs without real network/GRIB.
    Returns the list that records each download's lon_range."""
    import tempfile

    import numpy as np

    calls: list = []

    async def fake_cycle(grid, num_days=2):
        return ("20260524", "18")

    async def fake_download(
        grid, date, cycle, fhour, variables=None, lat_range=None, lon_range=None
    ):
        calls.append(lon_range)
        f = tempfile.NamedTemporaryFile(suffix=".grib2", delete=False)
        f.write(b"GRIB")
        f.close()
        return Path(f.name)

    monkeypatch.setattr(client, "resolve_latest_cycle", fake_cycle)
    monkeypatch.setattr(client, "download_grib_subset", fake_download)
    monkeypatch.setattr(
        "xarray.open_dataset",
        lambda *a, **k: _FakeDataset({"swh": np.array([1.0, 2.0, 3.0])}),
    )
    return calls


class TestRegionalSummarySeam:
    """ww3_get_regional_summary must handle boxes that wrap the 0/360 seam."""

    async def test_normal_box_is_a_single_request(self, client, monkeypatch):
        """A box that does not wrap the seam stays one request."""
        from ww3_mcp.tools.forecast import ww3_get_regional_summary

        calls = _patch_regional(monkeypatch, client)
        ctx = make_ctx(client)
        result = await ww3_get_regional_summary(
            ctx,
            lat_min=30,
            lat_max=40,
            lon_min=-75,
            lon_max=-65,
            response_format="json",
        )
        data = json.loads(result)
        assert calls == [(285.0, 295.0)]  # -75/-65 -> 285/295, west<east
        assert data["statistics"]["swh"]["n_points"] == 3

    async def test_seam_crossing_box_splits_and_merges(self, client, monkeypatch):
        """A Greenwich-crossing box splits into [west,360]+[0,east] and the
        per-variable point counts are the exact union of both pieces."""
        from ww3_mcp.tools.forecast import ww3_get_regional_summary

        calls = _patch_regional(monkeypatch, client)
        ctx = make_ctx(client)
        result = await ww3_get_regional_summary(
            ctx,
            lat_min=30,
            lat_max=40,
            lon_min=-30,
            lon_max=20,
            response_format="json",
        )
        data = json.loads(result)
        # -30/20 -> 330/20, west>east -> split at the seam, two requests.
        assert calls == [(330.0, 360.0), (0.0, 20.0)]
        # Union of both halves (3 + 3), not silently empty/errored.
        assert data["statistics"]["swh"]["n_points"] == 6


# ============================================================================
# Realtime window by timestamp — real excerpts, see
# fixtures/ndbc_realtime_SOURCES.md for the source files and their SHA-256
# ============================================================================

NDBC_REALTIME_URL = "https://www.ndbc.noaa.gov/data/realtime2/"


def mock_realtime(fixture: str) -> None:
    """Serve a real realtime2 excerpt for any realtime2 URL."""
    respx.get(url__startswith=NDBC_REALTIME_URL).mock(
        return_value=httpx.Response(200, content=(FIXTURES_DIR / fixture).read_bytes())
    )


class TestWw3GetBuoyObservationsWindow:
    """ww3_get_buoy_observations returns the requested hours, not a row count."""

    @respx.mock
    async def test_window_covers_the_requested_hours(self, client):
        """41009 (10-min rows): hours=3 returns the 19 rows 23:00-02:00."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        mock_realtime("ndbc_realtime_41009_excerpt.txt")
        data = json.loads(
            await ww3_get_buoy_observations(
                make_ctx(client), "41009", hours=3, response_format="json"
            )
        )
        obs = data["observations"]
        assert len(obs) == data["returned"] == data["total"] == data["records"] == 19
        assert obs[0]["timestamp"] == "2026-11-09 02:00"
        assert obs[-1]["timestamp"] == "2026-11-08 23:00"
        assert data["window"]["window_start"] == "2026-11-08 23:00"
        assert data["window"]["typical_interval_minutes"] == 10
        assert data["truncated"] is False
        assert data["timezone"] == "UTC"

    @respx.mock
    async def test_station_with_another_reporting_interval(self, client):
        """44025 (30-min rows with gaps): hours=6 returns the 12 rows in 6 h."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        mock_realtime("ndbc_realtime_44025_excerpt.txt")
        data = json.loads(
            await ww3_get_buoy_observations(
                make_ctx(client), "44025", hours=6, response_format="json"
            )
        )
        assert data["total"] == 12
        assert data["observations"][-1]["timestamp"] == "2026-11-08 19:40"
        assert data["window"]["typical_interval_minutes"] == 30

    @respx.mock
    async def test_truncation_envelope_keeps_the_most_recent_rows(self, client):
        """max_records caps the JSON rows, newest kept, with the envelope."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        mock_realtime("ndbc_realtime_41009_excerpt.txt")
        data = json.loads(
            await ww3_get_buoy_observations(
                make_ctx(client),
                "41009",
                hours=6,
                response_format="json",
                max_records=5,
            )
        )
        assert data["truncated"] is True
        assert data["returned"] == len(data["observations"]) == 5
        assert data["total"] == 37  # 20:00 to 02:00 at 10 min, both ends included
        assert "hint" in data
        assert [o["timestamp"][-5:] for o in data["observations"]] == [
            "02:00", "01:50", "01:40", "01:30", "01:20",
        ]  # fmt: skip

    @respx.mock
    async def test_clamp_and_short_file_are_reported(self, client):
        """A clamped hours value and a file shorter than the window are noted."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        mock_realtime("ndbc_realtime_41009_excerpt.txt")
        data = json.loads(
            await ww3_get_buoy_observations(
                make_ctx(client), "41009", hours=5000, response_format="json"
            )
        )
        notes = " ".join(data["notes"])
        assert "clamped to 1080" in notes
        assert "reaches back only to 2026-11-08 19:10" in notes
        assert data["window"]["covers_full_window"] is False

    @respx.mock
    async def test_markdown_states_the_window(self, client):
        """Markdown names the window, its rows and the interval found."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        mock_realtime("ndbc_realtime_41009_excerpt.txt")
        result = await ww3_get_buoy_observations(make_ctx(client), "41009", hours=3)
        assert (
            "**Window**: 3 h before the latest row "
            "(2026-11-08 23:00 to 2026-11-09 02:00 UTC): 19 rows, typically every 10 min"
        ) in result
        assert "rows valid" in result


class TestCompareForecastWithBuoyWindow:
    """ww3_compare_forecast_with_buoy gets the full observation window."""

    @respx.mock
    async def test_comparison_uses_the_full_observation_window(
        self, client, monkeypatch
    ):
        """hours_to_compare=6 pairs 21:00 and 00:00; the old row rule paired none."""
        from datetime import datetime, timedelta

        from ww3_mcp.tools.forecast import ww3_compare_forecast_with_buoy

        mock_realtime("ndbc_realtime_41009_excerpt.txt")

        async def fake_cycle(grid, num_days=2):
            return ("20261108", "18")

        async def fake_download(grid, date, cycle, fhour, **kwargs):
            return Path(f"/nonexistent/ww3-test-f{fhour:03d}.grib2")

        def fake_extract(path, lat, lon):
            fhour = int(Path(path).stem.split("-f")[-1])
            valid = datetime(2026, 11, 8, 18) + timedelta(hours=fhour)
            return {"valid_time": valid.strftime("%Y-%m-%d %H:%M"), "HTSGW": 1.5}

        monkeypatch.setattr(client, "resolve_latest_cycle", fake_cycle)
        monkeypatch.setattr(client, "download_grib_subset", fake_download)
        monkeypatch.setattr("ww3_mcp.tools.forecast.extract_grib_point", fake_extract)

        data = json.loads(
            await ww3_compare_forecast_with_buoy(
                make_ctx(client),
                "41009",
                28.5,
                -80.2,
                hours_to_compare=6,
                response_format="json",
            )
        )
        window = data["observation_window"]
        assert window["window_start"] == "2026-11-08 20:00"
        assert window["rows_in_window"] == 37
        assert window["rows_with_wvht"] == 18
        # 18:00 is outside the window; 21:00 pairs with 21:10 (tie with 20:50,
        # first in file order wins); 00:00 pairs with 23:50.
        assert data["comparison_times"] == ["2026-11-08 21:00", "2026-11-09 00:00"]
        assert data["observed_values"] == [1.3, 1.6]
        assert data["stats"]["n"] == 2
