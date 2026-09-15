import SwiftUI
import UniformTypeIdentifiers

/// One primary path: list → preview + paired IDT → 处理已锁定片段.
/// Preview dominates the window. Sidebar / inspector / chrome recede.
/// Right inspector is Exposure + WB only. Paired IDT stays under preview
/// (never inside 「高级」). Node strip / Resolve export sit behind 「高级」
/// (hidden by default). UI copy uses "已实现（未验证）"
/// — never "supported". Primary action is "处理已锁定片段" — never 一键还原.
/// Unlocked IDT is skipped, never guessed. Export: "导出 ACEScct / EXR".
struct ContentView: View {
    @StateObject private var session = SessionModel()
    @State private var showAdvanced = false

    var body: some View {
        HSplitView {
            ClipSidebarView(session: session)
                .frame(minWidth: 196, idealWidth: 228, maxWidth: 280)
            VStack(spacing: 0) {
                SplitPreview(session: session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .layoutPriority(1)
                LBChrome.decisionDock {
                    PairedIDTBar(session: session)
                    ProcessLockedBar(session: session)
                }
                AdvancedPanel(session: session, isExpanded: $showAdvanced)
                StatusBar(session: session)
            }
            .frame(minWidth: 520)
            InspectorView(session: session)
                .frame(minWidth: 196, idealWidth: 220, maxWidth: 260)
        }
        .preferredColorScheme(.dark)
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
                .background(LBChrome.controlMaterial)
                .preferredColorScheme(.dark)
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

/// Center column action. Shown only when locked-clip count > 0.
/// Write progress lives on SplitPreview (WriteProgressLine), not here.
/// Not a second process button — StatusBar has no process control.
/// Never 一键还原. Hover/help is Chinese locked phrases.
/// Python copy-lock (test_batch_locked): 写出代理 EXR 序列（_ACES2065-1_proxy），不是 mov。整段代理，不是全精度成片。ACES2065-1 AP0 线性，不是 ACEScct。待选跳过（先选择 Log 与色域 / 先选择成对 IDT）。
/// Python copy-lock (test_batch_locked): 写出代理 EXR 序列（_ACES2065-1_proxy），不是 mov。整段代理，不是全精度成片。
struct ProcessLockedBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        LBChrome.processModule {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 12) {
                    Text(session.lockStatusText)
                        .font(.subheadline.weight(.semibold))
                    Spacer(minLength: 8)
                    if session.showsProcessLockedButton {
                        Button(session.isWritingDeliverables ? "取消" : "处理已锁定片段") {
                            if session.isWritingDeliverables {
                                session.cancelLockedDeliverables()
                            } else {
                                session.processLockedClips()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .font(.body.weight(.semibold))
                        .tint(session.isWritingDeliverables ? LBChrome.warn : LBChrome.locked)
                        .help("写出的是图片序列（EXR），不是 mp4/mov")
                    }
                }
                Text("代理 EXR，不是视频。整段代理，不是全精度成片。")
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
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
        .padding(.bottom, 14)
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
                    .help("只处理已锁定片段。待选跳过。709 预览。预览·非成片。不必全部锁定。")
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
        .font(.caption2)
        .foregroundStyle(.tertiary)
        .help("节点与导出 ACEScct / EXR。默认收起。预览·非成片。")
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .background(LBChrome.controlMaterial)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(LBChrome.hairline)
                .frame(height: 1)
        }
    }
}

struct SplitPreview: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
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
                if session.clips.isEmpty {
                    EmptyPreviewHero(targeted: session.dropTargeted) {
                        session.showImporter = true
                    }
                }
            }
            .background(LBChrome.canvas)
            PreviewScrubBar(session: session)
            // Mid-write: lastExportNote is 「写出代理 i/N · 第 k 帧」. Idle: selected caption only.
            if session.isExporting {
                WriteProgressLine(text: session.lastExportNote, writing: true)
            } else if let caption = session.selectedClip?.previewCaption {
                WriteProgressLine(text: caption)
            }
        }
    }
}

/// Movie: time axis from published duration. Decode lands on a frame via published fps.
/// Missing fps/duration: Chinese fail, no fake range. Stills: reserved strip, no slider.
/// Selected clip always keeps this strip so the viewer is not a dead pane.
struct PreviewScrubBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        // Hidden during write. Identity, not a fade. Scrub is not the write line.
        if session.isExporting || session.selectedClip == nil {
            EmptyView()
        } else {
            HStack(spacing: 12) {
                if session.previewScrubLastFrame != nil,
                   let duration = session.previewScrubDuration,
                   duration > 0,
                   session.previewScrubFPS != nil {
                    Slider(
                        value: Binding(
                            get: { session.previewTimeSeconds },
                            set: { session.setPreviewTime($0) }
                        ),
                        in: 0...duration
                    )
                    .controlSize(.regular)
                    .tint(LBChrome.locked)
                    .help("预览·非成片")
                    Text("\(SessionModel.formatPreviewClock(session.previewTimeSeconds)) / \(SessionModel.formatPreviewClock(duration))")
                        .font(.caption.monospacedDigit().weight(.medium))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(LBChrome.controlMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    if let fps = session.previewScrubFPS {
                        Text(SessionModel.formatPreviewFPS(fps))
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.tertiary)
                    }
                    Text("预览·非成片")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                } else if let fail = session.previewScrubFail {
                    Text(fail)
                        .font(.caption)
                        .foregroundStyle(LBChrome.warn)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Text("预览·非成片")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                } else {
                    Text("静帧。预览·非成片。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(LBChrome.controlMaterial)
            .overlay(alignment: .top) {
                Rectangle()
                    .fill(LBChrome.hairline)
                    .frame(height: 1)
            }
        }
    }
}

/// One Chinese line on the preview: write progress, or selected 待选 / 失败 / 已写出代理.
/// Mid-write wording stays 「写出代理 i/N · 第 k 帧」 (「第 k / 共 m 帧」 when total known). No cancel / process / retry button here.
struct WriteProgressLine: View {
    let text: String
    var writing: Bool = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown: Bool

    init(text: String, writing: Bool = false) {
        self.text = text
        self.writing = writing
        _shown = State(initialValue: !writing)
    }

    var body: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 1)
                .fill(LBChrome.locked)
                .frame(width: 2, height: 10)
            Text(text)
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14)
        .padding(.vertical, 5)
        .background(LBChrome.controlMaterial)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(LBChrome.hairline)
                .frame(height: 1)
        }
        .opacity(shown ? 1 : 0)
        .onAppear {
            guard writing, !shown else { return }
            LBChrome.runAppearMotion(reduceMotion) {
                shown = true
            }
        }
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
                    Button("在 Finder 中显示") {
                        session.revealLastExportInFinder()
                    }
                    .buttonStyle(.plain)
                    .help(SessionModel.revealInFinderLabel)
                } else {
                    Text(session.lastExportNote)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            Spacer()
        }
        .font(.caption2)
        .foregroundStyle(.tertiary)
        .padding(.horizontal, 16)
        .padding(.vertical, 5)
        .background(LBChrome.controlMaterial)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(LBChrome.hairline)
                .frame(height: 1)
        }
        .help("按每一帧出一张图，不是一条视频")
    }
}
