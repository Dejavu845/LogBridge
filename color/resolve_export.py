"""DaVinci Resolve export: a real bypassable WB node, not a prose sidecar.

Standard deliverable: ACEScct timeline or ACES2065-1 EXR / ACES workflow.
Rec.709 is preview only (optional node 3, off by default).
Rec.2100 HLG / PQ are optional ACES Output Transform / BT.2100 nodes
(unverified). No homemade HLG/PQ LUT.

  1. IDT  — camera log → ACES2065-1 → ACEScct (LUT and/or Resolve CST)
  2. WB   — linear AP0 Bradford/CAT02 (CCT + tint). DCTL decodes ACEScct
            to ACES2065-1, applies the AP0 3×3, encodes ACEScct. Same 3×3
            works on ACES2065-1 linear. Disable node 2 = IDT → ACEScct, no bake.
  3. ODT  — Rec.709 preview (LUT and/or Resolve CST). Off by default.

WB is never a CAT on ACEScct-encoded values and is never baked into the
IDT or ODT cubes. Status: implemented (unverified).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .curves import decode_log, nlog_normalized_to_linear
from .gamuts import IDT_PAIRS
from .graph import SerialGraph, graph_from_export_args, odt_node_name
from .odt import (
    CONFIG_ACES_HLG,
    CONFIG_ACES_PQ,
    HDR_ODTS,
    ODT_HLG,
    ODT_OFF,
    ODT_PQ,
    ODT_REC709,
    declared_hdr_styles,
    odt_descriptor,
)
from .pipeline import apply_idt, apply_odt_rec709, camera_linear_to_working
from .wb import white_balance_matrix, apply_white_balance
from .working_space import (
    DEFAULT_WORKING_LINEAR,
    aces2065_to_acescct,
    aces2065_to_ap1,
    acescct_decode,
    acescct_encode,
    acescct_to_aces2065,
    davinci_intermediate_decode,
    davinci_intermediate_encode,
)

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

RESOLVE_OUTPUT_CS = "ACEScct"
RESOLVE_OUTPUT_GAMMA = "ACEScct"
RESOLVE_SCENE_LINEAR = "ACES2065-1"


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


def _acescct_encode_lut(lin_ap1):
    """ACEScct encode for export LUTs. Keep log2 defined for tiny/negative."""
    lin = np.asarray(lin_ap1, dtype=np.float64)
    return acescct_encode(np.maximum(lin, 1e-10))


def idt_to_acescct(log_01, idt_id: str) -> np.ndarray:
    """IDT node: camera log (0-1) → ACEScct. No WB.

    N-Log LUT domain is 0-1 = code/1023; ``apply_idt`` takes 10-bit codes.
    """
    curve, _gamut = IDT_PAIRS[idt_id]
    log = np.asarray(log_01, dtype=np.float64)
    if curve == "nlog":
        log = log * 1023.0
    aces = apply_idt(log, idt_id)
    return aces2065_to_acescct(aces)


def wb_in_aces2065(
    aces_ap0,
    cct: float,
    tint: float = 0.0,
    method: str = "bradford",
) -> np.ndarray:
    """WB on ACES2065-1 scene-linear (AP0). Linear AP0 3×3 CAT."""
    return apply_white_balance(
        np.asarray(aces_ap0, dtype=np.float64),
        cct,
        tint=tint,
        rgb_space="AP0",
        method=method,
    )


def wb_in_acescct(
    acescct_rgb,
    cct: float,
    tint: float = 0.0,
    method: str = "bradford",
) -> np.ndarray:
    """WB node on an ACEScct timeline: decode → AP0 CAT → encode.

    Never applies the CAT to ACEScct-encoded values.
    """
    ap0 = acescct_to_aces2065(np.asarray(acescct_rgb, dtype=np.float64))
    ap0 = wb_in_aces2065(ap0, cct, tint=tint, method=method)
    return _acescct_encode_lut(aces2065_to_ap1(ap0))


def odt_from_acescct(acescct_rgb) -> np.ndarray:
    """ODT node: ACEScct → Rec.709 encoded. No WB."""
    return apply_odt_rec709(acescct_rgb, working="ACEScct")


# --- Optional named-space helpers (DWG Intermediate). Not the default. ---

def _di_encode_lut(lin):
    """DI encode for optional DWG export LUTs."""
    lin = np.asarray(lin, dtype=np.float64)
    return davinci_intermediate_encode(np.maximum(lin, -0.0075 + 1e-12))


def idt_to_di(log_01, idt_id: str) -> np.ndarray:
    """Optional named-space IDT: camera log → DWG Intermediate. Not default."""
    cam_lin = decode_camera_log_01(log_01, idt_id)
    work_lin = camera_linear_to_working(cam_lin, idt_id, working="DWG")
    return _di_encode_lut(work_lin)


def wb_in_di(
    di_rgb,
    cct: float,
    tint: float = 0.0,
    method: str = "bradford",
) -> np.ndarray:
    """Optional named-space WB on a DI timeline. Not the default export."""
    lin = davinci_intermediate_decode(np.asarray(di_rgb, dtype=np.float64))
    lin = apply_white_balance(lin, cct, tint=tint, rgb_space="DWG", method=method)
    return _di_encode_lut(lin)


def odt_from_di(di_rgb) -> np.ndarray:
    """Optional named-space ODT: DaVinci Intermediate → Rec.709. Not default."""
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
    out = idt_to_acescct(grid, idt_id)
    return format_cube(
        f"LogBridge IDT {idt_id} → ACEScct (no WB)", out, size
    )


def wb_cube_bytes(
    cct: float, tint: float = 0.0, size: int = 17, method: str = "bradford"
) -> str:
    grid = _cube_sample_grid(size)
    out = wb_in_acescct(grid, cct, tint=tint, method=method)
    return format_cube(
        f"LogBridge WB AP0 CAT {cct:.0f}K tint {tint} (ACEScct decode→ACES2065-1→encode)",
        out,
        size,
    )


def odt_cube_bytes(size: int = 17) -> str:
    grid = _cube_sample_grid(size)
    out = odt_from_acescct(grid)
    return format_cube(
        "LogBridge ODT ACEScct → Rec.709 (no WB)", out, size
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
    m = white_balance_matrix(
        cct, tint=tint, rgb_space=DEFAULT_WORKING_LINEAR, method=method
    )
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
    m = white_balance_matrix(
        cct, tint=tint, rgb_space=DEFAULT_WORKING_LINEAR, method=method
    )
    els = ", ".join(f"{m[i, j]:.10f}f" for i in range(3) for j in range(3))
    return f"""// LogBridge M1 WB node — scene-linear Bradford/CAT02 in ACES2065-1 (AP0).
