"""DaVinci Resolve export: a real bypassable WB node, not a prose sidecar.

Timeline / working space is DaVinci Wide Gamut + DaVinci Intermediate (D65).
The graph is three serial nodes:

  1. IDT  — camera log → DWG Intermediate (LUT and/or Resolve CST)
  2. WB   — scene-linear Bradford/CAT02 (CCT + tint). Own corrector/LUT/DCTL.
            Bypass this node in Resolve to restore IDT → working space →
            optional Rec.709 ODT.
  3. ODT  — Rec.709 (LUT and/or Resolve CST). Optional / later node.

WB is never baked into the IDT or ODT cubes. Status: implemented (unverified).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .curves import decode_log, nlog_normalized_to_linear
from .gamuts import IDT_PAIRS
from .pipeline import apply_odt_rec709, camera_linear_to_working
from .wb import white_balance_matrix, apply_white_balance
from .working_space import davinci_intermediate_decode, davinci_intermediate_encode

# Resolve Color Space Transform labels (implemented, unverified).
RESOLVE_CST = {
    "arri_logc4_awg4": {
        "input_color_space": "ARRI Wide Gamut 4",
        "input_gamma": "ARRI LogC4",
    },
    "sony_slog3_sgamut3": {
        "input_color_space": "Sony S-Gamut3",
        "input_gamma": "Sony S-Log3",
    },
    "sony_slog3_sgamut3cine": {
        "input_color_space": "Sony S-Gamut3.Cine",
        "input_gamma": "Sony S-Log3",
    },
    "panasonic_vlog_vgamut": {
        "input_color_space": "Panasonic V-Gamut",
        "input_gamma": "Panasonic V-Log",
    },
    "fujifilm_flog2_bt2020": {
        "input_color_space": "Rec.2020",
        "input_gamma": "Fujifilm F-Log2",
    },
    "nikon_nlog_bt2020": {
        "input_color_space": "Rec.2020",
        "input_gamma": "Nikon N-Log",
    },
    "red_log3g10_rwg": {
        "input_color_space": "REDWideGamutRGB",
        "input_gamma": "RED Log3G10",
    },
}


def decode_camera_log_01(log_01, idt_id: str) -> np.ndarray:
    """Decode 0-1 camera log buffers to scene-linear camera RGB.

    Nikon N-Log white-paper ``x`` is a 10-bit code (0-1023). LUT / image
    buffers are 0-1 = code/1023; expand before the curve.
    """
    curve, _gamut = IDT_PAIRS[idt_id]
    log_01 = np.asarray(log_01, dtype=np.float64)
    if curve == "nlog":
        return nlog_normalized_to_linear(log_01)
    return decode_log(curve, log_01)


def _di_encode_lut(lin):
    """DI encode for export LUTs. Clamp below DI black so log2 is defined."""
    lin = np.asarray(lin, dtype=np.float64)
    return davinci_intermediate_encode(np.maximum(lin, -0.0075 + 1e-12))


def idt_to_di(log_01, idt_id: str) -> np.ndarray:
    """IDT node: camera log (0-1) → DaVinci Intermediate (DWG, D65). No WB."""
    cam_lin = decode_camera_log_01(log_01, idt_id)
    work_lin = camera_linear_to_working(cam_lin, idt_id, working="DWG")
    return _di_encode_lut(work_lin)


def wb_in_di(
    di_rgb,
    cct: float,
    tint: float = 0.0,
    method: str = "bradford",
) -> np.ndarray:
    """WB node on a DI timeline: decode DI → linear CAT → encode DI."""
    lin = davinci_intermediate_decode(np.asarray(di_rgb, dtype=np.float64))
    lin = apply_white_balance(
        lin, cct, tint=tint, rgb_space="DWG", method=method
    )
    return _di_encode_lut(lin)


def odt_from_di(di_rgb) -> np.ndarray:
    """ODT node: DaVinci Intermediate → Rec.709 encoded. No WB."""
    lin = davinci_intermediate_decode(np.asarray(di_rgb, dtype=np.float64))
    return apply_odt_rec709(lin, working="DWG")


def _cube_sample_grid(size: int) -> np.ndarray:
    """Adobe/IRIDAS .cube lattice: R fastest, then G, then B. Shape (N, 3)."""
    xs = np.linspace(0.0, 1.0, size)
    b, g, r = np.meshgrid(xs, xs, xs, indexing="ij")
    return np.stack([r, g, b], axis=-1).reshape(-1, 3)


def format_cube(title: str, rgb: np.ndarray, size: int) -> str:
    lines = [
        f'TITLE "{title}"',
        "# LogBridge M1 — implemented (unverified). Not a camera-support claim.",
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    rgb = np.asarray(rgb, dtype=np.float64).reshape(-1, 3)
    for row in rgb:
        lines.append(f"{row[0]:.8f} {row[1]:.8f} {row[2]:.8f}")
    return "\n".join(lines) + "\n"


def idt_cube_bytes(idt_id: str, size: int = 17) -> str:
    grid = _cube_sample_grid(size)
    out = idt_to_di(grid, idt_id)
    return format_cube(
        f"LogBridge IDT {idt_id} → DWG Intermediate (no WB)", out, size
    )


def wb_cube_bytes(
    cct: float, tint: float = 0.0, size: int = 17, method: str = "bradford"
) -> str:
    grid = _cube_sample_grid(size)
    out = wb_in_di(grid, cct, tint=tint, method=method)
    return format_cube(
        f"LogBridge WB Bradford CAT {cct:.0f}K tint {tint} (DI in/out)",
        out,
        size,
    )


def odt_cube_bytes(size: int = 17) -> str:
    grid = _cube_sample_grid(size)
    out = odt_from_di(grid)
    return format_cube(
        "LogBridge ODT DWG Intermediate → Rec.709 (no WB)", out, size
    )


def cdl_slope_offset_power(
    cct: float, tint: float = 0.0, method: str = "bradford"
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ASC CDL SOP for a bypassable Color Corrector.

    Slope is the Bradford RGB CAT applied to (1,1,1) so a Color Corrector
    node maps equal-energy the same way the CAT maps white. Offset 0, power 1.
    The full 3x3 CAT (off-diagonals) is the .cube / .dctl — use those as the
    WB node; the CDL is the same serial slot in CDL form so Resolve can
    bypass a native corrector.
    """
    m = white_balance_matrix(cct, tint=tint, rgb_space="DWG", method=method)
    slope = m @ np.array([1.0, 1.0, 1.0], dtype=np.float64)
    offset = np.zeros(3, dtype=np.float64)
    power = np.ones(3, dtype=np.float64)
    return slope, offset, power


