"""Cycle 35: missing as-shot CCT stays None (never invent 5600/6504)."""

from __future__ import annotations

from color.as_shot import (
    NEVER_GUESS_CCT,
    pending_as_shot_has_no_guess,
    read_as_shot_wb,
)


def test_constants_are_the_forbidden_guesses():
    assert NEVER_GUESS_CCT == (5600.0, 6504.0)


def test_empty_metadata_does_not_guess():
    shot = read_as_shot_wb({})
    assert shot.cct is None
    assert shot.pending
    assert pending_as_shot_has_no_guess(shot)
    assert shot.cct not in NEVER_GUESS_CCT


def test_nclc_cannot_supply_a_guess():
    shot = read_as_shot_wb({"nclc": "1-1-1", "quicktime_nclc": "5600"})
    assert shot.cct is None
    assert pending_as_shot_has_no_guess(shot)


def test_camera_written_5600_is_honored():
    shot = read_as_shot_wb({"cct": 5600})
    assert shot.cct == 5600.0
    assert not shot.pending
    assert pending_as_shot_has_no_guess(shot)
