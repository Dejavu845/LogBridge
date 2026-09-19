"""File-as-text floors for color/batch.py.

Lives in its own module so a SyntaxError in batch.py cannot hide the
assertion (tests/test_engineering_contracts.py imports color.batch at
module scope). Does not import color.*.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "color" / "batch.py"

# Live file is 1350 lines. 1340 leaves 10-line slack for real edits and
# still fails the ~340-line MCP truncation (1006 lines).
BATCH_LINE_FLOOR = 1340


def test_batch_py_is_not_a_truncated_mcp_rewrite():
    """MCP contents uploads previously dropped ~340 lines. Do not re-emit this file."""
    text = BATCH.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) >= BATCH_LINE_FLOOR
    assert "def ycbcr_to_rgb_float" in text
    assert "def estimate_locked_proxy_bytes" in text
    assert "def process_locked_writes" in text
    assert "def dest_has_space" in text


def test_ci_guard_counts_splitlines_not_wc():
    script = (ROOT / "scripts" / "ci-guard-tests.sh").read_text(encoding="utf-8")
    assert "splitlines()" in script
    assert "wc -l < color/batch.py" not in script
    assert str(BATCH_LINE_FLOOR) in script