// Timeline: ACEScct (ACES workflow). Scene-linear interchange: ACES2065-1.
// Decode ACEScct → AP1 → AP0, apply cat_ap0, AP0 → AP1 → ACEScct.
// Tick input_aces2065 if the clip is already ACES2065-1 linear (skip ACEScct wrap).
// Bypass this DCTL in Resolve to restore IDT → ACEScct, no bake. Rec.709 is preview only.
// CCT {cct:.0f} K  tint {tint}  method {method}
// Implemented (unverified). Not a camera-support claim.

DEFINE_UI_PARAMS(bypass_wb, Bypass WB, DCTLUI_CHECK_BOX, 0, 0, 1)
DEFINE_UI_PARAMS(input_aces2065, Input is ACES2065-1 linear, DCTLUI_CHECK_BOX, 0, 0, 1)

__DEVICE__ float acescct_decode(float x)
{{
    const float lo_s = 10.5402377416545f;
    const float lo_o = 0.0729055341958355f;
    const float y_break = 0.1552511415525113f;
    if (x <= y_break)
        return (x - lo_o) / lo_s;
    return _exp2f(x * 17.52f - 9.72f);
}}

__DEVICE__ float acescct_encode(float lin)
{{
    const float lo_s = 10.5402377416545f;
    const float lo_o = 0.0729055341958355f;
    const float lin_break = 0.0078125f;
    if (lin <= lin_break)
        return lo_s * lin + lo_o;
    float v = lin > 1e-10f ? lin : 1e-10f;
    return (_log2f(v) + 9.72f) / 17.52f;
}}

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{{
    if (bypass_wb)
        return make_float3(p_R, p_G, p_B);

    float r = p_R;
    float g = p_G;
    float b = p_B;
    if (!input_aces2065)
    {{
        // ACEScct → AP1 linear
        r = acescct_decode(p_R);
        g = acescct_decode(p_G);
        b = acescct_decode(p_B);
        // AP1 → ACES2065-1 (AP0)
        const float ap1_to_ap0[9] = {{
            0.6954522414f, 0.1406786965f, 0.1638690622f,
            0.0447945634f, 0.8596711185f, 0.0955343182f,
            -0.0055258826f, 0.0040252103f, 1.0015006723f
        }};
        float ar = ap1_to_ap0[0] * r + ap1_to_ap0[1] * g + ap1_to_ap0[2] * b;
        float ag = ap1_to_ap0[3] * r + ap1_to_ap0[4] * g + ap1_to_ap0[5] * b;
        float ab = ap1_to_ap0[6] * r + ap1_to_ap0[7] * g + ap1_to_ap0[8] * b;
        r = ar; g = ag; b = ab;
    }}

    const float cat_ap0[9] = {{ {els} }};
    float or_ = cat_ap0[0] * r + cat_ap0[1] * g + cat_ap0[2] * b;
    float og  = cat_ap0[3] * r + cat_ap0[4] * g + cat_ap0[5] * b;
    float ob  = cat_ap0[6] * r + cat_ap0[7] * g + cat_ap0[8] * b;

    if (input_aces2065)
        return make_float3(or_, og, ob);

    const float ap0_to_ap1[9] = {{
        1.4514393161f, -0.2365107469f, -0.2149285693f,
        -0.0765537734f, 1.1762296998f, -0.0996759264f,
        0.0083161484f, -0.0060324498f, 0.9977163014f
    }};
    float pr = ap0_to_ap1[0] * or_ + ap0_to_ap1[1] * og + ap0_to_ap1[2] * ob;
    float pg = ap0_to_ap1[3] * or_ + ap0_to_ap1[4] * og + ap0_to_ap1[5] * ob;
    float pb = ap0_to_ap1[6] * or_ + ap0_to_ap1[7] * og + ap0_to_ap1[8] * ob;
    return make_float3(acescct_encode(pr), acescct_encode(pg), acescct_encode(pb));
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
  idt  [label="IDT\\n{idt_label}\\n01_IDT_<idt>.cube\\nor Resolve CST → ACEScct (ACES workflow)"];
  wb   [label="WB (bypassable)\\nscene-linear Bradford/CAT02\\n{cct:.0f} K  tint {tint}\\n02_WB.cube / .cdl / .ccc / .dctl", style="filled,{wb_style}", fillcolor="{wb_fill}"];
  odt  [label="Rec.709 ODT (later node)\\n03_ODT_Rec709.cube\\nor CST ACEScct → Rec.709"];
  timeline [shape=oval, label="Timeline\\nACEScct"];

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
    odt_enabled: bool = False,
    odt: str | None = None,
    graph: SerialGraph | None = None,
) -> str:
    if graph is None:
        graph = graph_from_export_args(
            idt_id=idt_ids[0] if idt_ids else None,
            cct=cct,
            tint=tint,
            include_wb=include_wb,
            odt_enabled=odt_enabled,
            method=method,
            odt=odt,
        )
    wb_enabled = "true" if graph.wb_enabled else "false"
    odt_on = "true" if graph.odt_enabled else "false"
    odt_mode = graph.odt
    odt_name = odt_node_name(odt_mode)
    cct = graph.wb_cct
    tint = graph.wb_tint
    method = graph.wb_method
    idt_nodes = []
    for i, idt_id in enumerate(idt_ids):
        cst = RESOLVE_CST.get(idt_id, {})
        ics = _xml_escape(cst.get("input_color_space", idt_id))
        ig = _xml_escape(cst.get("input_gamma", idt_id))
        idt_nodes.append(
            "    "
            f'<IDT idt="{_xml_escape(idt_id)}" file="01_IDT_{idt_id}.cube" '
            f'resolveInputColorSpace="{ics}" resolveInputGamma="{ig}" '
            'resolveOutputColorSpace="ACEScct" '
            'resolveOutputGamma="ACEScct"/>'
        )
    if not idt_nodes:
        idt_nodes.append(
            '    <IDT idt="(user picker)" file="" '
            'resolveOutputColorSpace="ACEScct" '
            'resolveOutputGamma="ACEScct"/>'
        )
    idt_block = "\n".join(idt_nodes)
    if odt_mode == ODT_HLG:
        styles = declared_hdr_styles(ODT_HLG)
        odt_type = "ACES_OT"
        odt_desc = (
            "Rec.2100 HLG via ACES Output Transform / BT.2100. "
            "Implemented (unverified). Not supported. No homemade HLG curve."
        )
        style_xml = "\n".join(
            f'    <OCIOBuiltin style="{s}"/>' for s in styles
        )
        odt_payload = (
            f"{style_xml}\n"
            f'    <ConfigACES name="{CONFIG_ACES_HLG}"/>\n'
            '    <ResolveCST inputColorSpace="ACEScct" inputGamma="ACEScct" '
            'outputColorSpace="Rec.2100-HLG" outputGamma="Rec.2100 HLG"/>\n'
        )
    elif odt_mode == ODT_PQ:
        styles = declared_hdr_styles(ODT_PQ)
        odt_type = "ACES_OT"
        odt_desc = (
            "Rec.2100 PQ via ACES Output Transform / BT.2100. "
            "Implemented (unverified). Not supported. No homemade PQ curve."
        )
        style_xml = "\n".join(
            f'    <OCIOBuiltin style="{s}"/>' for s in styles
        )
        odt_payload = (
            f"{style_xml}\n"
            f'    <ConfigACES name="{CONFIG_ACES_PQ}"/>\n'
            '    <ResolveCST inputColorSpace="ACEScct" inputGamma="ACEScct" '
            'outputColorSpace="Rec.2100-PQ" outputGamma="Rec.2100 PQ"/>\n'
        )
    else:
        odt_type = "LUT_or_CST"
        odt_desc = (
            "Rec.709 preview ODT only. Not the standard deliverable. "
            "Off = ACEScct deliverable (or ACES2065-1 EXR). No RRT."
        )
        odt_payload = (
            '    <File role="lut">03_ODT_Rec709.cube</File>\n'
            '    <ResolveCST inputColorSpace="ACEScct" inputGamma="ACEScct" '
            'outputColorSpace="Rec.709" outputGamma="Rec.709"/>\n'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<LogBridgeResolveGraph version="1" status="implemented (unverified)">
  <WorkingSpace gamut="AP0" encoding="ACEScct" white="ACES" scene_linear="ACES2065-1"/>
  <Node index="1" name="IDT" type="LUT_or_CST" bypassable="false">
    <Description>Camera log to ACEScct via ACES2065-1. No white balance. ACES workflow. Disable node 2 = IDT → ACEScct, no bake.</Description>
{idt_block}
  </Node>
  <Node index="2" name="WB" type="Corrector" bypassable="true" enabled="{wb_enabled}" method="{_xml_escape(method)}">
    <Description>Linear AP0 Bradford/CAT02 (CCT + tint) in ACES2065-1. Never a CAT on ACEScct-encoded values. Bypass this node in Resolve (Color page: disable node 2, or DCTL Bypass WB, or skip 02_WB.cube). Remaining graph is IDT → ACEScct, no bake.</Description>
    <CCT>{cct:.4f}</CCT>
    <Tint>{tint:.6f}</Tint>
    <File role="lut">02_WB.cube</File>
    <File role="cdl">02_WB.cdl</File>
    <File role="ccc">02_WB.ccc</File>
    <File role="dctl">02_WB.dctl</File>
  </Node>
  <Node index="3" name="{odt_name}" type="{odt_type}" bypassable="true" enabled="{odt_on}" odt="{odt_mode}">
    <Description>{odt_desc}</Description>
{odt_payload}  </Node>
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

Timeline color management: **ACEScct**, ACES workflow. Scene-linear interchange: **ACES2065-1**.
Do not set DaVinci Wide Gamut Intermediate as the default deliverable.

1. **IDT** — `01_IDT_<idt>.cube` or Color Space Transform
   - Input: camera log / camera gamut (`{idt_list}`)
   - Output: ACEScct (via ACES2065-1)
   - Contains **no** white balance.

2. **WB** — own corrector, **{wb_state}**
   - `02_WB.cube` — 3D LUT of the Bradford/CAT02 3×3 in ACES2065-1 (AP0), wrapped in ACEScct so it sits on the ACEScct timeline.
   - `02_WB.dctl` — same 3×3 as a DCTL (Decode ACEScct → matrix → Encode ACEScct). Checkbox **Bypass WB** inside the DCTL, or disable the node.
   - `02_WB.cdl` / `02_WB.ccc` — ASC CDL Color Corrector for the same serial slot (slope = CAT × (1,1,1); offset 0; power 1). Prefer the cube/DCTL for the full 3×3; the CDL is the bypassable corrector form.
   - CCT {cct:.0f} K, tint {tint}, method Bradford (CAT02 selectable in code). Scene-linear only.

3. **ODT** — Off (ACEScct deliverable, default) | Rec.709 preview | Rec.2100 HLG | Rec.2100 PQ
   - Rec.709: `03_ODT_Rec709.cube` or CST. **preview only**, off by default. BT.709 OETF, no RRT.
   - Rec.2100 HLG / PQ: ACES Output Transform / BT.2100 OCIO Builtin (no homemade curve). Implemented (unverified). Not a support claim.
   - Contains **no** white balance. Optional later node.

## How to bypass WB in Resolve

Color page, serial node graph:

- Apply **IDT** (node 1: LUT `01_IDT_*.cube`, or CST camera → ACEScct, ACES workflow).
- Apply **WB** (node 2: LUT `02_WB.cube`, **or** DCTL `02_WB.dctl`, **or** import `02_WB.cdl` onto a Color Corrector).
- Apply **ODT** (node 3: LUT `03_ODT_Rec709.cube`, or CST ACEScct → Rec.709) if you need a 709 viewing/output node.

To bypass WB: disable node 2 (or tick DCTL **Bypass WB**, or skip the CDL/LUT). The remaining graph is **IDT → working space (ACEScct) → optional Rec.709 ODT**. Camera linear after IDT is uncorrected.

Do not use a single Rec.709 file as the only deliverable. Rec.709 is preview only.

## Files

| File | Role |
| --- | --- |
| `graph.xml` | Machine-readable node graph (bypassable WB) |
| `graph.dot` | Graphviz of the same graph |
| `01_IDT_<idt>.cube` | IDT LUT (no WB) |
| `02_WB.cube` | WB LUT (Bradford CAT, ACEScct-wrapped) |
| `02_WB.cdl` / `02_WB.ccc` | WB as ASC CDL Color Corrector |
| `02_WB.dctl` | WB as DCTL (exact 3×3) |
| `03_ODT_Rec709.cube` | Rec.709 ODT (no WB) |
| `README_RESOLVE.md` | This file |

M1 is a serial node graph (IDT → WB → ODT), not a general node editor. Golden grey-card samples are required before any accuracy claim. Implemented (unverified).
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
    odt_enabled: bool = False,
    odt: str | None = None,
    graph: SerialGraph | None = None,
) -> list[Path]:
    """Write a Resolve-importable graph (XML, DOT, CDL, DCTL, cubes, README).

    Bypass flags come from ``graph`` when given (node 2 off = IDT → ACEScct, no bake).
    Default timeline is ACEScct / ACES2065-1. Rec.709 ODT is preview, off by default.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    idt_ids = list(idt_ids or [])
    if graph is not None:
        include_wb = graph.wb_enabled
        cct = graph.wb_cct
        tint = graph.wb_tint
        method = graph.wb_method
        odt_enabled = graph.odt_enabled
        odt = graph.odt
    else:
        graph = graph_from_export_args(
            idt_id=idt_ids[0] if idt_ids else None,
            cct=cct,
            tint=tint,
            include_wb=include_wb,
            odt_enabled=odt_enabled,
            method=method,
            odt=odt,
        )
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
    _w("graph.xml", format_graph_xml(idt_ids, cct, tint, include_wb, method, odt_enabled=odt_enabled, graph=graph))
    _w("graph.dot", format_dot(idt_ids, cct, tint, include_wb))
    _w("02_WB.cdl", format_cdl(cct, tint, method))
    _w("02_WB.ccc", format_ccc(cct, tint, method))
    _w("02_WB.dctl", format_dctl(cct, tint, method))
    _w("02_WB.cube", wb_cube_bytes(cct, tint, size=lut_size, method=method))
    _w("03_ODT_Rec709.cube", odt_cube_bytes(size=lut_size))
    for idt_id in idt_ids:
        _w(f"01_IDT_{idt_id}.cube", idt_cube_bytes(idt_id, size=lut_size))
    return written
