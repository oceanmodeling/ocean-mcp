"""Tests for RTOFS models, enums, and client validation logic."""

import math

import pytest

from rtofs_mcp.client import (
    RTOFSAPIError,
    RTOFSClient,
    _parse_csv,
    compute_auto_stride,
    handle_rtofs_error,
    haversine,
)
from rtofs_mcp.models import (
    DATASETS,
    PROFILE_VARIABLES,
    SURFACE_VARIABLES,
    THREDDS_BASE,
    RTOFSDatasetType,
    RTOFSVariable,
)


class TestEnums:
    """Test enum definitions."""

    def test_dataset_type_values(self):
        """Verify dataset type enum values."""
        assert RTOFSDatasetType.SURFACE_FORECAST == "surface_forecast"
        assert RTOFSDatasetType.PROFILE_FORECAST == "profile_forecast"

    def test_variable_enum_values(self):
        """Verify variable enum values."""
        assert RTOFSVariable.SST == "sst"
        assert RTOFSVariable.SSH == "ssh"
        assert RTOFSVariable.U_CURRENT == "u_current"


class TestDatasetRegistry:
    """Test DATASETS configuration."""

    def test_all_datasets_have_required_keys(self):
        """Each dataset must have path, variables, description, dimensions."""
        for key, ds in DATASETS.items():
            assert "path" in ds, f"Dataset '{key}' missing 'path'"
            assert "variables" in ds, f"Dataset '{key}' missing 'variables'"
            assert "description" in ds, f"Dataset '{key}' missing 'description'"
            assert "dimensions" in ds, f"Dataset '{key}' missing 'dimensions'"
            assert ds["dimensions"] in ("2D", "3D"), (
                f"Dataset '{key}' has invalid dimensions"
            )

    def test_all_datasets_have_default_window(self):
        """Each dataset has a positive default window so queries stay bounded."""
        for key, ds in DATASETS.items():
            hours = ds.get("default_window_hours")
            assert isinstance(hours, int) and hours > 0, (
                f"Dataset '{key}' needs a positive int default_window_hours"
            )

    def test_all_datasets_have_variables(self):
        """Each dataset must have at least one variable."""
        for key, ds in DATASETS.items():
            assert len(ds["variables"]) >= 1, f"Dataset '{key}' has no variables"

    def test_ssh_is_2d(self):
        """SSH dataset should be 2D."""
        assert DATASETS["ssh"]["dimensions"] == "2D"

    def test_sst_is_3d(self):
        """SST/temperature dataset should be 3D (includes depth)."""
        assert DATASETS["sst"]["dimensions"] == "3D"


class TestSurfaceVariables:
    """Test SURFACE_VARIABLES mapping."""

    def test_all_surface_vars_reference_valid_dataset(self):
        """Each surface variable must point to a valid dataset key."""
        for var, info in SURFACE_VARIABLES.items():
            assert info["dataset"] in DATASETS, (
                f"Surface var '{var}' references unknown dataset '{info['dataset']}'"
            )

    def test_all_surface_vars_have_required_keys(self):
        """Each surface variable must have dataset, thredds_var, unit, long_name."""
        required = {"dataset", "thredds_var", "unit", "long_name"}
        for var, info in SURFACE_VARIABLES.items():
            for key in required:
                assert key in info, f"Surface var '{var}' missing '{key}'"

    def test_thredds_var_exists_in_dataset(self):
        """Each surface variable's thredds_var must exist in its dataset's variables."""
        for var, info in SURFACE_VARIABLES.items():
            ds = DATASETS[info["dataset"]]
            assert info["thredds_var"] in ds["variables"], (
                f"Surface var '{var}' thredds_var '{info['thredds_var']}' "
                f"not in dataset '{info['dataset']}'"
            )


