#!/usr/bin/env bash
# Repeat WP5 offline from the archives: no request reaches NOAA or any data host.
#
#   ./run_all.sh                  # everything (sessions take hours)
#   SESSIONS=skip ./run_all.sh    # reuse the archived session transcripts; redo all analysis
#   JOBS=1 ./run_all.sh           # replay sessions at a time (default 1)
#
# Inputs: data/archive/{models,coops,refonly,meta,templates} (bodies identified by SHA-256 in each
# index.json), data/raw/vdatum_grids (A1), and the WP1 archive for the pre-freeze self-test.
# Python environments are built from environment/*.freeze.txt if missing (needs PyPI or a uv
# cache, never NOAA). MCP sessions run in replay mode inside `unshare -rn`; any replay miss or
# network attempt makes a session invalid and fails the run.
set -euo pipefail
V="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git -C "$V" worktree list --porcelain | awk '/^worktree /{print $2; exit}')}"
WP1="$REPO/.claude/worktrees/safeguards-comparison/verification_safeguards_comparison/data/archive/base"
ENVS="$V/.envs"
PY="${PYTHON:-$(uv python find 3.13.12)}"
JOBS="${JOBS:-1}"   # serial by default: parallel sessions crashed this host twice
WHEEL="$REPO/verification_post_wp1/dist/stofs_mcp-0.3.0-py3-none-any.whl"
WHEEL_SHA=ba4edc2e05a527f33785bc9fcabd0d313bc57ccabed8373e50376462d297be9a
say() { printf '\n== %s\n' "$*"; }

R="$ENVS/ref/bin/python"   # as set in step 1 of run_all.sh
A=(--models "$V/data/archive/models" --coops "$V/data/archive/coops" --meta "$V/data/archive/meta" --lists "$V/phase0/coops")   # as set in step 3
say "4. A1 datum consistency (offline VDatum)"
"$ENVS/vdatum/bin/python" -I "$V/reference/a1_datum_consistency.py" --run "$V/results/a1/datum_consistency.json"

say "5. block containment and the pre-session scan (acquisition record)"
python3 -I "$V/phase2/check_blocks.py"
"$R" -I "$V/phase2/scan_requests.py"

if [ "${SESSIONS:-run}" != "skip" ]; then
  say "6. MCP sessions in replay mode (unshare -rn), $JOBS at a time"
  "$R" -I "$V/phase2/build_sessions.py" "$V/reference/results/w49_7/cases.jsonl"
  nice -n 19 python3 -I "$V/phase2/run_sessions.py" --jobs "${JOBS}"
fi

say "7. Study 1 grading and tables"
"$R" -I "$V/analysis/study1_outcomes.py"
"$R" -I "$V/analysis/study1_report.py"

say "8. Study 2, Study 3, human check"
"$R" -I "$V/analysis/study2_run.py"
"$R" -I "$V/analysis/study2_tables.py"
"$R" -I "$V/analysis/posthoc_leverage.py" > /dev/null   # post hoc, labelled as such in REPORT.md 2.8
"$R" -I "$V/analysis/study3_boston.py" > /dev/null
"$R" -I "$V/human_check/draw.py" > /dev/null

say "9. regenerated results against the committed checksums"
(cd "$V" && sha256sum -c results/SHA256SUMS --quiet) && echo "all results reproduced"
