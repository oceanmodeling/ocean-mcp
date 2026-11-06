#!/usr/bin/env bash
# Repeat the whole WP1 comparison offline: no request reaches NOAA or any data host.
#
#   ./run_all.sh                 # everything: Phase 0 proof, references, arms A-D, grading
#   UNTIL=ab ./run_all.sh        # stop after arms A and B are graded (no MCP arm is run)
#
# Inputs come only from data/archive (identified by SHA-256 in data/manifest.json).
# Python environments are created from environment/*.freeze.txt if missing; that step
# needs PyPI (or a populated uv cache), never NOAA. All MCP sessions run in replay mode
# inside `unshare -rn` (no network namespace), and a session with any replay miss or
# network attempt is invalid and fails the run.
#
# Variables: REPO (main checkout holding verification_release_readiness/ and the Boston
# worktree; default: first entry of `git worktree list`), ENVS (default .envs/),
# PYTHON (interpreter for new environments; default python3.13 from uv).
set -euo pipefail
V="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git -C "$V" worktree list --porcelain | awk '/^worktree /{print $2; exit}')}"
ENVS="${ENVS:-$V/.envs}"
PYTHON="${PYTHON:-$(uv python find 3.13)}"
BOSTON="$REPO/.claude/worktrees/stofs-v31-boston-v2/verification_stofs_v31_boston"
UNTIL="${UNTIL:-all}"
WHEEL="$REPO/verification_release_readiness/dist/stofs_mcp-0.3.0-py3-none-any.whl"
WHEEL_SHA=29fcb737d21f2782c3219955f6100e8559f80b22230dead4b056e006dc68afdd

say() { printf '\n== %s\n' "$*"; }

say "0. archive bodies present and unchanged"
if ! python3 -I "$V/tools/verify_archive.py" "$V"; then
  echo "Missing NetCDF bodies are restored by: replay/fetch_inputs.py (real files, online) and"
  echo "synthetic/make_synthetic.py (mutations, offline). Then rerun." >&2
  exit 1
fi
echo "$WHEEL_SHA  $WHEEL" | sha256sum -c -

say "1. environments ($ENVS)"
mkenv() {  # name, then extra install arguments
  local name="$1"; shift
  [ -x "$ENVS/$name/bin/python" ] && return 0
  uv venv -q -p "$PYTHON" "$ENVS/$name"
  VIRTUAL_ENV="$ENVS/$name" uv pip install -q "$@"
}
mkenv armab -r "$V/environment/armab.freeze.txt"
mkenv harness -r "$V/environment/harness.freeze.txt"
mkenv stofs030 "$WHEEL" -r <(grep -v '^stofs-mcp' "$V/environment/stofs030.freeze.txt")
mkenv stofs020 -r "$V/environment/stofs020.freeze.txt"
mkenv coops -r "$V/environment/coops.freeze.txt"
mkenv erddap -r "$V/environment/erddap.freeze.txt"
mkenv ww3_012 -r "$V/environment/ww3_012.freeze.txt"
WW3C=$(ls "$REPO"/verification_ww3_history_fix/dist/ww3_mcp-0.1.3-*.whl 2>/dev/null | head -1 || true)
if [ -n "$WW3C" ]; then mkenv ww3_013 "$WW3C"; fi

say "2. Phase 0: Boston replay through MCP, fail-loud checks"
python3 -I "$V/tools/make_phase0_specs.py" "$V" "$ENVS" "$V/run_log/repeat/phase0"
for pair in boston_stofs030:boston_stofs030_replay stofs020_smoke:stofs020_smoke \
            stofs030_failloud:stofs030_failloud ww3_012_failloud:ww3_012_failloud; do
  s="${pair%%:*}"; d="${pair##*:}"
  unshare -rn "$ENVS/harness/bin/python" "$V/replay/run_session.py" \
    "$V/run_log/repeat/phase0/spec_$s.json" "$V/run_log/repeat/phase0/sessions/$d" || true
done
"$ENVS/harness/bin/python" "$V/replay/run_session.py" \
  "$V/run_log/repeat/phase0/spec_erddap_dnsguard.json" "$V/run_log/repeat/phase0/sessions/erddap_dnsguard" || true
python3 -I "$V/phase0/verify_phase0.py" "$V/run_log/repeat" "$BOSTON" > "$V/run_log/repeat/phase0_check.json"
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print('phase0 passed:', r['phase0_passed']); sys.exit(0 if r['phase0_passed'] else 1)" "$V/run_log/repeat/phase0_check.json"

say "3. synthetic mutations, references, grader self-test"
"$ENVS/armab/bin/python" -I "$V/synthetic/make_synthetic.py" "$V" > /dev/null
"$ENVS/armab/bin/python" -I "$V/references/derive_references.py" "$V" "$BOSTON" > /dev/null
python3 -I "$V/references/build_references.py" "$V"
python3 -I "$V/references/amend_references.py" "$V"
python3 -I "$V/grader/test_grader.py" "$V" | tail -1

say "4. arms A and B (no Ocean-MCP package importable)"
"$ENVS/armab/bin/python" -I "$V/arms/A/arm_a.py" "$V" > /dev/null
"$ENVS/armab/bin/python" -I "$V/arms/B/arm_b.py" "$V" > /dev/null
python3 -I "$V/grader/grade.py" "$V" --arms A,B > /dev/null
python3 -I "$V/grader/grade_amended.py" "$V" --arms A,B > /dev/null
[ "$UNTIL" = "ab" ] && { say "stopped after arms A and B (UNTIL=ab)"; exit 0; }

say "5. arms C and D: real MCP stdio sessions, replay, no network"
"$ENVS/harness/bin/python" "$V/arms/C_D/run_mcp_arms.py" "$V" "$REPO" "$ENVS" --arms C,D

say "6. grading, all arms (frozen references, then amended)"
python3 -I "$V/grader/grade.py" "$V" --arms A,B,C,D > /dev/null
python3 -I "$V/grader/grade_amended.py" "$V" --arms A,B,C,D
python3 -I "$V/grader/grade_sensitivity.py" --selftest | tail -1
python3 -I "$V/grader/grade_sensitivity.py" "$V" --arms A,B,C,D
python3 -I "$V/tools/build_report_tables.py" "$V"
say "done; compare with the committed results: git -C \"$V\" diff --stat -- results/"