def format_cdl(
    cct: float, tint: float = 0.0, method: str = "bradford", ident: str = "LogBridge_WB"
) -> str:
    slope, offset, power = cdl_slope_offset_power(cct, tint, method)
    def _v(a):
        return f"{a[0]:.10f} {a[1]:.10f} {a[2]:.10f}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ColorDecisionList xmlns="urn:ASC:CDL:v1.01">\n'
        "  <ColorDecision>\n"
        f'    <ColorCorrection id="{ident}">\n'
        "      <SOPNode>\n"
        f"        <Slope>{_v(slope)}</Slope>\n"
        f"        <Offset>{_v(offset)}</Offset>\n"
        f"        <Power>{_v(power)}</Power>\n"
        "      </SOPNode>\n"
        "      <SatNode>\n"
        "        <Saturation>1.0</Saturation>\n"
        "      </SatNode>\n"
        "    </ColorCorrection>\n"
        "  </ColorDecision>\n"
        "</ColorDecisionList>\n"
    )


def format_ccc(
    cct: float, tint: float = 0.0, method: str = "bradford", ident: str = "LogBridge_WB"
) -> str:
    slope, offset, power = cdl_slope_offset_power(cct, tint, method)
    def _v(a):
        return f"{a[0]:.10f} {a[1]:.10f} {a[2]:.10f}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ColorCorrectionCollection xmlns="urn:ASC:CDL:v1.01">\n'
        f'  <ColorCorrection id="{ident}">\n'
        "    <SOPNode>\n"
        f"      <Slope>{_v(slope)}</Slope>\n"
        f"      <Offset>{_v(offset)}</Offset>\n"
        f"      <Power>{_v(power)}</Power>\n"
        "    </SOPNode>\n"
        "    <SatNode>\n"
        "      <Saturation>1.0</Saturation>\n"
        "    </SatNode>\n"
        "  </ColorCorrection>\n"
        "</ColorCorrectionCollection>\n"
    )


