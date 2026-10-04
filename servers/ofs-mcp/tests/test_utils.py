"""Unit tests for OFS MCP utils — no network required."""

from __future__ import annotations

import pytest

from ofs_mcp.client import OFSClient
from ofs_mcp.models import OFS_MODELS
from ofs_mcp.utils import (
    align_timeseries,
    clean_timeseries,
    compute_validation_stats,
    _read_point_series,
    extract_point_timeseries,
    find_nearest_fvcom,
    find_nearest_roms,
    haversine,
)


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


def test_haversine_known_distance():
    # NYC to LA: roughly 3940 km
    dist = haversine(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3900 < dist < 3980


def test_haversine_zero():
    assert haversine(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)


def test_haversine_short():
    # ~111 km per degree of latitude
    dist = haversine(0.0, 0.0, 1.0, 0.0)
    assert 110 < dist < 113


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------


def test_validation_stats_perfect():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = compute_validation_stats(vals, vals)
    assert stats["bias"] == pytest.approx(0.0)
    assert stats["rmse"] == pytest.approx(0.0)
    assert stats["mae"] == pytest.approx(0.0)
    assert stats["peak_error"] == pytest.approx(0.0)
    assert stats["n"] == 5


def test_validation_stats_known_bias():
    forecast = [1.1, 2.1, 3.1]
    observed = [1.0, 2.0, 3.0]
    stats = compute_validation_stats(forecast, observed)
    assert stats["bias"] == pytest.approx(0.1, abs=1e-4)
    assert stats["rmse"] == pytest.approx(0.1, abs=1e-4)
    assert stats["mae"] == pytest.approx(0.1, abs=1e-4)
    assert stats["correlation"] == pytest.approx(1.0, abs=1e-6)


def test_validation_stats_empty():
    stats = compute_validation_stats([], [])
    assert stats["n"] == 0
    assert stats["bias"] is None


def test_validation_stats_mismatched_lengths():
    stats = compute_validation_stats([1.0, 2.0], [1.0])
    assert stats["n"] == 0


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------


def test_align_timeseries_exact_match():
    t_f = ["2026-02-19 00:00", "2026-02-19 01:00", "2026-02-19 02:00"]
    v_f = [1.0, 2.0, 3.0]
    t_o = ["2026-02-19 00:00", "2026-02-19 01:00", "2026-02-19 02:00"]
    v_o = [1.1, 2.1, 3.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o)
    assert len(common) == 3
    assert af == v_f
    assert ao == v_o


def test_align_timeseries_partial_overlap():
    t_f = ["2026-02-19 00:00", "2026-02-19 01:00", "2026-02-19 02:00"]
    v_f = [1.0, 2.0, 3.0]
    t_o = ["2026-02-19 01:00", "2026-02-19 02:00", "2026-02-19 03:00"]
    v_o = [2.1, 3.1, 4.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o)
    assert len(common) == 2
    assert af == [2.0, 3.0]
    assert ao == [2.1, 3.1]


def test_align_timeseries_tolerance():
    # 5-minute offset, within default 10-minute tolerance
    t_f = ["2026-02-19 00:00"]
    v_f = [1.0]
    t_o = ["2026-02-19 00:05"]
    v_o = [1.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o, tolerance_minutes=10)
    assert len(common) == 1


def test_align_timeseries_outside_tolerance():
    t_f = ["2026-02-19 00:00"]
    v_f = [1.0]
    t_o = ["2026-02-19 01:00"]
    v_o = [1.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o, tolerance_minutes=10)
    assert len(common) == 0


# ---------------------------------------------------------------------------
# S3 URL construction
# ---------------------------------------------------------------------------


def test_s3_url_cbofs_forecast():
    client = OFSClient()
    url = client.build_s3_url("cbofs", "20260219", "06", "f", 1)
    assert "noaa-nos-ofs-pds" in url
    assert "cbofs/netcdf/2026/02/19" in url
    # Real S3 object embeds the YYYYMMDD date; cbofs uses the 'fields' infix.
    assert "cbofs.t06z.20260219.fields.f001.nc" in url


def test_s3_url_ngofs2_nowcast():
    client = OFSClient()
    url = client.build_s3_url("ngofs2", "20260219", "12", "n", 3)
    assert "ngofs2/netcdf/2026/02/19" in url
    # ngofs2 uses the '2ds' infix, not 'fields'.
    assert "ngofs2.t12z.20260219.2ds.n003.nc" in url


def test_s3_url_wcofs():
    client = OFSClient()
    url = client.build_s3_url("wcofs", "20260219", "03", "f", 48)
    assert "wcofs/netcdf/2026/02/19" in url
    # wcofs uses the '2ds' infix, not 'fields'.
    assert "wcofs.t03z.20260219.2ds.f048.nc" in url


# ---------------------------------------------------------------------------
# THREDDS URL construction
# ---------------------------------------------------------------------------


def test_thredds_url_cbofs():
    """CBOFS has FMRC — should return a valid FMRC URL."""
    client = OFSClient()
    url = client.build_thredds_url("cbofs")
    assert url is not None
    assert "opendap.co-ops.nos.noaa.gov" in url
    assert "CBOFS" in url
    assert "Aggregated_7_day_CBOFS_Fields_Forecast_best.ncd" in url


def test_thredds_url_ngofs2():
    """NGOFS2 has no FMRC — should return None."""
    client = OFSClient()
    url = client.build_thredds_url("ngofs2")
    assert url is None


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------


def test_all_models_have_required_keys():
    required = [
        "name",
        "short_name",
        "grid_type",
        "domain",
        "cycles",
        "forecast_hours",
        "datum",
        "nc_vars",
        "thredds_id",
    ]
    for model_id, info in OFS_MODELS.items():
        for key in required:
            assert key in info, f"Model '{model_id}' missing key '{key}'"


def test_model_nc_vars_have_time_and_water_level():
    for model_id, info in OFS_MODELS.items():
        nc_vars = info["nc_vars"]
        assert "time" in nc_vars, f"Model '{model_id}' missing nc_vars['time']"
        assert "water_level" in nc_vars, (
            f"Model '{model_id}' missing nc_vars['water_level']"
        )


def test_roms_models_have_lon_rho():
    for model_id, info in OFS_MODELS.items():
        if info["grid_type"] == "roms":
            assert info["nc_vars"]["lon"] in ["lon_rho", "lon"], (
                f"ROMS model '{model_id}' should have lon_rho coordinate"
            )


def test_fvcom_models_have_lon():
    for model_id, info in OFS_MODELS.items():
        if info["grid_type"] == "fvcom":
            assert info["nc_vars"]["lon"] == "lon", (
                f"FVCOM model '{model_id}' should have lon coordinate"
            )


# ---------------------------------------------------------------------------
# Find nearest point (offline — using simple synthetic grids)
# ---------------------------------------------------------------------------


def test_find_nearest_fvcom_known_point():
    import numpy as np

    lats = np.array([38.0, 38.5, 39.0, 39.5])
    lons = np.array([-76.0, -76.5, -77.0, -77.5])

    result = find_nearest_fvcom(38.49, -76.48, lats, lons, max_distance_km=50.0)
    assert result is not None
    idx, dist = result
    assert idx == 1  # Nearest to (38.5, -76.5)
    assert dist < 5.0


def test_find_nearest_fvcom_out_of_range():
    import numpy as np

    lats = np.array([38.0])
    lons = np.array([-76.0])

    result = find_nearest_fvcom(60.0, -76.0, lats, lons, max_distance_km=50.0)
    assert result is None


def test_find_nearest_roms_known_point():
    import numpy as np

    # Simple 3x3 rho grid
    lats = np.array([[38.0, 38.0, 38.0], [38.5, 38.5, 38.5], [39.0, 39.0, 39.0]])
    lons = np.array(
        [[-77.0, -76.5, -76.0], [-77.0, -76.5, -76.0], [-77.0, -76.5, -76.0]]
    )

    result = find_nearest_roms(38.49, -76.49, lats, lons, max_distance_km=50.0)
    assert result is not None
    i, j, dist = result
    assert (i, j) == (1, 1)  # Middle cell nearest to (38.5, -76.5)
    assert dist < 5.0


def test_find_nearest_roms_out_of_range():
    import numpy as np

    lats = np.array([[38.0]])
    lons = np.array([[-76.0]])

    result = find_nearest_roms(50.0, -76.0, lats, lons, max_distance_km=50.0)
    assert result is None


# ---------------------------------------------------------------------------
# Domain coverage
# ---------------------------------------------------------------------------


def test_chesapeake_bay_in_cbofs_domain():
    domain = OFS_MODELS["cbofs"]["domain"]
    lat, lon = 38.98, -76.48  # Chesapeake Bay
    assert domain["lat_min"] <= lat <= domain["lat_max"]
    assert domain["lon_min"] <= lon <= domain["lon_max"]


def test_san_francisco_in_sfbofs_domain():
    domain = OFS_MODELS["sfbofs"]["domain"]
    lat, lon = 37.77, -122.42  # San Francisco
    assert domain["lat_min"] <= lat <= domain["lat_max"]
    assert domain["lon_min"] <= lon <= domain["lon_max"]


def test_alaska_in_ciofs_domain():
    domain = OFS_MODELS["ciofs"]["domain"]
    lat, lon = 60.5, -150.8  # Kenai area
    assert domain["lat_min"] <= lat <= domain["lat_max"]
    assert domain["lon_min"] <= lon <= domain["lon_max"]


# ---------------------------------------------------------------------------
# clean_timeseries
# ---------------------------------------------------------------------------


def test_clean_timeseries_empty():
    """Empty input returns empty result with is_sparse=True."""
    result = clean_timeseries([], [])
    assert result["times"] == []
    assert result["values"] == []
    assert result["is_sparse"] is True
    assert result["n_original"] == 0


def test_clean_timeseries_dedup():
    """Duplicate timestamps are removed, keeping last value."""
    times = [
        "2026-03-01 00:00",
        "2026-03-01 01:00",
        "2026-03-01 01:00",
        "2026-03-01 02:00",
    ]
    values = [1.0, 2.0, 2.5, 3.0]
    result = clean_timeseries(times, values)
    assert result["n_duplicates_removed"] == 1
    assert len(result["times"]) == 3
    # Last value for 01:00 should be 2.5
    idx = result["times"].index("2026-03-01 01:00")
    assert result["values"][idx] == 2.5


def test_clean_timeseries_sorts():
    """Out-of-order timestamps are sorted."""
    times = [
        "2026-03-01 02:00",
        "2026-03-01 00:00",
        "2026-03-01 01:00",
    ]
    values = [3.0, 1.0, 2.0]
    result = clean_timeseries(times, values)
    assert result["times"] == [
        "2026-03-01 00:00",
        "2026-03-01 01:00",
        "2026-03-01 02:00",
    ]
    assert result["values"] == [1.0, 2.0, 3.0]


def test_clean_timeseries_gap_split():
    """Large time gaps split the series; longest segment is kept."""
    times = [
        "2026-03-01 00:00",
        "2026-03-01 01:00",
        # 12-hour gap
        "2026-03-01 13:00",
        "2026-03-01 14:00",
        "2026-03-01 15:00",
        "2026-03-01 16:00",
    ]
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    result = clean_timeseries(times, values, max_gap_hours=6.0)
    assert result["n_segments"] == 2
    assert len(result["times"]) == 4  # Longer segment (4 pts)
    assert result["times"][0] == "2026-03-01 13:00"


def test_clean_timeseries_sparse_rejection():
    """Series with fewer than min_points is flagged as sparse."""
    times = ["2026-03-01 00:00", "2026-03-01 01:00"]
    values = [1.0, 2.0]
    result = clean_timeseries(times, values, min_points=5)
    assert result["is_sparse"] is True


def test_clean_timeseries_contiguous():
    """A clean contiguous series passes through unchanged."""
    times = [f"2026-03-01 {h:02d}:00" for h in range(24)]
    values = [float(h) for h in range(24)]
    result = clean_timeseries(times, values)
    assert result["times"] == times
    assert result["values"] == values
    assert result["n_duplicates_removed"] == 0
    assert result["n_parse_failures"] == 0
    assert result["n_segments"] == 1
    assert result["is_sparse"] is False


def test_clean_timeseries_unparseable():
    """Unparseable timestamps are tracked separately from duplicates."""
    times = [
        "2026-03-01 00:00",
        "BADTIME",
        "2026-03-01 01:00",
        "NOT-A-DATE",
        "2026-03-01 02:00",
    ]
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = clean_timeseries(times, values)
    assert result["n_original"] == 5
    assert result["n_parse_failures"] == 2
    assert result["n_duplicates_removed"] == 0
    assert len(result["times"]) == 3


# ---------------------------------------------------------------------------
# has_fmrc flag
# ---------------------------------------------------------------------------


def test_all_models_have_has_fmrc_flag():
    """Every model in the registry should have a has_fmrc boolean."""
    for model_id, info in OFS_MODELS.items():
        assert "has_fmrc" in info, f"Model '{model_id}' missing has_fmrc flag"
        assert isinstance(info["has_fmrc"], bool)


# ---------------------------------------------------------------------------
# Point extraction from the NetCDF layouts NOAA actually serves
# ---------------------------------------------------------------------------

# Grid used by every structured fixture: 3 x 4 cells, lat 39.0-39.2,
# lon -76.0 to -75.7. The target (39.1, -75.8) is cell (i=1, j=2).
_NT, _NY, _NX = 6, 3, 4
_TARGET = (39.1, -75.8)
_FMRC_UNITS = "hours since 2026-09-26 01:00:00.000 UTC"


def _cell_value(k: int, i: int, j: int) -> float:
    """Value written at time k, cell (i, j): identifies both in the result."""
    return k + 0.01 * (i * _NX + j)


def _write_structured(
    path,
    *,
    time_name: str = "time",
    stray_ocean_time: bool = False,
    lon_name: str = "lon_rho",
    lat_name: str = "lat_rho",
    ydim: str = "eta_rho",
    xdim: str = "xi_rho",
    level_dim: str | None = None,
    time_coordinate: bool = True,
    land: tuple[int, int] | None = None,
    dry: tuple[int, int] | None = None,
    nan_steps: tuple[int, ...] = (),
):
    """Write a tiny structured-grid file (ROMS or POM layout).

    ``land`` marks one cell mask_rho = 0, ``dry`` gives one cell h < 0 (a
    tidal flat on a wetting/drying grid), and ``nan_steps`` puts NaN into the
    target cell at those time steps.
    """
    import netCDF4
    import numpy as np

    with netCDF4.Dataset(path, "w") as nc:
        nc.createDimension(time_name, _NT)
        nc.createDimension(ydim, _NY)
        nc.createDimension(xdim, _NX)
        if time_coordinate:
            t = nc.createVariable(time_name, "f8", (time_name,))
            t.units = _FMRC_UNITS
            t[:] = np.arange(_NT)
        if stray_ocean_time:
            # FMRC leftover: a length-1 ocean_time beside the real time axis.
            nc.createDimension("ocean_time", 1)
            ot = nc.createVariable("ocean_time", "f8", ("ocean_time",))
            ot.units = "seconds since 2016-01-01 00:00:00"
            ot[:] = [3.396e8]
        lon = nc.createVariable(lon_name, "f8", (ydim, xdim))
        lat = nc.createVariable(lat_name, "f8", (ydim, xdim))
        lon[:] = np.tile(-76.0 + 0.1 * np.arange(_NX), (_NY, 1))
        lat[:] = np.tile((39.0 + 0.1 * np.arange(_NY))[:, None], (1, _NX))
        zeta = nc.createVariable("zeta", "f4", (time_name, ydim, xdim))
        values = np.array(
            [
                [[_cell_value(k, i, j) for j in range(_NX)] for i in range(_NY)]
                for k in range(_NT)
            ],
            dtype="f4",
        )
        for k in nan_steps:
            values[k, 1, 2] = np.nan
        zeta[:] = values
        if land is not None:
            mask = nc.createVariable("mask_rho", "f8", (ydim, xdim))
            grid = np.ones((_NY, _NX))
            grid[land] = 0.0
            mask[:] = grid
        if dry is not None:
            h = nc.createVariable("h", "f8", (ydim, xdim))
            grid = np.full((_NY, _NX), 10.0)
            grid[dry] = -7.0
            h[:] = grid
        if level_dim:
            nc.createDimension(level_dim, 3)
            temp = nc.createVariable("temp", "f4", (time_name, level_dim, ydim, xdim))
            # Value = level index, so the test can see which level was taken.
            temp[:] = np.broadcast_to(
                np.arange(3, dtype="f4")[None, :, None, None], (_NT, 3, _NY, _NX)
            )


def _write_fvcom(path, *, with_siglay: bool = False):
    """Write a tiny FVCOM-layout file: 1-D node coordinates, zeta(time, node)."""
    import netCDF4
    import numpy as np

    with netCDF4.Dataset(path, "w") as nc:
        nc.createDimension("time", _NT)
        nc.createDimension("node", 3)
        t = nc.createVariable("time", "f8", ("time",))
        t.units = "days since 2026-10-01 00:00:00"
        t[:] = np.arange(_NT) / 24.0
        lon = nc.createVariable("lon", "f8", ("node",))
        lat = nc.createVariable("lat", "f8", ("node",))
        lon[:] = [-90.0, -89.5, -89.0]
        lat[:] = [29.0, 29.5, 30.0]
        zeta = nc.createVariable("zeta", "f4", ("time", "node"))
        zeta[:] = [[k + 0.1 * n for n in range(3)] for k in range(_NT)]
        if with_siglay:
            nc.createDimension("siglay", 3)
            temp = nc.createVariable("temp", "f4", ("time", "siglay", "node"))
            temp[:] = np.broadcast_to(
                np.arange(3, dtype="f4")[None, :, None], (_NT, 3, 3)
            )


def _open(path):
    import netCDF4

    return netCDF4.Dataset(path)


# netCDF4 1.7 itself sets .shape on arrays it writes, which NumPy 2.5
# deprecates; only these fixtures write files.
@pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)
class TestExtractPointTimeseries:
    """extract_point_timeseries on the file layouts the live services serve."""

    def test_fmrc_layout_reads_time_from_the_variable(self, tmp_path):
        """FMRC: zeta on 'time' beside a stray length-1 'ocean_time' gives the full series."""
        path = tmp_path / "cbofs_fmrc.nc"
        _write_structured(path, stray_ocean_time=True)
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "cbofs", "water_level", *_TARGET)
        assert len(out["times"]) == _NT
        assert out["times"][0] == "2026-09-26 01:00"
        assert out["times"][-1] == "2026-09-26 06:00"
        assert out["values"] == [round(_cell_value(k, 1, 2), 4) for k in range(_NT)]

    def test_s3_roms_layout_uses_ocean_time(self, tmp_path):
        """S3 ROMS files put zeta on 'ocean_time'; that axis is used."""
        path = tmp_path / "cbofs_s3.nc"
        _write_structured(path, time_name="ocean_time")
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "cbofs", "water_level", *_TARGET)
        assert len(out["values"]) == _NT

    def test_grid_layout_comes_from_the_file(self, tmp_path):
        """A ROMS file is read as ROMS even when the registry says FVCOM."""
        path = tmp_path / "roms_under_fvcom_entry.nc"
        _write_structured(path, stray_ocean_time=True)
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "sfbofs", "water_level", *_TARGET)
        assert out["values"][0] == round(_cell_value(0, 1, 2), 4)
        assert (out["lat"], out["lon"]) == pytest.approx(_TARGET)

    def test_pom_layout(self, tmp_path):
        """NYOFS (POM): 2-D lon/lat on (ny, nx) is a structured grid."""
        path = tmp_path / "nyofs_fmrc.nc"
        _write_structured(path, lon_name="lon", lat_name="lat", ydim="ny", xdim="nx")
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "nyofs", "water_level", *_TARGET)
        assert out["values"] == [round(_cell_value(k, 1, 2), 4) for k in range(_NT)]

    def test_fvcom_layout(self, tmp_path):
        """FVCOM: 1-D node coordinates, value taken at the nearest node."""
        path = tmp_path / "ngofs2.nc"
        _write_fvcom(path)
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "ngofs2", "water_level", 29.5, -89.5)
        assert out["values"] == [round(k + 0.1, 4) for k in range(_NT)]
        assert out["times"][1] == "2026-10-01 01:00"

    def test_roms_surface_is_the_last_level(self, tmp_path):
        """ROMS s_rho counts up from the bottom: surface temperature is the last level."""
        path = tmp_path / "roms_temp.nc"
        _write_structured(path, stray_ocean_time=True, level_dim="s_rho")
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "cbofs", "temperature", *_TARGET)
        assert set(out["values"]) == {2.0}

    def test_pom_surface_is_the_first_level(self, tmp_path):
        """POM sigma counts down from the surface: surface is level 0."""
        path = tmp_path / "pom_temp.nc"
        _write_structured(
            path,
            lon_name="lon",
            lat_name="lat",
            ydim="ny",
            xdim="nx",
            level_dim="sigma",
        )
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "nyofs", "temperature", *_TARGET)
        assert set(out["values"]) == {0.0}

    def test_fvcom_surface_is_the_first_siglay(self, tmp_path):
        """FVCOM siglay index 0 is the surface layer."""
        path = tmp_path / "fvcom_temp.nc"
        _write_fvcom(path, with_siglay=True)
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "ngofs2", "temperature", 29.5, -89.5)
        assert set(out["values"]) == {0.0}

    def test_land_cell_is_skipped(self, tmp_path):
        """When the nearest cell is land, the nearest water cell is used."""
        path = tmp_path / "land_nearest.nc"
        _write_structured(path, stray_ocean_time=True, land=(1, 2))
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "cbofs", "water_level", *_TARGET)
        assert (out["lat"], out["lon"]) != pytest.approx(_TARGET)
        assert out["values"][0] != round(_cell_value(0, 1, 2), 4)
        assert len(out["values"]) == _NT

    def test_dry_cell_with_negative_depth_is_skipped(self, tmp_path):
        """A tidal-flat cell (water in the mask, h < 0) is not used."""
        path = tmp_path / "dry_nearest.nc"
        _write_structured(path, stray_ocean_time=True, land=(0, 0), dry=(1, 2))
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "ciofs", "water_level", *_TARGET)
        assert out["values"][0] != round(_cell_value(0, 1, 2), 4)

    def test_nan_values_are_dropped(self, tmp_path):
        """NaN gaps in an FMRC series count as fill, not as values."""
        path = tmp_path / "nan_gaps.nc"
        _write_structured(path, stray_ocean_time=True, nan_steps=(1, 4))
        with _open(path) as nc:
            out = extract_point_timeseries(nc, "nyofs", "water_level", *_TARGET)
        assert len(out["values"]) == _NT - 2
        assert out["fill_count"] == 2
        assert "2026-09-26 02:00" not in out["times"]

    def test_mismatched_time_axis_raises(self, tmp_path):
        """With no coordinate for zeta's time dimension, a length-1 fallback is refused."""
        path = tmp_path / "no_time_coordinate.nc"
        _write_structured(
            path, time_name="t", time_coordinate=False, stray_ocean_time=True
        )
        with _open(path) as nc:
            with pytest.raises(RuntimeError, match="refusing to pair"):
                extract_point_timeseries(nc, "cbofs", "water_level", *_TARGET)


