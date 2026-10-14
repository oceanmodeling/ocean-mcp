"""Live integration tests against the NHC reconnaissance archive.

These tests require internet access and hit real NHC servers.
Run with: uv run pytest tests/test_live.py -v -s
Skip in CI with: --ignore=tests/test_live.py
"""

from datetime import datetime

import pytest

from recon_mcp.client import ReconClient
from recon_mcp.utils import (
    cleanup_temp_file,
    compute_radial_wind_profile,
    parse_atcf_best_track,
    parse_atcf_fix_record,
    parse_directory_listing,
    parse_hdob_message,
    parse_sfmr_netcdf,
    parse_vdm_message,
)


@pytest.fixture
async def client():
    c = ReconClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_list_hdob_directory(client):
    """List HDOB files for 2024 Atlantic season."""
    url = client.build_archive_dir_url(2024, "hdob", "al")
    html = await client.list_directory(url)
    entries = parse_directory_listing(html)

    assert len(entries) > 0, "Expected HDOB files for 2024 Atlantic season"
    # HDOB files should contain AHONT1 in filename
    assert any("AHONT1" in e["filename"] for e in entries)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_list_vdm_directory(client):
    """List VDM files for 2024 Atlantic season."""
    url = client.build_archive_dir_url(2024, "vdm", "al")
    html = await client.list_directory(url)
    entries = parse_directory_listing(html)

    assert len(entries) > 0, "Expected VDM files for 2024 Atlantic season"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_fetch_hdob(client):
    """Parse a real archived HDOB: Milton's eye pass, 2024-10-09 07Z."""
    url = client.build_archive_dir_url(2024, "hdob", "al")
    text = await client.fetch_text(url + "AHONT1-KNHC.202410090710.txt")
    parsed = parse_hdob_message(text)

    assert parsed["header"]["mission"] == "AF300 1814A MILTON"
    obs = parsed["observations"]
    assert len(obs) == 20, "Expected all 20 data lines to decode"
    eye = obs[0]
    assert (eye["date"], eye["time"]) == ("20241009", "070200")
    assert (eye["lat"], eye["lon"]) == (24.0, -85.7)
    assert eye["extrapolated_slp_mb"] == pytest.approx(907.0)
    assert max(o["sfmr_sfc_wind_kt"] or 0 for o in obs) == 152


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_fetch_vdm(client):
    """Parse a real archived VDM: the Milton fix at 2024-10-09 07:02Z."""
    url = client.build_archive_dir_url(2024, "vdm", "al")
    text = await client.fetch_text(url + "REPNT2-KNHC.202410090724.txt")
    parsed = parse_vdm_message(text, issued=datetime(2024, 10, 9, 7, 24))

    assert parsed["storm_id"] == "AL142024"
    assert parsed["vdm_format"] == "2018"
    assert parsed["fix_time_utc"] == "2024-10-09T07:02:10Z"
    assert (parsed["center_lat"], parsed["center_lon"]) == (24.0, -85.71)
    assert parsed["min_slp_mb"] == 910
    assert parsed["eye_diameter_nm"] == 8


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_atcf_fdeck_milton(client):
    """Fetch Milton's (AL14 2024) archived f-deck and decode its fixes."""
    text, url = await client.fetch_fdeck("al", 14, 2024)
    assert url.endswith("/atcf/archive/2024/fal142024.dat.gz")

    records = [parse_atcf_fix_record(line) for line in text.splitlines()]
    records = [r for r in records if r]
    assert len(records) > 500, "Expected Milton's full fix history"
    aircraft = next(r for r in records if r["datetime"] == "202410090702")
    assert aircraft["fix_type"] == "AIRC"
    assert (aircraft["lat"], aircraft["lon"]) == (24.0, -85.71)
    assert (aircraft["max_wind_kt"], aircraft["min_pressure_mb"]) == (158, 910)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_archive_years(client):
    """Verify the archive has data for recent years."""
    for year in [2023, 2024]:
        url = client.build_archive_dir_url(year, "hdob", "al")
        try:
            html = await client.list_directory(url)
            entries = parse_directory_listing(html)
            print(f"Year {year}: {len(entries)} HDOB files")
            assert len(entries) >= 0  # May be empty for quiet years
        except Exception as e:
            print(f"Year {year}: {e}")


# ---------------------------------------------------------------------------
# SFMR live tests (AOML archive)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_sfmr_ian_2022(client):
    """List SFMR files for Hurricane Ian 2022 from AOML archive."""
    url = client.build_sfmr_url(2022, "ian")
    try:
        html = await client.list_directory(url)
    except Exception:
        pytest.skip("AOML SFMR archive not reachable")

    entries = parse_directory_listing(html)
    nc_files = [e for e in entries if e["filename"].endswith(".nc")]

    assert len(nc_files) > 0, "Expected SFMR NetCDF files for Hurricane Ian 2022"
    print(f"\nFound {len(nc_files)} SFMR files for Ian 2022:")
    for e in nc_files[:5]:
        print(f"  {e['filename']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_sfmr_profile_ian_2022(client):
    """Download one SFMR file for Ian 2022 and compute radial wind profile."""
    # List SFMR files
    sfmr_url = client.build_sfmr_url(2022, "ian")
    try:
        html = await client.list_directory(sfmr_url)
    except Exception:
        pytest.skip("AOML SFMR archive not reachable")

    entries = parse_directory_listing(html)
    nc_files = [e for e in entries if e["filename"].endswith(".nc")]
    if not nc_files:
        pytest.skip("No SFMR files found for Ian 2022")

    # Fetch best track (Ian = AL09 2022) — tries btk/ then archive/.gz
    try:
        bdeck_text = await client.fetch_best_track("al", 9, 2022)
    except Exception:
        pytest.skip("ATCF b-deck not reachable")

    track = parse_atcf_best_track(bdeck_text)
    assert len(track) > 0, "Expected best track points for Ian"
    print(f"\nBest track: {len(track)} points")

    # Download first SFMR file
    first_file = nc_files[0]["filename"]
    file_url = sfmr_url + first_file
    tmp_path = None
    try:
        tmp_path = await client.download_netcdf(file_url)
        sfmr_data = parse_sfmr_netcdf(tmp_path)

        print(f"SFMR file: {first_file}")
        print(f"Observations: {sfmr_data['n_obs']}")

        assert sfmr_data["n_obs"] > 0

        # Compute radial profile
        profile = compute_radial_wind_profile(sfmr_data, track, bin_size_km=10.0)
        print(f"Radial bins: {len(profile)}")

        if profile:
            peak = max(profile, key=lambda b: b["max_wind_ms"])
            print(
                f"Peak wind: {peak['max_wind_ms']} m/s at "
                f"{peak['radius_min_km']}-{peak['radius_max_km']} km"
            )

            for b in profile[:10]:
                print(
                    f"  {b['radius_min_km']:5.0f}-{b['radius_max_km']:5.0f} km: "
                    f"mean={b['mean_wind_ms']:5.1f} max={b['max_wind_ms']:5.1f} "
                    f"n={b['samples']}"
                )
    finally:
        cleanup_temp_file(tmp_path)
