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
    change = content.split(".onChange(of: session.selectedID)")[1].split(".background")[0]
    assert "noteSelectionForSharedGrade" in change
    assert "applyClipWBToGraph" not in change
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
