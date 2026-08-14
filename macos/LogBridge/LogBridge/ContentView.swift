import SwiftUI
import UniformTypeIdentifiers

/// Drop zone, clip list, split preview, node strip, inspector.
/// UI copy uses "implemented (unverified)" — never "supported".
/// Primary action is "处理已锁定片段" — never 一键还原.
/// Pending IDT button: "先选择 Log 与色域" (disabled). Export: "导出 ACEScct / EXR".
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
                    title: session.odtPreviewTitle,
                    caption: session.odtPreviewCaption,
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
            Text("LogBridge · serial graph · implemented (unverified)")
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
            Button(session.canProcessSelected ? "处理已锁定片段" : "先选择 Log 与色域") {
                session.processSelected()
            }
            .buttonStyle(.borderedProminent)
            .disabled(!session.canProcessSelected)
            .help("Apply the serial graph to locked clips. Blocked until a paired IDT is chosen. Never 一键还原.")
            Button("Apply graph") {
                session.applyGraph()
            }
            .disabled(!session.canProcessSelected)
            .help("Apply the serial graph to the selected clip. Same lock as 处理已锁定片段.")
            Button("导出 ACEScct / EXR") {
                session.exportResolve()
            }
            .disabled(!session.canProcess)
            .help("Export ACEScct timeline / ACES2065-1 EXR. Blocked while any clip is pending.")
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
