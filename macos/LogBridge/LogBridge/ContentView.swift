import SwiftUI
import UniformTypeIdentifiers

/// One primary path: list → preview + paired IDT → 处理已锁定片段.
/// Right inspector is Exposure + WB only. Paired IDT stays under preview
/// (never inside 「高级」). Node strip / Resolve export sit behind 「高级」
/// (hidden by default). UI copy uses "implemented (unverified)"
/// — never "supported". Primary action is "处理已锁定片段" — never 一键还原.
/// Unlocked IDT is skipped, never guessed. Export: "导出 ACEScct / EXR".
struct ContentView: View {
    @StateObject private var session = SessionModel()
    @State private var showAdvanced = false

    var body: some View {
        HSplitView {
            ClipSidebarView(session: session)
                .frame(minWidth: 240, idealWidth: 280, maxWidth: 360)
            VStack(spacing: 0) {
                SplitPreview(session: session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                PairedIDTBar(session: session)
                ProcessLockedBar(session: session)
                AdvancedPanel(session: session, isExpanded: $showAdvanced)
                StatusBar(session: session)
            }
            .frame(minWidth: 520)
            InspectorView(session: session)
                .frame(minWidth: 260, idealWidth: 300, maxWidth: 380)
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
    }
}

/// Center column action. Shown only when locked-clip count > 0.
/// Not a second process button — StatusBar has no process control.
struct ProcessLockedBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 12) {
            Text(session.lockStatusText)
                .font(.subheadline.weight(.semibold))
            if let reason = session.selectedClip?.processSkipReason {
                Text(reason)
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .lineLimit(1)
            }
            Spacer()
            if session.showsProcessLockedButton {
                Button("处理已锁定片段") {
                    session.processLockedClips()
                }
                .buttonStyle(.borderedProminent)
                .help("Batch locked clips only. Unlocked stay listed (先选择 Log 与色域 / 先选择成对 IDT). Never 一键还原.")
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.accentColor.opacity(0.05))
    }
}

/// Node strip + Resolve export only. Hidden by default.
/// Paired IDT stays on the main path under the preview — never here.
struct AdvancedPanel: View {
    @ObservedObject var session: SessionModel
    @Binding var isExpanded: Bool

    var body: some View {
        DisclosureGroup("高级", isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 8) {
                NodeStripView(session: session)
                HStack {
                    Button("导出 ACEScct / EXR") {
                        session.exportResolve()
                    }
                    .disabled(!session.canProcess)
                    .help("Export ACEScct timeline / ACES2065-1 EXR. Blocked while any clip is pending.")
                    if let reason = session.processBlockedReason {
                        Text(reason)
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                    Spacer()
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.primary.opacity(0.03))
    }
}

struct SplitPreview: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HSplitView {
            SourcePreviewView(
                title: "源（相机 Log）",
                caption: "未套 Rec.709。相机编码值。",
                image: session.preview.sourceImage
            )
            Rec709PreviewView(
                title: session.odtPreviewTitle,
                caption: session.odtPreviewCaption,
                image: session.preview.odtImage,
                pickingNeutral: session.pickingNeutral,
                onPick: { nx, ny in
                    session.handlePreviewPick(nx: nx, ny: ny)
                }
            )
        }
        .padding(8)
    }
}

/// Status only — no process button here (one primary path).
struct StatusBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 12) {
            Text("LogBridge · serial graph · implemented (unverified)")
            if session.preview.isWorking {
                ProgressView()
                    .controlSize(.small)
            }
            Text(session.preview.status)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            if !session.lastExportNote.isEmpty {
                Text(session.lastExportNote)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
        }
        .font(.caption)
        .padding(8)
        .background(.bar)
    }
}
