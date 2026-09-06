"""Resolve export is a bypassable WB node graph, not a prose sidecar."""

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
    EXPORT_NOTE_REC709,
    EXPORT_NOTE_WB_BYPASS,
    EXPORT_NOTE_WB_OFF,
    GRAPH_ODT_USER,
    GRAPH_ODT_XML_DESC,
    REC709_CUBE_COMMENT,
    REC709_CUBE_TITLE,
    REC709_PREVIEW_LABEL,
    RESOLVE_README_HONESTY,
    cdl_slope_offset_power,
    export_locked_resolve_bundle,
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
    assert "Bradford" in xml
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
    assert "bypassable" in dot
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
    assert "ACEScct deliverable" in xml
    assert "preview" in xml.lower()
    readme = (tmp_path / "README_RESOLVE.md").read_text(encoding="utf-8")
    assert "preview only" in readme.lower()
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
    assert "机内色温只填旋钮，默认 CAT 是单位阵。" in honesty
    assert "用户改色温才做相对变换 CAT(user→D65)·inv(CAT(as→D65))，3200→5600 变暖。" in honesty
    assert "灰卡是绝对 CAT；读不到就保持单位阵，不猜 5600。" in honesty
    assert "机内白转到 D65" not in readme
    assert "精准" not in readme
    assert "一键还原" not in readme
    assert readme.index("诚实说明") < readme.index("Graph (serial nodes)")
    _assert_chengpian_not_a_deliverable_claim(readme)
    graph = _graph_section(readme)
    assert GRAPH_ODT_USER in graph
    for token in GRAPH_ODT_BANNED:
        assert token not in graph
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
        assert "机内色温只填旋钮，默认 CAT 是单位阵。" in blob
        assert "CAT(user→D65)·inv(CAT(as→D65))" in blob
        assert "3200→5600 变暖" in blob
        assert "不猜 5600" in blob
        assert "机内白转到 D65" not in blob
        assert "精准" not in blob
        assert "一键还原" not in blob
        stripped = blob.replace("CAT(user→D65)·inv(CAT(as→D65))", "")
        assert "CAT(as→D65)" not in stripped
        _assert_chengpian_not_a_deliverable_claim(blob)
    swift_graph = _graph_section(readme_fn)
    assert GRAPH_ODT_USER in swift_graph
    for token in GRAPH_ODT_BANNED:
        assert token not in swift_graph
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
    assert "709 预览" in written_graph
    assert "预览·非成片" in written_graph
    for token in GRAPH_ODT_BANNED:
        assert token not in py_graph
        assert token not in written_graph

    assert GRAPH_ODT_XML_DESC in xml
    assert GRAPH_ODT_USER in xml
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
    assert GRAPH_ODT_USER in py_readme
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
    assert "Not an ACES Output Transform" not in xml
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
    assert RESOLVE_CCT_PENDING_LABEL in xml
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
    assert RESOLVE_CCT_PENDING_LABEL in xml_fn
    assert RESOLVE_CCT_PENDING_LABEL in readme_fn
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

