#!/usr/bin/env python3
"""Build the controlled mutations S1 to S5 (synthetic, labelled as such).

Each mutation starts from a copy of a real archived NOAA response and changes
only what its definition names. Every result is stored in its own overlay
archive (``data/archive/synthetic/<task>/``) under the *same request key* as
the real file, so a replay session stacked as [overlay, base] receives the
mutated bytes, and arms A and B read the same bytes from the same place.

After writing, the script re-reads each mutated file and checks that
everything outside the named change is unchanged (all variables' raw values,
all other attributes). The base archive is never modified.

S1  3D 2026-10-30: zeta:standard_name and zeta:long_name deleted (no datum label).
S2  3D 2026-10-30: zeta:long_name set to "water surface elevation above navd88";
    zeta:standard_name keeps sea_surface_height_above_msl (conflict).
S3  2D 2026-10-30: global title and comments say STOFS_2D_GLOBAL.V4.0.0
    (an undocumented version) instead of V3.1.0.
S4  CO-OPS Boston MSL water levels 2026-10-29..11-01: the "v" field of five
    records inside 0 < lead <= 48 h of the 2026-10-30 12z cycle set to
    "", "NaN", "Infinity", "-Infinity", "" (other fields untouched).
S5  3D 2026-10-30: the datum labels reworded without changing their meaning:
    standard_name = sea_surface_height_above_mean_sea_level (the CF standard
    name), long_name = "water surface elevation above mean sea level".

Usage: python -I make_synthetic.py <verification_dir>
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

import netCDF4
import numpy as np

URL_2D = "https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.20261030/stofs_2d_glo.t12z.points.cwl.nc"
URL_3D = (
    "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/stofs_3d_atl.20261030/"
    "stofs_3d_atl.t12z.points.cwl.nc"
)
S4_MASTER_INPUT = "coops_8443970_MSL_20261029_1101"
S4_INJECT = [
    ("2026-10-30 18:00", ""),
    ("2026-10-31 00:00", "NaN"),
    ("2026-10-31 06:00", "Infinity"),
    ("2026-10-31 12:00", "-Infinity"),
    ("2026-11-01 00:00", ""),
]

NC_MUTATIONS = {
    "S1": dict(url=URL_3D, var_delete={"zeta": ["standard_name", "long_name"]}, var_set={}, global_set={},
               description="zeta:standard_name and zeta:long_name deleted; no other change"),
    "S2": dict(url=URL_3D, var_delete={}, var_set={"zeta": {"long_name": "water surface elevation above navd88"}},
               global_set={},
               description="zeta:long_name changed from 'water surface elevation above msl' to "
                           "'water surface elevation above navd88'; standard_name unchanged "
                           "(sea_surface_height_above_msl)"),
    "S3": dict(url=URL_2D, var_delete={}, var_set={},
               global_set={"title": "STOFS_2D_GLOBAL.V4.0.0     ! NCPROJ - PROJECT TITLE",
                           "comments": "STOFS_2D_GLOBAL.V4.0.0     ! NCCOM  - PROJECT COMMENTS"},
               description="global title and comments changed from STOFS_2D_GLOBAL.V3.1.0 to "
                           "STOFS_2D_GLOBAL.V4.0.0 (same padding and suffix)"),
    "S5": dict(url=URL_3D, var_delete={},
               var_set={"zeta": {"standard_name": "sea_surface_height_above_mean_sea_level",
                                 "long_name": "water surface elevation above mean sea level"}},
               global_set={},
               description="zeta:standard_name 'sea_surface_height_above_msl' -> "
                           "'sea_surface_height_above_mean_sea_level' (CF standard name); "
                           "zeta:long_name 'water surface elevation above msl' -> "
                           "'water surface elevation above mean sea level'"),
}


def load_launcher(vdir: Path):
    spec = importlib.util.spec_from_file_location("ocean_replay_launcher", vdir / "replay/ocean_replay_launcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def snapshot(path: Path) -> dict:
    """All attributes and raw variable values of a NetCDF file."""
    ds = netCDF4.Dataset(path)
    ds.set_auto_maskandscale(False)
    out = {"global": {k: ds.getncattr(k) for k in ds.ncattrs()}, "vars": {}}
    for name, v in ds.variables.items():
        out["vars"][name] = {
            "attrs": {k: v.getncattr(k) for k in v.ncattrs()},
            "data": np.array(v[:]),
        }
    ds.close()
    return out


def check_only_named_changes(before: dict, after: dict, m: dict) -> list[str]:
    problems = []
    for name, vb in before["vars"].items():
        va = after["vars"].get(name)
        if va is None:
            problems.append(f"variable {name} missing")
            continue
        if not np.array_equal(vb["data"], va["data"], equal_nan=vb["data"].dtype.kind == "f"):
            problems.append(f"data of {name} changed")
        exp = dict(vb["attrs"])
        for k in m["var_delete"].get(name, []):
            exp.pop(k, None)
        exp.update(m["var_set"].get(name, {}))
        if {k: str(v) for k, v in exp.items()} != {k: str(v) for k, v in va["attrs"].items()}:
            problems.append(f"attributes of {name} differ from the intended mutation")
    gexp = dict(before["global"])
    gexp.update(m["global_set"])
    if {k: str(v) for k, v in gexp.items()} != {k: str(v) for k, v in after["global"].items()}:
        problems.append("global attributes differ from the intended mutation")
    return problems


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    L = load_launcher(vdir)
    base = L.Archive(vdir / "data/archive/base")
    report = {}
    for task, m in NC_MUTATIONS.items():
        entry = base.by_key[L.key_string(L.request_key("GET", m["url"]))]
        src_bytes = base.body_bytes(entry)
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "mutated.nc"
            orig = Path(td) / "orig.nc"
            orig.write_bytes(src_bytes)
            shutil.copy(orig, work)
            ds = netCDF4.Dataset(work, "r+")
            for var, names in m["var_delete"].items():
                for a in names:
                    ds.variables[var].delncattr(a)
            for var, attrs in m["var_set"].items():
                for a, val in attrs.items():
                    ds.variables[var].setncattr(a, val)
            for a, val in m["global_set"].items():
                ds.setncattr(a, val)
            ds.close()
            problems = check_only_named_changes(snapshot(orig), snapshot(work), m)
            if problems:
                print(task, "MUTATION CHECK FAILED:", problems, file=sys.stderr)
                return 1
            body = work.read_bytes()
        out_dir = vdir / "data/archive/synthetic" / task
        if out_dir.exists():
            shutil.rmtree(out_dir)
        arc = L.Archive(out_dir, writable=True)
        e = arc.add(entry["key"], entry["url"], 200, entry["response"]["headers"], body,
                    {"source": "synthetic", "task": task, "mutation": m["description"],
                     "origin_entry": entry["id"], "origin_sha256": entry["response"]["body_sha256"],
                     "label": "SYNTHETIC: controlled mutation of a real NOAA file"})
        report[task] = {"origin_sha256": entry["response"]["body_sha256"], "sha256": e["response"]["body_sha256"],
                        "bytes": e["response"]["bytes"], "mutation": m["description"],
                        "check": "only the named attributes differ; all variable data identical"}

    # S4: CO-OPS observations with injected blank and non-finite values
    master = next(e for e in base.doc["entries"] if e["provenance"].get("input_name") == S4_MASTER_INPUT)
    doc = base.verified_master(master)
    doc = json.loads(json.dumps(doc))
    by_t = {r["t"]: r for r in doc["data"]}
    injected = []
    for t, v in S4_INJECT:
        rec = by_t[t]
        injected.append({"t": t, "original_v": rec["v"], "injected_v": v})
        rec["v"] = v
    body = L.coops_serialize(doc)
    out_dir = vdir / "data/archive/synthetic/S4"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    arc = L.Archive(out_dir, writable=True)
    e = arc.add(master["key"], master["url"], 200, master["response"]["headers"], body,
                {"source": "synthetic", "task": "S4",
                 "mutation": "v field of five records replaced: " + json.dumps(injected),
                 "origin_entry": master["id"], "origin_sha256": master["response"]["body_sha256"],
                 "retrieved_at": master["provenance"]["retrieved_at"],
                 "label": "SYNTHETIC: controlled mutation of a real CO-OPS response"},
                kind="coops_master")
    arc.verified_master(e)
    changed = [a for a, b in zip(json.loads(base.body_bytes(master))["data"], doc["data"]) if a != b]
    assert len(changed) == len(S4_INJECT)
    report["S4"] = {"origin_sha256": master["response"]["body_sha256"], "sha256": e["response"]["body_sha256"],
                    "bytes": e["response"]["bytes"], "injected": injected,
                    "check": "exactly five records differ, only in v; byte-exact CO-OPS layout"}
    (vdir / "synthetic/synthetic_manifest.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
