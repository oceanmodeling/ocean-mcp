"""Unit tests for recon-mcp tool functions with mocked HTTP.

Tests cover all five tool modules:
  - recon_list_missions (missions.py)
  - recon_get_hdobs (hdob.py)
  - recon_get_vdms (vdm.py)
  - recon_get_fixes (fixes.py)
  - recon_list_sfmr (sfmr.py)

Each tool is called directly with a mock Context object.  HTTP calls
are intercepted by respx so no network access occurs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from recon_mcp.client import ReconClient, RetryTransport
from recon_mcp.models import (
    AOML_SFMR_BASE,
    ATCF_ARCHIVE_BASE,
    ATCF_BDECK_BASE,
    ATCF_FIX_BASE,
    NHC_RECON_ARCHIVE_BASE,
)

# Import tool functions directly
from recon_mcp.tools.fixes import recon_get_fixes
from recon_mcp.tools.hdob import recon_get_hdobs
from recon_mcp.tools.missions import recon_list_missions
from recon_mcp.tools.sfmr import recon_get_sfmr, recon_list_sfmr
from recon_mcp.tools.vdm import recon_get_vdms

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file from the fixtures directory."""
    return (FIXTURES_DIR / name).read_text()


# ---------------------------------------------------------------------------
# Helper: build a mock MCP Context
# ---------------------------------------------------------------------------


def make_ctx(client: ReconClient) -> MagicMock:
    """Build a mock ``Context`` whose lifespan_context holds *client*.

    The tool functions access the client via:
        ctx.request_context.lifespan_context["recon_client"]
    """
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"recon_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Fixture: ReconClient backed by a respx-mocked transport
# ---------------------------------------------------------------------------


@pytest.fixture
def recon_client() -> ReconClient:
    """Return a fresh ``ReconClient`` (backoff_factor=0 so the retry transport
    replays transient failures with no real delay)."""
    return ReconClient(backoff_factor=0)


@pytest.fixture
def ctx(recon_client: ReconClient) -> MagicMock:
    """Return a mock Context wired to *recon_client*."""
    return make_ctx(recon_client)


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = ReconClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


# ===================================================================
# Tests for recon_list_missions
# ===================================================================


class TestListMissions:
    """Tests for the recon_list_missions tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_markdown(self, ctx: MagicMock) -> None:
        """Listing HDOB missions returns a markdown table with filenames."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(ctx, year=2024, product="hdob", basin="al")

        assert "## Reconnaissance Archive" in result
        assert "URNT15-KNHC.202410091200.txt" in result
        assert "URNT15-KNHC.202410091300.txt" in result
        assert "3 files" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_json(self, ctx: MagicMock) -> None:
        """Listing missions with response_format='json' returns valid JSON."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] == 3
        assert "retrieved_at" in parsed
        filenames = [entry["filename"] for entry in parsed["data"]]
        assert "URNT15-KNHC.202410091200.txt" in filenames

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_empty_directory(self, ctx: MagicMock) -> None:
        """An empty directory listing returns a helpful 'no files found' message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_list_missions(ctx, year=2024, product="hdob", basin="al")

        assert "No HDOB files found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_month_filter(self, ctx: MagicMock) -> None:
        """Filtering by month narrows results to matching filenames."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        # The fixture files all contain "202410" so month=10 should match all
        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", month=10
        )
        assert "3 files" in result

        # Month=1 should match none
        result_empty = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", month=1
        )
        assert "No HDOB files found" in result_empty

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_404_error(self, ctx: MagicMock) -> None:
        """A 404 from the archive returns a user-friendly error message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/1990/AHONT1/"
        respx.get(dir_url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_list_missions(ctx, year=1990, product="hdob", basin="al")

        assert "not found" in result.lower() or "404" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_vdm_product(self, ctx: MagicMock) -> None:
        """Listing VDM files uses the REPNT2 directory path."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(ctx, year=2024, product="vdm", basin="al")

        assert "VDM" in result
        assert "3 files" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_limit(self, ctx: MagicMock) -> None:
        """The limit parameter caps the number of returned entries."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", limit=2
        )

        assert "2 files" in result


# ===================================================================
# Tests for recon_get_hdobs
# ===================================================================


