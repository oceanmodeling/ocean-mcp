#!/usr/bin/env python3
"""Write tasks/tasks.json: the frozen WP1 task definitions.

Every task has an identifier, a class, one plain-language statement used
identically for all arms, its inputs (resolved from the archive index, with
SHA-256), the archive stack its sessions and arms read from, and the exact
MCP calls for arms C and D. Arm D calls that cannot express the task (stofs-mcp
0.2.0 has no lead-time window) are the nearest equivalent call, labelled so.

Usage: python -I build_tasks.py <verification_dir>
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

S3_2D = "https://noaa-gestofs-pds.s3.amazonaws.com"
S3_3D = "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl"
F2D_1030 = f"{S3_2D}/stofs_2d_glo.20261030/stofs_2d_glo.t12z.points.cwl.nc"
F3D_1030 = f"{S3_3D}/stofs_3d_atl.20261030/stofs_3d_atl.t12z.points.cwl.nc"
F3D_0816 = f"{S3_3D}/stofs_3d_atl.20260816/stofs_3d_atl.t12z.points.cwl.nc"
F3D_0817 = f"{S3_3D}/stofs_3d_atl.20260817/stofs_3d_atl.t12z.points.cwl.nc"
F3D_0218 = f"{S3_3D}/stofs_3d_atl.20260218/stofs_3d_atl.t12z.points.cwl.nc"
GAUGE = {"latitude": 42.3539, "longitude": -71.0503}  # CO-OPS metadata, archived response

COMPARE_STATEMENT = (
    "For NOAA CO-OPS station {sid} ({sname}), compare the {model} station forecast of the "
    "{cycle} UTC cycle with observed water levels for forecast lead times 0 < lead <= 48 h. "
    "Report the number of compared pairs, bias (model minus observed), RMSE, MAE and Pearson "
    "correlation; the vertical datum of the model values and of the observations, each with "
    "its source; the units; the product version; and any caveat, exclusion, or reason not to "
    "compare."
)


def compare_c(sid, model, date):
    return {"tool": "stofs_compare_with_observations", "arguments": {
        "station_id": sid, "model": model, "cycle_date": date, "cycle_hour": "12",
        "lead_start_hours": 0.0, "lead_end_hours": 48.0, "full_resolution": True,
        "max_points": 2000, "response_format": "json"}}


def compare_d(sid, model, date):
    hours = 54 if model == "2d_global" else 72
    nowcast = 6 if model == "2d_global" else 24
    return {"tool": "stofs_compare_with_observations", "arguments": {
        "station_id": sid, "model": model, "cycle_date": date, "cycle_hour": "12",
        "hours_to_compare": hours, "full_resolution": True, "max_points": 2000,
        "response_format": "json"},
        "nearest_equivalent": True,
        "nearest_equivalent_note": (
            f"stofs-mcp 0.2.0 has no lead-time window; its window starts at the file start "
            f"(cycle - {nowcast} h). hours_to_compare={hours} is the smallest value whose window "
            f"contains 0 < lead <= 48 h; it also includes the {nowcast} h nowcast and the record "
            "at lead 48.1 h.")}


TASKS = [
    # ------------------------------------------------------------- nominal
    dict(id="N1", cls="nominal", title="STOFS-2D-Global vs CO-OPS at Boston, 0-48 h",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-2D-Global",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="2d_global", station="8443970", cycle="2026-10-30",
         inputs=[F2D_1030, ("coops", "8443970", "MSL")], archives=["base"],
         c=[compare_c("8443970", "2d_global", "2026-10-30")],
         d=[compare_d("8443970", "2d_global", "2026-10-30")]),
    dict(id="N2", cls="nominal", title="STOFS-3D-Atlantic vs CO-OPS at Boston, 0-48 h",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-3D-Atlantic",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="3d_atlantic", station="8443970", cycle="2026-10-30",
         inputs=[F3D_1030, ("coops", "8443970", "MSL"), ("coops", "8443970", "NAVD")], archives=["base"],
         c=[compare_c("8443970", "3d_atlantic", "2026-10-30")],
         d=[compare_d("8443970", "3d_atlantic", "2026-10-30")]),
    dict(id="N3", cls="nominal", title="Hurricane Ian non-tidal residual maximum at Fort Myers",
         statement=("For CO-OPS station 8725520 (Fort Myers, FL), 2022-09-27 00:00 to 2022-09-29 23:54 UTC, "
                    "compute the non-tidal residual (observed 6-minute water level minus the 6-minute tide "
                    "prediction, matched by time) and report its maximum with the time(s) at which it occurs, "
                    "the vertical datum and units of both series with their source, and any caveat or "
                    "reason not to compute it."),
         kind="residual", station="8725520",
         inputs=["coops_8725520_water_level_MLLW_20220927_29", "coops_8725520_predictions_MLLW_20220927_29"],
         archives=["base"],
         c=[{"tool": "coops_get_water_levels", "arguments": {
                "station_id": "8725520", "begin_date": "20220927", "end_date": "20220929", "datum": "MLLW",
                "units": "metric", "time_zone": "gmt", "response_format": "json", "max_records": 2000}},
            {"tool": "coops_get_tide_predictions", "arguments": {
                "station_id": "8725520", "begin_date": "20220927", "end_date": "20220929", "datum": "MLLW",
                "units": "metric", "time_zone": "gmt", "response_format": "json", "max_records": 2000}}],
         d="same_as_c",
         note=("coops-mcp has no residual tool. Arms C and D retrieve both series through MCP; the residual "
               "is computed by the frozen client join in grader/adapters.py (exact timestamp match, "
               "observed minus predicted, rounded to 1 mm, maximum and all times attaining it). Arms C and D "
               "use the same package (coops-mcp 0.1.1), so they are expected to be identical.")),
    dict(id="N4", cls="nominal", title="MUR SST subset: cells, finite cells, range",
         statement=("From the ERDDAP dataset jplMURSST41 at https://coastwatch.pfeg.noaa.gov/erddap, "
                    "retrieve analysed_sst at 2024-07-15T09:00:00Z for 40.8 to 42.0 N and 72.2 to 70.8 W at "
                    "native resolution. Report the number of grid cells, the number with a finite value, the "
                    "minimum and maximum, the units with their source, and any caveat or exclusion."),
         kind="griddap",
         inputs=["erddap_jplMURSST41_info", "erddap_jplMURSST41_subset"], archives=["base"],
         c=[{"tool": "erddap_get_griddap_data", "arguments": {
                "server_url": "https://coastwatch.pfeg.noaa.gov/erddap", "dataset_id": "jplMURSST41",
                "variables": ["analysed_sst"], "time_range": ["2024-07-15T09:00:00Z", "2024-07-15T09:00:00Z"],
                "latitude_range": [40.8, 42.0], "longitude_range": [-72.2, -70.8], "stride": 1,
                "response_format": "json", "max_records": 30000}}],
         d="same_as_c",
         note="Arguments as archived in manuscript-final-runs-2026-07-27.md section 3. Arms C and D use erddap-mcp 0.1.2."),
    # ------------------------------------------------- defects in real files
    dict(id="R1a", cls="real_defect", title="STOFS-3D: five highest water levels among stations",
         statement=("In the STOFS-3D-Atlantic station file of the 2026-10-30 12:00 UTC cycle, which five stations "
                    "have the highest water level over all records in the file, and what are those maxima? "
                    "Report the datum and units with their source, and any station or value excluded and why."),
         kind="max", model="3d_atlantic", cycle="2026-10-30", inputs=[F3D_1030], archives=["base"],
         c=[{"tool": "stofs_get_max_water_level", "arguments": {
                "model": "3d_atlantic", "cycle_date": "2026-10-30", "cycle_hour": "12", "top_n": 5,
                "response_format": "json"}}],
         d="same_as_c"),
    dict(id="R1b", cls="real_defect", title="STOFS-3D vs CO-OPS at 9751381 (Lameshur Bay), 0-48 h",
         statement=COMPARE_STATEMENT.format(sid="9751381", sname="Lameshur Bay, St John, VI", model="STOFS-3D-Atlantic",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="3d_atlantic", station="9751381", cycle="2026-10-30",
         inputs=[F3D_1030, ("coops", "9751381", "MSL"), ("coops", "9751381", "NAVD")], archives=["base"],
         c=[compare_c("9751381", "3d_atlantic", "2026-10-30")],
         d=[compare_d("9751381", "3d_atlantic", "2026-10-30")]),
    dict(id="R2", cls="real_defect", title="STOFS-2D: minimum water level at 8571421 (Bishops Head)",
         statement=("In the STOFS-2D-Global station file of the 2026-10-30 12:00 UTC cycle, what is the lowest water "
                    "level at station 8571421 (Bishops Head, MD) over all records in the file? Report the datum and "
                    "units with their source, and any value excluded and why."),
         kind="station_min", model="2d_global", station="8571421", cycle="2026-10-30",
         inputs=[F2D_1030], archives=["base"],
         c=[{"tool": "stofs_get_station_forecast", "arguments": {
                "station_id": "8571421", "model": "2d_global", "product": "cwl", "cycle_date": "2026-10-30",
                "cycle_hour": "12", "response_format": "json"}}],
         d="same_as_c"),
    dict(id="R3", cls="real_defect", title="STOFS-2D: station with the highest water level",
         statement=("In the STOFS-2D-Global station file of the 2026-10-30 12:00 UTC cycle, which station has the "
                    "highest water level over all records in the file, and what is it? Report the datum and units "
                    "with their source, and any station or value excluded and why."),
         kind="max", model="2d_global", cycle="2026-10-30", inputs=[F2D_1030], archives=["base"],
         c=[{"tool": "stofs_get_max_water_level", "arguments": {
                "model": "2d_global", "cycle_date": "2026-10-30", "cycle_hour": "12", "top_n": 5,
                "response_format": "json"}}],
         d="same_as_c"),
    dict(id="R4a", cls="real_defect", title="STOFS-3D vs CO-OPS at Boston, cycle 2026-08-16 12 UTC (one workflow for R4a and R4b)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-3D-Atlantic",
                                            cycle="2026-08-16 12:00")
         + " Use the same, unchanged workflow as for task R4b.",
         kind="compare", model="3d_atlantic", station="8443970", cycle="2026-08-16",
         inputs=[F3D_0816, ("coops", "8443970", "NAVD"), ("coops", "8443970", "MSL")], archives=["base"],
         c=[compare_c("8443970", "3d_atlantic", "2026-08-16")],
         d=[compare_d("8443970", "3d_atlantic", "2026-08-16")]),
    dict(id="R4b", cls="real_defect", title="STOFS-3D vs CO-OPS at Boston, cycle 2026-08-17 12 UTC (one workflow for R4a and R4b)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-3D-Atlantic",
                                            cycle="2026-08-17 12:00")
         + " Use the same, unchanged workflow as for task R4a.",
         kind="compare", model="3d_atlantic", station="8443970", cycle="2026-08-17",
         inputs=[F3D_0817, ("coops", "8443970", "MSL"), ("coops", "8443970", "NAVD")], archives=["base"],
         c=[compare_c("8443970", "3d_atlantic", "2026-08-17")],
         d=[compare_d("8443970", "3d_atlantic", "2026-08-17")]),
    dict(id="R5", cls="real_defect", title="STOFS-2D: vertical datum of the station output",
         statement=("What is the vertical datum of the water levels in the STOFS-2D-Global station file of the "
                    "2026-10-30 12:00 UTC cycle (station 8443970, Boston, MA), and what is the source of that "
                    "statement? Report the product version and units, and any caveat."),
         kind="station_datum", model="2d_global", station="8443970", cycle="2026-10-30",
         inputs=[F2D_1030], archives=["base"],
         c=[{"tool": "stofs_get_station_forecast", "arguments": {
                "station_id": "8443970", "model": "2d_global", "product": "cwl", "cycle_date": "2026-10-30",
                "cycle_hour": "12", "response_format": "json"}}],
         d="same_as_c"),
    dict(id="R6", cls="real_defect", title="STOFS-3D 2026-02-18: station nearest the Boston gauge",
         statement=("In the STOFS-3D-Atlantic station file of the 2026-02-18 12:00 UTC cycle, which station is "
                    "nearest to the CO-OPS Boston gauge at 42.3539 N, 71.0503 W, and how far from it is that "
                    "station? Report any caveat about the station coordinates."),
         kind="nearest", model="3d_atlantic", cycle="2026-02-18", inputs=[F3D_0218], archives=["base"],
         c=[{"tool": "stofs_get_point_forecast", "arguments": {
                **GAUGE, "model": "3d_atlantic", "product": "cwl", "cycle_date": "2026-02-18",
                "cycle_hour": "12", "max_distance_km": 50.0, "response_format": "json"}}],
         d="same_as_c"),
    dict(id="R7", cls="real_defect", title="NDBC 41009, 2024 historical file: highest significant wave height",
         statement=("From NDBC's 2024 historical standard meteorological file for buoy 41009 (41009h2024.txt), "
                    "what is the highest significant wave height (WVHT), and when? Report the units and any value "
                    "excluded and why."),
         kind="buoy_max", station="41009",
         inputs=["https://www.ndbc.noaa.gov/view_text_file.php?filename=41009h2024.txt.gz&dir=data/historical/stdmet/"],
         archives=["base"],
         c=[{"tool": "ww3_get_buoy_history", "arguments": {
                "station_id": "41009", "year": 2024, "max_records": 5000, "response_format": "json"}}],
         d="same_as_c",
         note=("Arm D is ww3-mcp 0.1.2 from PyPI. Arm C is the ww3-mcp 0.1.3 wheel in "
               "verification_ww3_history_fix/dist/ if it exists when Phase 2 starts; otherwise arm C is recorded as "
               "'candidate not available'. The tool caps max_records at 5000 and subsamples the 52,692 rows, so it "
               "cannot return every record; the grade uses the highest WVHT it does return.")),
    # ---------------------------------------------------- synthetic mutations
    dict(id="S1", cls="synthetic", title="SYNTHETIC: 3D datum labels removed (Boston, 0-48 h)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-3D-Atlantic",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="3d_atlantic", station="8443970", cycle="2026-10-30",
         inputs=[F3D_1030, ("coops", "8443970", "MSL"), ("coops", "8443970", "NAVD")], archives=["synthetic/S1", "base"],
         c=[compare_c("8443970", "3d_atlantic", "2026-10-30")], d=[compare_d("8443970", "3d_atlantic", "2026-10-30")]),
    dict(id="S2", cls="synthetic", title="SYNTHETIC: 3D conflicting datum labels (Boston, 0-48 h)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-3D-Atlantic",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="3d_atlantic", station="8443970", cycle="2026-10-30",
         inputs=[F3D_1030, ("coops", "8443970", "MSL"), ("coops", "8443970", "NAVD")], archives=["synthetic/S2", "base"],
         c=[compare_c("8443970", "3d_atlantic", "2026-10-30")], d=[compare_d("8443970", "3d_atlantic", "2026-10-30")]),
    dict(id="S3", cls="synthetic", title="SYNTHETIC: 2D undocumented product version V4.0.0 (Boston, 0-48 h)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-2D-Global",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="2d_global", station="8443970", cycle="2026-10-30",
         inputs=[F2D_1030, ("coops", "8443970", "MSL")], archives=["synthetic/S3", "base"],
         c=[compare_c("8443970", "2d_global", "2026-10-30")], d=[compare_d("8443970", "2d_global", "2026-10-30")]),
    dict(id="S4", cls="synthetic", title="SYNTHETIC: blank and non-finite observations (2D, Boston, 0-48 h)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-2D-Global",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="2d_global", station="8443970", cycle="2026-10-30",
         inputs=[F2D_1030, ("coops", "8443970", "MSL")], archives=["synthetic/S4", "base"],
         c=[compare_c("8443970", "2d_global", "2026-10-30")], d=[compare_d("8443970", "2d_global", "2026-10-30")]),
    dict(id="S5", cls="synthetic", title="SYNTHETIC: harmless wording variant of the 3D datum label (Boston, 0-48 h)",
         statement=COMPARE_STATEMENT.format(sid="8443970", sname="Boston, MA", model="STOFS-3D-Atlantic",
                                            cycle="2026-10-30 12:00"),
         kind="compare", model="3d_atlantic", station="8443970", cycle="2026-10-30",
         inputs=[F3D_1030, ("coops", "8443970", "MSL"), ("coops", "8443970", "NAVD")], archives=["synthetic/S5", "base"],
         c=[compare_c("8443970", "3d_atlantic", "2026-10-30")], d=[compare_d("8443970", "3d_atlantic", "2026-10-30")]),
]

SERVER_FOR_TOOL = {
    "stofs_": "stofs", "coops_": "coops", "erddap_": "erddap", "ww3_": "ww3",
}


def resolve_inputs(vdir: Path, task: dict) -> list[dict]:
    out = []
    stacks = [json.loads((vdir / "data/archive" / a / "index.json").read_text()) for a in task["archives"]]
    for item in task["inputs"]:
        if isinstance(item, tuple):  # CO-OPS water_level masters for station/datum
            _, sid, datum = item
            cyc = datetime.strptime(task["cycle"], "%Y-%m-%d") + timedelta(hours=12)
            need = (cyc - timedelta(hours=24), cyc + timedelta(hours=49))  # widest window any arm asks for
            for a, doc in zip(task["archives"], stacks):
                for e in doc["entries"]:
                    q = dict(parse_qsl(urlsplit(e["url"]).query))
                    if e.get("kind") == "coops_master" and q.get("station") == sid and q.get("datum") == datum:
                        lo = _t(q["begin_date"], False)
                        hi = _t(q["end_date"], True)
                        if lo <= need[1] and need[0] <= hi:
                            out.append(_row(a, e))
            continue
        hits = []
        for a, doc in zip(task["archives"], stacks):
            for e in doc["entries"]:
                if e["url"] == item or e["provenance"].get("input_name") == item:
                    hits.append(_row(a, e))
        if not hits:
            raise LookupError(f"{task['id']}: input {item} not archived")
        out.extend(hits)
    return out


def _t(s, end):
    try:
        return datetime.strptime(s, "%Y%m%d %H:%M")
    except ValueError:
        d = datetime.strptime(s, "%Y%m%d")
        return d.replace(hour=23, minute=59) if end else d


def _row(archive, e):
    return {"archive": archive, "entry": e["id"], "url": e["url"], "sha256": e["response"]["body_sha256"],
            "bytes": e["response"]["bytes"], "source": e["provenance"].get("source"),
            "retrieved_at": e["provenance"].get("retrieved_at"), "kind": e.get("kind"),
            "label": e["provenance"].get("label")}


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    out = []
    for t in TASKS:
        row = {k: v for k, v in t.items() if k not in ("c", "d", "inputs")}
        row["class"] = row.pop("cls")
        row["inputs"] = resolve_inputs(vdir, t)
        calls_c = t["c"]
        calls_d = t["c"] if t["d"] == "same_as_c" else t["d"]
        server = next(v for k, v in SERVER_FOR_TOOL.items() if calls_c[0]["tool"].startswith(k))
        row["server"] = server
        row["mcp_calls"] = {
            "C": [{"call_id": f"{t['id']}_C_{i}", **c} for i, c in enumerate(calls_c)],
            "D": [{"call_id": f"{t['id']}_D_{i}", **c} for i, c in enumerate(calls_d)],
        }
        out.append(row)
    doc = {
        "format": "wp1-tasks/1",
        "arms": {
            "A": "Basic Python: xarray (default decoding) and pandas used as documented; fixed datum pairing from "
                 "current product documentation (STOFS-2D LMSL, STOFS-3D LMSL, both against CO-OPS MSL); no added "
                 "domain rules. Runs where no Ocean-MCP package is importable.",
            "B": "Validated Python: arm A plus datum, quality and temporal rules implemented independently from "
                 "NOAA documentation and CF conventions, each rule's source cited in the code. Does not import, copy "
                 "or paraphrase Ocean-MCP code.",
            "C": "Ocean-MCP candidate through real MCP stdio sessions in replay mode: stofs-mcp 0.3.0 (WP0 wheel, "
                 "sha256 29fcb737...dafdd); coops-mcp 0.1.1, erddap-mcp 0.1.2 from PyPI; for R7 the ww3-mcp 0.1.3 "
                 "wheel if it exists at Phase 2, else 'candidate not available'.",
            "D": "Ocean-MCP released: stofs-mcp 0.2.0 from PyPI through the same sessions; coops-mcp 0.1.1, "
                 "erddap-mcp 0.1.2, and ww3-mcp 0.1.2 (R7) from PyPI. Answers 'what changed between versions', "
                 "not a comparison with Python.",
        },
        "session_rule": "one MCP session per task and arm; replay mode; archives stacked as listed (first wins); "
                        "run inside `unshare -rn` (no network); a session with any replay miss or blocked network "
                        "attempt is invalid",
        "tasks": out,
    }
    (vdir / "tasks/tasks.json").write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{len(out)} tasks written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
