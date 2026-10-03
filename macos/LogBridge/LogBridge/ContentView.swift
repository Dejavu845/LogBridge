import SwiftUI
import UniformTypeIdentifiers

/// The window's session, published for menu commands.
/// Lives here so the screenshot compile (which skips LogBridgeApp.swift) can see it.
/// A focused-scene value keeps working when the sidebar is not in the tree,
/// and still targets only the focused window.
struct SessionFocus: Hashable {
    weak var session: SessionModel?

    static func == (lhs: SessionFocus, rhs: SessionFocus) -> Bool {
        lhs.session === rhs.session
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(session.map { ObjectIdentifier($0) })
    }
}

private struct LogBridgeSessionKey: FocusedValueKey {
    typealias Value = SessionFocus
}

extension FocusedValues {
    var logBridgeSession: SessionFocus? {
        get { self[LogBridgeSessionKey.self] }
        set { self[LogBridgeSessionKey.self] = newValue }
    }
}

/// One primary path: list → preview + paired IDT → 处理已锁定片段.
/// Preview dominates the window. Sidebar / inspector / chrome recede.
/// Right inspector is Exposure + WB only. Paired IDT stays under preview
/// (never inside 「高级」). Node strip / Resolve export sit behind 「高级」
/// (hidden by default). UI copy uses "已实现（未验证）"
/// — never "supported". Primary action is "处理已锁定片段" — 不是一步还原.
/// Unlocked IDT is skipped, never guessed. Export: "导出 ACEScct / EXR".
/// Team B shell: empty = full drop canvas; working = header steps + same path.
struct ContentView: View {
    @StateObject private var session: SessionModel
    @ObservedObject private var settings = AppSettings.shared

    /// Live window uses a fresh session. The macOS screenshot baseline passes sample state.
    init(session: SessionModel? = nil) {
        _session = StateObject(wrappedValue: session ?? SessionModel())
    }

    var body: some View {
        VStack(spacing: 8) {
            WorkspaceHeader(session: session)
            if session.clips.isEmpty {
                EmptyPreviewStage(session: session)
            } else {
                HSplitView {
                    ClipSidebarView(session: session)
                        .frame(minWidth: 196, idealWidth: 228, maxWidth: 280)
                    VStack(spacing: 0) {
                        SplitPreview(session: session)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .layoutPriority(1)
                        PairedIDTBar(session: session)
                        ProcessLockedBar(session: session)
                        AdvancedPanel(session: session, isExpanded: $settings.advancedPanelExpanded)
                        StatusBar(session: session)
                    }
                    .frame(minWidth: 520)
                    InspectorView(session: session)
                        .frame(minWidth: 196, idealWidth: 220, maxWidth: 260)
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                ProcessLockedToolbarButton(session: session)
            }
        }
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
        .sheet(isPresented: $session.showSettings) {
            SettingsView(settings: session.settings, session: session)
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

/// Center column status. The primary button lives in the window toolbar.
/// Write progress lives on SplitPreview (WriteProgressLine), not here.
/// Not a second process button — StatusBar has no process control.
/// 不是一步还原. Hover/help is Chinese locked phrases.
/// Python copy-lock (test_batch_locked): 写出代理 EXR 序列（_ACES2065-1_proxy），不是 mov。整段代理，代理精度。ACES2065-1 AP0 线性，不是 ACEScct。待选跳过（先选择 Log 与色域 / 先选择成对 IDT）。
/// Python copy-lock (test_batch_locked): 写出代理 EXR 序列（_ACES2065-1_proxy），不是 mov。整段代理，代理精度。
struct ProcessLockedBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("写出代理")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Text(session.lockStatusText)
                        .font(.subheadline.weight(.semibold))
                }
                if let reason = session.selectedClip?.processSkipReason {
                    // Warning: skip reason. Orange is only for this warning.
                    Text(reason)
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .lineLimit(2)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.orange.opacity(0.12))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                } else if !session.showsProcessLockedButton {
                    // Warning: nothing locked yet. Orange is only for this warning.
                    Text(session.processBlockedReason ?? "先选择 Log 与色域")
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .lineLimit(2)
                }
                Spacer(minLength: 8)
            }
            Text("代理 EXR，不是视频。整段代理，代理精度。")
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if session.showsBatchSummary {
                Text(session.lastExportNote)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.accentColor.opacity(0.06))
    }
}

