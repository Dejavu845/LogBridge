"""Cycle 37: CCT must be camera Kelvin. nclc 1-1-1 is not a color temperature."""

from __future__ import annotations

from pathlib import Path

from color.as_shot import (
    CCT_MAX,
    CCT_MIN,
    cct_in_camera_range,
    pending_as_shot_has_no_guess,
    read_as_shot_wb,
)

DETECTOR = (
    Path(__file__).resolve().parents[1]
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Detection"
    / "ClipDetector.swift"
)


def test_range_matches_swift_parse_cct():
    assert CCT_MIN == 1000.0
    assert CCT_MAX == 25000.0
    text = DETECTOR.read_text(encoding="utf-8")
    chunk = text.split("private static func parseCCT")[1].split("private static func parseTint")[0]
    assert "cct >= 1000" in chunk
    assert "cct <= 25000" in chunk


def test_nclc_triplet_is_not_kelvin():
    assert cct_in_camera_range(1.0) is None
    assert cct_in_camera_range(1.0) not in (5600.0, 6504.0)
    shot = read_as_shot_wb({"cct": 1})
    assert shot.cct is None
    assert pending_as_shot_has_no_guess(shot)


def test_camera_kelvin_still_honored():
    shot = read_as_shot_wb({"cct": 3200})
    assert shot.cct == 3200.0
    assert not shot.pending