def format_dctl(
    cct: float, tint: float = 0.0, method: str = "bradford"
) -> str:
    m = white_balance_matrix(cct, tint=tint, rgb_space="DWG", method=method)
    # Row-major 3x3 in DWG linear.
    els = ", ".join(f"{m[i, j]:.10f}f" for i in range(3) for j in range(3))
    return f"""// LogBridge M1 WB node — scene-linear Bradford/CAT02 in DWG.
// Timeline: DaVinci Wide Gamut / DaVinci Intermediate (D65).
// Bypass this DCTL in Resolve to restore IDT → working space → optional Rec.709 ODT.
// CCT {cct:.0f} K  tint {tint}  method {method}
// Implemented (unverified). Not a camera-support claim.

DEFINE_UI_PARAMS(bypass_wb, Bypass WB, DCTLUI_CHECK_BOX, 0, 0, 1)

__DEVICE__ float di_decode(float x)
{{
    const float A = 0.0075f;
    const float B = 7.0f;
    const float C = 0.07329248f;
    const float M = 10.44426855f;
    const float LOG_CUT = 0.02740668f;
    if (x > LOG_CUT)
        return _exp2f(x / C - B) - A;
    return x / M;
}}

__DEVICE__ float di_encode(float lin)
{{
    const float A = 0.0075f;
    const float B = 7.0f;
    const float C = 0.07329248f;
    const float M = 10.44426855f;
    const float LIN_CUT = 0.00262409f;
    if (lin > LIN_CUT)
        return (_log2f(lin + A) + B) * C;
    return lin * M;
}}

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{{
    if (bypass_wb)
        return make_float3(p_R, p_G, p_B);

    float r = di_decode(p_R);
    float g = di_decode(p_G);
    float b = di_decode(p_B);

    const float m[9] = {{ {els} }};
    float or_ = m[0] * r + m[1] * g + m[2] * b;
    float og  = m[3] * r + m[4] * g + m[5] * b;
    float ob  = m[6] * r + m[7] * g + m[8] * b;

    return make_float3(di_encode(or_), di_encode(og), di_encode(ob));
}}
"""


