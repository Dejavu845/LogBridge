"""UI plan: single-window grade/delivery, no personal data, scopes stay advanced."""

import math
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


def test_folder_panel_sticks_to_the_window_after_the_write_sheet():
    """Confirming the write sheet must not go quiet. The folder panel stays on this window."""
    content = _read(CONTENT)
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert "openingExportFolder = true" in bar
    assert "选文件夹会贴在这个窗口上" in bar
    assert "取消则不写出" in bar
    assert "attachedSheet" in bar
    assert "showImporter" in bar
    assert bar.count("Button(") == 1
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    body = clip.split("func processLockedClips()")[1].split("static func exportFolderHostWindow")[0]
    assert "beginSheetModal" in body
    assert "panel.begin" in body
    assert "openingExportFolder = false" in body
    assert "rememberExportDirectory" in body
    hint = clip.split("var loopStepHint")[1].split("var showsProcessLockedButton")[0]
    assert "正在打开选文件夹" in hint
    deliver = _read(DELIVER)
    assert "选文件夹贴在这个窗口上" in deliver
    assert "取消则不写出" in deliver
    plan = _read(PLAN)
    assert "正在打开选文件夹" in plan
    assert "贴在主窗口" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


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
    preview = content.split("SplitPreview(")[1].split("ProcessLockedBar")[0]
    assert "monitorLayout" in preview
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


def test_wb_steps_restore_camera_values_and_the_write_sheet_names_the_grade():
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert 'Button("−100 K")' in inspector
    assert 'Button("+100 K")' in inspector
    assert 'Button("回到机内")' in inspector
    assert "nudgeWBCCT(-100)" in inspector
    assert "nudgeWBCCT(100)" in inspector
    assert "restoreAsShotWB()" in inspector
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canNudgeWB")[1].split("func nudgeWBCCT")[0]
    assert "wbEnabled" in gate
    assert "wbCCT" in gate
    assert "isWritingDeliverables" in gate
    assert "showDeliverSheet" in gate
    nudge = clip.split("func nudgeWBCCT")[1].split("var canRestoreAsShotWB")[0]
    assert "canNudgeWB" in nudge
    assert "graph.wbCCT" in nudge
    assert "setWBParams" in nudge
    assert "2000" in nudge
    assert "10000" in nudge
    assert "5600" not in nudge
    assert "6504" not in nudge
    restore_gate = clip.split("var canRestoreAsShotWB")[1].split("func restoreAsShotWB")[0]
    assert "wbEnabled" in restore_gate
    assert "isWritingDeliverables" in restore_gate
    assert "showDeliverSheet" in restore_gate
    assert "asShotCCT" in restore_gate
    restore = clip.split("func restoreAsShotWB")[1].split("func selectAdjacentClip")[0]
    assert "canRestoreAsShotWB" in restore
    assert "wbSource = .asShot" in restore
    assert "wbSource = .unknown" in restore
    assert "wbCCT = nil" in restore
    assert "5600" not in restore
    assert "6504" not in restore
    assert "setWBParams" not in restore
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    assert "色温 +100" in app
    assert "色温 −100" in app
    assert "回到机内" in app
    assert "nudgeWBCCT(100)" in app
    assert "nudgeWBCCT(-100)" in app
    assert "restoreAsShotWB" in app
    deliver = _read(DELIVER)
    assert "sharedGradeWriteLine" in deliver
    line = clip.split("var sharedGradeWriteLine")[1].split("var showsProcessLockedButton")[0]
    assert "这一套会套到已锁定素材" in line
    assert "曝光" in line
    assert "白平衡关" in line
    assert "绿品" in line
    plan = _read(PLAN)
    assert "−100 K" in plan
    assert "回到机内" in plan
    assert "不猜 5600" in plan
    assert "这一套会套到已锁定素材" in plan


