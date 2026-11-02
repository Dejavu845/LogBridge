import SwiftUI
import UniformTypeIdentifiers

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
    @State private var monitorLayout: MonitorLayout = .split
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
                    MonitorHeader(session: session, layout: $monitorLayout, zoom: $monitorZoom)
                        .onChange(of: monitorZoom) { _, _ in
                            monitorPan.reset()
                        }
                        .onChange(of: session.selectedID) { _, _ in
                            monitorPan.reset()
                        }
                    SplitPreview(
                        session: session,
                        layout: monitorLayout,
                        zoom: monitorZoom,
                        panBus: monitorPan
                    )
                        .frame(minHeight: 200, maxWidth: .infinity, maxHeight: .infinity)
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
        .fileImporter(
            isPresented: $session.showImporter,
            allowedContentTypes: [.movie, .quickTimeMovie, .mpeg4Movie, .folder, .item],
            allowsMultipleSelection: true
        ) { result in
            session.handleImporter(result)
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
                onUndoGrade: {
                    session.undoSharedGrade()
                },
                onRedoGrade: {
                    session.redoSharedGrade()
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

/// Top bar: add, global settings, write. Not a multi-page shell.
private struct WorkspaceToolbar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 1) {
                Text("LogBridge")
                    .font(.headline)
                Text(session.loopStepHint)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .help("打开后的下一步。导入、选成对 IDT、调色、写出，都在这一窗。")
            }
            Spacer(minLength: 12)
            Button("添加…") { session.presentImporter() }
                .controlSize(.large)
                .disabled(session.openingExportFolder)
            Button("设置") {
                session.presentSettings()
            }
            .controlSize(.large)
            .disabled(session.openingExportFolder)
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
    case source
    case grade

    var id: String { rawValue }

    var label: String {
        switch self {
        case .split: return "分屏"
        case .source: return "源"
        case .grade: return "预览"
        }
    }

    var caption: String {
        switch self {
        case .split: return "左：源（相机 Log）  右：预览"
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
                .frame(width: 210)
                .labelsHidden()
                .help("分屏对照，或把预览放大来看调色。点灰卡时会显示预览。仅预览。")
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
                    Text(gradeReadout)
                        .font(.callout.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .help(session.previewShowsGradeBefore
                              ? "画面不含曝光和白平衡。这一行仍是检查器里会写出的那一套。仅预览。"
                              : "和右侧检查器是同一套。换一条素材，这一行的曝光和白平衡不改。仅预览。")
                }
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

    /// 监视器上的调色读数。数字来自当前检查器，不另存一套，也不参与写出。
    private var gradeReadout: String {
        let clipName = session.selectedClip?.filename ?? ""
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
        let line = "\(clipName) · \(pending)\(exposure) · \(wb)"
        if session.previewShowsGradeBefore {
            return "看调色前 · \(line)"
        }
        return line
    }
}

/// 检查器跟当前选中。标题固定；成对 IDT、曝光、白平衡在下面整栏滚动。
/// 窗口变矮时仍能滚到曝光和白平衡，不会被成对 IDT 顶出画面。
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
                    Text("先拖入或点「添加…」。选中一条后，这里跟这条。")
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
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    PairedIDTBar(session: session)
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
        }
        .background(Color.primary.opacity(0.02))
    }
}

