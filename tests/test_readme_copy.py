"""CJK batch.py constants ↔ README/ACCEPTANCE, plus user-visible forbidden phrases.

Many filename/metadata notes are Swift-locked but not spelled in README yet.
Those stay on KNOWN_DESYNC (xfail inventory) — do not "fix" by weakening this
list. Product chips that already appear in the spec must stay there.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "color" / "batch.py"
README = ROOT / "README.md"
ACCEPTANCE = ROOT / "ACCEPTANCE.md"
CJK = re.compile(r"[\u3400-\u9fff]")

# Inventory as of 2026-09-13. Shrink this set by adding the string to README
# or ACCEPTANCE — never by deleting a constant.
KNOWN_DESYNC = {
    "STUB_CHIP",
    "EMPTY_RGB_CHIP",
    "NOTE_DLOG_M",
    "NOTE_SLOG3_NO_GAMUT",
    "NOTE_SLOG3_NO_GAMUT_VENICE",
    "NOTE_CLOG2_NO_GAMUT",
    "NOTE_CLOG3_NO_GAMUT",
    "NOTE_VENICE_PICK",
    "NOTE_FILENAME_SGAMUT3",
    "NOTE_FILENAME_SGAMUT3_CINE",
    "NOTE_FILENAME_LOGC4",
    "NOTE_FILENAME_VLOG",
    "NOTE_FILENAME_FLOG2",
    "NOTE_FILENAME_NLOG",
    "NOTE_FILENAME_LOG3G10",
    "NOTE_FILENAME_APPLE_LOG2",
    "NOTE_FILENAME_LOGC3",
    "NOTE_FILENAME_AWG3",
    "NOTE_FILENAME_CLOG2_CGAMUT",
    "NOTE_FILENAME_CLOG2_BT2020",
    "NOTE_FILENAME_CLOG3_CGAMUT",
    "NOTE_FILENAME_CLOG3_BT2020",
    "NOTE_FILENAME_APPLE_LOG",
    "NOTE_FILENAME_DLOG",
    "NOTE_MODEL_HINT",
    "NOTE_META_ARRI_MXF",
    "NOTE_META_SONY",
    "NOTE_META_SONY_VENICE",
    "NOTE_META_CLOG2_CGAMUT",
    "NOTE_META_CLOG2_BT2020",
    "NOTE_META_CLOG3_CGAMUT",
    "NOTE_META_CLOG3_BT2020",
    "NOTE_META_RED_RMD",
    "NOTE_META_FUJI",
    "NOTE_META_NIKON",
    "NOTE_META_PANA",
    "NOTE_META_APPLE_LOG2",
    "NOTE_META_APPLE_LOG",
    "NOTE_META_DLOG",
    "NOTE_META_LOGC3",
    "WROTE_FILES_NOTE",
    "PREVIEW_STATUS_EMPTY",
    "PREVIEW_STATUS_DECODING",
    "PREVIEW_STATUS_DECODE_FAIL",
    "PREVIEW_STATUS_ODT_CACHE_HIT",
    "PREVIEW_STATUS_PROXY",
    "PREVIEW_STATUS_ODT_OFF",
    "LOCK_STATUS_TEMPLATE",
    "PROCESSED_STATUS_TEMPLATE",
    "FOLDER_PICKER_MESSAGE",
    "PROCESS_DELIVERABLE_NOTE",
    "PROCESS_BUTTON_HELP",
    "PROCESS_BUTTON_HELP_UI",
    "PROCESS_DELIVERABLE_NOTE_UI",
    "FOLDER_PICKER_MESSAGE_UI",
    "PROGRESS_STATUS_HELP",
    "USER_PICKED_IDT_NOTE",
    "ADVANCED_EXPORT_HELP",
    "ADVANCED_DISCLOSURE_HELP",
    "CANCELLED_STATUS_TEMPLATE",
    "WRITE_FAILED_CHIP",
    "GENERIC_PARSE_FAILED",
    "MISSING_YCBCR_TAGS_CHIP",
    "DISK_SHORT_STATUS_TEMPLATE",
    "BATCH_SUMMARY_TEMPLATE",
}


def _cjk_constants() -> dict[str, str]:
    tree = ast.parse(BATCH.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(
            node.value.value, str
        ):
            continue
        if CJK.search(node.value.value):
            out[target.id] = node.value.value
    return out


def test_cjk_batch_constants_in_spec_or_known_desync():
    spec = README.read_text(encoding="utf-8") + "\n" + ACCEPTANCE.read_text(
        encoding="utf-8"
    )
    constants = _cjk_constants()
    unexpected_missing = []
    unexpectedly_present = []
    for name, value in constants.items():
        in_spec = value in spec
        if name in KNOWN_DESYNC:
            if in_spec:
                unexpectedly_present.append(name)
        elif not in_spec:
            unexpected_missing.append(f"{name}: {value[:60]}")
    assert unexpected_missing == [], unexpected_missing
    assert unexpectedly_present == [], (
        "KNOWN_DESYNC entry now appears in README/ACCEPTANCE; drop it: "
        + ", ".join(unexpectedly_present)
    )
    unknown = set(KNOWN_DESYNC) - set(constants)
    assert not unknown, sorted(unknown)


# Exact disclaimer lines. A future Text("一键精准校准，不写日志") must not
# borrow a substring exemption.
_BAN_QUOTE_ALLOWLIST = {
    ROOT
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Views"
    / "SettingsView.swift": (
        "/// 设置页。中文。不写精准 / 一键还原 / 全自动校准。",
        'Text("已实现（未验证）。不写精准 / 一键还原 / 全自动校准。")',
    )
}

_UI_LITERAL = re.compile(
    r"(\.help|navigationTitle|Text|Button|Toggle|Picker|Label|Section|"
    r"Menu|TextField|Alert)\(\s*\""
)
_UI_CTOR = re.compile(
    r"(\.help|navigationTitle|Text|Button|Toggle|Picker|Label|Section|"
    r"Menu|TextField|Alert)\("
)
# Cycle 9 / C7 M4: `let overclaim = "一键精准校准"` then Text(overclaim)
# must not hide the needle from the constructor-only gate.
_ASSIGNED_LITERAL = re.compile(
    r"""\b(?:static\s+)?(?:let|var)\s+[A-Za-z_]\w*\s*(?::[^=]+)?=\s*\""""
)
_ASSIGN_HEAD = re.compile(
    r"""\b(?:static\s+)?(?:let|var)\s+[A-Za-z_]\w*\s*(?::[^=]+)?="""
)
# Continuation of `let x = "一键"` / `Text(` ↵ `"精准校准"` / `"一键" + "还原"`.
_STR_CONT = re.compile(
    r"""^\s*(?:\+\s*)?(?:\"[^\"]*\"\s*(?:\+\s*)*)+;?\s*$"""
)

