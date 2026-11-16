"""Step 4: vertical-reference evidence for the comparison (no offsets applied).

Collects: the zeta datum labels and product versions from the files; NOAA's
statements from the archived documentation pages; the CO-OPS station datums
and their tidal epoch; and the recent monthly mean sea level relative to the
CO-OPS MSL datum (how far present-day water levels sit above the 1983-2001
epoch datum). Writes results/datum_assessment.json.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/04_datum_assessment.py
"""

from __future__ import annotations

import html
import re
import sys

import numpy as np

import _common as c


def sentences(doc: str, pattern: str) -> list[str]:
    text = (c.DOCS / doc).read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))
    return [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if re.search(pattern, s)
    ]


def main() -> int:
    files = {}
    for model in c.STOFS_FILES:
        ex = c.load_json(c.DERIVED / f"boston_{model}.json")
        g = ex["global_attributes"]
        version = None
        m = re.search(r"stofs\.v(\d+(?:\.\d+)*)", str(g.get("history", "")))
        if m:
            version = f"stofs.v{m.group(1)}"
        m = re.search(
            r"STOFS_2D_GLOBAL[ ._]*V?(\d+(?:\.\d+)*)", str(g.get("title", ""))
        )
        if m:
            version = f"STOFS_2D_GLOBAL V{m.group(1)}"
        files[model] = {
            "zeta_standard_name": ex["zeta_attributes"].get("standard_name"),
            "zeta_long_name": ex["zeta_attributes"].get("long_name"),
            "product_version": version,
            "model_attribute": g.get("model"),
            "station_point": {"x_lon": ex["x_raw"], "y_lat": ex["y_raw"]},
        }

    noaa = {
        "stofs_3d_atl_portal": sentences(
            "polar_estofs_atl.htm",
            r"(?i)LMSL|NAVD88|xGEOID|MLLW|12 UTC cycle|bias correction",
        ),
        "stofs_2d_glo_portal": sentences(
            "polar_estofs_glo.htm", r"(?i)bias correction|12 UTC cycle|MSL"
        ),
        "nomads_stofs_global": sentences(
            "nomads_STOFS_Global_txt.html", r"(?i)referenced to|datum|LMSL"
        ),
    }

    dat = c.load_json(c.COOPS / "datums_8443970.json")
    v = {d["name"]: d["value"] for d in dat["datums"]}
    coops = {
        "epoch": dat.get("epoch"),
        "units": dat.get("units"),
        "MSL_above_STND_m": v["MSL"],
        "NAVD88_above_STND_m": v["NAVD88"],
        "NAVD88_minus_MSL_m": round(v["NAVD88"] - v["MSL"], 4),
    }

    mm = c.load_json(c.COOPS / "monthly_mean_8443970_MSL.json")["data"]
    monthly = [
        {
            "month": f"{r['year']}-{int(r['month']):02d}",
            "mean_sea_level_vs_MSL_datum_m": float(r["MSL"]),
        }
        for r in mm
        if r.get("MSL") not in (None, "")
    ]
    last12 = monthly[-12:]
    vals = np.array([r["mean_sea_level_vs_MSL_datum_m"] for r in last12])

    stats = c.load_json(c.RESULTS / "statistics_independent.json")["results"]
    obs_mean = {k: w["statistics"]["obs_mean_m"] for k, w in stats.items()}

    out = {
        "files": files,
        "noaa_statements": noaa,
        "coops_station_datums": coops,
        "monthly_mean_sea_level": {
            "months": monthly,
            "last_12_months": [last12[0]["month"], last12[-1]["month"]],
            "last_12_mean_m": round(float(vals.mean()), 4),
            "last_12_range_m": [
                round(float(vals.min()), 4),
                round(float(vals.max()), 4),
            ],
        },
        "observed_mean_in_windows_vs_MSL_datum_m": obs_mean,
        "note": (
            "No vertical transformation or offset is applied anywhere in this package. "
            "These numbers describe the references; they are not corrections."
        ),
    }
    c.dump_json(out, c.RESULTS / "datum_assessment.json")
    for k, f in files.items():
        print(k, f)
    print("CO-OPS:", coops)
    print(
        "monthly MSL vs datum, last 12:",
        out["monthly_mean_sea_level"]["last_12_months"],
        "mean",
        out["monthly_mean_sea_level"]["last_12_mean_m"],
        "range",
        out["monthly_mean_sea_level"]["last_12_range_m"],
    )
    print("observed mean in windows:", {k: round(x, 4) for k, x in obs_mean.items()})
    for k, ss in noaa.items():
        print(k, "->", len(ss), "sentences;", ss[:3])
    return 0


if __name__ == "__main__":
    sys.exit(main())
