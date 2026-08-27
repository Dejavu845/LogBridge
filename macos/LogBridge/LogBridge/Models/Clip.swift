import Foundation
import Combine
import AppKit
import simd

/// One imported clip with a locked curve+gamut pair (or a pending picker).
///
/// `idt` is nil until metadata/filename/model locks a pair or the user picks
/// a paired IDT. Never default S-Log3 to S-Gamut3.Cine, or C-Log2/C-Log3 to Cinema Gamut.
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
    var asShotCCT: Double?
    var asShotTint: Double
    var wbSource: WBSource
    var wbCCT: Double?
    var wbTint: Double
    var formatNote: String

    var filename: String { url.lastPathComponent }

    var asShotUnknown: Bool { asShotCCT == nil && wbSource == .unknown }

    var lockedPairLabel: String {
        if let idt {
            return idt.pairLabel
        }
        if let curve = detectedCurve {
            return "\(curve) + (pick pair)"
        }
        return "先选择成对 IDT"
    }

    /// Paired IDTs only. Venice rows appear only if this clip is a Venice body.
    var pickerPairs: [IDT] {
        IDT.pickerPairs(
            curveHint: displayCurve,
            veniceDetected: veniceDetected,
            needsPicker: needsUserPicker || idt == nil
        )
    }

    /// No locked implemented pair — stays pending; batch skips this clip.
    var isPending: Bool { idt == nil || needsUserPicker }

    var hasLockedPair: Bool {
        guard let idt, !idt.isStub else { return false }
        return !needsUserPicker
    }

    /// Unlocked / pending stay in the list with this reason. Never guess an IDT.
    var processSkipReason: String? {
        if hasLockedPair { return nil }
        if detectedCurve != nil || idt != nil || needsUserPicker {
            return "先选择成对 IDT"
        }
        return "先选择 Log 与色域"
    }

    var verificationBadge: String {
        if let idt, idt.isStub { return "stub" }
        if isPending { return "待选" }
        return "已实现（未验证）"
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
    @Published var lastImportNote: String = ""
    @Published var pickingNeutral: Bool = false
    @Published var showSettings = false
    @Published var isWritingDeliverables = false

    let preview = PreviewEngine()
    let settings = AppSettings.shared
    private let writeCancel = WriteCancelFlag()
    private var lastProgressUptime: TimeInterval = 0

    init() {
        graph.odt = settings.defaultPreviewODT
    }

    var selectedClip: Clip? {
        clips.first { $0.id == selectedID }
    }

    func refreshPreview() {
        preview.refresh(clip: selectedClip, graph: graph)
    }

    /// ODT / scrub: do not invalidate graded linear (IDT+exposure+WB).
    func refreshODTOnly() {
        preview.refreshODT(clip: selectedClip, graph: graph)
    }

    var pendingPickerCount: Int {
        clips.filter { $0.needsUserPicker || $0.idt == nil }.count
    }

    var lockedClips: [Clip] { clips.filter(\.hasLockedPair) }
    var lockedClipCount: Int { lockedClips.count }
    var pendingClipCount: Int { clips.filter { !$0.hasLockedPair }.count }

    /// 「N 条已锁定 / M 条待选」
    var lockStatusText: String {
        "\(lockedClipCount) 条已锁定 / \(pendingClipCount) 条待选"
    }

    /// Primary button is shown only when at least one paired IDT is locked.
    var showsProcessLockedButton: Bool {
        settings.blockUnlockedIDT && lockedClipCount > 0
    }

    /// ACEScct / EXR export for locked clips. Pending clips in the same bin
    /// do not block — they stay listed and are skipped.
    var canProcess: Bool {
        !clips.isEmpty && lockedClipCount > 0
    }

    /// Selected clip has a locked pair (preview / inspector).
    var canProcessSelected: Bool {
        selectedClip?.hasLockedPair == true
    }

    var processBlockedReason: String? {
        if clips.isEmpty { return "把混源文件夹拖进来" }
        if lockedClipCount == 0 {
            return clips.first?.processSkipReason ?? "先选择 Log 与色域"
        }
        return nil
    }

    var processSelectedBlockedReason: String? {
        guard let clip = selectedClip else { return "No clip selected" }
        return clip.processSkipReason
    }

    /// Batch: write one ACES2065-1 AP0 proxy EXR sequence per locked clip.
    /// Unlocked stay listed with a Chinese reason. 「N 条已处理」 is sequences
    /// written or attempted with a per-clip error — not a preview refresh.
    /// Never guess an IDT. Never 一键还原. One process entry point.
    /// Mixed bins are allowed. 整段代理，不是全精度成片.
    func processLockedClips() {
        if isWritingDeliverables { return }
        let locked = clips.filter(\.hasLockedPair)
        let skipped = clips.filter { !$0.hasLockedPair }
        guard !locked.isEmpty else {
            lastExportNote = skipped.first?.processSkipReason ?? "先选择 Log 与色域"
            return
        }
        if selectedClip?.hasLockedPair == true {
            refreshPreview()
        }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "写出"
        panel.message = "已锁定片段写出 ACES2065-1 代理 EXR 序列（AP0 线性）。整段代理，不是全精度成片。未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。预览·非成片。已实现（未验证）。"
        panel.begin { [weak self] response in
            guard let self, response == .OK, let dest = panel.url else { return }
            self.writeLockedDeliverables(locked: locked, skippedCount: skipped.count, dest: dest)
        }
    }

    /// Writes ACES2065-1 AP0 proxy EXR sequences for locked clips only.
    func writeLockedDeliverables(locked: [Clip], skippedCount: Int, dest: URL) {
        let graphCopy = graph
        let clipTotal = locked.count
        writeCancel.reset()
        lastProgressUptime = 0
        isWritingDeliverables = true
        lastExportNote = Self.exportProgressText(clipIndex: 1, clipTotal: clipTotal)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            var written: [URL] = []
            var errors: [String] = []
            var cancelled = false
            for (offset, clip) in locked.enumerated() {
                if self.writeCancel.isRequested {
                    cancelled = true
                    break
                }
                let clipIndex = offset + 1
                self.publishExportProgress(
                    Self.exportProgressText(clipIndex: clipIndex, clipTotal: clipTotal),
                    force: true
                )
                do {
                    let url = try self.exportLockedEXR(
                        clip: clip,
                        graph: graphCopy,
                        dest: dest
                    ) { frame in
                        self.publishExportProgress(
                            Self.exportProgressText(
                                clipIndex: clipIndex,
                                clipTotal: clipTotal,
                                frame: frame
                            )
                        )
                    }
                    written.append(url)
                } catch is LockedWriteCancel {
                    cancelled = true
                    break
                } catch {
                    errors.append("\(clip.filename): \(error.localizedDescription)")
                }
            }
            let processed = written.count + errors.count
            var note: String
            if cancelled {
                note = Self.cancelledExportNote(processed: processed, skipped: skippedCount)
            } else {
                note = "处理已锁定片段 — \(processed) 条已处理 / \(skippedCount) 条已跳过（先选择 Log 与色域 / 先选择成对 IDT）。整段代理，不是全精度成片。预览·非成片。已实现（未验证）。"
            }
            if !errors.isEmpty {
                note += " " + errors.joined(separator: " ")
            }
            DispatchQueue.main.async {
                self.lastExportNote = note
                self.isWritingDeliverables = false
            }
        }
    }

    /// One ACES2065-1 AP0 proxy EXR sequence. Decode loop + PreviewColor grade; no ODT.
    /// Not ACEScct. Not a Rec.709 movie. 整段代理，不是全精度成片.
    func exportLockedEXR(
        clip: Clip,
        graph: SerialGraph,
        dest: URL,
        onFrame: ((Int) -> Void)? = nil
    ) throws -> URL {
        guard clip.hasLockedPair else {
            throw NSError(domain: "LogBridge", code: 1, userInfo: [
                NSLocalizedDescriptionKey: clip.processSkipReason ?? "先选择成对 IDT"
            ])
        }
        let seqDir = ResolveExporter.deliverableSequenceDirectory(for: clip, in: dest)
        if FileManager.default.fileExists(atPath: seqDir.path) {
            try FileManager.default.removeItem(at: seqDir)
        }
        try FileManager.default.createDirectory(at: seqDir, withIntermediateDirectories: true)
        do {
            let count = try preview.exportGradedAP0Sequence(clip: clip, graph: graph) { index, rgb, width, height in
                if self.writeCancel.isRequested {
                    throw LockedWriteCancel()
                }
                let url = ResolveExporter.sequenceFrameURL(in: seqDir, index: index)
                try ResolveExporter.writeACES2065EXR(
                    rgb: rgb,
                    width: width,
                    height: height,
                    to: url
                )
                onFrame?(index + 1)
            }
            if count < 1 {
                throw NSError(domain: "LogBridge", code: 2, userInfo: [
                    NSLocalizedDescriptionKey: "decode/grade failed"
                ])
            }
        } catch {
            try? FileManager.default.removeItem(at: seqDir)
            throw error
        }
        return seqDir
    }

    /// Same primary button becomes 取消 while writing. Not a second process button.
    func cancelLockedDeliverables() {
        writeCancel.request()
    }

    /// 「写出代理 2/5 · frame 120」. Frame total omitted when unknown.
    static func exportProgressText(clipIndex: Int, clipTotal: Int, frame: Int? = nil, frameTotal: Int? = nil) -> String {
        var note = "写出代理 \(clipIndex)/\(clipTotal)"
        if let frame {
            if let frameTotal {
                note += " · frame \(frame)/\(frameTotal)"
            } else {
                note += " · frame \(frame)"
            }
        }
        return note
    }

    /// Cancelled batch. 已取消 + honesty. Partial output is 不是成片.
    static func cancelledExportNote(processed: Int, skipped: Int) -> String {
        "处理已锁定片段 — 已取消。\(processed) 条已处理 / \(skipped) 条已跳过（先选择 Log 与色域 / 先选择成对 IDT）。整段代理，不是全精度成片。预览·非成片。已实现（未验证）。"
    }

    private func publishExportProgress(_ note: String, force: Bool = false) {
        let now = ProcessInfo.processInfo.systemUptime
        if !force && (now - lastProgressUptime) < 0.12 { return }
        lastProgressUptime = now
        DispatchQueue.main.async { [weak self] in
            self?.lastExportNote = note
        }
    }

    /// Primary action alias. Label is "处理已锁定片段" — never 一键还原.
    func processSelected() {
        processLockedClips()
    }

    /// Same batch as processLockedClips. Never 一键还原. Not a second button.
    func applyGraph() {
        processLockedClips()
    }

    var odtPreviewTitle: String {
        switch graph.odt {
        case .off:
            return "成片预览关 · ACEScct"
        case .rec709:
            return "Rec.709 预览·非成片"
        case .hlg:
            return "HLG 预览·非成片（未匹配 709）"
        case .pq:
            return "PQ 预览·非成片（未匹配 709）"
        }
    }

    var odtPreviewCaption: String {
        let badge = "预览·非成片 — 8-bit thumbnail is not a deliverable."
        switch graph.odt {
        case .off:
            return "Node 4 off: ACEScct deliverable. This pane is not tagged Rec.709. Not a finished picture. \(badge)"
        case .rec709:
            return "Tagged CGColorSpace.itur_709. Preview only — not a finished grade on the 709 pane. \(badge) Golden grey-card samples required before any accuracy claim."
        case .hlg, .pq:
            return "\(graph.odt.acesOTNote) 未与 709 匹配，不是同一条渲染。Preview does not invent a homemade HLG/PQ curve. \(badge)"
        }
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

    func setExposureEnabled(_ enabled: Bool) {
        graph.setEnabled(.exposure, enabled)
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setExposureStops(_ stops: Double) {
        graph.exposureStops = stops
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setWBEnabled(_ enabled: Bool) {
        graph.setEnabled(.wb, enabled)
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setODTEnabled(_ enabled: Bool) {
        graph.setEnabled(.odt, enabled)
        refreshODTOnly()
    }

    func setODT(_ mode: ODTMode) {
        graph.odt = mode
        refreshODTOnly()
    }

    func setWBParams(cct: Double? = nil, tint: Double? = nil, method: String? = nil) {
        if let cct {
            graph.wbCCT = cct
            graph.wbSource = .user
        }
        if let tint {
            graph.wbTint = tint
            if graph.wbCCT != nil {
                graph.wbSource = .user
            }
        }
        if let method { graph.wbMethod = method }
        persistGraphWBToSelectedClip()
        preview.invalidateWBODT()
        refreshPreview()
    }

    func applyClipWBToGraph(_ clip: Clip) {
        graph.asShotCCT = clip.asShotCCT
        graph.asShotTint = clip.asShotTint
        graph.wbSource = clip.wbSource
        graph.wbCCT = clip.wbCCT
        graph.wbTint = clip.wbTint
        if clip.wbSource == .asShot || clip.wbSource == .grey || clip.wbSource == .estimate {
            graph.wbEnabled = true
        }
    }

    func persistGraphWBToSelectedClip() {
        guard let id = selectedID, let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        clips[idx].wbSource = graph.wbSource
        clips[idx].wbCCT = graph.wbCCT
        clips[idx].wbTint = graph.wbTint
    }

    /// Grey-card pick: sample after IDT in ACES2065-1 (AP0) linear. Overrides metadata.
    func pickNeutral(linearRGB: SIMD3<Double>) {
        guard let est = WhiteBalanceNode.pickNeutral(linearRGB: linearRGB, rgbToXYZ: WhiteBalanceNode.ap0ToXYZ) else { return }
        graph.wbCCT = est.cct
        graph.wbTint = est.tint
        graph.wbSource = .grey
        graph.wbEnabled = true
        persistGraphWBToSelectedClip()
        preview.invalidateWBODT()
        refreshPreview()
    }

    /// 白平衡（估计）: SoG on cached post-IDT AP0. Does not write CAT.
    func proposeAutoWB() {
        guard let clip = selectedClip, clip.hasLockedPair else { return }
        guard let frame = preview.linearAP0Frame(clipID: clip.id) else { return }
        if let est = WhiteBalanceNode.estimateAutoWB(ap0: frame.rgb, width: frame.width, height: frame.height) {
            graph.autoWBCCT = est.cct
            graph.autoWBTint = est.tint
        } else {
            graph.autoWBCCT = nil
            graph.autoWBTint = 0
        }
    }

    /// Confirm estimate → absolute AP0 CAT. Grey-card wins. Empty stays empty.
    func confirmAutoWB() {
        guard graph.wbSource != .grey, let cct = graph.autoWBCCT else { return }
        graph.wbCCT = cct
        graph.wbTint = graph.autoWBTint
        graph.wbSource = .estimate
        graph.wbEnabled = true
        persistGraphWBToSelectedClip()
        preview.invalidateWBODT()
        refreshPreview()
    }

    /// Click on the processed pane: sample cached post-IDT AP0 linear (not log, not ACEScct).
    func handlePreviewPick(nx: Double, ny: Double) {
        guard pickingNeutral, let clip = selectedClip else { return }
        guard let rgb = preview.sampleLinearRGB(
            clipID: clip.id,
            nx: nx,
            ny: ny,
            exposureStops: 0,
            exposureEnabled: false
        ) else { return }
        pickNeutral(linearRGB: rgb)
        pickingNeutral = false
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
            var skipped: [String] = []
            var built: [Clip] = []
            for file in files {
                let probe = MediaFormat.probe(url: file)
                if probe.decision == .refuse {
                    skipped.append("\(file.lastPathComponent)：\(probe.note)")
                    continue
                }
                if probe.decision == .tryDecode {
                    // MXF: only keep if the system can open a video track.
                    if MediaFormat.codecFourCC(url: file) == nil {
                        skipped.append("\(file.lastPathComponent)：\(MediaFormat.noteARRIMxf)")
                        continue
                    }
                }
                let detection = ClipDetector.detect(url: file)
                // Never silently assign an IDT. S-Log3 without gamut stays nil.
                let shot = detection.asShotCCT
                built.append(Clip(
                    id: UUID(),
                    url: file,
                    idt: detection.idt,
                    detectedCurve: detection.curve,
                    detectedGamut: detection.gamut,
                    detectionSource: detection.source,
                    needsUserPicker: detection.needsUserPicker,
                    detectionNote: detection.note,
                    veniceDetected: detection.veniceDetected,
                    asShotCCT: shot,
                    asShotTint: detection.asShotTint,
                    wbSource: shot == nil ? .unknown : .asShot,
                    wbCCT: shot,
                    wbTint: detection.asShotTint,
                    formatNote: probe.note
                ))
            }
            DispatchQueue.main.async {
                guard let self else { return }
                for clip in built {
                    self.clips.append(clip)
                    if self.selectedID == nil {
                        self.selectedID = clip.id
                        self.applyClipWBToGraph(clip)
                    }
                }
                if !skipped.isEmpty {
                    self.lastImportNote = skipped.joined(separator: "\n")
                }
                if self.settings.promptEstimateWBOnImport {
                    let locked = built.contains { $0.hasLockedPair }
                    let hint = "可点「估计白平衡」查看估计，确认后才写入。不是校准，不猜 5600。"
                    if locked {
                        self.lastImportNote = (self.lastImportNote.isEmpty ? hint : self.lastImportNote + "\n" + hint)
                    }
                }
                self.refreshPreview()
            }
        }
    }

    private static let clipExtensions: Set<String> = MediaFormat.expandExt

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
                ?? clips.first?.processSkipReason
                ?? "先选择 Log 与色域"
            return
        }
        let locked = lockedClips
        let skipped = clips.filter { !$0.hasLockedPair }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Export"
        panel.message = "已锁定片段写出 Resolve 节点图（XML / DCTL / .cube）。未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。709 预览。预览·非成片。已实现（未验证）。"
        panel.begin { [weak self] response in
            guard let self, response == .OK, let url = panel.url else { return }
            do {
                let written = try ResolveExporter.export(
                    to: url,
                    clips: locked,
                    includeWBNode: self.graph.wbEnabled,
                    cct: self.graph.wbCCT,
                    tint: self.graph.wbTint,
                    catCCT: self.graph.effectiveWBCCT,
                    useEffectiveCAT: true,
                    srcCCT: self.graph.effectiveSrcCCT,
                    srcTint: self.graph.asShotTint,
                    odtEnabled: self.graph.odtEnabled,
                    exposureStops: self.graph.exposureStops,
                    exposureEnabled: self.graph.exposureEnabled
                )
                var note = ResolveExporter.exportNote(
                    clips: locked,
                    includeWBNode: self.graph.wbEnabled,
                    cct: self.graph.wbCCT,
                    tint: self.graph.wbTint
                )
                note += "\nWrote \(written.count) files to \(url.path). \(locked.count) 条已锁定 / \(skipped.count) 条已跳过（先选择 Log 与色域 / 先选择成对 IDT）。709 预览。预览·非成片。已实现（未验证）。"
                self.lastExportNote = note
            } catch {
                self.lastExportNote = "Export failed: \(error.localizedDescription)"
            }
        }
    }
}

/// Thrown when the user cancels a locked-clip proxy write.
struct LockedWriteCancel: Error {}

/// Thread-safe cancel flag. Written from the button, read from the write queue.
final class WriteCancelFlag {
    private let lock = NSLock()
    private var flagged = false

    func reset() {
        lock.lock()
        flagged = false
        lock.unlock()
    }

    func request() {
        lock.lock()
        flagged = true
        lock.unlock()
    }

    var isRequested: Bool {
        lock.lock()
        defer { lock.unlock() }
        return flagged
    }
}
