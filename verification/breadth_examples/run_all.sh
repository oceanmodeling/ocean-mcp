#!/usr/bin/env bash
# Offline replay of verification/breadth_examples (Part B).
#
# Checks every archived file against archive/MANIFEST.sha256, re-runs the
# analysis and the figures from the archive, and compares every output with
# results/SHA256SUMS. Exits non-zero on any mismatch. Needs no network.
#
# B3: this replays the archived vdatum_convert responses. The conversion
# itself cannot be rerun offline: vdatum-mcp fetches its grids over HTTPS.
# B1: until archive/session2_record.json exists, only session 1 is replayed
# and no pairing, statistics or B1 figure is produced.
set -euo pipefail
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"   # the package sits in verification/
cd "$PKG"
PY="${PYTHON:-python3}"
FIGPY=(uv run --offline --no-project --isolated --managed-python --python 3.13.12
       --with-requirements scripts/requirements-figures.txt python -I)

echo "[1/5] archive checksums (archive/MANIFEST.sha256)"
sha256sum --quiet --strict -c archive/MANIFEST.sha256
echo "[2/5] Ian session used for the B3 position and value (read in place)"
echo "cc8b52830f23ca98be0ea932e196accc2775490cb6c55542608f9f6ee4fcf1bd  $ROOT/verification/ian_cross_server/session_record.json" \
  | sha256sum --quiet --strict -c -
echo "[3/5] analysis (B3 replays archived responses; the conversion is not rerun)"
"$PY" -I scripts/analyze_part_b.py
echo "[4/5] figures"
"${FIGPY[@]}" scripts/make_figures.py > /dev/null
echo "[5/5] outputs against results/SHA256SUMS"
sha256sum --quiet --strict -c results/SHA256SUMS
if [ ! -f archive/session2_record.json ]; then
  echo "NOTE: B1 session 2 not archived yet; B1 pairing and figure not produced"
fi
echo "OK: every output matches"
