"""Cycle 31: S-Log3 without a gamut token stays on the picker (never silent Cine)."""

from __future__ import annotations

from pathlib import Path

from color.detect import (
    can_one_click_process,
    detect_from_filename,
    slog3_filename_needs_picker,
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

NEEDS_PICKER = (
    "A001_SLog3_take.mov",
    "clip_s-log3.mxf",
    "venice_SLog3_only.mov",
    "SLOG3.mov",
)

HAS_GAMUT = (
    "A001_SLog3_SGamut3.mov",
    "A001_SLog3_SGamut3.Cine.mov",
    "clip_sgamut3cine.mov",
    "s-gamut3_clip.mxf",
)


def test_helper_bare_slog3_needs_picker():
    for name in NEEDS_PICKER:
        assert slog3_filename_needs_picker(name) is True, name


def test_helper_gamut_token_does_not_need_picker():
    for name in HAS_GAMUT:
        assert slog3_filename_needs_picker(name) is False, name
    assert slog3_filename_needs_picker("logc4_clip.mov") is False
    assert slog3_filename_needs_picker("") is False


def test_detect_filename_bare_slog3_never_locks_cine():
    from color.batch import NOTE_SLOG3_NO_GAMUT, NOTE_SLOG3_NO_GAMUT_VENICE

    d = detect_from_filename("A001_SLog3_take.mov")
    assert d is not None
    assert d.idt_id is None
    assert d.needs_user_picker
    assert d.gamut is None
    assert d.note == NOTE_SLOG3_NO_GAMUT
    assert can_one_click_process(d) is False

    v = detect_from_filename("venice_SLog3_only.mov")
    assert v is not None
    assert v.idt_id is None
    assert v.needs_user_picker
    assert v.venice_detected
    assert v.note == NOTE_SLOG3_NO_GAMUT_VENICE
    assert can_one_click_process(v) is False


def test_detect_filename_sgamut3_still_locks():
    d = detect_from_filename("A001_SLog3_SGamut3.mov")
    assert d is not None
    assert d.idt_id == "sony_slog3_sgamut3"
    assert d.needs_user_picker is False


def test_swift_uses_named_gate():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "static func filenameNeedsSLog3Picker" in text
    body = text.split("func detectFilename")[1].split("func detectModel")[0]
    assert "filenameNeedsSLog3Picker(name)" in body
    assert "sonySLog3SGamut3Cine" not in body.split("filenameNeedsSLog3Picker")[1]
