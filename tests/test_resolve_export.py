"""Resolve export is a bypassable WB node graph, not a prose sidecar."""

import re
from pathlib import Path

import numpy as np
import pytest

from color.curves import linear_to_logc4, linear_to_slog3
from color.pipeline import process_to_rec709
from color.as_shot import WB_SOURCE_GREY
from color.batch import (
    REASON_PICK_LOG_GAMUT,
    REASON_PICK_PAIRED_IDT,
    RESOLVE_INCOMPLETE_CHIP,
    RESOLVE_REQUIRED_CUBE,
    RESOLVE_REQUIRED_DCTL,
    RESOLVE_REQUIRED_NAMES,
    RESOLVE_REQUIRED_README,
    RESOLVE_REQUIRED_XML,
    WRITTEN_CHIP,
    BatchClip,
    verify_resolve_bundle,
)
from color.graph import SerialGraph
from color.resolve_export import (
    EXPORT_NOTE_IN_CAMERA,
    EXPORT_NOTE_ODT,
    EXPORT_NOTE_REC709,
    EXPORT_NOTE_WB_BYPASS,
    EXPORT_NOTE_WB_OFF,
    GRAPH_DOT_CLIP_LABEL,
    GRAPH_DOT_EXP_FILE,
    GRAPH_DOT_EXP_HEAD,
    GRAPH_DOT_IDT_THIRD,
    GRAPH_DOT_ODT_HEAD,
    GRAPH_DOT_TIMELINE_LABEL,
    GRAPH_DOT_WB_FILE,
    GRAPH_DOT_WB_HEAD,
    GRAPH_DOT_WB_LINE,
    GRAPH_DOT_WORKING_SPACE,
    GRAPH_EXP_XML_DESC,
    GRAPH_IDT_XML_DESC,
    GRAPH_ODT_USER,
    GRAPH_ODT_XML_DESC,
    GRAPH_WB_SUMMARY,
    GRAPH_WB_XML_DESC,
    REC709_CUBE_COMMENT,
    REC709_CUBE_TITLE,
    REC709_PREVIEW_LABEL,
    RESOLVE_README_HONESTY,
    cdl_slope_offset_power,
    export_locked_resolve_bundle,
    export_note,
    export_resolve_bundle,
    format_ccc,
    format_cdl,
    format_dctl,
    format_dot,
    format_graph_xml,
    format_readme,
    idt_to_acescct,
    odt_cube_bytes,
    odt_from_acescct,
    wb_cube_bytes,
    wb_in_aces2065,
    wb_in_acescct,
)
from color.wb import apply_white_balance
from color.working_space import (
    ACESCCT_18_PERCENT,
    aces2065_to_acescct,
    acescct_to_aces2065,
)


def test_idt_acescct_18_percent_logc4():
    log = np.full(3, float(linear_to_logc4(0.18)))
    enc = idt_to_acescct(log, "arri_logc4_awg4")
    np.testing.assert_allclose(enc, ACESCCT_18_PERCENT, atol=5e-5)
    assert enc[0] == pytest.approx(enc[1], rel=1e-5)


def test_bypass_wb_idt_then_odt_matches_pipeline():
    log = np.full(3, float(linear_to_slog3(0.18)))
    enc = idt_to_acescct(log, "sony_slog3_sgamut3")
    rec = odt_from_acescct(enc)
    direct = process_to_rec709(log, "sony_slog3_sgamut3", apply_wb=False)
    np.testing.assert_allclose(rec, direct, atol=1e-6)
    assert rec[0] == pytest.approx(rec[1], rel=1e-5)


def test_wb_node_identity_at_d65_not_at_tungsten():
    grey = np.full(3, ACESCCT_18_PERCENT)
    a = wb_in_acescct(grey, 6504.0)
    np.testing.assert_allclose(a, grey, atol=2e-3)
    b = wb_in_acescct(grey, 3200.0)
    assert not np.allclose(b, grey, atol=1e-3)


def test_odt_has_no_wb_baked():
    """ODT of tungsten-shifted ACEScct grey is not the ODT of D65 grey — WB is separate."""
    grey = np.full(3, ACESCCT_18_PERCENT)
    shifted = wb_in_acescct(grey, 3200.0)
    assert not np.allclose(odt_from_acescct(shifted), odt_from_acescct(grey), atol=1e-3)


def test_cdl_slope_near_identity_at_6504k():
    slope, offset, power = cdl_slope_offset_power(6504.0)
    np.testing.assert_allclose(slope, 1.0, atol=5e-3)
    np.testing.assert_allclose(offset, 0.0, atol=0)
    np.testing.assert_allclose(power, 1.0, atol=0)


def test_cdl_slope_moves_at_3200k():
    s65, _, _ = cdl_slope_offset_power(6504.0)
    s32, _, _ = cdl_slope_offset_power(3200.0)
    assert not np.allclose(s32, s65, atol=1e-3)


def test_export_bundle_writes_graph_not_sidecar_only(tmp_path: Path):
    written = export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4", "sony_slog3_sgamut3"],
        cct=3200.0,
        tint=0.5,
        include_wb=True,
        lut_size=5,
    )
    names = {p.name for p in written}
    assert "README_RESOLVE.md" in names
    assert "graph.xml" in names
    assert "graph.dot" in names
    assert "02_Exposure.cube" in names
    assert "02_Exposure.dctl" in names
    assert "03_WB.cdl" in names
    assert "03_WB.ccc" in names
    assert "03_WB.dctl" in names
    assert "03_WB.cube" in names
    assert "04_ODT_Rec709.cube" in names
    assert "01_IDT_arri_logc4_awg4.cube" in names
    assert "01_IDT_sony_slog3_sgamut3.cube" in names
    assert len(written) >= 8


def test_xml_wb_node_is_bypassable(tmp_path: Path):
    export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], include_wb=True, lut_size=5
    )
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    assert 'name="WB"' in xml
    assert 'bypassable="true"' in xml
    assert 'method="bradford"' in xml
    assert "ACEScct" in xml
    assert "ACES2065-1" in xml
    assert "03_WB.cube" in xml
    assert "03_WB.cdl" in xml
    off = format_graph_xml(["arri_logc4_awg4"], 5600.0, 0.0, include_wb=False)
    assert 'enabled="false"' in off
    assert 'bypassable="true"' in off


def test_dot_and_readme_explain_bypass():
    dot = format_dot(["arri_logc4_awg4"], 3200.0, 0.0, True)
    assert "WB" in dot
    assert "可旁路" in dot
    readme = format_readme(["arri_logc4_awg4"], 3200.0, 0.0, True)
    assert "bypass" in readme.lower()
    assert "ACEScct" in readme
    assert "ACES2065-1" in readme
    assert RESOLVE_README_STATUS in readme
    assert "implemented (unverified)" not in _readme_status_line(readme)
    assert RESOLVE_DOT_STATUS_LABEL in dot
    assert "implemented (unverified)" not in _dot_status_label(dot)
    assert "supported" not in readme.lower()
    assert "一键精准" not in readme
    assert "preview only" in readme.lower() or "preview" in readme.lower()
    assert "ACEScct deliverable" in readme or "ACEScct" in readme
    assert "most standard" not in readme.lower()
    assert "ACES2065-1" in readme
    # Default copy is ACES deliverable, not DWG.
    assert "default deliverable" not in readme.lower() or "ACES" in readme


def test_cdl_ccc_dctl_are_real_payloads():
    cdl = format_cdl(3200.0, 0.0)
    assert "<Slope>" in cdl
    assert "ColorDecisionList" in cdl
    ccc = format_ccc(3200.0, 0.0)
    assert "ColorCorrectionCollection" in ccc
    dctl = format_dctl(3200.0, 1.0)
    assert "acescct_decode" in dctl
    assert "bypass_wb" in dctl
    assert "cat_ap0" in dctl
    assert "ACES2065-1" in dctl
    assert "input_aces2065" in dctl
    assert "davinci" not in dctl.lower()
    assert "intermediate" not in dctl.lower()


def test_cubes_have_lattice(tmp_path: Path):
    export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], lut_size=5, cct=3200.0
    )
    for name in ("03_WB.cube", "04_ODT_Rec709.cube", "01_IDT_arri_logc4_awg4.cube"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "LUT_3D_SIZE 5" in text
        rgb_lines = [
            ln
            for ln in text.splitlines()
            if ln.strip()
            and not ln.startswith("#")
            and not ln.startswith("TITLE")
            and not ln.startswith("LUT_")
            and not ln.startswith("DOMAIN")
        ]
        assert len(rgb_lines) == 125


def test_skips_unknown_idt_ids(tmp_path: Path):
    written = export_resolve_bundle(
        tmp_path, idt_ids=["canon_clog2", "arri_logc4_awg4"], lut_size=5
    )
    names = {p.name for p in written}
    assert "01_IDT_arri_logc4_awg4.cube" in names
    assert not any("canon" in n for n in names)


def test_wb_acescct_wrap_is_ap0_cat_not_encoded_cat():
    """WB on ACEScct timeline decodes to ACES2065-1, CATs in AP0, encodes."""
    ap0 = np.array([0.10, 0.18, 0.30])
    enc = aces2065_to_acescct(ap0)
    wrapped = wb_in_acescct(enc, 3200.0)
    direct = aces2065_to_acescct(wb_in_aces2065(ap0, 3200.0))
    np.testing.assert_allclose(wrapped, direct, atol=1e-10)
    # CAT applied to ACEScct codes is a different (wrong) operator.
    wrong = apply_white_balance(enc, 3200.0, rgb_space="AP0")
    assert not np.allclose(wrapped, wrong, atol=1e-3)


def test_export_default_odt_off_acescct_deliverable(tmp_path: Path):
    written = export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], lut_size=5
    )
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    assert 'name="ODT_Rec709" type="LUT_or_CST" bypassable="true" enabled="false"' in xml
    assert GRAPH_ODT_USER in xml
    assert GRAPH_ODT_XML_DESC == GRAPH_ODT_USER
    assert "预览·非成片" in xml
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    assert GRAPH_ODT_USER in readme
    assert "preview only" not in _graph_section(readme)
    assert "most standard" not in readme.lower()
    names = {p.name for p in written}
    assert "03_WB.dctl" in names
    dctl = (tmp_path / "03_WB.dctl").read_text(encoding="utf-8")
    assert "AP0" in dctl or "ACES2065-1" in dctl


def _cube_rgb_lines(text: str) -> list[str]:
    return [
        ln
        for ln in text.splitlines()
        if ln.strip()
        and not ln.startswith("#")
        and not ln.startswith("TITLE")
        and not ln.startswith("LUT_")
        and not ln.startswith("DOMAIN")
    ]


def _dctl_cat_is_identity(text: str, atol: float = 1e-8) -> bool:
    start = text.find("cat_ap0[9]")
    if start < 0:
        start = text.find("const float m[9]")
    assert start >= 0, "DCTL is missing the AP0 CAT matrix"
    brace = text.find("{", start)
    end = text.find("}", brace)
    nums = [
        float(tok.replace("f", ""))
        for tok in text[brace + 1 : end].replace("\n", " ").split(",")
        if tok.strip()
    ]
    assert len(nums) == 9
    ident = np.eye(3).reshape(-1)
    return bool(np.allclose(nums, ident, atol=atol))


LOCKED_REC709_CUBE_TITLE = (
    "LogBridge 709 预览 ACEScct → Rec.709 (BT.709 OETF preview, not ACES OT)"
)
LOCKED_NODE_FILES = (
    "graph.xml",
    "graph.dot",
    "01_IDT_",
    "03_WB",
    "04_ODT_Rec709.cube",
    "README_RESOLVE.md",
)
LOCKED_BUNDLE_FILES = (
    "README_RESOLVE.md",
    "graph.xml",
    "graph.dot",
    "02_Exposure.cube",
    "02_Exposure.dctl",
    "03_WB.cdl",
    "03_WB.ccc",
    "03_WB.dctl",
    "03_WB.cube",
    "04_ODT_Rec709.cube",
)
RESOLVE_README_STATUS = "状态：**已实现（未验证）**。不是相机支持声明。"
RESOLVE_README_STATUS_PARALLEL_EN = (
    "状态：**已实现（未验证）** / implemented (unverified)。不是相机支持声明。"
)
RESOLVE_DOT_STATUS_LABEL = "LogBridge M1 Resolve graph — 已实现（未验证）"
RESOLVE_XML_STATUS_ATTR = 'status="implemented (unverified)"'
RESOLVE_CUBE_STATUS_COMMENT = (
    "# LogBridge M1 — implemented (unverified). Not a camera-support claim."
)


def _readme_status_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("状态："):
            return stripped
    raise AssertionError("README_RESOLVE missing 状态： line")


