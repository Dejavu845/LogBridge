import SwiftUI

/// Single window for local grading and delivery. Not an editor timeline.
/// List | large preview | inspector that follows the selection.
/// Global preferences stay on ⌘,. Per-clip IDT / exposure / WB live in the inspector.
/// Write is its own sheet, then the existing folder panel. Not a save dialog.
/// Default export: ProRes 422 HQ. Advanced: ACEScct / EXR, nodes, histogram.
/// UI copy uses "已实现（未验证）". Primary action is "处理已锁定片段".
/// Unlocked IDT is skipped, never guessed.
struct ContentView: View {
    @StateObject private var session = SessionModel()
    @ObservedObject private var settings = AppSettings.shared
    @State private var monitorZoom: MonitorZoom = .fit
    @State private var monitorPan = MonitorPanBus()

    var body: some View {
        VStack(spacing: 0) {
            WorkspaceToolbar(session: session)
            Divider()
            HSplitView {
                ClipSidebarView(session: session)
                    .frame(minWidth: 240, idealWidth: 292, maxWidth: 380)
                VStack(spacing: 0) {
                    MonitorHeader(session: session, layout: monitorLayoutBinding, zoom: $monitorZoom)
                        .onChange(of: monitorZoom) { _, _ in
                            monitorPan.reset()
                        }
                        .onChange(of: session.selectedID) { _, _ in
                            monitorPan.reset()
                        }
                    SplitPreview(
                        session: session,
                        layout: session.monitorLayout,
                        zoom: monitorZoom,
                        panBus: monitorPan
                    )
                        .frame(maxWidth: .infinity, minHeight: 200, maxHeight: .infinity)
                        .layoutPriority(1)
                    ProcessLockedBar(session: session)
                    AdvancedPanel(session: session, isExpanded: $settings.advancedPanelExpanded)
                    StatusBar(session: session)
                }
                .frame(minWidth: 560)
                .layoutPriority(1)
                InspectorColumn(session: session)
                    .frame(minWidth: 280, idealWidth: 332, maxWidth: 420)
            }
        }
        .preferredColorScheme(settings.windowAppearance.colorScheme)
        .onDrop(of: [.fileURL], isTargeted: $session.dropTargeted) { providers in
            session.importProviders(providers)
            return true
        }
        .sheet(isPresented: presentedSheet, onDismiss: {
            session.activeSheet = nil
        }) {
            if session.activeSheet == .deliver {
                DeliverSheet(session: session)
            } else {
                SettingsView(settings: session.settings, session: session)
            }
        }
        .onChange(of: session.selectedID) { _, _ in
            if let clip = session.selectedClip {
                session.noteSelectionForSharedGrade(clip)
            }
            session.refreshPreview()
        }
        .background {
            ClipListArrowMonitor(
                handler: { delta in
                    session.selectAdjacentClip(delta)
                },
                onEscape: {
                    session.cancelWritingFromEscape()
                },
                onDelete: {
                    session.removeSelectedClipFromSession()
                },
                onStepFrame: { delta in
                    session.stepPreviewFrame(delta)
                },
                onJumpToStart: {
                    session.jumpPreviewToStart()
                },
                onJumpToEnd: {
                    session.jumpPreviewToEnd()
                },
                onStepSecond: { direction in
                    session.stepPreviewBySecond(direction)
                },
                onTogglePlayback: {
                    session.togglePreviewPlayback()
                },
                onPlayBackward: {
                    session.playPreviewBackward()
                },
                onPausePlayback: {
                    session.pausePreviewPlayback()
                },
                onUndoGrade: {
                    session.undoSharedGrade()
                },
                onRedoGrade: {
                    session.redoSharedGrade()
                },
                onLockShortPair: { index in
                    session.lockShortListPair(at: index)
                },
                onFollowLoop: {
                    session.followLoopWithReturn()
                },
                onToggleSplitAndGrade: {
                    session.toggleSplitAndGrade()
                },
                onGradeStrokeEnd: {
                    session.closeSharedGradeStroke()
                }
            )
        }
        .onMoveCommand { direction in
            switch direction {
            case .up:
                session.selectAdjacentClip(-1)
            case .down:
                session.selectAdjacentClip(1)
            default:
                break
            }
        }
        .onDeleteCommand {
            session.removeSelectedClipFromSession()
        }
        .focusedSceneValue(\.logBridgeSession, SessionFocus(session: session))
    }

    /// Picker writes the session layout. 对照 is refused until a pair is locked.
    private var monitorLayoutBinding: Binding<MonitorLayout> {
        Binding(
            get: { session.monitorLayout },
            set: { session.setMonitorLayout($0) }
        )
    }

    /// One sheet for global preferences or the write step. Not a save dialog.
    private var presentedSheet: Binding<Bool> {
        Binding(
            get: { session.showSettings || session.showDeliverSheet },
            set: { presented in
                if !presented {
                    session.showSettings = false
                    session.showDeliverSheet = false
                }
            }
        )
    }
}

/// Four steps under the title. The current one is marked.
/// 导入 opens the add panel. 选 IDT scrolls to the pair list, or moves to the next pending clip.
/// 调色 only reveals exposure and white balance. 写出 opens the write sheet.
/// None of them assign an IDT or edit the shared grade.
private struct LoopStepStrip: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 4) {
            loopChip(
                "导入",
                index: 0,
                enabled: session.canOpenImporter,
                help: "和「添加…」一样。面板贴在这个窗口上。取消则不读入。没有素材时，回车是同一套。不改这一套曝光和白平衡。"
            ) {
                session.presentImporter()
            }
            loopChip(
                "选 IDT",
                index: 1,
                enabled: session.canFocusPendingIDT,
                help: "当前这条还没锁定，就滚到成对 IDT。已经锁定且后面还有待选，就去下一条待选，不替它选。待选时回车只滚到这一列，不替你选。不改这一套曝光和白平衡。"
            ) {
                session.focusPendingIDT()
            }
            loopChip(
                "调色",
                index: 2,
                enabled: session.canFocusGradeControls,
                help: "当前这条已锁定时，展开曝光和白平衡并滚到曝光。回车是同一套。不改数字，不改预览帧，也不改成对 IDT。"
            ) {
                session.focusGradeControls()
            }
            loopChip(
                "写出",
                index: 3,
                enabled: session.canStartWriteFromLoop,
                help: "打开写出说明。没有已锁定时不起作用。正在写出时用顶栏「取消」。回车不打开这一步。不改这一套曝光和白平衡。"
            ) {
                session.presentDeliverSheet()
            }
        }
    }

    private func loopChip(
        _ title: String,
        index: Int,
        enabled: Bool,
        help: String,
        action: @escaping () -> Void
    ) -> some View {
        let current = session.loopStepIndex == index
        return Button(title, action: action)
            .buttonStyle(.plain)
            .font(.caption.weight(current ? .semibold : .regular))
            .foregroundStyle(current ? Color.accentColor : Color.primary)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(
                Capsule().fill(current ? Color.accentColor.opacity(0.22) : Color.primary.opacity(0.05))
            )
            .disabled(!enabled)
            .help(help)
    }
}

