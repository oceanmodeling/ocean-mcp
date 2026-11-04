"""Shared fixtures for stofs-mcp tests."""

from datetime import datetime

import pytest

from stofs_mcp.client import STOFSClient

# zeta attributes copied from real station files on noaa-*-pds (inspected
# 2026-11-02). STOFS-3D switched from NAVD88 to MSL with v3.1 (2026-08-17
# 12z cycle); STOFS-2D-Global writes ADCIRC's generic "above geoid" label.
ZETA_3D_V21 = {
    "standard_name": "sea_surface_height_above_navd88",
    "long_name": "water surface elevation above navd88",
}
ZETA_3D_V31 = {
    "standard_name": "sea_surface_height_above_msl",
    "long_name": "water surface elevation above msl",
}
ZETA_2D = {
    "standard_name": "sea_surface_height_above_geoid",
    "long_name": "water surface elevation above geoid",
}

# Global attributes identifying the producer, copied from the same real files
# (ADCIRC pads its titles with "! NCPROJ - PROJECT TITLE").
GLOBAL_2D = {
    "model": "ADCIRC",
    "title": "STOFS_2D_GLOBAL.V3.1.0     ! NCPROJ - PROJECT TITLE",
}
GLOBAL_ESTOFS = {
    "model": "ADCIRC",
    "title": "ESTOFS GLOBAL V2.1.0       ! NCPROJ - PROJECT TITLE",
}
GLOBAL_3D_V21 = {
    "title": "SCHISM Model output",
    "history": "ncap2 -O -F -S /lfs/h1/ops/prod/packages/stofs.v2.1.18/fix/stofs_3d_atl/"
    "stofs_3d_atl_sta_cwl_xgeoid_to_navd.nco in.nc out_navd.nc",
}
GLOBAL_3D_V31 = {
    "title": "SCHISM Model output",
    "history": "ncap2 -O -F -S /lfs/h1/ops/prod/packages/stofs.v3.1.4/fix/stofs_3d_atl/"
    "stofs_3d_atl_sta_cwl_xgeoid_to_msl.nco in.nc out_msl.nc",
}


def adcirc_2d_meta(title: str = GLOBAL_2D["title"]) -> dict:
    """Datum fields parse_station_netcdf returns for a real 2D/ESTOFS file,
    for tests that stub the parser."""
    return {
        "datum": "",
        "datum_status": "generic",
        "datum_label": "zeta:standard_name=sea_surface_height_above_geoid",
        "datum_reference": "geoid",
        "datum_attributes": {"zeta:standard_name": "sea_surface_height_above_geoid"},
        "product": {"model": "ADCIRC", "title": title.split("!")[0].strip()},
    }


@pytest.fixture
async def client():
    """Create a STOFSClient and close it after the test."""
    c = STOFSClient()
    yield c
    await c.close()


@pytest.fixture
def station_nc(tmp_path):
    """Factory writing a minimal STOFS-like station NetCDF file.

    ``station_nc(zeta_attrs, start, values, stations=("8443970",), xy=None)``
    writes 6-minute ``zeta`` values (same series at every station) starting
    one step after ``start`` ('YYYY-MM-DD HH:MM'), with the real files' layout:
    zeta(time, station), station_name(station, namelen), x/y coordinates
    (``xy``: one (x, y) pair per station; default Boston, correctly ordered)
    and optional ``global_attrs`` (e.g. GLOBAL_2D) identifying the producer.
    """
    import netCDF4
    import numpy as np

    counter = {"n": 0}

    def _write(
        zeta_attrs, start, values, stations=("8443970",), xy=None, global_attrs=None
    ):
        counter["n"] += 1
        path = tmp_path / f"station_{counter['n']}.nc"
        nc = netCDF4.Dataset(str(path), "w")
        try:
            for key, value in (global_attrs or {}).items():
                setattr(nc, key, value)
            nc.createDimension("time", len(values))
            nc.createDimension("station", len(stations))
            nc.createDimension("namelen", 50)
            t = nc.createVariable("time", "f8", ("time",))
            t.units = f"seconds since {start}:00 UTC"
            t[:] = [360.0 * (i + 1) for i in range(len(values))]
            names = nc.createVariable("station_name", "S1", ("station", "namelen"))
            chars = np.full((len(stations), 50), b"", dtype="S1")
            for i, sid in enumerate(stations):
                chars[i, : len(sid)] = [bytes([c]) for c in sid.encode()]
            names[:] = chars
            xy = xy or [(-71.05, 42.35)] * len(stations)
            nc.createVariable("x", "f8", ("station",))[:] = [p[0] for p in xy]
            nc.createVariable("y", "f8", ("station",))[:] = [p[1] for p in xy]
            z = nc.createVariable(
                "zeta", "f8", ("time", "station"), fill_value=-99999.0
            )
            for key, value in zeta_attrs.items():
                setattr(z, key, value)
            z.units = "m"
            z[:] = np.repeat(np.array(values, dtype=float)[:, None], len(stations), 1)
        finally:
            nc.close()
        return path

    return _write


def six_minute_times(start: str, n: int) -> list[str]:
    """``n`` consecutive 6-minute timestamps beginning one step after ``start``."""
    from datetime import timedelta

    t0 = datetime.strptime(start, "%Y-%m-%d %H:%M")
    return [
        (t0 + timedelta(minutes=6 * (i + 1))).strftime("%Y-%m-%d %H:%M")
        for i in range(n)
    ]
