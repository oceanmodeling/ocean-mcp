# WP7: Figure 5, one full offline repeat, and three fixes to stofs-mcp (post-WP5)

Branch `fix/stofs-post-wp5` (from `fix/stofs-post-wp1` `52c7f46`), worktree
`.claude/worktrees/stofs-post-wp5`. Local only.

- **Code:** commit `f5ab1fd`, only `servers/stofs-mcp/`.
- **This report and its evidence:** under `verification/regression_stofs_0.3.0/` (first committed as
  `verification_post_wp5/`).
- **Network:** no network request was made for WP7. Everything ran from archives and caches
  already on disk.
- **Load:** CPU-heavy work ran one job at a time, at `nice 19` and `ionice` idle priority.

## Task C: the three fixes

| # | Fix | Where |
|---|---|---|
| D-1 | **CO-OPS rejection message.** A non-200 CO-OPS answer with a JSON `error.message` raises `ValueError("CO-OPS API error: <message>")` before `raise_for_status()`. The compare tool therefore says "Could not fetch CO-OPS observations: CO-OPS API error: <message>" and no longer blames the S3 bucket | `client.py` `fetch_coops_observations` |
| D-2 | **Duplicated station identifiers.** The first matching record is still used. All matches are recorded, and `station_warning` (JSON) and a "Station warning" line (Markdown) name the matching records, the record used, and the largest absolute difference of their valid values: in the comparison window for the compare tool, over the series for the station tool. The point tool selects by coordinates and is unchanged | `utils.py` (`parse_station_netcdf`, `station_match_warning`, `station_match_markdown_lines`), `tools/validation.py`, `tools/forecast.py` |
| Epoch | **Epoch in the datum note.** When the CO-OPS datum is tidal (MSL, MLLW, MLW, MTL, DTL, MHW, MHHW; not NAVD), `datum_note` appends: "The CO-OPS <datum> datum is defined on a tidal-datum epoch (1983–2001 at most stations); recent mean sea level may differ from it, so a mean bias includes that difference unless the model carries present-day mean level. The station's epoch is not checked here." | `models.py` `COOPS_TIDAL_DATUMS`, `tools/validation.py` |

**CHANGELOG** (version stays 0.3.0, unreleased):
- a "WP5 fixes" section describing the three fixes;
- lines 71–72 corrected: `alignment` and `observation_quality` are now listed under "Added", since
  0.2.0 had neither key (checked in `stofs-mcp-v0.2.0`). `station_warning` is listed there too.

