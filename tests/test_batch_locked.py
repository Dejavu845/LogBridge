"""Locked-IDT batch: walk locked clips only. Unlocked stay listed."""

from pathlib import Path

from color.as_shot import WB_SOURCE_AS_SHOT, WB_SOURCE_ESTIMATE, WB_SOURCE_GREY
from color.batch import (
    ADVANCED_DISCLOSURE,
    PROCESS_BUTTON,
    REASON_PICK_LOG_GAMUT,
    REASON_PICK_PAIRED_IDT,
    BatchClip,
    confirm_auto_wb,
    estimate_chip_lit,
    has_locked_idt,
    never_guess_cct,
    plan_locked_batch,
    process_locked_names,
    propose_auto_wb,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SWIFT_ROOT = ROOT / "macos"
CLIP = SWIFT_ROOT / "LogBridge/LogBridge/Models/Clip.swift"
CONTENT = SWIFT_ROOT / "LogBridge/LogBridge/ContentView.swift"
INSPECTOR = SWIFT_ROOT / "LogBridge/LogBridge/Views/InspectorView.swift"
SIDEBAR = SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _all_swift() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SWIFT_ROOT.rglob("*.swift"))


def test_batch_walks_locked_only_skips_unlocked():
    clips = [
        BatchClip("locked.mov", idt="sony_slog3_sgamut3"),
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
        BatchClip("empty.mov"),
        BatchClip("stub.mov", idt="future", is_stub=True),
    ]
    plan = plan_locked_batch(clips)
    assert process_locked_names(clips) == ["locked.mov"]
    assert plan.locked_count == 1
    assert plan.pending_count == 3
    assert plan.lock_status_text == "1 条已锁定 / 3 条待选"
    assert plan.shows_process_button is True
    reasons = {c.name: reason for c, reason in plan.skipped}
    assert reasons["pending.mov"] == REASON_PICK_PAIRED_IDT
    assert reasons["empty.mov"] == REASON_PICK_LOG_GAMUT
    assert reasons["stub.mov"] == REASON_PICK_PAIRED_IDT
    assert skip_reason(clips[0]) is None
    assert has_locked_idt(clips[1]) is False


def test_no_process_button_when_nothing_locked():
    clips = [
        BatchClip("a.mov"),
        BatchClip("b.mov", detected_curve="C-Log2", needs_user_picker=True),
    ]
    plan = plan_locked_batch(clips)
    assert plan.shows_process_button is False
    assert process_locked_names(clips) == []
    assert plan.lock_status_text == "0 条已锁定 / 2 条待选"


def test_needs_picker_even_with_idt_is_skipped():
    clip = BatchClip("half.mov", idt="sony_slog3_sgamut3", needs_user_picker=True)
    assert has_locked_idt(clip) is False
    assert skip_reason(clip) == REASON_PICK_PAIRED_IDT


def test_estimate_chip_lights_only_after_confirm():
    state = {"wb_source": WB_SOURCE_AS_SHOT, "wb_cct": 3200.0, "auto_wb_cct": None}
    proposed = propose_auto_wb(state, 4100.0, 0.2)
    assert proposed["auto_wb_cct"] == 4100.0
    assert proposed["wb_source"] == WB_SOURCE_AS_SHOT
    assert proposed["wb_cct"] == 3200.0
    assert estimate_chip_lit(proposed["wb_source"]) is False
    confirmed = confirm_auto_wb(proposed)
    assert confirmed["wb_source"] == WB_SOURCE_ESTIMATE
    assert confirmed["wb_cct"] == 4100.0
    assert estimate_chip_lit(confirmed["wb_source"]) is True


def test_grey_card_overrides_estimate_and_no_5600_guess():
    grey = {
        "wb_source": WB_SOURCE_GREY,
        "wb_cct": 4800.0,
        "auto_wb_cct": 4100.0,
    }
    assert confirm_auto_wb(grey)["wb_source"] == WB_SOURCE_GREY
    assert confirm_auto_wb(grey)["wb_cct"] == 4800.0
    empty = propose_auto_wb({"wb_source": WB_SOURCE_AS_SHOT}, None)
    assert empty["auto_wb_cct"] is None
    assert confirm_auto_wb(empty)["wb_source"] == WB_SOURCE_AS_SHOT
    assert "wb_cct" not in confirm_auto_wb(empty)
    assert never_guess_cct(None) is True
    assert never_guess_cct(5600) is False


def test_swift_mirrors_locked_batch_and_one_button():
    clip = _read(CLIP)
    content = _read(CONTENT)
    inspector = _read(INSPECTOR)
    sidebar = _read(SIDEBAR)
    swift = _all_swift()
    assert "func processLockedClips()" in clip
    assert "processLockedClips()" in clip.split("func processSelected()")[1]
    assert "processLockedClips()" in clip.split("func applyGraph()")[1]
    assert "lockedClipCount" in clip
    assert "lockStatusText" in clip
    assert "showsProcessLockedButton" in clip
    assert "processSkipReason" in clip
    assert "先选择成对 IDT" in clip
    assert "先选择 Log 与色域" in clip
    assert "条已锁定" in clip and "条待选" in clip
    assert 'Button("处理已锁定片段")' in content
    assert "showsProcessLockedButton" in content
    assert "ProcessLockedBar" in content
    assert content.count("处理已锁定片段") >= 1
    assert 'Button("处理已锁定片段")' not in content.split("struct StatusBar")[1]
    assert 'Button("导出 ACEScct / EXR")' in content.split("struct AdvancedPanel")[1]
    assert ADVANCED_DISCLOSURE in content
    assert 'DisclosureGroup("高级"' in content
    assert "showAdvanced = false" in content
    assert "PairedIDTBar" in content
    assert "InspectorView" in content
    assert PROCESS_BUTTON in swift
    assert "机内 as-shot" in inspector
    assert "白平衡（估计）" in inspector
    assert "灰卡" in inspector
    assert "on: session.graph.wbSource == .estimate" in inspector
    assert "proposeAutoWB" in inspector
    assert "确认估计" in inspector
    assert "processSkipReason" in sidebar
    assert "一键还原" not in content or "Never 一键还原" in content


def test_inspector_is_exposure_and_wb_only():
    inspector = _read(INSPECTOR)
    content = _read(CONTENT)
    assert "ExposureInspector" in inspector
    assert "WBInspector" in inspector
    assert "struct InspectorView" in inspector
    body = inspector.split("struct InspectorView")[1].split("struct WBInspector")[0]
    assert "ExposureInspector" in body
    assert "WBInspector" in body
    assert "IDTInspector" not in body
    assert "ODTInspector" not in body
    assert "ODTInspector" in content  # advanced only
    assert "NodeStripView" in content.split("struct AdvancedPanel")[1]
