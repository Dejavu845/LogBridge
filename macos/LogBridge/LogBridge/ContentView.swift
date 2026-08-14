import SwiftUI
import UniformTypeIdentifiers

/// Drop zone, clip list, split preview, node strip, inspector.
/// UI copy uses "implemented (unverified)" — never "supported".
/// Primary actions are "Process selected" / "Apply graph" — never 一键还原.
struct ContentView: View {
    @StateObject private var session = SessionModel()

    var body: some View {
        HSplitView {
            ClipSidebarView(session: session)
                .frame(minWidth: 240, idealWidth: 300, maxWidth: 380)
            VStack(spacing: 0) {
                SplitPreview(session: session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                NodeStripView(session: session)
                InspectorView(session: session)
                StatusBar(session: session)
            }
            .frame(minWidth: 640)
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
        .onChange(of: session.selectedID) { _, _ in
            session.refreshPreview()
        }
    }
}

struct SplitPreview: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HSplitView {
            ZStack(alignment: .topLeading) {
                SourcePreviewView(
                    title: "Source (camera log)",
                    caption: "Untagged. Camera/log code values. Do not blit Rec.709 pixels into this pane. 预览·非成片 — 8-bit thumbnail is not a deliverable.",
                    image: session.preview.sourceImage
                )
                PreviewBadge()
            }
            ZStack(alignment: .topLeading) {
                Rec709PreviewView(
                    title: session.graph.odtEnabled
                        ? "Rec.709 ODT (implemented, unverified)"
                        : "ODT off — working space (not Rec.709)",
                    caption: session.graph.odtEnabled
                        ? "Tagged CGColorSpace.itur_709. 预览·非成片 — 8-bit thumbnail is not a deliverable. Golden grey-card samples required before any accuracy claim."
                        : "Node 3 off: ACEScct deliverable. This pane is not tagged Rec.709. 预览·非成片 — 8-bit thumbnail is not a deliverable.",
                    image: session.preview.odtImage
                )
                PreviewBadge()
            }
        }
        .padding(8)
    }
}

struct StatusBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 12) {
            Text("LogBridge M1 · serial graph · implemented (unverified)")
            if session.preview.isWorking {
                ProgressView()
                    .controlSize(.small)
            }
            Text(session.preview.status)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            if let reason = session.processBlockedReason {
                Text(reason)
                    .foregroundStyle(.orange)
                    .lineLimit(1)
            }
            if !session.lastExportNote.isEmpty {
                Text(session.lastExportNote)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
            Button("Process selected") {
                session.processSelected()
            }
            .buttonStyle(.borderedProminent)
            .disabled(!session.canProcessSelected)
            .help("Apply the serial graph to the selected clip. Blocked while the clip is pending (no locked IDT pair). Never 一键还原.")
            Button("Apply graph") {
                session.applyGraph()
            }
            .disabled(!session.canProcessSelected)
            .help("Apply the serial graph to the selected clip. Same lock as Process selected.")
            Button("Export for Resolve…") {
                session.exportResolve()
            }
            .disabled(!session.canProcess)
            .help("Blocked while any clip is pending without a locked IDT pair.")
        }
        .font(.caption)
        .padding(8)
        .background(.bar)
    }
}

struct PreviewBadge: View {
    var body: some View {
        Text("预览·非成片")
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(.black.opacity(0.65))
            .foregroundStyle(.white)
            .clipShape(Capsule())
            .padding(12)
            .help("8-bit thumbnail / proxy. Not a color-accurate deliverable.")
    }
}
