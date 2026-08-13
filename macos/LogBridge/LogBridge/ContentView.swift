import SwiftUI
import UniformTypeIdentifiers

/// Drop files/folder, clip list, split preview placeholder.
/// UI copy uses "implemented (unverified)" — never "supported" or marketing claims.
struct ContentView: View {
    @StateObject private var session = SessionModel()

    var body: some View {
        NavigationSplitView {
            ClipListView(session: session)
                .navigationSplitViewColumnWidth(min: 260, ideal: 320)
        } detail: {
            VStack(spacing: 0) {
                PipelineBar(session: session)
                SplitPreviewPlaceholder(session: session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                StatusBar(session: session)
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
    }
}

struct ClipListView: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Clips")
                    .font(.headline)
                Spacer()
                Button("Add…") { session.showImporter = true }
            }
            .padding(.horizontal, 12)
            .padding(.top, 8)

            Text("Drop files or a folder. Detection: camera-private metadata → filename/model → user picker. QuickTime nclc is never used to identify S-Log3 or LogC4.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)

            List(selection: $session.selectedID) {
                ForEach(session.clips) { clip in
                    ClipRow(clip: clip)
                        .tag(clip.id)
                }
            }
            .listStyle(.inset)

            if session.dropTargeted {
                Text("Drop to import")
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(.quaternary)
            }
        }
    }
}

struct ClipRow: View {
    let clip: Clip

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(clip.url.lastPathComponent)
                .lineLimit(1)
            HStack {
                Text(clip.lockedPairLabel)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(clip.verificationBadge)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.orange.opacity(0.2))
                    .clipShape(Capsule())
            }
        }
        .padding(.vertical, 2)
    }
}

struct PipelineBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(spacing: 16) {
            Text("Pipeline")
                .font(.headline)
            Text("IDT → WB (scene-linear) → Rec.709 ODT")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            if let clip = session.selectedClip {
                Picker("IDT", selection: Binding(
                    get: { clip.idt },
                    set: { session.setIDT(clip.id, $0) }
                )) {
                    ForEach(IDT.allCases) { idt in
                        Text(idt.menuLabel).tag(idt)
                    }
                }
                .frame(maxWidth: 360)
                Toggle("WB node (linear)", isOn: $session.whiteBalanceEnabled)
                if session.whiteBalanceEnabled {
                    Text("CCT")
                    Slider(value: $session.cct, in: 2000...10000, step: 10)
                        .frame(width: 120)
                    Text("\(Int(session.cct)) K")
                        .monospacedDigit()
                        .frame(width: 64, alignment: .trailing)
                    Text("tint")
                    Slider(value: $session.tint, in: -10...10, step: 0.1)
                        .frame(width: 80)
                }
            }
        }
        .padding(8)
        .background(.bar)
    }
}

struct SplitPreviewPlaceholder: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HSplitView {
            Rec709PreviewView(
                title: "Source (log, tagged Rec.709 preview)",
                caption: "Placeholder. Framebuffer is Rec.709-tagged; this is not an untagged P3 blit."
            )
            Rec709PreviewView(
                title: "Rec.709 output (implemented, unverified)",
                caption: "ODT is Rec.709 OETF after scene-linear WB. Golden grey-card samples are required before any accuracy claim."
            )
        }
        .padding(8)
    }
}

struct StatusBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack {
            Text("LogBridge M1 · implemented (unverified)")
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
