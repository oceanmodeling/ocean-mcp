"""Unit tests for RTOFS tools with mocked HTTP (respx)."""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from rtofs_mcp.client import RetryTransport, RTOFSClient
from rtofs_mcp.models import DATASETS, THREDDS_BASE

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _mock_ctx(client: RTOFSClient):
    """Create a mock MCP Context with an RTOFSClient in lifespan."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"rtofs_client": client}
    return ctx


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = RTOFSClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


class TestFetchPointCSV:
    """Test client.fetch_point_csv with mocked HTTP."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_ssh_point(self):
        """Fetch SSH at a point returns parsed CSV data."""
        fixture_text = FIXTURES_DIR.joinpath("ssh_point.csv").read_text()
        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"

        respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))

        client = RTOFSClient()
        try:
            rows = await client.fetch_point_csv(
                dataset_key="ssh",
                variable="surf_el",
                latitude=40.0,
                longitude=-74.0,
                time="present",
            )
            assert len(rows) >= 1
            assert "surf_el" in rows[0]
            assert "latitude" in rows[0]
            assert "time" in rows[0]
            assert isinstance(rows[0]["surf_el"], float)
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_temp_profile(self):
        """Fetch temperature profile returns rows with depth."""
        fixture_text = FIXTURES_DIR.joinpath("temp_profile.csv").read_text()
        ds = DATASETS["sst"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"

        respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))

        client = RTOFSClient()
        try:
            rows = await client.fetch_point_csv(
                dataset_key="sst",
                variable="water_temp",
                latitude=40.0,
                longitude=-74.0,
                time="present",
            )
            assert len(rows) >= 1
            assert "water_temp" in rows[0]
            assert "vertCoord" in rows[0]
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_sst_timeseries(self):
        """Fetch SST surface time series returns multiple rows."""
        fixture_text = FIXTURES_DIR.joinpath("sst_timeseries.csv").read_text()
        ds = DATASETS["sst"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"

        respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))

        client = RTOFSClient()
        try:
            rows = await client.fetch_point_csv(
                dataset_key="sst",
                variable="water_temp",
                latitude=40.0,
                longitude=-74.0,
                vert_coord=0.0,
            )
            assert len(rows) > 10
            # All should have the same lat/lon
            lats = {r["latitude"] for r in rows}
            assert len(lats) == 1
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_handles_404(self):
        """HTTP 404 should raise RTOFSAPIError."""
        from rtofs_mcp.client import RTOFSAPIError

        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"
        respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))

        client = RTOFSClient()
        try:
            with pytest.raises(RTOFSAPIError, match="404"):
                await client.fetch_point_csv(
                    dataset_key="ssh",
                    variable="surf_el",
                    latitude=40.0,
                    longitude=-74.0,
                )
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_handles_timeout(self):
        """Timeout should raise RTOFSAPIError."""
        from rtofs_mcp.client import RTOFSAPIError

        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"
        respx.get(url).mock(side_effect=httpx.ReadTimeout("timeout"))

        client = RTOFSClient(backoff_factor=0)
        try:
            with pytest.raises(RTOFSAPIError, match="timed out"):
                await client.fetch_point_csv(
                    dataset_key="ssh",
                    variable="surf_el",
                    latitude=40.0,
                    longitude=-74.0,
                )
        finally:
            await client.close()