/// Top bar: add, global settings, write. Not a multi-page shell.
private struct WorkspaceToolbar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("LogBridge")
                    .font(.headline)
                LoopStepStrip(session: session)
                Text(session.loopStepHint)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .help("打开后的下一步。导入、选成对 IDT、调色、写出，都在这一窗。")
            }
            Spacer(minLength: 12)
            Button("添加…") { session.presentImporter() }
                .controlSize(.large)
                .disabled(session.openingExportFolder || session.showImporter)
                .help("选素材或文件夹，面板贴在这个窗口上。下次从上次的文件夹打开。取消则不读入。不改这一套调色。")
            Button("设置") {
                session.presentSettings()
            }
            .controlSize(.large)
            .disabled(session.openingExportFolder || session.showImporter)
            .help("全局偏好。改完即生效。")
            Button(session.isWritingDeliverables ? "取消" : "写出") {
                if session.isWritingDeliverables {
                    session.cancelLockedDeliverables()
                } else {
                    session.presentDeliverSheet()
                }
            }
            .controlSize(.large)
            .disabled(session.openingExportFolder
                      || session.showImporter
                      || (!session.isWritingDeliverables && !session.showsProcessLockedButton))
            .help("先看写出说明。确认后选文件夹贴在这个窗口上。整段代理，代理精度。")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
    }
}

/// How the monitor uses its space. Default stays the source | grade split.
enum MonitorLayout: String, CaseIterable, Identifiable {
    case split
    case compare
    case source
    case grade

    var id: String { rawValue }

    var label: String {
        switch self {
        case .split: return "分屏"
        case .compare: return "对照"
        case .source: return "源"
        case .grade: return "预览"
        }
    }

    var caption: String {
        switch self {
        case .split: return "左：源（相机 Log）  右：预览"
        case .compare: return "左：调色前  右：这一套。不含曝光和白平衡的是左幅。仅预览。"
        case .source: return "源（相机 Log）"
        case .grade: return "预览放大。角标仍是仅预览。"
        }
    }
}

