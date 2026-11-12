#!/usr/bin/env bash
# Repeat WP5 offline from the archives: no request reaches NOAA or any data host.
#
#   ./run_all.sh                  # everything (sessions take hours)
#   SESSIONS=skip ./run_all.sh    # reuse the archived session transcripts; redo all analysis
#   JOBS=4 ./run_all.sh           # parallel replay sessions (default 4)
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
JOBS="${JOBS:-4}"
WHEEL="$REPO/verification_post_wp1/dist/stofs_mcp-0.3.0-py3-none-any.whl"
WHEEL_SHA=ba4edc2e05a527f33785bc9fcabd0d313bc57ccabed8373e50376462d297be9a
say() { printf '\n== %s\n' "$*"; }

say "0. archive bodies present and unchanged; wheel checksum"
python3 -I - "$V" <<'EOF'
import hashlib, json, sys
from pathlib import Path
V = Path(sys.argv[1]); bad = 0; n = 0
for a in ("models", "coops", "refonly", "meta", "templates"):
    doc = json.loads((V / "data/archive" / a / "index.json").read_text())
    for e in doc["entries"]:
        p = V / "data/archive" / a / e["response"]["body_file"]; n += 1
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != e["response"]["body_sha256"]:
            bad += 1; print("BAD", p)
print(f"{n} archived bodies checked, {bad} bad"); sys.exit(1 if bad else 0)
EOF
echo "$WHEEL_SHA  $WHEEL" | sha256sum -c -

say "1. environments"
mkenv() { local name="$1"; shift; [ -x "$ENVS/$name/bin/python" ] && return 0
  uv venv -q -p "$PY" "$ENVS/$name"; VIRTUAL_ENV="$ENVS/$name" uv pip install -q "$@"; }
mkenv ref -r "$V/environment/ref.freeze.txt"
mkenv vdatum -r "$V/environment/vdatum.freeze.txt"
mkenv harness -r "$V/environment/harness.freeze.txt"
mkenv stofs030post "$WHEEL" -r <(grep -v '^stofs-mcp' "$V/environment/cpost.freeze.txt")
mkenv stofs020 -r "$V/environment/stofs020.freeze.txt"
mkenv coops -r "$V/environment/coops.freeze.txt"
R="$ENVS/ref/bin/python"

say "2. pre-freeze self-test of the reference (previously seen WP1 files)"
"$R" -I "$V/reference/selftest_wp1.py" "$WP1" "$V/run_log/repeat/selftest"

say "3. reference classification: windows (0,49.7], (0,24.8], (0,48]; 2D noanomaly"
A=(--models "$V/data/archive/models" --coops "$V/data/archive/coops" --meta "$V/data/archive/meta" --lists "$V/phase0/coops")
"$R" -I "$V/reference/classify.py" "${A[@]}" --out "$V/reference/results/w49_7"
"$R" -I "$V/reference/classify.py" "${A[@]}" --out "$V/reference/results/w24_8" --lead-end 24.8
"$R" -I "$V/reference/classify.py" "${A[@]}" --out "$V/reference/results/w48" --lead-end 48
"$R" -I "$V/reference/classify.py" "${A[@]}" --out "$V/reference/results/noanomaly_w49_7" --only-variant cwl.noanomaly

say "4. A1 datum consistency (offline VDatum)"
"$ENVS/vdatum/bin/python" -I "$V/reference/a1_datum_consistency.py" --run "$V/results/a1/datum_consistency.json"

say "5. block containment and the pre-session scan (acquisition record)"
python3 -I "$V/phase2/check_blocks.py"
"$R" -I "$V/phase2/scan_requests.py"

if [ "${SESSIONS:-run}" != "skip" ]; then
  say "6. MCP sessions in replay mode (unshare -rn), $JOBS at a time"
  "$R" -I "$V/phase2/build_sessions.py" "$V/reference/results/w49_7/cases.jsonl"
  python3 -I "$V/phase2/run_sessions.py" --jobs "$JOBS"
fi

say "7. Study 1 grading and tables"
"$R" -I "$V/analysis/study1_outcomes.py"
"$R" -I "$V/analysis/study1_report.py"

say "8. Study 2, Study 3, human check"
"$R" -I "$V/analysis/study2_run.py"
"$R" -I "$V/analysis/study2_tables.py"
"$R" -I "$V/analysis/study3_boston.py" > /dev/null
"$R" -I "$V/human_check/draw.py" > /dev/null

say "9. regenerated results against the committed checksums"
sha256sum -c "$V/results/SHA256SUMS" --quiet && echo "all results reproduced"
