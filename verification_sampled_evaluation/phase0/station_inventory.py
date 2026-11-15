#!/usr/bin/env python3
"""Phase 0: station identifiers in the archived station files and their CO-OPS mapping.

Rule (also in DESIGN.md): a station record maps to a CO-OPS water-level station if its
``station_name`` contains a 7-digit token (not part of a longer number) that is the ``id``
of a station in the CO-OPS metadata API list ``type=waterlevels`` (active) or
``type=historicwl`` (historic). No Ocean-MCP code is imported.
"""
import collections, json, re, sys
from pathlib import Path
import netCDF4

PKG = Path(__file__).resolve().parent.parent
WP1 = Path("/mnt/d/ocean-mcp/.claude/worktrees/safeguards-comparison/verification_safeguards_comparison/data/archive/base/bodies")
FILES = {  # archived WP1 bodies (sha256 prefix): product, cycle, version
    "3d_20260218": "d13345a36695ac69ff463f52f6f5dc187639e65a068a33626d9ab2090ca633b5",
    "3d_20260816": "f78e84ef18ae35083c7efe83c26df4c907d7359fb397155e1c2d748001d02462",
    "3d_20260817": "f47962fa8504ef4017e5a858603fa8ee0894546524e125ec38025e1fe05289c4",
    "3d_20261030": "4660819425aa1d2eec0e63a37d3a78e8fef2e00f62a1cb56f088347ef51a450f",
    "2d_20261030": "f1ed4e592982fc5974d5356ba06a90c00bdb41ead0308163221a54b018746c23",
}
TOK = re.compile(r"(?<!\d)\d{7}(?!\d)")

def coops_ids():
    act = json.loads((PKG / "phase0/coops/d9ae610d14ccb426fce30ec9daad921a8f57169e9ff57ad6610a204aad457284.json").read_text())
    his = json.loads((PKG / "phase0/coops/b34a6a56c4c0be623b3de3a3cac8632770d55207ef66b0f8dc927e80952a28e9.json").read_text())
    a = {s["id"]: s for s in act["stations"]}
    h = {s["id"]: s for s in his["stations"]}
    return a, h

def main():
    act, his = coops_ids()
    out = {"rule": __doc__.strip().splitlines()[2:6], "files": {}}
    union = {}
    for name, sha in FILES.items():
        ds = netCDF4.Dataset(WP1 / f"{sha}.nc")
        names = [str(s).strip() for s in netCDF4.chartostring(ds.variables["station_name"][:])]
        ds.close()
        recs = []
        for i, n in enumerate(names):
            toks = TOK.findall(n)
            m = [t for t in toks if t in act or t in his]
            recs.append({"index": i, "name": n, "tokens": toks, "coops_id": m[0] if len(m) == 1 else None,
                         "ambiguous": len(m) > 1, "status": ("active" if m and m[0] in act else "historic" if m else None)})
        ids = collections.Counter(r["coops_id"] for r in recs if r["coops_id"])
        out["files"][name] = {
            "sha256": sha, "records": len(names),
            "records_with_7digit_token": sum(bool(r["tokens"]) for r in recs),
            "records_mapped": sum(bool(r["coops_id"]) for r in recs),
            "distinct_coops_ids": len(ids),
            "ids_on_more_than_one_record": {k: v for k, v in ids.items() if v > 1},
            "mapped_historic_only": sorted({r["coops_id"] for r in recs if r["status"] == "historic"}),
            "unmapped_7digit_examples": [r["name"] for r in recs if r["tokens"] and not r["coops_id"]][:15],
            "great_lakes_ids": sorted({r["coops_id"] for r in recs if r["coops_id"] and (act.get(r["coops_id"]) or his.get(r["coops_id"]) or {}).get("greatlakes")}),
        }
        for r in recs:
            if r["coops_id"]:
                union.setdefault(r["coops_id"], set()).add(name)
    # SCN 26-51: stations removed at v3.1 (present in v2.1 files) and the renamed ID
    scn_removed = {"8651370": "Duck, NC", "8423898": "Fort Point, NH", "8639348": "Money Point, VA",
                   "8661070": "Springmaid Pier, SC", "8531680": "Sandy Hook? (South Amboy, check)", "8725110": "Naples Bay, North (old ID)"}
    out["union_ids"] = {k: sorted(v) for k, v in sorted(union.items())}
    out["n_union"] = len(union)
    out["n_union_3d"] = sum(1 for v in union.values() if any(x.startswith("3d") for x in v))
    out["n_union_2d_only"] = sum(1 for v in union.values() if not any(x.startswith("3d") for x in v))
    out["scn_26_51_removed_or_renamed_ids_checked"] = {k: {"label": v, "in_union": k in union,
        "in_coops_lists": k in act or k in his} for k, v in scn_removed.items()}
    (PKG / "phase0/station_inventory.json").write_text(json.dumps(out, indent=1) + "\n")
    for k, v in out["files"].items():
        print(k, {kk: vv for kk, vv in v.items() if kk not in ("unmapped_7digit_examples",)})
        print("   unmapped:", v["unmapped_7digit_examples"][:8])
    print("union", out["n_union"], "3d", out["n_union_3d"], "2d-only", out["n_union_2d_only"])
    print(out["scn_26_51_removed_or_renamed_ids_checked"])

main()
