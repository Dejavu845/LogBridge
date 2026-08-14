#!/usr/bin/env python3
"""Generate SPI1D LUTs, SPIMTX matrices, and ocio/config.ocio from color/.

Python curves are the source of truth. Re-run after changing color/curves.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from color.curves import (  # noqa: E402
    flog2_to_linear,
    log3g10_to_linear,
    logc4_to_linear,
    nlog_normalized_to_linear,
    slog3_to_linear,
    vlog_to_linear,
)
from color.gamuts import rgb_to_rgb_matrix, rgb_to_xyz_matrix  # noqa: E402

LUT_DIR = ROOT / "ocio" / "luts"
MTX_DIR = ROOT / "ocio" / "matrices"
CONFIG = ROOT / "ocio" / "config.ocio"
LUT_SIZE = 4096


def write_spi1d(path: Path, values: np.ndarray, from_min=0.0, from_max=1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Version 1",
        f"From {from_min:.10f} {from_max:.10f}",
        f"Length {len(values)}",
        "Components 1",
        "{",
    ]
    for v in values:
        lines.append(f"  {float(v):.10e}")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_spimtx(path: Path, m: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(3):
        rows.append(f"{m[i, 0]:.12f} {m[i, 1]:.12f} {m[i, 2]:.12f} 0")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def ocio_matrix_16(m3: np.ndarray) -> str:
    """Row-major 4x4 for OCIO MatrixTransform."""
    m = np.eye(4)
    m[:3, :3] = m3
    return ", ".join(f"{v:.10f}" for v in m.reshape(-1))


def generate_luts() -> None:
    x = np.linspace(0.0, 1.0, LUT_SIZE)
    write_spi1d(LUT_DIR / "LogC4_to_lin.spi1d", logc4_to_linear(x))
    write_spi1d(LUT_DIR / "SLog3_to_lin.spi1d", slog3_to_linear(x))
    write_spi1d(LUT_DIR / "VLog_to_lin.spi1d", vlog_to_linear(x))
    write_spi1d(LUT_DIR / "FLog2_to_lin.spi1d", flog2_to_linear(x))
    # N-Log LUT is sampled in 0-1 (code/1023); the curve still sees 10-bit codes.
    write_spi1d(LUT_DIR / "NLog_to_lin.spi1d", nlog_normalized_to_linear(x))
    write_spi1d(LUT_DIR / "Log3G10_to_lin.spi1d", log3g10_to_linear(x))

    # Rec.709 OETF LUT over 0-1 linear (preview ODT).
    from color.rec709 import rec709_oetf

    write_spi1d(LUT_DIR / "lin_to_Rec709_oetf.spi1d", rec709_oetf(x))


def generate_matrices() -> None:
    for name in (
        "AWG4",
        "SGamut3",
        "SGamut3Cine",
        "VGamut",
        "BT2020",
        "REDWideGamutRGB",
        "Rec709",
        "DWG",
        "AP1",
    ):
        write_spimtx(MTX_DIR / f"{name}_to_XYZ.spimtx", rgb_to_xyz_matrix(name))
        write_spimtx(
            MTX_DIR / f"{name}_to_DWG.spimtx", rgb_to_rgb_matrix(name, "DWG")
        )
    write_spimtx(MTX_DIR / "DWG_to_Rec709.spimtx", rgb_to_rgb_matrix("DWG", "Rec709"))


def colorspace_idt(name: str, lut: str, matrix16: str, description: str) -> str:
    return f"""  - !<ColorSpace>
    name: {name}
    family: Input/LogBridge
    equalitygroup: ""
    bitdepth: 32f
    description: |
      {description}
      Status: implemented (unverified). Not marked supported.
    isdata: false
    allocation: uniform
    from_scene_reference: !<GroupTransform>
      children:
        - !<MatrixTransform> {{matrix: [{matrix16}], inverse: true}}
        - !<FileTransform> {{src: {lut}, interpolation: linear, inverse: true}}
    to_scene_reference: !<GroupTransform>
      children:
        - !<FileTransform> {{src: {lut}, interpolation: linear}}
        - !<MatrixTransform> {{matrix: [{matrix16}]}}
