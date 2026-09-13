#!/usr/bin/env bash
# Fail CI if the pytest suite has been deleted. Counts test_*.py files (recursive).
# Called from both Linux and macOS jobs via `bash scripts/ci-guard-tests.sh`.
# Executable bit is not required. CI 绿不等于达芬奇已验证。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

test -d tests
n=$(find tests -name 'test_*.py' | wc -l | tr -d '[:space:]')
echo "test modules: ${n}"
test "${n}" -ge 10

# Catch MCP/contents-API rewrites that drop public helpers (Opus B1).
test -f color/batch.py
batch_lines=$(wc -l < color/batch.py | tr -d '[:space:]')
echo "color/batch.py lines: ${batch_lines}"
test "${batch_lines}" -ge 1300