def test_write_sheet_names_the_proxy_and_the_toolbar_says_the_next_step():
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    name = clip.split("func plannedDeliverableName")[1].split("var asShotUnknown")[0]
    assert "ProResWriter.proresSuffix" in name
    assert "ResolveExporter.proxyFolderSuffix" in name
    assert "5600" not in name
    exporter = _read(ROOT / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift")
    assert 'static let proxyFolderSuffix = "_ACES2065-1_proxy"' in exporter
    directory = exporter.split("func deliverableSequenceDirectory")[1].split("func sequenceFrameURL")[0]
    assert "proxyFolderSuffix" in directory
    deliver = _read(DELIVER)
    assert "plannedDeliverableName" in deliver
    assert "将得到" in deliver
    assert "clip.filename" in deliver
    hint = clip.split("var loopStepHint")[1].split("var showsProcessLockedButton")[0]
    assert "先拖入或点添加" in hint
    assert "在右侧检查器选成对 IDT" in hint
    assert "可调色，再点写出" in hint
    assert "正在写出代理" in hint
    content = _read(CONTENT)
    assert "session.loopStepHint" in content
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert "先拖入或点「添加…」" in column
    assert "session.clips.isEmpty" in column
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    zone = sidebar.split("struct DropZone")[1]
    assert "或点这里添加" in zone
    tap = zone.split(".onTapGesture")[1].split("struct ClipRow")[0]
    assert "if empty" not in tap
    assert "onTap()" in tap
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('Button("写出…")')[1].split('CommandMenu("调色")')[0]
    assert "showsProcessLockedButton" in menu
    assert "isWritingDeliverables" in menu
    plan = _read(PLAN)
    assert "将得到" in plan
    assert "先拖入或点添加" in plan


def test_shared_grade_stays_when_selection_changes():
    """Browsing clips must not replace the one exposure / WB set write uses."""
    content = _read(CONTENT)
    # Monitor zoom resets pan on the first selectedID change. That handler
    # must not touch the grade. The shared set stays on the later handler.
    parts = content.split(".onChange(of: session.selectedID)")
    assert len(parts) >= 3
    pan_reset = parts[1].split("SplitPreview")[0]
    assert "monitorPan.reset()" in pan_reset
    assert "noteSelectionForSharedGrade" not in pan_reset
    assert "applyClipWBToGraph" not in pan_reset
    handlers = parts[1:]
    grade = [part.split("refreshPreview()")[0] for part in handlers if "noteSelectionForSharedGrade" in part]
    assert len(grade) == 1
    assert "applyClipWBToGraph" not in grade[0]
    assert "这次预览" in content
    assert "setODT" in content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    note = clip.split("func noteSelectionForSharedGrade")[1].split("func persistGraphWBToSelectedClip")[0]
    assert "sharedGradeIsFactory" in note
    assert "applyClipWBToGraph" in note
    adjacent = clip.split("func selectAdjacentClip")[1].split("func removeSelectedClipFromSession")[0]
    assert "visibleClips" in adjacent
    assert "noteSelectionForSharedGrade" in adjacent
    assert "applyClipWBToGraph" not in adjacent
    restore = clip.split("func restoreAsShotWB")[1].split("func selectAdjacentClip")[0]
    assert "selectedClip?.asShotCCT" in restore
    assert "touchSharedGrade" in restore
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert "clipListFilter" in sidebar
    assert "visibleClips" in sidebar
    assert "待选" in sidebar
    assert "已锁定" in sidebar
    plan = _read(PLAN)
    assert "这次预览" in plan
    assert "不会改掉" in plan
    assert "全部 / 待选 / 已锁定" in plan


def test_tint_steps_zero_without_moving_temperature_and_the_monitor_shows_it():
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    wb = inspector.split("struct WBInspector")[1].split("struct ODTInspector")[0]
    assert 'Button("−1")' in wb
    assert 'Button("+1")' in wb
    assert 'Button("绿品归零")' in wb
    assert "nudgeWBTint(-1)" in wb
    assert "nudgeWBTint(1)" in wb
    assert "resetWBTint()" in wb
    assert "canNudgeWBTint" in wb
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canNudgeWBTint")[1].split("func nudgeWBTint")[0]
    assert "canNudgeWB" in gate
    nudge = clip.split("func nudgeWBTint")[1].split("func resetWBTint")[0]
    assert "canNudgeWBTint" in nudge
    assert "setWBParams(tint:" in nudge
    assert "-10" in nudge
    assert "10" in nudge
    assert "5600" not in nudge
    assert "6504" not in nudge
    assert "wbCCT" not in nudge
    reset = clip.split("func resetWBTint")[1].split("func setExposureEnabled")[0]
    assert "canNudgeWBTint" in reset
    assert "setWBParams(tint: 0)" in reset
    assert "wbCCT" not in reset
    assert "5600" not in reset
    assert "6504" not in reset
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    assert "绿品 +1" in app
    assert "绿品 −1" in app
    assert "绿品归零" in app
    assert "nudgeWBTint(1)" in app
    assert "nudgeWBTint(-1)" in app
    assert "resetWBTint" in app
    content = _read(CONTENT)
    header = content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    assert "绿品" in header
    plan = _read(PLAN)
    assert "绿品归零" in plan
    assert "色温不动" in plan
    assert "−10 到 +10" in plan


def test_preview_frame_steps_without_inventing_a_range_or_moving_the_grade():
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canStepPreviewFrame")[1].split("var canStepPreviewBackward")[0]
    assert "previewScrubLastFrame" in gate
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    back = clip.split("var canStepPreviewBackward")[1].split("var canStepPreviewForward")[0]
    assert "previewFrameIndex > 0" in back
    forward = clip.split("var canStepPreviewForward")[1].split("func stepPreviewFrame")[0]
    assert "previewFrameIndex < last" in forward
    step = clip.split("func stepPreviewFrame")[1].split("var lockedClips")[0]
    assert "setPreviewFrame" in step
    assert "previewFrameIndex - 1" in step
    assert "previewFrameIndex + 1" in step
    assert "return true" in step
    assert "setExposureStops" not in step
    assert "setWBParams" not in step
    assert "touchSharedGrade" not in step
    assert "24" not in step
    assert "30" not in step
    assert "5600" not in step
    assert "6504" not in step
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button("上一帧")' in bar
    assert 'Button("下一帧")' in bar
    assert "stepPreviewFrame(-1)" in bar
    assert "stepPreviewFrame(1)" in bar
    assert "canStepPreviewBackward" in bar
    assert "canStepPreviewForward" in bar
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "case 123:" in monitor
    assert "case 124:" in monitor
    assert "onStepFrame?(-1)" in monitor
    assert "onStepFrame?(1)" in monitor
    assert "isArrowConsumedByTextInput" in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert 'Button("上一帧")' in menu
    assert 'Button("下一帧")' in menu
    assert "stepPreviewFrame(-1)" in menu
    assert "stepPreviewFrame(1)" in menu
    assert "canStepPreviewBackward" in menu
    assert "canStepPreviewForward" in menu
    plan = _read(PLAN)
    assert "上一帧" in plan
    assert "下一帧" in plan
    assert "到头就停" in plan
    assert "不改曝光和白平衡" in plan
    assert "不猜帧率" in plan


def test_preview_clock_uses_the_clip_rate_and_jumps_leave_the_grade():
    """Clock is index ÷ metadata fps. Home/End move the preview frame only."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func previewClock(")[1].split("enum DetectionSource")[0]
    assert "frameIndex >= 0" in fn
    assert "fps.isFinite, fps > 0" in fn
    assert "return nil" in fn
    assert "Double(frameIndex) / fps" in fn
    assert "1000" in fn
    assert "%d:%02d.%03d" in fn
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams"):
        assert token not in fn, token
    shown = clip.split("var previewClockText")[1].split("var canStepPreviewFrame")[0]
    assert "previewFrameIndex" in shown
    assert "previewPlaybackFPS" in shown
    start = clip.split("func jumpPreviewToStart")[1].split("func jumpPreviewToEnd")[0]
    assert "setPreviewFrame(0)" in start
    assert "stopPreviewPlayback" in start
    assert "setExposureStops" not in start
    assert "setWBParams" not in start
    assert "touchSharedGrade" not in start
    end = clip.split("func jumpPreviewToEnd")[1].split("var canPlayPreview")[0]
    assert "previewScrubLastFrame" in end
    assert "setPreviewFrame(last)" in end
    assert "setExposureStops" not in end
    assert "setWBParams" not in end
    assert "touchSharedGrade" not in end
    for token in ("24", "30", "5600", "6504"):
        assert token not in start, token
        assert token not in end, token
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button("回到开头")' in bar
    assert 'Button("到结尾")' in bar
    assert "jumpPreviewToStart" in bar
    assert "jumpPreviewToEnd" in bar
    assert "previewClockText" in bar
    assert "canJumpPreviewToStart" in bar
    assert "canJumpPreviewToEnd" in bar
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "case 115:" in monitor
    assert "case 119:" in monitor
    assert "onJumpToStart?()" in monitor
    assert "onJumpToEnd?()" in monitor
    assert "isArrowConsumedByTextInput" in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert 'Button("回到开头")' in menu
    assert 'Button("到结尾")' in menu
    assert "jumpPreviewToStart" in menu
    assert "jumpPreviewToEnd" in menu
    assert "canJumpPreviewToStart" in menu
    assert "canJumpPreviewToEnd" in menu
    plan = _read(PLAN)
    assert "预览时间" in plan
    assert "回到开头" in plan
    assert "到结尾" in plan
    assert "不猜 24 或 30" in plan
    assert "不改曝光和白平衡" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_preview_second_step_uses_this_clip_rate_and_names_the_last_frame():
    """One second is this clip's rate, rounded. The clock names the last frame too."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func previewSecondFrameCount")[1].split("enum DetectionSource")[0]
    assert "fps.isFinite, fps > 0" in fn
    assert "return nil" in fn
    assert "rounded()" in fn
    assert "frames >= 1" in fn
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams"):
        assert token not in fn, token
    end_clock = clip.split("var previewClockEndText")[1].split("var canStepPreviewFrame")[0]
    assert "previewScrubLastFrame" in end_clock
    assert "previewClock(frameIndex: last" in end_clock
    assert "previewPlaybackFPS" in end_clock
    step = clip.split("func stepPreviewBySecond")[1].split("var canPlayPreview")[0]
    assert "previewSecondFrameCount" in step
    assert "stopPreviewPlayback()" in step
    assert "setPreviewFrame(next)" in step
    assert "previewFrameIndex + delta" in step
    assert "setExposureStops" not in step
    assert "setWBParams" not in step
    assert "touchSharedGrade" not in step
    for token in ("24", "30", "5600", "6504"):
        assert token not in step, token
    show = clip.split("var showsPreviewSecondStep")[1].split("var canPlayPreview")[0]
    assert "previewSecondFrameCount" in show
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button("退 1 秒")' in bar
    assert 'Button("进 1 秒")' in bar
    assert "showsPreviewSecondStep" in bar
    assert "stepPreviewBySecond(-1)" in bar
    assert "stepPreviewBySecond(1)" in bar
    assert "canStepPreviewSecondBackward" in bar
    assert "canStepPreviewSecondForward" in bar
    assert "previewClockText" in bar
    assert "previewClockEndText" in bar
    assert '" · \\(clock) / \\(end)"' in bar
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "transportShiftOnly" in monitor
    assert "onStepSecond?(-1)" in monitor
    assert "onStepSecond?(1)" in monitor
    assert "onStepFrame?(-1)" in monitor
    assert "onStepFrame?(1)" in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert 'Button("退 1 秒")' in menu
    assert 'Button("进 1 秒")' in menu
    assert "stepPreviewBySecond(-1)" in menu
    assert "stepPreviewBySecond(1)" in menu
    assert "canStepPreviewSecondBackward" in menu
    assert "canStepPreviewSecondForward" in menu
    plan = _read(PLAN)
    assert "退 1 秒" in plan
    assert "进 1 秒" in plan
    assert "大约 1 秒" in plan
    assert "最后一帧" in plan
    assert "不是片源时长" in plan
    assert "滑条下面这一行" in plan
    assert "不猜 24 或 30" in plan
    assert "不改曝光和白平衡" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def _schoolbook_round(value: float) -> int:
    """Same tie break as Swift `rounded()` for a finite value: half away from zero."""
    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def _preview_clock_text(frame_index: int, fps: float) -> str:
    """Same digits as Clip.previewClock. Used to check a typed readout lands back."""
    whole = _schoolbook_round((frame_index / fps) * 1000)
    millis = whole % 1000
    total = whole // 1000
    secs = total % 60
    minutes = (total // 60) % 60
    hours = total // 3600
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes}:{secs:02d}.{millis:03d}"


def _preview_frame_index(text: str, fps: float | None, last_frame: int) -> int | None:
    """Mirror of Clip.previewFrameIndex(forClock:fps:lastFrame:)."""
    if last_frame < 0 or fps is None or not math.isfinite(fps) or fps <= 0:
        return None
    trimmed = text.strip().replace("：", ":")
    if not trimmed:
        return None
    if "帧" in trimmed:
        stripped = trimmed.replace("第", "").replace("帧", "").strip()
        try:
            display = int(stripped)
        except ValueError:
            return None
        if display < 1:
            return None
        return min(display - 1, last_frame)
    if trimmed.endswith("秒"):
        trimmed = trimmed[:-1].strip()
    seconds = _preview_clock_seconds(trimmed)
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return None
    raw = float(_schoolbook_round(seconds * fps))
    if not math.isfinite(raw) or raw < 0:
        return None
    if raw > last_frame:
        return last_frame
    return int(raw)


def _preview_clock_seconds(text: str) -> float | None:
    parts = [part.strip() for part in text.split(":")]
    # split drops nothing; an empty field stays so "1::2" is not one minute.
    if not 1 <= len(parts) <= 3:
        return None

    def number(part: str) -> float | None:
        if not part:
            return None
        try:
            value = float(part)
        except ValueError:
            return None
        if not math.isfinite(value) or value < 0:
            return None
        return value

    def whole(value: float) -> bool:
        return float(_schoolbook_round(value)) == value

    if len(parts) == 1:
        return number(parts[0])
    if len(parts) == 2:
        minutes = number(parts[0])
        seconds = number(parts[1])
        if minutes is None or seconds is None or not whole(minutes) or seconds >= 60:
            return None
        return minutes * 60 + seconds
    hours = number(parts[0])
    minutes = number(parts[1])
    seconds = number(parts[2])
    if (
        hours is None
        or minutes is None
        or seconds is None
        or not whole(hours)
        or not whole(minutes)
        or minutes >= 60
        or seconds >= 60
    ):
        return None
    hour = 60.0
    return hours * hour * hour + minutes * hour + seconds


def test_preview_jump_reads_a_clock_or_a_frame_and_leaves_the_grade():
    """Typed time uses this clip's rate. It does not invent 24/30 or move the grade."""
    assert _preview_frame_index("0:01.000", 25, 1000) == 25
    assert _preview_frame_index("1.5", 25, 1000) == 38
    assert _preview_frame_index("1.5秒", 25, 1000) == 38
    assert _preview_frame_index("0：01.500", 25, 1000) == 38
    assert _preview_frame_index("第 12 帧", 25, 1000) == 11
    assert _preview_frame_index("12帧", 25, 1000) == 11
    assert _preview_frame_index("第 1 帧", 25, 1000) == 0
    assert _preview_frame_index("第 9 帧", 25, 3) == 3
    assert _preview_frame_index("9:00", 25, 10) == 10
    assert _preview_frame_index("1:02:03", 25, 100000) == (3600 + 120 + 3) * 25
    assert _preview_frame_index("", 25, 1000) is None
    assert _preview_frame_index("   ", 25, 1000) is None
    assert _preview_frame_index("abc", 25, 1000) is None
    assert _preview_frame_index("1:60", 25, 1000) is None
    assert _preview_frame_index("1.5:00", 25, 1000) is None
    assert _preview_frame_index("第 0 帧", 25, 1000) is None
    assert _preview_frame_index("0:01.000", None, 1000) is None
    assert _preview_frame_index("0:01.000", 25, -1) is None
    for fps in (23.976, 24, 25, 29.97, 30, 59.94, 60):
        last = int(fps * 90)
        for frame in range(0, last + 1, 7):
            typed = _preview_clock_text(frame, fps)
            assert _preview_frame_index(typed, fps, last) == frame, (fps, frame, typed)
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func previewFrameIndex(forClock")[1].split("static func previewSecondFrameCount")[0]
    assert "fps.isFinite, fps > 0" in fn
    assert "return nil" in fn
    assert "replacingOccurrences(of: \"：\"" in fn
    assert "contains(\"帧\")" in fn
    assert "hasSuffix(\"秒\")" in fn
    assert "previewClockSeconds" in fn
    assert "rounded()" in fn
    assert "lastFrame" in fn
    assert "hour * hour" in fn
    assert "seconds < 60" in fn
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams"):
        assert token not in fn, token
    jump = clip.split("func jumpPreview(toClock")[1].split("var lockedClips")[0]
    assert "canJumpPreviewToClock" in jump
    assert "previewFrameIndex(forClock:" in jump
    assert "stopPreviewPlayback()" in jump
    assert "setPreviewFrame(index)" in jump
    assert "setExposureStops" not in jump
    assert "setWBParams" not in jump
    assert "touchSharedGrade" not in jump
    gate = clip.split("var canJumpPreviewToClock")[1].split("func jumpPreview(toClock")[0]
    assert "canStepPreviewFrame" in gate
    assert "previewPlaybackFPS" in gate
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button("跳到")' in bar
    assert 'TextField("0:01.500"' in bar
    assert "previewClockText != nil" in bar
    assert "commitPreviewJump" in bar
    assert "jumpPreview(toClock: text)" in bar
    assert "认不出这个时间" in bar
    assert "先写出时间，如 0:01.500 或第 12 帧" in bar
    assert "canJumpPreviewToClock" in bar
    assert 'jumpText = ""' in bar
    plan = _read(PLAN)
    assert "跳到" in plan
    assert "认不出这个时间" in plan
    assert "第 12 帧" in plan
    assert "不是时间码" in plan
    assert "不猜 24 或 30" in plan
    assert "不改曝光和白平衡" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_grade_before_is_preview_only_and_leaves_the_shared_set():
    """Compare drops exposure and WB in the picture. Write keeps the shared set."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canTogglePreviewGradeBefore")[1].split("var graphForPreview")[0]
    assert "hasLockedPair" in gate
    assert "previewShowsGradeBefore" in gate
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    assert "pickingNeutral" in gate
    picture = clip.split("var graphForPreview")[1].split("func togglePreviewGradeBefore")[0]
    assert "previewShowsGradeBefore" in picture
    assert "exposureEnabled = false" in picture
    assert "wbEnabled = false" in picture
    assert "5600" not in picture
    assert "6504" not in picture
    toggle = clip.split("func togglePreviewGradeBefore")[1].split("func refreshPreview")[0]
    assert "canTogglePreviewGradeBefore" in toggle
    assert "invalidateWBODT" in toggle
    assert "refreshPreview()" in toggle
    assert "touchSharedGrade" not in toggle
    assert "setExposureStops" not in toggle
    assert "setWBParams" not in toggle
    assert "previewFrameIndex" not in toggle
    refresh = clip.split("func refreshPreview()")[1].split("func refreshODTOnly()")[0]
    assert "graphForPreview" in refresh
    only = clip.split("func refreshODTOnly()")[1].split("func setPreviewFrame")[0]
    assert "graphForPreview" in only
    scrub = clip.split("func setPreviewFrame")[1].split("func resetPreviewScrub")[0]
    assert "graphForPreview" in scrub
    write_line = clip.split("var sharedGradeWriteLine")[1].split("var loopStepHint")[0]
    assert "previewShowsGradeBefore" not in write_line
    assert "这一套会套到已锁定素材" in write_line
    content = _read(CONTENT)
    header = content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    assert 'Button(session.previewShowsGradeBefore ? "回到调色" : "看调色前")' in header
    assert "togglePreviewGradeBefore" in header
    assert "canTogglePreviewGradeBefore" in header
    assert "看调色前 ·" in header
    preview = content.split("struct SplitPreview")[1]
    assert "调色前 ·" in preview
    assert "不含曝光和白平衡" in preview
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert "看调色前" in menu
    assert "回到调色" in menu
    assert "togglePreviewGradeBefore" in menu
    assert "canTogglePreviewGradeBefore" in menu
    assert 'keyboardShortcut("\\\\"' in menu
    plan = _read(PLAN)
    assert "看调色前" in plan
    assert "回到调色" in plan
    assert "不含曝光和白平衡" in plan
    assert "检查器数字不动" in plan


def test_import_names_what_arrived_and_the_filter_cannot_hide_it():
    """A drop always answers. A pending/locked filter cannot swallow the new rows."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    arrival = clip.split("static func importArrivalNote")[1].split("static func importEmptyNote")[0]
    assert "读入" in arrival
    assert "在右侧检查器选成对 IDT" in arrival
    assert "可在监视器看预览，再点写出" in arrival
    assert "imported > 0" in arrival
    assert "5600" not in arrival
    assert "6504" not in arrival
    empty = clip.split("static func importEmptyNote")[1].split("static func importFilterHidesNewRow")[0]
    assert "没有能读的素材" in empty
    assert "5600" not in empty
    hides = clip.split("static func importFilterHidesNewRow")[1].split("static func importSkipSummary")[0]
    assert "case .all" in hides
    assert "return false" in hides
    assert "hasLockedPair" in hides
    apply = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert 'lastImportNote = "正在读入…"' in apply
    assert "importArrivalNote" in apply
    assert "importEmptyNote" in apply
    assert "importFilterHidesNewRow" in apply
    assert "clipListFilter = .all" in apply
    assert "Self.importSkipSummary(skipped)" in apply
    assert "needsUserPicker" in apply
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert "lastImportNote" in sidebar
    assert "importNoteIsProblem" in sidebar
    assert "没有能读" in sidebar
    plan = _read(PLAN)
    assert "正在读入" in plan
    assert "没有能读的素材" in plan
    assert "读入 N 条" in plan


def test_idt_lock_stays_on_the_clip_being_previewed():
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    body = clip.split("func setIDT(")[1].split("func selectNextPendingAfterLock")[0]
    assert "selectNextPendingAfterLock" not in body
    assert "refreshPreview()" in body
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert "下一条待选" in inspector


def test_paired_idt_is_a_visible_list_and_search_does_not_lock():
    """The inspector shows pairs as rows. Search hides rows and never locks one."""
    idt = _read(ROOT / "macos/LogBridge/LogBridge/Models/IDT.swift")
    assert "static let pairListShowsSearchAfter = 4" in idt
    fn = idt.split("static func filteredPairs")[1].split("static func isSLog3")[0]
    assert "trimmingCharacters" in fn
    assert "searchText" in fn
    assert "localizedStandardContains" in fn
    assert "return pairs" in fn
    assert "setIDT" not in fn
    assert "5600" not in fn
    assert "6504" not in fn
    brands = idt.split("var searchText")[1].split("var menuLabel")[0]
    for word in ("索尼", "佳能", "阿莱", "松下", "富士", "尼康", "苹果", "大疆"):
        assert word in brands, word
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    choices = inspector.split("struct PairedIDTChoices")[1].split("struct InspectorView")[0]
    assert 'TextField("查找 Log 或色域"' in choices
    assert "filteredPairs" in choices
    assert "pairListShowsSearchAfter" in choices
    assert "setIDT(clip.id, pair)" in choices
    assert "clip.idt != pair" in choices
    assert "点一行锁定" in choices
    assert "没有匹配的成对 IDT" in choices
    assert "当前这一对不在查找里" in choices
    assert 'Button("清空")' in choices
    assert "maxHeight: 180" in choices
    assert "onChange(of: session.selectedID)" in choices
    assert 'pairQuery = ""' in choices
    assert "isExporting" in choices
    assert "Picker(" not in choices
    bar = inspector.split("struct PairedIDTBar")[1].split("struct PairedIDTChoices")[0]
    assert "PairedIDTChoices" in bar
    plan = _read(PLAN)
    assert "查找 Log 或色域" in plan
    assert "点一行" in plan
    assert "不会因为只剩一对就替你选" in plan
    assert "索尼" in plan


def test_preview_playback_uses_metadata_rate_and_stops_at_the_end():
    """Play is preview transport. It does not invent a rate or move the shared grade."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    play = clip.split("var canPlayPreview")[1].split("var lockedClips")[0]
    assert "previewPlaybackFPS" in play
    assert "canStepPreviewForward" in play
    assert "pickingNeutral" in play
    assert "keepPlaying: true" in play
    assert "preview.isWorking" in play
    advance = clip.split("func advancePreviewPlayback")[1].split("var lockedClips")[0]
    assert advance.index("preview.isWorking") < advance.index("setPreviewFrame")
    engine = _read(ROOT / "macos/LogBridge/LogBridge/Preview/PreviewEngine.swift")
    scrub = engine.split("func scrub(")[1].split("private func applyScrub")[0]
    assert "isWorking = true" in scrub
    assert scrub.index("isWorking = true") < scrub.index("applyScrub")
    assert "conservativeFPS" not in play
    assert "5600" not in play
    assert "6504" not in play
    assert "24" not in play
    assert "30" not in play
    assert "setExposureStops" not in play
    assert "setWBParams" not in play
    assert "touchSharedGrade" not in play
    reset = clip.split("func resetPreviewScrub()")[1].split("var pendingPickerCount")[0]
    assert "previewPlaybackFPS = nil" in reset
    assert "previewPlaybackFPS = fps" in reset
    manual = clip.split("func setPreviewFrame")[1].split("func resetPreviewScrub")[0]
    assert "keepPlaying" in manual
    assert "stopPreviewPlayback()" in manual
    step = clip.split("func stepPreviewFrame")[1].split("var canPlayPreview")[0]
    assert "stopPreviewPlayback()" in step
    gates = clip.split("func presentSettings()")[1].split("func presentDeliverSheet()")[0]
    assert "stopPreviewPlayback()" in gates
    deliver = clip.split("func presentDeliverSheet()")[1].split("func importProviders")[0]
    assert "stopPreviewPlayback()" in deliver
    writing = clip.split("func writeLockedDeliverables")[1].split("DispatchQueue.global")[0]
    assert writing.index("stopPreviewPlayback()") < writing.index("isWritingDeliverables = true")
    hint = clip.split("var loopStepHint")[1].split("var showsProcessLockedButton")[0]
    assert "已写出代理。可再调色，或在状态栏打开 Finder" in hint
    assert "可调色，再点写出" in hint
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button(session.isPreviewPlaying ? "暂停" : "播放")' in bar
    assert "togglePreviewPlayback()" in bar
    assert "canTogglePreviewPlayback" in bar
    assert "播放中" in bar
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "case 49:" in monitor
    assert "isPlaybackKeyConsumedByControl" in monitor
    assert "onTogglePlayback" in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert "播放预览" in menu
    assert "暂停预览" in menu
    assert "togglePreviewPlayback()" in menu
    assert "canTogglePreviewPlayback" in menu
    plan = _read(PLAN)
    assert "播放预览" in plan
    assert "到最后一帧就停" in plan
    assert "不猜帧率" in plan
    assert "不改曝光和白平衡" in plan
    assert "已写出代理。可再调色，或在状态栏打开 Finder" in plan


def _preview_play_next(index: int, last: int, loops: bool, backward: bool = False) -> int | None:
    """Mirror of Clip.previewPlayNextFrame. Nil means playback stops."""
    if last < 0 or index < 0 or index > last:
        return None
    if backward:
        if index > 0:
            return index - 1
        if loops and last > 0:
            return last
        return None
    if index < last:
        return index + 1
    if loops and last > 0:
        return 0
    return None


def _preview_play_start(index: int, last: int, loops: bool, backward: bool = False) -> int | None:
    """Mirror of Clip.previewPlayStartFrame. Nil means playback cannot start."""
    if last < 0 or index < 0 or index > last:
        return None
    if backward:
        if index > 0:
            return index
        if loops and last > 0:
            return last
        return None
    if index < last:
        return index
    if loops and last > 0:
        return 0
    return None


def test_preview_loop_wraps_to_the_first_frame_and_leaves_the_grade():
    """Loop is optional. Off still stops at the end. Turning it on does not move the grade."""
    assert _preview_play_next(0, 10, False) == 1
    assert _preview_play_next(9, 10, False) == 10
    assert _preview_play_next(10, 10, False) is None
    assert _preview_play_next(10, 10, True) == 0
    assert _preview_play_next(4, 10, True) == 5
    assert _preview_play_next(0, 0, True) is None
    assert _preview_play_next(0, 0, False) is None
    assert _preview_play_next(-1, 10, True) is None
    assert _preview_play_next(11, 10, True) is None
    assert _preview_play_start(3, 10, False) == 3
    assert _preview_play_start(10, 10, False) is None
    assert _preview_play_start(10, 10, True) == 0
    assert _preview_play_start(0, 10, True) == 0
    assert _preview_play_start(0, 0, True) is None
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    nxt = clip.split("static func previewPlayNextFrame")[1].split("static func previewPlayStartFrame")[0]
    assert "index < last" in nxt
    assert "loops, last > 0" in nxt
    assert "return 0" in nxt
    assert "return nil" in nxt
    start_fn = clip.split("static func previewPlayStartFrame")[1].split("enum DetectionSource")[0]
    assert "index < last" in start_fn
    assert "loops, last > 0" in start_fn
    assert "return 0" in start_fn
    assert "return nil" in start_fn
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams"):
        assert token not in nxt, token
        assert token not in start_fn, token
    assert "previewLoops = false" in clip
    show = clip.split("var showsPreviewLoop")[1].split("var canTogglePreviewLoop")[0]
    assert "last > 0" in show
    assert "previewPlaybackFPS" in show
    gate = clip.split("var canTogglePreviewLoop")[1].split("func togglePreviewLoop")[0]
    assert "showsPreviewLoop" in gate
    assert "canStepPreviewFrame" in gate
    assert "pickingNeutral" in gate
    toggle = clip.split("func togglePreviewLoop")[1].split("func startPreviewPlayback")[0]
    assert "previewLoops.toggle()" in toggle
    assert "setPreviewFrame" not in toggle
    assert "setExposureStops" not in toggle
    assert "setWBParams" not in toggle
    assert "touchSharedGrade" not in toggle
    play = clip.split("var canPlayPreview")[1].split("var canTogglePreviewPlayback")[0]
    assert "previewLoops" in play
    assert "canStepPreviewForward" in play
    assert "last > 0" in play
    begin = clip.split("func startPreviewPlayback")[1].split("func stopPreviewPlayback")[0]
    assert "previewPlayStartFrame" in begin
    assert "loops: previewLoops" in begin
    advance = clip.split("func advancePreviewPlayback")[1].split("var canJumpPreviewToClock")[0]
    assert "previewPlayNextFrame" in advance
    assert "loops: previewLoops" in advance
    assert "keepPlaying: true" in advance
    assert advance.index("preview.isWorking") < advance.index("setPreviewFrame")
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button(session.previewLoops ? "循环中" : "循环")' in bar
    assert "showsPreviewLoop" in bar
    assert "togglePreviewLoop()" in bar
    assert "canTogglePreviewLoop" in bar
    assert "循环播放" in bar
    assert "播放中" in bar
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert "循环播放" in menu
    assert "关掉循环" in menu
    assert "togglePreviewLoop()" in menu
    assert "canTogglePreviewLoop" in menu
    assert 'keyboardShortcut("l", modifiers: [.command, .option])' in menu
    plan = _read(PLAN)
    assert "循环播放" in plan
    assert "回到第 1 帧接着播" in plan
    assert "只有一帧" in plan
    assert "⌥⌘L" in plan
    assert "到最后一帧就停" in plan
    assert "不改曝光和白平衡" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_preview_reverse_stops_at_the_first_frame_and_leaves_the_grade():
    """Backward playback stops on frame 0. Loop wraps to the last frame. Grade stays put."""
    assert _preview_play_next(5, 10, False, backward=True) == 4
    assert _preview_play_next(1, 10, False, backward=True) == 0
    assert _preview_play_next(0, 10, False, backward=True) is None
    assert _preview_play_next(0, 10, True, backward=True) == 10
    assert _preview_play_next(10, 10, True, backward=True) == 9
    assert _preview_play_next(0, 0, True, backward=True) is None
    assert _preview_play_next(0, 0, False, backward=True) is None
    assert _preview_play_next(-1, 10, True, backward=True) is None
    assert _preview_play_next(11, 10, True, backward=True) is None
    assert _preview_play_next(4, 10, False, backward=False) == 5
    assert _preview_play_start(5, 10, False, backward=True) == 5
    assert _preview_play_start(0, 10, False, backward=True) is None
    assert _preview_play_start(0, 10, True, backward=True) == 10
    assert _preview_play_start(1, 10, True, backward=True) == 1
    assert _preview_play_start(0, 0, True, backward=True) is None
    assert _preview_play_start(10, 10, False, backward=False) is None
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    nxt = clip.split("static func previewPlayNextFrame")[1].split("static func previewPlayStartFrame")[0]
    assert "backward" in nxt
    assert "index - 1" in nxt
    assert "return last" in nxt
    assert "index < last" in nxt
    assert "return 0" in nxt
    start_fn = clip.split("static func previewPlayStartFrame")[1].split("enum DetectionSource")[0]
    assert "backward" in start_fn
    assert "return last" in start_fn
    assert "index > 0" in start_fn
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams"):
        assert token not in nxt, token
        assert token not in start_fn, token
    assert "previewPlaysBackward = false" in clip
    gate = clip.split("var canReversePreview")[1].split("var canTogglePreviewReverse")[0]
    assert "previewLoops" in gate
    assert "canStepPreviewBackward" in gate
    assert "last > 0" in gate
    assert "previewPlaybackFPS" in gate
    toggle = clip.split("var canTogglePreviewReverse")[1].split("func togglePreviewPlayback")[0]
    assert "previewPlaysBackward" in toggle
    assert "canReversePreview" in toggle
    reverse = clip.split("func playPreviewBackward")[1].split("func pausePreviewPlayback")[0]
    assert "startPreviewPlayback(backward: true)" in reverse
    assert "stopPreviewPlayback()" in reverse
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams", "setPreviewFrame"):
        assert token not in reverse, token
    pause = clip.split("func pausePreviewPlayback")[1].split("var canJumpPreviewToClock")[0]
    assert "isPreviewPlaying" in pause
    assert "stopPreviewPlayback()" in pause
    assert "setExposureStops" not in pause
    begin = clip.split("func startPreviewPlayback")[1].split("func stopPreviewPlayback")[0]
    assert "backward: backward" in begin
    assert "canReversePreview" in begin
    advance = clip.split("func advancePreviewPlayback")[1].split("func playPreviewBackward")[0]
    assert "backward: previewPlaysBackward" in advance
    assert "keepPlaying: true" in advance
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    assert 'Button(session.isPreviewPlaying && session.previewPlaysBackward ? "倒放中" : "倒放")' in bar
    assert "playPreviewBackward()" in bar
    assert "canTogglePreviewReverse" in bar
    assert "循环倒放" in bar
    assert "倒放中" in bar
    assert "播放中" in bar
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "consumeShuttleKey" in monitor
    assert 'key == "j"' in monitor
    assert 'key == "k"' in monitor
    assert 'key == "l"' in monitor
    assert "isPlaybackKeyConsumedByControl" in monitor
    assert "onPlayBackward" in monitor
    assert "onPausePlayback" in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert "倒放预览" in menu
    assert "暂停倒放" in menu
    assert "playPreviewBackward()" in menu
    assert "canTogglePreviewReverse" in menu
    plan = _read(PLAN)
    assert "倒放预览" in plan
    assert "到第 1 帧就停" in plan
    assert "回到最后一帧接着倒放" in plan
    assert "不猜 24 或 30" in plan
    assert "不改曝光和白平衡" in plan
    assert "这不是时间线" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_media_fact_line_is_shared_and_does_not_invent_a_rate():
    """List, monitor, inspector, and the write sheet name the source. No 24/30 fill-in."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func mediaFactLine(")[1].split("static func formatMediaFPS")[0]
    assert "静帧" in fn
    assert "帧/秒" in fn
    assert "width > 0" in fn
    assert "fps.isFinite, fps > 0" in fn
    assert "seconds.isFinite, seconds > 0" in fn
    assert "return nil" in fn
    assert "isStill" in fn
    for token in ("24", "30", "5600", "6504", "setExposureStops", "setWBParams"):
        assert token not in fn, token
    fps = clip.split("static func formatMediaFPS")[1].split("static func formatMediaDuration")[0]
    assert "1000" in fps
    assert "%.3f" in fps
    for token in ("24", "30", "5600", "6504"):
        assert token not in fps, token
    duration = clip.split("static func formatMediaDuration")[1].split("enum DetectionSource")[0]
    assert "秒" in duration
    assert "分" in duration
    assert "小时" in duration
    for token in ("24", "30", "5600", "6504"):
        assert token not in duration, token
    apply = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert "MediaFormat.extent" in apply
    assert "pixelWidth: extent.width" in apply
    assert "pixelHeight: extent.height" in apply
    assert "mediaFPS: extent.fps" in apply
    assert "durationSeconds: extent.durationSeconds" in apply
    assert "isStill: probe.kind == .still" in apply
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert "clip.mediaFactLine" in sidebar
    content = _read(CONTENT)
    header = content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    assert "selectedClip?.mediaFactLine" in header
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert "clip.mediaFactLine" in column
    deliver = _read(DELIVER)
    assert deliver.count("fact: clip.mediaFactLine") == 2
    plan = _read(PLAN)
    assert "静帧" in plan
    assert "不猜 24 或 30" in plan
    assert "片源尺寸" in plan


def test_write_progress_names_the_clip_and_the_row_opens_the_proxy():
    """Default ProRes: progress names the file, and 已写出代理 opens that .mov."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    total = clip.split("static func knownWriteFrameTotal")[1].split("static func cancelledExportNote")[0]
    assert "isStill" in total
    assert "return 1" in total
    assert "expectedSourceFrames" in total
    assert "durationSeconds" in total
    assert "mediaFPS" in total
    assert "conservativeFPS" not in total
    for token in ("24", "30", "5600", "6504"):
        assert token not in total, token
    progress = clip.split("static func exportProgressText")[1].split("static func knownWriteFrameTotal")[0]
    assert "clipName" in progress
    assert "第 \\(frame) / 共 \\(frameTotal) 帧" in progress
    assert "第 \\(frame) 帧" in progress
    writing = clip.split("func writeLockedDeliverables")[1].split("static func batchSummaryText")[0]
    assert "knownWriteFrameTotal(for: clip)" in writing
    assert "clipName: clip.filename" in writing
    assert "frameTotal: frameTotal" in writing
    assert "writingClipID = nil" in writing
    assert "writtenName: url.lastPathComponent" in writing
    assert "writtenPath: url.path" in writing
    reveal = clip.split("func revealClipExportInFinder")[1].split("private func publishExportProgress")[0]
    assert "writtenRevealPath" in reveal
    assert "clipProResRevealURL" in reveal
    assert "clipSequenceRevealURL" in reveal
    assert "lastExportDirectoryURL" in reveal
    assert "fileExists" in reveal
    assert "exportFormat == .exrACES2065" in reveal
    prores = clip.split("static func clipProResRevealURL")[1].split("func revealClipExportInFinder")[0]
    assert "wroteProxyChip" in prores
    assert "ProResWriter.deliverableURL" in prores
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert "正在写出" in sidebar
    assert "writingClipID" in sidebar
    assert "writtenDeliverableName" in sidebar
    assert "session.revealClipExportInFinder(clip)" in sidebar
    plan = _read(PLAN)
    assert "正在写出" in plan
    assert "第 k / 共 m 帧" in plan
    assert "不猜 24 或 30" in plan
    assert "_Rec709_proxy.mov" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_clip_posters_are_source_first_frames_and_not_the_grade():
    """The bin picture is the camera-log first frame. It does not follow the scrub or the write."""
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    cache = sidebar.split("final class ClipPosterCache")[1].split("struct ClipSourcePoster")[0]
    assert "decodeDownscaled" in cache
    assert "frameIndex: 0" in cache
    assert "maxLongEdge: longEdge" in cache
    assert "app.logbridge.posters" in cache
    assert "gradeAP0" not in cache
    assert "applyIDT" not in cache
    assert "setIDT" not in cache
    assert "setExposureStops" not in cache
    assert "setWBParams" not in cache
    assert "FileManager" not in cache
    assert "write(to:" not in cache
    for token in ("24", "30", "5600", "6504"):
        assert token not in cache, token
    poster = sidebar.split("struct ClipSourcePoster")[1].split("struct ClipSidebarView")[0]
    assert 'Text("源")' in poster
    assert 'Text("没有画面")' in poster
    assert "requestClipPoster" in poster
    assert "isWritingDeliverables" in poster
    assert "不含曝光和白平衡，不参与写出" in poster
    assert "第一帧" in poster
    row = sidebar.split("struct ClipRow")[1]
    assert "ClipSourcePoster(session: session, posters: session.posters, clip: clip)" in row
    content = _read(CONTENT)
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert "ClipSourcePoster(session: session, posters: session.posters, clip: clip)" in column
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    ask = clip.split("func requestClipPoster")[1].split("func removeSelectedClipFromSession")[0]
    assert "isWritingDeliverables" in ask
    assert "posters.request" in ask
    assert "setIDT" not in ask
    assert "5600" not in ask
    assert "6504" not in ask
    remove = clip.split("func removeSelectedClipFromSession")[1].split("static func isArrowConsumedByTextInput")[0]
    assert "posters.drop(id: id)" in remove
    plan = _read(PLAN)
    assert "角上写「源」" in plan
    assert "不跟着当前预览帧走" in plan
    assert "没有画面" in plan
    assert "不写入磁盘" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_shared_grade_undo_steps_back_without_moving_idt_or_the_frame():
    """Undo restores exposure and white balance. One slider drag is one step."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    undo = clip.split("func undoSharedGrade()")[1].split("func redoSharedGrade()")[0]
    assert "canUndoSharedGrade" in undo
    assert "applySharedGradeSnapshot" in undo
    assert "stopPreviewPlayback()" in undo
    assert "gradeRedoStack" in undo
    for token in ("setIDT", "setODT", "setPreviewFrame", "previewFrameIndex", "5600", "6504", "24", "30"):
        assert token not in undo, token
    redo = clip.split("func redoSharedGrade()")[1].split("var canNudgeExposure")[0]
    assert "canRedoSharedGrade" in redo
    assert "applySharedGradeSnapshot" in redo
    assert "stopPreviewPlayback()" in redo
    for token in ("setIDT", "setPreviewFrame", "5600", "6504"):
        assert token not in redo, token
    gate = clip.split("var canEditSharedGradeNow")[1].split("func undoSharedGrade")[0]
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    assert "openingExportFolder" in gate
    apply = clip.split("func applySharedGradeSnapshot")[1].split("func rememberSharedGrade")[0]
    assert "graph.wbCCT = snap.wbCCT" in apply
    assert "graph.exposureStops = snap.exposureStops" in apply
    assert "invalidateWBODT" in apply
    assert "refreshPreview()" in apply
    for token in ("setIDT", "setODT", "setPreviewFrame", "5600", "6504"):
        assert token not in apply, token
    remember = clip.split("func rememberSharedGrade")[1].split("func closeSharedGradeStroke")[0]
    assert "openGradeStroke == stroke" in remember
    assert "gradeUndoStack.append" in remember
    assert "gradeRedoStack.removeAll()" in remember
    exposure = clip.split("func setExposureStops")[1].split("func setWBEnabled")[0]
    assert "rememberSharedGrade(stroke: .exposure)" in exposure
    assert "invalidateWBODT" in exposure
    wb = clip.split("func setWBParams")[1].split("func applyClipWBToGraph")[0]
    assert "rememberSharedGrade(stroke: .cct)" in wb
    assert "rememberSharedGrade(stroke: .tint)" in wb
    assert "5600" not in wb
    assert "6504" not in wb
    odt = clip.split("func setODT(")[1].split("func setWBParams")[0]
    assert "rememberSharedGrade" not in odt
    note = clip.split("func noteSelectionForSharedGrade")[1].split("func persistGraphWBToSelectedClip")[0]
    assert "rememberSharedGrade" not in note
    assert "sharedGradeIsFactory" in note
    content = _read(CONTENT)
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert 'Button("撤销这一套")' in column
    assert 'Button("重做这一套")' in column
    assert "undoSharedGrade()" in column
    assert "redoSharedGrade()" in column
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "leftMouseUp" in monitor
    assert "onGradeStrokeEnd" in monitor
    assert "consumeGradeUndoKey" in monitor
    assert "isUndoConsumedByTextInput" in monitor
    assert 'charactersIgnoringModifiers?.lowercased() == "z"' in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert 'Button("撤销这一套")' in menu
    assert 'Button("重做这一套")' in menu
    assert "undoSharedGrade()" in menu
    assert "redoSharedGrade()" in menu
    assert 'keyboardShortcut("z"' not in menu
    plan = _read(PLAN)
    assert "撤销这一套" in plan
    assert "一次拖动滑条算一步" in plan
    assert "不改成对 IDT" in plan
    assert "不记进撤销" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_locked_pair_moves_only_when_the_next_pending_list_has_it():
    """The current pair is written onto the next pending clip only if that clip already lists it."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    nxt = clip.split("func nextPendingClip")[1].split("var applyPairToNextPendingNote")[0]
    assert "!$0.hasLockedPair" in nxt
    assert "dropFirst" in nxt
    note = clip.split("var applyPairToNextPendingNote")[1].split("var canApplyLockedPairToNextPending")[0]
    assert "下一条待选的列表里没有这一对。不替它选。" in note
    assert "canApplyLockedPairToNextPending" in note
    assert "isWritingDeliverables" in note
    assert "openingExportFolder" in note
    gate = clip.split("var canApplyLockedPairToNextPending")[1].split("func applyLockedPairToNextPending")[0]
    assert "pickerPairs.contains(idt)" in gate
    assert "hasLockedPair" in gate
    assert "isWritingDeliverables" in gate
    assert "showDeliverSheet" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "openingExportFolder" in gate
    assert "isStub" in gate
    apply = clip.split("func applyLockedPairToNextPending()")[1].split("private func currentSharedGradeSnapshot")[0]
    assert "canApplyLockedPairToNextPending" in apply
    assert "stopPreviewPlayback()" in apply
    assert "selectedID = next.id" in apply
    assert "noteSelectionForSharedGrade(next)" in apply
    assert "setIDT(next.id, idt)" in apply
    for token in ("setExposureStops", "setWBParams", "setODT", "5600", "6504", "24", "30"):
        assert token not in apply, token
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert 'Button("这一对给下一条待选")' in inspector
    assert "applyLockedPairToNextPending()" in inspector
    assert "canApplyLockedPairToNextPending" in inspector
    assert "applyPairToNextPendingNote" in inspector
    assert 'Button("下一条待选")' in inspector
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert 'Button("这一对给下一条待选")' in menu
    assert "applyLockedPairToNextPending()" in menu
    assert "canApplyLockedPairToNextPending" in menu
    assert 'keyboardShortcut("]", modifiers: [.command, .shift])' in menu
    plan = _read(PLAN)
    assert "这一对给下一条待选" in plan
    assert "不替它选" in plan
    assert "不改这一套曝光和白平衡" in plan
    assert "⇧⌘]" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_typed_exposure_and_color_temperature_stay_on_the_shared_grade():
    """Typing a stop or Kelvin uses the same set as the sliders. A bad string changes nothing."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    exposure = clip.split("static func parseTypedExposureStops")[1].split("func applyTypedExposureStops")[0]
    assert "hasSuffix(\"档\")" in exposure
    assert "rounded < -8 || rounded > 8" in exposure
    assert "return .outOfRange" in exposure
    assert "return .value(rounded)" in exposure
    for token in ("5600", "6504", "24", "30", "setIDT", "setPreviewFrame"):
        assert token not in exposure, token
    apply_ev = clip.split("func applyTypedExposureStops")[1].split("var canTypeWBCCT")[0]
    assert "canNudgeExposure" in apply_ev
    assert "先写出档，如 +0.50" in apply_ev
    assert "认不出这个档" in apply_ev
    assert "档要在 −8 到 +8" in apply_ev
    assert "closeSharedGradeStroke()" in apply_ev
    assert "setExposureStops(stops)" in apply_ev
    assert "setExposureEnabled" not in apply_ev
    assert "setIDT" not in apply_ev
    assert "setPreviewFrame" not in apply_ev
    for token in ("5600", "6504", "24", "30"):
        assert token not in apply_ev, token
    gate = clip.split("var canTypeWBCCT")[1].split("static func parseTypedWBCCT")[0]
    assert "graph.wbEnabled" in gate
    assert "wbCCT != nil" not in gate
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    assert "setWBEnabled" not in gate
    cct = clip.split("static func parseTypedWBCCT")[1].split("func applyTypedWBCCT")[0]
    assert 'hasSuffix("K")' in cct
    assert "rounded < 2000 || rounded > 10000" in cct
    assert "return .outOfRange" in cct
    for token in ("5600", "6504", "24", "30"):
        assert token not in cct, token
    apply_cct = clip.split("func applyTypedWBCCT(_ text: String) -> Bool {")[1].split("\n    }\n")[0]
    assert "canTypeWBCCT" in apply_cct
    assert "先写出色温，如 4500" in apply_cct
    assert "认不出这个色温" in apply_cct
    assert "色温要在 2000 到 10000" in apply_cct
    assert "graph.wbCCT == cct" in apply_cct
    assert "setWBParams(cct: cct)" in apply_cct
    assert "closeSharedGradeStroke()" in apply_cct
    assert "setExposureStops" not in apply_cct
    assert "setIDT" not in apply_cct
    assert "setPreviewFrame" not in apply_cct
    for token in ("5600", "6504", "24", "30"):
        assert token not in apply_cct, token
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert 'Button("写入档")' in inspector
    assert "applyTypedExposureStops(exposureDraft)" in inspector
    assert "typedExposureNote" in inspector
    assert 'Button("写入色温")' in inspector
    assert "applyTypedWBCCT(cctDraft)" in inspector
    assert "canTypeWBCCT" in inspector
    assert "typedCCTNote" in inspector
    assert 'TextField("如 +0.50"' in inspector
    assert 'TextField("如 4500"' in inspector
    plan = _read(PLAN)
    assert "写入档" in plan
    assert "写入色温" in plan
    assert "认不出这个档" in plan
    assert "认不出这个色温" in plan
    assert "不猜 5600 或 6504" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_typed_tint_stays_on_the_shared_grade():
    """Typing green–magenta uses the same set as the slider. A bad string changes nothing."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canTypeWBTint")[1].split("static func parseTypedWBTint")[0]
    assert "canNudgeWBTint" in gate
    assert "setWBEnabled" not in gate
    tint = clip.split("static func parseTypedWBTint")[1].split("func applyTypedWBTint")[0]
    assert 'hasSuffix("绿品")' in tint
    assert "dropLast(2)" in tint
    assert "rounded < -10 || rounded > 10" in tint
    assert "return .outOfRange" in tint
    assert "return .value(rounded)" in tint
    for token in ("5600", "6504", "24", "30", "setIDT", "setPreviewFrame", "setWBEnabled"):
        assert token not in tint, token
    apply = clip.split("func applyTypedWBTint(_ text: String) -> Bool {")[1].split("\n    }\n")[0]
    assert "canTypeWBTint" in apply
    assert "先写出绿品，如 +1.5" in apply
    assert "认不出这个绿品" in apply
    assert "绿品要在 −10 到 +10" in apply
    assert "abs(graph.wbTint - tint) <= 1e-9" in apply
    assert "setWBParams(tint: tint)" in apply
    assert "closeSharedGradeStroke()" in apply
    assert "setExposureStops" not in apply
    assert "setIDT" not in apply
    assert "setPreviewFrame" not in apply
    assert "setWBEnabled" not in apply
    assert "wbCCT" not in apply
    for token in ("5600", "6504", "24", "30"):
        assert token not in apply, token
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    assert 'Button("写入绿品")' in inspector
    assert "applyTypedWBTint(tintDraft)" in inspector
    assert "canTypeWBTint" in inspector
    assert "typedTintNote" in inspector
    assert 'TextField("如 +1.5"' in inspector
    plan = _read(PLAN)
    assert "写入绿品" in plan
    assert "认不出这个绿品" in plan
    assert "绿品要在 −10 到 +10" in plan
    assert "色温空着时不能写入" in plan
    assert "色温不动" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_clip_list_search_narrows_rows_without_moving_the_grade():
    """A filename or folder query only hides rows. It does not lock an IDT or edit the grade."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    assert "var folderName: String" in clip
    match = clip.split("static func clipMatchesListQuery")[1].split("private var sharedGradeIsFactory")[0]
    assert "trimmingCharacters" in match
    assert "needle.isEmpty" in match
    assert "return true" in match
    assert "clip.filename.localizedStandardContains(needle)" in match
    assert "clip.folderName" in match
    assert "folder.localizedStandardContains(needle)" in match
    assert "return false" in match
    for token in ("5600", "6504", "24", "30", "setIDT", "setExposureStops", "setPreviewFrame", "selectedID"):
        assert token not in match, token
    visible = clip.split("var visibleClips")[1].split("static func clipMatchesListQuery")[0]
    assert "clipListFilter" in visible
    assert "clipMatchesListQuery(clip, query: clipListQuery)" in visible
    hides = clip.split("static func importQueryHidesNewRow")[1].split("static func importSkipSummary")[0]
    assert "needle.isEmpty" in hides
    assert "return false" in hides
    assert "clipMatchesListQuery" in hides
    apply = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert "importQueryHidesNewRow" in apply
    assert 'clipListQuery = ""' in apply
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert 'TextField("查找文件名"' in sidebar
    assert "clipListQuery" in sidebar
    assert 'Button("清空")' in sidebar
    assert "没有匹配的素材。清空查找再看列表。" in sidebar
    assert "当前这条不在查找里。监视器不跟着查找换。" in sidebar
    assert "当前这条不在这个筛选里。监视器不跟着筛选换。" in sidebar
    assert "folderName" in sidebar
    plan = _read(PLAN)
    assert "查找文件名" in plan
    assert "没有匹配的素材" in plan
    assert "当前这条不在查找里" in plan
    assert "不写整条路径" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_remove_from_list_leaves_the_file_and_the_shared_grade():
    """Taking a row off the bin does not touch the source file or the grade."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("var canRemoveClipsFromSession")[1].split("var canRemoveSelectedClip")[0]
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    assert "openingExportFolder" in gate
    assert "FileManager" not in gate
    remove = clip.split("func removeSelectedClipFromSession")[1].split("static func isArrowConsumedByTextInput")[0]
    assert "canRemoveClipsFromSession" in remove
    assert "respectTextInput" in remove
    assert "isArrowConsumedByTextInput()" in remove
    assert "removedWasSelected" in remove
    assert "stopPreviewPlayback()" in remove
    assert "preview.evict(clipID: id)" in remove
    assert "posters.drop(id: id)" in remove
    assert "noteSelectionForSharedGrade" in remove
    for token in ("setExposureStops", "setWBParams", "setIDT", "setPreviewFrame", "setODT", "5600", "6504", "FileManager"):
        assert token not in remove, token
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert 'Button("从列表拿掉（不删文件）")' in sidebar
    assert "canRemoveClipsFromSession" in sidebar
    assert "respectTextInput: false" in sidebar
    assert "clipID: clip.id" in sidebar
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('Button("添加…")')[1].split('Button("设置…")')[0]
    assert 'Button("从列表拿掉（不删文件）")' in menu
    assert "removeSelectedClipFromSession(respectTextInput: false)" in menu
    assert "canRemoveSelectedClip" in menu
    plan = _read(PLAN)
    assert "从列表拿掉（不删文件）" in plan
    assert "源文件留在原处" in plan
    assert "已经写出的代理也不删" in plan
    assert "没有确认面板" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_finished_preview_reaches_the_monitor_without_another_click():
    """A decoded frame publishes on the preview engine. The window has to hear it."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    init_body = clip.split("init() {")[1].split("deinit {")[0]
    assert "preview.objectWillChange" in init_body
    assert "objectWillChange.send()" in init_body
    assert "setExposureStops" not in init_body
    assert "setIDT" not in init_body
    note = clip.split("static func monitorPaneGapNote(")[1].split("func refreshPreview()")[0]
    assert 'return "正在解码预览…"' in note
    assert 'status == "解不出预览帧"' in note
    assert 'status == "解码失败"' in note
    assert "waitingOnPair" in note
    assert "imageMissing" in note
    assert "5600" not in note
    assert "6504" not in note
    assert "setExposureStops" not in note
    assert "setIDT" not in note
    assert "setPreviewFrame" not in note
    content = _read(CONTENT)
    preview = content.split("struct SplitPreview")[1].split("struct PreviewScrubBar")[0]
    assert "monitorPaneGapNote" in preview
    assert "session.isExporting ? nil" in preview
    assert "waitingOnPair: session.selectedClip?.isPending == true" in preview
    assert "waitingOnPair: false" in preview
    assert "sourceImage" in preview
    assert "compareBeforeImage" in preview
    assert "odtImage" in preview
    plan = _read(PLAN)
    assert "正在解码预览…" in plan
    assert "解不出预览帧" in plan
    assert "解码失败" in plan
    assert "不用再点一下才出现" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_compare_layout_shows_grade_before_beside_the_shared_set():
    """对照 is two preview panes. The left drops exposure and WB. Write keeps the set."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    before = clip.split("var graphForCompareBefore")[1].split("var canTogglePreviewGradeBefore")[0]
    assert "monitorLayout == .compare" in before
    assert "hasLockedPair" in before
    assert "exposureEnabled = false" in before
    assert "wbEnabled = false" in before
    assert "5600" not in before
    assert "6504" not in before
    gate = clip.split("var canTogglePreviewCompare")[1].split("var graphForPreview")[0]
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    assert "openingExportFolder" in gate
    assert "pickingNeutral" in gate
    assert "hasLockedPair" in gate
    layout = clip.split("func setMonitorLayout")[1].split("func togglePreviewCompare")[0]
    assert "canTogglePreviewCompare" in layout
    assert "previewShowsGradeBefore = false" in layout
    assert "compareBeforeImage = nil" in layout
    assert "refreshPreview()" in layout
    for token in ("setExposureStops", "setWBParams", "setIDT", "setPreviewFrame", "5600", "6504"):
        assert token not in layout, token
    toggle = clip.split("func togglePreviewCompare")[1].split("func resetPreviewScrub")[0]
    assert "setMonitorLayout(.compare)" in toggle
    assert "setMonitorLayout(back)" in toggle
    refresh = clip.split("func refreshPreview()")[1].split("func refreshODTOnly()")[0]
    assert "compareBefore: graphForCompareBefore" in refresh
    assert "graphForPreview" in refresh
    scrub = clip.split("func setPreviewFrame")[1].split("func setMonitorLayout")[0]
    assert "compareBefore: graphForCompareBefore" in scrub
    content = _read(CONTENT)
    assert "case compare" in content
    assert 'return "对照"' in content
    assert "compareBeforePane" in content
    assert "compareBeforeImage" in content
    assert "调色前" in content
    assert "不含曝光和白平衡" in content
    header = content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    assert "对照 ·" in header
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    assert "对照调色前后" in menu
    assert "关掉对照" in menu
    assert "togglePreviewCompare" in menu
    assert "canTogglePreviewCompare" in menu
    assert 'keyboardShortcut("/"' in menu
    engine = _read(ROOT / "macos/LogBridge/LogBridge/Preview/PreviewEngine.swift")
    assert "compareBeforeImage" in engine
    assert "gradedFromLinear" in engine
    assert "func comparePicture" in engine
    plan = _read(PLAN)
    assert "对照" in plan
    assert "左：调色前" in plan
    assert "未锁定时不能切过去" in plan
    assert "对照调色前后" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_write_sheet_shows_the_graded_frame_only_when_it_matches_the_write():
    """The sheet still is the Rec.709 monitor frame. 调色前 / HDR / EXR are words."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    glance = clip.split("static func makeDeliverPreviewGlance")[1].split("var canProcess")[0]
    assert "previewShowsGradeBefore" not in glance
    assert "gradeBefore" in glance
    assert "showStill: false" in glance
    assert "不是调色前" in glance
    assert "监视器在看调色前。写出仍是检查器里这一套。" in glance
    assert "exrACES2065" in glance
    assert "不是监视器上这一幅" in glance
    assert "isHDR" in glance
    assert "不是这一幅 HDR" in glance
    assert "odt == .off" in glance
    assert "709 预览关" in glance
    assert "comparing" in glance
    assert "不是左幅调色前" in glance
    assert "showStill: hasPicture" in glance
    assert "showStill: true" in glance
    assert "和监视器同一幅" in glance
    assert "不是最终画面" in glance
    assert "5600" not in glance
    assert "6504" not in glance
    label = clip.split("static func deliverPreviewFrameLabel")[1].split("static func makeDeliverPreviewGlance")[0]
    assert "静帧" in label
    assert "frameIndex + 1" in label
    assert "lastFrame" in label
    for token in ("5600", "6504", "24", "30", "fps"):
        assert token not in label, token
    deliver = _read(DELIVER)
    assert "deliverPreviewGlance" in deliver
    assert "仅预览" in deliver
    assert "odtImage" in deliver
    assert "sharedGradeWriteLine" in deliver
    content = _read(CONTENT)
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert "barCaution" in bar
    assert bar.count("Button(") == 1
    plan = _read(PLAN)
    assert "这一小图和监视器同一幅" in plan
    assert "不把监视器那一幅放进说明" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_repeat_import_does_not_add_another_row():
    """A second drop of the same path stays one row. Selection and the grade stay."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    identity = clip.split("static func clipIdentityPath")[1].split("static func importPathIsAlreadyKept")[0]
    assert "standardizedFileURL" in identity
    assert "resolvingSymlinksInPath" in identity
    for token in ("setIDT", "setExposureStops", "setPreviewFrame", "5600", "6504"):
        assert token not in identity, token
    kept = clip.split("static func importPathIsAlreadyKept")[1].split("static func importDuplicateNote")[0]
    assert "existingPaths.contains(path)" in kept
    assert "acceptedThisDrop.contains(path)" in kept
    assert "return" in kept
    for token in ("setIDT", "5600", "6504", "24", "30"):
        assert token not in kept, token
    note = clip.split("static func importDuplicateNote")[1].split("func importURL")[0]
    assert "count > 0" in note
    assert 'return ""' in note
    assert "同一文件" in note
    assert "没有另加一行" in note
    for token in ("5600", "6504", "没有能读的素材"):
        assert token not in note, token
    apply = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert "importPathIsAlreadyKept" in apply
    assert "refusedThisDrop" in apply
    assert "alreadyListed += 1" in apply
    assert "acceptedThisDrop.insert(path)" in apply
    assert "var added: [Clip] = []" in apply
    assert "repeated += 1" in apply
    assert "importDuplicateNote(count: repeated)" in apply
    assert "added.isEmpty, skipped.isEmpty, repeated == 0" in apply
    assert "if !added.isEmpty {\n                    self.refreshPreview()" in apply
    assert "selectedID = pending.id" in apply
    for token in ("setIDT", "setExposureStops", "setPreviewFrame", "setWBParams"):
        assert token not in apply, token
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert "同一文件再拖一次，不另加一行" in sidebar
    plan = _read(PLAN)
    assert "同一文件 N 条已经在列表里，没有另加一行。" in plan
    assert "全是重复时，筛选和查找也不动" in plan
    assert "不把当前画面再解一遍" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_add_panel_sticks_to_the_window_and_reopens_the_last_folder():
    """添加… is a sheet on this window. Cancel reads nothing. Next open starts at the last folder."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    present = clip.split("func presentImporter()")[1].split("func presentDeliverSheet()")[0]
    assert "beginSheetModal" in present
    assert "panel.begin" in present
    assert "showImporter = false" in present
    assert "guard response == .OK" in present
    assert present.index("showImporter = false") < present.index("guard response == .OK")
    assert "handleImporter" in present
    assert "lastImportDirectoryURL" in present
    assert "directoryURL = remembered" in present
    assert "取消则不读入" in present
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in present, token
    remembered = clip.split("static func directoryToRememberAfterImport")[1].split("func exportResolve")[0]
    assert "isDir.boolValue" in remembered
    assert "return standard" in remembered
    assert "deletingLastPathComponent" in remembered
    assert "return nil" in remembered
    for token in ("setIDT", "5600", "6504", "24", "30"):
        assert token not in remembered, token
    apply = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert "directoryToRememberAfterImport" in apply
    assert "rememberImportDirectory" in apply
    hint = clip.split("var loopStepHint")[1].split("var showsProcessLockedButton")[0]
    assert "正在打开添加" in hint
    settings = _read(ROOT / "macos/LogBridge/LogBridge/Models/AppSettings.swift")
    assert "lastImportDirectoryPath" in settings
    assert "logbridge.lastImportDirectory" in settings
    assert "lastImportDirectoryURL" in settings
    content = _read(CONTENT)
    assert "fileImporter" not in content
    assert "showImporter" in content
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('Button("添加…")')[1].split('Button("设置…")')[0]
    assert "showImporter" in menu
    plan = _read(PLAN)
    assert "正在打开添加" in plan
    assert "面板贴在这个窗口上" in plan
    assert "取消则不读入" in plan
    assert "不在 ⌘, 里" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_short_pair_list_locks_from_a_digit_without_guessing_the_catalog():
    """Digits lock a two-row S-Log3 / C-Log list. The full catalog has no digit."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    gate = clip.split("func canLockShortListPair")[1].split("func lockShortListPair")[0]
    assert "pairListShowsSearchAfter" in gate
    assert "pickerPairs" in gate
    assert "isStub" in gate
    assert "isWritingDeliverables" in gate
    assert "showSettings" in gate
    assert "showImporter" in gate
    assert "showDeliverSheet" in gate
    assert "openingExportFolder" in gate
    assert "oneBased <= pairs.count" in gate
    for token in ("5600", "6504", "setIDT", "setExposureStops", "24", "30"):
        assert token not in gate, token
    lock = clip.split("func lockShortListPair")[1].split("func nextPendingClip")[0]
    assert "canLockShortListPair" in lock
    assert "clip.idt == pair, clip.hasLockedPair { return true }" in lock
    assert "stopPreviewPlayback()" in lock
    assert "setIDT(clip.id, pair)" in lock
    assert lock.index("return true") < lock.index("stopPreviewPlayback()")
    for token in ("setExposureStops", "setWBParams", "setPreviewFrame", "setODT", "5600", "6504", "24", "30"):
        assert token not in lock, token
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    choices = inspector.split("struct PairedIDTChoices")[1].split("struct InspectorView")[0]
    assert "pairListShowsSearchAfter" in choices
    assert "shortListKeyLabel" in choices
    assert "锁定这一列" in choices
    assert "没有数字键" in choices
    assert "不从整表里猜" in choices
    assert "帧和播放留着" in choices
    assert "monospacedDigit" in choices
    content = _read(CONTENT)
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "consumeShortPairKey" in monitor
    assert "onLockShortPair" in monitor
    assert "lockShortListPair" in content
    assert "(1...4).contains(digit)" in monitor
    assert "isArrowConsumedByTextInput" in monitor
    assert "isEscapeReservedByPresentedUI" in monitor
    assert "flags.isEmpty" in monitor
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('CommandMenu("调色")')[1]
    first = menu.split('Button("锁定第 1 对")')[1].split('Button("锁定第 2 对")')[0]
    assert "lockShortListPair(at: 1)" in first
    assert "canLockShortListPair(at: 1)" in first
    assert "keyboardShortcut" not in first
    assert 'Button("锁定第 4 对")' in menu
    assert "lockShortListPair(at: 4)" in menu
    plan = _read(PLAN)
    assert "行前标 1、2" in plan
    assert "按 1 也不会从整表里锁第一行" in plan
    assert "锁定第 1 对" in plan
    assert "不改这一套曝光和白平衡" in plan
    assert "菜单上不标快捷键" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_pending_selection_scrolls_the_inspector_back_to_the_paired_idt():
    """A short window can leave the pair list above the fold. Pending selection returns there."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func inspectorScrollAnchor")[1].split("写出说明上的这一套")[0]
    assert "inspectorPairedIDTAnchor" in fn
    assert "selectedIsPending ? inspectorPairedIDTAnchor : nil" in fn
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "setODT", "5600", "6504", "24", "30"):
        assert token not in fn, token
    content = _read(CONTENT)
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert "ScrollViewReader" in column
    assert "inspectorPairedIDTAnchor" in column
    assert "inspectorScrollAnchor" in column
    assert "selectedIsPending: session.selectedClip?.isPending == true" in column
    assert "proxy.scrollTo(anchor, anchor: .top)" in column
    assert column.index("onChange(of: session.selectedID)") < column.index("proxy.scrollTo")
    assert "回到成对 IDT" in column
    assert "不跟着滚" in column
    assert "不改这一套调色，不改预览帧，也不参与写出" in column
    plan = _read(PLAN)
    assert "这一栏回到成对 IDT" in plan
    assert "换到已锁定时不跟着滚" in plan
    assert "不改这一套调色，不改预览帧，也不参与写出" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_inspector_header_pins_the_locked_pair_and_does_not_invent_one():
    """The fixed title keeps a locked pair visible while the grade scrolls. Pending stays blank."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func inspectorPinnedPairLine")[1].split("写出说明上的这一套")[0]
    assert "guard hasLockedPair else { return nil }" in fn
    assert "trimmingCharacters" in fn
    assert "guard !trimmed.isEmpty else { return nil }" in fn
    assert "return trimmed" in fn
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "setODT", "5600", "6504", "24", "30"):
        assert token not in fn, token
    content = _read(CONTENT)
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    header, scroll = column.split("ScrollViewReader", 1)
    assert "inspectorPinnedPairLine" in header
    assert "inspectorPinnedPairLine" not in scroll
    assert "clip.hasLockedPair" in header
    assert "clip.idt?.pairLabel" in header
    assert "待选不在标题里写一对" in header
    assert "不改这一套调色，不改预览帧，也不参与写出" in header
    assert "PairedIDTBar" in scroll
    plan = _read(PLAN)
    assert "标题下固定写出这一对的名字" in plan
    assert "待选不在标题里写一对" in plan
    assert "不猜成对 IDT" in plan
    assert "滚到曝光和白平衡时这一行还在" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_write_sheet_names_the_last_export_folder_without_the_full_path():
    """The sheet, the bar, and the folder panel name the last folder, or say it is gone."""
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    name = clip.split("static func exportFolderResumeName")[1].split("static func exportFolderOpenNote")[0]
    assert "lastPathComponent" in name
    assert 'name == "/"' in name
    assert "return nil" in name
    assert "return name" in name
    assert ".path" not in name
    for token in ("setIDT", "setExposureStops", "5600", "6504", "24", "30"):
        assert token not in name, token
    note = clip.split("static func exportFolderOpenNote")[1].split("func processLockedClips()")[0]
    assert "选文件夹会从上次写出的文件夹打开" in note
    assert "还没有上次写出的文件夹" in note
    assert "选文件夹从系统给出的位置打开" in note
    assert "folderName" in note
    for token in ("setIDT", "setExposureStops", "setWBParams", "5600", "6504", ".path"):
        assert token not in note, token
    body = clip.split("func processLockedClips()")[1].split("static func exportFolderHostWindow")[0]
    assert "exportFolderResumeName(from: remembered)" in body
    assert "exportFolderOpenNote(folderName: resumeName)" in body
    assert "lastExportDirectoryURL" in body
    assert "panel.directoryURL = remembered" in body
    assert body.index("exportFolderResumeName") < body.index("panel.directoryURL = remembered")
    assert "取消则不写出。" in body
    for token in ("setIDT", "setExposureStops", "5600", "6504"):
        assert token not in body.split("panel.message")[1].split("openingExportFolder = true")[0], token
    deliver = _read(DELIVER)
    assert "session.exportFolderOpenNote" in deliver
    assert "不写整条路径" in deliver
    assert "选文件夹贴在这个窗口上" in deliver
    assert "取消则不写出" in deliver
    content = _read(CONTENT)
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert "session.exportFolderOpenNote" in bar
    assert "选文件夹会贴在这个窗口上" in bar
    assert "取消则不写出" in bar
    settings = _read(SETTINGS)
    assert "lastExportDirectory" not in settings
    assert "exportFolderOpenNote" not in settings
    plan = _read(PLAN)
    assert "选文件夹会从上次写出的文件夹打开" in plan
    assert "不写整条路径" in plan
    assert "选文件夹从系统给出的位置打开" in plan
    assert "不在 ⌘, 里" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def test_preview_slider_keeps_its_own_row_when_the_window_is_narrow():
    """The scrub slider stays a full row. Transport buttons scroll under it."""
    content = _read(CONTENT)
    bar = content.split("struct PreviewScrubBar")[1].split("struct WriteProgressLine")[0]
    play = 'Button(session.isPreviewPlaying ? "暂停" : "播放")'
    assert "Slider(" in bar
    assert play in bar
    assert bar.index("Slider(") < bar.index(play)
    assert bar.index(play) < bar.index('Button("上一帧")')
    assert bar.index('Button("上一帧")') < bar.index('Button("下一帧")')
    assert bar.index('Button("下一帧")') < bar.index('TextField("0:01.500"')
    assert "ScrollView(.horizontal" in bar
    assert "scrollBounceBehavior(.basedOnSize, axes: .horizontal)" in bar
    assert "fixedSize(horizontal: false, vertical: true)" in bar
    assert "maxHeight: 56" in bar
    assert "不把滑条挤没" in bar
    assert "可横着滚" in bar
    assert "这不是时间线" in bar
    assert "showsPreviewSecondStep" in bar
    transport = bar.split("Slider(")[1].split("if session.previewClockText")[0]
    for token in ("setExposureStops", "setWBParams", "setIDT", "5600", "6504"):
        assert token not in transport, token
    plan = _read(PLAN)
    assert "预览帧滑条自己占一行" in plan
    assert "不把滑条挤没" in plan
    assert "可横着滚" in plan
    assert "滑条留在上面" in plan
    assert "滑条下面这一行" in plan
    assert "这不是时间线" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def _loop_step_index(
    *,
    clips_empty,
    importing,
    opening_folder,
    writing,
    locked_count,
    selected_pending,
):
    """Same order as SessionModel.loopStepIndex. Write wins, then import, then pick IDT."""
    if writing or opening_folder:
        return 3
    if clips_empty or importing:
        return 0
    if locked_count == 0 or selected_pending:
        return 1
    return 2


def test_loop_steps_follow_import_grade_and_write():
    """The title steps follow the open path. 调色 only reveals the knobs."""
    assert _loop_step_index(
        clips_empty=True, importing=False, opening_folder=False,
        writing=False, locked_count=0, selected_pending=False,
    ) == 0
    assert _loop_step_index(
        clips_empty=False, importing=True, opening_folder=False,
        writing=False, locked_count=2, selected_pending=False,
    ) == 0
    assert _loop_step_index(
        clips_empty=False, importing=False, opening_folder=False,
        writing=True, locked_count=0, selected_pending=False,
    ) == 3
    assert _loop_step_index(
        clips_empty=False, importing=False, opening_folder=True,
        writing=False, locked_count=1, selected_pending=False,
    ) == 3
    assert _loop_step_index(
        clips_empty=True, importing=True, opening_folder=False,
        writing=True, locked_count=0, selected_pending=False,
    ) == 3
    assert _loop_step_index(
        clips_empty=False, importing=False, opening_folder=False,
        writing=False, locked_count=0, selected_pending=True,
    ) == 1
    assert _loop_step_index(
        clips_empty=False, importing=False, opening_folder=False,
        writing=False, locked_count=1, selected_pending=True,
    ) == 1
    assert _loop_step_index(
        clips_empty=False, importing=False, opening_folder=False,
        writing=False, locked_count=2, selected_pending=False,
    ) == 2
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func loopStepIndex(")[1].split("var loopStepIndex")[0]
    assert "if writing || openingFolder { return 3 }" in fn
    assert "if clipsEmpty || importing { return 0 }" in fn
    assert "if lockedCount == 0 || selectedPending { return 1 }" in fn
    assert fn.index("return 3") < fn.index("return 0") < fn.index("return 1")
    assert "return 2" in fn
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in fn, token
    pending = clip.split("func focusPendingIDT()")[1].split("func focusGradeControls()")[0]
    assert "inspectorPairedIDTAnchor" in pending
    assert "selectNextPendingFromMenu()" in pending
    assert "isPending" in pending
    for token in ("setIDT", "setExposureStops", "setWBParams", "5600", "6504"):
        assert token not in pending, token
    grade = clip.split("func focusGradeControls()")[1].split("func requestInspectorScroll")[0]
    assert "inspectorExposureAnchor" in grade
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in grade, token
    content = _read(CONTENT)
    strip = content.split("struct LoopStepStrip")[1].split("struct WorkspaceToolbar")[0]
    assert "presentImporter()" in strip
    assert "focusPendingIDT()" in strip
    assert "focusGradeControls()" in strip
    assert "presentDeliverSheet()" in strip
    for label in ("导入", "选 IDT", "调色", "写出"):
        assert label in strip
    toolbar = content.split("struct WorkspaceToolbar")[1].split("enum MonitorLayout")[0]
    assert "LoopStepStrip(session: session)" in toolbar
    assert "session.loopStepHint" in toolbar
    header = content.split("struct MonitorHeader")[1].split("struct InspectorColumn")[0]
    assert "gradeClipTitle" in header
    assert "gradeNumberLine" in header
    assert "fixedSize(horizontal: true, vertical: false)" in header
    assert header.index("Text(gradeClipTitle)") < header.index("Text(gradeNumberLine)")
    assert "看调色前 ·" in header
    assert "对照 ·" in header
    column = content.split("struct InspectorColumn")[1].split("struct ClipListArrowMonitor")[0]
    assert column.index("onChange(of: session.selectedID)") < column.index("onChange(of: session.inspectorScrollToken)")
    inspector = _read(ROOT / "macos/LogBridge/LogBridge/Views/InspectorView.swift")
    body = inspector.split("struct InspectorView")[1].split("struct WBInspector")[0]
    assert "inspectorExposureAnchor" in body
    reveal = body.split("onChange(of: session.inspectorScrollToken)")[1]
    assert "exposureOpen = true" in reveal
    assert "wbOpen = true" in reveal
    for token in ("setExposureStops", "setWBParams", "setIDT", "5600", "6504"):
        assert token not in reveal, token
    plan = _read(PLAN)
    assert "导入、选 IDT、调色、写出" in plan
    assert "不改数字，不改预览帧" in plan
    assert "文件名可以截断" in plan
    assert "不猜成对 IDT" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def _clip_list_filter_count(filter_name, clip_count, pending_count, locked_count):
    """Same branches as SessionModel.clipListFilterCount. The query is not a count."""
    if filter_name == "all":
        return clip_count
    if filter_name == "pending":
        return pending_count
    if filter_name == "locked":
        return locked_count
    raise AssertionError(filter_name)


def _clip_list_filter_title(filter_name, count):
    labels = {"all": "全部", "pending": "待选", "locked": "已锁定"}
    return f"{labels[filter_name]} {count}"


def _clip_list_remainder_line(pending_count, locked_count):
    if pending_count > 0:
        return f"还有 {pending_count} 条待选。点一条，到右侧选成对 IDT。"
    if locked_count > 0:
        return "成对 IDT 都已选上。可调色，再写出。"
    return None


def test_clip_list_filter_shows_bin_counts_and_the_remaining_step():
    """Filter segments name how many clips are pending. Search does not change that count."""
    assert _clip_list_filter_count("all", 5, 2, 3) == 5
    assert _clip_list_filter_count("pending", 5, 2, 3) == 2
    assert _clip_list_filter_count("locked", 5, 2, 3) == 3
    assert _clip_list_filter_title("pending", 2) == "待选 2"
    assert _clip_list_filter_title("locked", 0) == "已锁定 0"
    assert _clip_list_remainder_line(2, 3) == "还有 2 条待选。点一条，到右侧选成对 IDT。"
    assert _clip_list_remainder_line(0, 4) == "成对 IDT 都已选上。可调色，再写出。"
    assert _clip_list_remainder_line(0, 0) is None
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    count = clip.split("static func clipListFilterCount")[1].split("static func clipListFilterTitle")[0]
    assert "case .all: return clipCount" in count
    assert "case .pending: return pendingCount" in count
    assert "case .locked: return lockedCount" in count
    assert "clipListQuery" not in count
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in count, token
    title = clip.split("static func clipListFilterTitle")[1].split("static func clipListRemainderLine")[0]
    assert "filter.label" in title
    assert "5600" not in title
    line = clip.split("static func clipListRemainderLine")[1].split("func clipListFilterTitle(_")[0]
    assert "还有 \\(pendingCount) 条待选。点一条，到右侧选成对 IDT。" in line
    assert "成对 IDT 都已选上。可调色，再写出。" in line
    assert "return nil" in line
    assert line.index("pendingCount > 0") < line.index("lockedCount > 0")
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in line, token
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    picker = sidebar.split('Picker("列表"')[1].split('TextField("查找文件名"')[0]
    assert "session.clipListFilterTitle(item)" in picker
    assert "session.clipListRemainderLine" in picker
    assert "还有待选时，点一条，到右侧选成对 IDT" in picker
    assert "查找不改这些数字" in picker
    assert "不改选中，不改这一套调色，不改成对 IDT，不改预览帧，也不参与写出" in picker
    plan = _read(PLAN)
    assert "每一段写出条数" in plan
    assert "查找不改这些数字" in plan
    assert "还有 N 条待选" in plan
    assert "成对 IDT 都已选上。可调色，再写出。" in plan
    assert "不改选中，不改这一套调色，不改成对 IDT，不改预览帧，不参与写出" in plan
    for token in BANNED_CONTACT:
        assert token not in plan


def _loop_return_action(*, blocked, clips_empty, selected_pending, selected_locked):
    """Same order as SessionModel.loopReturnAction. Write is not a Return action."""
    if blocked:
        return "none"
    if clips_empty:
        return "import"
    if selected_pending:
        return "idt"
    if selected_locked:
        return "grade"
    return "none"


def test_return_follows_the_current_loop_step_without_writing():
    """Return opens add, scrolls to the pair list, or reveals exposure. It does not write."""
    assert _loop_return_action(
        blocked=False, clips_empty=True, selected_pending=False, selected_locked=False
    ) == "import"
    assert _loop_return_action(
        blocked=True, clips_empty=True, selected_pending=False, selected_locked=False
    ) == "none"
    assert _loop_return_action(
        blocked=False, clips_empty=False, selected_pending=True, selected_locked=False
    ) == "idt"
    assert _loop_return_action(
        blocked=False, clips_empty=False, selected_pending=True, selected_locked=True
    ) == "idt"
    assert _loop_return_action(
        blocked=False, clips_empty=False, selected_pending=False, selected_locked=True
    ) == "grade"
    assert _loop_return_action(
        blocked=False, clips_empty=False, selected_pending=False, selected_locked=False
    ) == "none"
    assert _loop_return_action(
        blocked=True, clips_empty=False, selected_pending=False, selected_locked=True
    ) == "none"
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func loopReturnAction(")[1].split("var canFollowLoopWithReturn")[0]
    assert 'if blocked { return "none" }' in fn
    assert 'if clipsEmpty { return "import" }' in fn
    assert 'if selectedPending { return "idt" }' in fn
    assert 'if selectedLocked { return "grade" }' in fn
    assert fn.index('return "none"') < fn.index('return "import"')
    assert fn.index('return "import"') < fn.index('return "idt"')
    assert fn.index('return "idt"') < fn.index('return "grade"')
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "presentDeliverSheet", "5600", "6504"):
        assert token not in fn, token
    body = clip.split("func followLoopWithReturn()")[1].split("func requestInspectorScroll")[0]
    assert "presentImporter()" in body
    assert "inspectorPairedIDTAnchor" in body
    assert "focusGradeControls()" in body
    assert "presentDeliverSheet" not in body
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in body, token
    hint = clip.split("var loopStepHint")[1].split("var exportFolderOpenNote")[0]
    assert "按回车也是添加" in hint
    assert "按回车滚到这一列，不替你选" in hint
    assert "按回车滚到曝光，不改数字" in hint
    content = _read(CONTENT)
    monitor = content.split("struct ClipListArrowMonitor")[1].split("struct ProcessLockedBar")[0]
    assert "case 36, 76:" in monitor
    assert "onFollowLoop" in monitor
    assert "isArrowConsumedByTextInput" in monitor
    returns = monitor.split("case 36, 76:")[1].split("default:")[0]
    assert "returnFlags.isEmpty" in returns
    assert "isArrowConsumedByTextInput" in returns
    empty = content.split("if session.clips.isEmpty {")[1].split("} else if let clip = session.selectedClip, clip.isPending")[0]
    assert "或按回车" in empty
    pending = content.split("clip.isPending, !session.isExporting")[1].split("private var compareBeforePane")[0]
    assert "按回车滚到右侧成对 IDT" in pending
    assert "不替你选" in pending
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    zone = sidebar.split("struct DropZone")[1].split("struct ClipRow")[0]
    assert "按回车也是添加。取消则不读入。" in zone
    app = _read(ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift")
    menu = app.split('Button("跟当前这一步")')[1].split('Button("曝光 +0.10")')[0]
    assert "followLoopWithReturn()" in menu
    assert "canFollowLoopWithReturn" in menu
    assert "keyboardShortcut" not in menu
    assert "不打开写出说明" in menu
    plan = _read(PLAN)
    assert "回车跟当前这一步" in plan
    assert "回车不打开写出说明" in plan
    assert "菜单上不标快捷键，避免抢走输入框里的回车" in plan
    assert "列表里已经有素材时，回车不再打开添加" in plan
    readme = _read(ROOT / "README.md")
    assert "本机打开试用" in readme
    assert "macos/LogBridge/LogBridge.xcodeproj" in readme
    assert "按回车滚到成对 IDT" in readme
    for token in BANNED_CONTACT:
        assert token not in plan
        assert token not in readme.split("## 本机打开试用")[1].split("## Quick start")[0]


def _monitor_will_write_line(
    *, selected_locked, exporting, name, locked_count, pending_count, can_open_sheet
):
    """Same branches as SessionModel.monitorWillWriteLine. Pending clips stay quiet."""
    if not selected_locked or exporting or locked_count <= 0:
        return None
    name = name.strip()
    if not name:
        return None
    action = "点这一行打开写出说明，再选文件夹。" if can_open_sheet else None
    if locked_count == 1 and pending_count == 0:
        if action:
            return f"将得到 {name}。{action}"
        return f"将得到 {name}。"
    if pending_count > 0:
        base = f"已锁定 {locked_count} 条会写出，待选 {pending_count} 条会跳过。这一条将得到 {name}"
        if action:
            return f"{base}。{action}"
        return base
    base = f"已锁定 {locked_count} 条都会写出。这一条将得到 {name}"
    if action:
        return f"{base}。{action}"
    return base


def test_monitor_names_the_file_this_locked_clip_will_write():
    """A locked clip shows the same deliverable name as the write sheet. Pending stays blank.

    When the write sheet can open, the line says a click opens it. It does not
    pick a folder. A covering sheet keeps the name and is not a button.
    """
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="A_Rec709_proxy.mov",
        locked_count=1, pending_count=0, can_open_sheet=True,
    ) == "将得到 A_Rec709_proxy.mov。点这一行打开写出说明，再选文件夹。"
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="A_Rec709_proxy.mov",
        locked_count=1, pending_count=0, can_open_sheet=False,
    ) == "将得到 A_Rec709_proxy.mov。"
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="  A_ACES2065-1_proxy  ",
        locked_count=3, pending_count=0, can_open_sheet=True,
    ) == "已锁定 3 条都会写出。这一条将得到 A_ACES2065-1_proxy。点这一行打开写出说明，再选文件夹。"
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="A_ACES2065-1_proxy",
        locked_count=3, pending_count=0, can_open_sheet=False,
    ) == "已锁定 3 条都会写出。这一条将得到 A_ACES2065-1_proxy"
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="A_Rec709_proxy.mov",
        locked_count=1, pending_count=2, can_open_sheet=True,
    ) == "已锁定 1 条会写出，待选 2 条会跳过。这一条将得到 A_Rec709_proxy.mov。点这一行打开写出说明，再选文件夹。"
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="A_Rec709_proxy.mov",
        locked_count=1, pending_count=2, can_open_sheet=False,
    ) == "已锁定 1 条会写出，待选 2 条会跳过。这一条将得到 A_Rec709_proxy.mov"
    assert _monitor_will_write_line(
        selected_locked=False, exporting=False, name="A_Rec709_proxy.mov",
        locked_count=1, pending_count=1, can_open_sheet=True,
    ) is None
    assert _monitor_will_write_line(
        selected_locked=True, exporting=True, name="A_Rec709_proxy.mov",
        locked_count=2, pending_count=0, can_open_sheet=True,
    ) is None
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="   ",
        locked_count=1, pending_count=0, can_open_sheet=True,
    ) is None
    assert _monitor_will_write_line(
        selected_locked=True, exporting=False, name="A_Rec709_proxy.mov",
        locked_count=0, pending_count=0, can_open_sheet=True,
    ) is None
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    fn = clip.split("static func monitorWillWriteLine(")[1].split("static func monitorPaneGapNote(")[0]
    assert "guard selectedLocked, !exporting, lockedCount > 0 else { return nil }" in fn
    assert "trimmingCharacters" in fn
    assert 'let action: String? = canOpenSheet ? "点这一行打开写出说明，再选文件夹。" : nil' in fn
    assert 'return "将得到 \\(name)。\\(action)"' in fn
    assert 'return "将得到 \\(name)。"' in fn
    assert "待选 \\(pendingCount) 条会跳过" in fn
    assert "已锁定 \\(lockedCount) 条都会写出" in fn
    assert fn.index("pendingCount > 0") < fn.index("条都会写出")
    assert "canOpenSheet" in fn
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "setODT", ".path", "5600", "6504", "24", "30"):
        assert token not in fn, token
    prop = clip.split("var monitorWillWriteLine")[1].split("static let inspectorPairedIDTAnchor")[0]
    assert "plannedDeliverableName(format: settings.exportFormat)" in prop
    assert "isWritingDeliverables" in prop
    assert "clip.hasLockedPair" in prop
    assert "canStartWriteFromLoop" in prop
    opener = clip.split("func openWriteSheetFromMonitorLine()")[1].split("func presentDeliverSheet()")[0]
    assert "canStartWriteFromLoop" in opener
    assert "hasLockedPair" in opener
    assert "presentDeliverSheet()" in opener
    assert "processLockedClips" not in opener
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in opener, token
    content = _read(CONTENT)
    preview = content.split("struct SplitPreview")[1].split("private var compareBeforePane")[0]
    assert "session.monitorWillWriteLine" in preview
    assert preview.index("PreviewScrubBar(session: session)") < preview.index("session.monitorWillWriteLine")
    assert preview.index("session.monitorWillWriteLine") < preview.index("session.selectedClip?.previewCaption")
    assert "session.isExporting" in preview
    exporting = preview.split("if session.isExporting {")[1].split("} else {")[0]
    assert "monitorWillWriteLine" not in exporting
    clickable = preview.split("if session.canStartWriteFromLoop {")[1].split("} else {")[0]
    assert "openWriteSheetFromMonitorLine()" in clickable
    assert "processLockedClips" not in clickable
    quiet = preview.split("if session.canStartWriteFromLoop {")[1].split("} else {", 1)[1].split("if let caption")[0]
    assert "openWriteSheetFromMonitorLine" not in quiet
    assert "不写整条路径" in preview
    assert "truncation: .middle" in preview
    assert "这一行只留名字" in preview
    plan = _read(PLAN)
    assert "将得到 {名}。点这一行打开写出说明，再选文件夹。" in plan
    assert "待选不出现这一行" in plan
    assert "不写整条路径" in plan
    assert "这一行只留名字" in plan
    assert "不改这一套曝光和白平衡，也不改成对 IDT，也不改预览帧" in plan
    readme = _read(ROOT / "README.md")
    trial = readme.split("## 本机打开试用")[1].split("## Quick start")[0]
    assert "将得到的文件名" in trial
    assert "待选不写这一行" in trial
    assert "点这一行也打开写出说明" in trial
    for token in BANNED_CONTACT:
        assert token not in plan
        assert token not in trial


def _list_reveal_adjustments(*, has_selection, matches_filter, matches_query):
    """Same branches as SessionModel.listRevealAdjustments. Already visible stays put."""
    if not has_selection or (matches_filter and matches_query):
        return None
    return (not matches_filter, not matches_query)


def test_hidden_selection_can_be_shown_again_without_moving_the_grade():
    """「显示这条」 only widens the list. It does not move the selection or the grade.

    A pending filter that hid a just-locked clip goes back to 全部.
    A filename query that hid the row is cleared. Both, when both hide it.
    """
    assert _list_reveal_adjustments(
        has_selection=False, matches_filter=False, matches_query=False
    ) is None
    assert _list_reveal_adjustments(
        has_selection=True, matches_filter=True, matches_query=True
    ) is None
    assert _list_reveal_adjustments(
        has_selection=True, matches_filter=False, matches_query=True
    ) == (True, False)
    assert _list_reveal_adjustments(
        has_selection=True, matches_filter=True, matches_query=False
    ) == (False, True)
    assert _list_reveal_adjustments(
        has_selection=True, matches_filter=False, matches_query=False
    ) == (True, True)
    clip = _read(ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift")
    filt = clip.split("static func clipMatchesListFilter")[1].split("static func clipMatchesListQuery")[0]
    assert "case .all:" in filt
    assert "return true" in filt
    assert "case .pending:" in filt
    assert "return !clip.hasLockedPair" in filt
    assert "case .locked:" in filt
    assert "return clip.hasLockedPair" in filt
    assert "clipListQuery" not in filt
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "selectedID", "5600", "6504"):
        assert token not in filt, token
    adjust = clip.split("static func listRevealAdjustments(")[1].split("func revealSelectedClipInList()")[0]
    assert "guard hasSelection, !(matchesFilter && matchesQuery) else { return nil }" in adjust
    assert "return (!matchesFilter, !matchesQuery)" in adjust
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "selectedID", "5600", "6504"):
        assert token not in adjust, token
    body = clip.split("func revealSelectedClipInList()")[1].split("private var sharedGradeIsFactory")[0]
    assert "listRevealAdjustments(" in body
    assert "clipMatchesListFilter(clip, filter: clipListFilter)" in body
    assert "clipMatchesListQuery(clip, query: clipListQuery)" in body
    assert "clipListFilter = .all" in body
    assert 'clipListQuery = ""' in body
    assert "listRevealToken += 1" in body
    assert body.index("clearFilter") < body.index("clearQuery")
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "selectedID", "5600", "6504", "processLockedClips"):
        assert token not in body, token
    sidebar = _read(ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift")
    hidden = sidebar.split("hiddenSelectionNote")[1].split("ForEach(session.visibleClips)")[0]
    assert 'Button("显示这条")' in hidden
    assert "revealSelectedClipInList()" in hidden
    assert "不改选中，不改这一套调色，不改成对 IDT，不改预览帧，也不参与写出" in hidden
    scroll = sidebar.split("onChange(of: session.listRevealToken)")[1].split("background(Color.primary")[0]
    assert "proxy.scrollTo(id, anchor: .center)" in scroll
    assert "session.visibleClips.contains" in scroll
    plan = _read(PLAN)
    assert "旁边有「显示这条」" in plan
    assert "两样都挡着就一起改" in plan
    assert "已经看得到时没有这一下" in plan
    assert "点完列表滚到这一行" in plan
    readme = _read(ROOT / "README.md")
    trial = readme.split("## 本机打开试用")[1].split("## Quick start")[0]
    assert "显示这条" in trial
    for token in BANNED_CONTACT:
        assert token not in plan
        assert token not in trial


def _sheet_scroll_closes_before(source: str, marker: str) -> bool:
    """The first ScrollView in source closes before marker. Buttons can sit under it."""
    start = source.find("ScrollView {")
    if start < 0 or marker not in source:
        return False
    depth = 0
    opened = source.find("{", start)
    for index in range(opened, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index < source.find(marker)
    return False


def test_write_sheet_pins_confirm_and_marks_the_monitor_clip():
    """The confirm stays under the notes. The monitor's clip is marked and scrolled into view.

    Marking does not start a write and does not edit the shared grade.
    """
    deliver = _read(DELIVER)
    body = deliver.split("var body: some View")[1].split("private var skippedClips")[0]
    assert body.count("ScrollView {") == 1
    assert _sheet_scroll_closes_before(body, 'Button("选出文件夹并写出")')
    assert _sheet_scroll_closes_before(body, 'Button("关闭")')
    assert body.index("ScrollView {") < body.index('Button("选出文件夹并写出")')
    assert ".frame(maxHeight: 480)" in body
    assert ".keyboardShortcut(.defaultAction)" in body
    assert ".keyboardShortcut(.cancelAction)" in body
    assert "deliverSheetConfirmed = true" in body
    assert "processLockedClips" not in deliver
    listing = deliver.split("private var clipList")[1].split("private func revealCurrentClip")[0]
    assert listing.count("clip.id == session.selectedID") == 2
    assert listing.count(".id(clip.id)") == 2
    assert "proxy.scrollTo(id, anchor: .center)" in deliver
    assert 'Text("当前这条")' in deliver
    assert "会写出或会跳过都标" in deliver
    for token in ("setIDT", "setExposureStops", "setWBParams", "setPreviewFrame", "5600", "6504"):
        assert token not in deliver, token
    plan = _read(PLAN)
    assert "当前这一条标「当前这条」" in plan
    assert "留在说明下面" in plan
    assert "不在这一下开始写文件" in plan
    readme = _read(ROOT / "README.md")
    trial = readme.split("## 本机打开试用")[1].split("## Quick start")[0]
    assert "当前这一条标「当前这条」" in trial
    assert "确认和关闭留在下面" in trial
    for token in BANNED_CONTACT:
        assert token not in plan
        assert token not in trial