"""


def write_config() -> None:
    m_awg = ocio_matrix_16(rgb_to_rgb_matrix("AWG4", "DWG"))
    m_sg3 = ocio_matrix_16(rgb_to_rgb_matrix("SGamut3", "DWG"))
    m_sg3c = ocio_matrix_16(rgb_to_rgb_matrix("SGamut3Cine", "DWG"))
    m_vg = ocio_matrix_16(rgb_to_rgb_matrix("VGamut", "DWG"))
    m_2020 = ocio_matrix_16(rgb_to_rgb_matrix("BT2020", "DWG"))
    m_rwg = ocio_matrix_16(rgb_to_rgb_matrix("REDWideGamutRGB", "DWG"))
    m_709 = ocio_matrix_16(rgb_to_rgb_matrix("DWG", "Rec709"))
    m_ap1 = ocio_matrix_16(rgb_to_rgb_matrix("AP1", "DWG"))
    m_xyz = ocio_matrix_16(rgb_to_xyz_matrix("DWG"))

    # Inverse of DWG->Rec709 is Rec709->DWG, already handled by inverse: true
    # on the ODT from_scene_reference.

    text = f"""ocio_profile_version: 2

# LogBridge M1 OCIO config.
# Internal / scene_linear: Linear DaVinci Wide Gamut (D65).
# Alternate grading encoding: DaVinci Intermediate (and ACEScct as a named space).
# Python package color/ is the source of truth; LUTs were generated from it.
# All IDTs: implemented (unverified). Do not mark cameras as supported.

environment: {{}}

search_path: luts:matrices

roles:
  scene_linear: Linear DWG
  color_timing: DaVinci Intermediate
  compositing_log: DaVinci Intermediate
  default: Linear DWG
  data: Raw
  reference: Linear DWG
  rendering: Linear DWG
  color_picking: Rec.709
  rec709: Rec.709
  matte_paint: DaVinci Intermediate
  texture_paint: Linear DWG
  aces_interchange: ACES2065-1
  cie_xyz_d65_interchange: CIE-XYZ-D65

file_rules:
  - !<Rule> {{name: Default, colorspace: default}}

displays:
  Rec.709:
    - !<View> {{name: Rec.709, colorspace: Rec.709}}
  ACEScct:
    - !<View> {{name: ACEScct, colorspace: ACEScct}}

active_displays: [Rec.709]
active_views: [Rec.709]

colorspaces:
  - !<ColorSpace>
    name: Raw
    family: Data
    isdata: true
    allocation: uniform

  - !<ColorSpace>
    name: Linear DWG
    family: Working
    equalitygroup: ""
    bitdepth: 32f
    description: |
      Scene-linear DaVinci Wide Gamut, D65. LogBridge M1 internal linear space.
      White balance (Bradford/CAT02) is applied here, never in log.
    isdata: false
    allocation: lg2
    allocationvars: [-8, 8, 0.00390625]

  - !<ColorSpace>
    name: CIE-XYZ-D65
    family: Working
    bitdepth: 32f
    isdata: false
    allocation: uniform
    to_scene_reference: !<MatrixTransform> {{matrix: [{ocio_matrix_16(np.linalg.inv(rgb_to_xyz_matrix("DWG")))}]}}
    from_scene_reference: !<MatrixTransform> {{matrix: [{m_xyz}]}}

  - !<ColorSpace>
    name: ACES2065-1
    family: ACES
    bitdepth: 32f
    isdata: false
    allocation: lg2
    allocationvars: [-8, 8, 0.00390625]
    description: |
      Placeholder AP0 linear named for the aces_interchange role.
      Convert via CIE-XYZ-D65; AP0 white is ACES white (~D60), not D65.

  - !<ColorSpace>
    name: Linear ACEScg
    family: ACES
    bitdepth: 32f
    isdata: false
    description: Linear AP1. Alternate internal gamut (D60). Requires CAT from D65.
    to_scene_reference: !<MatrixTransform> {{matrix: [{m_ap1}]}}
    from_scene_reference: !<MatrixTransform> {{matrix: [{m_ap1}], inverse: true}}

  - !<ColorSpace>
    name: ACEScct
    family: ACES
    bitdepth: 32f
    isdata: false
    description: |
      ACEScct (AP1 log). Alternate internal encoding.
      Implemented (unverified). Use Linear DWG for scene-linear WB.

  - !<ColorSpace>
    name: DaVinci Intermediate
    family: Working
    bitdepth: 32f
    isdata: false
    description: |
      DaVinci Wide Gamut Intermediate log encoding of Linear DWG.
      18% grey maps to ~0.336043. Implemented (unverified).

  - !<ColorSpace>
    name: Rec.709
    family: Output
    bitdepth: 32f
    isdata: false
    description: |
      Rec.709 primaries + BT.709 OETF. Preview framebuffers MUST be tagged
      Rec.709 (CGColorSpace.itur_709 / Metal layer.colorspace). Never blit
      Rec.709 pixels into an untagged Display P3 surface.
      Simple ODT, no RRT/DRT. Implemented (unverified).
    to_scene_reference: !<GroupTransform>
      children:
        - !<FileTransform> {{src: lin_to_Rec709_oetf.spi1d, interpolation: linear, inverse: true}}
        - !<MatrixTransform> {{matrix: [{m_709}], inverse: true}}
    from_scene_reference: !<GroupTransform>
      children:
        - !<MatrixTransform> {{matrix: [{m_709}]}}
        - !<FileTransform> {{src: lin_to_Rec709_oetf.spi1d, interpolation: linear}}