class TestTimeWindow:
    """NCSS point queries are always time-bounded (never temporal=all)."""

    async def _query_params(self, dataset_key: str, **kwargs) -> dict[str, str]:
        """Run fetch_point_csv against a mock and return the sent query params."""
        fixture_text = FIXTURES_DIR.joinpath("ssh_point.csv").read_text()
        url = f"{THREDDS_BASE}/ncss/{DATASETS[dataset_key]['path']}"
        route = respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))
        client = RTOFSClient()
        try:
            await client.fetch_point_csv(
                dataset_key=dataset_key,
                variable="surf_el",
                latitude=35.0,
                longitude=-65.0,
                **kwargs,
            )
        finally:
            await client.close()
        return dict(route.calls.last.request.url.params)

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_time_requests_default_window_from_present(self):
        """No time arguments: the dataset's default window starting now."""
        params = await self._query_params("ssh")
        assert params["time_start"] == "present"
        assert params["time_duration"] == "PT24H"
        assert "temporal" not in params

    @pytest.mark.asyncio
    @respx.mock
    async def test_3d_default_window_is_72h(self):
        """The 3-hourly 3D datasets default to a 72 h window."""
        params = await self._query_params("sst", vert_coord=0.0)
        assert params["time_duration"] == "PT72H"
        assert "temporal" not in params

    @pytest.mark.asyncio
    @respx.mock
    async def test_time_start_only_gets_default_duration(self):
        """A start with no end is completed with the default window."""
        params = await self._query_params("ssh", time_start="2026-10-12T00:00:00Z")
        assert params["time_start"] == "2026-10-12T00:00:00Z"
        assert params["time_duration"] == "PT24H"
        assert "time_end" not in params

    @pytest.mark.asyncio
    @respx.mock
    async def test_time_end_only_uses_given_duration(self):
        """An end with an explicit duration is a window ending there."""
        params = await self._query_params(
            "sst", time_end="present", time_duration="PT6H"
        )
        assert params["time_end"] == "present"
        assert params["time_duration"] == "PT6H"
        assert "time_start" not in params

    @pytest.mark.asyncio
    @respx.mock
    async def test_explicit_range_is_passed_through(self):
        """A full start/end range is sent as-is, with no duration."""
        params = await self._query_params(
            "ssh",
            time_start="2026-10-12T00:00:00Z",
            time_end="2026-10-13T00:00:00Z",
        )
        assert params["time_start"] == "2026-10-12T00:00:00Z"
        assert params["time_end"] == "2026-10-13T00:00:00Z"
        assert "time_duration" not in params

    @pytest.mark.asyncio
    @respx.mock
    async def test_single_time_wins(self):
        """A single time is sent alone."""
        params = await self._query_params(
            "ssh", time="present", time_start="2026-10-12T00:00:00Z"
        )
        assert params["time"] == "present"
        assert "time_start" not in params
        assert "time_duration" not in params

    @pytest.mark.asyncio
    @respx.mock
    async def test_multi_var_default_is_bounded(self):
        """fetch_multi_var_csv uses the same bounded default."""
        url = f"{THREDDS_BASE}/ncss/{DATASETS['currents']['path']}"
        route = respx.get(url).mock(
            return_value=httpx.Response(
                200, text="time,water_u,water_v\n2026-10-14T00:00:00Z,0.1,0.2\n"
            )
        )
        client = RTOFSClient()
        try:
            await client.fetch_multi_var_csv(
                dataset_key="currents",
                variables=["water_u", "water_v"],
                latitude=35.0,
                longitude=-65.0,
            )
        finally:
            await client.close()
        params = route.calls.last.request.url.params
        assert params.get_list("var") == ["water_u", "water_v"]
        assert params["time_start"] == "present"
        assert params["time_duration"] == "PT72H"
        assert "temporal" not in params


