# Verification packages

Each folder is a self-contained record of one verification or evaluation of the Ocean-MCP servers:
its inputs (or their SHA-256), the scripts, the results and a report (`REPORT.md`). None of them is
part of a server package, and CI does not run them.

| Folder | What it is | Run |
|---|---|---|
| [`stofs_v31_boston/`](stofs_v31_boston/) | STOFS-2D-Global and STOFS-3D-Atlantic v3.1 at Boston (CO-OPS 8443970): one fixed, archived cycle, independent statistics and the figure | From the repository root: `uv run --project servers/stofs-mcp python verification/stofs_v31_boston/scripts/02b_replay_tools_offline.py` (offline replay). The full sequence is in `REPORT.md`, section "Reproduction". |
| [`ian_cross_server/`](ian_cross_server/) | Hurricane Ian (2022): one client holding two MCP sessions (nhc-mcp and coops-mcp) runs a fixed tool sequence | `python3 -I verification/ian_cross_server/replay_offline.py` (offline, standard library only) |
| [`safeguards_comparison/`](safeguards_comparison/) | 18 data tasks answered four ways (two without Ocean-MCP, two through real MCP sessions in replay mode) and graded against frozen references | `cd verification/safeguards_comparison && ./run_all.sh` |
| [`sampled_evaluation/`](sampled_evaluation/) | Sampled evaluation of the stofs-mcp 0.3.0 safeguards over archived STOFS-2D and STOFS-3D cycles and CO-OPS stations | `cd verification/sampled_evaluation && SESSIONS=skip ./run_all.sh` reuses the archived sessions; without `SESSIONS=skip` every MCP session is replayed, which takes hours |
| [`regression_stofs_0.3.0/`](regression_stofs_0.3.0/) | The stofs-mcp fixes made after the sampled evaluation, their regression checks against the two evaluations, and a full offline repeat of the sampled evaluation | Report and evidence only; see `REPORT.md` |

## Inputs that are not in Git

- Large data bodies (STOFS NetCDF station files, archived CO-OPS responses) are not committed. Each
  is identified by URL and SHA-256 in its package's `manifest.json` or `index.json`.
  `stofs_v31_boston/scripts/00_fetch_inputs.py` and `safeguards_comparison/replay/fetch_inputs.py`
  restore them and check each SHA-256.
- The two evaluation packages install the server wheels they tested. Each `run_all.sh` names the
  wheel files it needs and checks their SHA-256 before using them.

## Layout history

The packages were first committed at the repository root as `verification_<name>/`, and
`regression_stofs_0.3.0/` as `verification_post_wp5/`. They were moved here in one commit that
changed no file content; the next commit fixed the paths that the move affected. Reports,
transcripts and logs written before the move keep the paths of that time. No commit hash changed.
