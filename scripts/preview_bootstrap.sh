#!/usr/bin/env bash
# Restore gitignored market data from data/seed/historical.tar.xz.
# Safe to run on every start: existing identical files are left untouched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

exec "$PYTHON" "$ROOT/scripts/preview_bootstrap.py"