/// Window-level Up/Down for the sidebar list. Left/Right steps the preview
/// frame (same as 上一帧 / 下一帧). Shift+Left/Right jumps about one second
/// when this clip's rate was read. Home / End jump to the first or last
/// preview frame. Space plays or pauses that preview.
/// Escape while writing is the existing 取消
/// (same cancelLockedDeliverables). Idle Escape does nothing.
/// Delete / Backspace drops the selected clip from the session only
/// (source file and already-written `_proxy` stay). Mid-write ignores Delete.
/// No help overlay. No extra button. No confirm sheet.
/// Same window only; text / numeric / search / slider first-responders keep
/// arrows and Delete. Sheets / alerts / settings keep Escape and Delete.
/// ⌘Z / ⇧⌘Z step the shared grade, unless a text field has the keys.
private struct ClipListArrowMonitor: NSViewRepresentable {
    var handler: (Int) -> Bool
    var onEscape: () -> Bool
    var onDelete: () -> Bool
    var onStepFrame: (Int) -> Bool
    var onJumpToStart: () -> Bool
    var onJumpToEnd: () -> Bool
    var onStepSecond: (Int) -> Bool
    var onTogglePlayback: () -> Bool
    var onUndoGrade: () -> Bool
    var onRedoGrade: () -> Bool
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
        view.onUndoGrade = onUndoGrade
        view.onRedoGrade = onRedoGrade
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
        nsView.onUndoGrade = onUndoGrade
        nsView.onRedoGrade = onRedoGrade
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
        var onUndoGrade: (() -> Bool)?
        var onRedoGrade: (() -> Bool)?
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
                default:
                    return event
                }
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
                Text("写出说明已收起。选文件夹会贴在这个窗口上。取消则不写出。")
                    .font(.body.weight(.semibold))
                    .lineLimit(2)
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
                case .source:
                    sourcePane
                case .grade:
                    previewPane
                }
                PreviewScrubBar(session: session)
                if session.isExporting {
                    WriteProgressLine(text: session.lastExportNote)
                } else if let caption = session.selectedClip?.previewCaption {
                    WriteProgressLine(text: caption)
                }
            }
            if session.clips.isEmpty {
                VStack(spacing: 10) {
                    Text("把混源文件夹拖进来")
                        .font(.title2.weight(.semibold))
                    Text("或点「添加…」。每条再选成对 Log 与色域。")
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
                    Text("在右侧检查器选成对 IDT。预览角标仍是仅预览。")
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

    private var sourcePane: some View {
        SourcePreviewView(
            title: "源（相机 Log）",
            caption: "未套 Rec.709。相机编码值。",
            image: session.preview.sourceImage,
            zoom: shownZoom,
            panBus: panBus
        )
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
        if session.graph.odt.isHDR {
            HDRPreviewView(
                title: gradePaneTitle,
                caption: gradePaneCaption,
                image: session.preview.odtImage,
                zoom: shownZoom,
                panBus: panBus,
                odt: session.graph.odt,
                pickingNeutral: session.pickingNeutral && !session.isExporting,
                onPick: { nx, ny in
                    session.handlePreviewPick(nx: nx, ny: ny)
                },
                onLayerFail: {
                    session.failClosedHDRPreviewLayer()
                }
            )
        } else {
            Rec709PreviewView(
                title: gradePaneTitle,
                caption: gradePaneCaption,
                image: session.preview.odtImage,
                zoom: shownZoom,
                panBus: panBus,
                pickingNeutral: session.pickingNeutral && !session.isExporting,
                onPick: { nx, ny in
                    session.handlePreviewPick(nx: nx, ny: ny)
                }
            )
        }
    }
}

/// Movie: slider first…last from duration × metadata fps. Cache hit: 只重跑预览输出.
/// Missing fps/duration: Chinese fail, no fake range. Stills: no slider.
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
                HStack(spacing: 8) {
                    Button(session.isPreviewPlaying ? "暂停" : "播放") {
                        session.togglePreviewPlayback()
                    }
                    .controlSize(.regular)
                    .disabled(!session.canTogglePreviewPlayback)
                    .help("按这条素材自己的帧率走预览。这一帧还没画完就等它。循环关掉时到最后一帧就停，不绕回。循环打开时回到第 1 帧接着播。空格是同一套。不改曝光和白平衡，不参与写出。读不到帧率就不能播。")
                    if session.showsPreviewLoop {
                        Button(session.previewLoops ? "循环中" : "循环") {
                            session.togglePreviewLoop()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canTogglePreviewLoop)
                        .help("打开后，播放到最后一帧回到第 1 帧接着播。关掉则到最后一帧就停，不绕回。⌥⌘L 是同一套。只有一帧、静帧或读不到帧率时没有这一下。打开或关掉不改当前帧，不改这一套曝光和白平衡，也不参与写出。")
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
                    Slider(
                        value: Binding(
                            get: { Double(session.previewFrameIndex) },
                            set: { session.setPreviewFrame(Int($0.rounded())) }
                        ),
                        in: 0...Double(last),
                        step: 1
                    )
                    .controlSize(.regular)
                    .help("仅预览")
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
            line += session.isPreviewPlaying ? " · 循环播放" : " · 循环"
        } else if session.isPreviewPlaying {
            line += " · 播放中"
        }
        return line
    }
}

/// One Chinese line on the preview: write progress, or selected 待选 / 失败 / 已写出代理.
/// Mid-write wording is 「写出代理 i/N · 文件名 · 第 k 帧」 (「第 k / 共 m 帧」 when this clip's total is known). No cancel / process / retry button here.
struct WriteProgressLine: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.callout.monospacedDigit())
            .foregroundStyle(.secondary)
            .lineLimit(1)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.accentColor.opacity(0.08))
            .help(UICopy.PROGRESS_STATUS_HELP)
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
