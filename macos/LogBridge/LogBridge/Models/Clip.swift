import Foundation
import Combine
import AppKit

/// One imported clip with a locked curve+gamut pair (or a pending picker).
///
/// `idt` is nil until metadata/filename/model locks a pair or the user picks
/// a paired IDT. Never default S-Log3 to S-Gamut3.Cine.
struct Clip: Identifiable, Hashable {
    let id: UUID
    let url: URL
    var idt: IDT?
    var detectedCurve: String?
    var detectedGamut: String?
    var detectionSource: DetectionSource
    var needsUserPicker: Bool
    var detectionNote: String
    var veniceDetected: Bool

    var filename: String { url.lastPathComponent }

    var lockedPairLabel: String {
        if let idt {
            return idt.pairLabel
        }
        if let curve = detectedCurve {
            return "\(curve) + (pick pair)"
        }
        return "pick a paired IDT"
    }

    /// Paired IDTs only. Venice rows appear only if this clip is a Venice body.
    var pickerPairs: [IDT] {
        IDT.pickerPairs(
            curveHint: displayCurve,
            veniceDetected: veniceDetected,
            needsPicker: needsUserPicker || idt == nil
        )
    }

    /// No locked implemented pair — stays pending; process/export blocked.
    var isPending: Bool { idt == nil || needsUserPicker }

    var hasLockedPair: Bool {
        guard let idt, !idt.isStub else { return false }
        return !needsUserPicker
    }

    var verificationBadge: String {
        if let idt, idt.isStub { return "stub" }
        if isPending { return "pending" }
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

    var pendingPickerCount: Int {
        clips.filter { $0.needsUserPicker || $0.idt == nil }.count
    }

    /// Batch process / Resolve export. Blocked until every clip has a locked pair.
    var canProcess: Bool {
        !clips.isEmpty
            && pendingPickerCount == 0
            && clips.allSatisfy { $0.hasLockedPair }
    }

    /// Process selected / Apply graph — only the selected clip must be locked.
    var canProcessSelected: Bool {
        selectedClip?.hasLockedPair == true
    }

    var processBlockedReason: String? {
        if clips.isEmpty { return "Drop a folder of mixed clips" }
        if pendingPickerCount > 0 {
            let n = pendingPickerCount
            return "Pick a paired IDT for \(n) pending clip\(n == 1 ? "" : "s") — process/export blocked"
        }
        if clips.contains(where: { $0.idt?.isStub == true }) {
            return "Stub IDT — process/export blocked"
        }
        return nil
    }

    var processSelectedBlockedReason: String? {
        guard let clip = selectedClip else { return "No clip selected" }
        if clip.isPending {
            return "Selected clip is pending — pick a paired IDT. Process selected / Apply graph blocked."
        }
        if clip.idt?.isStub == true {
            return "Stub IDT — Process selected / Apply graph blocked."
        }
        return nil
    }

    /// Primary action. Label is "Process selected" — never 一键还原.
    func processSelected() {
        guard canProcessSelected else {
            lastExportNote = processSelectedBlockedReason
                ?? "Selected clip is pending — process blocked."
            return
        }
        refreshPreview()
        lastExportNote = "Process selected — applied serial graph (预览·非成片; 8-bit thumbnail is not a deliverable)."
    }

    /// Same lock as processSelected. Label is "Apply graph" — never 一键还原.
    func applyGraph() {
        guard canProcessSelected else {
            lastExportNote = processSelectedBlockedReason
                ?? "Selected clip is pending — Apply graph blocked."
            return
        }
        refreshPreview()
        lastExportNote = "Apply graph — serial graph applied to the selected clip (preview proxy, not a deliverable)."
    }

    func setIDT(_ id: UUID, _ idt: IDT) {
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        clips[idx].idt = idt
        clips[idx].detectedCurve = idt.curve
        clips[idx].detectedGamut = idt.gamut
        clips[idx].detectionSource = .user
        clips[idx].needsUserPicker = false
        clips[idx].detectionNote = "user picker (paired IDT)"
        preview.invalidateIDT(clipID: id)
        refreshPreview()
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
        // Keep the security scope for the session so preview decode can reopen the URL.
        _ = url.startAccessingSecurityScopedResource()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let files = Self.expandToClipURLs(url)
            let built: [Clip] = files.map { file in
                let detection = ClipDetector.detect(url: file)
                // Never silently assign an IDT. S-Log3 without gamut stays nil.
                return Clip(
                    id: UUID(),
                    url: file,
                    idt: detection.idt,
                    detectedCurve: detection.curve,
                    detectedGamut: detection.gamut,
                    detectionSource: detection.source,
                    needsUserPicker: detection.needsUserPicker,
                    detectionNote: detection.note,
                    veniceDetected: detection.veniceDetected
                )
            }
            DispatchQueue.main.async {
                guard let self else { return }
                for clip in built {
                    self.clips.append(clip)
                    if self.selectedID == nil { self.selectedID = clip.id }
                }
                self.refreshPreview()
            }
        }
    }

    private static let clipExtensions: Set<String> = [
        "mov", "mp4", "m4v", "mxf", "avi", "mkv", "r3d", "braw",
        "ari", "arx", "dng", "exr", "tif", "tiff", "dpx"
    ]

    /// Folder drop expands to media files. A single dropped file is kept as-is.
    static func expandToClipURLs(_ url: URL) -> [URL] {
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir) else {
            return [url]
        }
        if !isDir.boolValue {
            return [url]
        }
        var out: [URL] = []
        let keys: [URLResourceKey] = [.isRegularFileKey]
        if let enumerator = FileManager.default.enumerator(
            at: url,
            includingPropertiesForKeys: keys,
            options: [.skipsHiddenFiles]
        ) {
            for case let file as URL in enumerator {
                if clipExtensions.contains(file.pathExtension.lowercased()) {
                    out.append(file)
                }
            }
        }
        return out.sorted {
            $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending
        }
    }

    func exportResolve() {
        guard canProcess else {
            lastExportNote = processBlockedReason
                ?? "Pick a paired IDT before export. Process selected / Apply graph is blocked for pending clips."
            return
        }
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
