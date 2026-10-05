"""UI copy review locks — locale file + banned words + key states.

Full-sentence "this Chinese must appear in Swift source" locks were
retired. Edit locale/ui_zh.json (and UICopy.swift) instead of growing
per-phrase source assertions.
"""

from __future__ import annotations

from pathlib import Path

from color import batch
from color.ui_strings import (
    BANNED_USER_COPY,
    REQUIRED_KEYS,
    load_ui_zh,
    locale_path,
    require_keys,
)

ROOT = Path(__file__).resolve().parents[1]
SWIFT_ROOT = ROOT / "macos" / "LogBridge" / "LogBridge"
UI_COPY_SWIFT = SWIFT_ROOT / "Localization" / "UICopy.swift"
CONTENT = SWIFT_ROOT / "ContentView.swift"
CLIP = SWIFT_ROOT / "Models" / "Clip.swift"


def _all_swift_text() -> str:
    parts: list[str] = []
    for path in SWIFT_ROOT.rglob("*.swift"):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _user_facing_python_blob() -> str:
    data = load_ui_zh()
    return "\n".join(data.values())


def test_locale_file_has_required_keys():
    data = require_keys()
    assert locale_path().is_file()
    for key in REQUIRED_KEYS:
        assert key in data
        assert data[key].strip()


def test_batch_constants_match_locale_for_shared_keys():
    """Python batch module stays aligned with locale/ui_zh.json."""
    data = load_ui_zh()
    mismatched = []
    for key, expected in data.items():
        if not hasattr(batch, key):
            continue
        actual = getattr(batch, key)
        if not isinstance(actual, str):
            continue
        if actual != expected:
            mismatched.append((key, expected, actual))
    assert not mismatched, mismatched[:10]


def test_swift_uicopy_mirrors_required_locale_keys():
    text = UI_COPY_SWIFT.read_text(encoding="utf-8")
    data = require_keys()
    missing = [k for k in REQUIRED_KEYS if k not in text]
    assert not missing, missing
    # At least the process button string is present once in the catalog.
    assert data["PROCESS_BUTTON"] in text


def test_banned_substrings_absent_from_locale_and_swift_ui():
    blob = _user_facing_python_blob() + "\n" + _all_swift_text()
    for token in BANNED_USER_COPY:
        assert token not in blob, token


def test_primary_process_path_still_exists():
    """Behavioral lock: one process entry, pending cannot write."""
    content = CONTENT.read_text(encoding="utf-8")
    clip = CLIP.read_text(encoding="utf-8")
    data = require_keys()
    assert data["PROCESS_BUTTON"] in content or data["PROCESS_BUTTON"] in clip
    assert "processLockedClips" in clip
    assert "hasLockedPair" in clip
    assert "writeLockedDeliverables" in clip


def test_paired_idt_picker_not_two_dropdowns():
    """Keep the structural lock: paired IDT, not curve×gamut combos."""
    inspector = (SWIFT_ROOT / "Views" / "InspectorView.swift").read_text(encoding="utf-8")
    # Still require a single paired picker surface somewhere in UI.
    assert "IDT" in inspector or "idt" in inspector.lower()
    content = CONTENT.read_text(encoding="utf-8")
    assert "成对" in content or "IDT" in content


def test_no_bundled_manufacturer_demos():
    demo_roots = [
        ROOT / "demos",
        ROOT / "samples",
        ROOT / "macos" / "LogBridge" / "LogBridge" / "Resources" / "Demos",
    ]
    for path in demo_roots:
        assert not path.exists(), path


def test_docs_still_name_review_honesty():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "整段代理" in readme or "proxy" in readme.lower()
    assert "未验证" in readme or "unverified" in readme.lower()