_OVERCLAIM_NEEDLES = ("一键精准", "一键校准", "一键还原", "全自动校准")


def _joined_quotes(line: str) -> str:
    """`Text("一键" + "精准校准")` has no contiguous needle until quotes join."""
    return "".join(re.findall(r'"([^"]*)"', line))


def _span_joined(lines: list[str], start: int, head_ok) -> str | None:
    """Join quoted fragments on `start` plus up to 7 string-continuation lines."""
    code = lines[start].split("//")[0]
    if not head_ok(code):
        return None
    parts = [_joined_quotes(code)]
    for j in range(start + 1, min(start + 8, len(lines))):
        nxt = lines[j].split("//")[0]
        stripped = nxt.strip()
        if not stripped:
            break
        if _STR_CONT.match(nxt) or (stripped.startswith("+") and '"' in nxt):
            parts.append(_joined_quotes(nxt))
            continue
        break
    return "".join(parts)


def _overclaim_hits(
    text: str, rel: str, allowed: set[str] | None = None
) -> list[str]:
    """Scan Swift (or a synthetic snippet) for banned UI/assignment phrases."""
    allowed = allowed or set()
    hits: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() in allowed:
            continue
        code = line.split("//")[0]
        assign_span = _span_joined(lines, i, _ASSIGN_HEAD.search)
        ctor_span = _span_joined(lines, i, _UI_CTOR.search)
        if assign_span and any(n in assign_span for n in _OVERCLAIM_NEEDLES):
            hits.append(f"{rel}:{i + 1}:{line.strip()}")
            continue
        if ctor_span and any(n in ctor_span for n in _OVERCLAIM_NEEDLES):
            hits.append(f"{rel}:{i + 1}:{line.strip()}")
            continue
        joined = _joined_quotes(line)
        if not any(n in line or n in joined for n in _OVERCLAIM_NEEDLES):
            # Cycle 11: Text(↵ "一键精准校准") — needle on the next line.
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if (
                    _UI_CTOR.search(line)
                    and '"' not in code
                    and any(n in _joined_quotes(nxt) for n in _OVERCLAIM_NEEDLES)
                    and nxt.strip() not in allowed
                ):
                    hits.append(f"{rel}:{i + 2}:{nxt.strip()}")
            continue
        if (
            _UI_LITERAL.search(line)
            or _ASSIGNED_LITERAL.search(line)
            or (_UI_CTOR.search(line) and any(n in joined for n in _OVERCLAIM_NEEDLES))
        ):
            hits.append(f"{rel}:{i + 1}:{line.strip()}")
    return hits


def test_cycle12_assignment_and_ctor_spans_catch_split_overclaims():
    """`let x = "一键"` ↵ `+ "精准校准"` must not hide the needle."""
    cases = (
        'let overclaim = "一键"\n    + "精准校准"\n',
        'let overclaim =\n    "一键精准校准"\n',
        'static let overclaim: String =\n    "一键" + "还原"\n',
        'let overclaim = "一键" +\n    "校准"\n',
        'Text(\n    "一键"\n    + "精准校准"\n)\n',
    )
    for src in cases:
        assert _overclaim_hits(src, "synthetic.swift"), src
    safe = 'let title = "已实现（未验证）"\nText("处理已锁定片段")\n'
    assert _overclaim_hits(safe, "synthetic.swift") == []


def test_user_visible_surfaces_forbid_overclaim_phrases():
    """Do not grep README/ACCEPTANCE — they quote the forbidden words on purpose."""
    swift_root = ROOT / "macos" / "LogBridge" / "LogBridge"
    hits: list[str] = []
    for path in swift_root.rglob("*.swift"):
        allowed = {ln.strip() for ln in _BAN_QUOTE_ALLOWLIST.get(path, ())}
        hits.extend(
            _overclaim_hits(
                path.read_text(encoding="utf-8"),
                str(path.relative_to(ROOT)),
                allowed,
            )
        )
    constants = _cjk_constants()
    for name, value in constants.items():
        for n in _OVERCLAIM_NEEDLES:
            if n in value:
                hits.append(f"color/batch.py:{name}")
        if re.search(r"(?<![未])已验证", value):
            hits.append(f"color/batch.py:{name}:已验证")
    assert hits == [], hits
