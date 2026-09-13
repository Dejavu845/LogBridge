"""Cycle 39: Venice rows are never a silent default."""

from __future__ import annotations

from pathlib import Path

from color.detect import venice_model_needs_picker, venice_rows_allowed

FUTURE = (
    Path(__file__).resolve().parents[1]
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Stubs"
    / "FutureIDTs.swift"
)


def test_venice_silent_default_stays_false():
    text = FUTURE.read_text(encoding="utf-8")
    assert "static func veniceIsSilentDefault() -> Bool { false }" in text
    assert "dLogMIsSupported() -> Bool { false }" in text


def test_venice_rows_need_an_explicit_flag():
    assert venice_rows_allowed(False) is False
    assert venice_model_needs_picker("VENICE") is True
