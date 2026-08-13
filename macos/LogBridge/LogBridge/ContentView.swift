import SwiftUI
import UniformTypeIdentifiers

/// Drop zone, clip list, split preview, node strip, inspector.
/// UI copy uses "implemented (unverified)" — never "supported".
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
            SourcePreviewView(
                title: "Source (camera log)",
                caption: "Untagged. Camera/log code values. Do not blit Rec.709 pixels into this pane. Preview is a downscaled proxy.",
                image: session.preview.sourceImage
            )
            Rec709PreviewView(
                title: session.graph.odtEnabled
                    ? "Rec.709 ODT (implemented, unverified)"
                    : "ODT off — working space (not Rec.709)",
                caption: session.graph.odtEnabled
                    ? "Tagged CGColorSpace.itur_709. Preview ≠ full render. Golden grey-card samples required before any accuracy claim."
                    : "Node 3 off: ACEScct deliverable. This pane is not tagged Rec.709.",
                image: session.preview.odtImage
            )
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
            Spacer()
            Button("Export for Resolve…") {
                session.exportResolve()
            }
            .disabled(session.clips.isEmpty)
        }
        .font(.caption)
        .padding(8)
        .background(.bar)
    }
}