private struct MonitorHeader: View {
    @ObservedObject var session: SessionModel
    @Binding var layout: MonitorLayout
    @Binding var zoom: MonitorZoom

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Text("监视器")
                    .font(.headline)
                Text(session.previewShowsGradeBefore
                     ? "预览不含曝光和白平衡。写出仍用检查器这一套。"
                     : layout.caption)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Spacer(minLength: 8)
                Picker("画面", selection: $layout) {
                    ForEach(MonitorLayout.allCases) { item in
                        Text(item.label).tag(item)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 268)
                .labelsHidden()
                .help("分屏是源和预览。对照是调色前和这一套，左右同时看，不改检查器，也不改写出。未锁定时不能切到对照。按 V 只在分屏和预览之间换，源和对照不在这一下里。点灰卡时仍在预览上取样。仅预览。")
                if session.canToggleSplitAndGrade {
                    Text("V 切换")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .help("按 V 在分屏和预览之间换。菜单「调色」里的「分屏与预览」是同一套，菜单不标快捷键。正在看源或对照时不出现这一句，V 也不改画面。查找框、手填档、手填色温、手填绿品、跳到仍吃 V。写出进行中，或设置、写出说明、导入、正在打开选文件夹、点灰卡时不起作用。不改这一套曝光和白平衡，不改成对 IDT，不改预览帧，也不参与写出。")
                }
                Button(session.previewShowsGradeBefore ? "回到调色" : "看调色前") {
                    session.togglePreviewGradeBefore()
                }
                .controlSize(.regular)
                .disabled(!session.canTogglePreviewGradeBefore)
                .help("只改监视器画面：不含曝光和白平衡。检查器数字不动，写出也不改。再点一次回到调色。仅预览。")
                if session.previewShowsGradeBefore {
                    Text("调色前")
                        .font(.caption.weight(.bold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.orange.opacity(0.28))
                        .clipShape(Capsule())
                }
                Text("仅预览")
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.primary.opacity(0.08))
                    .clipShape(Capsule())
            }
                if session.selectedClip != nil {
                HStack(spacing: 8) {
                    Picker("这次预览", selection: Binding(
                        get: { session.monitorPreviewODT },
                        set: { session.setODT($0) }
                    )) {
                        Text("Rec.709").tag(ODTMode.rec709)
                        Text("HLG").tag(ODTMode.hlg)
                        Text("PQ").tag(ODTMode.pq)
                    }
                    .pickerStyle(.menu)
                    .fixedSize()
                    .disabled(session.isExporting)
                    .help("只改这次监视器。默认预览在设置。角标仍是仅预览。不改写出。")
                    Picker("放大", selection: $zoom) {
                        ForEach(MonitorZoom.allCases) { item in
                            Text(item.label).tag(item)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 168)
                    .labelsHidden()
                    .disabled(session.pickingNeutral)
                    .help("只改监视器画面大小。适应是整幅塞进窗口。100% 是预览画面的一个像素对一个屏幕像素，不是片源逐像素，预览长边仍会缩小。200% 再大一倍，停在中央，可拖动；分屏时源和预览一起动。换放大倍数或换一条回到中央。不改这一套调色，不参与写出。点灰卡时回到适应，取样仍按整幅，点完仍停在刚才拖到的位置。")
                    if session.pickingNeutral {
                        Text("点灰卡时适应")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    } else if zoom != .fit {
                        Text("可拖动")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }
                HStack(spacing: 8) {
                    Text(gradeClipTitle)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .layoutPriority(0)
                    Text(gradeNumberLine)
                        .font(.callout.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .fixedSize(horizontal: true, vertical: false)
                        .layoutPriority(1)
                }
                .help(session.previewShowsGradeBefore
                      ? "画面不含曝光和白平衡。数字仍是检查器里会写出的那一套。文件名可以截断，曝光和白平衡留着。仅预览。"
                      : "和右侧检查器是同一套。文件名可以截断，曝光和白平衡留着。换一条素材，这一套不改。仅预览。")
                .accessibilityLabel(gradeReadout)
                if let fact = session.selectedClip?.mediaFactLine {
                    Text(fact)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .help("片源读到的画面尺寸、帧率和时长。缺的不写，不猜帧率。静帧写静帧。预览长边仍会缩小，这一行不跟着变，也不参与写出。")
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.03))
    }

    /// Filename only. It may truncate. The numbers live on `gradeNumberLine`.
    private var gradeClipTitle: String {
        session.selectedClip?.filename ?? ""
    }

    /// Exposure and white balance, without the filename, so a long name cannot eat them.
    /// 看调色前 and 对照 stay in front of the numbers. Same set as the inspector. Preview only.
    private var gradeNumberLine: String {
        let numbers = gradeFacts.numbers
        if session.previewShowsGradeBefore {
            return "看调色前 · \(numbers)"
        }
        if session.monitorLayout == .compare {
            return "对照 · \(numbers)"
        }
        return numbers
    }

    /// 监视器上的调色读数。数字来自当前检查器，不另存一套，也不参与写出。
    private var gradeReadout: String {
        let facts = gradeFacts
        let body = facts.name.isEmpty ? facts.numbers : "\(facts.name) · \(facts.numbers)"
        if session.previewShowsGradeBefore {
            return "看调色前 · \(body)"
        }
        if session.monitorLayout == .compare {
            return "对照 · \(body)"
        }
        return body
    }

    private var gradeFacts: (name: String, numbers: String) {
        let exposure: String
        if session.graph.exposureEnabled {
            exposure = String(format: "曝光 %+.2f 档", session.graph.exposureStops)
        } else {
            exposure = "曝光关"
        }
        let wb: String
        if !session.graph.wbEnabled {
            wb = "白平衡关"
        } else if let cct = session.graph.wbCCT {
            let tint = String(format: "%+.1f", session.graph.wbTint)
            wb = "\(session.graph.wbSource.title) \(Int(cct.rounded())) K · 绿品 \(tint)"
        } else {
            wb = session.graph.wbSource.title
        }
        let pending = session.selectedClip?.isPending == true ? "待选 · " : ""
        return (gradeClipTitle, "\(pending)\(exposure) · \(wb)")
    }
}

/// 检查器跟当前选中。标题固定；成对 IDT、曝光、白平衡在下面整栏滚动。
/// 窗口变矮时仍能滚到曝光和白平衡，不会被成对 IDT 顶出画面。
/// 已锁定时，标题下固定这一对的名字，滚到曝光时还在。待选不在标题里写一对。
/// 换到待选时回到成对 IDT。换到已锁定时不跟着滚。
private struct InspectorColumn: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text("检查器")
                    .font(.title3.weight(.semibold))
                if let clip = session.selectedClip {
                    HStack(alignment: .top, spacing: 8) {
                        ClipSourcePoster(session: session, posters: session.posters, clip: clip)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(clip.filename)
                                .font(.body.weight(.semibold))
                                .lineLimit(1)
                                .truncationMode(.middle)
                            if let fact = clip.mediaFactLine {
                                Text(fact)
                                    .font(.caption.monospacedDigit())
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                                    .help("和左侧列表、监视器、写出说明是同一行。缺的不写，不猜帧率。不参与写出。")
                            }
                            Text(clip.hasLockedPair
                                 ? "跟这条选中。曝光和白平衡是全片这一套，换一条也不改。"
                                 : "跟这条选中。先选成对 IDT。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                                .help("换到还没锁定的一条时，下面这一栏回到成对 IDT。换到已锁定时不跟着滚，曝光和白平衡留在刚才的位置。已锁定时，标题下这一行是这一对的名字，滚到曝光也还在。待选不在标题里写一对。不改这一套调色，不改预览帧，也不参与写出。")
                            if let pair = SessionModel.inspectorPinnedPairLine(
                                hasLockedPair: clip.hasLockedPair,
                                pairLabel: clip.idt?.pairLabel ?? ""
                            ) {
                                Text(pair)
                                    .font(.callout.weight(.semibold))
                                    .lineLimit(2)
                                    .help("这条已锁定的成对 IDT，和列表、写出说明是同一句。标题固定，滚到曝光和白平衡时这一行还在。待选不在标题里写一对。换一条跟着换。不改这一套调色，不改预览帧，也不参与写出。")
                            }
                        }
                    }
                    HStack(spacing: 8) {
                        Button("撤销这一套") {
                            session.undoSharedGrade()
                        }
                        .disabled(!session.canUndoSharedGrade)
                        Button("重做这一套") {
                            session.redoSharedGrade()
                        }
                        .disabled(!session.canRedoSharedGrade)
                    }
                    .controlSize(.regular)
                    .padding(.top, 4)
                    .help("回到上一次曝光和白平衡。一次拖动滑条算一步，松开后再拖是另一步。不改成对 IDT，不改预览帧，不改这次预览。⌘Z、⇧⌘Z 和菜单「调色」是同一套。查找框里的 ⌘Z 仍改文字。写出进行中不能撤销。")
                } else if session.clips.isEmpty {
                    Text("先拖入或点「添加…」，或按回车。选中一条后，这里跟这条。")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    Text("先在左侧点一条素材。")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            Divider()
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        PairedIDTBar(session: session)
                            .id(SessionModel.inspectorPairedIDTAnchor)
                        Divider()
                        InspectorView(session: session)
                        Text("写出时已锁定素材共用当前这一套曝光和白平衡，每条仍用自己的成对 IDT。点另一条、方向键或再拖入，都不会改掉这一套。")
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.horizontal, 12)
                            .padding(.bottom, 12)
                    }
                }
                .onChange(of: session.selectedID) { _, _ in
                    guard let anchor = SessionModel.inspectorScrollAnchor(
                        selectedIsPending: session.selectedClip?.isPending == true
                    ) else { return }
                    proxy.scrollTo(anchor, anchor: .top)
                }
                .onChange(of: session.inspectorScrollToken) { _, _ in
                    guard let anchor = session.inspectorScrollTarget else { return }
                    proxy.scrollTo(anchor, anchor: .top)
                }
            }
        }
        .background(Color.primary.opacity(0.02))
    }
}

