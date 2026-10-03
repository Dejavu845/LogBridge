#!/usr/bin/env python3
"""Fail CI when a UI screenshot is the SwiftUI prohibited placeholder or a blank field.

Placeholder pixels are near pure yellow #FFCC00 and pure red #FF3B30 together.
More than 2% of pixels in those two colors fails the shot. A flat field
(luminance stddev under 1) is a blank native capture. after-write must not
share a file hash with locked.
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

YELLOW = (255, 204, 0)
RED = (255, 59, 48)
CHANNEL_TOL = 8
PLACEHOLDER_FRACTION = 0.02
BLANK_STDDEV = 1.0

STATES = ("empty", "dropped-awaiting", "locked", "after-write")
SIZES = ("1440x900", "1280x800")
APPEARANCES = ("light", "dark")


@dataclass(frozen=True)
class ShotStats:
    yellow_frac: float
    red_frac: float
    stddev: float
    width: int
    height: int


def is_prohibited_placeholder(yellow_frac: float, red_frac: float) -> bool:
    """True when yellow and red are both present and together exceed 2%."""
    return (
        yellow_frac > 0
        and red_frac > 0
        and (yellow_frac + red_frac) > PLACEHOLDER_FRACTION
    )


def is_blank_capture(stddev: float) -> bool:
    return stddev < BLANK_STDDEV


def analyze_image(image: Image.Image) -> ShotStats:
    rgb = image.convert("RGB")
    pixels = np.asarray(rgb, dtype=np.int16)
    flat = pixels.reshape(-1, 3)
    total = int(flat.shape[0])
    if total == 0:
        return ShotStats(0.0, 0.0, 0.0, rgb.size[0], rgb.size[1])
    yellow = np.array(YELLOW, dtype=np.int16)
    red = np.array(RED, dtype=np.int16)
    yellow_frac = float(
        np.count_nonzero(np.max(np.abs(flat - yellow), axis=1) <= CHANNEL_TOL) / total
    )
    red_frac = float(
        np.count_nonzero(np.max(np.abs(flat - red), axis=1) <= CHANNEL_TOL) / total
    )
    luminance = flat.mean(axis=1).astype(np.float64)
    return ShotStats(
        yellow_frac=yellow_frac,
        red_frac=red_frac,
        stddev=float(luminance.std()),
        width=rgb.size[0],
        height=rgb.size[1],
    )


def analyze_path(path: Path) -> ShotStats:
    with Image.open(path) as image:
        return analyze_image(image)


def expected_names() -> list[str]:
    names: list[str] = []
    for state in STATES:
        for size in SIZES:
            for appearance in APPEARANCES:
                names.append(f"{state}-{size}-{appearance}.png")
    return names


def nominal_content_height(name: str) -> int | None:
    """`empty-1440x900-light.png` -> 900. The whole window must be taller than this."""
    stem = name[:-4] if name.endswith(".png") else name
    parts = stem.split("-")
    if len(parts) < 2 or "x" not in parts[-2]:
        return None
    return int(parts[-2].split("x")[1])


def toolbar_region_present(pixel_height: int, content_height: int) -> bool:
    """Title bar / toolbar makes the capture taller than the content view."""
    return pixel_height > content_height


# Used only to decide whether a foreground XCUITest shot actually drew blue.
# Grey pixels do not fail the screenshot checker. Enabled state is isEnabled.
ACCENT_BLUE_MIN = 170
ACCENT_BLUE_PIXELS = 40
BUTTON_REGION_WIDTH = 420


def is_accent_blue(red: int, green: int, blue: int) -> bool:
    return (
        blue >= ACCENT_BLUE_MIN
        and blue >= red + 70
        and blue >= green + 40
    )


def accent_blue_count(image: Image.Image, content_height: int) -> int:
    """Accent-blue pixels in the trailing toolbar band, above the content."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    height, width, _ = rgb.shape
    chrome = height - content_height
    if chrome <= 0 or width <= 0:
        return 0
    span = min(BUTTON_REGION_WIDTH, width)
    region = rgb[:chrome, width - span :]
    red = region[:, :, 0]
    green = region[:, :, 1]
    blue = region[:, :, 2]
    mask = (blue >= ACCENT_BLUE_MIN) & (blue >= red + 70) & (blue >= green + 40)
    return int(np.count_nonzero(mask))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


MIN_BADGE_CONTRAST = 4.5


