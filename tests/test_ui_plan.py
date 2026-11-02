"""UI plan: single-window grade/delivery, no personal data, scopes stay advanced."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "ui-plan.md"
CONTENT = ROOT / "macos" / "LogBridge" / "LogBridge" / "ContentView.swift"
SETTINGS = ROOT / "macos" / "LogBridge" / "LogBridge" / "Views" / "SettingsView.swift"
DELIVER = ROOT / "macos" / "LogBridge" / "LogBridge" / "Views" / "DeliverSheet.swift"
HISTOGRAM = ROOT / "macos" / "LogBridge" / "LogBridge" / "Views" / "PreviewHistogramView.swift"

BANNED_CONTACT = (
    "@",
    "微信",
    "WeChat",
    "weixin",
    "Dejavu",
    "Phillip",
    "Hopkins",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ui_plan_records_layout_and_stays_private():
    text = _read(PLAN)
    assert "没有剪辑时间线" in text
    assert "示波器" in text
    assert "全局偏好" in text
    assert "检查器" in text
    assert "整段代理" in text
    assert "LogBridge contributors" not in text or "MIT" in _read(ROOT / "README.md")
    for token in BANNED_CONTACT:
        assert token not in text, token
    for token in ("支持", "一键", "精准", "成片", "成品"):
        assert token not in text, token


def test_histogram_stays_inside_advanced_panel():
    content = _read(CONTENT)
    advanced = content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    assert "PreviewHistogramView" in advanced
    assert "PreviewHistogramView" not in content.split("struct AdvancedPanel")[0]
    histogram = _read(HISTOGRAM)
    assert "不是示波器读数" in histogram
    assert "不参与写出" in histogram


def test_settings_apply_immediately_without_save_cancel():
    settings = _read(SETTINGS)
    assert "改完即生效" in settings
    assert 'Button("保存"' not in settings
    assert 'Button("取消"' not in settings
    assert "默认写出格式" in settings


def test_deliver_sheet_is_separate_from_preferences():
    deliver = _read(DELIVER)
    content = _read(CONTENT)
    assert "选出文件夹并写出" in deliver
    assert "processLockedClips" not in deliver
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "processLockedClips" in bar
    assert "showDeliverSheet" in bar
    assert "attachedSheet" in bar
    assert "下一步：在右侧检查器选成对 IDT" in bar
    assert "DeliverSheet" not in _read(SETTINGS)
    assert "session.activeSheet == .deliver" in content
    assert "if session.showDeliverSheet" not in content


def test_deliver_sheet_names_each_clip_before_the_folder_panel():
    deliver = _read(DELIVER)
    assert "会写出" in deliver
    assert "会跳过" in deliver
    assert "session.lockedClips" in deliver
    assert "clip.filename" in deliver
    assert "lockedPairLabel" in deliver
    assert "processSkipReason" in deliver
    assert "skippedClips" in deliver
    assert "!$0.hasLockedPair" in deliver
    assert "选出文件夹并写出" in deliver
    assert "processLockedClips" not in deliver
    plan = _read(PLAN)
    assert "会写出" in plan
    assert "会跳过" in plan


def test_monitor_can_enlarge_the_grade_preview():
    content = _read(CONTENT)
    assert "enum MonitorLayout" in content
    assert "case grade" in content
    assert 'Text("分屏")' in content or 'return "分屏"' in content
    assert "HSplitView" in content
    assert "SourcePreviewView" in content
    assert "Rec709PreviewView" in content
    preview = content.split("struct SplitPreview")[1]
    assert "pickingNeutral" in preview
    assert "shownLayout" in preview


def test_short_window_keeps_inspector_and_grade_readout():
    content = _read(CONTENT)
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert "ScrollView" in column
    assert "PairedIDTBar" in column
    assert "InspectorView" in column
    assert "跟这条选中" in column
    header = content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    assert "gradeReadout" in header
    assert "曝光关" in header
    assert "白平衡关" in header
    assert "仅预览" in header
    preview = content.split("SplitPreview(session: session, layout: monitorLayout)")[1].split(
        "ProcessLockedBar"
    )[0]
    assert "minHeight: 200" in preview
    advanced = content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    assert "maxHeight: 220" in advanced
    assert "ScrollView" in advanced
    plan = _read(PLAN)
    assert "整栏滚动" in plan
    assert "一行读数" in plan


def test_exposure_steps_and_luma_waveform_stay_on_the_preview_path():
    content = _read(CONTENT)
    before = content.split("struct AdvancedPanel")[0]
    assert "亮度波形" not in before
    advanced = content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    assert "亮度波形" in advanced
    assert "PreviewHistogramView" in advanced
    histogram = _read(HISTOGRAM)
    assert "亮度波形" in histogram
    assert "LumaWaveformSampler" in histogram
    assert "不参与写出" in histogram
    assert "不是示波器读数" in histogram
    assert "export" not in histogram.split("enum LumaWaveformSampler")[1].split("private struct LumaWaveformBars")[0]
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert 'Button("归零")' in inspector
    assert "nudgeExposureStops(-0.10)" in inspector
    assert "nudgeExposureStops(0.10)" in inspector
    assert "resetExposureStops()" in inspector
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canNudgeExposure")[1].split("func nudgeExposureStops")[0]
    assert "exposureEnabled" in gate
    assert "isWritingDeliverables" in gate
    assert "showDeliverSheet" in gate
    nudge = clip.split("func nudgeExposureStops")[1].split("func resetExposureStops")[0]
    assert "canNudgeExposure" in nudge
    assert "setExposureStops" in nudge
    reset = clip.split("func resetExposureStops")[1].split("func ")[0]
    assert "setExposureStops(0)" in reset
    pending_gate = clip.split("var canSelectNextPending")[1].split("func selectNextPendingFromMenu")[0]
    assert "hasLockedPair" in pending_gate
    assert "isWritingDeliverables" in pending_gate
    menu_fn = clip.split("func selectNextPendingFromMenu")[1].split("func ")[0]
    assert "canSelectNextPending" in menu_fn
    assert "selectNextPendingAfterLock" in menu_fn
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    assert 'CommandMenu("调色")' in app
    assert "曝光归零" in app
    assert "下一条待选" in app
    assert "selectNextPendingFromMenu" in app
    plan = _read(PLAN)
    assert "亮度波形" in plan
    assert "归零" in plan
    assert "不是示波器读数" in plan


def test_idt_lock_stays_on_the_clip_being_previewed():
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    body = clip.split("func setIDT(")[1].split("func selectNextPendingAfterLock")[0]
    assert "selectNextPendingAfterLock" not in body
    assert "refreshPreview()" in body
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert "下一条待选" in inspector