{colorspace_idt(
    "ARRI LogC4 AWG4",
    "LogC4_to_lin.spi1d",
    m_awg,
    "ARRI LogC4 curve + ARRI Wide Gamut 4. EI-independent. Negatives: linear extension (spec s, t).",
)}
{colorspace_idt(
    "Sony S-Log3 S-Gamut3",
    "SLog3_to_lin.spi1d",
    m_sg3,
    "Sony S-Log3 + S-Gamut3. Do NOT default S-Log3 to S-Gamut3.Cine. User/metadata picks the gamut.",
)}
{colorspace_idt(
    "Sony S-Log3 S-Gamut3.Cine",
    "SLog3_to_lin.spi1d",
    m_sg3c,
    "Sony S-Log3 + S-Gamut3.Cine. Separate IDT; never the implicit S-Log3 default.",
)}
{colorspace_idt(
    "Panasonic V-Log V-Gamut",
    "VLog_to_lin.spi1d",
    m_vg,
    "Panasonic V-Log + V-Gamut (D65).",
)}
{colorspace_idt(
    "Fujifilm F-Log2 BT.2020",
    "FLog2_to_lin.spi1d",
    m_2020,
    "Fujifilm F-Log2 (a=5.555556) + BT.2020 / D65. 18% grey is 400/1023.",
)}
{colorspace_idt(
    "Nikon N-Log BT.2020",
    "NLog_to_lin.spi1d",
    m_2020,
    "Nikon N-Log + BT.2020 / D65. White-paper x is 10-bit code 0-1023. "
    "This LUT is sampled on 0-1 = code/1023 so OCIO buffers stay normalized; "
    "the curve itself is evaluated at x*1023. Do not divide by 1023 in the Python API.",
)}
{colorspace_idt(
    "RED Log3G10 REDWideGamutRGB",
    "Log3G10_to_lin.spi1d",
    m_rwg,
    "RED Log3G10 + REDWideGamutRGB. 18% grey maps to 1/3.",
)}
  # --- Extension-point stubs (M1 does not implement these curves) ---
  - !<ColorSpace>
    name: Canon C-Log2 (stub)
    family: Input/Stub
    bitdepth: 32f
    isdata: false
    description: |
      STUB. Canon C-Log2 has a negative toe. Do not invent a mirrored toe.
      When implementing, use OCIO builtin CURVE - CANON_CLOG2_to_LINEAR
      or the ACES CLF. Not marked supported.

  - !<ColorSpace>
    name: Canon C-Log3 (stub)
    family: Input/Stub
    bitdepth: 32f
    isdata: false
    description: |
      STUB. Use OCIO builtin CURVE - CANON_CLOG3_to_LINEAR or ACES CLF.

  - !<ColorSpace>
    name: Apple Log (stub)
    family: Input/Stub
    bitdepth: 32f
    isdata: false
    description: STUB. Apple Log IDT is out of scope for M1.

  - !<ColorSpace>
    name: DJI D-Log (stub)
    family: Input/Stub
    bitdepth: 32f
    isdata: false
    description: STUB. DJI D-Log IDT is out of scope for M1.
"""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(text, encoding="utf-8")


def main() -> None:
    generate_luts()
    generate_matrices()
    write_config()
    print(f"Wrote LUTs in {LUT_DIR}")
    print(f"Wrote matrices in {MTX_DIR}")
    print(f"Wrote {CONFIG}")


if __name__ == "__main__":
    main()
