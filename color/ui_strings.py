"""Canonical Chinese UI copy loaded from locale/ui_zh.json.

Swift mirrors the same keys in Localization/UICopy.swift.
Edit the JSON (or both sides together); do not scatter one-off
Chinese locks across tests. Banned-word and key-presence tests live
in tests/test_ui_copy.py.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_LOCALE = _ROOT / "locale" / "ui_zh.json"

# Tokens never allowed in user-facing copy (even after negation).
BANNED_USER_COPY = ("支持", "一键", "精准", "成片", "成品")

# Keys that must exist for the primary review path.
REQUIRED_KEYS = (
    "PROCESS_BUTTON",
    "HONEST_PROXY_NOTE",
    "REASON_PICK_LOG_GAMUT",
    "REASON_PICK_PAIRED_IDT",
    "SKIPPED_BUCKET",
    "FAILED_BUCKET",
    "CANCEL_BUTTON",
    "CANCELLED_NOTE",
    "WRITTEN_CHIP",
    "WRITE_FAILED_CHIP",
    "DECODE_FAILED_CHIP",
    "FRAME_MISMATCH_CHIP",
    "DISK_SHORT_STATUS",
    "ADVANCED_DISCLOSURE",
    "REVEAL_IN_FINDER",
    "EMPTY_STATE_STEP_1",
    "EMPTY_STATE_STEP_2",
    "EMPTY_STATE_STEP_3",
)


def locale_path() -> Path:
    return _LOCALE


def load_ui_zh() -> dict[str, str]:
    data = json.loads(_LOCALE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("locale/ui_zh.json must be an object")
    out: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError(f"locale entry must be str→str, got {key!r}")
        out[key] = value
    return out


def require_keys(data: dict[str, str] | None = None) -> dict[str, str]:
    data = load_ui_zh() if data is None else data
    missing = [k for k in REQUIRED_KEYS if k not in data or not data[k].strip()]
    if missing:
        raise KeyError(f"locale/ui_zh.json missing keys: {missing}")
    return data
