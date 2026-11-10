#!/usr/bin/env python3
"""Draw the 30 human-check station-cycles (DESIGN.md 9). Frozen sampling rule:

* frame: every case in reference/results/w49_7/cases.jsonl, sorted by case_id;
* 20 cases by simple random sampling from the whole frame, then 10 more from the cases the
  reference marks as non-routine (expected outcome refuse or not_eligible, any invalid model
  value in the station series, a label/documentation mismatch, or a duplicated station ID),
  excluding the first 20; if fewer than 10 non-routine cases exist, all are taken and the
  remainder is filled from the frame;
* random.Random(SEED).sample, SEED = 20261109; the 30 are then shuffled with the same generator
  so the stratum is not visible from the order.

Per case it writes cases/<k>.png (raw model series of the whole file with the window shaded,
observed series on the paired datum, no statistics, < 1600 px) and cases/<k>.txt (the file's
zeta and global datum attributes, the CO-OPS datum list and epoch for the station). The tool's
and the reference's outcomes go to SEALED_outcomes.json, whose SHA-256 is written to
SEALED_outcomes.sha256 before anyone looks at the plots. Run in Phase 3.
"""
import json
import random
from pathlib import Path

SEED = 20261109
N_RANDOM, N_NONROUTINE = 20, 10
PKG = Path(__file__).resolve().parent.parent


def non_routine(c: dict) -> bool:
    inv = sum(v for k, v in c["model_counts_all"].items() if k != "valid")
    return (c["expected"]["expected"] != "compare" or inv > 0
            or c["reference_datum_status"] not in ("label_matches_documentation", "documented_generic_label")
            or c["duplicate_id"] is not None)


def draw(cases: list[dict]) -> list[dict]:
    frame = sorted(cases, key=lambda c: c["case_id"])
    rng = random.Random(SEED)
    first = rng.sample(frame, N_RANDOM)
    ids = {c["case_id"] for c in first}
    pool = [c for c in frame if non_routine(c) and c["case_id"] not in ids]
    k = min(N_NONROUTINE, len(pool))
    second = rng.sample(pool, k)
    if k < N_NONROUTINE:
        rest = [c for c in frame if c["case_id"] not in ids | {x["case_id"] for x in second}]
        second += rng.sample(rest, N_NONROUTINE - k)
    chosen = [dict(c, _stratum="random") for c in first] + [dict(c, _stratum="non_routine") for c in second]
    rng.shuffle(chosen)
    return chosen


if __name__ == "__main__":  # plotting is wired up in Phase 3
    cases = [json.loads(x) for x in (PKG / "reference/results/w49_7/cases.jsonl").read_text().splitlines()]
    print(json.dumps([c["case_id"] for c in draw(cases)]))