def format_dot(
    idt_ids: list[str],
    cct: float,
    tint: float,
    include_wb: bool,
) -> str:
    idt_label = ", ".join(idt_ids) if idt_ids else "(per clip CST/LUT)"
    wb_style = "solid" if include_wb else "dashed"
    wb_fill = "lightgrey" if include_wb else "white"
    return f"""digraph LogBridgeResolve {{
  rankdir=LR;
  labelloc="t";
  label="LogBridge M1 Resolve graph — implemented (unverified)";
  node [shape=box, fontname="Helvetica"];

  clip [label="Clip\\ncamera log"];
  idt  [label="IDT\\n{idt_label}\\n01_IDT_<idt>.cube\\nor Resolve CST → DWG Intermediate"];
  wb   [label="WB (bypassable)\\nscene-linear Bradford/CAT02\\n{cct:.0f} K  tint {tint}\\n02_WB.cube / .cdl / .ccc / .dctl", style="filled,{wb_style}", fillcolor="{wb_fill}"];
  odt  [label="Rec.709 ODT (later node)\\n03_ODT_Rec709.cube\\nor CST DWG Intermediate → Rec.709"];
  timeline [shape=oval, label="Timeline\\nDWG Intermediate"];

  clip -> idt -> wb -> odt;
  idt -> timeline [style=dashed, label="working space"];
}}
"""


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_graph_xml(
    idt_ids: list[str],
    cct: float,
    tint: float,
    include_wb: bool,
    method: str = "bradford",
) -> str:
    wb_enabled = "true" if include_wb else "false"
    idt_nodes = []
    for i, idt_id in enumerate(idt_ids):
        cst = RESOLVE_CST.get(idt_id, {})
        ics = _xml_escape(cst.get("input_color_space", idt_id))
        ig = _xml_escape(cst.get("input_gamma", idt_id))
        idt_nodes.append(
            "    "
            f'<IDT idt="{_xml_escape(idt_id)}" file="01_IDT_{idt_id}.cube" '
            f'resolveInputColorSpace="{ics}" resolveInputGamma="{ig}" '
            'resolveOutputColorSpace="DaVinci Wide Gamut" '
            'resolveOutputGamma="DaVinci Intermediate"/>'
        )
    if not idt_nodes:
        idt_nodes.append(
            '    <IDT idt="(user picker)" file="" '
            'resolveOutputColorSpace="DaVinci Wide Gamut" '
            'resolveOutputGamma="DaVinci Intermediate"/>'
        )
    idt_block = "\n".join(idt_nodes)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<LogBridgeResolveGraph version="1" status="implemented (unverified)">
  <WorkingSpace gamut="DaVinci Wide Gamut" encoding="DaVinci Intermediate" white="D65"/>
  <Node index="1" name="IDT" type="LUT_or_CST" bypassable="false">
    <Description>Camera log to DWG Intermediate. No white balance.</Description>
{idt_block}
  </Node>
  <Node index="2" name="WB" type="Corrector" bypassable="true" enabled="{wb_enabled}" method="{_xml_escape(method)}">
    <Description>Scene-linear Bradford/CAT02 (CCT + tint). Bypass this node in Resolve (Color page: disable node 2, or DCTL Bypass WB, or skip 02_WB.cube). Remaining graph is IDT → DWG Intermediate → optional Rec.709 ODT.</Description>
    <CCT>{cct:.4f}</CCT>
    <Tint>{tint:.6f}</Tint>
    <File role="lut">02_WB.cube</File>
    <File role="cdl">02_WB.cdl</File>
    <File role="ccc">02_WB.ccc</File>
    <File role="dctl">02_WB.dctl</File>
  </Node>
  <Node index="3" name="ODT_Rec709" type="LUT_or_CST" bypassable="true" enabled="true">
    <Description>Optional Rec.709 ODT. Not the only deliverable; timeline stays DWG Intermediate when this node is off.</Description>
    <File role="lut">03_ODT_Rec709.cube</File>
    <ResolveCST inputColorSpace="DaVinci Wide Gamut" inputGamma="DaVinci Intermediate" outputColorSpace="Rec.709" outputGamma="Rec.709"/>
  </Node>
</LogBridgeResolveGraph>
"""


def format_readme(
    idt_ids: list[str],
    cct: float,
    tint: float,
    include_wb: bool,
) -> str:
    idt_list = ", ".join(idt_ids) if idt_ids else "(none — assign IDT in Resolve CST)"
    wb_state = "enabled by default" if include_wb else "present but bypassed by default"
    return f"""# LogBridge Resolve export

Status: **implemented (unverified)**. This is not a camera-support claim.

## Graph (serial nodes)

Timeline color management: **DaVinci Wide Gamut / DaVinci Intermediate**, D65.

1. **IDT** — `01_IDT_<idt>.cube` or Color Space Transform
   - Input: camera log / camera gamut (`{idt_list}`)
   - Output: DaVinci Wide Gamut, DaVinci Intermediate
   - Contains **no** white balance.