/// Window-level Up/Down for the sidebar list. Left/Right steps the preview
/// frame (same as 上一帧 / 下一帧). Shift+Left/Right jumps about one second
/// when this clip's rate was read. Home / End jump to the first or last
/// preview frame. Space plays or pauses that preview.
/// J reverses, L is the same as 播放, K only pauses. Text fields keep those letters.
/// Escape while writing is the existing 取消
/// (same cancelLockedDeliverables). Idle Escape does nothing.
/// Delete / Backspace drops the selected clip from the session only
/// (source file and already-written `_proxy` stay). Mid-write ignores Delete.
/// No help overlay. No extra button. No confirm sheet.
/// Same window only; text / numeric / search / slider first-responders keep
/// arrows and Delete. Sheets / alerts / settings keep Escape and Delete.
/// ⌘Z / ⇧⌘Z step the shared grade, unless a text field has the keys.
/// Bare 1…4 lock a short paired-IDT list. Text fields keep the digits.
/// A long catalog has no digit, so 1 does not lock the first catalog row.
/// Return follows the marked step, except 写出. Text fields keep Return.
/// Bare V toggles 分屏 and 预览. Text fields keep V. 源 and 对照 do not.
private struct ClipListArrowMonitor: NSViewRepresentable {
    var handler: (Int) -> Bool
    var onEscape: () -> Bool
    var onDelete: () -> Bool
    var onStepFrame: (Int) -> Bool
    var onJumpToStart: () -> Bool
    var onJumpToEnd: () -> Bool
    var onStepSecond: (Int) -> Bool
    var onTogglePlayback: () -> Bool
    var onPlayBackward: () -> Bool
    var onPausePlayback: () -> Bool
    var onUndoGrade: () -> Bool
    var onRedoGrade: () -> Bool
    var onLockShortPair: (Int) -> Bool
    var onFollowLoop: () -> Bool
    var onToggleSplitAndGrade: () -> Bool
    var onGradeStrokeEnd: () -> Void

    func makeNSView(context: Context) -> MonitorView {
        let view = MonitorView()
        view.handler = handler
        view.onEscape = onEscape
        view.onDelete = onDelete
        view.onStepFrame = onStepFrame
        view.onJumpToStart = onJumpToStart
        view.onJumpToEnd = onJumpToEnd
        view.onStepSecond = onStepSecond
        view.onTogglePlayback = onTogglePlayback
        view.onPlayBackward = onPlayBackward
        view.onPausePlayback = onPausePlayback
        view.onUndoGrade = onUndoGrade
        view.onRedoGrade = onRedoGrade
        view.onLockShortPair = onLockShortPair
        view.onFollowLoop = onFollowLoop
        view.onToggleSplitAndGrade = onToggleSplitAndGrade
        view.onGradeStrokeEnd = onGradeStrokeEnd
        return view
    }

    func updateNSView(_ nsView: MonitorView, context: Context) {
        nsView.handler = handler
        nsView.onEscape = onEscape
        nsView.onDelete = onDelete
        nsView.onStepFrame = onStepFrame
        nsView.onJumpToStart = onJumpToStart
        nsView.onJumpToEnd = onJumpToEnd
        nsView.onStepSecond = onStepSecond
        nsView.onTogglePlayback = onTogglePlayback
        nsView.onPlayBackward = onPlayBackward
        nsView.onPausePlayback = onPausePlayback
        nsView.onUndoGrade = onUndoGrade
        nsView.onRedoGrade = onRedoGrade
        nsView.onLockShortPair = onLockShortPair
        nsView.onFollowLoop = onFollowLoop
        nsView.onToggleSplitAndGrade = onToggleSplitAndGrade
        nsView.onGradeStrokeEnd = onGradeStrokeEnd
    }

    static func dismantleNSView(_ nsView: MonitorView, coordinator: ()) {
        nsView.removeMonitor()
    }

    final class MonitorView: NSView {
        var handler: ((Int) -> Bool)?
        var onEscape: (() -> Bool)?
        var onDelete: (() -> Bool)?
        var onStepFrame: ((Int) -> Bool)?
        var onJumpToStart: (() -> Bool)?
        var onJumpToEnd: (() -> Bool)?
        var onStepSecond: ((Int) -> Bool)?
        var onTogglePlayback: (() -> Bool)?
        var onPlayBackward: (() -> Bool)?
        var onPausePlayback: (() -> Bool)?
        var onUndoGrade: (() -> Bool)?
        var onRedoGrade: (() -> Bool)?
        var onLockShortPair: ((Int) -> Bool)?
        var onFollowLoop: (() -> Bool)?
        var onToggleSplitAndGrade: (() -> Bool)?
        var onGradeStrokeEnd: (() -> Void)?
        private var monitor: Any?

        /// Shift alone, ignoring flags arrow keys already carry.
        private static func transportShiftOnly(_ event: NSEvent) -> Bool {
            let flags = event.modifierFlags
                .intersection(.deviceIndependentFlagsMask)
                .subtracting([.numericPad, .function, .capsLock])
            return flags == .shift
        }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            if window == nil {
                removeMonitor()
            } else {
                installMonitor()
            }
        }