class TestGetHdobs:
    """Tests for the recon_get_hdobs tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_markdown(self, ctx: MagicMock) -> None:
        """Fetching HDBOs returns a markdown table with observation data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        # Mock each individual bulletin fetch — all three files return the same bulletin
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(ctx, year=2024, basin="al", limit=3)

        assert "## HDOB Flight-Level Observations" in result
        assert "observations" in result.lower()
        # Should contain lat/lon from the fixture
        assert "20241009" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_json(self, ctx: MagicMock) -> None:
        """Fetching HDBOs with JSON format returns valid JSON with observation data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx, year=2024, basin="al", limit=3, response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] > 0
        # Each observation should have lat/lon
        obs = parsed["data"][0]
        assert "lat" in obs
        assert "lon" in obs
        assert "sfmr_sfc_wind_kt" in obs

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_empty_archive(self, ctx: MagicMock) -> None:
        """An empty directory returns a 'no bulletins found' message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_get_hdobs(ctx, year=2024, basin="al")

        assert "No HDOB bulletins found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_observation_values(self, ctx: MagicMock) -> None:
        """Parsed HDOB observations contain expected numeric values from fixture."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx, year=2024, basin="al", limit=1, response_format="json"
        )

        parsed = json.loads(result)
        obs = parsed["data"][0]
        # First record of the real Milton bulletin (070200, in the eye):
        # 2400N 08542W = 24.0, -85.7 (degrees + minutes), 907.0 mb.
        assert obs["date"] == "20241009"
        assert obs["time"] == "070200"
        assert obs["lat"] == pytest.approx(24.0)
        assert obs["lon"] == pytest.approx(-85.7)
        assert obs["extrapolated_slp_mb"] == pytest.approx(907.0)
        assert obs["fl_wind_speed_kt"] == 6
        assert obs["sfmr_sfc_wind_kt"] == 53
        assert obs["aircraft"] == "AF300"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_bulletin_fetch_failure(self, ctx: MagicMock) -> None:
        """If individual bulletin fetches fail, the tool still returns gracefully."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        # All three bulletin fetches fail
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        result = await recon_get_hdobs(ctx, year=2024, basin="al", limit=3)

        # Should gracefully report the parsing failure
        assert "could not parse" in result.lower() or "HDOB" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_date_filter(self, ctx: MagicMock) -> None:
        """Month and day filters narrow the bulletin list before fetching."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx, year=2024, basin="al", month=10, day=9, limit=20
        )

        # All fixture files are from 20241009, so all should match
        assert "HDOB" in result
        assert "observations" in result.lower()


# ===================================================================
# Tests for recon_get_vdms
# ===================================================================


class TestGetVdms:
    """Tests for the recon_get_vdms tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_markdown(self, ctx: MagicMock) -> None:
        """Fetching VDMs returns a markdown table with storm center data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        result = await recon_get_vdms(ctx, year=2024, basin="al", limit=3)

        assert "## Vortex Data Messages" in result
        assert "AL142024" in result
        assert "VDMs" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_json(self, ctx: MagicMock) -> None:
        """Fetching VDMs in JSON format returns parseable structured data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        result = await recon_get_vdms(
            ctx, year=2024, basin="al", limit=3, response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] == 3
        first = parsed["data"][0]
        assert first["storm_id"] == "AL142024"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_parsed_fields(self, ctx: MagicMock) -> None:
        """VDM parser extracts min SLP, max winds, and eye info from the fixture."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        result = await recon_get_vdms(
            ctx, year=2024, basin="al", limit=1, response_format="json"
        )

        parsed = json.loads(result)
        record = parsed["data"][0]
        # Real Milton VDM; year and month come from the archive file name.
        assert record["storm_id"] == "AL142024"
        assert record["fix_time_utc"] == "2024-10-09T07:02:10Z"
        assert (record["center_lat"], record["center_lon"]) == (24.0, -85.71)
        assert record["min_slp_mb"] == 910
        assert record["max_sfc_wind_inbound_kt"] == 158
        assert record["max_fl_wind_outbound_kt"] == 135
        assert record["eye_diameter_nm"] == 8

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_storm_id_filter(self, ctx: MagicMock) -> None:
        """Filtering by storm_id narrows results to matching VDMs."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        # Filter for the correct storm — should find all 3
        result = await recon_get_vdms(
            ctx,
            year=2024,
            basin="al",
            storm_id="AL142024",
            limit=3,
            response_format="json",
        )
        parsed = json.loads(result)
        assert parsed["record_count"] == 3

        # Filter for a non-existent storm — should find none
        result_empty = await recon_get_vdms(
            ctx,
            year=2024,
            basin="al",
            storm_id="AL992024",
            limit=3,
        )
        assert "No VDMs found" in result_empty

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_empty_directory(self, ctx: MagicMock) -> None:
        """An empty VDM directory returns a user-friendly message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_get_vdms(ctx, year=2024, basin="al")

        assert "No VDM files found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_404_error(self, ctx: MagicMock) -> None:
        """A 404 response returns a helpful error message, not a stack trace."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/1980/REPNT2/"
        respx.get(dir_url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_get_vdms(ctx, year=1980, basin="al")

        assert "not found" in result.lower() or "404" in result


# ===================================================================
# Tests for recon_get_fixes
# ===================================================================


class TestGetFixes:
    """Tests for the recon_get_fixes tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_markdown(self, ctx: MagicMock) -> None:
        """Fetching f-deck fixes returns a markdown table with fix records."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(ctx, basin="al", storm_number=14, year=2024)

        assert "## ATCF Aircraft Fixes" in result
        assert "AL142024" in result
        assert "fix records" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_json(self, ctx: MagicMock) -> None:
        """Fetching fixes with JSON format returns valid structured data."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx, basin="al", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] == 8
        first = parsed["data"][0]
        assert first["basin"] == "AL"
        assert first["cyclone_num"] == 14
        assert first["fix_type"] == "AIRC"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_latlon_parsing(self, ctx: MagicMock) -> None:
        """ATCF lat/lon strings are correctly parsed to decimal degrees."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx, basin="al", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        first = parsed["data"][0]
        # F-deck encodes position in hundredths of a degree, not zero padded:
        # 2400N → 24.00, 8571W → -85.71 (the 0702Z Milton aircraft fix).
        assert first["lat"] == pytest.approx(24.0)
        assert first["lon"] == pytest.approx(-85.71)
        assert first["max_wind_kt"] == 158
        assert first["min_pressure_mb"] == 910

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_404(self, ctx: MagicMock) -> None:
        """A 404 for the f-deck file returns a user-friendly error."""
        url = f"{ATCF_FIX_BASE}/fal992024.dat"
        respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))
        archive_url = f"{ATCF_ARCHIVE_BASE}/2024/fal992024.dat.gz"
        respx.get(archive_url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_get_fixes(ctx, basin="al", storm_number=99, year=2024)

        assert "not found" in result.lower() or "404" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_empty_file(self, ctx: MagicMock) -> None:
        """An empty f-deck file returns a 'no records' message."""
        url = f"{ATCF_FIX_BASE}/fal012024.dat"
        respx.get(url).mock(return_value=httpx.Response(200, text="\n\n"))

        result = await recon_get_fixes(ctx, basin="al", storm_number=1, year=2024)

        assert "No fix records found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_pressure_and_wind(self, ctx: MagicMock) -> None:
        """Fix records include wind and pressure values from the f-deck."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx, basin="al", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        # Analysis fix: pressure only. Satellite (DPNT) fix: wind and pressure.
        analysis, dpnt = parsed["data"][1], parsed["data"][3]
        assert (analysis["max_wind_kt"], analysis["min_pressure_mb"]) == (None, 908)
        assert (dpnt["max_wind_kt"], dpnt["min_pressure_mb"]) == (127, 934)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_ep_basin(self, ctx: MagicMock) -> None:
        """EP basin correctly builds the f-deck URL with 'ep' prefix."""
        url = f"{ATCF_FIX_BASE}/fep052026.dat"
        # Real EP05 2026 analysis fix; longitudes of 100+ have five digits.
        ep_record = (
            "EP, 05, 202607131200,  70, ANAL,         CI,  , 1220N, 10100W,"
            "    10, 2,  30, 2, 1009, 2, MEAS,    ,     ,\n"
        )
        respx.get(url).mock(return_value=httpx.Response(200, text=ep_record))

        result = await recon_get_fixes(
            ctx, basin="ep", storm_number=5, year=2026, response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["record_count"] == 1
        record = parsed["data"][0]
        assert record["basin"] == "EP"
        assert (record["lat"], record["lon"]) == (12.2, -101.0)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_archived_season(self, ctx: MagicMock) -> None:
        """Past seasons are not in fix/: fall back to the gzipped archive."""
        import gzip

        respx.get(f"{ATCF_FIX_BASE}/fal142024.dat").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(f"{ATCF_ARCHIVE_BASE}/2024/fal142024.dat.gz").mock(
            return_value=httpx.Response(200, content=gzip.compress(fdeck.encode()))
        )

        result = await recon_get_fixes(
            ctx, basin="AL", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["record_count"] == 8
        assert parsed["data"][0]["min_pressure_mb"] == 910


# ===================================================================
# Tests for recon_list_sfmr
# ===================================================================


class TestListSfmr:
    """Tests for the recon_list_sfmr tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_markdown(self, ctx: MagicMock) -> None:
        """Listing SFMR files returns a markdown table with decoded filenames."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(ctx, year=2022, storm_name="ian")

        assert "## SFMR Files" in result
        assert "Ian" in result
        assert "AFRC_SFMR20220926H1.nc" in result
        assert "AFRC_SFMR20220927U1.nc" in result
        assert "AFRC_SFMR20220928I1.nc" in result
        assert "3 SFMR files" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_json(self, ctx: MagicMock) -> None:
        """Listing SFMR files in JSON returns decoded aircraft information."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(
            ctx, year=2022, storm_name="ian", response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["record_count"] == 3
        # Verify aircraft code decoding
        filenames = {d["filename"]: d for d in parsed["data"]}
        assert filenames["AFRC_SFMR20220926H1.nc"]["aircraft_code"] == "H"
        assert "P-3" in filenames["AFRC_SFMR20220926H1.nc"]["aircraft"]
        assert filenames["AFRC_SFMR20220927U1.nc"]["aircraft_code"] == "U"
        assert "WC-130J" in filenames["AFRC_SFMR20220927U1.nc"]["aircraft"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_no_files(self, ctx: MagicMock) -> None:
        """An empty SFMR directory returns a 'no files' message."""
        url = f"{AOML_SFMR_BASE}/2024/fake/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_list_sfmr(ctx, year=2024, storm_name="fake")

        assert "No SFMR NetCDF files found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_404(self, ctx: MagicMock) -> None:
        """A 404 for the SFMR directory returns a user-friendly error."""
        url = f"{AOML_SFMR_BASE}/1999/unknown/"
        respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_list_sfmr(ctx, year=1999, storm_name="unknown")

        assert "not found" in result.lower() or "404" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_date_decoding(self, ctx: MagicMock) -> None:
        """SFMR filenames are decoded to extract date, aircraft, and sequence."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(
            ctx, year=2022, storm_name="ian", response_format="json"
        )

        parsed = json.loads(result)
        first = parsed["data"][0]
        assert first["date"] == "20220926"
        assert first["mission_seq"] == "1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_storm_name_case(self, ctx: MagicMock) -> None:
        """Storm name is lowercased in the URL and title-cased in output."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        # Pass mixed-case name — client should lowercase it for URL
        result = await recon_list_sfmr(ctx, year=2022, storm_name="Ian")

        assert "Ian" in result  # Title-cased in output


# ===================================================================
# Tests for output caps (max_records wiring + truncation envelope)
# ===================================================================


class TestOutputCaps:
    """Tests that max_records is wired through to the JSON/markdown caps."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_hdobs_max_records_truncates_json(self, ctx: MagicMock) -> None:
        """A small max_records truncates the JSON observation list and flags it."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        # 3 bulletins x 20 observations each = 60 total observations.
        result = await recon_get_hdobs(
            ctx,
            year=2024,
            basin="al",
            limit=3,
            max_records=5,
            response_format="json",
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["record_count"] == 5
        assert parsed["total_count"] == 60
        assert "hint" in parsed

    @respx.mock
    @pytest.mark.asyncio
    async def test_hdobs_max_records_under_total_not_truncated(
        self, ctx: MagicMock
    ) -> None:
        """max_records above the total leaves truncated False."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx,
            year=2024,
            basin="al",
            limit=1,
            max_records=2000,
            response_format="json",
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is False
        assert parsed["record_count"] == parsed["total_count"] == 20
        assert "hint" not in parsed

    @respx.mock
    @pytest.mark.asyncio
    async def test_fixes_max_records_keeps_most_recent(self, ctx: MagicMock) -> None:
        """ATCF f-decks are oldest-first; a max_records cap keeps the tail
        (most recent fix), not the head."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx,
            basin="al",
            storm_number=14,
            year=2024,
            max_records=1,
            response_format="json",
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["record_count"] == 1
        assert parsed["total_count"] == 8
        # The fixture's last record is the most recent: the 1059Z Key West
        # radar fix (real f-decks are in ascending time order).
        assert parsed["data"][0]["datetime"] == "202410091059"
        assert parsed["data"][0]["fix_type"] == "RDRD"

    @respx.mock
    @pytest.mark.asyncio
    async def test_missions_max_records_truncates_markdown(
        self, ctx: MagicMock
    ) -> None:
        """A small max_records truncates the markdown table with a footer."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", max_records=2
        )

        assert "Showing the first 2 of 3 files" in result
        assert "(truncated)" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_max_records_keeps_most_recent(
        self, ctx: MagicMock
    ) -> None:
        """SFMR files are listed oldest-first; a cap keeps the most recent."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(
            ctx, year=2022, storm_name="ian", max_records=1, response_format="json"
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["record_count"] == 1
        assert parsed["total_count"] == 3
        # Fixture files sort 20220926 < 20220927 < 20220928 — the most
        # recent (0928) must be the one kept.
        assert parsed["data"][0]["date"] == "20220928"


# ===================================================================
# Tests for recon_get_sfmr (radial wind profile, requires NetCDF download)
# ===================================================================

SAMPLE_BDECK_IAN = (
    "AL, 09, 2022092600,   , BEST,   0,  197N,  0835W,  40,  998, TS,\n"
    "AL, 09, 2022092700,   , BEST,   0,  213N,  0862W,  85,  965, HU,\n"
)


def _build_sfmr_nc_bytes(tmp_path, name: str, date_str: str) -> bytes:
    """Build a minimal SFMR NetCDF file and return its raw bytes."""
    from netCDF4 import Dataset

    path = tmp_path / name
    ds = Dataset(str(path), "w", format="NETCDF4")
    try:
        n = 5
        ds.createDimension("obs", n)
        date_var = ds.createVariable("DATE", "i4", ("obs",))
        time_var = ds.createVariable("TIME", "i4", ("obs",))
        lat_var = ds.createVariable("LAT", "f4", ("obs",))
        lon_var = ds.createVariable("LON", "f4", ("obs",))
        sws_var = ds.createVariable("SWS", "f4", ("obs",))
        date_var[:] = [int(date_str)] * n
        time_var[:] = [120000 + i * 100 for i in range(n)]
        lat_var[:] = [20.0 + i * 0.01 for i in range(n)]
        lon_var[:] = [-80.0 - i * 0.01 for i in range(n)]
        sws_var[:] = [30.0 + i for i in range(n)]
    finally:
        ds.close()
    return path.read_bytes()


class TestGetSfmr:
    """Tests for the recon_get_sfmr tool, including max_records wiring."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_sfmr_max_records_truncates_and_keeps_most_recent(
        self, ctx: MagicMock, tmp_path
    ) -> None:
        """AOML's raw directory listing groups files by agency prefix
        (AFRC_* vs NOAA_*), not chronologically — live Ian/Ida/Laura
        directories all mix both agencies. max_records must keep the
        files with the most recent *decoded date*, not the files that
        happen to sort last as raw strings, and flag truncation in the
        envelope.

        Fixture mirrors the real 2022/ian directory shape: sorting these
        four filenames as raw strings groups both AFRC_* entries before
        both NOAA_* entries (since 'A' < 'N'), which would wrongly keep
        the tail-2 as {NOAA_SFMR20220926H1.nc, NOAA_SFMR20220928H1.nc} —
        dropping the genuinely newest file (AFRC_SFMR20220929U1.nc) and
        keeping a file older (0926) than one it displaced (AFRC 0927).
        Sorting by decoded date instead correctly keeps the 0928/0929
        pair.
        """
        sfmr_url = f"{AOML_SFMR_BASE}/2022/ian/"
        btk_url = f"{ATCF_BDECK_BASE}/bal092022.dat"

        listing_html = (
            "<html><body><pre>"
            '<a href="../">Parent Directory</a>'
            '<a href="NOAA_SFMR20220926H1.nc">NOAA_SFMR20220926H1.nc</a>'
            '<a href="AFRC_SFMR20220927U1.nc">AFRC_SFMR20220927U1.nc</a>'
            '<a href="NOAA_SFMR20220928H1.nc">NOAA_SFMR20220928H1.nc</a>'
            '<a href="AFRC_SFMR20220929U1.nc">AFRC_SFMR20220929U1.nc</a>'
            "</pre></body></html>"
        )
        respx.get(sfmr_url).mock(return_value=httpx.Response(200, text=listing_html))
        respx.get(btk_url).mock(return_value=httpx.Response(200, text=SAMPLE_BDECK_IAN))

        for fname, date_str in (
            ("NOAA_SFMR20220926H1.nc", "20220926"),
            ("AFRC_SFMR20220927U1.nc", "20220927"),
            ("NOAA_SFMR20220928H1.nc", "20220928"),
            ("AFRC_SFMR20220929U1.nc", "20220929"),
        ):
            nc_bytes = _build_sfmr_nc_bytes(tmp_path, fname, date_str)
            respx.get(sfmr_url + fname).mock(
                return_value=httpx.Response(200, content=nc_bytes)
            )

        result = await recon_get_sfmr(
            ctx,
            year=2022,
            storm_name="ian",
            storm_number=9,
            basin="al",
            max_records=2,
            response_format="json",
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["record_count"] == 2
        assert parsed["total_count"] == 4
        assert "hint" in parsed
        filenames = {m["filename"] for m in parsed["missions"]}
        # Correct (date-sorted) tail-2: the 0928 and 0929 files.
        assert filenames == {"NOAA_SFMR20220928H1.nc", "AFRC_SFMR20220929U1.nc"}
        # Raw-filename sort would wrongly keep this (0926) instead of the
        # genuinely newest file (0929, dropped entirely by the old bug).
        assert "NOAA_SFMR20220926H1.nc" not in filenames
        assert "AFRC_SFMR20220929U1.nc" in filenames

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_sfmr_no_truncation_when_under_cap(
        self, ctx: MagicMock, tmp_path
    ) -> None:
        """When available files are within max_records, nothing is truncated."""
        sfmr_url = f"{AOML_SFMR_BASE}/2022/ian/"
        btk_url = f"{ATCF_BDECK_BASE}/bal092022.dat"

        listing_html = (
            "<html><body><pre>"
            '<a href="../">Parent Directory</a>'
            '<a href="AFRC_SFMR20220926H1.nc">AFRC_SFMR20220926H1.nc</a>'
            "</pre></body></html>"
        )
        respx.get(sfmr_url).mock(return_value=httpx.Response(200, text=listing_html))
        respx.get(btk_url).mock(return_value=httpx.Response(200, text=SAMPLE_BDECK_IAN))

        nc_bytes = _build_sfmr_nc_bytes(tmp_path, "AFRC_SFMR20220926H1.nc", "20220926")
        respx.get(sfmr_url + "AFRC_SFMR20220926H1.nc").mock(
            return_value=httpx.Response(200, content=nc_bytes)
        )

        result = await recon_get_sfmr(
            ctx,
            year=2022,
            storm_name="ian",
            storm_number=9,
            basin="al",
            max_records=10,
            response_format="json",
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is False
        assert parsed["record_count"] == parsed["total_count"] == 1
        assert "hint" not in parsed


# ===================================================================
# Tests for error handling
# ===================================================================


class TestErrorHandling:
    """Tests for graceful error handling across all tools."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error_hdobs(self, ctx: MagicMock) -> None:
        """A timeout during HDOB fetch produces a user-friendly message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        respx.get(dir_url).mock(side_effect=httpx.ConnectTimeout("Timed out"))

        result = await recon_get_hdobs(ctx, year=2024, basin="al")

        assert "timed out" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error_fixes(self, ctx: MagicMock) -> None:
        """A timeout during fix fetch produces a user-friendly message."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        respx.get(url).mock(side_effect=httpx.ReadTimeout("Timed out"))

        result = await recon_get_fixes(ctx, basin="al", storm_number=14, year=2024)

        assert "timed out" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_500_error_vdms(self, ctx: MagicMock) -> None:
        """A 500 error returns an error message about server unavailability."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        respx.get(dir_url).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        result = await recon_get_vdms(ctx, year=2024, basin="al")

        assert "500" in result or "unavailable" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_list_missions(self, ctx: MagicMock) -> None:
        """A generic network error returns a message with the exception type."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        respx.get(dir_url).mock(side_effect=httpx.ConnectError("Connection refused"))

        result = await recon_list_missions(ctx, year=2024, product="hdob", basin="al")

        assert "error" in result.lower() or "ConnectError" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_invalid_product_list_missions(self, ctx: MagicMock) -> None:
        """An invalid product name returns a ValueError-based error message."""
        result = await recon_list_missions(
            ctx, year=2024, product="invalid_product", basin="al"
        )

        # The client.build_archive_dir_url raises ValueError for unknown products
        assert "error" in result.lower() or "invalid" in result.lower()
