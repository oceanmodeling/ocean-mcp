#!/usr/bin/env bash
# Offline replay of verification/ian_multi_server (Part A).
#
# Checks every archived file and the reused Ian session against their
# SHA-256, re-runs the reference check, the buoy selection, the analysis and
# the figures from the archive, and compares every output with
# results/SHA256SUMS. Exits non-zero on any mismatch. Needs no network:
# analysis uses the standard library; the figures use the pinned plotting set
# from the uv cache (--offline).
set -euo pipefail
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"   # the package sits in verification/
cd "$PKG"
PY="${PYTHON:-python3}"
FIGPY=(uv run --offline --no-project --isolated --managed-python --python 3.13.12
       --with-requirements scripts/requirements-figures.txt python -I)

echo "[1/7] archive checksums (archive/MANIFEST.sha256)"
sha256sum --quiet --strict -c archive/MANIFEST.sha256
echo "[2/7] reused Ian session (read in place, never written)"
echo "cc8b52830f23ca98be0ea932e196accc2775490cb6c55542608f9f6ee4fcf1bd  $ROOT/verification/ian_cross_server/session_record.json" \
  | sha256sum --quiet --strict -c -
echo "[3/7] HDOB format quotations"
"$PY" -I scripts/check_references.py
echo "[4/7] buoy selection"
"$PY" -I scripts/select_buoy.py
echo "[5/7] analysis"
"$PY" -I scripts/analyze_part_a.py
echo "[6/7] figures"
"${FIGPY[@]}" scripts/make_figures.py > /dev/null
echo "[7/7] outputs against results/SHA256SUMS"
sha256sum --quiet --strict -c results/SHA256SUMS
echo "OK: every output matches"