**Tests:** 11 new, in `tests/test_wp5_fixes.py`. They use verbatim archived NOAA bytes
(`tests/fixtures/wp5_fixtures_SOURCES.md`):
- the two HTTP 400 bodies ("The supported Datum values are: …" and "There is no MSL for the
  station: 8531232") and the no-data body;
- an excerpt of the real STOFS-2D-Global 2026-10-26 12z file in which 8414721 sits on two
  records, 'STKM1 … Fort Point' and 'FRAM1 … Frankfort'. The two are different named places; one
  stores the −99999 dry value. The excerpt was extracted by `scripts/extract_dup_excerpt.py`;
- one epoch-sentence test, with a NAVD control.

The expected differences are recalculated in the tests independently of the code under test.

### Test gate

| Check | Result |
|---|---|
| CPython 3.13.12, `pytest tests/ --ignore=tests/test_live.py` | **384 collected, 384 passed** (373 before + 11 new); `logs/py3.13.pytest.log` |
| CPython 3.11, 3.12 | **Not run.** `uv sync --offline` cannot obtain `pydantic-core==2.50.4` cp311/cp312 wheels from the local cache (`logs/py3.11.sync.log`, `py3.12.sync.log`), and the brief forbids network requests. An offline install from WP1b's recorded freezes failed for the same reason |
| `ruff check servers/ --select E,F,W --ignore E501` (ruff 0.15.2) | pass |
| `ruff format --check servers/` | pass (313 files) |
| `uv build` (offline) | wheel `stofs_mcp-0.3.0-py3-none-any.whl`, **SHA-256 `afb8be50d4bd025a07207b9aa3b67e4a733c3c9350bf65064c0b9c32f9cbd0cc`**, identical in two builds; copy in `dist/` |

### Regression 1: the WP5 sampled evaluation with the new wheel

- **Setup.** A scratch copy of `verification_sampled_evaluation/` (from `c1ace27`) was used, so
  the package on its branch is unchanged.
  - Archive bodies and environments are hard links.
  - A new environment holds the new wheel; every other package is from the C-post freeze.
- **Sessions.** The 60 stofs-mcp 0.3.0 sessions (15,197 calls) ran in replay mode, serially,
  inside `unshare -rn`: **all 60 valid, 0 replay misses.**
- **Grading.** Regraded with the frozen WP5 grader against the committed reference
  (`results/regression_sampled/summary.json`, `changed_cases.json`, `scripts/regress_sampled.py`).

| Quantity | Expected | Result |
|---|---|---|
| Outcome classes (correct comparison / correct refusal / refusal reason differs / false refusal / undetected / not eligible / other) | 9,948 / 105 / 0 / 0 / 0 / 5,143 / 1 | **9,948 / 105 / 0 / 0 / 0 / 5,143 / 1** |
| Of the 465 misattributed refusals, now carrying the CO-OPS message | 465 | **465** (e.g. `2d_20260601_8532786`: "Could not fetch CO-OPS observations: CO-OPS API error: There is no MSL for the station: 8532786") |
| Cases with `station_warning` | the 146 duplicate-identifier cases | **72**. See below |
| Cases whose class changed | 0 | **0** |

**Station warnings: 72, not 146.**
- The 146 duplicate-identifier cases are 72 comparisons and 74 not-eligible cases.
- The not-eligible ones decline (no usable observations) before any JSON is produced, so they
  carry no warning. This was anticipated before the run.
- Every one of the 72 compared duplicate cases carries the warning, and no case outside the 146
  does.

**Sub-label changes: 465**, exactly the D-1 cases: from "declined, other reason (http_error)" to
"declined, reason matches". Their class stays not eligible.

### Regression 2: the WP1 conformance test (workflow C-post) with the new wheel

**Setup.** A scratch copy of `verification_safeguards_comparison/` (from `1b284cf`) was used, with
`arms/C_post/wheels.json` pointed at the new wheel (`results/regression_conformance/wheels_scratch.json`).
- The environment is the C-post set with the new stofs-mcp wheel. erddap-mcp 0.1.3, ww3-mcp 0.1.3
  and coops-mcp 0.1.1 are the same, and every other package equals `cpost.freeze.txt`.
- WP1's own runner (`run_c_post.py`) produced **18 sessions, all valid**.
- Regrading followed WP1 `run_all.sh` steps 8–9:
  - v1 frozen, amended, A2 sensitivity, A3 and the WP1b tables;
  - v2: 17/17 self-tests pass, and the fairness check passes ("14 changed cells, 0 unexplained").

**Comparison with the committed files** (152 files under `results/`):
- **147 byte-identical**, including every v1 and v2 grade file, every table and the decision
  evidence. **No grade cell differs** under v1 or v2.
- **5 differ:** the C-post answers of N1, N2, R4b, S4 and S5. In each, the only difference is the
  epoch sentence appended to the response text (`texts[0]`, `datum_note`). These are exactly the
  tasks compared against CO-OPS MSL; R4a (NAVD) is unchanged.
- **Caveat detection is not altered:** the same caveat patterns fire, and the decision grades are
  identical (`results/regression_conformance/answer_*.json`).

## Task A: Figure 5 (no result changes)

Written to the untracked `verification_manuscript_facts/figures/` in the main checkout. The
script `fig5_bias_offset_190mm.py` reads the WP5 station tables and the OLS lines from
`results.json`; nothing is recomputed.

**Outputs:** `fig5_bias_offset_190mm_{full,zoom}.pdf`, `_600dpi.png` and `_report.json`.

**Format:**
- 190 × 85 mm, two panels with a shared y axis;
- bold "(a)" and "(b)" labels, and no title;
- palette `#2a78d6` / `#eb6834`, ink `#0b0b0b`.

**Checks:**
- **Series:** 94 / 122 / 114 / 114 points, as required; the two panel (b) series hold the same
  stations.
- **Fonts:** the smallest drawn font is 8.0 pt.
- **Overlaps:** no legend covers a data point, no text covers a data point, and no text lies
  outside the canvas or overlaps another.
- **Zoom version:** every station except 8764044 lies inside the axes. 8764044 is drawn as arrows
  at the left edge, with its offsets and biases in a legend note.

**Array hashes** (SHA-256, in the `_report.json` files):

| version | series | n | x | y |
|---|---|---:|---|---|
| full | 3D v2.1 | 94 | `3e8f4b07c1f116c1…` | `bc382b504837a7d0…` |
| full | 3D v3.1 | 122 | `0206971bbb826910…` | `bbdc1f7e3cb6143e…` |
| full | 3D v3.1 boundary stations | 11 | `07952afb605bc42b…` | `6eaf7523f20cad5f…` |
| full | 2D uncorrected | 114 | `188e9ec134ac9b25…` | `0f1886dd389f82de…` |
| full | 2D corrected | 114 | `188e9ec134ac9b25…` | `8feed8c69715772f…` |

## Task B: one full offline repeat of the WP5 package

**Setup.**
- A copy of `verification_sampled_evaluation/` from `eval/sampled-evaluation` (`c1ace27`, clean
  worktree) was placed in `/mnt/d/ocean-mcp-wp7-scratch/taskB/`, outside the repository.
- Archive bodies and environments are hard links; code was copied; all generated outputs were
  removed.
- `./run_all.sh` ran serially inside `unshare -rn`. The WP5 worktree was not touched.
- Logs are in `results/task_b/`.

**The first attempt (in `/tmp`) was lost** when WSL restarted, during the copy and checksum
phase. The rerun used `/mnt/d` and hard links to avoid that I/O burst.

**Defect 1: `run_all.sh` does not run from a clean tree.**
- Step 4 (A1) failed with `FileNotFoundError: results/a1/datum_consistency.json`, because
  `a1_datum_consistency.py` never creates `results/a1/`.
- Steps 0–3 had completed. All 12 regenerated reference files were byte-identical.
- As the brief requires, the WP5 package was not changed. In the scratch copy only, the empty
  folder was created and steps 4–9 were run with the script's own commands
  (`resume_from_step4.sh`).
- **Proposed fix:** `out_path.parent.mkdir(parents=True, exist_ok=True)` in the A1 script.

**Result.**
- **Every regenerated result file is byte-identical:** 94 of 94, with 0 differing.
- **Sessions:** all 121 MCP sessions are valid.

**Defect 2: six committed files are not produced by `run_all.sh`.**
- Five are `.gz` copies made by hand for git.
- One is `results/study2/station_table_3d_post.md`, the REPORT appendix table, generated by hand.
- `run_all.sh` step 9 therefore reports one unreadable file.
- **Proposed fix:** generate these in `study2_tables.py`, or drop them from `SHA256SUMS`.

## Preservation

- **Branches and worktrees.** No existing branch or worktree changed: every worktree is at its
  previous commit with no tracked changes. `eval/sampled-evaluation` is still `c1ace27` and
  `eval/safeguards-comparison` is still `1b284cf`. The only new branch is `fix/stofs-post-wp5`.
- **Remote and network.** Nothing was pushed, pulled, fetched, merged, rebased, tagged,
  published or uploaded. No network request was made.
