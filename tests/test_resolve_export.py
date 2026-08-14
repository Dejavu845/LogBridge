"""Resolve export is a bypassable WB node graph, not a prose sidecar."""

from pathlib import Path

import numpy as np
import pytest

from color.curves import linear_to_logc4, linear_to_slog3
from color.pipeline import process_to_rec709
from color.resolve_export import (
    cdl_slope_offset_power,
    export_resolve_bundle,
    format_ccc,
    format_cdl,
    format_dctl,
    format_dot,
    format_graph_xml,
    format_readme,
    idt_to_acescct,
    odt_from_acescct,
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
    assert "02_WB.cdl" in names
    assert "02_WB.ccc" in names
    assert "02_WB.dctl" in names
    assert "02_WB.cube" in names
    assert "03_ODT_Rec709.cube" in names
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
    assert "02_WB.cube" in xml
    assert "02_WB.cdl" in xml
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
    assert "implemented (unverified)" in readme
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
    for name in ("02_WB.cube", "03_ODT_Rec709.cube", "01_IDT_arri_logc4_awg4.cube"):
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
    assert "02_WB.dctl" in names
    dctl = (tmp_path / "02_WB.dctl").read_text(encoding="utf-8")
    assert "AP0" in dctl or "ACES2065-1" in dctl

