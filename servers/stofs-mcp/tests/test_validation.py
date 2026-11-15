"""Validation tests for stofs-mcp Pydantic models and constants."""

import pytest

from stofs_mcp.models import (
    COOPS_DATUM_FOR_MODEL_DATUM,
    GRIDDED_DATUMS,
    MODEL_CYCLES,
    MODEL_LAG_HOURS,
    STOFS_V31_FIRST_CYCLE,
    Region,
    STOFSModel,
    STOFSProduct,
    documented_station_datum,
)


class TestSTOFSModel:
    """Tests for the STOFSModel enum."""

    def test_2d_global_value(self):
        """STOFSModel.GLOBAL_2D should have value '2d_global'."""
        assert STOFSModel.GLOBAL_2D.value == "2d_global"

    def test_3d_atlantic_value(self):
        """STOFSModel.ATLANTIC_3D should have value '3d_atlantic'."""
        assert STOFSModel.ATLANTIC_3D.value == "3d_atlantic"

    def test_model_has_exactly_two_members(self):
        """STOFSModel should have exactly two members."""
        assert len(STOFSModel) == 2

    def test_rejects_invalid_value(self):
        """STOFSModel should raise ValueError for unknown model strings."""
        with pytest.raises(ValueError):
            STOFSModel("invalid_model")

    def test_rejects_empty_string(self):
        """STOFSModel should raise ValueError for an empty string."""
        with pytest.raises(ValueError):
            STOFSModel("")

    def test_value_as_string(self):
        """STOFSModel members should have correct .value strings."""
        assert STOFSModel.GLOBAL_2D.value == "2d_global"
        assert STOFSModel.ATLANTIC_3D.value == "3d_atlantic"


class TestSTOFSProduct:
    """Tests for the STOFSProduct enum."""

    def test_cwl_value(self):
        """STOFSProduct.CWL should have value 'cwl'."""
        assert STOFSProduct.CWL.value == "cwl"

    def test_htp_value(self):
        """STOFSProduct.HTP should have value 'htp'."""
        assert STOFSProduct.HTP.value == "htp"

    def test_swl_value(self):
        """STOFSProduct.SWL should have value 'swl'."""
        assert STOFSProduct.SWL.value == "swl"

    def test_product_has_exactly_three_members(self):
        """STOFSProduct should have exactly three members."""
        assert len(STOFSProduct) == 3

    def test_rejects_invalid_product(self):
        """STOFSProduct should raise ValueError for unknown product strings."""
        with pytest.raises(ValueError):
            STOFSProduct("invalid_product")


class TestRegion:
    """Tests for the Region enum."""

    def test_east_coast_value(self):
        """Region.EAST_COAST should have value 'east_coast'."""
        assert Region.EAST_COAST.value == "east_coast"

    def test_gulf_value(self):
        """Region.GULF should have value 'gulf'."""
        assert Region.GULF.value == "gulf"

    def test_west_coast_value(self):
        """Region.WEST_COAST should have value 'west_coast'."""
        assert Region.WEST_COAST.value == "west_coast"

    def test_alaska_value(self):
        """Region.ALASKA should have value 'alaska'."""
        assert Region.ALASKA.value == "alaska"

    def test_hawaii_value(self):
        """Region.HAWAII should have value 'hawaii'."""
        assert Region.HAWAII.value == "hawaii"

    def test_puerto_rico_value(self):
        """Region.PUERTO_RICO should have value 'puerto_rico'."""
        assert Region.PUERTO_RICO.value == "puerto_rico"

    def test_region_has_exactly_six_members(self):
        """Region should have exactly six members."""
        assert len(Region) == 6

    def test_rejects_invalid_region(self):
        """Region should raise ValueError for unknown region strings."""
        with pytest.raises(ValueError):
            Region("atlantic")


class TestModelCycles:
    """Tests for the MODEL_CYCLES constant."""

    def test_has_2d_global_entry(self):
        """MODEL_CYCLES should have an entry for '2d_global'."""
        assert "2d_global" in MODEL_CYCLES

    def test_has_3d_atlantic_entry(self):
        """MODEL_CYCLES should have an entry for '3d_atlantic'."""
        assert "3d_atlantic" in MODEL_CYCLES

    def test_2d_global_has_four_cycles(self):
        """2d_global should have four cycle hours."""
        assert len(MODEL_CYCLES["2d_global"]) == 4

    def test_3d_atlantic_has_one_cycle(self):
        """3d_atlantic should have one cycle hour."""
        assert len(MODEL_CYCLES["3d_atlantic"]) == 1

    def test_2d_global_cycles_are_valid_hours(self):
        """All 2d_global cycle hours should be two-digit strings."""
        for cycle in MODEL_CYCLES["2d_global"]:
            assert cycle in {"00", "06", "12", "18"}

    def test_3d_atlantic_cycle_is_12z(self):
        """3d_atlantic should only run at 12z."""
        assert MODEL_CYCLES["3d_atlantic"] == ["12"]