def _dot_status_label(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("label="):
            return stripped
    raise AssertionError("graph.dot missing label= line")


HONESTY_BANNED = (
    "DIY BT.709 OETF",
    "identity / enabled=false",
    "identity / `enabled=false`",
    "enabled=false",
    "preview only",
    "Not an ACES Output Transform",
    "不烘焙白平衡",
    "完善",
    "精准",
    "CAT(user→D65)",
    "CAT(user→D65)·inv(CAT(as→D65))",
    "默认 CAT 是单位阵",
    "相对变换 CAT",
    "绝对 CAT",
)
GRAPH_WB_SUMMARY_LOCKED = (
    "色温 {cctLabel}，绿品 {tint}，方法 Bradford。"
    "机内只填旋钮；默认单位阵（不把机内色温当光源去校正）。"
    "读不到则为待定/单位阵，不猜 5600 或 6504。"
)
GRAPH_WB_SWIFT = (
    "色温 \\(cctLabel(cct))，绿品 \\(tint)，方法 Bradford。"
    "机内只填旋钮；默认单位阵（不把机内色温当光源去校正）。"
    "读不到则为待定/单位阵，不猜 5600 或 6504。"
)
GRAPH_WB_BANNED = (
    "identity",
    "CAT(user→D65)",
    "CAT(user→D65)·inv(CAT(as→D65))",
    "As-shot fills knobs",
    "default CAT is identity",
    "Scene-linear only",
)


def _dedent_swift_honesty(readme_fn: str) -> str:
    raw = readme_fn.split("## 诚实说明", 1)[1].split("## Graph (serial nodes)", 1)[0]
    lines = ["## 诚实说明"]
    for line in raw.splitlines():
        lines.append(line[8:] if line.startswith("        ") else line)
    return "\n".join(ln for ln in lines if ln.strip()).strip()


def _honesty_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _graph_section(text: str) -> str:
    return text.split("## Graph (serial nodes)", 1)[1].split("## How to bypass", 1)[0]


def _apply_section(text: str) -> str:
    return text.split("## How to bypass", 1)[1]


def _apply_odt_line(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip().startswith("- Apply **ODT**"):
            return ln.strip()
    raise AssertionError("Apply ODT line missing")


def _files_section(text: str) -> str:
    return text.split("## Files", 1)[1]


def _files_graph_dot_row(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip().startswith("| `graph.dot`"):
            return ln.strip()
    raise AssertionError("Files graph.dot row missing")


def _color_page_title_line(text: str) -> str:
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped in (
            README_COLOR_PAGE_TITLE_TO,
            README_COLOR_PAGE_TITLE_FROM,
        ) or stripped.startswith("Color page, serial node graph"):
            return stripped
        if stripped.startswith("调色页，串行节点图"):
            return stripped
    raise AssertionError("Color page title line missing")


def _files_header_row(text: str) -> str:
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped in (
            README_FILES_HEADER_TO,
            README_FILES_HEADER_FROM,
        ) or stripped.startswith("| File | Role") or stripped.startswith("| 文件 | 作用"):
            return stripped
    raise AssertionError("Files table header row missing")


def _files_graph_xml_row(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip().startswith("| `graph.xml`"):
            return ln.strip()
    raise AssertionError("Files graph.xml row missing")


def _files_readme_row(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip().startswith("| `README_RESOLVE.md`"):
            return ln.strip()
    raise AssertionError("Files README_RESOLVE.md row missing")


def _files_idt_row(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip().startswith("| `01_IDT_<idt>.cube`"):
            return ln.strip()
    raise AssertionError("Files 01_IDT_<idt>.cube row missing")


def _graph_wb_summary_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        if "机内只填旋钮" in stripped and "方法 Bradford" in stripped:
            return stripped
    raise AssertionError("Graph WB summary line missing")


GRAPH_ODT_BANNED = (
    "DIY BT.709 OETF",
    "preview only",
    "Not an ACES Output Transform",
)


def _assert_chengpian_not_a_deliverable_claim(text: str) -> None:
    cleaned = (
        text.replace("预览·非成片", "")
        .replace("不是全精度成片", "")
        .replace("不是整段成片", "")
        .replace("不是成片", "")
        .replace("成片预览关", "")
    )
    assert "成片" not in cleaned
    assert "精准" not in cleaned
    assert "一键还原" not in cleaned
    assert "一键校准" not in cleaned


@pytest.mark.parametrize(
    "missing",
    [
        RESOLVE_REQUIRED_XML,
        RESOLVE_REQUIRED_README,
        RESOLVE_REQUIRED_DCTL,
        RESOLVE_REQUIRED_CUBE,
    ],
)
def test_missing_resolve_package_file_fails_chinese(tmp_path: Path, missing: str):
    """Missing graph.xml / DCTL / cube / README: 达芬奇包不完整，未写出. Not 已写出代理."""
    dest = tmp_path / "half"
    dest.mkdir()
    for name in RESOLVE_REQUIRED_NAMES:
        if name == missing:
            continue
        (dest / name).write_text("x")
    ok, err = verify_resolve_bundle(dest)
    assert ok is False
    assert err == RESOLVE_INCOMPLETE_CHIP
    assert err != WRITTEN_CHIP
    assert (dest / missing).exists() is False


def test_unlocked_never_exported(tmp_path: Path):
    clips = [
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
        BatchClip("empty.mov"),
        BatchClip("stub.mov", idt="future", is_stub=True),
    ]
    dest = tmp_path / "empty_pkg"
    report = export_locked_resolve_bundle(dest, clips, lut_size=5)
    assert report.written == ()
    assert not dest.exists()
    assert report.skipped_reasons["pending.mov"] == REASON_PICK_PAIRED_IDT
    assert report.skipped_reasons["empty.mov"] == REASON_PICK_LOG_GAMUT
    assert report.skipped_reasons["stub.mov"] == REASON_PICK_PAIRED_IDT


def test_locked_session_package_skips_pending(tmp_path: Path):
    clips = [
        BatchClip("locked.mov", idt="sony_slog3_sgamut3"),
        BatchClip("also.mov", idt="arri_logc4_awg4"),
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
        BatchClip("empty.mov"),
    ]
    dest = tmp_path / "pkg"
    report = export_locked_resolve_bundle(dest, clips, lut_size=5)
    names = set(report.written_names)
    assert "graph.xml" in names
    assert "03_WB.dctl" in names
    assert "04_ODT_Rec709.cube" in names
    assert "01_IDT_sony_slog3_sgamut3.cube" in names
    assert "01_IDT_arri_logc4_awg4.cube" in names
    assert not any("pending" in n for n in names)
    assert not any("empty" in n for n in names)
    assert report.skipped_reasons["pending.mov"] == REASON_PICK_PAIRED_IDT
    assert report.skipped_reasons["empty.mov"] == REASON_PICK_LOG_GAMUT
    xml = (dest / "graph.xml").read_text(encoding="utf-8")
    assert "sony_slog3_sgamut3" in xml
    assert "arri_logc4_awg4" in xml
    assert "pending.mov" not in xml


def test_wb_off_has_no_baked_cat(tmp_path: Path):
    """WB off + grey-card CCT must not bake CAT(user) into DCTL/cube/CDL."""
    g = SerialGraph(
        idt_id="arri_logc4_awg4",
        wb_enabled=False,
        wb_cct=3200.0,
        wb_tint=0.4,
        wb_source=WB_SOURCE_GREY,
    )
    assert g.effective_wb_cct == pytest.approx(3200.0)
    export_resolve_bundle(tmp_path / "off", idt_ids=["arri_logc4_awg4"], graph=g, lut_size=5)
    off_dctl = (tmp_path / "off" / "03_WB.dctl").read_text(encoding="utf-8")
    off_cube = (tmp_path / "off" / "03_WB.cube").read_text(encoding="utf-8")
    off_cdl = (tmp_path / "off" / "03_WB.cdl").read_text(encoding="utf-8")
    xml = (tmp_path / "off" / "graph.xml").read_text(encoding="utf-8")
    assert 'name="WB" type="Corrector" bypassable="true" enabled="false"' in xml
    assert _dctl_cat_is_identity(off_dctl)
    identity_cube = wb_cube_bytes(None, 0.0, size=5)
    assert _cube_rgb_lines(off_cube) == _cube_rgb_lines(identity_cube)
    baked = wb_cube_bytes(3200.0, 0.4, size=5)
    assert _cube_rgb_lines(off_cube) != _cube_rgb_lines(baked)
    assert "<Slope>1.0000000000 1.0000000000 1.0000000000</Slope>" in off_cdl

    export_resolve_bundle(
        tmp_path / "flag",
        idt_ids=["arri_logc4_awg4"],
        include_wb=False,
        cct=3200.0,
        tint=0.4,
        lut_size=5,
    )
    flag_dctl = (tmp_path / "flag" / "03_WB.dctl").read_text(encoding="utf-8")
    assert _dctl_cat_is_identity(flag_dctl)
    xml_flag = (tmp_path / "flag" / "graph.xml").read_text(encoding="utf-8")
    assert 'enabled="false"' in xml_flag

    on = SerialGraph(
        idt_id="arri_logc4_awg4",
        wb_enabled=True,
        wb_cct=3200.0,
        wb_tint=0.4,
        wb_source=WB_SOURCE_GREY,
    )
    export_resolve_bundle(tmp_path / "on", idt_ids=["arri_logc4_awg4"], graph=on, lut_size=5)
    on_dctl = (tmp_path / "on" / "03_WB.dctl").read_text(encoding="utf-8")
    on_cube = (tmp_path / "on" / "03_WB.cube").read_text(encoding="utf-8")
    assert not _dctl_cat_is_identity(on_dctl)
    assert _cube_rgb_lines(on_cube) == _cube_rgb_lines(baked)


def test_readme_resolve_chinese_honesty_notes(tmp_path: Path):
    """高级 Resolve 导出 README：中文诚实说明，不改色彩数字。"""
    export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], include_wb=False, lut_size=5
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    honesty = readme.split("## Graph (serial nodes)")[0]
    assert "709 预览" in honesty
    assert "整段代理，不是全精度成片" in honesty
    assert "_proxy" in honesty
    assert "已实现（未验证）" in readme
    assert RESOLVE_README_HONESTY.strip() in readme
    assert EXPORT_NOTE_REC709 in honesty
    assert EXPORT_NOTE_WB_BYPASS in honesty
    assert EXPORT_NOTE_WB_OFF == "已写出但默认旁路（不改颜色）"
    assert EXPORT_NOTE_WB_OFF in readme
    for token in HONESTY_BANNED:
        assert token not in honesty
        assert token not in RESOLVE_README_HONESTY
        assert token not in EXPORT_NOTE_WB_OFF
        assert token not in EXPORT_NOTE_WB_BYPASS
        assert token not in EXPORT_NOTE_REC709
    assert "identity" not in honesty
    assert EXPORT_NOTE_IN_CAMERA == (
        "机内色温只填旋钮，默认是单位阵。"
        "只有你改色温才做相对校正（例如 3200→5600 变暖）。"
        "灰卡是绝对校正；读不到就保持单位阵，不猜 5600。"
    )
    assert EXPORT_NOTE_IN_CAMERA in honesty
    assert EXPORT_NOTE_IN_CAMERA in RESOLVE_README_HONESTY
    assert "默认 CAT 是单位阵" not in honesty
    assert "CAT(user→D65)" not in honesty
    assert "CAT(user→D65)·inv(CAT(as→D65))" not in honesty
    assert "相对变换" not in honesty
    assert "绝对 CAT" not in honesty
    assert "机内白转到 D65" not in readme
    assert "精准" not in readme
    assert "一键还原" not in readme
    assert readme.index("诚实说明") < readme.index("Graph (serial nodes)")
    _assert_chengpian_not_a_deliverable_claim(readme)
    graph = _graph_section(readme)
    assert GRAPH_ODT_USER in graph
    for token in GRAPH_ODT_BANNED:
        assert token not in graph
    assert GRAPH_WB_SUMMARY == GRAPH_WB_SUMMARY_LOCKED
    wb_line = _graph_wb_summary_line(graph)
    assert wb_line == GRAPH_WB_SUMMARY.format(cctLabel="6504 K", tint=0.0)
    assert not wb_line.startswith("CCT")
    assert "CCT" not in wb_line.replace("ACEScct", "")
    for token in GRAPH_WB_BANNED:
        assert token not in wb_line, token
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    assert REC709_PREVIEW_LABEL in cube
    assert REC709_CUBE_COMMENT in cube
    assert "DIY BT.709 OETF" not in cube
    assert "Not an ACES Output Transform" not in cube
    assert "ACES Output Transform" not in cube
    assert "ACES OT" not in cube.replace("not ACES OT", "")
    _assert_chengpian_not_a_deliverable_claim(cube)

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    note_fn = swift.split("static func exportNote")[1].split("static func export(")[0]
    readme_fn = swift.split("private static func readme")[1].split("/// Proxy sequence folder")[0]
    swift_honesty = _dedent_swift_honesty(readme_fn)
    assert _honesty_lines(swift_honesty) == _honesty_lines(RESOLVE_README_HONESTY)
    assert EXPORT_NOTE_REC709 in swift_honesty
    assert EXPORT_NOTE_WB_BYPASS in swift_honesty
    assert EXPORT_NOTE_WB_OFF in readme_fn
    for token in HONESTY_BANNED:
        assert token not in swift_honesty
    assert "identity" not in swift_honesty
    assert "不烘焙白平衡" not in readme_fn
    assert "不烘焙白平衡" not in note_fn
    assert "不烘焙白平衡" not in readme
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    for name in LOCKED_NODE_FILES:
        assert name in readme_fn
        assert name in readme
    for name in LOCKED_BUNDLE_FILES:
        assert f'"{name}"' in swift
    for blob in (note_fn, readme_fn):
        assert "709 预览" in blob
        assert "整段代理，不是全精度成片" in blob
        assert "已实现（未验证）" in blob
        assert EXPORT_NOTE_IN_CAMERA in blob
        assert "默认 CAT 是单位阵" not in blob
        assert "CAT(user→D65)" not in blob
        assert "CAT(user→D65)·inv(CAT(as→D65))" not in blob
        assert "相对变换" not in blob
        assert "绝对 CAT" not in blob
        assert "3200→5600 变暖" in blob
        assert "不猜 5600" in blob
        assert "机内白转到 D65" not in blob
        assert "精准" not in blob
        assert "一键还原" not in blob
        _assert_chengpian_not_a_deliverable_claim(blob)
    swift_graph = _graph_section(readme_fn)
    assert GRAPH_ODT_USER in swift_graph
    for token in GRAPH_ODT_BANNED:
        assert token not in swift_graph
    swift_wb = _graph_wb_summary_line(readme_fn)
    assert GRAPH_WB_SWIFT in readme_fn
    assert swift_wb == GRAPH_WB_SWIFT
    assert not swift_wb.startswith("CCT")
    assert "CCT" not in swift_wb.replace("ACEScct", "")
    for token in GRAPH_WB_BANNED:
        assert token not in swift_wb, token
    ui_note = "\n".join(line.split("//", 1)[0] for line in note_fn.splitlines())
    assert "identity" not in ui_note
    assert "enabled=false" not in ui_note
    assert "DIY BT.709 OETF" not in ui_note
    assert "Bradford CAT" not in ui_note
    assert "stops" not in ui_note


def test_readme_resolve_status_line_drops_parallel_english(tmp_path: Path):
    """README_RESOLVE 状态行：只留中文。XML / cube 机读英文可留。"""
    export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], include_wb=False, lut_size=5
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    dot = (tmp_path / "graph.dot").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")

    status = _readme_status_line(readme)
    assert status == RESOLVE_README_STATUS
    assert "implemented (unverified)" not in status
    assert RESOLVE_README_STATUS_PARALLEL_EN not in readme
    assert "未验证" in status
    assert "预览·非成片" in readme
    assert "整段代理，不是全精度成片" in readme
    _assert_chengpian_not_a_deliverable_claim(readme)

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.0, True)
    assert _readme_status_line(generated) == RESOLVE_README_STATUS
    assert RESOLVE_README_STATUS_PARALLEL_EN not in generated

    assert RESOLVE_DOT_STATUS_LABEL in dot
    assert "implemented (unverified)" not in _dot_status_label(dot)
    assert RESOLVE_XML_STATUS_ATTR in xml
    assert RESOLVE_CUBE_STATUS_COMMENT in cube

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]

    assert RESOLVE_README_STATUS in readme_fn
    assert RESOLVE_README_STATUS in py_readme
    assert _readme_status_line(readme_fn) == _readme_status_line(py_readme)
    assert RESOLVE_README_STATUS_PARALLEL_EN not in readme_fn
    assert RESOLVE_README_STATUS_PARALLEL_EN not in py_readme
    assert RESOLVE_DOT_STATUS_LABEL in dot_fn
    assert RESOLVE_DOT_STATUS_LABEL in py_dot
    assert RESOLVE_XML_STATUS_ATTR in xml_fn
    assert RESOLVE_XML_STATUS_ATTR in py_xml
    assert RESOLVE_CUBE_STATUS_COMMENT in swift
    assert RESOLVE_CUBE_STATUS_COMMENT in py
    assert "未验证" in readme_fn
    assert "未验证" in py_readme
    assert "预览·非成片" in readme_fn
    assert "预览·非成片" in py_readme


def test_readme_graph_odt_user_copy_is_locked_chinese(tmp_path: Path):
    """Graph / ODT Description / dot / cube # comment: locked ⑭. TITLE + nodes stay."""
    export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], include_wb=False, lut_size=5
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    dot = (tmp_path / "graph.dot").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")

    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.0, True)
    py_graph = _graph_section(generated)
    written_graph = _graph_section(readme)
    assert GRAPH_ODT_USER in py_graph
    assert GRAPH_ODT_USER in written_graph
    assert _graph_wb_summary_line(py_graph) == GRAPH_WB_SUMMARY.format(
        cctLabel="3200 K", tint=0.0
    )
    assert "709 预览" in written_graph
    assert "预览·非成片" in written_graph
    for token in GRAPH_ODT_BANNED:
        assert token not in py_graph
        assert token not in written_graph

    assert GRAPH_ODT_USER in xml
    assert GRAPH_ODT_XML_DESC == GRAPH_ODT_USER
    assert 'name="ODT_Rec709" type="LUT_or_CST" bypassable="true"' in xml
    assert 'name="IDT"' in xml
    assert 'name="Exposure"' in xml
    assert 'name="WB"' in xml
    for token in GRAPH_ODT_BANNED:
        desc = xml.split("<Node index=\"4\"", 1)[1].split("</Node>", 1)[0]
        assert token not in desc

    assert GRAPH_ODT_USER in dot
    odt_label = dot.split("odt  [label=", 1)[1].split("];", 1)[0]
    for token in GRAPH_ODT_BANNED:
        assert token not in odt_label

    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert REC709_CUBE_COMMENT == f"# {GRAPH_ODT_USER}"
    assert REC709_CUBE_COMMENT in cube
    for token in GRAPH_ODT_BANNED:
        assert token not in cube

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    odt_fn = swift.split("private static func odtCube")[1].split(
        "private static func exposureCube"
    )[0]

    swift_graph = _graph_section(readme_fn)
    assert GRAPH_ODT_USER in swift_graph
    assert "{GRAPH_ODT_USER}" in py_readme
    assert f'GRAPH_ODT_USER = "{GRAPH_ODT_USER}"' in py
    assert _graph_section(readme_fn).count(GRAPH_ODT_USER) >= 1
    for token in GRAPH_ODT_BANNED:
        assert token not in swift_graph
        assert token not in _graph_section(py_readme)
    assert GRAPH_ODT_XML_DESC in xml_fn
    assert "GRAPH_ODT_XML_DESC" in py_xml or GRAPH_ODT_XML_DESC in py_xml
    assert GRAPH_ODT_USER in dot_fn
    assert "GRAPH_ODT_USER" in py_dot or GRAPH_ODT_USER in py_dot
    assert f'"{REC709_CUBE_COMMENT}"' in odt_fn
    assert f'GRAPH_ODT_USER = "{GRAPH_ODT_USER}"' in py
    assert REC709_CUBE_TITLE in odt_fn
    assert REC709_CUBE_TITLE in py
    assert LOCKED_REC709_CUBE_TITLE in swift
    odt_xml_desc = xml_fn.split('name="ODT_Rec709"', 1)[1].split(
        "<Description>", 1
    )[1].split("</Description>", 1)[0]
    comment_assign = py.split("REC709_CUBE_COMMENT =", 1)[1].split(
        "GRAPH_ODT_XML_DESC", 1
    )[0]
    for token in GRAPH_ODT_BANNED:
        assert token not in odt_fn
        assert token not in comment_assign
        assert token not in odt_xml_desc
    assert "完善" not in written_graph
    assert "精准" not in written_graph
    assert "达芬奇已验证" not in written_graph
    assert "达芬奇已验证" not in xml
    assert "达芬奇已验证" not in cube
    _assert_chengpian_not_a_deliverable_claim(written_graph)
    _assert_chengpian_not_a_deliverable_claim(xml)
    _assert_chengpian_not_a_deliverable_claim(cube)


