#!/usr/bin/env bash
# Cloud Agent / Linux bootstrap. Idempotent. Does not require Xcode.
#
# Installs numpy + pytest + ruff via pyproject extras so
# `python -m pytest -q` and `python -m ruff check color tests scripts` work.
# macOS Xcode / Metal / Finder / real EXR writes are out of scope here.
# CI 绿不等于达芬奇已验证。整段代理，不是全精度成片.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python3.12 >/dev/null 2>&1; then
  PY=python3.12
else
  PY=python3
fi

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Need python3.12 or python3 (>= 3.10). Xcode is not required on Linux." >&2
  exit 1
fi

"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
  || {
    echo "Need Python >= 3.10 (prefer 3.12). Found: $($PY --version 2>&1)" >&2
    exit 1
  }

echo "Resolved interpreter: $PY"
"$PY" -c 'import sys; print(sys.executable); print(sys.version)'

install_pkg() {
  "$PY" -m pip install "$@"
}

"$PY" -m pip install --upgrade pip || true
if ! install_pkg -e ".[test,lint]"; then
  install_pkg --break-system-packages -e ".[test,lint]"
fi

"$PY" - <<'PY'
import numpy
import pytest
import sys

print(
    "LogBridge Linux deps ok:",
    f"python={sys.version.split()[0]}",
    f"executable={sys.executable}",
    f"numpy={numpy.__version__}",
    f"pytest={pytest.__version__}",
)
PY

"$PY" -m ruff --version