class TestDocumentedStationDatum:
    """The documented station-file datum depends on the model and cycle date."""

    def test_v31_first_cycle_is_2026_08_17_12z(self):
        """NOAA implemented STOFS v3.1 at the 12 UTC cycle on 2026-08-17."""
        assert STOFS_V31_FIRST_CYCLE == "2026081712"

    def test_3d_atlantic_before_v31_is_navd88(self):
        """3D station output is NAVD88 for the Boston example's 2026-02-18 cycle."""
        assert documented_station_datum("3d_atlantic", "20260218", "12") == "NAVD88"

    def test_3d_atlantic_last_v21_cycle_is_navd88(self):
        """The 2026-08-16 12z cycle, the last v2.1 run, is still NAVD88."""
        assert documented_station_datum("3d_atlantic", "20260816", "12") == "NAVD88"

    def test_3d_atlantic_from_v31_is_lmsl(self):
        """From the 2026-08-17 12z cycle, 3D station output is LMSL, not NAVD88."""
        assert documented_station_datum("3d_atlantic", "20260817", "12") == "LMSL"
        assert documented_station_datum("3d_atlantic", "20261101", "12") == "LMSL"

    @pytest.mark.parametrize(
        "date,hour",
        [
            ("20221201", "00"),
            ("20260218", "18"),
            ("20260817", "12"),
            ("20261101", "06"),
        ],
    )
    def test_2d_global_is_lmsl_throughout(self, date, hour):
        """2D-Global station output is LMSL before and after the v3.1 upgrade."""
        assert documented_station_datum("2d_global", date, hour) == "LMSL"


class TestGriddedDatums:
    """Gridded output has its own datum, separate from the station files."""

    def test_3d_atlantic_gridded_is_xgeoid20b(self):
        """NOAA: STOFS-3D gridded output remains referenced to xGEOID20b."""
        assert GRIDDED_DATUMS["3d_atlantic"] == "xGEOID20b"

    def test_2d_global_gridded_is_lmsl(self):
        """NOMADS documents 2D-Global gridded and station output as LMSL."""
        assert GRIDDED_DATUMS["2d_global"] == "LMSL"


class TestCoopsDatumForModelDatum:
    """The CO-OPS request datum follows the model datum, not the model name."""

    def test_lmsl_requests_msl(self):
        """LMSL model output is compared with CO-OPS MSL."""
        assert COOPS_DATUM_FOR_MODEL_DATUM["LMSL"] == "MSL"

    def test_navd88_requests_navd(self):
        """CO-OPS spells NAVD88 as 'NAVD' in its API."""
        assert COOPS_DATUM_FOR_MODEL_DATUM["NAVD88"] == "NAVD"

    def test_xgeoid_has_no_coops_equivalent(self):
        """xGEOID20b has no CO-OPS datum, so no comparison should be attempted."""
        assert "xGEOID20b" not in COOPS_DATUM_FOR_MODEL_DATUM


class TestModelLagHours:
    """Tests for the MODEL_LAG_HOURS constant."""

    def test_has_2d_global_entry(self):
        """MODEL_LAG_HOURS should have an entry for '2d_global'."""
        assert "2d_global" in MODEL_LAG_HOURS

    def test_has_3d_atlantic_entry(self):
        """MODEL_LAG_HOURS should have an entry for '3d_atlantic'."""
        assert "3d_atlantic" in MODEL_LAG_HOURS

    def test_lag_hours_are_positive_integers(self):
        """All lag hour values should be positive integers."""
        for model, lag in MODEL_LAG_HOURS.items():
            assert isinstance(lag, int), f"Lag for {model} should be an int"
            assert lag > 0, f"Lag for {model} should be positive"

    def test_3d_atlantic_lag_greater_than_2d_global(self):
        """3d_atlantic should have a longer lag than 2d_global."""
        assert MODEL_LAG_HOURS["3d_atlantic"] > MODEL_LAG_HOURS["2d_global"]


class TestDeprecatedDatumMaps:
    """The 0.2.0 public maps still import, with their old values, but warn."""

    def test_model_datums_warns_and_keeps_0_2_0_values(self):
        """MODEL_DATUMS is importable; access emits a DeprecationWarning."""
        import stofs_mcp.models as models

        with pytest.warns(DeprecationWarning, match="MODEL_DATUMS is deprecated"):
            value = models.MODEL_DATUMS
        assert value == {"2d_global": "LMSL", "3d_atlantic": "NAVD88"}

    def test_coops_validation_datums_warns_and_keeps_0_2_0_values(self):
        """COOPS_VALIDATION_DATUMS is importable via 'from ... import'."""
        with pytest.warns(DeprecationWarning, match="COOPS_VALIDATION_DATUMS"):
            from stofs_mcp.models import COOPS_VALIDATION_DATUMS
        assert COOPS_VALIDATION_DATUMS == {"2d_global": "MSL", "3d_atlantic": "NAVD"}

    def test_mutating_the_returned_map_does_not_leak(self):
        """Each access returns a copy."""
        import stofs_mcp.models as models

        with pytest.warns(DeprecationWarning):
            models.MODEL_DATUMS["3d_atlantic"] = "x"
        with pytest.warns(DeprecationWarning):
            assert models.MODEL_DATUMS["3d_atlantic"] == "NAVD88"

    def test_unknown_attribute_still_raises(self):
        """Module __getattr__ does not swallow other missing names."""
        import stofs_mcp.models as models

        with pytest.raises(AttributeError):
            models.NOT_A_NAME  # noqa: B018

    def test_no_tool_uses_the_deprecated_maps(self):
        """The package source never reads the deprecated names."""
        import pathlib

        import stofs_mcp

        root = pathlib.Path(stofs_mcp.__file__).parent
        for path in root.rglob("*.py"):
            text = path.read_text()
            if path.name == "models.py":
                continue
            assert (
                "MODEL_DATUMS" not in text and "COOPS_VALIDATION_DATUMS" not in text
            ), path
