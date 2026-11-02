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

    var body: some View {
        VStack(spacing: 0) {
            WorkspaceToolbar(session: session)
            Divider()
            HSplitView {
                ClipSidebarView(session: session)
                    .frame(minWidth: 240, idealWidth: 292, maxWidth: 380)
                VStack(spacing: 0) {
                    MonitorHeader()
                    SplitPreview(session: session)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
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
        .sheet(isPresented: presentedSheet) {
            if session.showDeliverSheet {
                DeliverSheet(session: session)
            } else {
                SettingsView(settings: session.settings, session: session)
            }
        }
        .onChange(of: session.selectedID) { _, _ in
            if let clip = session.selectedClip {
                session.applyClipWBToGraph(clip)
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
                Text("调色与交付")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 12)
            Button("添加…") { session.showImporter = true }
                .controlSize(.large)
            Button("设置") {
                session.showDeliverSheet = false
                session.showSettings = true
            }
            .controlSize(.large)
            .help("全局偏好。改完即生效。")
            Button(session.isWritingDeliverables ? "取消" : "写出") {
                if session.isWritingDeliverables {
                    session.cancelLockedDeliverables()
                } else {
                    session.showSettings = false
                    session.showDeliverSheet = true
                }
            }
            .controlSize(.large)
            .disabled(!session.isWritingDeliverables && !session.showsProcessLockedButton)
            .help("先看写出说明，再选文件夹。整段代理，代理精度。")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
    }
}

private struct MonitorHeader: View {
    var body: some View {
        HStack(spacing: 8) {
            Text("监视器")
                .font(.headline)
            Text("左：源（相机 Log）  右：预览")
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            Text("仅预览")
                .font(.caption.weight(.bold))
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(Color.primary.opacity(0.08))
                .clipShape(Capsule())
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.primary.opacity(0.03))
    }
}

/// Inspector follows the selected clip. IDT, then exposure and white balance.
private struct InspectorColumn: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("检查器")
                    .font(.title3.weight(.semibold))
                if let clip = session.selectedClip {
                    Text(clip.filename)
                        .font(.body.weight(.semibold))
                        .lineLimit(1)
                    Text("成对 IDT 记在这条素材上。曝光和白平衡改完即在预览里生效；写出时已锁定素材共用当前这一套。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    Text("先在左侧点一条素材。")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            Divider()
            PairedIDTBar(session: session)
            Divider()
            InspectorView(session: session)
        }
        .background(Color.primary.opacity(0.02))
    }
}

/// Window-level Up/Down for the sidebar list. Escape while writing is the
/// existing 取消 (same cancelLockedDeliverables). Idle Escape does nothing.
/// Delete / Backspace drops the selected clip from the session only
/// (source file and already-written `_proxy` stay). Mid-write ignores Delete.
/// No help overlay. No extra button. No confirm sheet.
/// Same window only; text / numeric / search first-responders keep arrows
/// and Delete. Sheets / alerts / settings keep Escape and Delete.
private struct ClipListArrowMonitor: NSViewRepresentable {
    var handler: (Int) -> Bool
    var onEscape: () -> Bool
    var onDelete: () -> Bool

    func makeNSView(context: Context) -> MonitorView {
        let view = MonitorView()
        view.handler = handler
        view.onEscape = onEscape
        view.onDelete = onDelete
        return view
    }

    func updateNSView(_ nsView: MonitorView, context: Context) {
        nsView.handler = handler
        nsView.onEscape = onEscape
        nsView.onDelete = onDelete
    }

    static func dismantleNSView(_ nsView: MonitorView, coordinator: ()) {
        nsView.removeMonitor()
    }

    final class MonitorView: NSView {
        var handler: ((Int) -> Bool)?
        var onEscape: (() -> Bool)?
        var onDelete: (() -> Bool)?
        private var monitor: Any?

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
            monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
                guard let self, event.window === self.window else { return event }
                switch event.keyCode {
                case 126:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if self.handler?(-1) == true { return nil }
                    return event
                case 125:
                    if SessionModel.isArrowConsumedByTextInput() { return event }
                    if self.handler?(1) == true { return nil }
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
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("写出")
                    .font(.title3.weight(.semibold))
                Text(session.lockStatusText)
                    .font(.body.weight(.semibold))
                if let reason = session.selectedClip?.processSkipReason, session.showsProcessLockedButton {
                    Text(reason)
                        .font(.callout)
                        .foregroundStyle(.orange)
                        .lineLimit(2)
                }
                Spacer(minLength: 8)
                if session.showsProcessLockedButton {
                    Button(session.isWritingDeliverables ? "取消" : "处理已锁定片段") {
                        if session.isWritingDeliverables {
                            session.cancelLockedDeliverables()
                        } else {
                            session.showSettings = false
                            session.showDeliverSheet = true
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .help(UICopy.PROCESS_BUTTON_HELP_UI)
                }
            }
            Text(session.settings.exportFormat.labelZH)
                .font(.callout)
            Text(deliverableNote)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if !session.showsProcessLockedButton, !session.clips.isEmpty, !session.isWritingDeliverables {
                Text("下一步：在右侧检查器选成对 IDT。选完才能写出。")
                    .font(.body.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
                Text(session.selectedClip?.processSkipReason ?? "先选择 Log 与色域")
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if session.showsBatchSummary {
                Text(session.lastExportNote)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.accentColor.opacity(session.showsProcessLockedButton ? 0.08 : 0.04))
        .onChange(of: session.deliverSheetConfirmed) { _, confirmed in
            guard confirmed else { return }
            session.deliverSheetConfirmed = false
            openFolderPanelAfterSheet()
        }
    }

    /// NSOpenPanel on top of a dismissing sheet often never appears.
    /// Wait until the write sheet is gone, then use the existing folder panel.
    private func openFolderPanelAfterSheet() {
        let session = session
        func kick(_ attempt: Int) {
            DispatchQueue.main.async {
                let sheetStillUp = session.showDeliverSheet
                    || session.showSettings
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

/// Node strip, format, Resolve export, and the on-demand histogram.
/// Hidden by default. Paired IDT stays in the inspector — never here.
struct AdvancedPanel: View {
    @ObservedObject var session: SessionModel
    @Binding var isExpanded: Bool

    var body: some View {
        DisclosureGroup("高级", isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 8) {
                Text("节点、写出格式、直方图。默认收起，不挡预览。")
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
        .help(UICopy.ADVANCED_DISCLOSURE_HELP)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.primary.opacity(0.02))
    }
}

struct SplitPreview: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                HSplitView {
                    sourcePane
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
            image: session.preview.sourceImage
        )
    }

    @ViewBuilder
    private var previewPane: some View {
        if session.graph.odt.isHDR {
            HDRPreviewView(
                title: session.odtPreviewTitle,
                caption: session.odtPreviewCaption,
                image: session.preview.odtImage,
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
                title: session.odtPreviewTitle,
                caption: session.odtPreviewCaption,
                image: session.preview.odtImage,
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
            HStack(spacing: 10) {
                Text("预览帧")
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.secondary)
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
                Text("第 \(session.previewFrameIndex + 1) / \(last + 1) 帧")
                    .font(.body.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .frame(minWidth: 120, alignment: .trailing)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
    }
}

/// One Chinese line on the preview: write progress, or selected 待选 / 失败 / 已写出代理.
/// Mid-write wording stays 「写出代理 i/N · 第 k 帧」 (「第 k / 共 m 帧」 when total known). No cancel / process / retry button here.
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