        func installMonitor() {
            guard monitor == nil else { return }
            monitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .leftMouseUp]) { [weak self] event in
                guard let self else { return event }
                if event.type == .leftMouseUp {
                    self.onGradeStrokeEnd?()
                    return event
                }
                guard event.window === self.window else { return event }
                if self.consumeGradeUndoKey(event) { return nil }
                if self.consumeShuttleKey(event) { return nil }
                if self.consumeSplitGradeKey(event) { return nil }
                if self.consumeShortPairKey(event) { return nil }
                switch event.keyCode {
                case 126:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if self.handler?(-1) == true { return nil }
                    return event
                case 125:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if self.handler?(1) == true { return nil }
                    return event
                case 123:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if Self.transportShiftOnly(event) {
                        if self.onStepSecond?(-1) == true { return nil }
                        return event
                    }
                    if self.onStepFrame?(-1) == true { return nil }
                    return event
                case 124:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if Self.transportShiftOnly(event) {
                        if self.onStepSecond?(1) == true { return nil }
                        return event
                    }
                    if self.onStepFrame?(1) == true { return nil }
                    return event
                case 115:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onJumpToStart?() == true { return nil }
                    return event
                case 119:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onJumpToEnd?() == true { return nil }
                    return event
                case 49:
                    if SessionModel.isPlaybackKeyConsumedByControl() { return event }
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onTogglePlayback?() == true { return nil }
                    return event
                case 53:
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onEscape?() == true {
                        return nil
                    }
                    return event
                case 51:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onDelete?() == true {
                        return nil
                    }
                    return event
                case 117:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onDelete?() == true {
                        return nil
                    }
                    return event
                case 36, 76:
                    let returnFlags = event.modifierFlags
                        .intersection(.deviceIndependentFlagsMask)
                        .subtracting([.numericPad, .function, .capsLock])
                    if !returnFlags.isEmpty { return event }
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: self.window) {
                        return event
                    }
                    if self.onFollowLoop?() == true { return nil }
                    return event
                default:
                    return event
                }
            }
        }

        /// Bare 1…4 on a short paired list. No modifiers. Text, sliders, and search keep the digits.
        /// The session refuses a long catalog, so this does not lock a guessed pair.
        private func consumeShortPairKey(_ event: NSEvent) -> Bool {
            guard let key = event.charactersIgnoringModifiers, key.count == 1,
                  let digit = Int(key), (1...4).contains(digit) else { return false }
            let flags = event.modifierFlags
                .intersection(.deviceIndependentFlagsMask)
                .subtracting([.numericPad, .function, .capsLock])
            guard flags.isEmpty else { return false }
            if SessionModel.isArrowConsumedByTextInput() { return false }
            if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: window) { return false }
            return onLockShortPair?(digit) == true
        }

        /// Bare V toggles 分屏 and 预览. No modifiers. Text, sliders, and buttons keep the letter.
        /// 源 and 对照, a write, and a sheet make the session refuse, so this does not eat the key.
        private func consumeSplitGradeKey(_ event: NSEvent) -> Bool {
            guard event.charactersIgnoringModifiers?.lowercased() == "v" else { return false }
            let flags = event.modifierFlags
                .intersection(.deviceIndependentFlagsMask)
                .subtracting([.numericPad, .function, .capsLock])
            guard flags.isEmpty else { return false }
            if SessionModel.isPlaybackKeyConsumedByControl() { return false }
            if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: window) { return false }
            return onToggleSplitAndGrade?() == true
        }

        /// J reverse, L same as 播放, K pause. No modifiers. Text, sliders, and buttons keep the letters.
        private func consumeShuttleKey(_ event: NSEvent) -> Bool {
            guard let key = event.charactersIgnoringModifiers?.lowercased(), key.count == 1 else { return false }
            guard key == "j" || key == "k" || key == "l" else { return false }
            let flags = event.modifierFlags
                .intersection(.deviceIndependentFlagsMask)
                .subtracting([.numericPad, .function, .capsLock])
            guard flags.isEmpty else { return false }
            if SessionModel.isPlaybackKeyConsumedByControl() { return false }
            if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: window) { return false }
            switch key {
            case "j":
                return onPlayBackward?() == true
            case "k":
                return onPausePlayback?() == true
            case "l":
                return onTogglePlayback?() == true
            default:
                return false
            }
        }

        /// ⌘Z / ⇧⌘Z. Text and the pair search keep the keys. An empty stack does not eat the event.
        private func consumeGradeUndoKey(_ event: NSEvent) -> Bool {
            guard event.charactersIgnoringModifiers?.lowercased() == "z" else { return false }
            let flags = event.modifierFlags.intersection([.command, .shift, .option, .control])
            let undo = flags == .command
            let redo = flags == [.command, .shift]
            guard undo || redo else { return false }
            if SessionModel.isUndoConsumedByTextInput() { return false }
            if SessionModel.isEscapeReservedByPresentedUI(event: event, monitorWindow: window) { return false }
            if undo { return onUndoGrade?() == true }
            return onRedoGrade?() == true
        }

        func removeMonitor() {
            if let monitor {
                NSEvent.removeMonitor(monitor)
                self.monitor = nil
            }
        }

        deinit { removeMonitor() }
    }
}

/// Write step under the monitor. One button: open the deliver sheet, or 取消.
/// The sheet confirms, then this view calls processLockedClips (folder panel).
/// 不是一步还原. Default deliverable: ProRes 422 HQ. EXR remains advanced.
/// 整段代理，代理精度.
struct ProcessLockedBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("写出")
                    .font(.title3.weight(.semibold))
                Text(session.lockStatusText)
                    .font(.body.weight(.semibold))
                    .lineLimit(1)
                if let reason = session.selectedClip?.processSkipReason, session.showsProcessLockedButton {
                    Text(reason)
                        .font(.callout)
                        .foregroundStyle(.orange)
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
                if session.showsProcessLockedButton {
                    Button(session.isWritingDeliverables ? "取消" : "处理已锁定片段") {
                        if session.isWritingDeliverables {
                            session.cancelLockedDeliverables()
                        } else {
                            session.presentDeliverSheet()
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(session.openingExportFolder)
                    .help(UICopy.PROCESS_BUTTON_HELP_UI)
                }
            }
            if session.openingExportFolder {
                Text("写出说明已收起。选文件夹会贴在这个窗口上。取消则不写出。\(session.exportFolderOpenNote)")
                    .font(.body.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
                    .help("和写出说明同一句。只写文件夹的名字，不写整条路径。那个文件夹还在才用。取消则不写出。")
            }
            if let caution = session.deliverPreviewGlance.barCaution,
               session.showsProcessLockedButton,
               !session.isWritingDeliverables,
               !session.openingExportFolder {
                Text(caution)
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.orange)
                    .lineLimit(2)
                    .help("监视器若在看调色前、对照的左幅、HDR，或这次是高级 EXR，写出仍用检查器里这一套。不改检查器，也不改写出。")
            }
            Text("\(session.settings.exportFormat.labelZH) · \(deliverableNote)")
                .font(.callout)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            if !session.showsProcessLockedButton, !session.clips.isEmpty, !session.isWritingDeliverables {
                Text("下一步：在右侧检查器选成对 IDT。选完才能写出。")
                    .font(.body.weight(.semibold))
                    .lineLimit(2)
                Text(session.selectedClip?.processSkipReason ?? "先选择 Log 与色域")
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.orange)
                    .lineLimit(1)
            }
            if session.showsBatchSummary {
                Text(session.lastExportNote)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.accentColor.opacity(session.showsProcessLockedButton ? 0.08 : 0.04))
        .onChange(of: session.deliverSheetConfirmed) { _, confirmed in
            guard confirmed else { return }
            session.deliverSheetConfirmed = false
            session.openingExportFolder = true
            openFolderPanelAfterSheet()
        }
    }

    /// NSOpenPanel on top of a dismissing sheet often never appears.
    /// Wait until the write sheet is gone, then attach the folder panel to this window.
    /// Settings or the importer during the wait aborts. Cancel writes nothing.
    private func openFolderPanelAfterSheet() {
        let session = session
        func kick(_ attempt: Int) {
            DispatchQueue.main.async {
                if session.showSettings || session.showImporter || session.isWritingDeliverables {
                    session.openingExportFolder = false
                    return
                }
                let sheetStillUp = session.showDeliverSheet
                    || NSApp.windows.contains { $0.attachedSheet != nil }
                if sheetStillUp, attempt < 40 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                        kick(attempt + 1)
                    }
                    return
                }
                session.processLockedClips()
            }
        }
        kick(0)
    }

    private var deliverableNote: String {
        if session.settings.exportFormat == .prores422HQ {
            return UICopy.PROCESS_DELIVERABLE_NOTE_UI
        }
        return "高级格式走 ACES2065-1 EXR 序列。整段代理，代理精度。"
    }
}

