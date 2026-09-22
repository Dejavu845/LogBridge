"""Swift PreviewColor matrices must match Python camera_to_aces2065_matrix.

Parses the hardcoded 3×3 blocks in PreviewEngine.swift and compares them to
the Linux/no-OCIO reference in color/gamuts.py. Catches silent drift between
the write path and the Python source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from color.gamuts import IDT_PAIRS, camera_to_aces2065_matrix

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "macos/LogBridge/LogBridge/Preview/PreviewEngine.swift"

# PreviewColor.cameraToAP0 case labels → Python IDT id (gamut pair).
# Venice reuses the non-Venice matrix (documented fallback).
SWIFT_CASE_TO_IDT = {
    ".arriLogC4AWG4": "arri_logc4_awg4",
    ".sonySLog3SGamut3, .sonySLog3SGamut3Venice": "sony_slog3_sgamut3",
    ".sonySLog3SGamut3Cine, .sonySLog3SGamut3CineVenice": "sony_slog3_sgamut3cine",
    ".panasonicVLogVGamut": "panasonic_vlog_vgamut",
    ".fujiFLog2BT2020, .nikonNLogBT2020": "fujifilm_flog2_bt2020",
    ".redLog3G10RWG": "red_log3g10_rwg",
    ".canonCLog2CGamut, .canonCLog3CGamut": "canon_clog2_cgamut",
    ".canonCLog2BT2020, .canonCLog3BT2020, .appleLogBT2020": "canon_clog2_bt2020",
    ".djiDLogDGamut": "dji_dlog_dgamut",
    ".arriLogC3EI800AWG3": "arri_logc3_ei800_awg3",
    ".appleLog2AWG": "apple_log2_awg",
}


def _parse_swift_matrices(src: str) -> dict[str, np.ndarray]:
    body = src.split("private static func cameraToAP0")[1].split(
        "private static func decodeLog"
    )[0]
    # case .foo…:\n return simd_double3x3(rows: [\n SIMD3(a,b,c),\n ...
    pattern = re.compile(
        r"case\s+([^\n:]+):\s*"
        r"(?://[^\n]*\n\s*)*"
        r"return\s+simd_double3x3\(rows:\s*\[\s*"
        r"SIMD3\(([^)]+)\),\s*"
        r"SIMD3\(([^)]+)\),\s*"
        r"SIMD3\(([^)]+)\)",
        re.MULTILINE,
    )
    out: dict[str, np.ndarray] = {}
    for m in pattern.finditer(body):
        key = " ".join(m.group(1).split())
        rows = []
        for g in m.group(2, 3, 4):
            rows.append([float(x.strip()) for x in g.split(",")])
        out[key] = np.array(rows, dtype=np.float64)
    return out


def test_swift_preview_camera_to_ap0_matches_python_reference():
    src = ENGINE.read_text(encoding="utf-8")
    assert ".sonySLog3SGamut3Venice" in src
    matrices = _parse_swift_matrices(src)
    assert matrices, "no cameraToAP0 matrices parsed from PreviewEngine.swift"

    for case_key, idt_id in SWIFT_CASE_TO_IDT.items():
        assert case_key in matrices, f"missing Swift case {case_key!r}"
        assert idt_id in IDT_PAIRS
        _, gamut = IDT_PAIRS[idt_id]
        expected = camera_to_aces2065_matrix(gamut)
        # Swift stores rows as (R,G,B) out = M * cam; Python uses rgb @ M.T
        # so the 3×3 numbers should match row-wise.
        got = matrices[case_key]
        np.testing.assert_allclose(
            got,
            expected,
            atol=5e-4,
            rtol=0,
            err_msg=f"{case_key} / {idt_id} ({gamut}) drifted from Python reference",
        )


def test_exr_half_roundtrip_preserves_mid_grey(tmp_path: Path):
    from color.exr_write import PIXEL_HALF, read_rgb_exr, write_rgb_exr

    rgb = np.full((4, 6, 3), 0.18, dtype=np.float32)
    path = write_rgb_exr(tmp_path / "grey.exr", rgb)
    attrs = path.read_bytes()
    # chlist first channel pixelType little-endian int32 == 1 (HALF)
    assert b"channels" in attrs
    back = read_rgb_exr(path)
    np.testing.assert_allclose(back, 0.18, rtol=1e-3, atol=1e-3)
    # Spot-check header pixel type via reader path
    from color.exr_write import read_exr_attributes

    ch = read_exr_attributes(path)["channels"][1]
    nul = ch.index(b"\x00")
    import struct

    (ptype,) = struct.unpack_from("<i", ch, nul + 1)
    assert ptype == PIXEL_HALF
