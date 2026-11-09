# WP1: scientific-safeguards comparison (Ocean-MCP)

**Status: complete (Phases 0 to 3).** The results and the proposed manuscript text are in `REPORT.md`.

| Step | Commit |
|---|---|
| Design freeze: tasks, references, grader | `5d84c13` |
| Arms A and B: code and outputs; amendment A1 | `96fd7f8` |
| Phase 2 start: amendment A2 (sensitivity) and the rule-3 validation, before arms C and D | `53d0f3f` |
| Arms C and D, grading, report | `e74f02b` |
| WP1b: amendment A3 (R7, both readings) | `fe1cac5` |
| WP1b: arm C-post (0.3.0 post-fix) sessions and gradings | `03509ee` |
| WP1b: report revision | `45c68df` |
| WP1c: grader v2 (`grader/v2/`), fairness check, v2 tables, report | `3a3ccd3` and the commit after it |

Arms A and B and the gradings run with no Ocean-MCP package importable. Arms C and D are real MCP
stdio sessions in replay mode.

- `DESIGN.md`: the frozen design.
- `references/AMENDMENTS.md`: amendments A1 (a reference bug), A2 (sensitivity) and A3 (R7 reading).
- `grader/v2/CHANGES.md`: grader v2, five documented corrections of the frozen grader v1. v1 and its
  results are unchanged and reported first.
- **WP1b** added arm C-post (`arms/C_post/`, `results/answers/Cpost/`, `results/wp1b_*`). Run
  `UNTIL=wp1 ./run_all.sh` to reproduce only the original WP1 run.

## Layout

| Path | Contents |
|---|---|
| `replay/` | record and replay launcher (`ocean_replay_launcher.py`); MCP session harness; input seeding and fetching |
| `phase0/` | proof that archived Boston results reproduce through a real MCP session in replay mode |
| `data/archive/` | replay archives (`base/`, `synthetic/S1..S5/`): `index.json` and bodies under their SHA-256. NetCDF bodies are not committed |
| `data/manifest.json` | every input: URL, SHA-256, retrieval time, origin |
| `synthetic/` | the controlled mutations S1 to S5 (deterministic) |
| `tasks/` | `tasks.json`: statements, inputs, archive stacks, exact MCP calls for arms C and D |
| `references/` | `references.json` (frozen), `computed_values.json`, the derivation script, amendments |
| `grader/` | `grade.py` (three axes), `adapters.py` (MCP responses to answers), self-tests |
| `arms/` | `A/arm_a.py`, `B/arm_b.py`, `C_D/run_mcp_arms.py`, `common/archive_io.py` |
| `results/` | `answers/<arm>/<task>.json`, `grades_*.{csv,json,md}`, `counts_*.json` |
| `run_log/` | input fetch log, arm logs, session transcripts and HTTP logs, repeat runs |
| `environment/` | `pip freeze` of every environment; `system.txt` |

## Repeat everything offline

```bash
./run_all.sh            # Phase 0, references, arms A to D, grading
UNTIL=ab ./run_all.sh   # stop after arms A and B
```

- `REPO` defaults to the main checkout. It must hold `verification_release_readiness/` (the WP0
  wheel) and the Boston worktree.
- `ENVS` defaults to `.envs/`. Missing environments are built from `environment/*.freeze.txt`. This
  needs PyPI, never NOAA.
- No data request leaves the machine. Sessions run in replay mode inside `unshare -rn`.
- The NetCDF bodies must be present. If they are missing, `replay/fetch_inputs.py` restores the real
  files (online, checksum-verified) and `synthetic/make_synthetic.py` rebuilds the mutations (offline).