/// Node strip, format, Resolve export, histogram, and luma waveform.
/// Hidden by default. Paired IDT stays in the inspector — never here.
struct AdvancedPanel: View {
    @ObservedObject var session: SessionModel
    @Binding var isExpanded: Bool

    var body: some View {
        DisclosureGroup("高级", isExpanded: $isExpanded) {
            // 展开后在自己的高度里滚，监视器仍留一块预览。
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    Text("节点、写出格式、直方图、亮度波形。默认收起，不挡预览。")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                    Picker("写出格式", selection: Binding(
                        get: { session.settings.exportFormat },
                        set: { session.settings.exportFormat = $0 }
                    )) {
                        ForEach(ExportFormat.allCases) { fmt in
                            Text(fmt.labelZH).tag(fmt)
                        }
                    }
                    .pickerStyle(.radioGroup)
                    .help(session.settings.exportFormat.pickerHelpZH)
                    NodeStripView(session: session)
                    HStack {
                        Button("导出 ACEScct / EXR") {
                            session.exportResolve()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canProcess)
                        .help(UICopy.ADVANCED_EXPORT_HELP)
                        if let reason = session.processBlockedReason {
                            Text(reason)
                                .font(.caption)
                                .foregroundStyle(.orange)
                        }
                        Spacer()
                    }
                    .padding(.horizontal, 10)
                    PreviewHistogramView(image: isExpanded ? session.preview.odtImage : nil)
                        .padding(.horizontal, 10)
                        .padding(.bottom, 8)
                }
            }
            .frame(maxHeight: 220)
        }
        .help(UICopy.ADVANCED_DISCLOSURE_HELP)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.primary.opacity(0.02))
    }
}

struct SplitPreview: View {
    @ObservedObject var session: SessionModel
    var layout: MonitorLayout
    var zoom: MonitorZoom
    var panBus: MonitorPanBus = MonitorPanBus()

    /// Grey-card sampling hits the grade pane. Keep that pane up while sampling.
    private var shownLayout: MonitorLayout {
        if session.pickingNeutral, !session.isExporting, layout == .source {
            return .grade
        }
        return layout
    }