def test_readme_resolve_graph_wb_summary_plain_chinese(tmp_path: Path):
    """README_RESOLVE ㉕: honesty / Graph WB 人话. Align ⑮. XML / TITLE / nodes stay."""
    export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], include_wb=True, cct=3200.0, lut_size=5
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    honesty = readme.split("## Graph (serial nodes)")[0]
    graph = _graph_section(readme)

    assert EXPORT_NOTE_IN_CAMERA == (
        "机内色温只填旋钮，默认是单位阵。"
        "只有你改色温才做相对校正（例如 3200→5600 变暖）。"
        "灰卡是绝对校正；读不到就保持单位阵，不猜 5600。"
    )
    assert EXPORT_NOTE_IN_CAMERA in honesty
    assert GRAPH_WB_SUMMARY == GRAPH_WB_SUMMARY_LOCKED
    wb_line = _graph_wb_summary_line(graph)
    assert wb_line == GRAPH_WB_SUMMARY.format(cctLabel="3200 K", tint=0.0)
    assert "未验证" in readme
    assert "预览·非成片" in readme
    for token in HONESTY_BANNED:
        assert token not in honesty, token
    assert "identity" not in honesty
    assert "CAT(user→D65)" not in honesty
    assert "默认 CAT 是单位阵" not in honesty
    assert not wb_line.startswith("CCT")
    assert "CCT" not in wb_line.replace("ACEScct", "")
    for token in GRAPH_WB_BANNED:
        assert token not in wb_line, token

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    assert EXPORT_NOTE_IN_CAMERA in generated
    assert _graph_wb_summary_line(generated) == GRAPH_WB_SUMMARY.format(
        cctLabel="3200 K", tint=0.25
    )

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    note_fn = swift.split("static func exportNote")[1].split("static func export(")[0]
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    assert EXPORT_NOTE_IN_CAMERA in note_fn
    assert EXPORT_NOTE_IN_CAMERA in readme_fn
    assert GRAPH_WB_SWIFT in readme_fn
    assert _honesty_lines(_dedent_swift_honesty(readme_fn)) == _honesty_lines(
        RESOLVE_README_HONESTY
    )
    assert _graph_wb_summary_line(readme_fn) == GRAPH_WB_SWIFT
    assert "GRAPH_WB_SUMMARY.format" in py
    assert '"色温 {cctLabel}，绿品 {tint}，方法 Bradford。"' in py

    # FROZEN: cube TITLE, XML structure / filenames, node filenames.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert 'name="WB"' in xml
    assert GRAPH_WB_XML_DESC in xml
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "default CAT is identity" not in xml
    assert "default CAT is identity" not in xml_fn
    for name in LOCKED_NODE_FILES:
        assert name in readme
        assert name in readme_fn
    for name in LOCKED_BUNDLE_FILES:
        assert f'"{name}"' in swift
    assert "达芬奇已验证" not in honesty
    assert "达芬奇已验证" not in wb_line
    _assert_chengpian_not_a_deliverable_claim(honesty)
    _assert_chengpian_not_a_deliverable_claim(wb_line)


def test_709_cube_labeled_preview_not_aces_ot(tmp_path: Path):
    export_resolve_bundle(tmp_path, idt_ids=["arri_logc4_awg4"], lut_size=5)
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    assert REC709_PREVIEW_LABEL in cube
    assert REC709_CUBE_TITLE in cube
    assert "ACES Output Transform" not in cube
    assert "ACES OT" not in cube.replace("not ACES OT", "")
    _assert_chengpian_not_a_deliverable_claim(cube)
    assert REC709_PREVIEW_LABEL in xml
    assert 'type="ACES_OT"' not in xml
    assert GRAPH_ODT_USER in xml
    assert "预览·非成片" in xml
    assert REC709_PREVIEW_LABEL in readme
    assert GRAPH_ODT_USER in readme
    assert "Not an ACES Output Transform" not in _graph_section(readme)
    generated = odt_cube_bytes(size=5)
    assert generated.splitlines()[0] == f'TITLE "{REC709_CUBE_TITLE}"'
    _assert_chengpian_not_a_deliverable_claim(xml)
    _assert_chengpian_not_a_deliverable_claim(readme)


def test_resolve_copy_has_no_precision_or_chengpian_claims(tmp_path: Path):
    written = export_resolve_bundle(
        tmp_path, idt_ids=["arri_logc4_awg4"], include_wb=False, lut_size=5
    )
    blob = "\n".join(p.read_text(encoding="utf-8") for p in written)
    _assert_chengpian_not_a_deliverable_claim(blob)
    assert "implemented (unverified)" in blob.lower() or "已实现（未验证）" in blob
    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    clip = (root / "macos/LogBridge/LogBridge/Models/Clip.swift").read_text(encoding="utf-8")
    idt_fn = swift.split("func uniqueImplementedIDTs")[1].split("ap0ToXYZ")[0]
    assert "hasLockedPair" in idt_fn
    assert "includeWBNode" in swift
    assert "matrixCCT = nil" in swift
    assert REC709_PREVIEW_LABEL in swift
    assert "not ACES OT" in swift
    export_fn = clip.split("func exportResolve()")[1]
    assert "先选择成对 IDT" in export_fn
    assert "先选择 Log 与色域" in export_fn
    _assert_chengpian_not_a_deliverable_claim(
        swift.split("enum ResolveExporter")[1].split("Proxy sequence folder")[0]
    )
    _assert_chengpian_not_a_deliverable_claim(export_fn)


RESOLVE_IDT_PLACEHOLDER = 'idt="用户选择成对 IDT"'
RESOLVE_CCT_PENDING_LABEL = "待定 / 单位阵"
RESOLVE_README_EMPTY_IDT = "（无 — 请在达芬奇 CST 里指定 IDT）"
WB_CUBE_TITLE_HEAD = "LogBridge WB AP0 CAT"
LOCKED_NODE_NAMES = (
    'name="IDT"',
    'name="Exposure"',
    'name="WB"',
    'name="ODT_Rec709"',
)