def _linear_channel(value: float) -> float:
    channel = value / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    red, green, blue = (_linear_channel(float(channel)) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: tuple[float, float, float], background: tuple[float, float, float]) -> float:
    """WCAG contrast of a glyph color against its local background."""
    lighter = relative_luminance(foreground)
    darker = relative_luminance(background)
    if darker > lighter:
        lighter, darker = darker, lighter
    return (lighter + 0.05) / (darker + 0.05)


def measure_badge_contrast(image: Image.Image, appearance: str) -> tuple[float, tuple[int, int, int], tuple[int, int, int]]:
    """Sidebar trailing band: 待选 / 已锁定 glyphs versus the row behind them."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float64)
    height, width, _ = rgb.shape
    side = min(280, max(196, int(width * 0.16)))
    top = int(height * 0.18)
    bottom = int(height * 0.72)
    if bottom <= top or side < 64 or width < side:
        return 0.0, (0, 0, 0), (0, 0, 0)
    band = rgb[top:bottom, side - 56 : side]
    background = np.median(band.reshape(-1, 3), axis=0)
    luminance = band.mean(axis=2)
    mask = np.abs(luminance - float(background.mean())) >= 18
    count = int(np.count_nonzero(mask))
    if count < 12:
        bg = tuple(int(round(channel)) for channel in background)
        return 0.0, (0, 0, 0), bg  # type: ignore[return-value]
    glyphs = band[mask]
    order = np.argsort(glyphs.mean(axis=1))
    # Light: secondary sits lighter than primary. Dark: secondary sits darker.
    if appearance == "dark":
        chosen = glyphs[order[: max(1, count // 3)]]
    else:
        chosen = glyphs[order[-(max(1, count // 3)) :]]
    foreground = np.median(chosen, axis=0)
    fg = tuple(int(round(channel)) for channel in foreground)
    bg = tuple(int(round(channel)) for channel in background)
    return contrast_ratio(fg, bg), fg, bg  # type: ignore[return-value]


def badge_contrast_errors(out: Path) -> list[str]:
    """已锁定 and 待选, one light shot and one dark shot each."""
    errors: list[str] = []
    for state in ("dropped-awaiting", "locked"):
        for appearance in APPEARANCES:
            name = f"{state}-1440x900-{appearance}.png"
            path = out / name
            if not path.is_file():
                errors.append(f"{name}: missing badge contrast shot")
                continue
            with Image.open(path) as image:
                ratio, foreground, background = measure_badge_contrast(image, appearance)
            if ratio < MIN_BADGE_CONTRAST:
                errors.append(
                    f"{name}: badge contrast {ratio:.2f}:1 "
                    f"fg={foreground} bg={background} need {MIN_BADGE_CONTRAST}:1"
                )
    return errors


def check_directory(out: Path) -> list[str]:
    errors: list[str] = []
    if not out.is_dir():
        return [f"missing directory {out}"]
    for name in expected_names():
        path = out / name
        if not path.is_file():
            errors.append(f"missing {name}")
            continue
        stats = analyze_path(path)
        if stats.width < 200 or stats.height < 200:
            errors.append(f"{name}: capture is {stats.width}x{stats.height}")
        if nominal := nominal_content_height(name):
            if not toolbar_region_present(stats.height, nominal):
                errors.append(
                    f"{name}: missing toolbar chrome "
                    f"height {stats.height} is not above content {nominal}"
                )
        if is_prohibited_placeholder(stats.yellow_frac, stats.red_frac):
            errors.append(
                f"{name}: prohibited placeholder "
                f"yellow={stats.yellow_frac:.3%} red={stats.red_frac:.3%}"
            )
        elif is_blank_capture(stats.stddev):
            errors.append(f"{name}: blank native capture stddev={stats.stddev:.3f}")
    for size in SIZES:
        for appearance in APPEARANCES:
            locked = out / f"locked-{size}-{appearance}.png"
            wrote = out / f"after-write-{size}-{appearance}.png"
            if locked.is_file() and wrote.is_file():
                if file_sha256(locked) == file_sha256(wrote):
                    errors.append(f"after-write matches locked for {size} {appearance}")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_ui_screenshots.py OUT_DIR", file=sys.stderr)
        return 2
    # Enabled vs disabled is an isEnabled assertion, not a pixel color.
    # Badge contrast is glyph versus local background, light and dark.
    out = Path(argv[1])
    errors = check_directory(out)
    if os.environ.get("LOGBRIDGE_BADGE_CONTRAST", "1") != "0":
        errors.extend(badge_contrast_errors(out))
    if errors:
        print(f"ui-screenshots: {len(errors)} problem(s)", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"ui-screenshots: {len(expected_names())} shots accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