class TestProfileVariables:
    """Test PROFILE_VARIABLES mapping."""

    def test_all_profile_vars_reference_valid_dataset(self):
        """Each profile variable must point to a valid dataset key."""
        for var, info in PROFILE_VARIABLES.items():
            assert info["dataset"] in DATASETS

    def test_profile_datasets_are_3d(self):
        """Profile variables must come from 3D datasets."""
        for var, info in PROFILE_VARIABLES.items():
            ds = DATASETS[info["dataset"]]
            assert ds["dimensions"] == "3D", (
                f"Profile var '{var}' comes from non-3D dataset '{info['dataset']}'"
            )


class TestParseCSV:
    """Test CSV parsing utility."""

    def test_parse_simple_csv(self):
        """Parse a simple NCSS CSV response."""
        text = (
            'time,latitude[unit="degrees_north"],longitude[unit="degrees_east"],'
            'surf_el[unit="m"]\n'
            "2026-03-01T00:00:00Z,40.0,-74.0,-0.5\n"
        )
        rows = _parse_csv(text)
        assert len(rows) == 1
        assert rows[0]["latitude"] == 40.0
        assert rows[0]["longitude"] == -74.0
        assert rows[0]["surf_el"] == -0.5
        assert rows[0]["time"] == "2026-03-01T00:00:00Z"

    def test_parse_strips_unit_annotations(self):
        """Column names should have unit annotations stripped."""
        text = 'latitude[unit="degrees_north"],value[unit="m"]\n40.0,1.5\n'
        rows = _parse_csv(text)
        assert "latitude" in rows[0]
        assert "value" in rows[0]

    def test_parse_multiple_rows(self):
        """Parse CSV with multiple data rows."""
        text = "time,value\n2026-01-01,1.0\n2026-01-02,2.0\n2026-01-03,3.0\n"
        rows = _parse_csv(text)
        assert len(rows) == 3

    def test_parse_nan_values(self):
        """NaN values should parse as float NaN."""
        text = "time,value\n2026-01-01,NaN\n"
        rows = _parse_csv(text)
        assert len(rows) == 1
        assert math.isnan(rows[0]["value"])

    def test_parse_error_response_raises(self):
        """Error responses from THREDDS should raise RTOFSAPIError."""
        with pytest.raises(RTOFSAPIError):
            _parse_csv("Error: some THREDDS error message")


class TestHaversine:
    """Test haversine distance calculation."""

    def test_zero_distance(self):
        """Same point should return 0 distance."""
        assert haversine(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance(self):
        """NYC to London is approximately 5570 km."""
        dist = haversine(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5500 < dist < 5700

    def test_equator_1_degree(self):
        """1 degree of longitude at equator is ~111 km."""
        dist = haversine(0, 0, 0, 1)
        assert 110 < dist < 112


class TestComputeAutoStride:
    """Test auto-stride computation."""

    def test_small_area_stride_1(self):
        """Small area should have stride 1."""
        lat_s, lon_s = compute_auto_stride(40.0, 41.0, -74.0, -73.0)
        assert lat_s == 1
        assert lon_s == 1

    def test_large_area_gets_stride(self):
        """Large area should get stride > 1."""
        lat_s, lon_s = compute_auto_stride(0.0, 60.0, -80.0, 0.0, max_points=10)
        assert lat_s > 1
        assert lon_s > 1


class TestHandleError:
    """Test error formatting."""

    def test_rtofs_api_error(self):
        """RTOFSAPIError should include the message."""
        msg = handle_rtofs_error(RTOFSAPIError("test error"))
        assert "test error" in msg

    def test_value_error(self):
        """ValueError should return the message directly."""
        msg = handle_rtofs_error(ValueError("bad input"))
        assert msg == "bad input"

    def test_generic_error(self):
        """Generic exceptions should include type name."""
        msg = handle_rtofs_error(RuntimeError("oops"))
        assert "RuntimeError" in msg


class TestClientBuildUrl:
    """Test URL building."""

    def test_build_ncss_url(self):
        """NCSS URL should include THREDDS base and dataset path."""
        c = RTOFSClient()
        url = c.build_ncss_url("some/path.ncd")
        assert url == f"{THREDDS_BASE}/ncss/some/path.ncd"
