"""Integration tests that hit the live HYCOM THREDDS server.

Run with: pytest tests/test_live.py -v
These are excluded from CI unit test runs.
"""

import math

import pytest

from rtofs_mcp.client import RTOFSClient

# Hard per-test ceiling. HYCOM THREDDS intermittently stalls (connects, then
# never responds); without a cap the client's 120s timeout x retries can exceed
# the 5-minute CI job budget, getting the whole job SIGKILL'd with no
# diagnostics. 45s x 5 tests stays well under that budget and a hang fails the
# one test with a traceback instead of killing the run. Requires pytest-timeout.
pytestmark = pytest.mark.timeout(45)


@pytest.fixture
async def client():
    """Create and clean up a live client.

    Fail fast: these are single-point smoke queries. Healthy round-trips take
    1-25s (HYCOM extracts ~1 time step/s when its cache is cold), so a 30s
    timeout with a single retry rides out a one-off blip without letting a
    true stall consume the job budget.
    """
    c = RTOFSClient(timeout=30.0, max_retries=1)
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_ssh_point_query(client):
    """Fetch SSH at an open-ocean point from HYCOM THREDDS.

    Use a deep NW-Atlantic point (35N, 65W), NOT a coastal one: RTOFS/HYCOM
    is a ~9 km global model and masks near-shore cells (e.g. NY Harbor) as
    land, so SSH there is legitimately NaN — testing such a point would be a
    false negative about the live data path, not a real check.
    """
    rows = await client.fetch_point_csv(
        dataset_key="ssh",
        variable="surf_el",
        latitude=35.0,
        longitude=-65.0,
        time="present",
    )
    assert len(rows) >= 1, "Expected at least one SSH value"
    assert "surf_el" in rows[0]
    val = rows[0]["surf_el"]
    assert isinstance(val, float)
    assert not math.isnan(val), "SSH should not be NaN in the open ocean"
    # SSH should be reasonable (between -5 and 5 meters)
    assert -5.0 < val < 5.0
    print(f"\nSSH at 35N,65W: {val:.4f} m")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_sst_surface_timeseries(client):
    """Fetch SST time series at an open-ocean point (35N, 65W).

    Coastal cells are masked in the ~9 km HYCOM grid (see SSH test), so an
    open-ocean point is required to exercise the live time-series path.
    No time arguments: this is the default window the surface-forecast tool
    sends. It used to be ``temporal=all``, which took minutes (issue #127).
    """
    rows = await client.fetch_point_csv(
        dataset_key="sst",
        variable="water_temp",
        latitude=35.0,
        longitude=-65.0,
        vert_coord=0.0,  # Surface
    )
    valid = [r for r in rows if not math.isnan(r.get("water_temp", float("nan")))]
    assert len(valid) >= 5, f"Expected >=5 valid SST rows, got {len(valid)}"
    print(f"\nSST time series: {len(valid)} points")
    print(f"  First: {valid[0]['time']} → {valid[0]['water_temp']:.2f} °C")
    print(f"  Last:  {valid[-1]['time']} → {valid[-1]['water_temp']:.2f} °C")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_temperature_profile(client):
    """Fetch temperature depth profile in the Gulf Stream."""
    rows = await client.fetch_point_csv(
        dataset_key="sst",
        variable="water_temp",
        latitude=35.0,
        longitude=-74.0,  # Gulf Stream area
        time="present",
    )
    valid = [r for r in rows if not math.isnan(r.get("water_temp", float("nan")))]
    assert len(valid) >= 3, "Expected at least 3 valid depth levels"
    print("\nTemperature profile (Gulf Stream, 35°N 74°W):")
    for r in valid[:10]:
        print(f"  {r.get('vertCoord', 0):.0f} m: {r['water_temp']:.2f} °C")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_dataset_availability(client):
    """Check that key datasets are available on HYCOM THREDDS."""
    for key in ["ssh", "sst", "sss", "currents"]:
        available = await client.check_dataset_available(key)
        print(f"\n  {key}: {'available' if available else 'unavailable'}")
        assert available, f"Dataset '{key}' should be available"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_salinity_point(client):
    """Fetch salinity at a mid-ocean point."""
    rows = await client.fetch_point_csv(
        dataset_key="sss",
        variable="salinity",
        latitude=30.0,
        longitude=-50.0,  # Mid-Atlantic
        time="present",
        vert_coord=0.0,
    )
    assert len(rows) >= 1
    val = rows[0]["salinity"]
    assert not math.isnan(val), "Salinity should not be NaN at mid-ocean"
    # Ocean salinity is typically 33-37 PSU
    assert 30.0 < val < 40.0, f"Salinity {val} PSU is outside expected range"
    print(f"\nSalinity at (30°N, 50°W): {val:.2f} PSU")
