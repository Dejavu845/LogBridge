import Foundation
import Combine
import AppKit

/// One imported clip with a locked curve+gamut pair.
struct Clip: Identifiable, Hashable {
    let id: UUID
    let url: URL
    var idt: IDT
    var detectionSource: DetectionSource
    var needsUserPicker: Bool
    var detectionNote: String

    var lockedPairLabel: String {
        "\(idt.curve) + \(idt.gamut)"
    }

    var verificationBadge: String {
        if idt.isStub { return "stub" }
        return "implemented (unverified)"
    }
}

enum DetectionSource: String, Hashable {
    case metadata
    case filename
    case model
    case user
    case unresolved
}

final class SessionModel: ObservableObject {
    @Published var clips: [Clip] = []
    @Published var selectedID: UUID?
    @Published var showImporter = false
    @Published var dropTargeted = false
    @Published var whiteBalanceEnabled = false
    @Published var cct: Double = 6504
    @Published var tint: Double = 0
    @Published var lastExportNote: String = ""

    var selectedClip: Clip? {
        clips.first { $0.id == selectedID }
    }

    func setIDT(_ id: UUID, _ idt: IDT) {
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        clips[idx].idt = idt
        clips[idx].detectionSource = .user
        clips[idx].needsUserPicker = false
        clips[idx].detectionNote = "user picker"
    }

    func importProviders(_ providers: [NSItemProvider]) {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                let url: URL?
                if let data = item as? Data {
                    url = URL(dataRepresentation: data, relativeTo: nil)
                } else if let u = item as? URL {
                    url = u
                } else {
                    url = nil
                }
                guard let url else { return }
                DispatchQueue.main.async {
                    self.importURL(url)
                }
            }
        }
    }

    func handleImporter(_ result: Result<[URL], Error>) {
        if case .success(let urls) = result {
            urls.forEach { importURL($0) }
        }
    }

    func importURL(_ url: URL) {
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue {
            let keys: [URLResourceKey] = [.isRegularFileKey]
            if let enumerator = FileManager.default.enumerator(at: url, includingPropertiesForKeys: keys) {
                for case let file as URL in enumerator {
                    appendClip(file)
                }
            }
            return
        }
        appendClip(url)
    }

    private func appendClip(_ url: URL) {
        let detection = ClipDetector.detect(url: url)
        let clip = Clip(
            id: UUID(),
            url: url,
            idt: detection.idt ?? .sonySLog3SGamut3,
            detectionSource: detection.source,
            needsUserPicker: detection.needsUserPicker,
            detectionNote: detection.note
        )
        // If unresolved, still add the clip but force the picker — and NEVER
        // silently pick S-Gamut3.Cine for S-Log3.
        clips.append(clip)
        if selectedID == nil { selectedID = clip.id }
    }

    func exportResolve() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Export"
        panel.message = "Folder for the Resolve node graph (LUT / CDL / DCTL). WB is a bypassable node."
        panel.begin { [weak self] response in
            guard let self, response == .OK, let url = panel.url else { return }
            do {
                let written = try ResolveExporter.export(
                    to: url,
                    clips: self.clips,
                    includeWBNode: self.whiteBalanceEnabled,
                    cct: self.cct,
                    tint: self.tint
                )
                self.lastExportNote = ResolveExporter.exportNote(
                    clips: self.clips,
                    includeWBNode: self.whiteBalanceEnabled,
                    cct: self.cct,
                    tint: self.tint
                ) + "\nWrote \(written.count) files to \(url.path)"
            } catch {
                self.lastExportNote = "Export failed: \(error.localizedDescription)"
            }
        }
    }
}