2. **WB** — own corrector, **{wb_state}**
   - `02_WB.cube` — 3D LUT of the Bradford/CAT02 3×3 in scene-linear DWG, wrapped in DaVinci Intermediate so it sits on the DI timeline.
   - `02_WB.dctl` — same 3×3 as a DCTL (Decode DI → matrix → Encode DI). Checkbox **Bypass WB** inside the DCTL, or disable the node.
   - `02_WB.cdl` / `02_WB.ccc` — ASC CDL Color Corrector for the same serial slot (slope = CAT × (1,1,1); offset 0; power 1). Prefer the cube/DCTL for the full 3×3; the CDL is the bypassable corrector form.
   - CCT {cct:.0f} K, tint {tint}, method Bradford (CAT02 selectable in code). Scene-linear only.

3. **Rec.709 ODT** — `03_ODT_Rec709.cube` or CST
   - Input: DaVinci Wide Gamut / DaVinci Intermediate
   - Output: Rec.709 encoded (BT.709 OETF, no RRT)
   - Contains **no** white balance. Optional later node.

## How to bypass WB in Resolve

Color page, serial node graph:

- Apply **IDT** (node 1: LUT `01_IDT_*.cube`, or CST camera → DWG Intermediate).
- Apply **WB** (node 2: LUT `02_WB.cube`, **or** DCTL `02_WB.dctl`, **or** import `02_WB.cdl` onto a Color Corrector).
- Apply **ODT** (node 3: LUT `03_ODT_Rec709.cube`, or CST DWG Intermediate → Rec.709) if you need a 709 viewing/output node.

To bypass WB: disable node 2 (or tick DCTL **Bypass WB**, or skip the CDL/LUT). The remaining graph is **IDT → working space (DWG Intermediate) → optional Rec.709 ODT**. Camera linear after IDT is uncorrected.

Do not use a single Rec.709 file as the only deliverable. Rec.709 is a later node.

## Files

| File | Role |
| --- | --- |
| `graph.xml` | Machine-readable node graph (bypassable WB) |
| `graph.dot` | Graphviz of the same graph |
| `01_IDT_<idt>.cube` | IDT LUT (no WB) |
| `02_WB.cube` | WB LUT (Bradford CAT, DI-wrapped) |
| `02_WB.cdl` / `02_WB.ccc` | WB as ASC CDL Color Corrector |
| `02_WB.dctl` | WB as DCTL (exact 3×3) |
| `03_ODT_Rec709.cube` | Rec.709 ODT (no WB) |
| `README_RESOLVE.md` | This file |

M1 is a fixed pipeline, not a node editor. Golden grey-card samples are required before any accuracy claim.
"""


def export_resolve_bundle(
    dest,
    *,
    idt_ids: list[str] | None = None,
    cct: float = 6504.0,
    tint: float = 0.0,
    include_wb: bool = True,
    lut_size: int = 17,
    method: str = "bradford",
) -> list[Path]:
    """Write a Resolve-importable graph (XML, DOT, CDL, DCTL, cubes, README)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    idt_ids = list(idt_ids or [])
    # Stable unique order, skip stubs / unknown.
    seen: list[str] = []
    for i in idt_ids:
        if i in IDT_PAIRS and i not in seen:
            seen.append(i)
    idt_ids = seen

    written: list[Path] = []

    def _w(name: str, text: str) -> Path:
        p = dest / name
        p.write_text(text, encoding="utf-8")
        written.append(p)
        return p

    _w("README_RESOLVE.md", format_readme(idt_ids, cct, tint, include_wb))
    _w("graph.xml", format_graph_xml(idt_ids, cct, tint, include_wb, method))
    _w("graph.dot", format_dot(idt_ids, cct, tint, include_wb))
    _w("02_WB.cdl", format_cdl(cct, tint, method))
    _w("02_WB.ccc", format_ccc(cct, tint, method))
    _w("02_WB.dctl", format_dctl(cct, tint, method))
    _w("02_WB.cube", wb_cube_bytes(cct, tint, size=lut_size, method=method))
    _w("03_ODT_Rec709.cube", odt_cube_bytes(size=lut_size))
    for idt_id in idt_ids:
        _w(f"01_IDT_{idt_id}.cube", idt_cube_bytes(idt_id, size=lut_size))
    return written
