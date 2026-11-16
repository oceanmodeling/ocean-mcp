#!/usr/bin/env python3
"""Fetch the new WP1 inputs from NOAA (and two documentation pages) in record mode.

Requests go one at a time, with a pause between them, through an httpx client
whose transport is patched by ``ocean_replay_launcher`` in record mode. Each
request and its decoded response body (stored under its SHA-256) is appended
to the base archive, and DNS answers are recorded for the ERDDAP SSRF check.

Each URL is written exactly as the server package under test builds it (read
from the installed package source, not by running the tools), so that replay
can answer the server's own request by exact match. CO-OPS water-level
responses are marked as *masters*: replay slices them by time for servers
that ask for a sub-window.

An input that is already archived is skipped, so the script can be rerun.
Expected checksums, where an earlier review recorded them, are verified.

Usage: python -I fetch_inputs.py <archive_dir> <log.jsonl> [--only NAME ...]
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
PAUSE_S = 4.0

S3_3D = "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl"
COOPS = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap"


def coops_url(params: dict) -> str:
    return COOPS + "?" + urlencode(params)


def wl(station, datum, begin, end, application):
    # stofs_mcp/client.py fetch_coops_observations builds exactly these keys
    return {
        "station": station,
        "product": "water_level",
        "datum": datum,
        "units": "metric",
        "time_zone": "gmt",
        "format": "json",
        "begin_date": begin,
        "end_date": end,
        "application": application,
    }


INPUTS = [
    # --- STOFS-3D-Atlantic station files (R4, R6) -------------------------
    dict(name="stofs3d_20260218_t12z", task=["R6"], kind="exact",
         url=f"{S3_3D}/stofs_3d_atl.20260218/stofs_3d_atl.t12z.points.cwl.nc",
         expect_sha="d13345a36695ac69ff463f52f6f5dc187639e65a068a33626d9ab2090ca633b5",
         expect_source="MANUSCRIPT_SECOND_REVIEW.md checksum table"),
    dict(name="stofs3d_20260816_t12z", task=["R4"], kind="exact",
         url=f"{S3_3D}/stofs_3d_atl.20260816/stofs_3d_atl.t12z.points.cwl.nc",
         expect_sha="f78e84ef18ae35083c7efe83c26df4c907d7359fb397155e1c2d748001d02462",
         expect_source="MANUSCRIPT_SECOND_REVIEW.md checksum table"),
    dict(name="stofs3d_20260817_t12z", task=["R4"], kind="exact",
         url=f"{S3_3D}/stofs_3d_atl.20260817/stofs_3d_atl.t12z.points.cwl.nc",
         expect_sha="f47962fa8504ef4017e5a858603fa8ee0894546524e125ec38025e1fe05289c4",
         expect_source="MANUSCRIPT_SECOND_REVIEW.md checksum table"),
    # --- CO-OPS water-level masters (full UTC days) --------------------------
    dict(name="coops_8443970_NAVD_20260815_19", task=["R4"], kind="coops_master",
         url=coops_url(wl("8443970", "NAVD", "20260815", "20260819", "ocean_mcp_wp1"))),
    dict(name="coops_8443970_MSL_20260815_19", task=["R4"], kind="coops_master",
         url=coops_url(wl("8443970", "MSL", "20260815", "20260819", "ocean_mcp_wp1"))),
    dict(name="coops_8443970_MSL_20261029_1101", task=["N1", "S3", "S4", "S5"], kind="coops_master",
         url=coops_url(wl("8443970", "MSL", "20261029", "20261101", "ocean_mcp_wp1")),
         note="extends the 2026-11-04 Boston master past 2026-11-01 12:00; also a revision check"),
    dict(name="coops_8443970_NAVD_20261029_1101", task=["N2", "S1", "S2", "S5"], kind="coops_master",
         url=coops_url(wl("8443970", "NAVD", "20261029", "20261101", "ocean_mcp_wp1"))),
    dict(name="coops_9751381_MSL_20261029_1101", task=["R1"], kind="coops_master",
         url=coops_url(wl("9751381", "MSL", "20261029", "20261101", "ocean_mcp_wp1"))),
    dict(name="coops_9751381_NAVD_20261029_1101", task=["R1"], kind="coops_master",
         url=coops_url(wl("9751381", "NAVD", "20261029", "20261101", "ocean_mcp_wp1"))),
    # --- CO-OPS Hurricane Ian, Fort Myers (N3): exactly as coops-mcp 0.1.1 asks
    dict(name="coops_8725520_water_level_MLLW_20220927_29", task=["N3"], kind="exact",
         url=coops_url({"station": "8725520", "product": "water_level", "datum": "MLLW",
                        "units": "metric", "time_zone": "gmt", "begin_date": "20220927",
                        "end_date": "20220929", "format": "json", "application": "coops_mcp"})),
    dict(name="coops_8725520_predictions_MLLW_20220927_29", task=["N3"], kind="exact",
         url=coops_url({"station": "8725520", "product": "predictions", "datum": "MLLW",
                        "units": "metric", "time_zone": "gmt", "begin_date": "20220927",
                        "end_date": "20220929", "format": "json", "application": "coops_mcp"})),
    # --- ERDDAP MUR SST (N4): exactly as erddap-mcp 0.1.2 asks ----------------
    dict(name="erddap_jplMURSST41_info", task=["N4"], kind="exact",
         url=f"{ERDDAP}/info/jplMURSST41/index.json"),
    dict(name="erddap_jplMURSST41_subset", task=["N4"], kind="exact",
         url=f"{ERDDAP}/griddap/jplMURSST41.json?"
             "analysed_sst[(2024-07-15T09:00:00Z)][(40.8):(42.0)][(-72.2):(-70.8)]",
         expect_sha="3eb504b5454363bb5e4a88adf98729ffa0bdcedf831723d54513d3e94bf625da",
         expect_source="MANUSCRIPT_SECOND_REVIEW.md checksum table (fresh direct MUR response; "
                       "request form not recorded there, so a mismatch is informative only)",
         expect_strict=False),
    # --- R7 corroborating reference: NOAA CoastWatch ERDDAP copy of NDBC 41009
    # First attempt (kept in the archive as recorded): lower-case "wvht" is not
    # a variable of this dataset and ERDDAP answered 400. The variable is "WVHT".
    dict(name="erddap_cwwcNDBCMet_41009_2024_wvht_attempt1", task=["R7"], kind="exact",
         url=f"{ERDDAP}/tabledap/cwwcNDBCMet.csv?station,time,wvht"
             "&station=%2241009%22&time%3E=2024-01-01T00:00:00Z&time%3C2025-01-01T00:00:00Z"),
    dict(name="erddap_cwwcNDBCMet_41009_2024_WVHT", task=["R7"], kind="exact",
         url=f"{ERDDAP}/tabledap/cwwcNDBCMet.csv?station,time,WVHT"
             "&station=%2241009%22&time%3E=2024-01-01T00:00:00Z&time%3C2025-01-01T00:00:00Z"),
    # --- documentation used for reference outcomes ---------------------------
    dict(name="doc_ndbc_measdes", task=["R7"], kind="exact",
         url="https://www.ndbc.noaa.gov/faq/measdes.shtml"),
    dict(name="doc_coops_api_help", task=["N1", "N2", "N3"], kind="exact",
         url="https://api.tidesandcurrents.noaa.gov/api/prod/"),
    dict(name="doc_coops_response_help", task=["N1", "N2", "N3", "S4"], kind="exact",
         url="https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html"),
]


def load_launcher():
    spec = importlib.util.spec_from_file_location("ocean_replay_launcher", HERE / "ocean_replay_launcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def main() -> int:
    archive_dir, log = sys.argv[1], sys.argv[2]
    only = set(sys.argv[sys.argv.index("--only") + 1:]) if "--only" in sys.argv else None
    L = load_launcher()
    engine = L.install("record", [archive_dir], log)
    arc = engine.archives[0]
    import httpx

    report = []
    first = True
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        for item in INPUTS:
            if only and item["name"] not in only:
                continue
            key = L.key_string(L.request_key("GET", item["url"]))
            if key in arc.by_key:
                report.append({"name": item["name"], "status": "already archived",
                               "entry": arc.by_key[key]["id"]})
                continue
            if not first:
                time.sleep(PAUSE_S)
            first = False
            n_before = len(arc.doc["entries"])
            try:
                resp = await client.get(item["url"])
                status = resp.status_code
            except Exception as exc:  # report and continue
                report.append({"name": item["name"], "status": f"FAILED {type(exc).__name__}: {exc}"})
                continue
            new = arc.doc["entries"][n_before:]
            entry = arc.by_key.get(key) or (new[-1] if new else None)
            if entry is None:
                report.append({"name": item["name"], "status": "FAILED: not archived"})
                continue
            entry["kind"] = item["kind"]
            entry["provenance"].update({"input_name": item["name"], "tasks": item["task"],
                                        "note": item.get("note")})
            arc.save()
            row = {"name": item["name"], "entry": entry["id"], "http_status": status,
                   "bytes": entry["response"]["bytes"], "sha256": entry["response"]["body_sha256"],
                   "retrieved_at": entry["provenance"]["retrieved_at"]}
            if item.get("expect_sha"):
                row["expected_sha256"] = item["expect_sha"]
                row["expected_source"] = item["expect_source"]
                row["matches_expected"] = item["expect_sha"] == entry["response"]["body_sha256"]
            if item["kind"] == "coops_master" and status == 200:
                try:
                    doc = arc.verified_master(entry)
                    row["records"] = len(doc.get("data", []))
                    row["round_trip"] = "byte-exact"
                except Exception as exc:
                    row["round_trip"] = f"FAILED: {exc}"
                    if "error" in json.loads(arc.body_bytes(entry)):
                        row["coops_error"] = json.loads(arc.body_bytes(entry))["error"]
            report.append(row)
            print(json.dumps(row), flush=True)
    out = Path(archive_dir) / f"fetch_report_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