class TestCheckDatasetAvailable:
    """Test dataset availability checking."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_available_dataset(self):
        """Available dataset returns True."""
        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/dodsC/{ds['path']}.dds"
        respx.get(url).mock(return_value=httpx.Response(200, text="Dataset {}"))

        client = RTOFSClient()
        try:
            result = await client.check_dataset_available("ssh")
            assert result is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_unavailable_dataset(self):
        """404 response returns False."""
        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/dodsC/{ds['path']}.dds"
        respx.get(url).mock(return_value=httpx.Response(404))

        client = RTOFSClient()
        try:
            result = await client.check_dataset_available("ssh")
            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_unknown_dataset_key(self):
        """Unknown dataset key returns False without network call."""
        client = RTOFSClient()
        try:
            result = await client.check_dataset_available("nonexistent")
            assert result is False
        finally:
            await client.close()


class TestToolRegistration:
    """Verify all 8 tools are registered on the MCP server."""

    def test_all_tools_registered(self):
        """All 8 RTOFS tools should be registered."""
        from rtofs_mcp.server import mcp

        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {
            "rtofs_get_system_info",
            "rtofs_list_datasets",
            "rtofs_get_latest_time",
            "rtofs_get_surface_forecast",
            "rtofs_get_profile_forecast",
            "rtofs_get_area_forecast",
            "rtofs_get_transect",
            "rtofs_compare_with_observations",
        }
        for name in expected:
            assert name in tool_names, f"Tool '{name}' not registered"


def test_cap_series_json_caps_data():
    """_cap_series_json caps the surface-forecast `data` series + stamps retrieved_at."""
    import json

    from rtofs_mcp.tools.forecast import _cap_series_json

    parsed = json.loads(
        _cap_series_json(
            {"data": [{"time": i, "value": i} for i in range(2500)]}, max_points=2000
        )
    )
    assert parsed["truncated"] is True
    assert parsed["n_rows"] == 2000
    assert parsed["total_rows"] == 2500
    assert len(parsed["data"]) == 2000
    assert parsed["data"][0]["time"] == 0
    assert "retrieved_at" in parsed
    assert "first 2000 of 2500" in parsed["hint"]

    whole = json.loads(_cap_series_json({"data": [{"time": 0, "value": 1}]}))
    assert whole["truncated"] is False
    assert whole["total_rows"] == 1
    assert "retrieved_at" in whole


class TestToolTimeWindows:
    """The tools that used to fetch every time step now send bounded windows."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_surface_forecast_default_window(self):
        """rtofs_get_surface_forecast with no range asks for the next 72 h of SST."""
        from rtofs_mcp.tools.forecast import rtofs_get_surface_forecast

        fixture_text = FIXTURES_DIR.joinpath("sst_timeseries.csv").read_text()
        url = f"{THREDDS_BASE}/ncss/{DATASETS['sst']['path']}"
        route = respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))
        client = RTOFSClient()
        try:
            out = await rtofs_get_surface_forecast(
                _mock_ctx(client), latitude=35.0, longitude=-65.0
            )
        finally:
            await client.close()
        params = route.calls.last.request.url.params
        assert params["time_start"] == "present"
        assert params["time_duration"] == "PT72H"
        assert params["vertCoord"] == "0.0"
        assert "Surface Forecast" in out

    @pytest.mark.asyncio
    @respx.mock
    async def test_compare_fetches_24h_before_present(self):
        """rtofs_compare_with_observations asks only for the 24 h ending now."""
        import json

        from rtofs_mcp.tools.analysis import rtofs_compare_with_observations

        csv_text = (
            "time,latitude,longitude,vertCoord,water_temp\n"
            "2026-10-13T03:00:00Z,35.0,-65.0,0.0,26.0\n"
            "2026-10-13T15:00:00Z,35.0,-65.0,0.0,26.2\n"
            "2026-10-14T03:00:00Z,35.0,-65.0,0.0,26.5\n"
        )
        url = f"{THREDDS_BASE}/ncss/{DATASETS['sst']['path']}"
        route = respx.get(url).mock(return_value=httpx.Response(200, text=csv_text))
        client = RTOFSClient()
        try:
            out = await rtofs_compare_with_observations(
                _mock_ctx(client),
                latitude=35.0,
                longitude=-65.0,
                response_format="json",
            )
        finally:
            await client.close()
        params = route.calls.last.request.url.params
        assert params["time_end"] == "present"
        assert params["time_duration"] == "PT24H"
        assert "temporal" not in params
        result = json.loads(out)
        assert result["window_hours"] == 24
        assert result["earliest"]["time"] == "2026-10-13T03:00:00Z"
        assert result["latest"]["time"] == "2026-10-14T03:00:00Z"
        assert result["change_over_window"] == 0.5

    @pytest.mark.asyncio
    @respx.mock
    async def test_compare_window_ends_at_given_time(self):
        """A reference time becomes the end of the 24 h window."""
        from rtofs_mcp.tools.analysis import rtofs_compare_with_observations

        fixture_text = FIXTURES_DIR.joinpath("sst_timeseries.csv").read_text()
        url = f"{THREDDS_BASE}/ncss/{DATASETS['sst']['path']}"
        route = respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))
        client = RTOFSClient()
        try:
            out = await rtofs_compare_with_observations(
                _mock_ctx(client),
                latitude=35.0,
                longitude=-65.0,
                time="2026-10-12T00:00:00Z",
            )
        finally:
            await client.close()
        params = route.calls.last.request.url.params
        assert params["time_end"] == "2026-10-12T00:00:00Z"
        assert params["time_duration"] == "PT24H"
        assert "24 h window" in out
