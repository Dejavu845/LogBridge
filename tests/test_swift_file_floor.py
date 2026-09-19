"""File-as-text floors for PreviewEngine / ResolveExporter.

MCP contents uploads previously dropped Venice cases and the live LogC4
`if x < 0.0 { return x * s + t }` line. Do not re-emit those files via the
contents API. Local trees are ~1855 / ~1015 lines.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = (
    ROOT / "macos" / "LogBridge" / "LogBridge" / "Preview" / "PreviewEngine.swift"
)
EXPORTER = (
    ROOT / "macos" / "LogBridge" / "LogBridge" / "Export" / "ResolveExporter.swift"
)

PREVIEW_LINE_FLOOR = 1700
EXPORTER_LINE_FLOOR = 900
LOGC4_LIVE = "if x < 0.0 { return x * s + t }"


def test_preview_engine_is_not_an_mcp_stub():
    text = PREVIEW.read_text(encoding="utf-8")
    assert len(text.splitlines()) >= PREVIEW_LINE_FLOOR
    assert "Venice" in text
    assert LOGC4_LIVE in text
    assert "arriLogC4AWG4" in text


def test_resolve_exporter_is_not_an_mcp_stub():
    text = EXPORTER.read_text(encoding="utf-8")
    assert len(text.splitlines()) >= EXPORTER_LINE_FLOOR
    assert "Venice" in text
    assert LOGC4_LIVE in text
    assert "arriLogC4AWG4" in text


def test_ci_guard_mentions_swift_floors():
    script = (ROOT / "scripts" / "ci-guard-tests.sh").read_text(encoding="utf-8")
    assert "PreviewEngine.swift" in script
    assert str(PREVIEW_LINE_FLOOR) in script
    assert "Venice" in script
