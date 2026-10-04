"""Validation tests for ofs-mcp models and enums."""

import pytest

from ofs_mcp.models import GridType, OFS_MODELS, OFSModel, OFSVariable


class TestOFSModelEnum:
    """Tests for the OFSModel enum."""

    def test_ofs_model_has_nine_members(self):
        """OFSModel enum should contain exactly 9 model entries."""
        assert len(OFSModel) == 9

    def test_ofs_model_from_string_values(self):
        """OFSModel members should be constructible from their string values."""
        expected_values = [
            "cbofs",
            "dbofs",
            "gomofs",
            "ngofs2",
            "nyofs",
            "sfbofs",
            "tbofs",
            "wcofs",
            "ciofs",
        ]
        for value in expected_values:
            model = OFSModel(value)
            assert model.value == value

    def test_ofs_model_rejects_invalid_value(self):
        """OFSModel should raise ValueError for unknown model names."""
        with pytest.raises(ValueError):
            OFSModel("invalid_model")

    def test_ofs_model_rejects_empty_string(self):
        """OFSModel should raise ValueError for an empty string."""
        with pytest.raises(ValueError):
            OFSModel("")

    def test_ofs_model_is_string_enum(self):
        """OFSModel members should behave as strings."""
        assert OFSModel.CBOFS == "cbofs"
        assert isinstance(OFSModel.CBOFS, str)


class TestOFSVariableEnum:
    """Tests for the OFSVariable enum."""

    def test_ofs_variable_values(self):
        """OFSVariable should contain water_level, temperature, and salinity."""
        assert OFSVariable.WATER_LEVEL.value == "water_level"
        assert OFSVariable.TEMPERATURE.value == "temperature"
        assert OFSVariable.SALINITY.value == "salinity"

    def test_ofs_variable_has_three_members(self):
        """OFSVariable enum should have exactly 3 members."""
        assert len(OFSVariable) == 3

    def test_ofs_variable_rejects_invalid(self):
        """OFSVariable should raise ValueError for unknown variable names."""
        with pytest.raises(ValueError):
            OFSVariable("pressure")


class TestGridTypeEnum:
    """Tests for the GridType enum."""

    def test_grid_type_values(self):
        """GridType should contain roms, fvcom and pom."""
        assert GridType.ROMS.value == "roms"
        assert GridType.FVCOM.value == "fvcom"
        assert GridType.POM.value == "pom"

    def test_grid_type_has_three_members(self):
        """GridType enum should have exactly 3 members."""
        assert len(GridType) == 3


class TestOFSModelsRegistry:
    """Tests for the OFS_MODELS configuration dictionary."""

    def test_registry_has_all_nine_models(self):
        """OFS_MODELS should have an entry for every OFSModel enum member."""
        for model in OFSModel:
            assert model.value in OFS_MODELS, (
                f"Missing registry entry for {model.value}"
            )

    def test_registry_entries_have_required_keys(self):
        """Each OFS_MODELS entry should contain the required metadata keys."""
        required_keys = {"name", "grid_type", "domain", "cycles", "nc_vars"}
        for model_key, model_info in OFS_MODELS.items():
            missing = required_keys - set(model_info.keys())
            assert not missing, f"{model_key} is missing keys: {missing}"

    def test_domain_bounding_boxes_are_valid(self):
        """Domain lat_min < lat_max and lon_min < lon_max for all models."""
        for model_key, model_info in OFS_MODELS.items():
            domain = model_info["domain"]
            assert domain["lat_min"] < domain["lat_max"], (
                f"{model_key}: lat_min ({domain['lat_min']}) >= lat_max ({domain['lat_max']})"
            )
            assert domain["lon_min"] < domain["lon_max"], (
                f"{model_key}: lon_min ({domain['lon_min']}) >= lon_max ({domain['lon_max']})"
            )

    def test_cycles_are_valid_two_digit_strings(self):
        """All cycle entries should be two-digit zero-padded hour strings."""
        for model_key, model_info in OFS_MODELS.items():
            for cycle in model_info["cycles"]:
                assert len(cycle) == 2, f"{model_key} cycle '{cycle}' is not two digits"
                hour = int(cycle)
                assert 0 <= hour <= 23, (
                    f"{model_key} cycle '{cycle}' is not a valid hour"
                )

    def test_nc_vars_contain_core_variables(self):
        """Each model's nc_vars should map water_level, temperature, and salinity."""
        core_vars = {"water_level", "temperature", "salinity", "time", "lon", "lat"}
        for model_key, model_info in OFS_MODELS.items():
            nc_vars = model_info["nc_vars"]
            missing = core_vars - set(nc_vars.keys())
            assert not missing, f"{model_key} nc_vars is missing mappings: {missing}"

    def test_grid_types_match_known_types(self):
        """Each model's grid_type should be a valid GridType value."""
        valid_types = {gt.value for gt in GridType}
        for model_key, model_info in OFS_MODELS.items():
            assert model_info["grid_type"] in valid_types, (
                f"{model_key} has unknown grid_type '{model_info['grid_type']}'"
            )