/// The window toolbar's only primary action.
/// Disabled until at least one clip is locked. Same button cancels a write.
/// The caption sits in this item, next to the button. No second row under the header.
struct ProcessLockedToolbarButton: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 8) {
            if session.clips.isEmpty {
                Text("把混源文件夹拖进来")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .frame(minWidth: 0, alignment: .trailing)
                    .layoutPriority(0)
            } else if session.lockedClipCount == 0 {
                Text("先选成对 Log 与色域")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .frame(minWidth: 0, alignment: .trailing)
                    .layoutPriority(0)
            }
            Button(session.isWritingDeliverables ? "取消" : "处理已锁定片段") {
                if session.isWritingDeliverables {
                    session.cancelLockedDeliverables()
                } else {
                    session.processLockedClips()
                }
            }
            .buttonStyle(.borderedProminent)
            .fixedSize()
            .layoutPriority(1)
            .disabled(session.lockedClipCount == 0)
            .modifier(ProcessLockedButtonHelp(
                importing: session.clips.isEmpty,
                unlocked: session.lockedClipCount == 0
            ))
        }
    }
}

/// Tooltip matches the caption beside the button. The button keeps its own title.
/// Locked help stays the EXR line. `if` removes the caption once a clip is locked.
private struct ProcessLockedButtonHelp: ViewModifier {
    var importing: Bool
    var unlocked: Bool

    func body(content: Content) -> some View {
        if importing {
            content
                .help("把混源文件夹拖进来")
        } else if unlocked {
            content
                .help("先选成对 Log 与色域")
        } else {
            content
                .help("写出的是图片序列（EXR），不是 mp4/mov")
        }
    }
}

/// Node strip + Resolve export only. Hidden by default.
/// Paired IDT stays on the main path under the preview — never here.
struct AdvancedPanel: View {
    @ObservedObject var session: SessionModel
    @Binding var isExpanded: Bool

    var body: some View {
        DisclosureGroup("高级", isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 6) {
                NodeStripView(session: session)
                HStack {
                    Button("导出 ACEScct / EXR") {
                        session.exportResolve()
                    }
                    .controlSize(.small)
                    .disabled(!session.canProcess)
                    .help("只处理已锁定片段。待选跳过。写出整段代理，代理精度 EXR，以及 cube 节点。不必全部锁定。")
                    if let reason = session.processBlockedReason {
                        Text(reason)
                            .font(.caption2)
                            .foregroundStyle(.orange)
                    }
                    Spacer()
                }
                .padding(.horizontal, 10)
                .padding(.bottom, 6)
            }
        }
        .help("节点与导出 ACEScct / EXR。展开状态会记住。整段代理，代理精度。")
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(Color.primary.opacity(0.025))
    }
}

struct SplitPreview: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(spacing: 0) {
            if session.selectedClip == nil {
                VStack(spacing: 8) {
                    Text("先点一条素材")
                        .font(.headline)
                    Text("读不到元数据就在下面选成对 IDT，不猜。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.primary.opacity(0.03))
            } else {
                HSplitView {
                    SourcePreviewView(
                        title: "源（相机 Log）",
                        caption: "未套 Rec.709。相机编码值。",
                        image: session.preview.sourceImage
                    )
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
            PreviewScrubBar(session: session)
            if session.isExporting {
                WriteProgressLine(text: session.lastExportNote)
            } else if let caption = session.selectedClip?.previewCaption {
                WriteProgressLine(text: caption)
            }
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
                .font(.caption)
                .foregroundStyle(.orange)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
        } else if let last = session.previewScrubLastFrame {
            HStack(spacing: 8) {
                Slider(
                    value: Binding(
                        get: { Double(session.previewFrameIndex) },
                        set: { session.setPreviewFrame(Int($0.rounded())) }
                    ),
                    in: 0...Double(last),
                    step: 1
                )
                .controlSize(.small)
                .help("仅预览")
                Text("第 \(session.previewFrameIndex + 1) / \(last + 1) 帧")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .frame(minWidth: 88, alignment: .trailing)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
        }
    }
}

/// One Chinese line on the preview: write progress, or selected 待选 / 失败 / 已写出代理.
/// Mid-write wording stays 「写出代理 i/N · 第 k 帧」 (「第 k / 共 m 帧」 when total known). No cancel / process / retry button here.
struct WriteProgressLine: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption.monospacedDigit())
            .foregroundStyle(.secondary)
            .lineLimit(1)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(Color.accentColor.opacity(0.08))
            .help("按每一帧出一张图，不是一条视频")
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
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(.bar)
        .help("按每一帧出一张图，不是一条视频")
    }
}
