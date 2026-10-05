# UI copy (zh-Hans)

`ui_zh.json` is the canonical Chinese UI string table.

- Python: `color/ui_strings.py` loads it; `color/batch.py` keeps matching
  constants for the write path (synced by `tests/test_ui_copy.py`).
- Swift: `macos/LogBridge/LogBridge/Localization/UICopy.swift` mirrors the
  required keys used by the primary review path.

Edit the JSON and the Swift enum together. Do **not** add new pytest locks
that require a specific Chinese sentence to appear verbatim in Swift
source — keep banned-word checks and key-presence checks only.
