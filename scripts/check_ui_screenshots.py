#!/usr/bin/env python3
"""Fail CI when a UI screenshot is the SwiftUI prohibited placeholder or a blank field.

Placeholder pixels are near pure yellow #FFCC00 and pure red #FF3B30 together.
More than 2% of pixels in those two colors fails the shot. A flat field
(luminance stddev under 1) is a blank native capture. after-write must not
share a file hash with locked.
"""

from __future__ import annotations

import hashlib
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    errors = check_directory(Path(argv[1]))
    if errors:
        print(f"ui-screenshots: {len(errors)} problem(s)", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"ui-screenshots: {len(expected_names())} shots accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
