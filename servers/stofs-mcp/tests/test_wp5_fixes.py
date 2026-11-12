"""Fixes from the WP5 sampled evaluation (WP7 Task C).

D-1: a CO-OPS rejection (HTTP 400 with a JSON error message) is reported with CO-OPS's own
message, not as an S3 failure. D-2: a station identifier that matches more than one record of
a station file is reported. Epoch: the comparison's datum note says that a CO-OPS tidal datum
refers to a tidal-datum epoch. Fixtures are verbatim real NOAA answers and file excerpts
(tests/fixtures/wp5_fixtures_SOURCES.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import numpy as np
import pytest
import respx

from stofs_mcp.client import COOPS_API_BASE, STOFSClient
from stofs_mcp.models import STOFSModel
from stofs_mcp.utils import parse_station_netcdf, station_match_warning

from .conftest import ZETA_3D_V21, ZETA_3D_V31, six_minute_times

FIX = Path(__file__).parent / "fixtures"


def make_ctx(client: STOFSClient):
    """A minimal MCP Context whose lifespan state holds ``client`` (as in test_tools)."""
    from unittest.mock import MagicMock

    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"stofs_client": client}
    return ctx


BODY_UNSUPPORTED = (FIX / "coops_http400_unsupported_datum.json").read_bytes()
BODY_NO_MSL = (FIX / "coops_http400_no_msl.json").read_bytes()
BODY_NO_DATA = (FIX / "coops_no_data.json").read_bytes()
DUP = json.loads((FIX / "stofs2d_20261026_t12z_dup_excerpt.json").read_text())


@pytest.fixture
def dup_nc(tmp_path):
    """The real 2D excerpt written back as a station NetCDF (raw values, real attributes)."""
    import netCDF4

    path = tmp_path / "dup_excerpt.nc"
    nc = netCDF4.Dataset(str(path), "w")
    try:
        for key, value in DUP["global_attributes"].items():
            setattr(nc, key, value)
        rows = DUP["stations"]
        nc.createDimension("time", len(DUP["time"]["values"]))
        nc.createDimension("station", len(rows))
        nc.createDimension("namelen", 50)
        t = nc.createVariable("time", "f8", ("time",))
        t.units = DUP["time"]["units"]
        t[:] = DUP["time"]["values"]
        names = nc.createVariable("station_name", "S1", ("station", "namelen"))
        chars = np.full((len(rows), 50), b"", dtype="S1")
        for i, r in enumerate(rows):
            chars[i, : len(r["name"])] = [bytes([c]) for c in r["name"].encode()]
        names[:] = chars
        nc.createVariable("x", "f8", ("station",))[:] = [r["x"] for r in rows]
        nc.createVariable("y", "f8", ("station",))[:] = [r["y"] for r in rows]
        attrs = dict(DUP["zeta_attributes"])
        z = nc.createVariable(
            "zeta", "f8", ("time", "station"), fill_value=attrs.pop("_FillValue")
        )
        for key, value in attrs.items():
            setattr(z, key, value)
        z[:] = np.array([r["zeta"] for r in rows], dtype=float).T
    finally:
        nc.close()
    return path


def _fresh_copies(path):
    """download_netcdf stand-in: the tools delete the downloaded file after each call,
    so every call gets its own copy of ``path``."""
    import shutil

    n = {"i": 0}

    async def _download(url):
        n["i"] += 1
        dst = path.with_name(f"{path.stem}_call{n['i']}.nc")
        shutil.copy(path, dst)
        return dst

    return _download


def _expected_max_diff(window: set[str] | None) -> tuple[float, int]:
    """Largest |record 0 - record 1| over times where both are valid (independent of the code
    under test: valid means not the fill value and |v| < 50 m)."""
    import netCDF4

    times = netCDF4.num2date(
        DUP["time"]["values"], DUP["time"]["units"].split("!")[0].strip()
    )
    ts = [t.strftime("%Y-%m-%d %H:%M") for t in times]
    fill = DUP["zeta_attributes"]["_FillValue"]
    a, b = DUP["stations"][0]["zeta"], DUP["stations"][1]["zeta"]
    d = [
        abs(x - y)
        for t, x, y in zip(ts, a, b)
        if (window is None or t in window)
        and x != fill
        and y != fill
        and abs(x) < 50
        and abs(y) < 50
    ]
    return max(d), len(d)


class TestCoopsRejectionMessage:
    """D-1: CO-OPS's own message reaches the caller."""

    @pytest.mark.asyncio
    @respx.mock
    @pytest.mark.parametrize(
        "body, text",
        [
            (
                BODY_UNSUPPORTED,
                "CO-OPS API error: The supported Datum values are: MHHW, MHW, MTL, MSL, MLW, MLLW, LWI, HWI",
            ),
            (BODY_NO_MSL, "CO-OPS API error: There is no MSL for the station: 8531232"),
        ],
    )
    async def test_http_400_raises_value_error_with_the_message(self, body, text):
        """An HTTP 400 JSON error becomes a ValueError carrying the message, not HTTPStatusError."""
        respx.get(COOPS_API_BASE).mock(return_value=httpx.Response(400, content=body))
        client = STOFSClient(backoff_factor=0)
        try:
            with pytest.raises(ValueError) as exc:
                await client.fetch_coops_observations(
                    "8531232", "20261026 12:06", "20261028 13:42", datum="MSL"
                )
        finally:
            await client.close()
        assert str(exc.value) == text

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_data_answer_still_raises_value_error(self):
        """The HTTP 200 no-data document keeps raising ValueError with its message."""
        respx.get(COOPS_API_BASE).mock(
            return_value=httpx.Response(200, content=BODY_NO_DATA)
        )
        client = STOFSClient(backoff_factor=0)
        try:
            with pytest.raises(ValueError, match="No data was found"):
                await client.fetch_coops_observations(
                    "8419317", "20260601 12:06", "20260603 13:42"
                )
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_500_without_json_still_raises_http_error(self):
        """A server error without a CO-OPS message is not turned into a ValueError."""
        respx.get(COOPS_API_BASE).mock(
            return_value=httpx.Response(500, content=b"<html>oops</html>")
        )
        client = STOFSClient(max_retries=0, backoff_factor=0)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await client.fetch_coops_observations(
                    "8443970", "20261026 12:06", "20261028 13:42"
                )
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_compare_tool_reports_the_coops_message_not_s3(self, station_nc):
        """The compare tool now says why CO-OPS refused, and no longer blames the S3 bucket."""
        from stofs_mcp.tools.validation import stofs_compare_with_observations

        start = "2026-10-25 12:00"
        path = station_nc(ZETA_3D_V31, start, [0.2] * 600)
        respx.get(COOPS_API_BASE).mock(
            return_value=httpx.Response(400, content=BODY_NO_MSL)
        )
        client = STOFSClient(backoff_factor=0)
        client.download_netcdf = AsyncMock(return_value=path)
        try:
            out = await stofs_compare_with_observations(
                make_ctx(client),
                station_id="8443970",
                model=STOFSModel.ATLANTIC_3D,
                cycle_date="2026-10-26",
                cycle_hour="12",
                lead_start_hours=0,
                lead_end_hours=12,
            )
        finally:
            await client.close()
        assert out.startswith(
            "Could not fetch CO-OPS observations: CO-OPS API error: There is no MSL for the station: 8531232"
        )
        assert "S3" not in out


