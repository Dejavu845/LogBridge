"""Cycle 38: a Venice body name is not an IDT. Gamut still required."""

from __future__ import annotations

from pathlib import Path

from color.detect import (
    can_one_click_process,
    detect_from_model,
    venice_model_needs_picker,
)

DETECTOR = (
    Path(__file__).resolve().parents[1]
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Detection"
    / "ClipDetector.swift"
)


def test_helper_venice_body_needs_picker():
    assert venice_model_needs_picker("Sony VENICE 2") is True
    assert venice_model_needs_picker("venice") is True
    assert venice_model_needs_picker("Alexa 35") is False
    assert venice_model_needs_picker("") is False
    assert venice_model_needs_picker(None) is False


def test_detect_model_venice_never_locks_cine():
    from color.batch import NOTE_VENICE_PICK

    d = detect_from_model("Sony VENICE")
    assert d is not None
    assert d.idt_id is None
    assert d.needs_user_picker
    assert d.venice_detected
    assert d.note == NOTE_VENICE_PICK
    assert can_one_click_process(d) is False


def test_swift_uses_named_gate():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "static func modelNeedsVenicePicker" in text
    body = text.split("func detectModel")[1].split("func locked")[0]
    assert "modelNeedsVenicePicker" in body
    assert "sonySLog3SGamut3Cine" not in body
