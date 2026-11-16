"""Step 0: retrieve every input once, with checksums, into data/ and data/manifest.json.

Retrieval is sequential and cached: a file already present is not re-fetched
(its checksum is recomputed and compared with the manifest, if any). Network
use: 2 S3 files (~33 MB), 4 CO-OPS requests, 4 NOAA documentation pages.
Optional --grib also fetches the 49 STOFS-3D GRIB2 files used by script 05.

Usage (from the package directory):
  uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
      python scripts/00_fetch_inputs.py [--grib] [--verify-only]
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import _common as c

UA = {"User-Agent": "ocean-mcp-verification/1.0 (reproducibility package)"}


def fetch(url: str, dest, params: dict | None = None) -> dict:
    """Download url to dest unless present; return a manifest entry."""
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    entry = {"url": url, "params": params, "file": c.rel(dest)}
    if dest.exists() and dest.stat().st_size > 0:
        entry["status"] = "cached"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(full, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            entry["http_status"] = resp.status
            entry["last_modified"] = resp.headers.get("Last-Modified")
            entry["etag"] = resp.headers.get("ETag")
        dest.write_bytes(body)
        entry["status"] = "downloaded"
        entry["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if "tidesandcurrents" in url:
            time.sleep(2)  # be gentle with CO-OPS
    entry["bytes"] = dest.stat().st_size
    entry["sha256"] = c.sha256(dest)
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grib", action="store_true", help="also fetch 3D GRIB2 f000-f048")
    ap.add_argument(
        "--verify-only", action="store_true", help="check files against the manifest"
    )
    args = ap.parse_args()

    old = c.load_json(c.MANIFEST) if c.MANIFEST.exists() else {"entries": {}}
    if args.verify_only:
        bad = 0
        for key, e in old["entries"].items():
            path = c.PACKAGE / e["file"]
            ok = path.exists() and c.sha256(path) == e["sha256"]
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {key}: {e['file']}")
        return 1 if bad else 0

    entries = dict(old.get("entries", {}))

    def record(key, entry):
        prev = entries.get(key)
        if prev and entry["status"] == "cached":
            if prev["sha256"] != entry["sha256"]:
                sys.exit(f"checksum mismatch for cached {key}: {entry['file']}")
            entry = prev | {"status": "cached"}
        entries[key] = entry
        write_manifest(entries)
        print(
            f"{entry['status']:10} {key}: {entry['bytes']} bytes sha256={entry['sha256'][:16]}…"
        )

    for model, f in c.STOFS_FILES.items():
        record(f"stofs_{model}", fetch(f["url"], c.RAW / f["file"]))

    record(
        "coops_water_level_msl",
        fetch(
            c.COOPS_API, c.COOPS / "water_level_8443970_MSL.json", c.COOPS_OBS_PARAMS
        ),
    )
    record(
        "coops_datums",
        fetch(
            f"{c.COOPS_MDAPI}/{c.STATION}/datums.json",
            c.COOPS / "datums_8443970.json",
            {"units": "metric"},
        ),
    )
    record(
        "coops_monthly_mean_msl",
        fetch(
            c.COOPS_API,
            c.COOPS / "monthly_mean_8443970_MSL.json",
            {
                "station": c.STATION,
                "product": "monthly_mean",
                "datum": "MSL",
                "units": "metric",
                "time_zone": "gmt",
                "format": "json",
                "begin_date": "20250101",
                "end_date": "20261031",
                "application": "ocean_mcp_verification",
            },
        ),
    )
    record(
        "coops_sea_level_trend",
        fetch(
            "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/product/"
            "sealvltrends.json",
            c.COOPS / "sealvltrends_8443970.json",
            {"station": c.STATION},
        ),
    )
    docs = {
        "noaa_scn_26_51": (
            "https://www.weather.gov/media/notification/pdf_2026/scn26-51_STOFS.v3.1.pdf",
            "scn26-51_STOFS.v3.1.pdf",
        ),
        "noaa_portal_stofs_3d_atl": (
            "https://polar.ncep.noaa.gov/estofs/atl.htm",
            "polar_estofs_atl.htm",
        ),
        "noaa_portal_stofs_2d_glo": (
            "https://polar.ncep.noaa.gov/estofs/glo.htm",
            "polar_estofs_glo.htm",
        ),
        "nomads_stofs_global_description": (
            "https://nomads.ncep.noaa.gov/txt_descriptions/STOFS_Global_txt.html",
            "nomads_STOFS_Global_txt.html",
        ),
    }
    for key, (url, name) in docs.items():
        try:
            record(key, fetch(url, c.DOCS / name))
        except Exception as e:  # documentation pages are context, not data
            print(f"failed     {key}: {e}")
            entries[key] = {"url": url, "status": f"failed: {e}"}

    if args.grib:
        base = (
            "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/"
            f"stofs_3d_atl.{c.CYCLE_DATE}/"
        )
        for h in range(49):
            name = f"stofs_3d_atl.t12z.conus.east.f{h:03d}.grib2"
            record(f"grib_3d_f{h:03d}", fetch(base + name, c.RAW / "grib" / name))

    write_manifest(entries)
    print("manifest:", c.rel(c.MANIFEST))
    return 0


def write_manifest(entries: dict) -> None:
    c.dump_json(
        {
            "case": {
                "cycle": c.CYCLE_ISO + " UTC",
                "station": c.STATION,
                "forecast_window_hours": list(c.FORECAST_WINDOW),
                "nowcast_windows_hours": {
                    k: list(v) for k, v in c.NOWCAST_WINDOWS.items()
                },
            },
            "note": (
                "sha256 identifies the retrieved bytes; it does not guarantee that the "
                "upstream object is immutable. CO-OPS observations for recent days are "
                "preliminary and may be revised upstream."
            ),
            "entries": entries,
        },
        c.MANIFEST,
    )


if __name__ == "__main__":
    sys.exit(main())