def test_resolve_package_placeholders_are_locked_chinese(tmp_path: Path):
    """XML/README user copy: 用户选择成对 IDT + 待定/单位阵 + 空 IDT 人话. TITLE/nodes stay."""
    xml = format_graph_xml([], None, 0.0, include_wb=False)
    assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
    assert RESOLVE_IDT_PLACEHOLDER in xml
    assert "(user picker)" not in xml
    assert "pending / identity" not in xml
    assert GRAPH_WB_XML_DESC in xml
    assert "待定/单位阵" in xml
    for name in LOCKED_NODE_NAMES:
        assert name in xml
    assert 'type="LUT_or_CST"' in xml
    assert 'type="Corrector"' in xml
    assert 'bypassable="false"' in xml
    assert 'bypassable="true"' in xml
    assert 'name="WB" type="Corrector" bypassable="true" enabled="false"' in xml
    assert "完善" not in xml
    assert "精准" not in xml
    assert "达芬奇已验证" not in xml
    assert "implemented (unverified)" in xml
    _assert_chengpian_not_a_deliverable_claim(xml)

    empty = tmp_path / "empty"
    export_resolve_bundle(empty, idt_ids=[], lut_size=5, include_wb=False, cct=None)
    raw = (empty / "graph.xml").read_bytes()
    assert raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    assert "用户选择成对 IDT".encode("utf-8") in raw
    written_xml = raw.decode("utf-8")
    assert RESOLVE_IDT_PLACEHOLDER in written_xml
    assert "(user picker)" not in written_xml
    assert "pending / identity" not in written_xml
    readme = (empty / "README_RESOLVE.md").read_text(encoding="utf-8")
    assert RESOLVE_README_EMPTY_IDT in readme
    assert "none — assign" not in readme
    assert "pending / identity" not in readme
    assert "已实现（未验证）" in readme
    assert _readme_status_line(readme) == RESOLVE_README_STATUS
    assert "implemented (unverified)" not in _readme_status_line(readme)
    assert RESOLVE_README_STATUS_PARALLEL_EN not in readme
    assert "完善" not in readme
    assert "精准" not in readme
    assert "达芬奇已验证" not in readme
    _assert_chengpian_not_a_deliverable_claim(readme)
    empty_readme = format_readme([], None, 0.0, False)
    assert RESOLVE_README_EMPTY_IDT in empty_readme
    assert "none — assign" not in empty_readme
    filled_readme = format_readme(["arri_logc4_awg4"], 3200.0, 0.0, True)
    assert RESOLVE_README_EMPTY_IDT not in filled_readme
    assert "arri_logc4_awg4" in filled_readme
    assert "none — assign" not in filled_readme
    dot = (empty / "graph.dot").read_text(encoding="utf-8")
    assert "pending / identity" not in dot
    assert "(user picker)" not in dot

    cube = wb_cube_bytes(None, 0.0, size=5)
    title = cube.splitlines()[0]
    assert title.startswith(f'TITLE "{WB_CUBE_TITLE_HEAD}')
    assert "ACEScct decode→ACES2065-1→encode" in title
    # Python TITLE keeps English as-shot unknown (not the user-visible pending phrase).
    assert "as-shot unknown" in title

    locked = tmp_path / "locked"
    export_resolve_bundle(locked, idt_ids=["arri_logc4_awg4"], lut_size=5)
    pkg_xml = (locked / "graph.xml").read_text(encoding="utf-8")
    assert 'name="IDT" type="LUT_or_CST" bypassable="false"' in pkg_xml
    assert 'name="Exposure" type="Gain_1D" bypassable="true"' in pkg_xml
    assert 'name="WB" type="Corrector" bypassable="true"' in pkg_xml
    assert 'name="ODT_Rec709" type="LUT_or_CST" bypassable="true" enabled="false"' in pkg_xml
    assert "(user picker)" not in pkg_xml
    assert RESOLVE_IDT_PLACEHOLDER not in pkg_xml
    cube709 = (locked / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    assert cube709.splitlines()[0] == f'TITLE "{REC709_CUBE_TITLE}"'
    wb = (locked / "03_WB.cube").read_text(encoding="utf-8")
    assert wb.splitlines()[0].startswith(f'TITLE "{WB_CUBE_TITLE_HEAD}')

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    cct_fn = swift.split("private static func cctLabel")[1].split(
        "static func exportNote"
    )[0]
    wb_fn = swift.split("private static func wbCube")[1].split(
        "private static func odtCube"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]

    assert 'idt=\\"用户选择成对 IDT\\"' in xml_fn
    assert RESOLVE_IDT_PLACEHOLDER in py_xml
    assert "(user picker)" not in xml_fn
    assert "(user picker)" not in py_xml
    assert f'?? "{RESOLVE_CCT_PENDING_LABEL}"' in cct_fn
    assert "pending / identity" not in cct_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "待定/单位阵" in xml_fn
    assert GRAPH_WB_SWIFT in readme_fn
    assert "待定/单位阵" in readme_fn
    assert RESOLVE_README_EMPTY_IDT in readme_fn
    assert RESOLVE_README_EMPTY_IDT in py_readme
    assert RESOLVE_README_EMPTY_IDT not in xml_fn
    assert RESOLVE_README_EMPTY_IDT not in py_xml
    assert RESOLVE_README_EMPTY_IDT not in written_xml
    assert RESOLVE_README_EMPTY_IDT not in cube
    assert RESOLVE_README_EMPTY_IDT not in cube709
    assert "none — assign" not in readme_fn
    assert "none — assign" not in py_readme
    assert "none — assign" not in xml_fn
    assert "none — assign" not in py_xml
    assert "pending / identity" not in xml_fn
    assert "pending / identity" not in readme_fn
    assert "pending / identity" not in dot_fn
    assert "pending / identity" not in py_xml
    assert "pending / identity" not in py_readme
    # Cube TITLE may keep English pending / identity.
    assert '?? "pending / identity"' in wb_fn
    assert WB_CUBE_TITLE_HEAD in wb_fn
    for name in LOCKED_NODE_NAMES:
        assert name in xml_fn
        assert name in py_xml or (name == 'name="ODT_Rec709"' and "odt_name" in py_xml)
    assert 'name="IDT"' in py_xml
    assert 'name="Exposure"' in py_xml
    assert 'name="WB"' in py_xml
    assert "includeWBNode" in swift
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    for blob in (xml_fn, readme_fn, py_xml, py_readme, written_xml, readme):
        assert "完善" not in blob
        assert "精准" not in blob
        assert "达芬奇已验证" not in blob
        _assert_chengpian_not_a_deliverable_claim(blob)


EXPORT_NOTE_ODT_LOCKED = "预览输出：709 预览（不是 ACES 输出变换），默认关。预览·非成片。"
EXPORT_NOTE_ODT_FROM = "ODT：709 预览（不是 ACES 输出变换），默认关。预览·非成片。"


def test_export_note_odt_preview_output_zh():
    """exportNote ㉖: ODT： → 预览输出：. Align ㉑. ㉕ honesty/Graph WB / TITLE / XML stay."""
    assert EXPORT_NOTE_ODT == EXPORT_NOTE_ODT_LOCKED
    assert EXPORT_NOTE_ODT == (
        "预览输出：709 预览（不是 ACES 输出变换），默认关。预览·非成片。"
    )
    assert EXPORT_NOTE_ODT.startswith("预览输出：")
    assert EXPORT_NOTE_ODT.endswith("709 预览（不是 ACES 输出变换），默认关。预览·非成片。")
    assert "ODT：" not in EXPORT_NOTE_ODT
    assert not EXPORT_NOTE_ODT.startswith("ODT：")
    assert EXPORT_NOTE_ODT_FROM not in EXPORT_NOTE_ODT

    py_on = export_note(include_wb=True, cct=3200, tint=0.25)
    py_off = export_note(include_wb=False, cct=None, tint=0.0)
    assert EXPORT_NOTE_ODT in py_on
    assert EXPORT_NOTE_ODT in py_off
    assert EXPORT_NOTE_ODT_FROM not in py_on
    assert EXPORT_NOTE_ODT_FROM not in py_off
    for blob in (py_on, py_off):
        assert "ODT：" not in blob
        assert "达芬奇已验证" not in blob
        _assert_chengpian_not_a_deliverable_claim(blob)

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    note_fn = swift.split("static func exportNote")[1].split("static func export(")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    assert f'"{EXPORT_NOTE_ODT}"' in note_fn
    assert f'EXPORT_NOTE_ODT = "{EXPORT_NOTE_ODT}"' in py
    assert EXPORT_NOTE_ODT_FROM not in note_fn
    assert EXPORT_NOTE_ODT_FROM not in py
    assert "ODT：" not in note_fn
    assert 'EXPORT_NOTE_ODT = "ODT：' not in py

    # ㉕诚实说明 / Graph WB 一字不动.
    assert EXPORT_NOTE_IN_CAMERA == (
        "机内色温只填旋钮，默认是单位阵。"
        "只有你改色温才做相对校正（例如 3200→5600 变暖）。"
        "灰卡是绝对校正；读不到就保持单位阵，不猜 5600。"
    )
    assert EXPORT_NOTE_IN_CAMERA in note_fn
    assert EXPORT_NOTE_IN_CAMERA in readme_fn
    assert GRAPH_WB_SUMMARY == GRAPH_WB_SUMMARY_LOCKED
    assert GRAPH_WB_SWIFT in readme_fn

    # FROZEN: cube TITLE, XML / Graph Descriptions, node filenames.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_XML_DESC == GRAPH_ODT_USER
    assert GRAPH_ODT_USER in _graph_section(readme_fn)
    assert "04_ODT_Rec709.cube" in note_fn
    assert "04_ODT_Rec709.cube" in py
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    for name in LOCKED_BUNDLE_FILES:
        assert f'"{name}"' in swift
    assert 'name="ODT_Rec709"' in xml_fn or "ODT_Rec709" in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "default CAT is identity" not in xml_fn
    assert "matrixCCT = nil" in swift
    assert "def odt_from_acescct" in py
    assert "def odt_cube_bytes" in py
    assert "达芬奇已验证" not in note_fn
    assert "达芬奇已验证" not in EXPORT_NOTE_ODT
    _assert_chengpian_not_a_deliverable_claim(EXPORT_NOTE_ODT)
    _assert_chengpian_not_a_deliverable_claim(note_fn)


GRAPH_DOT_EXP_BANNED = (
    "Exposure (zeroable)",
    "Exposure (bypassable/zeroable)",
    "ACES2065-1 linear gain",
    "stops",
)
GRAPH_DOT_WB_BANNED = (
    "WB (bypassable)",
    "scene-linear Bradford/CAT02",
    " tint ",
    "identity",
    "CAT(user→D65)",
    "，绿品",
)
GRAPH_EXP_WB_XML_BANNED = (
    "stops",
    "identity",
    "CAT(user→D65)",
    "default CAT is identity",
    "不把机内色温当光源",
)
GRAPH_EXP_XML_DESC_LOCKED = (
    "ACES2065-1 线性按档增益；不加减 Log 码值。独立节点；0 档不写进 IDT/白平衡。"
)
GRAPH_WB_XML_DESC_LOCKED = (
    "机内色温/绿品只填旋钮；默认单位阵（不把机内 5600/6504 当光源去校正）。"
    "读不到则为待定/单位阵，不猜 5600 或 6504。"
    "旁路白平衡 = IDT → 曝光 → ACEScct，不烘焙。"
)
GRAPH_DOT_WB_LINE_LOCKED = "色温 {cctLabel}  绿品 {tint}"
GRAPH_DOT_WB_SWIFT = "色温 \\(cctLabel(cct))  绿品 \\(tint)"
GRAPH_DOT_CLIP_LABEL_LOCKED = "素材\\n相机 Log"
GRAPH_DOT_WORKING_SPACE_LOCKED = "工作空间"
GRAPH_IDT_XML_DESC_LOCKED = (
    "相机 Log 经 ACES2065-1 到 ACEScct。不含白平衡、不含曝光。"
)
GRAPH_IDT_XML_DESC_FROM = (
    "Camera log to ACEScct via ACES2065-1. No white balance, no exposure."
)
GRAPH_IDT_XML_DESC_FROM_PY_TAIL = (
    "ACES workflow. Exposure is its own node (not baked into IDT)."
)
GRAPH_DOT_CLIP_WS_BANNED = (
    "Clip\\ncamera log",
    "camera log",
    "working space",
    GRAPH_IDT_XML_DESC_FROM,
    GRAPH_IDT_XML_DESC_FROM_PY_TAIL,
)
GRAPH_DOT_IDT_THIRD_LOCKED = "或 ACES IDT / CST → ACEScct"
GRAPH_DOT_ODT_HEAD_LOCKED = "709 预览（后续节点）"
GRAPH_DOT_TIMELINE_LABEL_LOCKED = "时间线\\nACEScct"
GRAPH_DOT_IDT_THIRD_FROM_SWIFT = "or ACES IDT / CST → ACEScct"
GRAPH_DOT_IDT_THIRD_FROM_PY = "or Resolve CST → ACEScct (ACES workflow)"
GRAPH_DOT_ODT_HEAD_FROM = "709 预览 (later node)"
GRAPH_DOT_TIMELINE_FROM = "Timeline\\nACEScct"
GRAPH_DOT_IDT_ODT_TL_BANNED = (
    GRAPH_DOT_IDT_THIRD_FROM_SWIFT,
    GRAPH_DOT_IDT_THIRD_FROM_PY,
    "or Resolve CST",
    "later node",
    GRAPH_DOT_TIMELINE_FROM,
    'label="Timeline',
)
GRAPH_DOT_ODT_CST_LOCKED = "或 CST ACEScct → Rec.709"
GRAPH_DOT_ODT_CST_FROM = "or CST ACEScct → Rec.709"
README_GRAPH_INPUT_TO = "输入：相机 Log / 相机色域"
README_GRAPH_INPUT_FROM = "Input: camera log / camera gamut"
README_GRAPH_INPUT_BANNED = "Input: camera log"
README_GRAPH_INPUT_SWIFT = "- 输入：相机 Log / 相机色域 (`\\(idtList)`)"
README_GRAPH_INPUT_PY = "- 输入：相机 Log / 相机色域 (`{idt_list}`)"
README_APPLY_ODT_HEAD = (
    "Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709)"
)
README_APPLY_ODT_TRAIL_TO = (
    "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
)
README_APPLY_ODT_TRAIL_FROM = (
    "if you need a **709 预览** viewing node (not ACES OT). 预览·非成片."
)
README_APPLY_ODT_LINE = (
    "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
    "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
)
README_APPLY_ODT_BANNED = ("viewing node", "if you need")
README_FILES_GRAPH_DOT_TO = "同一图的 Graphviz"
README_FILES_GRAPH_DOT_FROM = "Graphviz of the same graph"
README_FILES_GRAPH_DOT_ROW = "| `graph.dot` | 同一图的 Graphviz |"
README_FILES_GRAPH_DOT_BANNED = "Graphviz of the same graph"
README_FILES_GRAPH_XML_SWIFT_TO = "机器可读节点图（可旁路白平衡）"
README_FILES_GRAPH_XML_PY_TO = "机器可读节点图（可旁路曝光 + 白平衡）"
README_FILES_GRAPH_XML_SWIFT_FROM = "Machine-readable node graph (bypassable WB)"
README_FILES_GRAPH_XML_PY_FROM = (
    "Machine-readable node graph (bypassable Exposure + WB)"
)
README_FILES_GRAPH_XML_BANNED = "Machine-readable node graph"
README_FILES_ROW_XML_SWIFT = "| `graph.xml` | 机器可读节点图（可旁路白平衡） |"
README_FILES_ROW_XML_PY = (
    "| `graph.xml` | 机器可读节点图（可旁路曝光 + 白平衡） |"
)
README_FILES_IDT_SWIFT_TO = "IDT 查找表（不含白平衡）"
README_FILES_IDT_PY_TO = "IDT 查找表（不含白平衡、不含曝光）"
README_FILES_IDT_SWIFT_FROM = "IDT LUT (no WB)"
README_FILES_IDT_PY_FROM = "IDT LUT (no WB, no exposure)"
README_FILES_IDT_BANNED = "IDT LUT"
README_FILES_ROW_IDT_SWIFT = "| `01_IDT_<idt>.cube` | IDT 查找表（不含白平衡） |"
README_FILES_ROW_IDT_PY = "| `01_IDT_<idt>.cube` | IDT 查找表（不含白平衡、不含曝光） |"
README_FILES_ROW_EXP_CUBE = (
    "| `02_Exposure.cube` | Exposure 1D LUT (ACEScct-wrapped linear gain) |"
)
README_FILES_ROW_EXP_DCTL = (
    "| `02_Exposure.dctl` | Exposure as DCTL (linear gain) |"
)
README_FILES_ROW_WB_CUBE = (
    "| `03_WB.cube` | WB LUT (Bradford CAT, ACEScct-wrapped) |"
)
README_FILES_ROW_WB_CDL = (
    "| `03_WB.cdl` / `03_WB.ccc` | WB as ASC CDL Color Corrector |"
)
README_FILES_ROW_WB_DCTL = "| `03_WB.dctl` | WB as DCTL (exact 3×3) |"
README_FILES_ROW_ODT = (
    "| `04_ODT_Rec709.cube` | 709 预览 (BT.709 OETF, not ACES OT) |"
)
README_FILES_README_TO = "本说明"
README_FILES_README_FROM = "This file"
README_FILES_README_BANNED = "This file"
README_FILES_ROW_README = "| `README_RESOLVE.md` | 本说明 |"
README_COLOR_PAGE_TITLE_TO = "调色页，串行节点图："
README_COLOR_PAGE_TITLE_FROM = "Color page, serial node graph:"
README_COLOR_PAGE_TITLE_BANNED = "Color page, serial node graph"
README_FILES_HEADER_TO = "| 文件 | 作用 |"
README_FILES_HEADER_FROM = "| File | Role |"
README_FILES_HEADER_BANNED = "| File | Role |"


def _dot_node_label(dot: str, node: str) -> str:
    match = re.search(rf'{re.escape(node)}\s+\[[^\]]*label="([^"]*)"', dot)
    assert match, f"graph.dot missing {node} label"
    return match.group(1)


def _xml_node_description(xml: str, name: str) -> str:
    block = xml.split(f'name="{name}"', 1)[1].split("</Node>", 1)[0]
    return block.split("<Description>", 1)[1].split("</Description>", 1)[0]


def test_graph_dot_xml_exposure_wb_plain_chinese(tmp_path: Path):
    """graphDOT / XML ㉗: Exposure·WB 人话. ⑮–㉖ + TITLE / filenames / 色管 frozen."""
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_DOT_WB_LINE == "色温 {cctLabel}  绿品 {tint}"
    assert "  绿品" in GRAPH_DOT_WB_LINE
    assert "，绿品" not in GRAPH_DOT_WB_LINE
    assert GRAPH_DOT_WB_FILE == "03_WB.cube / .cdl / .ccc / .dctl"
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert "不把机内 5600/6504 当光源去校正" in GRAPH_WB_XML_DESC
    assert "不把机内色温当光源" not in GRAPH_WB_XML_DESC

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    dot = (tmp_path / "graph.dot").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    wb_cube = (tmp_path / "03_WB.cube").read_text(encoding="utf-8")

    exp_label = _dot_node_label(dot, "exp")
    wb_label = _dot_node_label(dot, "wb")
    assert exp_label == "曝光（可归零）\\n+1.50 档\\n02_Exposure.cube / .dctl"
    assert wb_label == GRAPH_DOT_WB_HEAD + "\\n" + GRAPH_DOT_WB_LINE.format(
        cctLabel="3200 K", tint=0.25
    ) + "\\n" + GRAPH_DOT_WB_FILE
    assert "色温 3200 K  绿品 0.25" in wb_label
    assert "色温 3200 K，绿品" not in wb_label
    generated_dot = format_dot(
        ["arri_logc4_awg4"], 3200.0, 0.25, True, exposure_stops=1.5
    )
    assert _dot_node_label(generated_dot, "exp") == exp_label
    assert _dot_node_label(generated_dot, "wb") == wb_label
    zero_dot = format_dot(["arri_logc4_awg4"], 3200.0, 0.0, True, exposure_stops=0.0)
    assert _dot_node_label(zero_dot, "exp") == (
        "曝光（可归零）\\n+0.00 档\\n02_Exposure.cube / .dctl"
    )

    exp_desc = _xml_node_description(xml, "Exposure")
    wb_desc = _xml_node_description(xml, "WB")
    assert exp_desc == GRAPH_EXP_XML_DESC_LOCKED
    assert wb_desc == GRAPH_WB_XML_DESC_LOCKED
    generated_xml = format_graph_xml(
        ["arri_logc4_awg4"], 3200.0, 0.25, include_wb=True
    )
    assert _xml_node_description(generated_xml, "Exposure") == GRAPH_EXP_XML_DESC
    assert _xml_node_description(generated_xml, "WB") == GRAPH_WB_XML_DESC
    assert 'stops="' in xml
    assert "<Stops>" in xml

    for token in GRAPH_DOT_EXP_BANNED:
        assert token not in exp_label, token
    for token in GRAPH_DOT_WB_BANNED:
        assert token not in wb_label, token
    for token in GRAPH_EXP_WB_XML_BANNED:
        assert token not in exp_desc, token
        assert token not in wb_desc, token
        assert token not in GRAPH_EXP_XML_DESC, token
        assert token not in GRAPH_WB_XML_DESC, token

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    note_fn = swift.split("static func exportNote")[1].split("static func export(")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    wb_fn = swift.split("private static func wbCube")[1].split(
        "private static func odtCube"
    )[0]

    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "{GRAPH_EXP_XML_DESC}" in py_xml
    assert "{GRAPH_WB_XML_DESC}" in py_xml
    assert "曝光（可归零）" in dot_fn
    assert 'String(format: "%+.2f", exposureStops)) 档' in dot_fn
    assert "02_Exposure.cube / .dctl" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert GRAPH_DOT_WB_SWIFT in dot_fn
    assert "03_WB.cube / .cdl / .ccc / .dctl" in dot_fn
    assert "色温 \\(cctLabel(cct))，绿品" not in dot_fn
    assert "GRAPH_DOT_EXP_HEAD" in py_dot
    assert "GRAPH_DOT_WB_LINE.format" in py_dot
    assert f'GRAPH_DOT_WB_LINE = "{GRAPH_DOT_WB_LINE_LOCKED}"' in py
    assert f'GRAPH_EXP_XML_DESC = (' in py or GRAPH_EXP_XML_DESC in py
    assert '"色温 {cctLabel}  绿品 {tint}"' in py
    assert "，绿品 {tint}" not in py_dot
    assert "Exposure (zeroable)" not in dot_fn
    assert "Exposure (bypassable" not in py_dot
    assert "ACES2065-1 linear gain" not in py_dot
    assert "WB (bypassable)" not in dot_fn
    assert "WB (bypassable)" not in py_dot
    assert "scene-linear Bradford/CAT02" not in dot_fn
    assert "scene-linear Bradford/CAT02" not in py_dot
    for token in ("identity", "CAT(user→D65)", "default CAT is identity"):
        assert token not in exp_label
        assert token not in wb_label
        assert token not in exp_desc
        assert token not in wb_desc
        assert token not in xml_fn
        assert token not in _xml_node_description(py_xml, "Exposure")
        # py_xml interpolates constants; lock the constant values instead.
    assert "identity" not in GRAPH_EXP_XML_DESC
    assert "identity" not in GRAPH_WB_XML_DESC
    assert "CAT(user→D65)" not in GRAPH_EXP_XML_DESC
    assert "CAT(user→D65)" not in GRAPH_WB_XML_DESC
    assert "stops" not in GRAPH_EXP_XML_DESC
    assert "stops" not in GRAPH_WB_XML_DESC
    assert "stops" not in exp_label
    assert "stops" not in wb_label

    # ㉖ exportNote 预览输出 + ㉕ honesty / Graph WB 一字不动.
    assert EXPORT_NOTE_ODT == EXPORT_NOTE_ODT_LOCKED
    assert EXPORT_NOTE_ODT in note_fn
    assert EXPORT_NOTE_IN_CAMERA in readme_fn
    assert GRAPH_WB_SUMMARY == GRAPH_WB_SUMMARY_LOCKED
    assert GRAPH_WB_SWIFT in readme_fn

    # FROZEN: cube TITLE (incl. pending/identity), filenames, 色管, stops= attrs.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert wb_cube.splitlines()[0].startswith(f'TITLE "{WB_CUBE_TITLE_HEAD}')
    assert '?? "pending / identity"' in wb_fn
    assert 'name="Exposure" type="Gain_1D" bypassable="true"' in xml
    assert 'name="WB" type="Corrector" bypassable="true"' in xml
    assert 'stops="1.500000"' in xml
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in exp_desc
    assert "达芬奇已验证" not in wb_desc
    assert "达芬奇已验证" not in exp_label
    assert "达芬奇已验证" not in wb_label
    _assert_chengpian_not_a_deliverable_claim(exp_desc)
    _assert_chengpian_not_a_deliverable_claim(wb_desc)
    _assert_chengpian_not_a_deliverable_claim(exp_label)
    _assert_chengpian_not_a_deliverable_claim(wb_label)


def test_graph_dot_xml_clip_working_space_idt_plain_chinese(tmp_path: Path):
    """graphDOT / XML ㉘: Clip / working space / IDT 人话. ㉗ + TITLE / filenames / 色管 frozen."""
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == "素材\\n相机 Log"
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == "工作空间"
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_IDT_XML_DESC == (
        "相机 Log 经 ACES2065-1 到 ACEScct。不含白平衡、不含曝光。"
    )

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    dot = (tmp_path / "graph.dot").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    wb_cube = (tmp_path / "03_WB.cube").read_text(encoding="utf-8")

    clip_label = _dot_node_label(dot, "clip")
    assert clip_label == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert 'clip [label="素材\\n相机 Log"]' in dot
    assert 'label="工作空间"' in dot
    generated_dot = format_dot(
        ["arri_logc4_awg4"], 3200.0, 0.25, True, exposure_stops=1.5
    )
    assert _dot_node_label(generated_dot, "clip") == GRAPH_DOT_CLIP_LABEL
    assert f'label="{GRAPH_DOT_WORKING_SPACE}"' in generated_dot
    assert _dot_node_label(generated_dot, "clip") == clip_label

    idt_desc = _xml_node_description(xml, "IDT")
    assert idt_desc == GRAPH_IDT_XML_DESC_LOCKED
    generated_xml = format_graph_xml(
        ["arri_logc4_awg4"], 3200.0, 0.25, include_wb=True
    )
    assert _xml_node_description(generated_xml, "IDT") == GRAPH_IDT_XML_DESC
    assert f"<Description>{GRAPH_IDT_XML_DESC_LOCKED}</Description>" in xml
    assert f"<Description>{GRAPH_IDT_XML_DESC_LOCKED}</Description>" in generated_xml

    for token in GRAPH_DOT_CLIP_WS_BANNED:
        assert token not in clip_label, token
        assert token not in idt_desc, token
        assert token not in GRAPH_DOT_CLIP_LABEL, token
        assert token not in GRAPH_DOT_WORKING_SPACE, token
        assert token not in GRAPH_IDT_XML_DESC, token

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    wb_fn = swift.split("private static func wbCube")[1].split(
        "private static func odtCube"
    )[0]

    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert "GRAPH_DOT_CLIP_LABEL" in py_dot
    assert "GRAPH_DOT_WORKING_SPACE" in py_dot
    assert r'GRAPH_DOT_CLIP_LABEL = "素材\\n相机 Log"' in py
    assert f'GRAPH_DOT_WORKING_SPACE = "{GRAPH_DOT_WORKING_SPACE_LOCKED}"' in py
    assert GRAPH_IDT_XML_DESC_LOCKED in py

    for token in GRAPH_DOT_CLIP_WS_BANNED:
        assert token not in clip_label, token
        assert token not in idt_desc, token
        assert token not in xml_fn, token
        assert token not in _xml_node_description(generated_xml, "IDT"), token
    assert "camera log" not in dot_fn
    assert "working space" not in dot_fn
    assert "camera log" not in py_dot
    assert "working space" not in py_dot
    assert GRAPH_IDT_XML_DESC_FROM not in xml_fn
    assert GRAPH_IDT_XML_DESC_FROM not in py_xml
    assert GRAPH_IDT_XML_DESC_FROM_PY_TAIL not in py_xml
    assert GRAPH_IDT_XML_DESC_FROM not in xml
    assert GRAPH_IDT_XML_DESC_FROM_PY_TAIL not in xml
    assert r"Clip\\ncamera log" not in dot_fn
    assert "Clip\\ncamera log" not in dot
    assert "Clip\\ncamera log" not in generated_dot

    # ㉗ four locked DOT/XML strings 一字不动.
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert GRAPH_DOT_WB_SWIFT in dot_fn
    assert _dot_node_label(dot, "exp") == (
        "曝光（可归零）\\n+1.50 档\\n02_Exposure.cube / .dctl"
    )
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED

    # FROZEN: cube TITLE (incl. pending/identity), filenames, 色管, stops= attrs.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert wb_cube.splitlines()[0].startswith(f'TITLE "{WB_CUBE_TITLE_HEAD}')
    assert '?? "pending / identity"' in wb_fn
    assert 'name="Exposure" type="Gain_1D" bypassable="true"' in xml
    assert 'name="WB" type="Corrector" bypassable="true"' in xml
    assert 'name="IDT" type="LUT_or_CST" bypassable="false"' in xml
    assert 'stops="1.500000"' in xml
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in clip_label
    assert "达芬奇已验证" not in idt_desc
    assert "达芬奇已验证" not in GRAPH_IDT_XML_DESC
    _assert_chengpian_not_a_deliverable_claim(clip_label)
    _assert_chengpian_not_a_deliverable_claim(idt_desc)
    _assert_chengpian_not_a_deliverable_claim(GRAPH_IDT_XML_DESC)


def test_graph_dot_idt_odt_timeline_plain_chinese(tmp_path: Path):
    """graphDOT ㉙: idt/odt/timeline 人话. ㉗+㉘ + TITLE / XML Desc / 色管 frozen."""
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_IDT_THIRD == "或 ACES IDT / CST → ACEScct"
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == "709 预览（后续节点）"
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == "时间线\\nACEScct"

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    dot = (tmp_path / "graph.dot").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    wb_cube = (tmp_path / "03_WB.cube").read_text(encoding="utf-8")

    idt_label = _dot_node_label(dot, "idt")
    odt_label = _dot_node_label(dot, "odt")
    timeline_label = _dot_node_label(dot, "timeline")
    idt_lines = idt_label.split("\\n")
    odt_lines = odt_label.split("\\n")
    assert idt_lines[3] == GRAPH_DOT_IDT_THIRD_LOCKED
    assert odt_lines[0] == GRAPH_DOT_ODT_HEAD_LOCKED
    assert odt_lines[1] == "04_ODT_Rec709.cube"
    assert odt_lines[2] == GRAPH_DOT_ODT_CST_LOCKED
    assert odt_lines[3] == GRAPH_ODT_USER
    assert timeline_label == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    generated_dot = format_dot(
        ["arri_logc4_awg4"], 3200.0, 0.25, True, exposure_stops=1.5
    )
    assert _dot_node_label(generated_dot, "idt").split("\\n")[3] == GRAPH_DOT_IDT_THIRD
    assert _dot_node_label(generated_dot, "odt").split("\\n")[0] == GRAPH_DOT_ODT_HEAD
    assert _dot_node_label(generated_dot, "timeline") == GRAPH_DOT_TIMELINE_LABEL
    assert _dot_node_label(generated_dot, "idt") == idt_label
    assert _dot_node_label(generated_dot, "odt") == odt_label
    assert _dot_node_label(generated_dot, "timeline") == timeline_label

    for token in GRAPH_DOT_IDT_ODT_TL_BANNED:
        assert token not in idt_lines[3], token
        assert token not in odt_lines[0], token
        assert token not in timeline_label, token
        assert token not in GRAPH_DOT_IDT_THIRD, token
        assert token not in GRAPH_DOT_ODT_HEAD, token
        assert token not in GRAPH_DOT_TIMELINE_LABEL, token
    assert not idt_lines[3].startswith("or ")
    assert "Timeline" not in timeline_label
    assert "later node" not in odt_lines[0]
    assert "（" in odt_lines[0] and "）" in odt_lines[0]
    assert "(" not in odt_lines[0] and ")" not in odt_lines[0]

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    wb_fn = swift.split("private static func wbCube")[1].split(
        "private static func odtCube"
    )[0]

    assert r"或 ACES IDT / CST → ACEScct" in dot_fn
    assert "709 预览（后续节点）" in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert "GRAPH_DOT_IDT_THIRD" in py_dot
    assert "GRAPH_DOT_ODT_HEAD" in py_dot
    assert "GRAPH_DOT_TIMELINE_LABEL" in py_dot
    assert f'GRAPH_DOT_IDT_THIRD = "{GRAPH_DOT_IDT_THIRD_LOCKED}"' in py
    assert f'GRAPH_DOT_ODT_HEAD = "{GRAPH_DOT_ODT_HEAD_LOCKED}"' in py
    assert r'GRAPH_DOT_TIMELINE_LABEL = "时间线\\nACEScct"' in py
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot

    for token in GRAPH_DOT_IDT_ODT_TL_BANNED:
        assert token not in idt_lines[3], token
        assert token not in odt_lines[0], token
        assert token not in timeline_label, token
        assert token not in dot_fn, token
        assert token not in py_dot, token
    assert GRAPH_DOT_IDT_THIRD_FROM_SWIFT not in dot_fn
    assert GRAPH_DOT_IDT_THIRD_FROM_PY not in py_dot
    assert GRAPH_DOT_ODT_HEAD_FROM not in dot_fn
    assert GRAPH_DOT_ODT_HEAD_FROM not in py_dot
    assert GRAPH_DOT_TIMELINE_FROM not in dot_fn
    assert GRAPH_DOT_TIMELINE_FROM not in py_dot
    assert "Timeline" not in dot_fn
    assert "Timeline" not in py_dot
    assert "later node" not in dot_fn
    assert "later node" not in py_dot

    # ㉗ four locked DOT/XML strings 一字不动.
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert GRAPH_DOT_WB_SWIFT in dot_fn
    assert _dot_node_label(dot, "exp") == (
        "曝光（可归零）\\n+1.50 档\\n02_Exposure.cube / .dctl"
    )
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED

    # ㉘ three locked strings 一字不动.
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _dot_node_label(dot, "clip") == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED

    # FROZEN: cube TITLE, XML Desc beyond this knife, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_XML_DESC == GRAPH_ODT_USER
    assert GRAPH_ODT_USER in odt_label
    assert wb_cube.splitlines()[0].startswith(f'TITLE "{WB_CUBE_TITLE_HEAD}')
    assert '?? "pending / identity"' in wb_fn
    assert 'name="Exposure" type="Gain_1D" bypassable="true"' in xml
    assert 'name="WB" type="Corrector" bypassable="true"' in xml
    assert 'name="IDT" type="LUT_or_CST" bypassable="false"' in xml
    assert 'stops="1.500000"' in xml
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in idt_lines[3]
    assert "达芬奇已验证" not in odt_lines[0]
    assert "达芬奇已验证" not in timeline_label
    _assert_chengpian_not_a_deliverable_claim(idt_lines[3])
    _assert_chengpian_not_a_deliverable_claim(odt_lines[0])
    _assert_chengpian_not_a_deliverable_claim(timeline_label)


def test_graph_dot_odt_cst_plain_chinese(tmp_path: Path):
    """graphDOT ㉚: odt CST 人话. ㉗+㉘+㉙ + TITLE / XML Desc / 色管 frozen."""
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_FROM == "or CST ACEScct → Rec.709"

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    dot = (tmp_path / "graph.dot").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    wb_cube = (tmp_path / "03_WB.cube").read_text(encoding="utf-8")

    odt_label = _dot_node_label(dot, "odt")
    odt_lines = odt_label.split("\\n")
    assert odt_lines[0] == GRAPH_DOT_ODT_HEAD_LOCKED
    assert odt_lines[1] == "04_ODT_Rec709.cube"
    assert odt_lines[2] == GRAPH_DOT_ODT_CST_LOCKED
    assert odt_lines[3] == GRAPH_ODT_USER
    generated_dot = format_dot(
        ["arri_logc4_awg4"], 3200.0, 0.25, True, exposure_stops=1.5
    )
    assert _dot_node_label(generated_dot, "odt").split("\\n")[2] == GRAPH_DOT_ODT_CST_LOCKED
    assert _dot_node_label(generated_dot, "odt") == odt_label

    assert not odt_lines[2].startswith("or ")
    assert odt_lines[2].startswith("或 ")
    assert GRAPH_DOT_ODT_CST_FROM not in odt_lines[2]

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    wb_fn = swift.split("private static func wbCube")[1].split(
        "private static func odtCube"
    )[0]

    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    # README / other ODT lines keep English or CST (not this knife).
    assert GRAPH_DOT_ODT_CST_FROM in readme_fn
    assert GRAPH_DOT_ODT_CST_FROM in py_readme

    # ㉗ four locked DOT/XML strings 一字不动.
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert GRAPH_DOT_WB_SWIFT in dot_fn
    assert _dot_node_label(dot, "exp") == (
        "曝光（可归零）\\n+1.50 档\\n02_Exposure.cube / .dctl"
    )
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED

    # ㉘ three locked strings 一字不动.
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _dot_node_label(dot, "clip") == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED

    # ㉙ three locked strings 一字不动.
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert r"或 ACES IDT / CST → ACEScct" in dot_fn
    assert "709 预览（后续节点）" in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert _dot_node_label(dot, "idt").split("\\n")[3] == GRAPH_DOT_IDT_THIRD_LOCKED
    assert odt_lines[0] == GRAPH_DOT_ODT_HEAD_LOCKED
    assert _dot_node_label(dot, "timeline") == GRAPH_DOT_TIMELINE_LABEL_LOCKED

    # FROZEN: cube TITLE, XML Desc, filenames, 色管, other ODT lines.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_XML_DESC == GRAPH_ODT_USER
    assert GRAPH_ODT_USER in odt_label
    assert wb_cube.splitlines()[0].startswith(f'TITLE "{WB_CUBE_TITLE_HEAD}')
    assert '?? "pending / identity"' in wb_fn
    assert 'name="Exposure" type="Gain_1D" bypassable="true"' in xml
    assert 'name="WB" type="Corrector" bypassable="true"' in xml
    assert 'name="IDT" type="LUT_or_CST" bypassable="false"' in xml
    assert 'stops="1.500000"' in xml
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in odt_lines[2]
    _assert_chengpian_not_a_deliverable_claim(odt_lines[2])


def test_readme_graph_input_plain_chinese(tmp_path: Path):
    """README Graph ㉛: 输入行人话. ㉗–㉚ + Apply / TITLE / XML Desc / 色管 frozen."""
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_FROM == "Input: camera log / camera gamut"
    assert README_GRAPH_INPUT_BANNED == "Input: camera log"
    assert README_GRAPH_INPUT_SWIFT == "- 输入：相机 Log / 相机色域 (`\\(idtList)`)"
    assert README_GRAPH_INPUT_PY == "- 输入：相机 Log / 相机色域 (`{idt_list}`)"

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = readme.split("## How to bypass", 1)[1]

    input_line = next(
        ln.strip()
        for ln in graph.splitlines()
        if "相机色域" in ln or "camera gamut" in ln or ln.strip().lstrip("- ").startswith("Input:")
    )
    assert input_line == "- 输入：相机 Log / 相机色域 (`arri_logc4_awg4`)"
    assert README_GRAPH_INPUT_TO in input_line
    assert README_GRAPH_INPUT_BANNED not in input_line
    assert README_GRAPH_INPUT_FROM not in graph
    assert README_GRAPH_INPUT_BANNED not in graph
    assert README_GRAPH_INPUT_BANNED not in readme

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_graph = _graph_section(generated)
    generated_line = next(
        ln.strip() for ln in generated_graph.splitlines() if "相机色域" in ln
    )
    assert generated_line == input_line
    empty = format_readme([], 3200.0, 0.0, True)
    empty_line = next(
        ln.strip() for ln in _graph_section(empty).splitlines() if "相机色域" in ln
    )
    assert empty_line == (
        "- 输入：相机 Log / 相机色域 (`（无 — 请在达芬奇 CST 里指定 IDT）`)"
    )

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = readme_fn.split("## How to bypass", 1)[1]
    py_apply = py_readme.split("## How to bypass", 1)[1]

    # 验法㉛-1: one TO 一字不差. Swift↔Py 标签一致；插值不动.
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in swift_graph
    assert README_GRAPH_INPUT_TO in py_graph
    assert "`\\(idtList)`" in swift_graph
    assert "`{idt_list}`" in py_graph
    assert README_GRAPH_INPUT_FROM not in swift_graph
    assert README_GRAPH_INPUT_FROM not in py_graph
    assert README_GRAPH_INPUT_BANNED not in swift_graph
    assert README_GRAPH_INPUT_BANNED not in py_graph
    assert README_GRAPH_INPUT_BANNED not in readme_fn
    assert README_GRAPH_INPUT_BANNED not in py_readme

    # Apply 整段另刀：英文 Apply 块一字不动.
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **ODT**" in swift_apply
    assert GRAPH_DOT_ODT_CST_FROM in swift_apply
    assert GRAPH_DOT_ODT_CST_FROM in py_apply
    assert GRAPH_DOT_ODT_CST_FROM in readme_fn
    assert GRAPH_DOT_ODT_CST_FROM in py_readme

    # ㉗–㉚ locked DOT/XML strings 一字不动.
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in input_line
    assert "达芬奇已验证" not in graph
    _assert_chengpian_not_a_deliverable_claim(input_line)


def test_readme_apply_odt_plain_chinese(tmp_path: Path):
    """README Apply ㉜: ODT 行尾查看节点人话. ㉗–㉛ + 行头 / TITLE / XML / 色管 frozen."""
    assert README_APPLY_ODT_HEAD == (
        "Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709)"
    )
    assert README_APPLY_ODT_TRAIL_TO == (
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert README_APPLY_ODT_TRAIL_FROM == (
        "if you need a **709 预览** viewing node (not ACES OT). 预览·非成片."
    )
    assert README_APPLY_ODT_LINE == (
        f"- {README_APPLY_ODT_HEAD} {README_APPLY_ODT_TRAIL_TO}"
    )
    assert README_APPLY_ODT_BANNED == ("viewing node", "if you need")

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    odt_line = _apply_odt_line(readme)

    assert odt_line == README_APPLY_ODT_LINE
    assert odt_line.startswith(f"- {README_APPLY_ODT_HEAD} ")
    assert odt_line.endswith(README_APPLY_ODT_TRAIL_TO)
    assert README_APPLY_ODT_TRAIL_TO in odt_line
    assert README_APPLY_ODT_TRAIL_FROM not in odt_line
    assert README_APPLY_ODT_TRAIL_FROM not in apply
    assert README_APPLY_ODT_TRAIL_FROM not in readme
    for token in README_APPLY_ODT_BANNED:
        assert token not in odt_line, token
        assert token not in apply, token

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_apply = _apply_section(generated)
    generated_line = _apply_odt_line(generated)
    assert generated_line == odt_line
    assert generated_line == README_APPLY_ODT_LINE
    for token in README_APPLY_ODT_BANNED:
        assert token not in generated_line, token
        assert token not in generated_apply, token

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_odt = _apply_odt_line(readme_fn)
    py_odt = _apply_odt_line(py_readme)

    # 验法㉜-1: one TO 一字不差. Swift↔Py 该片段一致；行头冻.
    assert swift_odt == README_APPLY_ODT_LINE
    assert py_odt == README_APPLY_ODT_LINE
    assert swift_odt == py_odt
    assert README_APPLY_ODT_HEAD in swift_odt
    assert README_APPLY_ODT_HEAD in py_odt
    assert README_APPLY_ODT_TRAIL_TO in swift_odt
    assert README_APPLY_ODT_TRAIL_TO in py_odt
    assert README_APPLY_ODT_TRAIL_FROM not in swift_odt
    assert README_APPLY_ODT_TRAIL_FROM not in py_odt
    assert README_APPLY_ODT_TRAIL_FROM not in swift_apply
    assert README_APPLY_ODT_TRAIL_FROM not in py_apply
    assert GRAPH_DOT_ODT_CST_FROM in README_APPLY_ODT_HEAD
    assert GRAPH_DOT_ODT_CST_FROM in swift_odt
    assert GRAPH_DOT_ODT_CST_FROM in py_odt
    for token in README_APPLY_ODT_BANNED:
        assert token not in swift_odt, token
        assert token not in py_odt, token
        assert token not in swift_apply, token
        assert token not in py_apply, token

    # Apply 其余冻：IDT / Exposure / WB 英文不动.
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply
    assert "- Apply **Exposure**" in py_apply
    assert (
        "- Apply **IDT** (node 1: LUT `01_IDT_*.cube`, or ACES IDT / CST camera → ACEScct)."
        in swift_apply
    )
    assert (
        "- Apply **IDT** (node 1: LUT `01_IDT_*.cube`, or CST camera → ACEScct, ACES workflow)."
        in py_apply
    )
    assert (
        "- Apply **Exposure** (node 2: LUT `02_Exposure.cube` or DCTL `02_Exposure.dctl`). "
        "Zero stops or bypass = identity."
    ) in py_apply
    assert (
        "- Apply **WB** (node 3: LUT `03_WB.cube`, **or** DCTL `03_WB.dctl`, "
        "**or** import `03_WB.cdl` onto a Color Corrector)."
    ) in swift_apply
    assert (
        "- Apply **WB** (node 3: LUT `03_WB.cube`, **or** DCTL `03_WB.dctl`, "
        "**or** import `03_WB.cdl` onto a Color Corrector)."
    ) in py_apply

    # ㉗–㉛ locked strings 一字不动.
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in odt_line
    assert "达芬奇已验证" not in apply
    _assert_chengpian_not_a_deliverable_claim(odt_line)
    _assert_chengpian_not_a_deliverable_claim(README_APPLY_ODT_TRAIL_TO)


def test_readme_files_graph_dot_plain_chinese(tmp_path: Path):
    """README Files ㉝: graph.dot 格人话. ㉗–㉜ + TITLE / XML / 色管 / Files 其余行 frozen."""
    assert README_FILES_GRAPH_DOT_TO == "同一图的 Graphviz"
    assert README_FILES_GRAPH_DOT_FROM == "Graphviz of the same graph"
    assert README_FILES_GRAPH_DOT_ROW == "| `graph.dot` | 同一图的 Graphviz |"
    assert README_FILES_GRAPH_DOT_BANNED == README_FILES_GRAPH_DOT_FROM

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    files = _files_section(readme)
    dot_row = _files_graph_dot_row(readme)

    assert dot_row == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_TO in dot_row
    assert README_FILES_GRAPH_DOT_FROM not in dot_row
    assert README_FILES_GRAPH_DOT_FROM not in files
    assert README_FILES_GRAPH_DOT_FROM not in readme
    assert README_FILES_GRAPH_DOT_BANNED not in files
    assert README_FILES_GRAPH_DOT_BANNED not in readme

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_files = _files_section(generated)
    generated_row = _files_graph_dot_row(generated)
    assert generated_row == dot_row
    assert generated_row == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_FROM not in generated
    assert README_FILES_GRAPH_DOT_FROM not in generated_files

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_files = _files_section(readme_fn)
    py_files = _files_section(py_readme)
    swift_dot = _files_graph_dot_row(readme_fn)
    py_dot_row = _files_graph_dot_row(py_readme)

    # 验法㉝-1: one TO 一字不差. Swift↔Py 该格一致；Files 其余冻.
    assert swift_dot == README_FILES_GRAPH_DOT_ROW
    assert py_dot_row == README_FILES_GRAPH_DOT_ROW
    assert swift_dot == py_dot_row
    assert README_FILES_GRAPH_DOT_TO in swift_dot
    assert README_FILES_GRAPH_DOT_TO in py_dot_row
    assert README_FILES_GRAPH_DOT_FROM not in swift_dot
    assert README_FILES_GRAPH_DOT_FROM not in py_dot_row
    assert README_FILES_GRAPH_DOT_FROM not in swift_files
    assert README_FILES_GRAPH_DOT_FROM not in py_files
    assert README_FILES_GRAPH_DOT_FROM not in readme_fn
    assert README_FILES_GRAPH_DOT_FROM not in py_readme
    assert README_FILES_GRAPH_DOT_BANNED not in readme_fn
    assert README_FILES_GRAPH_DOT_BANNED not in py_readme

    # Files 其余行冻（Swift / Py 各自原句，不借此刀对齐）.
    assert README_FILES_ROW_XML_SWIFT in swift_files
    assert README_FILES_ROW_XML_PY in py_files
    assert README_FILES_ROW_IDT_SWIFT in swift_files
    assert README_FILES_ROW_IDT_PY in py_files
    assert README_FILES_ROW_EXP_CUBE in py_files
    assert README_FILES_ROW_EXP_DCTL in py_files
    assert README_FILES_ROW_EXP_CUBE not in swift_files
    assert README_FILES_ROW_WB_CUBE in swift_files
    assert README_FILES_ROW_WB_CUBE in py_files
    assert README_FILES_ROW_WB_CDL in swift_files
    assert README_FILES_ROW_WB_CDL in py_files
    assert README_FILES_ROW_WB_DCTL in swift_files
    assert README_FILES_ROW_WB_DCTL in py_files
    assert README_FILES_ROW_ODT in swift_files
    assert README_FILES_ROW_ODT in py_files
    assert README_FILES_ROW_README in swift_files
    assert README_FILES_ROW_README in py_files
    assert README_FILES_ROW_XML_PY in files
    assert README_FILES_ROW_IDT_PY in files
    assert README_FILES_ROW_EXP_CUBE in files
    assert README_FILES_ROW_WB_CUBE in files

    # ㉗–㉜ locked strings 一字不动.
    assert README_APPLY_ODT_LINE == (
        "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert _apply_odt_line(readme) == README_APPLY_ODT_LINE
    assert _apply_odt_line(readme_fn) == README_APPLY_ODT_LINE
    assert _apply_odt_line(py_readme) == README_APPLY_ODT_LINE
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in dot_row
    assert "达芬奇已验证" not in files
    _assert_chengpian_not_a_deliverable_claim(dot_row)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_GRAPH_DOT_TO)


def test_readme_color_page_title_plain_chinese(tmp_path: Path):
    """README ㉞: Color page title 人话. ㉗–㉝ + TITLE / XML / 色管 frozen."""
    assert README_COLOR_PAGE_TITLE_TO == "调色页，串行节点图："
    assert README_COLOR_PAGE_TITLE_FROM == "Color page, serial node graph:"
    assert README_COLOR_PAGE_TITLE_TO.endswith("：")
    assert README_COLOR_PAGE_TITLE_FROM.endswith(":")
    assert README_COLOR_PAGE_TITLE_BANNED == "Color page, serial node graph"
    assert README_COLOR_PAGE_TITLE_BANNED in README_COLOR_PAGE_TITLE_FROM

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    files = _files_section(readme)
    title = _color_page_title_line(readme)

    assert title == README_COLOR_PAGE_TITLE_TO
    assert README_COLOR_PAGE_TITLE_FROM not in title
    assert README_COLOR_PAGE_TITLE_FROM not in apply
    assert README_COLOR_PAGE_TITLE_FROM not in readme
    assert README_COLOR_PAGE_TITLE_BANNED not in apply
    assert README_COLOR_PAGE_TITLE_BANNED not in readme
    assert README_COLOR_PAGE_TITLE_BANNED not in graph
    assert README_COLOR_PAGE_TITLE_BANNED not in files

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_title = _color_page_title_line(generated)
    generated_apply = _apply_section(generated)
    assert generated_title == title
    assert generated_title == README_COLOR_PAGE_TITLE_TO
    assert README_COLOR_PAGE_TITLE_FROM not in generated
    assert README_COLOR_PAGE_TITLE_BANNED not in generated
    assert README_COLOR_PAGE_TITLE_BANNED not in generated_apply

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_files = _files_section(readme_fn)
    py_files = _files_section(py_readme)
    swift_title = _color_page_title_line(readme_fn)
    py_title = _color_page_title_line(py_readme)

    # 验法㉞-1: one TO 一字不差. Swift↔Py 该行一致；仅此标题行.
    assert swift_title == README_COLOR_PAGE_TITLE_TO
    assert py_title == README_COLOR_PAGE_TITLE_TO
    assert swift_title == py_title
    assert README_COLOR_PAGE_TITLE_FROM not in swift_title
    assert README_COLOR_PAGE_TITLE_FROM not in py_title
    assert README_COLOR_PAGE_TITLE_FROM not in readme_fn
    assert README_COLOR_PAGE_TITLE_FROM not in py_readme
    assert README_COLOR_PAGE_TITLE_FROM not in swift
    assert README_COLOR_PAGE_TITLE_FROM not in py
    assert README_COLOR_PAGE_TITLE_BANNED not in readme_fn
    assert README_COLOR_PAGE_TITLE_BANNED not in py_readme
    assert README_COLOR_PAGE_TITLE_BANNED not in swift
    assert README_COLOR_PAGE_TITLE_BANNED not in py
    assert README_COLOR_PAGE_TITLE_BANNED not in swift_apply
    assert README_COLOR_PAGE_TITLE_BANNED not in py_apply

    # ㉗–㉝ locked strings 一字不动（含 同一图的 Graphviz）.
    assert README_FILES_GRAPH_DOT_TO == "同一图的 Graphviz"
    assert README_FILES_GRAPH_DOT_ROW == "| `graph.dot` | 同一图的 Graphviz |"
    assert _files_graph_dot_row(readme) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(readme_fn) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(py_readme) == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_FROM not in swift_files
    assert README_FILES_GRAPH_DOT_FROM not in py_files
    assert README_APPLY_ODT_LINE == (
        "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert _apply_odt_line(readme) == README_APPLY_ODT_LINE
    assert _apply_odt_line(readme_fn) == README_APPLY_ODT_LINE
    assert _apply_odt_line(py_readme) == README_APPLY_ODT_LINE
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply
    assert README_FILES_ROW_XML_SWIFT in swift_files
    assert README_FILES_ROW_XML_PY in py_files
    assert README_FILES_ROW_README in swift_files
    assert README_FILES_ROW_README in py_files

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in title
    assert "达芬奇已验证" not in apply
    _assert_chengpian_not_a_deliverable_claim(title)
    _assert_chengpian_not_a_deliverable_claim(README_COLOR_PAGE_TITLE_TO)


def test_readme_files_header_plain_chinese(tmp_path: Path):
    """README Files ㉟: 表头 文件|作用. ㉗–㉞ + TITLE / XML / 色管 / Files 数据行 frozen."""
    assert README_FILES_HEADER_TO == "| 文件 | 作用 |"
    assert README_FILES_HEADER_FROM == "| File | Role |"
    assert README_FILES_HEADER_BANNED == "| File | Role |"
    assert README_FILES_HEADER_BANNED == README_FILES_HEADER_FROM

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    files = _files_section(readme)
    header = _files_header_row(readme)

    assert header == README_FILES_HEADER_TO
    assert README_FILES_HEADER_FROM not in header
    assert README_FILES_HEADER_FROM not in files
    assert README_FILES_HEADER_FROM not in readme
    assert README_FILES_HEADER_BANNED not in files
    assert README_FILES_HEADER_BANNED not in readme
    assert README_FILES_HEADER_BANNED not in graph
    assert README_FILES_HEADER_BANNED not in apply

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_header = _files_header_row(generated)
    generated_files = _files_section(generated)
    assert generated_header == header
    assert generated_header == README_FILES_HEADER_TO
    assert README_FILES_HEADER_FROM not in generated
    assert README_FILES_HEADER_BANNED not in generated
    assert README_FILES_HEADER_BANNED not in generated_files

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_files = _files_section(readme_fn)
    py_files = _files_section(py_readme)
    swift_header = _files_header_row(readme_fn)
    py_header = _files_header_row(py_readme)

    # 验法㉟-1: one TO 一字不差. Swift↔Py 该表头一致；仅此表头行.
    assert swift_header == README_FILES_HEADER_TO
    assert py_header == README_FILES_HEADER_TO
    assert swift_header == py_header
    assert README_FILES_HEADER_FROM not in swift_header
    assert README_FILES_HEADER_FROM not in py_header
    assert README_FILES_HEADER_FROM not in readme_fn
    assert README_FILES_HEADER_FROM not in py_readme
    assert README_FILES_HEADER_FROM not in swift
    assert README_FILES_HEADER_FROM not in py
    assert README_FILES_HEADER_BANNED not in readme_fn
    assert README_FILES_HEADER_BANNED not in py_readme
    assert README_FILES_HEADER_BANNED not in swift
    assert README_FILES_HEADER_BANNED not in py
    assert README_FILES_HEADER_BANNED not in swift_files
    assert README_FILES_HEADER_BANNED not in py_files

    # ㉗–㉞ locked strings 一字不动（含 调色页，串行节点图： / 同一图的 Graphviz）.
    assert README_COLOR_PAGE_TITLE_TO == "调色页，串行节点图："
    assert _color_page_title_line(readme) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(readme_fn) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(py_readme) == README_COLOR_PAGE_TITLE_TO
    assert README_COLOR_PAGE_TITLE_FROM not in readme_fn
    assert README_COLOR_PAGE_TITLE_FROM not in py_readme
    assert README_FILES_GRAPH_DOT_TO == "同一图的 Graphviz"
    assert README_FILES_GRAPH_DOT_ROW == "| `graph.dot` | 同一图的 Graphviz |"
    assert _files_graph_dot_row(readme) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(readme_fn) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(py_readme) == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_FROM not in swift_files
    assert README_FILES_GRAPH_DOT_FROM not in py_files
    assert README_APPLY_ODT_LINE == (
        "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert _apply_odt_line(readme) == README_APPLY_ODT_LINE
    assert _apply_odt_line(readme_fn) == README_APPLY_ODT_LINE
    assert _apply_odt_line(py_readme) == README_APPLY_ODT_LINE
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply

    # Files 数据行冻（Swift / Py 各自原句，不借此刀对齐）.
    assert README_FILES_ROW_XML_SWIFT in swift_files
    assert README_FILES_ROW_XML_PY in py_files
    assert README_FILES_ROW_IDT_SWIFT in swift_files
    assert README_FILES_ROW_IDT_PY in py_files
    assert README_FILES_ROW_EXP_CUBE in py_files
    assert README_FILES_ROW_EXP_DCTL in py_files
    assert README_FILES_ROW_EXP_CUBE not in swift_files
    assert README_FILES_ROW_WB_CUBE in swift_files
    assert README_FILES_ROW_WB_CUBE in py_files
    assert README_FILES_ROW_WB_CDL in swift_files
    assert README_FILES_ROW_WB_CDL in py_files
    assert README_FILES_ROW_WB_DCTL in swift_files
    assert README_FILES_ROW_WB_DCTL in py_files
    assert README_FILES_ROW_ODT in swift_files
    assert README_FILES_ROW_ODT in py_files
    assert README_FILES_ROW_README in swift_files
    assert README_FILES_ROW_README in py_files
    assert README_FILES_ROW_XML_PY in files
    assert README_FILES_ROW_IDT_PY in files
    assert README_FILES_ROW_EXP_CUBE in files
    assert README_FILES_ROW_WB_CUBE in files

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in header
    assert "达芬奇已验证" not in files
    _assert_chengpian_not_a_deliverable_claim(header)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_HEADER_TO)


def test_readme_files_graph_xml_plain_chinese(tmp_path: Path):
    """README Files ㊱: graph.xml Role 人话. Swift/Py 分锁. ㉗–㉟ + TITLE / XML / 色管 / Files 其余行 frozen."""
    assert README_FILES_GRAPH_XML_SWIFT_TO == "机器可读节点图（可旁路白平衡）"
    assert README_FILES_GRAPH_XML_PY_TO == "机器可读节点图（可旁路曝光 + 白平衡）"
    assert README_FILES_GRAPH_XML_SWIFT_FROM == (
        "Machine-readable node graph (bypassable WB)"
    )
    assert README_FILES_GRAPH_XML_PY_FROM == (
        "Machine-readable node graph (bypassable Exposure + WB)"
    )
    assert README_FILES_GRAPH_XML_BANNED == "Machine-readable node graph"
    assert README_FILES_ROW_XML_SWIFT == (
        "| `graph.xml` | 机器可读节点图（可旁路白平衡） |"
    )
    assert README_FILES_ROW_XML_PY == (
        "| `graph.xml` | 机器可读节点图（可旁路曝光 + 白平衡） |"
    )
    assert README_FILES_ROW_XML_SWIFT != README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_SWIFT_TO != README_FILES_GRAPH_XML_PY_TO
    assert README_FILES_GRAPH_XML_SWIFT_TO in README_FILES_ROW_XML_SWIFT
    assert README_FILES_GRAPH_XML_PY_TO in README_FILES_ROW_XML_PY
    assert "曝光" not in README_FILES_GRAPH_XML_SWIFT_TO
    assert "曝光 + 白平衡" in README_FILES_GRAPH_XML_PY_TO
    assert README_FILES_GRAPH_XML_BANNED in README_FILES_GRAPH_XML_SWIFT_FROM
    assert README_FILES_GRAPH_XML_BANNED in README_FILES_GRAPH_XML_PY_FROM

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    files = _files_section(readme)
    xml_row = _files_graph_xml_row(readme)

    assert xml_row == README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_PY_TO in xml_row
    assert README_FILES_GRAPH_XML_SWIFT_TO not in xml_row
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in xml_row
    assert README_FILES_GRAPH_XML_PY_FROM not in xml_row
    assert README_FILES_GRAPH_XML_BANNED not in xml_row
    assert README_FILES_GRAPH_XML_BANNED not in files
    assert README_FILES_GRAPH_XML_BANNED not in readme
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in files
    assert README_FILES_GRAPH_XML_PY_FROM not in files
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in readme
    assert README_FILES_GRAPH_XML_PY_FROM not in readme

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_files = _files_section(generated)
    generated_row = _files_graph_xml_row(generated)
    assert generated_row == xml_row
    assert generated_row == README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_BANNED not in generated
    assert README_FILES_GRAPH_XML_BANNED not in generated_files
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in generated
    assert README_FILES_GRAPH_XML_PY_FROM not in generated

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_files = _files_section(readme_fn)
    py_files = _files_section(py_readme)
    swift_xml = _files_graph_xml_row(readme_fn)
    py_xml_row = _files_graph_xml_row(py_readme)

    # 验法㊱-1: Swift / Py 各锁各 TO，不拉平.
    assert swift_xml == README_FILES_ROW_XML_SWIFT
    assert py_xml_row == README_FILES_ROW_XML_PY
    assert swift_xml != py_xml_row
    assert README_FILES_GRAPH_XML_SWIFT_TO in swift_xml
    assert README_FILES_GRAPH_XML_PY_TO in py_xml_row
    assert README_FILES_GRAPH_XML_PY_TO not in swift_xml
    assert README_FILES_GRAPH_XML_SWIFT_TO not in py_xml_row
    assert README_FILES_ROW_XML_PY not in swift_files
    assert README_FILES_ROW_XML_SWIFT not in py_files
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in swift_xml
    assert README_FILES_GRAPH_XML_PY_FROM not in py_xml_row
    assert README_FILES_GRAPH_XML_BANNED not in swift_xml
    assert README_FILES_GRAPH_XML_BANNED not in py_xml_row
    assert README_FILES_GRAPH_XML_BANNED not in swift_files
    assert README_FILES_GRAPH_XML_BANNED not in py_files
    assert README_FILES_GRAPH_XML_BANNED not in readme_fn
    assert README_FILES_GRAPH_XML_BANNED not in py_readme
    assert README_FILES_GRAPH_XML_BANNED not in swift
    assert README_FILES_GRAPH_XML_BANNED not in py
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in readme_fn
    assert README_FILES_GRAPH_XML_PY_FROM not in py_readme
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in swift
    assert README_FILES_GRAPH_XML_PY_FROM not in py

    # Files 其余行冻（含 表头 | 文件 | 作用 |；不借此刀对齐 IDT/曝光格）.
    assert _files_header_row(readme) == README_FILES_HEADER_TO
    assert _files_header_row(readme_fn) == README_FILES_HEADER_TO
    assert _files_header_row(py_readme) == README_FILES_HEADER_TO
    assert README_FILES_HEADER_FROM not in swift_files
    assert README_FILES_HEADER_FROM not in py_files
    assert README_FILES_ROW_IDT_SWIFT in swift_files
    assert README_FILES_ROW_IDT_PY in py_files
    assert README_FILES_ROW_EXP_CUBE in py_files
    assert README_FILES_ROW_EXP_DCTL in py_files
    assert README_FILES_ROW_EXP_CUBE not in swift_files
    assert README_FILES_ROW_WB_CUBE in swift_files
    assert README_FILES_ROW_WB_CUBE in py_files
    assert README_FILES_ROW_WB_CDL in swift_files
    assert README_FILES_ROW_WB_CDL in py_files
    assert README_FILES_ROW_WB_DCTL in swift_files
    assert README_FILES_ROW_WB_DCTL in py_files
    assert README_FILES_ROW_ODT in swift_files
    assert README_FILES_ROW_ODT in py_files
    assert README_FILES_ROW_README in swift_files
    assert README_FILES_ROW_README in py_files
    assert README_FILES_ROW_XML_PY in files
    assert README_FILES_ROW_IDT_PY in files
    assert README_FILES_ROW_EXP_CUBE in files
    assert README_FILES_ROW_WB_CUBE in files

    # ㉗–㉟ locked strings 一字不动（含 | 文件 | 作用 | / 调色页，串行节点图： / 同一图的 Graphviz）.
    assert README_FILES_HEADER_TO == "| 文件 | 作用 |"
    assert README_COLOR_PAGE_TITLE_TO == "调色页，串行节点图："
    assert _color_page_title_line(readme) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(readme_fn) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(py_readme) == README_COLOR_PAGE_TITLE_TO
    assert README_COLOR_PAGE_TITLE_FROM not in readme_fn
    assert README_COLOR_PAGE_TITLE_FROM not in py_readme
    assert README_FILES_GRAPH_DOT_TO == "同一图的 Graphviz"
    assert README_FILES_GRAPH_DOT_ROW == "| `graph.dot` | 同一图的 Graphviz |"
    assert _files_graph_dot_row(readme) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(readme_fn) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(py_readme) == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_FROM not in swift_files
    assert README_FILES_GRAPH_DOT_FROM not in py_files
    assert README_APPLY_ODT_LINE == (
        "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert _apply_odt_line(readme) == README_APPLY_ODT_LINE
    assert _apply_odt_line(readme_fn) == README_APPLY_ODT_LINE
    assert _apply_odt_line(py_readme) == README_APPLY_ODT_LINE
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in swift_xml
    assert "达芬奇已验证" not in py_xml_row
    assert "达芬奇已验证" not in files
    _assert_chengpian_not_a_deliverable_claim(swift_xml)
    _assert_chengpian_not_a_deliverable_claim(py_xml_row)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_GRAPH_XML_SWIFT_TO)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_GRAPH_XML_PY_TO)


def test_readme_files_readme_plain_chinese(tmp_path: Path):
    """README Files ㊲: README_RESOLVE Role 人话. Swift↔Py 该格一致. ㉗–㊱ + TITLE / XML / 色管 / Files 其余行 frozen."""
    assert README_FILES_README_TO == "本说明"
    assert README_FILES_README_FROM == "This file"
    assert README_FILES_README_BANNED == "This file"
    assert README_FILES_README_BANNED == README_FILES_README_FROM
    assert README_FILES_ROW_README == "| `README_RESOLVE.md` | 本说明 |"
    assert README_FILES_README_TO in README_FILES_ROW_README
    assert README_FILES_README_FROM not in README_FILES_ROW_README

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    files = _files_section(readme)
    readme_row = _files_readme_row(readme)

    assert readme_row == README_FILES_ROW_README
    assert README_FILES_README_TO in readme_row
    assert README_FILES_README_FROM not in readme_row
    assert README_FILES_README_FROM not in files
    assert README_FILES_README_FROM not in readme
    assert README_FILES_README_BANNED not in files
    assert README_FILES_README_BANNED not in readme

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_files = _files_section(generated)
    generated_row = _files_readme_row(generated)
    assert generated_row == readme_row
    assert generated_row == README_FILES_ROW_README
    assert README_FILES_README_FROM not in generated
    assert README_FILES_README_FROM not in generated_files
    assert README_FILES_README_BANNED not in generated
    assert README_FILES_README_BANNED not in generated_files

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_files = _files_section(readme_fn)
    py_files = _files_section(py_readme)
    swift_readme = _files_readme_row(readme_fn)
    py_readme_row = _files_readme_row(py_readme)
    swift_xml = _files_graph_xml_row(readme_fn)
    py_xml_row = _files_graph_xml_row(py_readme)

    # 验法㊲-1: one TO 一字不差. Swift↔Py 该格一致；Files 其余冻.
    assert swift_readme == README_FILES_ROW_README
    assert py_readme_row == README_FILES_ROW_README
    assert swift_readme == py_readme_row
    assert README_FILES_README_TO in swift_readme
    assert README_FILES_README_TO in py_readme_row
    assert README_FILES_README_FROM not in swift_readme
    assert README_FILES_README_FROM not in py_readme_row
    assert README_FILES_README_FROM not in swift_files
    assert README_FILES_README_FROM not in py_files
    assert README_FILES_README_FROM not in readme_fn
    assert README_FILES_README_FROM not in py_readme
    assert README_FILES_README_FROM not in swift
    assert README_FILES_README_FROM not in py
    assert README_FILES_README_BANNED not in swift_readme
    assert README_FILES_README_BANNED not in py_readme_row
    assert README_FILES_README_BANNED not in swift_files
    assert README_FILES_README_BANNED not in py_files
    assert README_FILES_README_BANNED not in readme_fn
    assert README_FILES_README_BANNED not in py_readme
    assert README_FILES_README_BANNED not in swift
    assert README_FILES_README_BANNED not in py

    # Files 其余行冻（含 graph.xml Swift/Py 分锁；不借此刀对齐 IDT/曝光格）.
    assert swift_xml == README_FILES_ROW_XML_SWIFT
    assert py_xml_row == README_FILES_ROW_XML_PY
    assert swift_xml != py_xml_row
    assert README_FILES_ROW_XML_SWIFT != README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_SWIFT_TO in swift_xml
    assert README_FILES_GRAPH_XML_PY_TO in py_xml_row
    assert README_FILES_GRAPH_XML_PY_TO not in swift_xml
    assert README_FILES_GRAPH_XML_SWIFT_TO not in py_xml_row
    assert README_FILES_ROW_XML_PY not in swift_files
    assert README_FILES_ROW_XML_SWIFT not in py_files
    assert README_FILES_GRAPH_XML_BANNED not in swift_files
    assert README_FILES_GRAPH_XML_BANNED not in py_files
    assert _files_header_row(readme) == README_FILES_HEADER_TO
    assert _files_header_row(readme_fn) == README_FILES_HEADER_TO
    assert _files_header_row(py_readme) == README_FILES_HEADER_TO
    assert README_FILES_HEADER_FROM not in swift_files
    assert README_FILES_HEADER_FROM not in py_files
    assert README_FILES_ROW_IDT_SWIFT in swift_files
    assert README_FILES_ROW_IDT_PY in py_files
    assert README_FILES_ROW_EXP_CUBE in py_files
    assert README_FILES_ROW_EXP_DCTL in py_files
    assert README_FILES_ROW_EXP_CUBE not in swift_files
    assert README_FILES_ROW_WB_CUBE in swift_files
    assert README_FILES_ROW_WB_CUBE in py_files
    assert README_FILES_ROW_WB_CDL in swift_files
    assert README_FILES_ROW_WB_CDL in py_files
    assert README_FILES_ROW_WB_DCTL in swift_files
    assert README_FILES_ROW_WB_DCTL in py_files
    assert README_FILES_ROW_ODT in swift_files
    assert README_FILES_ROW_ODT in py_files
    assert README_FILES_ROW_XML_PY in files
    assert README_FILES_ROW_IDT_PY in files
    assert README_FILES_ROW_EXP_CUBE in files
    assert README_FILES_ROW_WB_CUBE in files
    assert README_FILES_ROW_README in files

    # ㉗–㊱ locked strings 一字不动（含 graph.xml 机器可读分锁 / | 文件 | 作用 | / 调色页，串行节点图： / 同一图的 Graphviz）.
    assert README_FILES_GRAPH_XML_SWIFT_TO == "机器可读节点图（可旁路白平衡）"
    assert README_FILES_GRAPH_XML_PY_TO == "机器可读节点图（可旁路曝光 + 白平衡）"
    assert README_FILES_ROW_XML_SWIFT == (
        "| `graph.xml` | 机器可读节点图（可旁路白平衡） |"
    )
    assert README_FILES_ROW_XML_PY == (
        "| `graph.xml` | 机器可读节点图（可旁路曝光 + 白平衡） |"
    )
    assert _files_graph_xml_row(readme) == README_FILES_ROW_XML_PY
    assert _files_graph_xml_row(readme_fn) == README_FILES_ROW_XML_SWIFT
    assert _files_graph_xml_row(py_readme) == README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in swift_files
    assert README_FILES_GRAPH_XML_PY_FROM not in py_files
    assert README_FILES_GRAPH_XML_BANNED not in readme_fn
    assert README_FILES_GRAPH_XML_BANNED not in py_readme
    assert README_FILES_HEADER_TO == "| 文件 | 作用 |"
    assert README_COLOR_PAGE_TITLE_TO == "调色页，串行节点图："
    assert _color_page_title_line(readme) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(readme_fn) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(py_readme) == README_COLOR_PAGE_TITLE_TO
    assert README_COLOR_PAGE_TITLE_FROM not in readme_fn
    assert README_COLOR_PAGE_TITLE_FROM not in py_readme
    assert README_FILES_GRAPH_DOT_TO == "同一图的 Graphviz"
    assert README_FILES_GRAPH_DOT_ROW == "| `graph.dot` | 同一图的 Graphviz |"
    assert _files_graph_dot_row(readme) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(readme_fn) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(py_readme) == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_FROM not in swift_files
    assert README_FILES_GRAPH_DOT_FROM not in py_files
    assert README_APPLY_ODT_LINE == (
        "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert _apply_odt_line(readme) == README_APPLY_ODT_LINE
    assert _apply_odt_line(readme_fn) == README_APPLY_ODT_LINE
    assert _apply_odt_line(py_readme) == README_APPLY_ODT_LINE
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in readme_row
    assert "达芬奇已验证" not in files
    _assert_chengpian_not_a_deliverable_claim(readme_row)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_README_TO)


def test_readme_files_idt_plain_chinese(tmp_path: Path):
    """README Files ㊳: 01_IDT Role 人话. Swift/Py 分锁. ㉗–㊲ + TITLE / XML / 色管 / Files 其余行 frozen."""
    assert README_FILES_IDT_SWIFT_TO == "IDT 查找表（不含白平衡）"
    assert README_FILES_IDT_PY_TO == "IDT 查找表（不含白平衡、不含曝光）"
    assert README_FILES_IDT_SWIFT_FROM == "IDT LUT (no WB)"
    assert README_FILES_IDT_PY_FROM == "IDT LUT (no WB, no exposure)"
    assert README_FILES_IDT_BANNED == "IDT LUT"
    assert README_FILES_ROW_IDT_SWIFT == (
        "| `01_IDT_<idt>.cube` | IDT 查找表（不含白平衡） |"
    )
    assert README_FILES_ROW_IDT_PY == (
        "| `01_IDT_<idt>.cube` | IDT 查找表（不含白平衡、不含曝光） |"
    )
    assert README_FILES_ROW_IDT_SWIFT != README_FILES_ROW_IDT_PY
    assert README_FILES_IDT_SWIFT_TO != README_FILES_IDT_PY_TO
    assert README_FILES_IDT_SWIFT_TO in README_FILES_ROW_IDT_SWIFT
    assert README_FILES_IDT_PY_TO in README_FILES_ROW_IDT_PY
    assert "曝光" not in README_FILES_IDT_SWIFT_TO
    assert "不含曝光" in README_FILES_IDT_PY_TO
    assert "不含白平衡、不含曝光" in README_FILES_IDT_PY_TO
    assert README_FILES_IDT_BANNED in README_FILES_IDT_SWIFT_FROM
    assert README_FILES_IDT_BANNED in README_FILES_IDT_PY_FROM

    export_resolve_bundle(
        tmp_path,
        idt_ids=["arri_logc4_awg4"],
        include_wb=True,
        cct=3200.0,
        tint=0.25,
        exposure_stops=1.5,
        lut_size=5,
    )
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    xml = (tmp_path / "graph.xml").read_text(encoding="utf-8")
    cube = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    graph = _graph_section(readme)
    apply = _apply_section(readme)
    files = _files_section(readme)
    idt_row = _files_idt_row(readme)

    assert idt_row == README_FILES_ROW_IDT_PY
    assert README_FILES_IDT_PY_TO in idt_row
    assert README_FILES_IDT_SWIFT_TO not in idt_row
    assert README_FILES_ROW_IDT_SWIFT not in files
    assert README_FILES_IDT_SWIFT_FROM not in idt_row
    assert README_FILES_IDT_PY_FROM not in idt_row
    assert README_FILES_IDT_BANNED not in idt_row
    assert README_FILES_IDT_BANNED not in files
    assert README_FILES_IDT_BANNED not in readme
    assert README_FILES_IDT_SWIFT_FROM not in files
    assert README_FILES_IDT_PY_FROM not in files
    assert README_FILES_IDT_SWIFT_FROM not in readme
    assert README_FILES_IDT_PY_FROM not in readme

    generated = format_readme(["arri_logc4_awg4"], 3200.0, 0.25, True)
    generated_files = _files_section(generated)
    generated_row = _files_idt_row(generated)
    assert generated_row == idt_row
    assert generated_row == README_FILES_ROW_IDT_PY
    assert README_FILES_IDT_BANNED not in generated
    assert README_FILES_IDT_BANNED not in generated_files
    assert README_FILES_IDT_SWIFT_FROM not in generated
    assert README_FILES_IDT_PY_FROM not in generated
    assert README_FILES_ROW_IDT_SWIFT not in generated
    assert README_FILES_IDT_SWIFT_TO not in generated_row

    root = Path(__file__).resolve().parents[1]
    swift = (root / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift").read_text(
        encoding="utf-8"
    )
    py = (root / "color/resolve_export.py").read_text(encoding="utf-8")
    xml_fn = swift.split("private static func graphXML")[1].split(
        "private static func graphDOT"
    )[0]
    dot_fn = swift.split("private static func graphDOT")[1].split(
        "private static func readme"
    )[0]
    py_dot = py.split("def format_dot")[1].split("def format_graph_xml")[0]
    py_xml = py.split("def format_graph_xml")[1].split("def format_readme")[0]
    readme_fn = swift.split("private static func readme")[1].split(
        "/// Proxy sequence folder"
    )[0]
    py_readme = py.split("def format_readme")[1].split("def export_resolve_bundle")[0]
    swift_graph = _graph_section(readme_fn)
    py_graph = _graph_section(py_readme)
    swift_apply = _apply_section(readme_fn)
    py_apply = _apply_section(py_readme)
    swift_files = _files_section(readme_fn)
    py_files = _files_section(py_readme)
    swift_idt = _files_idt_row(readme_fn)
    py_idt_row = _files_idt_row(py_readme)
    swift_xml = _files_graph_xml_row(readme_fn)
    py_xml_row = _files_graph_xml_row(py_readme)
    swift_readme = _files_readme_row(readme_fn)
    py_readme_row = _files_readme_row(py_readme)

    # 验法㊳-1: Swift / Py 各锁各 TO，不拉平.
    assert swift_idt == README_FILES_ROW_IDT_SWIFT
    assert py_idt_row == README_FILES_ROW_IDT_PY
    assert swift_idt != py_idt_row
    assert README_FILES_IDT_SWIFT_TO in swift_idt
    assert README_FILES_IDT_PY_TO in py_idt_row
    assert README_FILES_IDT_PY_TO not in swift_idt
    assert README_FILES_IDT_SWIFT_TO not in py_idt_row
    assert README_FILES_ROW_IDT_PY not in swift_files
    assert README_FILES_ROW_IDT_SWIFT not in py_files
    assert "曝光" not in swift_idt
    assert "不含曝光" in py_idt_row
    assert README_FILES_IDT_SWIFT_FROM not in swift_idt
    assert README_FILES_IDT_PY_FROM not in py_idt_row
    assert README_FILES_IDT_BANNED not in swift_idt
    assert README_FILES_IDT_BANNED not in py_idt_row
    assert README_FILES_IDT_BANNED not in swift_files
    assert README_FILES_IDT_BANNED not in py_files
    assert README_FILES_IDT_BANNED not in readme_fn
    assert README_FILES_IDT_BANNED not in py_readme
    assert README_FILES_IDT_BANNED not in swift
    assert README_FILES_IDT_BANNED not in py
    assert README_FILES_IDT_SWIFT_FROM not in readme_fn
    assert README_FILES_IDT_PY_FROM not in py_readme
    assert README_FILES_IDT_SWIFT_FROM not in swift
    assert README_FILES_IDT_PY_FROM not in py

    # Files 其余行冻（含 本说明 / graph.xml Swift/Py 分锁；不借此刀对齐曝光格）.
    assert swift_readme == README_FILES_ROW_README
    assert py_readme_row == README_FILES_ROW_README
    assert swift_readme == py_readme_row
    assert README_FILES_README_TO == "本说明"
    assert README_FILES_ROW_README == "| `README_RESOLVE.md` | 本说明 |"
    assert README_FILES_README_FROM not in swift_files
    assert README_FILES_README_FROM not in py_files
    assert swift_xml == README_FILES_ROW_XML_SWIFT
    assert py_xml_row == README_FILES_ROW_XML_PY
    assert swift_xml != py_xml_row
    assert README_FILES_ROW_XML_SWIFT != README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_SWIFT_TO in swift_xml
    assert README_FILES_GRAPH_XML_PY_TO in py_xml_row
    assert README_FILES_GRAPH_XML_PY_TO not in swift_xml
    assert README_FILES_GRAPH_XML_SWIFT_TO not in py_xml_row
    assert README_FILES_ROW_XML_PY not in swift_files
    assert README_FILES_ROW_XML_SWIFT not in py_files
    assert README_FILES_GRAPH_XML_BANNED not in swift_files
    assert README_FILES_GRAPH_XML_BANNED not in py_files
    assert _files_header_row(readme) == README_FILES_HEADER_TO
    assert _files_header_row(readme_fn) == README_FILES_HEADER_TO
    assert _files_header_row(py_readme) == README_FILES_HEADER_TO
    assert README_FILES_HEADER_FROM not in swift_files
    assert README_FILES_HEADER_FROM not in py_files
    assert README_FILES_ROW_EXP_CUBE in py_files
    assert README_FILES_ROW_EXP_DCTL in py_files
    assert README_FILES_ROW_EXP_CUBE not in swift_files
    assert README_FILES_ROW_WB_CUBE in swift_files
    assert README_FILES_ROW_WB_CUBE in py_files
    assert README_FILES_ROW_WB_CDL in swift_files
    assert README_FILES_ROW_WB_CDL in py_files
    assert README_FILES_ROW_WB_DCTL in swift_files
    assert README_FILES_ROW_WB_DCTL in py_files
    assert README_FILES_ROW_ODT in swift_files
    assert README_FILES_ROW_ODT in py_files
    assert README_FILES_ROW_README in swift_files
    assert README_FILES_ROW_README in py_files
    assert README_FILES_ROW_XML_PY in files
    assert README_FILES_ROW_IDT_PY in files
    assert README_FILES_ROW_EXP_CUBE in files
    assert README_FILES_ROW_WB_CUBE in files
    assert README_FILES_ROW_README in files

    # ㉗–㊲ locked strings 一字不动（含 本说明 / graph.xml 机器可读分锁 / | 文件 | 作用 | / 调色页，串行节点图： / 同一图的 Graphviz）.
    assert README_FILES_README_TO == "本说明"
    assert _files_readme_row(readme) == README_FILES_ROW_README
    assert _files_readme_row(readme_fn) == README_FILES_ROW_README
    assert _files_readme_row(py_readme) == README_FILES_ROW_README
    assert README_FILES_GRAPH_XML_SWIFT_TO == "机器可读节点图（可旁路白平衡）"
    assert README_FILES_GRAPH_XML_PY_TO == "机器可读节点图（可旁路曝光 + 白平衡）"
    assert README_FILES_ROW_XML_SWIFT == (
        "| `graph.xml` | 机器可读节点图（可旁路白平衡） |"
    )
    assert README_FILES_ROW_XML_PY == (
        "| `graph.xml` | 机器可读节点图（可旁路曝光 + 白平衡） |"
    )
    assert _files_graph_xml_row(readme) == README_FILES_ROW_XML_PY
    assert _files_graph_xml_row(readme_fn) == README_FILES_ROW_XML_SWIFT
    assert _files_graph_xml_row(py_readme) == README_FILES_ROW_XML_PY
    assert README_FILES_GRAPH_XML_SWIFT_FROM not in swift_files
    assert README_FILES_GRAPH_XML_PY_FROM not in py_files
    assert README_FILES_GRAPH_XML_BANNED not in readme_fn
    assert README_FILES_GRAPH_XML_BANNED not in py_readme
    assert README_FILES_HEADER_TO == "| 文件 | 作用 |"
    assert README_COLOR_PAGE_TITLE_TO == "调色页，串行节点图："
    assert _color_page_title_line(readme) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(readme_fn) == README_COLOR_PAGE_TITLE_TO
    assert _color_page_title_line(py_readme) == README_COLOR_PAGE_TITLE_TO
    assert README_COLOR_PAGE_TITLE_FROM not in readme_fn
    assert README_COLOR_PAGE_TITLE_FROM not in py_readme
    assert README_FILES_GRAPH_DOT_TO == "同一图的 Graphviz"
    assert README_FILES_GRAPH_DOT_ROW == "| `graph.dot` | 同一图的 Graphviz |"
    assert _files_graph_dot_row(readme) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(readme_fn) == README_FILES_GRAPH_DOT_ROW
    assert _files_graph_dot_row(py_readme) == README_FILES_GRAPH_DOT_ROW
    assert README_FILES_GRAPH_DOT_FROM not in swift_files
    assert README_FILES_GRAPH_DOT_FROM not in py_files
    assert README_APPLY_ODT_LINE == (
        "- Apply **ODT** (node 4: LUT `04_ODT_Rec709.cube`, or CST ACEScct → Rec.709) "
        "若需要 **709 预览** 查看节点（不是 ACES OT）。预览·非成片。"
    )
    assert _apply_odt_line(readme) == README_APPLY_ODT_LINE
    assert _apply_odt_line(readme_fn) == README_APPLY_ODT_LINE
    assert _apply_odt_line(py_readme) == README_APPLY_ODT_LINE
    assert README_GRAPH_INPUT_TO == "输入：相机 Log / 相机色域"
    assert README_GRAPH_INPUT_SWIFT in swift_graph
    assert README_GRAPH_INPUT_PY in py_graph
    assert README_GRAPH_INPUT_TO in graph
    assert GRAPH_DOT_EXP_HEAD == "曝光（可归零）"
    assert GRAPH_DOT_EXP_FILE == "02_Exposure.cube / .dctl"
    assert GRAPH_DOT_WB_HEAD == "白平衡（可旁路）"
    assert GRAPH_DOT_WB_LINE == GRAPH_DOT_WB_LINE_LOCKED
    assert GRAPH_EXP_XML_DESC == GRAPH_EXP_XML_DESC_LOCKED
    assert GRAPH_WB_XML_DESC == GRAPH_WB_XML_DESC_LOCKED
    assert GRAPH_DOT_CLIP_LABEL == GRAPH_DOT_CLIP_LABEL_LOCKED
    assert GRAPH_DOT_WORKING_SPACE == GRAPH_DOT_WORKING_SPACE_LOCKED
    assert GRAPH_IDT_XML_DESC == GRAPH_IDT_XML_DESC_LOCKED
    assert GRAPH_DOT_IDT_THIRD == GRAPH_DOT_IDT_THIRD_LOCKED
    assert GRAPH_DOT_ODT_HEAD == GRAPH_DOT_ODT_HEAD_LOCKED
    assert GRAPH_DOT_TIMELINE_LABEL == GRAPH_DOT_TIMELINE_LABEL_LOCKED
    assert GRAPH_DOT_ODT_CST_LOCKED == "或 CST ACEScct → Rec.709"
    assert GRAPH_DOT_ODT_CST_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_CST_LOCKED in py_dot
    assert GRAPH_DOT_ODT_CST_FROM not in dot_fn
    assert GRAPH_DOT_ODT_CST_FROM not in py_dot
    assert "曝光（可归零）" in dot_fn
    assert "白平衡（可旁路）" in dot_fn
    assert r'clip [label="素材\\n相机 Log"]' in dot_fn
    assert 'label="工作空间"' in dot_fn
    assert GRAPH_DOT_IDT_THIRD_LOCKED in dot_fn
    assert GRAPH_DOT_ODT_HEAD_LOCKED in dot_fn
    assert r'timeline [shape=oval, label="时间线\\nACEScct"]' in dot_fn
    assert GRAPH_EXP_XML_DESC in xml_fn
    assert GRAPH_WB_XML_DESC in xml_fn
    assert GRAPH_IDT_XML_DESC in xml_fn
    assert "{GRAPH_IDT_XML_DESC}" in py_xml
    assert _xml_node_description(xml, "Exposure") == GRAPH_EXP_XML_DESC_LOCKED
    assert _xml_node_description(xml, "WB") == GRAPH_WB_XML_DESC_LOCKED
    assert _xml_node_description(xml, "IDT") == GRAPH_IDT_XML_DESC_LOCKED
    assert "- Apply **IDT**" in apply
    assert "- Apply **IDT**" in swift_apply
    assert "- Apply **IDT**" in py_apply
    assert "- Apply **WB**" in swift_apply
    assert "- Apply **WB**" in py_apply

    # FROZEN: cube TITLE, XML Desc, filenames, 色管.
    assert REC709_CUBE_TITLE == LOCKED_REC709_CUBE_TITLE
    assert f'TITLE "{LOCKED_REC709_CUBE_TITLE}"' in cube
    assert LOCKED_REC709_CUBE_TITLE in swift
    assert GRAPH_ODT_USER == (
        "709 预览，不是 ACES 输出变换，不是成片。预览·非成片。默认关。"
    )
    assert GRAPH_ODT_USER in graph
    for name in LOCKED_NODE_FILES:
        assert name in swift
        assert name in py
    assert "matrixCCT = nil" in swift
    assert "white_balance_matrix" in py
    assert "def apply_exposure" in (root / "color/exposure.py").read_text(encoding="utf-8")
    assert "达芬奇已验证" not in swift_idt
    assert "达芬奇已验证" not in py_idt_row
    assert "达芬奇已验证" not in files
    _assert_chengpian_not_a_deliverable_claim(swift_idt)
    _assert_chengpian_not_a_deliverable_claim(py_idt_row)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_IDT_SWIFT_TO)
    _assert_chengpian_not_a_deliverable_claim(README_FILES_IDT_PY_TO)

