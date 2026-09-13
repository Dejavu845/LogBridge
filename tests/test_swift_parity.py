"""Python↔Swift IDT coverage and matrix/curve locks.

Reads Swift source. Does not execute Swift. No new cameras. Numbers
must match the existing Python tables; do not invent a Venice matrix.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from color.gamuts import IDT_PAIRS, camera_to_aces2065_matrix

ROOT = Path(__file__).resolve().parents[1]
IDT_SWIFT = ROOT / "macos" / "LogBridge" / "LogBridge" / "Models" / "IDT.swift"
PREVIEW = (
    ROOT
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Preview"
    / "PreviewEngine.swift"
)
EXPORTER = (
    ROOT
    / "macos"
    / "LogBridge"
    / "LogBridge"
    / "Export"
    / "ResolveExporter.swift"
)
WB_SWIFT = ROOT / "macos" / "LogBridge" / "LogBridge" / "Color" / "WhiteBalance.swift"


def _idt_cases() -> list[tuple[str, str]]:
    text = IDT_SWIFT.read_text(encoding="utf-8")
    return re.findall(r"case\s+(\w+)\s+=\s+\"([^\"]+)\"", text)


def _switch_body(src: str, func_name: str) -> str:
    marker = f"private static func {func_name}"
    start = src.index(marker)
    rest = src[start:]
    nxt = re.search(r"\n    (private static func |/// |\}\n)", rest[len(marker) :])
    if nxt is None:
        return rest
    return rest[: len(marker) + nxt.start()]


def _case_names_in(body: str) -> set[str]:
    names: set[str] = set()
    for raw in re.findall(r"\.([A-Za-z0-9]+)", body):
        names.add(raw)
    return names


def test_preview_engine_switches_cover_every_idt_case():
    cases = _idt_cases()
    preview = PREVIEW.read_text(encoding="utf-8")
    exporter = EXPORTER.read_text(encoding="utf-8")
    preview_ap0 = _switch_body(preview, "cameraToAP0")
    preview_log = _switch_body(preview, "decodeLog")
    export_ap0 = _switch_body(exporter, "cameraToAP0")
    export_log = _switch_body(exporter, "decodeLog")
    export_cst = exporter
    for name, raw in cases:
        if name.endswith("Stub") or raw.endswith("_stub") or "Stub" in name:
            continue
        for label, body in (
            ("PreviewEngine.cameraToAP0", preview_ap0),
            ("PreviewEngine.decodeLog", preview_log),
            ("ResolveExporter.cameraToAP0", export_ap0),
            ("ResolveExporter.decodeLog", export_log),
        ):
            assert name in _case_names_in(body), f"{name} missing from {label}"
        assert name in _case_names_in(export_cst), f"{name} missing from ResolveExporter"


def test_logc4_decode_has_negative_extension_in_both_swift_files():
    for path in (PREVIEW, EXPORTER):
        text = path.read_text(encoding="utf-8")
        body = _switch_body(text, "decodeLog")
        idx = body.index("arriLogC4AWG4")
        chunk = body[idx : idx + 800]
        assert "x < 0.0" in chunk, f"{path.name} LogC4 missing x < 0.0"
        assert "_LOGC4_S" in chunk or "14.0 * c / b" in chunk


def test_preview_and_exporter_camera_matrices_match_each_other_and_python():
    preview = PREVIEW.read_text(encoding="utf-8")
    exporter = EXPORTER.read_text(encoding="utf-8")
    p_mats = _extract_case_matrices(_switch_body(preview, "cameraToAP0"))
    e_mats = _extract_case_matrices(_switch_body(exporter, "cameraToAP0"))
    assert set(p_mats) == set(e_mats), sorted(set(p_mats) ^ set(e_mats))
    raw_by_case = {name: raw for name, raw in _idt_cases()}
    for case_name, mat in p_mats.items():
        np.testing.assert_allclose(
            mat, e_mats[case_name], atol=1e-12, err_msg=case_name
        )
        raw = raw_by_case[case_name]
        if raw not in IDT_PAIRS:
            continue
        _curve, gamut = IDT_PAIRS[raw]
        py = camera_to_aces2065_matrix(gamut)
        np.testing.assert_allclose(mat, py, atol=1e-9, err_msg=f"{case_name} vs {gamut}")


def test_white_balance_ap0_to_xyz_literal_matches_python():
    text = WB_SWIFT.read_text(encoding="utf-8")
    block = text[text.index("static let ap0ToXYZ") :]
    triples = re.findall(r"SIMD3\(([^)]+)\)", block)
    assert len(triples) >= 3
    swift = np.array(
        [[float(p.strip()) for p in triples[i].split(",")] for i in range(3)],
        dtype=np.float64,
    )
    from color.gamuts import rgb_to_xyz_matrix

    py = rgb_to_xyz_matrix("AP0")
    np.testing.assert_allclose(swift, py, atol=1e-9)


def _extract_case_matrices(body: str) -> dict[str, np.ndarray]:
    """Map Swift case name → 3×3 from the following simd_double3x3(rows:)."""
    out: dict[str, np.ndarray] = {}
    chunks = re.split(r"\n        case ", body)
    for chunk in chunks[1:]:
        header, _, rest = chunk.partition(":")
        if header.strip().startswith("default"):
            continue
        names = re.findall(r"\.([A-Za-z0-9]+)", header)
        triples = re.findall(r"SIMD3\(([^)]+)\)", rest)
        if len(triples) < 3:
            continue
        rows = [[float(p.strip()) for p in triples[i].split(",")] for i in range(3)]
        mat = np.array(rows, dtype=np.float64)
        for name in names:
            out[name] = mat
    return out