    /// Grey-card hits use the whole fitted frame. Magnify comes back after.
    private var shownZoom: MonitorZoom {
        if session.pickingNeutral, !session.isExporting {
            return .fit
        }
        return zoom
    }

    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                switch shownLayout {
                case .split:
                    HSplitView {
                        sourcePane
                        previewPane
                    }
                case .compare:
                    HSplitView {
                        compareBeforePane
                        previewPane
                    }
                case .source:
                    sourcePane
                case .grade:
                    previewPane
                }
                PreviewScrubBar(session: session)
                if session.isExporting {
                    WriteProgressLine(text: session.lastExportNote)
                } else {
                    if let line = session.monitorWillWriteLine {
                        if session.canStartWriteFromLoop {
                            Button {
                                session.openWriteSheetFromMonitorLine()
                            } label: {
                                WriteProgressLine(
                                    text: line,
                                    help: "点这一行打开写出说明，和顶栏「写出」、⌘E 一样。确认后才选文件夹，不开始写文件。只写文件名或文件夹名，不写整条路径。不改这一套曝光和白平衡，不改成对 IDT，也不改预览帧。播放会停。",
                                    truncation: .middle
                                )
                            }
                            .buttonStyle(.plain)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .help("点这一行打开写出说明。确认后才选文件夹。设置、添加、写出说明或正在打开选文件夹时，这一行只留名字，点不了。")
                        } else {
                            WriteProgressLine(
                                text: line,
                                help: "和写出说明里「将得到」是同一个名字。这一行现在只留名字：设置、添加、写出说明或选文件夹开着时点不了。不改这一套曝光和白平衡，也不改预览帧。",
                                truncation: .middle
                            )
                        }
                    }
                    if let caption = session.selectedClip?.previewCaption {
                        WriteProgressLine(text: caption)
                    }
                }
            }
            if session.clips.isEmpty {
                VStack(spacing: 10) {
                    Text("把混源文件夹拖进来")
                        .font(.title2.weight(.semibold))
                    Text("或点「添加…」，或按回车。每条再选成对 Log 与色域。")
                        .font(.body)
                        .multilineTextAlignment(.center)
                    Text("已实现（未验证）")
                        .font(.caption.weight(.semibold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.orange.opacity(0.28))
                        .clipShape(Capsule())
                }
                .foregroundStyle(.white)
                .padding(28)
                .background(.black.opacity(0.62))
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(32)
                .allowsHitTesting(false)
            } else if let clip = session.selectedClip, clip.isPending, !session.isExporting {
                VStack(spacing: 4) {
                    Text(clip.processSkipReason ?? "先选择 Log 与色域")
                        .font(.title3.weight(.semibold))
                    Text("按回车滚到右侧成对 IDT，点一行锁定。不替你选。预览角标仍是仅预览。")
                        .font(.callout)
                }
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(.black.opacity(0.72))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.bottom, 20)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                .allowsHitTesting(false)
            }
        }
    }

    /// Same IDT and this preview, without exposure or white balance. Not the camera log.
    @ViewBuilder
    private var compareBeforePane: some View {
        gradedPane(
            title: "调色前",
            caption: "同一成对 IDT、同一次预览，不含曝光和白平衡。检查器数字和写出都不改。仅预览。",
            image: session.preview.compareBeforeImage,
            picking: false
        )
        .overlay {
            paneGap(image: session.preview.compareBeforeImage, waitingOnPair: false)
        }
    }

    private var sourcePane: some View {
        SourcePreviewView(
            title: "源（相机 Log）",
            caption: "未套 Rec.709。相机编码值。",
            image: session.preview.sourceImage,
            zoom: shownZoom,
            panBus: panBus
        )
        .overlay {
            paneGap(image: session.preview.sourceImage, waitingOnPair: false)
        }
    }

    private var gradePaneTitle: String {
        if session.previewShowsGradeBefore {
            return "调色前 · \(session.odtPreviewTitle)"
        }
        return session.odtPreviewTitle
    }

    private var gradePaneCaption: String {
        if session.previewShowsGradeBefore {
            return "不含曝光和白平衡。检查器里的数字和写出都不改。仅预览。"
        }
        return session.odtPreviewCaption
    }

    @ViewBuilder
    private var previewPane: some View {
        gradedPane(
            title: gradePaneTitle,
            caption: gradePaneCaption,
            image: session.preview.odtImage,
            picking: session.pickingNeutral && !session.isExporting,
            onLayerFail: {
                session.failClosedHDRPreviewLayer()
            }
        )
        .overlay {
            paneGap(
                image: session.preview.odtImage,
                waitingOnPair: session.selectedClip?.isPending == true
            )
        }
    }

    /// Black pane only. A frame that is already up stays uncovered.
    /// Write and a clip still waiting on a paired IDT keep their own lines.
    @ViewBuilder
    private func paneGap(image: CGImage?, waitingOnPair: Bool) -> some View {
        let note: String? = session.isExporting ? nil : SessionModel.monitorPaneGapNote(
            imageMissing: image == nil,
            isWorking: session.preview.isWorking,
            status: session.preview.status,
            waitingOnPair: waitingOnPair
        )
        if let note {
            Text(note)
                .font(.title3.weight(.semibold))
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(.black.opacity(0.72))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .allowsHitTesting(false)
                .help("这一格还没画面。正在解码，或这一帧解不出来。不改这一套调色，不参与写出。")
        }
    }

    /// Rec.709 or HDR host. Grey-card hits only the pane that asks for them.
    @ViewBuilder
    private func gradedPane(
        title: String,
        caption: String,
        image: CGImage?,
        picking: Bool,
        onLayerFail: (() -> Void)? = nil
    ) -> some View {
        if session.graph.odt.isHDR {
            HDRPreviewView(
                title: title,
                caption: caption,
                image: image,
                zoom: shownZoom,
                panBus: panBus,
                odt: session.graph.odt,
                pickingNeutral: picking,
                onPick: { nx, ny in
                    session.handlePreviewPick(nx: nx, ny: ny)
                },
                onLayerFail: onLayerFail
            )
        } else {
            Rec709PreviewView(
                title: title,
                caption: caption,
                image: image,
                zoom: shownZoom,
                panBus: panBus,
                pickingNeutral: picking,
                onPick: { nx, ny in
                    session.handlePreviewPick(nx: nx, ny: ny)
                }
            )
        }
    }
}

/// Movie: slider first…last from duration × metadata fps. Cache hit: 只重跑预览输出.
/// The slider is its own row so transport buttons cannot squeeze it. A narrow
/// window scrolls that button row sideways. Missing fps/duration: Chinese fail,
/// no fake range. Stills: no slider. Not a timeline.
struct PreviewScrubBar: View {
    @ObservedObject var session: SessionModel
    @State private var jumpText = ""
    @State private var jumpNote: String?

