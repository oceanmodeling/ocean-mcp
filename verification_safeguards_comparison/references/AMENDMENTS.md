# Amendments to the frozen references

The frozen references are `references/references.json` from freeze commit `5d84c13`
(sha256 `e4e8b270…042f3`). They are never edited. `references/amend_references.py` applies the
amendments below and writes `references/references.amended.json`. Every grading is produced twice:

- `grader/grade.py` on the frozen references writes `results/grades_*.{json,csv,md}`;
- `grader/grade_amended.py` applies the same frozen grading functions to the amended references and
  writes `results/grades_*_amended.*`.

Both are kept.

## A1. S1, axis 1: values are graded only if the workflow proceeds

- **When recorded:** 2026-11-06, after arms A and B were graded and before arms C or D were run on
  any task.
- **Frozen value:** `tasks.S1.values.kind = "stats"`.
- **Amended value:** `"stats_if_proceeding"`.
- **Evidence:**
  - **The bug.** `references/build_references.py` writes the S1 values as
    `{"kind": "stats_if_proceeding", **compare_values(...)}`. `compare_values` returns its own
    `"kind": "stats"`, which overrides the intended key.
  - **The intended rule** is stated in three places, all committed in the freeze:
    - DESIGN.md §4 ("S1 | if proceeding: N2 values");
    - the S1 justification in `references.json` (a refusal is an accepted outcome);
    - `grade.py`, which has the branch `stats_if_proceeding` and action refuse, returning
      `not_applicable`.
  - **The effect.** With the frozen value, a workflow that correctly refuses S1 is scored
    `not_returned` on axis 1.
- **Observed effect:** S1 arm B, values `not_returned` → `not_applicable`. No other cell of arms A
  or B changes.
- **Scope:** axis 1 of task S1, for workflows that decline. No other task, axis, tolerance or rule
  changes.

## Other change after the freeze (not a reference amendment)

- **Phase 0 DNS-guard demonstration.**
  - *Why it changed.* The base archive gained the DNS answers for `coastwatch.pfeg.noaa.gov` when the
    N4 inputs were recorded. The original demonstration then no longer exercised the guard.
  - *What changed.*
    - `phase0/spec_erddap_dnsguard.json` now uses a host whose DNS is not archived
      (`erddap.secoora.org`), and the session was rerun.
    - `phase0/verify_phase0.py` now also checks the *reason* each fail-loud session is invalid
      (`replay_misses` or `network_blocked`).
  - *Effect.* No task, reference or grading rule is affected.

## A2. S2 and S3: sensitivity grading with a lenient decision rule (requested by the author)

- **When recorded:** 2026-11-06, at the start of Phase 2, before arms C or D were run on any task.
- **Who asked, and why:** the author asked for it. The frozen "refuse only" rule for S2 and S3
  coincides with what stofs-mcp 0.3.0 implements, and the designer had read that source.
- **What it is:** a second grading, not a change.
  - The frozen grading stays primary.
  - `grader/grade_sensitivity.py` reports, for S2 and S3 and all four arms, the frozen grade next
    to a lenient grade. It uses the frozen grading functions unchanged.
- **The lenient rule** also accepts proceeding when all three of these hold:
  1. the cause is stated explicitly, matched by the frozen cause patterns: the datum conflict (S2),
     or the undocumented version (S3);
  2. the datum used is attributed to documentation (the frozen `DOC_RE`, applied to the datum
     source), or labelled as an assumption (`/assum|presum|taken from documentation|per
     documentation/`);
  3. the observation datum is the CO-OPS datum of the stated model datum.

  Refusals are graded as in the frozen rule.
- **Metadata, lenient:** LMSL/MSL or NAVD88 is also accepted when condition 2 holds.
- **Values:** not re-graded. They stay "not applicable", and the returned values are listed.
- **Output:** `results/sensitivity_A2.{json,csv,md}`.
- **Self-test:** `grade_sensitivity.py --selftest` (6 cases).

## A3. R7: grade the maximum the response states as its answer (requested by the author)

- **When recorded:** 2026-11-08, before arm C-post (WP1b) was run.
- **Why it is needed.** The frozen R7 reading takes the maximum WVHT over the rows a response
  returns (`grader/adapters.py`, `adapt_buoy_max`).
  - **ww3-mcp 0.1.2:** the reading was adequate, because its returned rows were a stride through
    the whole year.
  - **ww3-mcp 0.1.3:** the reading misses the answer.
    - The response states the whole-file maximum in its summary: 6.32 m at
      2024-10-10 08:10 UTC.
    - It returns the most recent `max_records` rows, and their highest value is 5.35 m (WP0b
      REPORT §2).
  - So the frozen reading does not read the maximum a response states as its answer.
- **What it is:** a second grading of R7 for all arms. It changes nothing.
  - **Frozen reading:** the maximum over the returned rows. It is reported first.
  - **Amended reading:** the maximum the response reports as its answer to the task. This is a
    numeric `summary.max` (with `summary.max_time`) when the response has one. Otherwise it is the
    frozen reading, because the response states no other answer.
  - **Arms A and B:** the value the script reports, the same both ways.
  - **What stays frozen:** the grader, the adapters, the references, the tolerances and the
    decision rules. The tool was not asked to return different rows.
- **Output:** `results/r7_A3.{json,csv,md}`, with the triggering text for each grade.
- **Script:** `grader/grade_r7_a3.py` (3 self-tests).
- **Before C-post:** arms A, B, C and D are graded the same both ways:
  - A: 99.0, false proceed;
  - B: 6.32, correct;
  - C: candidate not available;
  - D: 99.0, false proceed.
- **With C-post (after WP1b):**
  - **Frozen reading:** 5.35 m, from the 5,000 most recent rows, so outside tolerance.
  - **Amended reading:** 6.32 m, from `summary.max`, so within tolerance.
  - **Metadata and decision:** the same both ways. They are misread by the frozen adapter (units
    map; exclusion key names), and reported as disagreements in REPORT §1.5.
