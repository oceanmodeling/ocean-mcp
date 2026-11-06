# WP1: scientific-safeguards comparison (Ocean-MCP)

**Status: Phase 1 complete (design frozen; arms A and B run and graded). Arms C and D have not been
run on any task.**

| Step | Commit |
|---|---|
| Design freeze: tasks, references, grader | `5d84c13` |
| Arms A and B: code and outputs; amendment A1 | see `git log` (second commit on `eval/safeguards-comparison`) |

- `DESIGN.md`: the frozen design (Phase 0 mechanism, arms, tasks, references and their sources, grading).
- `references/AMENDMENTS.md`: the post-freeze amendment record.

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