class TestDuplicateStationIdentifier:
    """D-2: an identifier on two records of a real STOFS-2D-Global file is reported."""

    def test_parser_records_both_matches_and_uses_the_first(self, dup_nc):
        """Both 8414721 records are listed; the first (Fort Point) supplies the series."""
        d = parse_station_netcdf(dup_nc, "8414721", model="2d_global")
        assert [r["name"] for r in d["matching_records"]] == [
            s["name"] for s in DUP["stations"][:2]
        ]
        assert (
            d["station_idx"] == 0 and "Fort Point" in d["matching_records"][0]["name"]
        )
        assert (
            len(d["duplicate_records"]) == 1 and d["duplicate_records"][0]["index"] == 1
        )

    def test_warning_gives_the_largest_valid_difference_over_the_series(self, dup_nc):
        """Over the series, the stated difference equals the independent recalculation."""
        d = parse_station_netcdf(dup_nc, "8414721", model="2d_global")
        w = station_match_warning(d)
        exp, n = _expected_max_diff(None)
        assert "matches 2 records" in w and "Fort Point" in w and "Frankfort" in w
        assert (
            f"largest absolute difference {exp:.3f} m over the series ({n} common valid times)"
            in w
        )

    def test_single_match_has_no_warning(self, dup_nc):
        """Portland (one record) gets no warning."""
        assert (
            station_match_warning(
                parse_station_netcdf(dup_nc, "8418150", model="2d_global")
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_compare_tool_json_and_markdown_carry_the_window_difference(
        self, dup_nc
    ):
        """The comparison states the records and their largest difference in its window."""
        from stofs_mcp.tools.validation import stofs_compare_with_observations

        times = six_minute_times("2026-10-26 06:00", 180)
        client = STOFSClient(backoff_factor=0)
        client.download_netcdf = _fresh_copies(dup_nc)
        client.fetch_coops_observations = AsyncMock(
            return_value={
                "data": [
                    {"t": t, "v": "0.100", "f": "0,0,0,0", "q": "v"} for t in times
                ]
            }
        )
        kw = dict(
            station_id="8414721",
            model=STOFSModel.GLOBAL_2D,
            cycle_date="2026-10-26",
            cycle_hour="12",
            lead_start_hours=0,
            lead_end_hours=6,
        )
        js = json.loads(
            await stofs_compare_with_observations(
                make_ctx(client), response_format="json", **kw
            )
        )
        window = {t for t in times if "2026-10-26 12:06" <= t <= "2026-10-26 18:00"}
        exp, n = _expected_max_diff(window)
        assert (
            f"largest absolute difference {exp:.3f} m in the comparison window ({n} common valid times)"
            in js["station_warning"]
        )
        md = await stofs_compare_with_observations(make_ctx(client), **kw)
        assert "Station warning: Station identifier '8414721' matches 2 records" in md

    @pytest.mark.asyncio
    async def test_station_tool_json_carries_the_warning(self, dup_nc):
        """stofs_get_station_forecast reports the duplicated identifier too."""
        from stofs_mcp.tools.forecast import stofs_get_station_forecast

        client = STOFSClient(backoff_factor=0)
        client.download_netcdf = _fresh_copies(dup_nc)
        js = json.loads(
            await stofs_get_station_forecast(
                make_ctx(client),
                station_id="8414721",
                model=STOFSModel.GLOBAL_2D,
                cycle_date="2026-10-26",
                cycle_hour="12",
                response_format="json",
            )
        )
        assert "matches 2 records" in js["station_warning"]
        js2 = json.loads(
            await stofs_get_station_forecast(
                make_ctx(client),
                station_id="8418150",
                model=STOFSModel.GLOBAL_2D,
                cycle_date="2026-10-26",
                cycle_hour="12",
                response_format="json",
            )
        )
        assert js2["station_warning"] is None


class TestEpochSentence:
    """The datum note names the tidal-datum epoch for CO-OPS tidal datums only."""

    @pytest.mark.asyncio
    async def test_msl_comparison_mentions_the_epoch_and_navd_does_not(
        self, station_nc
    ):
        """LMSL vs MSL carries the sentence; NAVD88 vs NAVD (a geodetic datum) does not."""
        from stofs_mcp.tools.validation import stofs_compare_with_observations

        async def run(zeta, date, start):
            path = station_nc(zeta, start, [0.2] * 300)
            client = STOFSClient(backoff_factor=0)
            client.download_netcdf = AsyncMock(return_value=path)
            client.fetch_coops_observations = AsyncMock(
                return_value={
                    "data": [
                        {"t": t, "v": "0.100", "f": "0,0,0,0", "q": "v"}
                        for t in six_minute_times(start, 300)
                    ]
                }
            )
            return json.loads(
                await stofs_compare_with_observations(
                    make_ctx(client),
                    station_id="8443970",
                    model=STOFSModel.ATLANTIC_3D,
                    cycle_date=date,
                    cycle_hour="12",
                    lead_start_hours=0,
                    lead_end_hours=6,
                    response_format="json",
                )
            )

        msl = await run(ZETA_3D_V31, "2026-10-26", "2026-10-25 12:00")
        navd = await run(ZETA_3D_V21, "2026-06-01", "2026-05-31 12:00")
        assert msl["coops_datum"] == "MSL" and navd["coops_datum"] == "NAVD"
        sentence = (
            "The CO-OPS MSL datum is defined on a tidal-datum epoch (1983–2001 at most "
            "stations); recent mean sea level may differ from it, so a mean bias includes "
            "that difference unless the model carries present-day mean level. The "
            "station's epoch is not checked here."
        )
        assert sentence in msl["datum_note"]
        assert "tidal-datum epoch" not in navd["datum_note"]
