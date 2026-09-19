"""Cycle 33: D-Log M tokens never lock D-Log + D-Gamut."""

from __future__ import annotations

from pathlib import Path

from color.detect import (
    can_one_click_process,
    detect_from_filename,
    detect_from_metadata,
    dlog_m_token_hit,
)

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = (
    ROOT
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Detection"
    / "ClipDetector.swift"
)

STUB_NAMES = (
    "A001_DLogM_take.mov",
    "clip_d-log m.mxf",
    "dlog m_clip.mov",
    "d-logm.mov",
)
DLOG_OK = ("A001_DLog_DGamut.mov", "clip_d-log.mov", "dlog.mov")


def test_helper_dlog_m_tokens():
    for name in STUB_NAMES:
        assert dlog_m_token_hit(name) is True, name
    for name in DLOG_OK:
        assert dlog_m_token_hit(name) is False, name
    assert dlog_m_token_hit("") is False


def test_filename_dlog_m_never_locks_dgamut():
    from color.batch import NOTE_DLOG_M

    d = detect_from_filename("A001_DLogM_take.mov")
    assert d is not None
    assert d.idt_id is None
    assert d.needs_user_picker
    assert d.note == NOTE_DLOG_M
    assert can_one_click_process(d) is False


def test_filename_dlog_still_locks_dgamut():
    d = detect_from_filename("A001_DLog_DGamut.mov")
    assert d is not None
    assert d.idt_id == "dji_dlog_dgamut"
    assert d.needs_user_picker is False


def test_metadata_dlog_m_never_locks():
    from color.batch import NOTE_DLOG_M

    d = detect_from_metadata({"dji_gamma": "D-Log M"})
    assert d is not None
    assert d.idt_id is None
    assert d.note == NOTE_DLOG_M


def test_swift_uses_named_gate():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "static func filenameIsDLogMStub" in text
    body = text.split("func detectFilename")[1].split("func detectModel")[0]
    assert "filenameIsDLogMStub(name)" in body
    assert ".djiDLogMStub" not in body
