import Foundation
import Combine
import AppKit

/// One imported clip with a locked curve+gamut pair (or a pending picker).
///
/// `idt` is nil until metadata/filename/model locks a pair or the user picks
/// both curve and gamut. Never default S-Log3 to S-Gamut3.Cine.
struct Clip: Identifiable, Hashable {
    let id: UUID
    let url: URL
    var idt: IDT?
    var detectedCurve: String?
    var detectedGamut: String?
    var detectionSource: DetectionSource
    var needsUserPicker: Bool
    var detectionNote: String

    var filename: String { url.lastPathComponent }

    var lockedPairLabel: String {
        if let idt {
            return "\(idt.curve) + \(idt.gamut)"
        }
        if let curve = detectedCurve, detectedGamut == nil {
            return "\(curve) + (pick gamut)"
        }
        return "pick curve + gamut"
    }

    var verificationBadge: String {
        if let idt, idt.isStub { return "stub" }
        if idt == nil { return "needs picker" }
        return "implemented (unverified)"
    }

    var displayCurve: String? { idt?.curve ?? detectedCurve }
    var displayGamut: String? { idt?.gamut ?? detectedGamut }
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
    @Published var selectedNode: NodeSlot = .idt
    @Published var graph = SerialGraph()
    @Published var showImporter = false
    @Published var dropTargeted = false
    @Published var lastExportNote: String = ""

    let preview = PreviewEngine()

    var selectedClip: Clip? {
        clips.first { $0.id == selectedID }
    }

    func refreshPreview() {
        preview.refresh(clip: selectedClip, graph: graph)
    }

    func setIDT(_ id: UUID, _ idt: IDT) {
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        clips[idx].idt = idt
        clips[idx].detectedCurve = idt.curve
        clips[idx].detectedGamut = idt.gamut
        clips[idx].detectionSource = .user
        clips[idx].needsUserPicker = false
        clips[idx].detectionNote = "user picker"
        preview.invalidateIDT(clipID: id)
        refreshPreview()
    }

    /// Curve picker. A single-gamut curve locks the pair; S-Log3 waits for gamut.
    func setCurve(_ id: UUID, curve: String) {
        let pairs = IDT.pairs(forCurve: curve)
        if pairs.count == 1 {
            setIDT(id, pairs[0])
            return
        }
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        clips[idx].idt = nil
        clips[idx].detectedCurve = curve
        clips[idx].detectedGamut = nil
        clips[idx].needsUserPicker = true
        clips[idx].detectionSource = .user
        clips[idx].detectionNote = "\(curve) selected; pick gamut (never default S-Gamut3.Cine)"
        preview.invalidateIDT(clipID: id)
        refreshPreview()
    }

    func setGamut(_ id: UUID, gamut: String) {
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        let curve = clips[idx].idt?.curve ?? clips[idx].detectedCurve
        guard let curve, let idt = IDT.match(curve: curve, gamut: gamut) else { return }
        setIDT(id, idt)
    }

    func setWBEnabled(_ enabled: Bool) {
        graph.setEnabled(.wb, enabled)
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setODTEnabled(_ enabled: Bool) {
        graph.setEnabled(.odt, enabled)
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setWBParams(cct: Double? = nil, tint: Double? = nil, method: String? = nil) {
        if let cct { graph.wbCCT = cct }
        if let tint { graph.wbTint = tint }
        if let method { graph.wbMethod = method }
        preview.invalidateWBODT()
        refreshPreview()
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
        // Never silently assign an IDT. S-Log3 without gamut stays nil
        // (user must pick S-Gamut3 or S-Gamut3.Cine — never default Cine).
        let clip = Clip(
            id: UUID(),
            url: url,
            idt: detection.idt,
            detectedCurve: detection.curve,
            detectedGamut: detection.gamut,
            detectionSource: detection.source,
            needsUserPicker: detection.needsUserPicker,
            detectionNote: detection.note
        )
        clips.append(clip)
        if selectedID == nil { selectedID = clip.id }
        refreshPreview()
    }

    func exportResolve() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Export"
        panel.message = "Folder for the Resolve node graph (LUT / CDL / DCTL). WB node 2 off = no bake."
        panel.begin { [weak self] response in
            guard let self, response == .OK, let url = panel.url else { return }
            do {
                let written = try ResolveExporter.export(
                    to: url,
                    clips: self.clips,
                    includeWBNode: self.graph.wbEnabled,
                    cct: self.graph.wbCCT,
                    tint: self.graph.wbTint,
                    odtEnabled: self.graph.odtEnabled
                )
                self.lastExportNote = ResolveExporter.exportNote(
                    clips: self.clips,
                    includeWBNode: self.graph.wbEnabled,
                    cct: self.graph.wbCCT,
                    tint: self.graph.wbTint
                ) + "\nWrote \(written.count) files to \(url.path)"
            } catch {
                self.lastExportNote = "Export failed: \(error.localizedDescription)"
            }
        }
    }
}
