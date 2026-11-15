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
        """Exactly the 8 RTOFS tools are registered, no more and no fewer."""
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
            "rtofs_compare_forecast_times",
        }
        assert tool_names == expected

    def test_old_compare_name_not_registered(self):
        """The pre-0.1.4 name rtofs_compare_with_observations is gone, not aliased."""
        from rtofs_mcp.server import mcp

        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        assert "rtofs_compare_with_observations" not in tool_names

    def test_compare_description_says_no_observations(self):
        """The compare tool's description opens by saying it uses no observations."""
        from rtofs_mcp.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        first_line = tools["rtofs_compare_forecast_times"].description.splitlines()[0]
        assert "two forecast times at one location" in first_line
        assert "no observations" in first_line


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
        """rtofs_compare_forecast_times asks only for the 24 h ending now."""
        import json

        from rtofs_mcp.tools.analysis import rtofs_compare_forecast_times

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
            out = await rtofs_compare_forecast_times(
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
        from rtofs_mcp.tools.analysis import rtofs_compare_forecast_times

        fixture_text = FIXTURES_DIR.joinpath("sst_timeseries.csv").read_text()
        url = f"{THREDDS_BASE}/ncss/{DATASETS['sst']['path']}"
        route = respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))
        client = RTOFSClient()
        try:
            out = await rtofs_compare_forecast_times(
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


# ---------------------------------------------------------------------------
# rtofs_get_latest_time: dataset time coordinate (saved THREDDS responses,
# see tests/fixtures/thredds_time/SOURCE.md for URLs and checksums)
# ---------------------------------------------------------------------------

TIME_FIXTURES = FIXTURES_DIR / "thredds_time"


def _mock_time_coordinate(prefix: str, dataset_key: str, ascii_text: str | None = None):
    """Serve the saved DAS and OPeNDAP ASCII time responses for one dataset."""
    base = f"{THREDDS_BASE}/dodsC/{DATASETS[dataset_key]['path']}"
    das_text = (TIME_FIXTURES / f"{prefix}.das").read_text()
    if ascii_text is None:
        ascii_text = (TIME_FIXTURES / f"{prefix}_time.ascii").read_text()
    das = respx.get(f"{base}.das").mock(return_value=httpx.Response(200, text=das_text))
    asc = respx.get(f"{base}.ascii?time,time_run").mock(
        return_value=httpx.Response(200, text=ascii_text)
    )
    return das, asc


class TestTimeCoordinateParsing:
    """Parse the saved THREDDS DAS and OPeNDAP ASCII responses."""

    def test_das_time_attributes(self):
        """The DAS gives the units and calendar of time and of time_run."""
        from rtofs_mcp.client import _parse_das_attributes

        das = (TIME_FIXTURES / "ssh_best.das").read_text()
        time_attrs = _parse_das_attributes(das, "time")
        assert time_attrs["units"] == "hours since 2026-10-30 12:00:00.000 UTC"
        assert time_attrs["calendar"] == "proleptic_gregorian"
        run_attrs = _parse_das_attributes(das, "time_run")
        assert run_attrs["standard_name"] == "forecast_reference_time"
        assert _parse_das_attributes(das, "no_such_variable") == {}

    def test_time_origin_attribute_is_not_the_axis_start(self):
        """The time_origin attribute 0.1.3 reported as 'first' is not the axis start."""
        from rtofs_mcp.client import _parse_das_attributes

        das = (TIME_FIXTURES / "ssh_best.das").read_text()
        assert _parse_das_attributes(das, "tau")["time_origin"] == "2026-11-06 12:00:00"
        assert "2026-10-30 12:00" in _parse_das_attributes(das, "time")["units"]

    def test_ascii_arrays(self):
        """Both coordinates are read, each with its declared number of values."""
        from rtofs_mcp.client import _parse_opendap_ascii

        arrays = _parse_opendap_ascii(
            (TIME_FIXTURES / "ssh_best_time.ascii").read_text()
        )
        assert len(arrays["time"]) == 385
        assert len(arrays["time_run"]) == 385
        assert arrays["time"][0] == 0.0
        assert arrays["time"][-1] == 384.0
        assert max(arrays["time_run"]) == 192.0

    def test_ascii_count_mismatch_raises(self):
        """A response with fewer values than declared is rejected, not half-read."""
        from rtofs_mcp.client import RTOFSAPIError, _parse_opendap_ascii

        text = (TIME_FIXTURES / "t3z_best_time.ascii").read_text()
        text = text.replace("time[129]\n", "time[130]\n", 1)
        with pytest.raises(RTOFSAPIError, match="declares 130 values but has 129"):
            _parse_opendap_ascii(text)

    def test_ascii_without_separator_raises(self):
        """An HTML error page instead of OPeNDAP ASCII is rejected."""
        from rtofs_mcp.client import RTOFSAPIError, _parse_opendap_ascii

        with pytest.raises(RTOFSAPIError, match="unexpected OPeNDAP ASCII"):
            _parse_opendap_ascii("<html><body>Error</body></html>")

    def test_cf_units_both_spellings(self):
        """Both unit spellings THREDDS serves decode to the same UTC origin."""
        from datetime import datetime, timezone

        from rtofs_mcp.client import _cf_time_to_datetime

        origin = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
        assert (
            _cf_time_to_datetime(
                0.0, "hours since 2026-10-30 12:00:00.000 UTC", "proleptic_gregorian"
            )
            == origin
        )
        assert (
            _cf_time_to_datetime(0.0, "hours since 2026-10-30T12:00:00Z", None)
            == origin
        )
        assert _cf_time_to_datetime(
            384.0, "hours since 2026-10-30 12:00:00.000 UTC", None
        ) == datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
        assert _cf_time_to_datetime(1.5, "days since 2026-01-01", None) == datetime(
            2026, 1, 2, 12, tzinfo=timezone.utc
        )

    def test_cf_units_unsupported_raise(self):
        """Units, offsets or calendars the converter cannot honour raise instead of guessing."""
        from rtofs_mcp.client import RTOFSAPIError, _cf_time_to_datetime

        with pytest.raises(RTOFSAPIError, match="units"):
            _cf_time_to_datetime(0.0, "months since 2026-01-01", None)
        with pytest.raises(RTOFSAPIError, match="units"):
            _cf_time_to_datetime(0.0, "hours since 2026-01-01 00:00 +05:00", None)
        with pytest.raises(RTOFSAPIError, match="calendar"):
            _cf_time_to_datetime(0.0, "hours since 2026-01-01", "noleap")


class TestDatasetTimeRange:
    """client.get_dataset_time_range and rtofs_get_latest_time on saved responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_ssh_time_range(self):
        """Hourly SSH: first and last from the time axis, 385 steps, newest run."""
        das, asc = _mock_time_coordinate("ssh_best", "ssh")
        client = RTOFSClient(backoff_factor=0)
        try:
            r = await client.get_dataset_time_range("ssh")
        finally:
            await client.close()
        assert r["first"] == "2026-10-30T12:00:00Z"
        assert r["last"] == "2026-11-15T12:00:00Z"
        assert r["n_time_steps"] == 385
        assert r["time_step_hours"] == 1.0
        assert r["latest_run"] == "2026-11-07T12:00:00Z"
        assert r["thredds_path"] == DATASETS["ssh"]["path"]
        assert das.call_count == 1
        assert asc.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_sst_time_range(self):
        """3-hourly temperature has its own axis: 129 steps, 3 h apart."""
        _mock_time_coordinate("t3z_best", "sst")
        client = RTOFSClient(backoff_factor=0)
        try:
            r = await client.get_dataset_time_range("sst")
        finally:
            await client.close()
        assert r["first"] == "2026-10-30T12:00:00Z"
        assert r["last"] == "2026-11-15T12:00:00Z"
        assert r["n_time_steps"] == 129
        assert r["time_step_hours"] == 3.0
        assert r["latest_run"] == "2026-11-08T12:00:00Z"

    @pytest.mark.asyncio
    @respx.mock
    async def test_nan_values_are_skipped(self):
        """NaN entries (the coordinate's missing_value) are not counted as times."""
        text = (TIME_FIXTURES / "ssh_best_time.ascii").read_text()
        text = text.replace("time[385]\n0.0, ", "time[385]\nNaN, ", 1)
        _mock_time_coordinate("ssh_best", "ssh", ascii_text=text)
        client = RTOFSClient(backoff_factor=0)
        try:
            r = await client.get_dataset_time_range("ssh")
        finally:
            await client.close()
        assert r["first"] == "2026-10-30T13:00:00Z"
        assert r["n_time_steps"] == 384

    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_json_reports_axis_not_present_step(self):
        """JSON names the dataset and reports the axis ends; no NCSS 'present' query."""
        import json

        from rtofs_mcp.tools.discovery import rtofs_get_latest_time

        _mock_time_coordinate("ssh_best", "ssh")
        ncss = respx.get(f"{THREDDS_BASE}/ncss/{DATASETS['ssh']['path']}").mock(
            return_value=httpx.Response(200, text="")
        )
        client = RTOFSClient(backoff_factor=0)
        try:
            out = await rtofs_get_latest_time(
                _mock_ctx(client), dataset="ssh", response_format="json"
            )
        finally:
            await client.close()
        r = json.loads(out)
        assert r["dataset"] == "ssh"
        assert r["thredds_dataset"] == DATASETS["ssh"]["path"]
        assert r["variables"] == ["surf_el"]
        assert r["first_time"] == "2026-10-30T12:00:00Z"
        assert r["last_time"] == "2026-11-15T12:00:00Z"
        assert r["latest_run"] == "2026-11-07T12:00:00Z"
        assert r["timezone"] == "UTC"
        assert r["source_url"].endswith("ssh_best.ncd.ascii?time,time_run")
        assert "retrieved_at" in r
        assert not ncss.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_markdown(self):
        """Markdown shows the THREDDS path, both ends, the steps and the newest run."""
        from rtofs_mcp.tools.discovery import rtofs_get_latest_time

        _mock_time_coordinate("t3z_best", "sst")
        client = RTOFSClient(backoff_factor=0)
        try:
            out = await rtofs_get_latest_time(_mock_ctx(client), dataset="sst")
        finally:
            await client.close()
        assert f"`{DATASETS['sst']['path']}`" in out
        assert "**First available**: 2026-10-30T12:00:00Z" in out
        assert "**Last available**: 2026-11-15T12:00:00Z" in out
        assert "**Time steps**: 129, every 3 h" in out
        assert "**Newest model run**: 2026-11-08T12:00:00Z" in out

    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_http_error_names_dataset(self):
        """A THREDDS failure is an 'RTOFS Error' that names the dataset path."""
        from rtofs_mcp.tools.discovery import rtofs_get_latest_time

        base = f"{THREDDS_BASE}/dodsC/{DATASETS['ssh']['path']}"
        respx.get(f"{base}.das").mock(return_value=httpx.Response(503))
        client = RTOFSClient(backoff_factor=0)
        try:
            out = await rtofs_get_latest_time(_mock_ctx(client), dataset="ssh")
        finally:
            await client.close()
        assert out.startswith("RTOFS Error: THREDDS OPeNDAP request failed (HTTP 503)")
        assert DATASETS["ssh"]["path"] in out


class TestDefaultTimeDocstrings:
    """The single-time tools describe their default time as THREDDS applies it."""

    def test_default_is_nearest_current_time(self):
        """No tool says its default time is 'latest'; three say 'nearest the current time'."""
        from rtofs_mcp.server import mcp

        descriptions = {
            t.name: " ".join(t.description.split())
            for t in mcp._tool_manager.list_tools()
        }
        for name, text in descriptions.items():
            assert "Default: latest" not in text, name
        for name in (
            "rtofs_get_profile_forecast",
            "rtofs_get_area_forecast",
            "rtofs_get_transect",
        ):
            assert (
                "Default: the step nearest the current time ('present')"
                in descriptions[name]
            )
