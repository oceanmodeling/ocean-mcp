"""Live integration tests against real ERDDAP servers.

Run manually: uv run pytest tests/test_live.py -v -s
These tests make actual HTTP requests to public ERDDAP servers.
"""

from datetime import datetime, timedelta

import pytest

from erddap_mcp.client import ERDDAPClient
from erddap_mcp.utils import parse_erddap_json

# PacIOOS, not coastwatch.pfeg.noaa.gov: NOAA CoastWatch's ERDDAP started
# returning 403 to GitHub Actions' runner IPs around 2026-06-08 (weekly drift
# issue #86) while staying reachable from everywhere else we checked — an
# upstream network policy on NOAA's end, not an ERDDAP/API change. PacIOOS
# runs the same ERDDAP software and has stayed reachable from CI.
# Its certificate chains to emSign Root CA - G1, which certifi 2026.10.18
# dropped and 2026.10.19 restored; a CERTIFICATE_VERIFY_FAILED here means the
# CA bundle changed again, not that ERDDAP drifted (weekly drift issue #126).
PACIOOS_URL = "https://pae-paha.pacioos.hawaii.edu/erddap"

# Hard per-test ceiling. PacIOOS has intermittently stalled for GitHub's
# runners (#126); a stalled request then sat through the client's 60 s timeout
# and retries until the 5-minute CI step was killed, with no traceback. 45 s x
# 5 tests stays under that budget, so a stall fails one test with a traceback.
# Requires pytest-timeout.
pytestmark = pytest.mark.timeout(45)


@pytest.fixture
async def client():
    c = ERDDAPClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_sst(client):
    """Search PacIOOS for 'sea surface temperature' — should return results."""
    data = await client.search(
        PACIOOS_URL, "sea surface temperature", items_per_page=10
    )
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected search results for SST"
    # Check structure
    first = rows[0]
    assert "Dataset ID" in first or "datasetID" in first


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_info_sst(client):
    """Get info for dhw_5km (Coral Reef Watch SST) on PacIOOS — should return variables."""
    data = await client.get_info(PACIOOS_URL, "dhw_5km")
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected info rows"
    # Should have dimension and variable rows
    row_types = {r.get("Row Type") for r in rows}
    assert (
        "variable" in row_types or "dimension" in row_types or "attribute" in row_types
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tabledap_buoy(client):
    """Get tabledap data from a PacIOOS water quality buoy — should return rows."""
    # Anchor the 2-day window to the dataset's own last timestamp instead of
    # `now`. wqb_04 stopped reporting on 2026-08-13 (weekly drift issue #121)
    # and a `now-2days` window against an offline buoy is ERDDAP's usual
    # "no matching results" 404 -- a sensor outage, not API drift. Reading
    # maxTime from allDatasets keeps this test about the tabledap API and
    # still exercises a string constraint plus two time constraints.
    meta = await client.get_all_datasets(
        PACIOOS_URL, 'datasetID,maxTime&datasetID="wqb_04"'
    )
    meta_rows = parse_erddap_json(meta)
    assert meta_rows, "wqb_04 is no longer listed on PacIOOS; pick another dataset"
    max_time = meta_rows[0]["maxTime"]
    assert max_time, "wqb_04 has no maxTime in allDatasets"

    end = datetime.fromisoformat(max_time.replace("Z", "+00:00"))
    start = end - timedelta(days=2)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    query = f"time,temperature&time>={start.strftime(fmt)}&time<={end.strftime(fmt)}"
    data = await client.get_tabledap(PACIOOS_URL, "wqb_04", query)
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected tabledap rows"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_all_datasets(client):
    """List all datasets on PacIOOS — should return 100+ datasets."""
    data = await client.get_all_datasets(PACIOOS_URL, "datasetID,title")
    rows = parse_erddap_json(data)
    assert len(rows) > 100, f"Expected 100+ datasets, got {len(rows)}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_griddap_small_subset(client):
    """Get a small griddap data subset — should return grid values."""
    # Latest time step, small spatial area, for dhw_5km's SST variable
    query = "CRW_SST[(last)][(36):(37)][(-123):(-122)]"
    data = await client.get_griddap(PACIOOS_URL, "dhw_5km", query)
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected griddap data rows"
    # Should have lat, lon, and CRW_SST columns
    first = rows[0]
    assert "latitude" in first or "CRW_SST" in first
