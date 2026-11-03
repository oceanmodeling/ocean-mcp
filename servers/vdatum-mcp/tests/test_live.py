"""Live accuracy checks: VDatum transformations against independent reference values.

These download the transformation grids, so they are excluded from CI like
every server's test_live.py. Reference values are NOAA CO-OPS published
station datums (tidal epoch 1983-2001), retrieved 2026-11-02 from
https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/<id>/datums.json:
the height of NAVD88 zero above MLLW and above MSL at each tide station. CO-OPS
datums come from the station's own tide record and leveling, independently of
the VDatum grids. Agreement observed when written: <= 1.7 cm (MLLW) and
<= 0.7 cm (LMSL) at these three stations; the 3 cm tolerance leaves headroom
without hiding a sign or grid error.
"""

import numpy as np
import pytest

from vdatum_mcp._vendor.coastalmodeling_vdatum import vdatum

TOLERANCE_M = 0.03

# station: (lat, lon, NAVD88 - MLLW, NAVD88 - MSL) in metres, CO-OPS datums.
REFERENCE = {
    "8443970 Boston, MA": (42.3539, -71.05028, 1.678, 0.092),
    "8518750 The Battery, NY": (40.700556, -74.014167, 0.846, 0.063),
    "8771450 Galveston Pier 21, TX": (29.31, -94.793306, 0.094, -0.158),
}


def _convert(target: str) -> np.ndarray:
    lat = np.array([v[0] for v in REFERENCE.values()])
    lon = np.array([v[1] for v in REFERENCE.values()])
    _, _, z = vdatum.convert(
        "navd88", target, lat, lon, np.zeros(len(REFERENCE)), online=True
    )
    return np.asarray(z)


class TestAgainstCoopsStationDatums:
    """NAVD88 zero expressed in tidal datums matches CO-OPS station datums."""

    def test_navd88_to_mllw(self):
        """navd88 -> mllw of z=0 equals CO-OPS NAVD88 - MLLW within 3 cm."""
        z = _convert("mllw")
        for (name, ref), got in zip(REFERENCE.items(), z):
            assert got == pytest.approx(ref[2], abs=TOLERANCE_M), name

    def test_navd88_to_lmsl(self):
        """navd88 -> lmsl of z=0 equals CO-OPS NAVD88 - MSL within 3 cm."""
        z = _convert("lmsl")
        for (name, ref), got in zip(REFERENCE.items(), z):
            assert got == pytest.approx(ref[3], abs=TOLERANCE_M), name

    def test_round_trip_is_identity(self):
        """navd88 -> mllw -> navd88 returns the input to within 1 mm."""
        lat = np.array([v[0] for v in REFERENCE.values()])
        lon = np.array([v[1] for v in REFERENCE.values()])
        z0 = np.array([1.0, -0.5, 2.0])
        _, _, z1 = vdatum.convert(
            "navd88", "mllw", lat.copy(), lon.copy(), z0.copy(), online=True
        )
        _, _, z2 = vdatum.convert(
            "mllw", "navd88", lat.copy(), lon.copy(), np.asarray(z1), online=True
        )
        assert np.allclose(z2, z0, atol=0.001)