    var body: some View {
        if session.isExporting {
            EmptyView()
        } else if let fail = session.previewScrubFail {
            Text(fail)
                .font(.callout)
                .foregroundStyle(.orange)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
        } else if let last = session.previewScrubLastFrame {
            VStack(alignment: .leading, spacing: 4) {
                Slider(
                    value: Binding(
                        get: { Double(session.previewFrameIndex) },
                        set: { session.setPreviewFrame(Int($0.rounded())) }
                    ),
                    in: 0...Double(last),
                    step: 1
                )
                .controlSize(.regular)
                .help("拖这一条看这一帧。按钮在下面，窗口窄时那一行可横着滚，不把滑条挤没。仅预览。不改这一套曝光和白平衡，也不参与写出。")
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        Button(session.isPreviewPlaying ? "暂停" : "播放") {
                            session.togglePreviewPlayback()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canTogglePreviewPlayback)
                        .help("按这条素材自己的帧率走预览。这一帧还没画完就等它。循环关掉时到最后一帧就停，不绕回。循环打开时回到第 1 帧接着播。空格和 L 是同一套。K 只暂停。不改曝光和白平衡，不参与写出。读不到帧率就不能播。")
                        Button(session.isPreviewPlaying && session.previewPlaysBackward ? "倒放中" : "倒放") {
                            session.playPreviewBackward()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canTogglePreviewReverse)
                        .help("从当前帧往回走，按这条自己的帧率。到第 1 帧就停，不绕回。循环打开时回到最后一帧接着倒放。正在向前播时改成倒放。再点一次暂停。J 是同一套。不改曝光和白平衡，不参与写出。读不到帧率就不能倒放。")
                        if session.showsPreviewLoop {
                            Button(session.previewLoops ? "循环中" : "循环") {
                                session.togglePreviewLoop()
                            }
                            .controlSize(.regular)
                            .disabled(!session.canTogglePreviewLoop)
                            .help("打开后，播放到最后一帧回到第 1 帧接着播，倒放则回到最后一帧接着倒放。关掉则到头就停，不绕回。⌥⌘L 是同一套。只有一帧、静帧或读不到帧率时没有这一下。打开或关掉不改当前帧，不改这一套曝光和白平衡，也不参与写出。")
                        }
                        Button("回到开头") {
                            session.jumpPreviewToStart()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canJumpPreviewToStart)
                        .help("回到第 1 帧。Home 是同一套。只改预览，不改这一套曝光和白平衡，也不参与写出。")
                        if session.showsPreviewSecondStep {
                            Button("退 1 秒") {
                                session.stepPreviewBySecond(-1)
                            }
                            .controlSize(.regular)
                            .disabled(!session.canStepPreviewSecondBackward)
                            .help("按这条帧率跳大约 1 秒，到头就停。⇧← 是同一套。读不到帧率就没有这一下。只改预览，不改这一套曝光和白平衡，也不参与写出。")
                        }
                        Button("上一帧") {
                            session.stepPreviewFrame(-1)
                        }
                        .controlSize(.regular)
                        .disabled(!session.canStepPreviewBackward)
                        .help("每次一帧，到头就停。左方向键是同一套。只改预览，不改这一套曝光和白平衡，也不参与写出。")
                        Button("下一帧") {
                            session.stepPreviewFrame(1)
                        }
                        .controlSize(.regular)
                        .disabled(!session.canStepPreviewForward)
                        .help("每次一帧，到头就停。右方向键是同一套。只改预览，不改这一套曝光和白平衡，也不参与写出。")
                        if session.showsPreviewSecondStep {
                            Button("进 1 秒") {
                                session.stepPreviewBySecond(1)
                            }
                            .controlSize(.regular)
                            .disabled(!session.canStepPreviewSecondForward)
                            .help("按这条帧率跳大约 1 秒，到头就停。⇧→ 是同一套。读不到帧率就没有这一下。只改预览，不改这一套曝光和白平衡，也不参与写出。")
                        }
                        Button("到结尾") {
                            session.jumpPreviewToEnd()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canJumpPreviewToEnd)
                        .help("到最后一帧。End 是同一套。只改预览，不改这一套曝光和白平衡，也不参与写出。")
                    }
                }
                .scrollBounceBehavior(.basedOnSize, axes: .horizontal)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, maxHeight: 56, alignment: .leading)
                .help("播放、倒放、回到开头、上一帧、下一帧在滑条下面。窗口窄时可横着滚，不把滑条挤没，也不把预览顶矮。不改这一套曝光和白平衡，也不参与写出。这不是时间线。")
                if session.previewClockText != nil {
                    HStack(spacing: 8) {
                        TextField("0:01.500", text: $jumpText)
                            .textFieldStyle(.roundedBorder)
                            .font(.body.monospacedDigit())
                            .frame(width: 148)
                            .onSubmit(commitPreviewJump)
                            .onChange(of: jumpText) { _, _ in
                                jumpNote = nil
                            }
                            .disabled(!session.canJumpPreviewToClock)
                        Button("跳到") {
                            commitPreviewJump()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canJumpPreviewToClock)
                        if let jumpNote {
                            Text(jumpNote)
                                .font(.callout)
                                .foregroundStyle(.orange)
                                .lineLimit(1)
                        }
                        Spacer(minLength: 8)
                    }
                    .help("按这条帧率落到最近的一帧。可写 0:01.500、1:02:03.004、秒数 1.5、1.5秒，或第 12 帧。超出就停在开头或结尾。回车和「跳到」是同一套。读不到帧率就没有这一栏。只改预览，不改这一套曝光和白平衡，也不参与写出。不是时间码。")
                }
                Text(previewFrameReadout(last: last))
                    .font(.body.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .help("帧数是这条预览的第几帧。读到帧率时，后面是当前这一帧 / 最后一帧的预览时间，都是这一帧除以这条帧率。右边不是片源时长，也不是时间码。读不到帧率就不写时间。不改这一套调色，不参与写出。")
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .onChange(of: session.selectedID) { _, _ in
                jumpText = ""
                jumpNote = nil
            }
        }
    }

    /// Empty and unrecognized stay on this frame. A real time moves the preview only.
    private func commitPreviewJump() {
        let text = jumpText.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.isEmpty {
            jumpNote = "先写出时间，如 0:01.500 或第 12 帧"
            return
        }
        if session.jumpPreview(toClock: text) {
            jumpNote = nil
        } else if session.canJumpPreviewToClock {
            jumpNote = "认不出这个时间"
        }
    }

    /// Frame count, and a clock when this clip's rate was read. Playback stays a suffix.
    private func previewFrameReadout(last: Int) -> String {
        var line = "第 \(session.previewFrameIndex + 1) / \(last + 1) 帧"
        if let clock = session.previewClockText {
            if let end = session.previewClockEndText {
                line += " · \(clock) / \(end)"
            } else {
                line += " · \(clock)"
            }
        }
        if session.previewLoops {
            if session.isPreviewPlaying {
                line += session.previewPlaysBackward ? " · 循环倒放" : " · 循环播放"
            } else {
                line += " · 循环"
            }
        } else if session.isPreviewPlaying {
            line += session.previewPlaysBackward ? " · 倒放中" : " · 播放中"
        }
        return line
    }
}

/// One Chinese line on the preview: the file this locked clip will get,
/// write progress, or selected 待选 / 失败 / 已写出代理.
/// Mid-write wording is 「写出代理 i/N · 文件名 · 第 k 帧」 (「第 k / 共 m 帧」 when this clip's total is known). No cancel / process / retry button here.
struct WriteProgressLine: View {
    let text: String
    var help: String = UICopy.PROGRESS_STATUS_HELP
    var truncation: Text.TruncationMode = .tail

    var body: some View {
        Text(text)
            .font(.callout.monospacedDigit())
            .foregroundStyle(.secondary)
            .lineLimit(1)
            .truncationMode(truncation)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.accentColor.opacity(0.08))
            .help(help)
    }
}

/// Status only — no process button here (one primary path).
struct StatusBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 10) {
            Text("LogBridge · 已实现（未验证）")
            if session.preview.isWorking {
                ProgressView()
                    .controlSize(.small)
            }
            Text(session.preview.status)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            if !session.isExporting, !session.lastExportNote.isEmpty {
                if session.canRevealLastExport {
                    Button(session.lastExportNote) {
                        session.revealLastExportInFinder()
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .help(SessionModel.revealInFinderLabel)
                    Button("在 Finder 中显示") {
                        session.revealLastExportInFinder()
                    }
                    .buttonStyle(.plain)
                } else {
                    Text(session.lastExportNote)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            Spacer()
        }
        .font(.caption)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.bar)
        .help(UICopy.PROGRESS_STATUS_HELP)
    }
}
