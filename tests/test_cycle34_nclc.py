"""Cycle 34: QuickTime nclc / nclx / colr never lock an IDT."""

from __future__ import annotations

from pathlib import Path

from color.as_shot import _NCLC_KEYS as AS_SHOT_NCLC
from color.detect import NCLC_KEYS, detect_clip, detect_from_metadata

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = (
    ROOT
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Detection"
    / "ClipDetector.swift"
)


def test_nclc_key_set_matches_as_shot():
    assert NCLC_KEYS == frozenset(AS_SHOT_NCLC)
    assert "nclc" in NCLC_KEYS
    assert "nclx" in NCLC_KEYS
    assert "colr" in NCLC_KEYS


def test_nclc_only_metadata_needs_picker():
    d = detect_from_metadata({"nclc": "1-1-1", "quicktime_nclc": "S-Log3"})
    assert d is None or d.idt_id is None
    clip = detect_clip("unknown.mov", metadata={"nclc": "1-1-1", "nclx": "S-Log3"})
    assert clip.idt_id is None
    assert clip.needs_user_picker


def test_nclc_cannot_override_camera_private():
    d = detect_from_metadata(
        {
            "nclc": "1-1-1",
            "arri_mxf_color_space": "ARRI LogC4 / AWG4",
        }
    )
    assert d is not None
    assert d.idt_id == "arri_logc4_awg4"
    assert d.source == "metadata"


def test_swift_discards_nclc():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "discardQuickTimeNCLC" in text
    assert "Do not map nclc" in text
    assert '"nclc"' in text
    assert '"nclx"' in text
    assert '"colr"' in text
