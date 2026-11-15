#!/usr/bin/env python3
"""Write references/references.json: the reference outcome of every task on each axis.

Combines the hand-written specification below (decisions, accepted metadata,
caveats, tolerances, sources) with the values derived independently by
derive_references.py (references/computed_values.json).

Usage: python -I build_references.py <verification_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ----------------------------------------------------------------- sources --
SRC = {
    "SCN26-51": ("NWS Service Change Notice 26-51 (STOFS v3.1), archived in the Boston package "
                 "data/docs/scn26-51_STOFS.v3.1.pdf, sha256 65621c7b...2370: 'Station netCDF output will now be "
                 "referenced to local mean sea level (LMSL) (no longer NAVD88), while gridded output will remain "
                 "referenced to xGEOID20b.' (STOFS-3D-Atlantic section)"),
    "PORTAL3D": ("NOAA STOFS-3D-Atlantic portal polar.ncep.noaa.gov/estofs/atl.htm, archived 2026-11-04, sha256 "
                 "40a2a7de...: 'Operational implementation of the STOFS-3D-Atlantic upgrade to v3.1 occurred at the "
                 "12 UTC cycle on August 17 2026.'"),
    "NOMADS2D": ("NOMADS STOFS-Global product description nomads.ncep.noaa.gov/txt_descriptions/STOFS_Global_txt.html, "
                 "archived 2026-11-04, sha256 616165ee...: 'STOFS-2D-Global water level forecast guidance is "
                 "referenced to Local Mean Sea Level (LMSL) for gridded and station output'"),
    "PORTAL2D": ("NOAA STOFS-2D-Global portal polar.ncep.noaa.gov/estofs/glo.htm, archived 2026-11-04: v3.1 "
                 "implemented at the 12 UTC cycle on August 17 2026"),
    "COOPS_API": ("CO-OPS Data API documentation api.tidesandcurrents.noaa.gov/api/prod/, archived 2026-11-06 "
                  "(base archive e0020): datum is mandatory for water level products; 'application' is an "
                  "identifier for logs"),
    "COOPS_RESP": ("CO-OPS response help api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html, archived "
                   "2026-11-06 (e0022): f = data flags (O count, F/R/L limits); q = p preliminary / v verified"),
    "NDBC_MEASDES": ("NDBC measurement descriptions www.ndbc.noaa.gov/faq/measdes.shtml, archived 2026-11-06 (e0019): "
                     "'Missing data in the Realtime files are denoted by \"MM\" while a variable number of 9's are "
                     "used to denote missing data in the Historical files, depending on the data type (for example: "
                     "999.0 99.0).'"),
    "BOSTON_IND": ("Boston package (branch docs/stofs-v31-boston-example-v2, 57e853e) results/statistics_independent.json: "
                   "pure recalculation from the raw NetCDF and the archived CO-OPS response, without Ocean-MCP; "
                   "reproduced to 1e-16 by STOFS_V31_FABLE_AUDIT.md section 2"),
    "BOSTON_DATUM": ("Boston REPORT.md revision 2 section 3 and STOFS_FINAL_HARDENING_REPORT.md section 6: NOAA's 3D "
                     "station conversion follows VDatum xGEOID20b->LMSL; the remaining reference caveats are the "
                     "tidal epoch (CO-OPS MSL is the 1983-2001 epoch datum) and the unverifiable 2D realization. "
                     "The labels are compatible; equivalence of the realizations is not established"),
    "REVIEW_D1": ("MANUSCRIPT_SECOND_REVIEW.md section D1: Fort Myers residual maximum +2.209 m, first occurrence "
                  "2022-09-28 22:18 UTC, tied at 22:30; 720 verified records, MLLW, metric"),
    "REVIEW_D3": ("MANUSCRIPT_SECOND_REVIEW.md section D3: 121 x 141 = 17,061 cells, 7,760 nulls, 9,301 finite, range "
                  "22.199-23.983 degree_C; nulls are missing, not zero. The archived subset here has the same "
                  "SHA-256 (3eb504b5...25da) as the review's fresh response"),
    "REVIEW_C2": ("MANUSCRIPT_SECOND_REVIEW.md section C2: 105 of 108 rows of the 2026-02-18 and 2026-08-16 3D files "
                  "satisfy the historical reversal pattern; x/y attributes say longitude/latitude even when values "
                  "are reversed; Boston resolves within about 0.002 km after correction"),
    "AUDIT_C1": ("STOFS_V31_FABLE_AUDIT.md C-1 and STOFS_FINAL_HARDENING_REPORT.md section 2: five Caribbean stations "
                 "hold 1e7 + c in all 1,200 records (no-data value plus the station's xGEOID20b->LMSL constant); "
                 "2D dry records hold -99998.6 (shifted -99999); SA816 (Sea of Azov) holds 90.7-136.2 m"),
    "PHYS": ("Physical bound: the largest tidal range on Earth is about 16 m (Bay of Fundy; amplitude about 8 m) and "
             "the largest recorded storm surges are about 8-13 m, so a coastal water level more than 30 m from a "
             "tidal or geodetic datum is not physical. computed_values.json gives, for each use, the interval of "
             "bounds that yields exactly the same result"),
    "CON": "Construction of the mutation (synthetic/make_synthetic.py; synthetic/synthetic_manifest.json)",
    "CF": ("CF standard name table: 'sea_surface_height_above_mean_sea_level' is a CF standard name; "
           "'sea_surface_height_above_msl' is not, so the S5 wording is the CF spelling of the same quantity"),
}

COMPARE_VALUE_TOL = {"n": 0, "bias_m": 0.01, "rmse_m": 0.01, "mae_m": 0.01, "r": 0.001}
TOL_NOTE = ("Statistics: 1 cm (prompt); n exact; Pearson r 0.001 (dimensionless, so the 1 cm rule cannot apply; "
            "three decimals is the precision at which r is normally reported). Retrieved values: 1 mm; "
            "SST 0.001 degree_C (the data's resolution); distance 0.1 km")

# Accepted datum values (canonical) and source classes
LMSL_SET = ["LMSL", "MSL"]
NAVD_SET = ["NAVD88", "NAVD"]
UNDETERMINED = "undetermined"   # canonical class for undetermined/unknown/conflicting/absent


def compare_metadata(model_set, model_source, obs, version_re, version_required=True):
    return {
        "model_datum": {"required": True, "accept": model_set, "source": model_source},
        "obs_datum": {"required": True, "accept": [obs]},
        "units": {"required": True, "accept": ["m"]},
        "product_version": {"required": version_required, "accept_regex": version_re},
    }


def build(computed: dict) -> dict:
    cv = computed
    R = {}

    def compare_values(stats):
        return {"kind": "stats", "values": {k: stats[k] for k in COMPARE_VALUE_TOL}, "tol": COMPARE_VALUE_TOL}

    realization = {"code": "realization", "meaning": "states that the model and observation vertical references are "
                   "treated as compatible but that their equivalence (realization, epoch) is not established, or "
                   "that they may differ"}

    R["N1"] = dict(
        values=compare_values(cv["N1"]["stats"]), values_class="IND", values_source=["BOSTON_IND"],
        metadata=compare_metadata(LMSL_SET, "DOC", "MSL", r"3\.1"),
        metadata_note="2D files carry only the generic label sea_surface_height_above_geoid; the datum comes from "
                      "NOAA documentation (NOMADS2D), so a datum source that cites the file label alone is wrong",
        decision={"kind": "proceed_with_caveat", "caveat": realization, "pairing": {"obs_datum": "MSL"}},
        decision_source=["NOMADS2D", "BOSTON_DATUM", "COOPS_API"],
        note="Prompt: the reference decision is 'proceed with caveat'. Observations were CO-OPS preliminary data "
             "when archived (721 records, all q=p).")
    R["N2"] = dict(
        values=compare_values(cv["N2"]["stats"]), values_class="IND", values_source=["BOSTON_IND"],
        metadata=compare_metadata(LMSL_SET, "FILE_OR_DOC", "MSL", r"3\.1"),
        decision={"kind": "proceed_with_caveat", "caveat": realization, "pairing": {"obs_datum": "MSL"}},
        decision_source=["SCN26-51", "PORTAL3D", "BOSTON_DATUM"])
    R["N3"] = dict(
        values={"kind": "residual", "values": {"residual_max_m": cv["N3"]["residual_max_m"],
                                               "time_utc_any_of": cv["N3"]["tie_times_utc"]},
                "tol": {"residual_max_m": 0.001}},
        values_class="IND", values_source=["REVIEW_D1"],
        metadata={"obs_datum": {"required": True, "accept": ["MLLW"]},
                  "pred_datum": {"required": True, "accept": ["MLLW"]},
                  "units": {"required": True, "accept": ["m"]}},
        decision={"kind": "proceed", "pairing": {"same_datum": True}},
        decision_source=["COOPS_API", "REVIEW_D1"],
        note="Either tied time is accepted; reporting both is also accepted.")
    R["N4"] = dict(
        values={"kind": "griddap", "values": {"cells": 17061, "finite": 9301, "min": 22.199, "max": 23.983},
                "tol": {"cells": 0, "finite": 0, "min": 0.001, "max": 0.001}},
        values_class="IND", values_source=["REVIEW_D3"],
        metadata={"units": {"required": True, "accept": ["degree_C"]}},
        decision={"kind": "proceed", "false_proceed_if": "nulls_as_values"},
        decision_source=["REVIEW_D3"])
    R["R1a"] = dict(
        values={"kind": "ranking", "values": {"top": cv["R1a"]["top5"]}, "tol": {"max_m": 0.001},
                "station_keys": ["8410140", "8411060", "8413320", "8443970", "8418150"]},
        values_class="RECALC+PHY", values_source=["PHYS", "AUDIT_C1"],
        metadata={"model_datum": {"required": True, "accept": LMSL_SET, "source": "FILE_OR_DOC"},
                  "units": {"required": True, "accept": ["m"]}},
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "excluded_stations", "ids": ["9751364", "9751401", "9751381", "9752695", "9752235"],
                             "count_any_of": [5, 6000],
                             "meaning": "the exclusion of the five no-data stations is reported (named, or counted)"},
                  "false_proceed_if": "sentinel_in_answer", "sentinel_ids": ["9751364", "9751401", "9751381", "9752695", "9752235"]},
        decision_source=["AUDIT_C1", "PHYS"],
        note="Over all 1,200 records of the file. Restricting to lead > 0 gives the same five stations with "
             "smaller maxima (computed_values.json R1a.lead_gt0_top5); the task statement fixes 'all records'.")
    R["R1b"] = dict(
        values={"kind": "not_applicable"}, values_class="PHY+CON", values_source=["AUDIT_C1", "PHYS"],
        metadata={"model_datum": {"required": False, "accept": LMSL_SET + [UNDETERMINED], "source": "ANY"},
                  "obs_datum": {"required": False, "accept": ["MSL"]}},
        decision={"kind": "refuse", "cause": "invalid_model_values",
                  "meaning": "declines because no model value is valid (all 1,200 records are no-data codes)"},
        decision_source=["AUDIT_C1", "PHYS"])
    R["R2"] = dict(
        values={"kind": "scalar", "values": {"min_m": cv["R2"]["min_m"]}, "tol": {"min_m": 0.001}},
        values_class="RECALC+PHY", values_source=["PHYS", "AUDIT_C1"],
        metadata={"model_datum": {"required": True, "accept": LMSL_SET, "source": "DOC"},
                  "units": {"required": True, "accept": ["m"]}},
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "excluded_records", "count_any_of": [47],
                             "meaning": "the exclusion of the 47 dry records (-99998.6) is reported"},
                  "false_proceed_if": "value_beyond_bound", "bound_m": 30.0},
        decision_source=["AUDIT_C1", "PHYS"],
        note="All 1,860 records; lead > 0 gives the same minimum and the same 47 exclusions.")
    R["R3"] = dict(
        values={"kind": "top1", "values": {"station": "SA852", "max_m": cv["R3"]["top"]["max_m"]},
                "tol": {"max_m": 0.001}},
        values_class="RECALC+PHY", values_source=["PHYS", "AUDIT_C1"],
        metadata={"model_datum": {"required": True, "accept": LMSL_SET, "source": "DOC"},
                  "units": {"required": True, "accept": ["m"]}},
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "excluded_stations", "ids": ["SA816"], "count_any_of": [],
                             "meaning": "the exclusion of SA816 (90.7-136.2 m, physically implausible) is reported"},
                  "false_proceed_if": "sentinel_in_answer", "sentinel_ids": ["SA816"]},
        decision_source=["AUDIT_C1", "PHYS"])
    R["R4a"] = dict(
        values=compare_values(cv["R4"]["R4a"]["stats"]), values_class="RECALC+DOC", values_source=["SCN26-51", "PORTAL3D"],
        metadata=compare_metadata(NAVD_SET, "FILE_OR_DOC", "NAVD", r"2\.1"),
        decision={"kind": "proceed", "pairing": {"obs_datum": "NAVD"}},
        decision_source=["SCN26-51", "PORTAL3D"],
        note="v2.1.18 file (before the 2026-08-17 12z implementation), label sea_surface_height_above_navd88; "
             "NAVD88 is one geodetic datum, so no realization caveat is required (one is accepted). For "
             "information: the same workflow with CO-OPS MSL gives bias -0.2155 m.")
    R["R4b"] = dict(
        values=compare_values(cv["R4"]["R4b"]["stats"]), values_class="RECALC+DOC", values_source=["SCN26-51", "PORTAL3D"],
        metadata=compare_metadata(LMSL_SET, "FILE_OR_DOC", "MSL", r"3\.1"),
        decision={"kind": "proceed_with_caveat", "caveat": realization, "pairing": {"obs_datum": "MSL"}},
        decision_source=["SCN26-51", "PORTAL3D", "BOSTON_DATUM"],
        note="v3.1.4, first v3.1 cycle; for information: with CO-OPS NAVD the bias would be +0.0566 m.")
    R["R5"] = dict(
        values={"kind": "not_applicable"}, values_class="DOC", values_source=["NOMADS2D"],
        metadata={"model_datum": {"required": True, "accept": LMSL_SET, "source": "DOC"},
                  "units": {"required": True, "accept": ["m"]},
                  "product_version": {"required": True, "accept_regex": r"3\.1"}},
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "doc_source", "meaning": "the datum is attributed to NOAA documentation, "
                             "not to the file label (which names no datum)"},
                  "false_proceed_if": "wrong_datum"},
        decision_source=["NOMADS2D"])
    R["R6"] = dict(
        values={"kind": "nearest", "values": {"station": "8443970", "distance_km": cv["R6"]["distance_km_with_x_read_as_latitude"]},
                "tol": {"distance_km": 0.1}},
        values_class="CON", values_source=["REVIEW_C2"],
        metadata={},
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "coords_reversed", "meaning": "states that the file's station coordinates are "
                             "stored in reversed order (x holds latitude) and were corrected, or flags them"},
                  "false_proceed_if": "wrong_station", "station": "8443970"},
        decision_source=["REVIEW_C2"],
        note="Reading x as longitude, as the attributes say, the Boston record lies at 71 S, 42 E, and the nearest "
             "record is Trident Pier, FL, 1,772 km away (computed_values.json R6, for information).")
    R["R7"] = dict(
        values={"kind": "scalar", "values": {"max_wvht_m": cv["R7"]["max_wvht_m"]}, "tol": {"max_wvht_m": 0.001}},
        values_class="DOC+RECALC", values_source=["NDBC_MEASDES"],
        values_corroboration="NOAA CoastWatch ERDDAP cwwcNDBCMet, 41009, 2024: 17,457 non-null WVHT, maximum 6.32 m at "
                             "2024-10-10T08:10:00Z (base archive e0021)",
        metadata={"units": {"required": True, "accept": ["m"]}},
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "excluded_records", "count_any_of": "any_positive",
                             "meaning": "the exclusion of the 9-filled missing values (WVHT 99.00) is reported"},
                  "false_proceed_if": "value_beyond_bound", "bound_m": 30.0},
        decision_source=["NDBC_MEASDES"],
        note="The value is the maximum over the whole file. A tool that returns a subsample is graded on the "
             "highest value it returns; if the true maximum is not in its subsample the value is outside tolerance.")
    R["S1"] = dict(
        values={"kind": "stats_if_proceeding", **compare_values(cv["S1"]["values_if_proceeding"])},
        values_class="CON", values_source=["CON"],
        metadata={"model_datum": {"required": True, "accept": [UNDETERMINED] + LMSL_SET, "source": "S1_RULE"},
                  "units": {"required": False, "accept": ["m"]}},
        metadata_note="Accepted: undetermined/absent, or LMSL/MSL attributed to documentation for v3.1 (the file "
                      "has no label). Wrong: a datum attributed to the file label, or NAVD88",
        decision={"kind": "refuse_or_flagged_proceed", "cause": "datum_label_absent",
                  "caveat": {"code": "label_absent_assumed", "meaning": "proceeds only while stating that the file "
                             "has no datum label and that the datum is assumed from documentation"},
                  "pairing": {"obs_datum": "MSL"}},
        decision_source=["SCN26-51", "PORTAL3D", "CON"],
        justification=("Refusal or a flagged assumption are both accepted. The product version is identifiable "
                       "(history names stofs.v3.1.6) and NOAA documents LMSL for v3.1 station output, so the datum "
                       "is not truly unknown: it is unlabelled. Proceeding with the documented datum is defensible "
                       "only if the missing label is stated. Proceeding silently is a false proceed."))
    R["S2"] = dict(
        values={"kind": "not_applicable"}, values_class="CON", values_source=["CON"],
        metadata={"model_datum": {"required": True, "accept": [UNDETERMINED], "source": "ANY"}},
        decision={"kind": "refuse", "cause": "datum_conflict"},
        decision_source=["CON"],
        justification=("Refusal only. The variable names two different datums (standard_name MSL, long_name NAVD88). "
                       "Documentation describes intended processing, not this file; one of the file's own labels "
                       "is wrong, so neither can be trusted and no assumption can be justified."))
    R["S3"] = dict(
        values={"kind": "not_applicable"}, values_class="CON", values_source=["CON"],
        metadata={"model_datum": {"required": True, "accept": [UNDETERMINED], "source": "ANY"},
                  "product_version": {"required": False, "accept_regex": r"4\.0"}},
        decision={"kind": "refuse", "cause": "version_undocumented"},
        decision_source=["NOMADS2D", "SCN26-51", "CON"],
        justification=("Refusal only. The 2D label (above geoid) names no datum, and NOAA documents the station datum "
                       "only for the released versions; for V4.0.0 the datum is truly unknown. STOFS-3D changed its "
                       "station datum at a version boundary in 2026, so carrying V3.1's datum forward is not a safe "
                       "assumption. Declining when the datum is truly unknown is a success (prompt)."))
    R["S4"] = dict(
        values=compare_values(cv["S4"]["stats"]), values_class="CON+RECALC", values_source=["CON"],
        metadata=compare_metadata(LMSL_SET, "DOC", "MSL", r"3\.1"),
        decision={"kind": "proceed_with_caveat",
                  "caveat": {"code": "excluded_obs", "count_any_of": [5],
                             "meaning": "the exclusion of the 5 blank or non-finite observations is reported"},
                  "false_proceed_if": "s4_invalid", "n_expected": 475, "pairing": {"obs_datum": "MSL"}},
        decision_source=["CON", "COOPS_RESP"],
        note=("Injected at 2026-10-30 18:00 (''), 10-31 00:00 ('NaN'), 06:00 ('Infinity'), 12:00 ('-Infinity'), "
              "11-01 00:00 (''). Because only 5 of 480 pairs change, a workflow that replaced the blanks by zero "
              "would still be within the 1 cm statistic tolerance; the decision axis (n, finite statistics, "
              "reported exclusion) is what distinguishes it."))
    R["S5"] = dict(
        values=compare_values(cv["S5"]["values_if_proceeding"]), values_class="CON", values_source=["CON", "CF"],
        metadata=compare_metadata(LMSL_SET, "FILE_OR_DOC", "MSL", r"3\.1"),
        decision={"kind": "proceed_with_caveat", "caveat": realization, "pairing": {"obs_datum": "MSL"}},
        decision_source=["CON", "CF", "SCN26-51"],
        note="Exists to detect false refusals: the correct outcome is to proceed, as in N2.")
    return R


def main() -> int:
    vdir = Path(sys.argv[1]).resolve()
    computed = json.loads((vdir / "references/computed_values.json").read_text())
    refs = build(computed)
    doc = {"format": "wp1-references/1", "sources": SRC, "tolerance_note": TOL_NOTE,
           "undetermined_class": UNDETERMINED,
           "decision_outcomes": [
               "correct_proceed", "correct_proceed_with_caveat", "proceed_caveat_missing",
               "correct_refusal_or_flag", "refusal_cause_not_named", "false_proceed", "false_refusal",
               "not_supported", "candidate_not_available", "error"],
           "decision_outcome_notes": {
               "proceed_caveat_missing": "added: the decision to compare or exclude was right, but the caveat or "
                                         "exclusion report that the reference requires is absent",
               "refusal_cause_not_named": "added: declined, but the stated reason is not the reference cause"},
           "tasks": refs}
    (vdir / "references/references.json").write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{len(refs)} task references written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
