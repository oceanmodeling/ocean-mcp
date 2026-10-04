"""Live integration tests for ofs-mcp.

These tests require internet access and hit real NOAA servers.
Run with: uv run pytest tests/test_live.py -v -s
Skip in CI with: -m "not integration"
"""

import pytest

from ofs_mcp.client import OFSClient
from ofs_mcp.models import OFS_MODELS


@pytest.fixture
async def client():
    """Create an OFSClient for live tests."""
    c = OFSClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_latest_cycle_cbofs(client):
    """Resolve the latest CBOFS forecast cycle from S3."""
    result = await client.resolve_latest_cycle("cbofs", num_days=3)
    if result is None:
        pytest.skip("No CBOFS cycle found on S3 in the last 3 days")
    date_str, cycle_str = result
    assert len(date_str) == 8, f"Expected YYYYMMDD, got {date_str}"
    assert cycle_str in OFS_MODELS["cbofs"]["cycles"]
    print(f"\nLatest CBOFS cycle: {date_str} {cycle_str}z")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_s3_file_exists_cbofs(client):
    """Check that at least one CBOFS forecast file exists on S3."""
    result = await client.resolve_latest_cycle("cbofs", num_days=3)
    if result is None:
        pytest.skip("No CBOFS cycle found on S3")
    date_str, cycle_str = result
    # Check forecast hour 1
    url = client.build_s3_url("cbofs", date_str, cycle_str, "f", 1)
    exists = await client.check_file_exists(url)
    assert exists, f"Expected forecast file to exist at {url}"
    print(f"\nFile exists: {url}")


@pytest.mark.integration
@pytest.mark.parametrize(
    "model, lat, lon",
    [
        ("cbofs", 39.2667, -76.5783),  # Baltimore (ROMS)
        ("tbofs", 27.7606, -82.6269),  # St. Petersburg (ROMS since the upgrade)
        ("nyofs", 40.7006, -74.0142),  # The Battery (POM)
    ],
)
def test_fmrc_point_series_is_continuous(client, model, lat, lon):
    """The FMRC point extraction returns a multi-day series, not one point."""
    from ofs_mcp.utils import extract_point_timeseries

    try:
        nc = client.open_opendap(model)
    except RuntimeError as exc:
        pytest.skip(f"{model} OPeNDAP unavailable: {exc}")
    try:
        out = extract_point_timeseries(nc, model, "water_level", lat, lon)
    finally:
        nc.close()
    assert len(out["values"]) >= 48, f"{model}: only {len(out['values'])} points"
    print(
        f"\n{model}: {len(out['values'])} points {out['times'][0]} → {out['times'][-1]}"
    )
