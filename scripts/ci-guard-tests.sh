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
# Count with splitlines() so a missing final newline cannot disagree with
# tests/test_batch_file_floor.py (wc -l counts newlines, not lines).
test -f color/batch.py
batch_lines=$(python3 -c 'from pathlib import Path; print(len(Path("color/batch.py").read_text(encoding="utf-8").splitlines()))')
echo "color/batch.py lines: ${batch_lines}"
test "${batch_lines}" -ge 1340

# Catch MCP/contents-API rewrites that drop Venice / live LogC4 (Cycle 13).
preview="macos/LogBridge/LogBridge/Preview/PreviewEngine.swift"
exporter="macos/LogBridge/LogBridge/Export/ResolveExporter.swift"
test -f "${preview}"
test -f "${exporter}"
preview_lines=$(python3 -c 'from pathlib import Path; print(len(Path("macos/LogBridge/LogBridge/Preview/PreviewEngine.swift").read_text(encoding="utf-8").splitlines()))')
echo "PreviewEngine.swift lines: ${preview_lines}"
test "${preview_lines}" -ge 1700
python3 -c 'from pathlib import Path
p = Path("macos/LogBridge/LogBridge/Preview/PreviewEngine.swift").read_text(encoding="utf-8")
e = Path("macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(encoding="utf-8")
assert "Venice" in p and "Venice" in e
assert "if x < 0.0 { return x * s + t }" in p
assert "if x < 0.0 { return x * s + t }" in e
'
