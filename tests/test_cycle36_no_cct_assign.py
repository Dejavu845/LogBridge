"""Cycle 36: Swift as-shot reader never assigns 5600 or 6504."""

from __future__ import annotations

from pathlib import Path

from color.as_shot import NEVER_GUESS_CCT, pending_as_shot_has_no_guess, read_as_shot_wb

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = (
    ROOT
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Detection"
    / "ClipDetector.swift"
)


def _live_swift(text: str) -> str:
    live = []
    for raw in text.splitlines():
        stripped = raw.lstrip()
        if stripped.startswith("//"):
            continue
        live.append(raw.split("//")[0])
    return "\n".join(live)


def test_read_as_shot_body_has_no_guess_literals():
    text = DETECTOR.read_text(encoding="utf-8")
    start = text.find("static func readAsShotWB(from")
    end = text.find("static func parseCCT", start)
    body = _live_swift(text[start:end])
    assert "var cct: Double?" in body
    assert "5600" not in body
    assert "6504" not in body
    for kelvin in NEVER_GUESS_CCT:
        assert str(int(kelvin)) not in body


def test_python_pending_still_unfilled():
    shot = read_as_shot_wb({})
    assert pending_as_shot_has_no_guess(shot)
    assert shot.cct is None
