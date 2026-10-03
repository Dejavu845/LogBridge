#!/usr/bin/env python3
"""Design-grid lint for the LogBridge macOS UI.

Spacing sites are numeric literals in ``.padding(...)``, stack ``spacing:``,
``cornerRadius:``, and ``minLength:``. A site is on the grid when padding,
spacing, and minLength are 0, 4, 8, 12, 16, 24, or 32, and cornerRadius is
4, 6, or 10. Corner radius of 1 or less is a hairline and is on the grid.
``lineWidth`` and frame sizes are not spacing sites, so 1pt strokes are exempt.

Partial opacity (anything other than 0 or 1) may use only two levels.
A grey fill block is a ``.background`` or ``.fill`` of
``Color.primary`` / ``secondary`` / ``gray`` / ``grey`` with ``.opacity``.
``.bar`` and ``Material`` are exempt. Strokes and foreground styles are not fills.

Orange and yellow are emphasis hues. Each use must sit with a comment that
says 警告 or 错误. Accent is the only other emphasis hue.

The before line is the stated 28066d5 review baseline. This script does not
read that commit: shallow CI clones do not have it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "macos" / "LogBridge" / "LogBridge"

SPACING_GRID = {0, 4, 8, 12, 16, 24, 32}
RADIUS_GRID = {4, 6, 10}
WARNING_MARK = ("警告", "错误")

# Stated review baseline for 28066d5. Not recomputed from that commit.
STATED_BEFORE = "non-grid 79/115, hues 3, grey blocks 20, opacity levels 9"

# The only user-visible pair hint. Picker labels may be named even when they
# do not match 选 together with Log/色域.
NEXT_STEP_PAIR_HINT = "先选成对 Log 与色域"
PICKER_LABEL_WHITELIST = (
    "用户选择成对 IDT",
    "— 先选择成对 IDT —",
)


def _swift_files() -> list[Path]:
    return sorted(p for p in UI_ROOT.rglob("*.swift") if p.is_file() and not p.name.startswith("._"))


def _code(line: str) -> str:
    return line.split("//", 1)[0]


def _call_inners(code: str, key: str) -> list[str]:
    found: list[str] = []
    start = 0
    while True:
        index = code.find(key, start)
        if index < 0:
            return found
        depth = 1
        cursor = index + len(key)
        while cursor < len(code) and depth:
            if code[cursor] == "(":
                depth += 1
            elif code[cursor] == ")":
                depth -= 1
            cursor += 1
        found.append(code[index + len(key) : cursor - 1])
        start = cursor


def _numbers(expr: str) -> list[float]:
    return [float(token) for token in re.findall(r"\d+(?:\.\d+)?", expr)]


def _spacing(code: str) -> tuple[int, int]:
    total = 0
    off = 0
    for inner in _call_inners(code, ".padding("):
        for value in _numbers(inner):
            total += 1
            if value not in SPACING_GRID:
                off += 1
    for match in re.finditer(r"(?:spacing|minLength):\s*([^,\n)]+)", code):
        for value in _numbers(match.group(1)):
            total += 1
            if value not in SPACING_GRID:
                off += 1
    for match in re.finditer(r"cornerRadius:\s*([^,\n)]+)", code):
        for value in _numbers(match.group(1)):
            total += 1
            if value not in RADIUS_GRID and value > 1:
                off += 1
    return total, off


def _opacity_levels(code: str) -> set[str]:
    levels: set[str] = set()
    for inner in _call_inners(code, "opacity("):
        for token in re.findall(r"\d+(?:\.\d+)?", inner):
            value = float(token)
            if value not in (0.0, 1.0):
                levels.add(f"{value:g}")
    return levels


def _is_grey_fill(code: str) -> bool:
    if any(token in code for token in (".bar", "Material")):
        return False
    if ".background" not in code and ".fill" not in code:
        return False
    if ".foregroundStyle" in code or ".stroke" in code:
        return False
    return re.search(
        r"Color\.(?:primary|secondary|gray|grey)(?:\.opacity)?",
        code,
    ) is not None and ".opacity" in code


def _hue_hits(code: str) -> list[str]:
    hits: list[str] = []
    if re.search(r"Color\.orange|(?<![\w])\.orange\b", code):
        hits.append("orange")
    if re.search(r"Color\.yellow|(?<![\w])\.yellow\b", code):
        hits.append("yellow")
    return hits


def _commented_warning(lines: list[str], index: int) -> bool:
    window = lines[max(0, index - 6) : index + 1]
    for line in window:
        if "//" not in line:
            continue
        note = line.split("//", 1)[1]
        if any(mark in note for mark in WARNING_MARK):
            return True
    return False


def measure() -> dict[str, object]:
    spacing_total = 0
    spacing_off = 0
    levels: set[str] = set()
    grey = 0
    uncommented: list[str] = []
    commented = 0
    for path in _swift_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, raw in enumerate(lines):
            code = _code(raw)
            total, off = _spacing(code)
            spacing_total += total
            spacing_off += off
            levels |= _opacity_levels(code)
            if _is_grey_fill(code):
                grey += 1
            for hue in _hue_hits(code):
                if _commented_warning(lines, index):
                    commented += 1
                else:
                    uncommented.append(f"{path.name}:{index + 1}:{hue}")
    return {
        "spacing_total": spacing_total,
        "spacing_off": spacing_off,
        "opacity_levels": len(levels),
        "opacity_values": sorted(levels, key=float),
        "grey": grey,
        "commented_warnings": commented,
        "uncommented": uncommented,
    }


def _view_files() -> list[Path]:
    files = sorted(p for p in (UI_ROOT / "Views").rglob("*.swift") if p.is_file() and not p.name.startswith("._"))
    content = UI_ROOT / "ContentView.swift"
    if content.is_file():
        files.append(content)
    return files


def _quoted(code: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r'"((?:[^"\\]|\\.)*)"', code)]


def guidance_hits() -> list[str]:
    """User-visible literals that say 选/选择 and also Log or 色域."""
    hits: list[str] = []
    for path in _view_files():
        for index, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for literal in _quoted(_code(raw)):
                if "选" not in literal:
                    continue
                if "Log" not in literal and "色域" not in literal:
                    continue
                if literal == NEXT_STEP_PAIR_HINT or literal in PICKER_LABEL_WHITELIST:
                    continue
                hits.append(f"{path.name}:{index}:{literal}")
    return hits


def main() -> int:
    stats = measure()
    print(f"ui-metrics: before 28066d5 stated: {STATED_BEFORE}")
    print(
        "ui-metrics: after: "
        f"non-grid {stats['spacing_off']}/{stats['spacing_total']}, "
        f"hues accent+commented warnings {stats['commented_warnings']}, "
        f"grey blocks {stats['grey']}, "
        f"opacity levels {stats['opacity_levels']} ({', '.join(stats['opacity_values'])})"
    )
    problems: list[str] = []
    if stats["spacing_off"] != 0:
        problems.append(f"non-grid spacing {stats['spacing_off']}")
    if stats["opacity_levels"] != 2:
        problems.append(f"opacity levels {stats['opacity_values']}")
    if stats["grey"] > 2:
        problems.append(f"grey fill blocks {stats['grey']}")
    if stats["uncommented"]:
        problems.append("uncommented orange/yellow: " + ", ".join(stats["uncommented"]))
    extra = guidance_hits()
    whitelist = "、".join(f"「{item}」" for item in PICKER_LABEL_WHITELIST)
    print(
        "ui-metrics: guidance allow "
        f"「{NEXT_STEP_PAIR_HINT}」; picker whitelist {whitelist}"
    )
    if extra:
        problems.append("extra pair guidance: " + ", ".join(extra))
    if problems:
        print("ui-metrics: fail", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("ui-metrics: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