class _FlakyVariable:
    """Stand-in for an OPeNDAP variable whose time steps >= ``bad_from`` fail."""

    def __init__(self, n: int, bad_from: int):
        import numpy as np

        self.shape = (n, 2)
        self._data = np.arange(n * 2, dtype=float).reshape(n, 2)
        self._bad_from = bad_from

    def __getitem__(self, key):
        t = key[0]
        stop = self.shape[0] if t.stop is None else t.stop
        if stop > self._bad_from:
            raise RuntimeError("NetCDF: DAP failure")
        return self._data[key]


class TestReadPointSeries:
    """_read_point_series around partly unreadable FMRC aggregations."""

    def test_unreadable_tail_becomes_nan(self):
        """A failing newest run leaves NaN only where it could not be read."""
        import numpy as np

        out = _read_point_series(_FlakyVariable(60, bad_from=50), (1,), chunk=24)
        assert np.isfinite(out[:48]).all()
        assert np.isnan(out[48:]).all()
        assert out[47] == 47 * 2 + 1

    def test_nothing_readable_reraises(self):
        """If no chunk can be read, the original error propagates."""
        with pytest.raises(RuntimeError, match="DAP failure"):
            _read_point_series(_FlakyVariable(30, bad_from=0), (0,), chunk=10)
