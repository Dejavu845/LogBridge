"""Cycle 32: C-Log2 / C-Log3 without a gamut token stay on the picker."""

from __future__ import annotations

from pathlib import Path

from color.detect import (
    can_one_click_process,
    clog2_filename_needs_picker,
    clog3_filename_needs_picker,
    detect_from_filename,
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

CLOG2_BARE = ("A001_CLog2_take.mov", "clip_c-log2.mxf", "CLOG2.mov")
CLOG3_BARE = ("A001_CLog3_take.mov", "clip_c-log3.mxf", "CLOG3.mov")
CLOG2_GAMUT = ("A001_CLog2_CinemaGamut.mov", "clog2_bt2020.mxf", "CLog2_CGamut.mov")
CLOG3_GAMUT = ("A001_CLog3_CinemaGamut.mov", "clog3_rec2020.mxf", "CLog3_CGamut.mov")


def test_helper_bare_clog_needs_picker():
    for name in CLOG2_BARE:
        assert clog2_filename_needs_picker(name) is True, name
        assert clog3_filename_needs_picker(name) is False, name
    for name in CLOG3_BARE:
        assert clog3_filename_needs_picker(name) is True, name
        assert clog2_filename_needs_picker(name) is False, name


def test_helper_gamut_token_does_not_need_picker():
    for name in CLOG2_GAMUT:
        assert clog2_filename_needs_picker(name) is False, name
    for name in CLOG3_GAMUT:
        assert clog3_filename_needs_picker(name) is False, name
    assert clog2_filename_needs_picker("slog3_clip.mov") is False
    assert clog3_filename_needs_picker("") is False


def test_detect_filename_bare_clog_never_locks_cinema():
    from color.batch import NOTE_CLOG2_NO_GAMUT, NOTE_CLOG3_NO_GAMUT

    d2 = detect_from_filename("A001_CLog2_take.mov")
    assert d2 is not None
    assert d2.idt_id is None
    assert d2.needs_user_picker
    assert d2.gamut is None
    assert d2.note == NOTE_CLOG2_NO_GAMUT
    assert can_one_click_process(d2) is False

    d3 = detect_from_filename("A001_CLog3_take.mov")
    assert d3 is not None
    assert d3.idt_id is None
    assert d3.needs_user_picker
    assert d3.note == NOTE_CLOG3_NO_GAMUT
    assert can_one_click_process(d3) is False


def test_detect_filename_clog_gamut_still_locks():
    c2 = detect_from_filename("A001_CLog2_CinemaGamut.mov")
    assert c2 is not None
    assert c2.idt_id == "canon_clog2_cgamut"
    assert c2.needs_user_picker is False

    b2 = detect_from_filename("clog2_bt2020.mxf")
    assert b2 is not None
    assert b2.idt_id == "canon_clog2_bt2020"

    c3 = detect_from_filename("A001_CLog3_CinemaGamut.mov")
    assert c3 is not None
    assert c3.idt_id == "canon_clog3_cgamut"


def test_swift_uses_named_gates():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "static func filenameNeedsCLog2Picker" in text
    assert "static func filenameNeedsCLog3Picker" in text
    body = text.split("func detectFilename")[1].split("func detectModel")[0]
    assert "filenameNeedsCLog2Picker(name)" in body
    assert "filenameNeedsCLog3Picker(name)" in body
