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
    /// Source pixels from `MediaFormat.extent`. Nil when that read failed. Not the 1920 preview.
    var pixelWidth: Int? = nil
    var pixelHeight: Int? = nil
    /// Metadata frame rate. Nil on stills and when the file has no rate. Never a 24/30 fill-in.
    var mediaFPS: Double? = nil
    /// Metadata duration in seconds. Nil on stills and when duration is missing.
    var durationSeconds: Double? = nil
    /// Still image. The fact line says 静帧 and does not invent a frame rate.
    var isStill: Bool = false
    /// Sidebar chip after 「处理已锁定片段」. `已写出代理`, a short Chinese error, or nil.
    /// Cleared on re-export. Cancelled in-progress stays nil. 未完成.
    var exportChip: String? = nil
    /// File name of the proxy this row just wrote. Nil unless the chip is 已写出代理.
    var writtenDeliverableName: String? = nil
    /// Absolute path of that proxy file or EXR folder. Nil unless the chip is 已写出代理.
    var writtenRevealPath: String? = nil

    var filename: String { url.lastPathComponent }

    /// File or folder the write will create. Same suffixes as the writers.
    /// ProRes: `{stem}_Rec709_proxy.mov`. EXR: `{stem}_ACES2065-1_proxy`.
    func plannedDeliverableName(format: ExportFormat) -> String {
        let stem = url.deletingPathExtension().lastPathComponent
        switch format {
        case .prores422HQ:
            return stem + ProResWriter.proresSuffix
        case .exrACES2065:
            return stem + ResolveExporter.proxyFolderSuffix
        }
    }

    var asShotUnknown: Bool { asShotCCT == nil && wbSource == .unknown }

    var lockedPairLabel: String {
        if let idt {
            return idt.pairLabel
        }
        if let curve = detectedCurve {
            return "\(curve) + 先选择成对 IDT"
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
        if let idt, idt.isStub { return "未实现" }
        if isPending { return "待选" }
        return "已实现（未验证）"
    }

    /// Sidebar row under the pair. Pending keep skip reasons.
    /// After a write: 已写出代理 or a short Chinese error.
    var sidebarStatusChip: String? { processSkipReason ?? exportChip }

    /// Preview chrome when selected and not mid-export. Existing phrases only.
    /// Pending / unlocked → that clip's processSkipReason. Failed / success → exportChip.
    var previewCaption: String? { processSkipReason ?? exportChip }

    var displayCurve: String? { idt?.curve ?? detectedCurve }
    var displayGamut: String? { idt?.gamut ?? detectedGamut }

    /// List, monitor, inspector, and the write sheet share this line.
    /// Only numbers `MediaFormat.extent` actually read. Missing fields stay off the line.
    /// Stills say 静帧 and do not show a rate. Not an input to write.
    var mediaFactLine: String? {
        Self.mediaFactLine(
            pixelWidth: pixelWidth,
            pixelHeight: pixelHeight,
            mediaFPS: mediaFPS,
            durationSeconds: durationSeconds,
            isStill: isStill
        )
    }

    static func mediaFactLine(
        pixelWidth: Int?,
        pixelHeight: Int?,
        mediaFPS: Double?,
        durationSeconds: Double?,
        isStill: Bool
    ) -> String? {
        var parts: [String] = []
        if let width = pixelWidth, let height = pixelHeight, width > 0, height > 0 {
            parts.append("\(width)×\(height)")
        }
        if isStill {
            parts.append("静帧")
        } else {
            if let fps = mediaFPS, fps.isFinite, fps > 0 {
                parts.append("\(formatMediaFPS(fps)) 帧/秒")
            }
            if let seconds = durationSeconds, seconds.isFinite, seconds > 0 {
                parts.append(formatMediaDuration(seconds))
            }
        }
        if parts.isEmpty { return nil }
        return parts.joined(separator: " · ")
    }

    /// Trim to milliseconds. 23.976 stays 23.976. An exact integer stays an integer.
    /// Does not replace a missing rate.
    static func formatMediaFPS(_ fps: Double) -> String {
        let milli = (fps * 1000).rounded()
        let rounded = milli / 1000
        if abs(milli.truncatingRemainder(dividingBy: 1000)) < 0.5 {
            return String(Int(rounded.rounded()))
        }
        var text = String(format: "%.3f", rounded)
        while text.hasSuffix("0") {
            text.removeLast()
        }
        if text.hasSuffix(".") {
            text.removeLast()
        }
        return text
    }

    /// Under a minute: tenths. Longer: clock, rounded to the second. No invented length.
    static func formatMediaDuration(_ seconds: Double) -> String {
        if seconds < 60 {
            let tenths = (seconds * 10).rounded() / 10
            if abs(tenths - tenths.rounded()) < 0.05 {
                return "\(Int(tenths.rounded())) 秒"
            }
            return String(format: "%.1f 秒", tenths)
        }
        let total = Int(seconds.rounded())
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let remain = total % 60
        if hours > 0 {
            return String(format: "%d 小时 %02d 分 %02d 秒", hours, minutes, remain)
        }
        return String(format: "%d 分 %02d 秒", minutes, remain)
    }

    /// Preview clock for this frame: index divided by this clip's metadata rate.
    /// Milliseconds. Nil when the rate is missing or not finite. Not camera timecode.
    /// Does not fill in a rate.
    static func previewClock(frameIndex: Int, fps: Double?) -> String? {
        guard frameIndex >= 0, let fps, fps.isFinite, fps > 0 else { return nil }
        let seconds = Double(frameIndex) / fps
        guard seconds.isFinite, seconds >= 0 else { return nil }
        let wholeMillis = Int((seconds * 1000).rounded())
        let millis = wholeMillis % 1000
        let totalSeconds = wholeMillis / 1000
        let secs = totalSeconds % 60
        let minutes = (totalSeconds / 60) % 60
        let hours = totalSeconds / 3600
        if hours > 0 {
            return String(format: "%d:%02d:%02d.%03d", hours, minutes, secs, millis)
        }
        return String(format: "%d:%02d.%03d", minutes, secs, millis)
    }

    /// Frames in about one second at this clip's rate. Nearest whole frame.
    /// Nil when the rate is missing or rounds to nothing. Does not fill in a rate.
    static func previewSecondFrameCount(fps: Double?) -> Int? {
        guard let fps, fps.isFinite, fps > 0 else { return nil }
        let frames = Int(fps.rounded())
        guard frames >= 1 else { return nil }
        return frames
    }
}

enum DetectionSource: String, Hashable {
    case metadata
    case filename
    case model
    case user
    case unresolved

    /// User-visible 来源 label. English raw values stay off the inspector line.
    var title: String {
        switch self {
        case .metadata: return "元数据"
        case .filename: return "文件名"
        case .model: return "机型"
        case .user: return "用户选择成对 IDT"
        case .unresolved: return "读不到"
        }
    }
}

/// Locked-clip dest estimate.
/// EXR: uncompressed half RGB (6 bytes / pixel).
/// Default ProRes: 1 byte / pixel. The note names which figure was used.
/// Header / offset table is covered by the 10% + 64 MiB margin. 未完成.
struct ProxyDiskEstimate {
    var bytes: Int64
    var usedFrameGuess: Bool
    var usedDurationFps: Bool
    var assumption: String

    var neededWithMargin: Int64 {
        bytes + bytes / 10 + 64 * 1024 * 1024
    }

    var note: String {
        let size = SessionModel.formatProxyBytes(bytes)
        if assumption == SessionModel.diskEstimateAssumption {
            if usedFrameGuess {
                return "约 \(size)（未压缩浮点图；帧数按每秒 24 帧估算）"
            }
            if usedDurationFps {
                return "约 \(size)（未压缩浮点图；帧数按时长×帧率估算）"
            }
            return "约 \(size)（未压缩浮点图）"
        }
        if usedFrameGuess {
            return "约 \(size)（\(assumption)；帧数按每秒 24 帧估算）"
        }
        if usedDurationFps {
            return "约 \(size)（\(assumption)；帧数按时长×帧率估算）"
        }
        return "约 \(size)（\(assumption)）"
    }

    var pickerSuffix: String { note + "。" }
}

enum WorkspaceSheet: Equatable {
    case settings
    case deliver
}

/// Sidebar list filter. Does not change the shared grade or which clip is previewed
/// until the user moves the selection inside the filtered rows.
/// One continuous slider drag. A button or another knob starts a new step.
private enum SharedGradeStroke {
    case exposure
    case cct
    case tint
}

/// Exposure and white balance only. Not the paired IDT, the preview frame, or this viewing ODT.
private struct SharedGradeSnapshot: Equatable {
    var exposureEnabled: Bool
    var exposureStops: Double
    var wbEnabled: Bool
    var wbCCT: Double?
    var wbTint: Double
    var wbMethod: String
    var wbSource: WBSource
    var asShotCCT: Double?
    var asShotTint: Double
}

enum ClipListFilter: String, CaseIterable, Identifiable {
    case all
    case pending
    case locked

    var id: String { rawValue }

    var label: String {
        switch self {
        case .all: return "全部"
        case .pending: return "待选"
        case .locked: return "已锁定"
        }
    }
}

final class SessionModel: ObservableObject {
    @Published var clips: [Clip] = []
    /// 全部 / 待选 / 已锁定. The monitor keeps the current clip until selection moves.
    @Published var clipListFilter: ClipListFilter = .all
    @Published var selectedID: UUID?
    @Published var selectedNode: NodeSlot = .idt
    @Published var graph = SerialGraph()
    @Published var showImporter = false {
        didSet {
            if showImporter {
                stopPreviewPlayback()
            }
        }
    }
    @Published var dropTargeted = false
    @Published var lastExportNote: String = ""
    @Published var lastImportNote: String = ""
    @Published var pickingNeutral: Bool = false {
        didSet {
            if pickingNeutral {
                stopPreviewPlayback()
            }
        }
    }
    @Published var showSettings = false
    /// 写出说明。确认后才走 processLockedClips 的选文件夹。不是偏好设置。
    @Published var showDeliverSheet = false
    /// Which sheet is on screen. Cleared only after dismiss, so the content
    /// does not flip from the write sheet to preferences while it is closing.
    @Published var activeSheet: WorkspaceSheet?
    /// Deliver sheet sets this; ProcessLockedBar starts the existing folder panel.
    @Published var deliverSheetConfirmed = false
    /// Write sheet has closed and the folder panel is not up yet, or is up.
    /// The top bar says so, so a quiet gap is not a missed click. Cancel writes nothing.
    @Published var openingExportFolder = false
    @Published var isWritingDeliverables = false
    /// Clip whose proxy is being written. Nil when idle. Does not move selection.
    @Published var writingClipID: UUID?
    /// Same busy flag. Preview progress + inspector / IDT lock read this.
    var isExporting: Bool { isWritingDeliverables }
    /// Completed `{stem}_ACES2065-1_proxy` folders from the last successful write.
    /// Empty while writing, after cancel, or when nothing was written.
    @Published var lastExportRevealURLs: [URL] = []
    /// Tiny-disk / test mock. When set, dest free-space check uses this
    /// instead of the volume. Nil reads the real volume.
    var destFreeBytesOverride: Int64? = nil
    /// Movie slider index. Stills stay 0. Missing fps/duration does not invent a range.
    @Published var previewFrameIndex: Int = 0
    /// Monitor compare. The picture drops exposure and white balance.
    /// Inspector numbers and the write keep the shared set.
    @Published var previewShowsGradeBefore = false
    /// Last index (duration × metadata fps − 1). Nil: still, or no clip, or fail.
    @Published var previewScrubLastFrame: Int? = nil
    /// 「读不到帧率，未核对」 / 「读不到时长，未核对」. No slider. No 24/30 guess.
    @Published var previewScrubFail: String? = nil
    /// Metadata fps captured with the scrub range. Nil when there is nothing to play.
    /// Playback uses this. It does not probe again, and it does not invent a rate.
    @Published var previewPlaybackFPS: Double? = nil
    /// Preview transport. Picture only. Stops at the last frame. Not a write.
    @Published var isPreviewPlaying = false
    private var previewPlayTimer: Timer?
    private var previewScrubClipID: UUID?

    let preview = PreviewEngine()
    /// Bin / inspector pictures. Not the monitor cache, and not the write.
    let posters = ClipPosterCache()
    let settings = AppSettings.shared
    /// User edited exposure / WB, or a camera reading already filled the one shared set.
    /// Selection must not replace that set. Write uses the same set for every locked clip.
    private var sharedGradeTouched = false
    /// Prior shared exposure / white-balance sets. The newest is last.
    private var gradeUndoStack: [SharedGradeSnapshot] = []
    private var gradeRedoStack: [SharedGradeSnapshot] = []
    /// Non-nil while a slider drag is one undo step. Mouse-up clears it.
    private var openGradeStroke: SharedGradeStroke?
    private static let gradeUndoLimit = 40
    private let writeCancel = WriteCancelFlag()
    private var lastProgressUptime: TimeInterval = 0

    init() {
        graph.odt = settings.defaultPreviewODT
    }

    deinit {
        previewPlayTimer?.invalidate()
    }

    var selectedClip: Clip? {
        clips.first { $0.id == selectedID }
    }

    /// Monitor menu. Off has no picture transform; the menu stays on Rec.709
    /// until the user picks HLG or PQ. Does not change the saved default.
    var monitorPreviewODT: ODTMode {
        switch graph.odt {
        case .hlg: return .hlg
        case .pq: return .pq
        case .rec709, .off: return .rec709
        }
    }

    /// Rows the sidebar is showing. Arrow keys move inside this list.
    var visibleClips: [Clip] {
        switch clipListFilter {
        case .all:
            return clips
        case .pending:
            return clips.filter { !$0.hasLockedPair }
        case .locked:
            return clips.filter(\.hasLockedPair)
        }
    }

    /// Factory knobs: nothing to protect yet. The next selected clip may fill them
    /// from its camera reading. After that, or after any edit, selection must not.
    private var sharedGradeIsFactory: Bool {
        !sharedGradeTouched
            && graph.exposureEnabled
            && graph.exposureStops == 0
            && !graph.wbEnabled
            && graph.wbCCT == nil
            && graph.wbSource == .unknown
            && abs(graph.wbTint) < 1e-9
    }

    private func touchSharedGrade() {
        sharedGradeTouched = true
    }

    /// Turn the compare on only after a paired IDT is locked.
    /// Turn it off whenever a clip is selected. Sheets, write, and grey-card
    /// sampling keep the current picture.
    var canTogglePreviewGradeBefore: Bool {
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !pickingNeutral
        else { return false }
        if previewShowsGradeBefore { return selectedClip != nil }
        return selectedClip?.hasLockedPair == true
    }

    /// Picture for the monitor. Compare copies the shared set with exposure
    /// and white balance off. Does not replace `graph`.
    var graphForPreview: SerialGraph {
        guard previewShowsGradeBefore else { return graph }
        var copy = graph
        copy.exposureEnabled = false
        copy.wbEnabled = false
        return copy
    }

    /// 看调色前 / 回到调色. Same frame. Does not edit the shared set.
    func togglePreviewGradeBefore() {
        guard canTogglePreviewGradeBefore else { return }
        previewShowsGradeBefore.toggle()
        preview.invalidateWBODT()
        refreshPreview()
    }

    func refreshPreview() {
        // Selected clip (or grade) changed. PreviewEngine keeps only this
        // clip's preview source/linear/graded and drops a stale first-frame
        // if selection already moved on. Write path is not this cache.
        if selectedID != previewScrubClipID {
            stopPreviewPlayback()
            resetPreviewScrub()
        }
        preview.refresh(clip: selectedClip, graph: graphForPreview, frameIndex: previewFrameIndex)
    }

    /// ODT / scrub: do not invalidate graded linear (IDT+exposure+WB).
    func refreshODTOnly() {
        preview.refreshODT(clip: selectedClip, graph: graphForPreview, frameIndex: previewFrameIndex)
    }

    /// Slider: first…last from duration × metadata fps. No 24/30 guess.
    /// Cache hit for that frame: ODT only. Miss: decode that frame only.
    /// A drag or a click stops playback. The play timer passes keepPlaying.
    func setPreviewFrame(_ index: Int, keepPlaying: Bool = false) {
        if !keepPlaying {
            stopPreviewPlayback()
        }
        guard let last = previewScrubLastFrame else { return }
        let next = max(0, min(index, last))
        previewFrameIndex = next
        preview.scrub(clip: selectedClip, graph: graphForPreview, frameIndex: next)
    }

    /// Stills: no slider. Movies: duration × metadata fps. Missing → Chinese fail.
    func resetPreviewScrub() {
        previewScrubClipID = selectedID
        previewFrameIndex = 0
        previewScrubLastFrame = nil
        previewScrubFail = nil
        previewPlaybackFPS = nil
        guard let clip = selectedClip else { return }
        if MediaFormat.probe(url: clip.url).kind == .still {
            return
        }
        let ext = MediaFormat.extent(url: clip.url)
        let (count, err) = Self.expectedSourceFrames(ext)
        if let err {
            // missingFpsChip / missingDurationChip
            previewScrubFail = err
            return
        }
        if let count {
            previewScrubLastFrame = max(0, count - 1)
            if let fps = ext.fps, fps.isFinite, fps > 0 {
                previewPlaybackFPS = fps
            }
        }
    }

    /// HDR layer could not enable EDR. Empty right pane. Never fall back to 709.
    func failClosedHDRPreviewLayer() {
        guard graph.odt.isHDR else { return }
        preview.failClosedHDRPreview()
    }

    var pendingPickerCount: Int {
        clips.filter { $0.needsUserPicker || $0.idt == nil }.count
    }

    /// Clock beside the frame count. Same index and the metadata rate already
    /// used for playback. Nil when that rate was not read. Not a write input.
    var previewClockText: String? {
        Clip.previewClock(frameIndex: previewFrameIndex, fps: previewPlaybackFPS)
    }

    /// Clock of the last scrub frame. Same rate. Not the source duration.
    var previewClockEndText: String? {
        guard let last = previewScrubLastFrame else { return nil }
        return Clip.previewClock(frameIndex: last, fps: previewPlaybackFPS)
    }

    /// Movie scrub range exists, and no sheet or write is up.
    /// Stills and missing fps/duration stay out: no invented frame count.
    var canStepPreviewFrame: Bool {
        previewScrubLastFrame != nil
            && !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
    }

    var canStepPreviewBackward: Bool {
        canStepPreviewFrame && previewFrameIndex > 0
    }

    var canStepPreviewForward: Bool {
        guard canStepPreviewFrame, let last = previewScrubLastFrame else { return false }
        return previewFrameIndex < last
    }

    /// One preview frame. Same index as the slider. Stops at the ends.
    /// Does not change exposure, white balance, or the write.
    @discardableResult
    func stepPreviewFrame(_ delta: Int) -> Bool {
        guard canStepPreviewFrame, delta != 0 else { return false }
        stopPreviewPlayback()
        if delta < 0 {
            guard previewFrameIndex > 0 else { return true }
            setPreviewFrame(previewFrameIndex - 1)
        } else {
            guard let last = previewScrubLastFrame, previewFrameIndex < last else { return true }
            setPreviewFrame(previewFrameIndex + 1)
        }
        return true
    }

    /// Home / 回到开头. Already on frame 0 still stops playback.
    var canJumpPreviewToStart: Bool {
        canStepPreviewFrame && previewFrameIndex > 0
    }

    /// End / 到结尾. Already on the last frame stays put.
    var canJumpPreviewToEnd: Bool {
        canStepPreviewForward
    }

    /// First preview frame. Stops playback. Does not change the shared grade.
    @discardableResult
    func jumpPreviewToStart() -> Bool {
        guard canStepPreviewFrame else { return false }
        if previewFrameIndex == 0 {
            stopPreviewPlayback()
            return true
        }
        setPreviewFrame(0)
        return true
    }

    /// Last preview frame from the existing scrub range. Stops playback.
    /// Does not change the shared grade, and does not invent a frame count.
    @discardableResult
    func jumpPreviewToEnd() -> Bool {
        guard canStepPreviewFrame, let last = previewScrubLastFrame else { return false }
        if previewFrameIndex >= last {
            stopPreviewPlayback()
            return true
        }
        setPreviewFrame(last)
        return true
    }

    /// Second-step buttons exist only when this clip's rate was read.
    var showsPreviewSecondStep: Bool {
        Clip.previewSecondFrameCount(fps: previewPlaybackFPS) != nil
    }

    /// Same window gates as a one-frame step, plus a real rate.
    var canStepPreviewBySecond: Bool {
        canStepPreviewFrame && showsPreviewSecondStep
    }

    var canStepPreviewSecondBackward: Bool {
        canStepPreviewBySecond && previewFrameIndex > 0
    }

    var canStepPreviewSecondForward: Bool {
        guard canStepPreviewBySecond, let last = previewScrubLastFrame else { return false }
        return previewFrameIndex < last
    }

    /// About one second, in this clip's frames. Stops at the ends.
    /// Does not change exposure, white balance, or the write.
    @discardableResult
    func stepPreviewBySecond(_ direction: Int) -> Bool {
        guard canStepPreviewBySecond, direction != 0,
              let frames = Clip.previewSecondFrameCount(fps: previewPlaybackFPS),
              let last = previewScrubLastFrame else { return false }
        stopPreviewPlayback()
        let delta = direction < 0 ? -frames : frames
        let next = min(max(previewFrameIndex + delta, 0), last)
        if next == previewFrameIndex { return true }
        setPreviewFrame(next)
        return true
    }

    /// Play only when this clip already has a scrub range and a metadata fps.
    /// Stills, missing rate, the last frame, grey-card pick, sheets, and write stay stopped.
    var canPlayPreview: Bool {
        guard canStepPreviewForward, !pickingNeutral else { return false }
        guard let fps = previewPlaybackFPS, fps.isFinite, fps > 0 else { return false }
        return true
    }

    /// Space and the scrub button. Pause is allowed until a sheet or a write takes the window.
    var canTogglePreviewPlayback: Bool {
        if isPreviewPlaying {
            return canStepPreviewFrame && !pickingNeutral
        }
        return canPlayPreview
    }

    /// Start or stop preview playback. Does not move exposure, white balance, or the write.
    /// At the last frame this does not jump back to the first frame.
    @discardableResult
    func togglePreviewPlayback() -> Bool {
        if isPreviewPlaying {
            stopPreviewPlayback()
            return true
        }
        return startPreviewPlayback()
    }

    /// One frame per tick, at the metadata rate. Waits out a preview that is still drawing.
    /// Does not skip ahead, and does not invent a frame rate.
    @discardableResult
    func startPreviewPlayback() -> Bool {
        guard canPlayPreview, let fps = previewPlaybackFPS else { return false }
        stopPreviewPlayback()
        isPreviewPlaying = true
        // Cap the timer so a wild metadata value cannot spin. Still one frame each fire.
        let interval = 1.0 / min(fps, 120)
        let timer = Timer(timeInterval: interval, repeats: true) { [weak self] _ in
            self?.advancePreviewPlayback()
        }
        RunLoop.main.add(timer, forMode: .common)
        previewPlayTimer = timer
        return true
    }

    func stopPreviewPlayback() {
        previewPlayTimer?.invalidate()
        previewPlayTimer = nil
        if isPreviewPlaying {
            isPreviewPlaying = false
        }
    }

    private func advancePreviewPlayback() {
        guard isPreviewPlaying else { return }
        guard canStepPreviewForward, !pickingNeutral else {
            stopPreviewPlayback()
            return
        }
        if preview.isWorking { return }
        setPreviewFrame(previewFrameIndex + 1, keepPlaying: true)
    }

    var lockedClips: [Clip] { clips.filter(\.hasLockedPair) }
    var lockedClipCount: Int { lockedClips.count }
    var pendingClipCount: Int { clips.filter { !$0.hasLockedPair }.count }

    /// 「N 条已锁定 / M 条待选」
    var lockStatusText: String {
        "\(lockedClipCount) 条已锁定 / \(pendingClipCount) 条待选"
    }

    /// 写出说明上的这一套。和检查器同一套曝光、白平衡，套到已锁定素材。
    /// 不另记数字，也不在色温空着时填 5600。
    var sharedGradeWriteLine: String {
        let exposure: String
        if graph.exposureEnabled {
            exposure = String(format: "曝光 %+.2f 档", graph.exposureStops)
        } else {
            exposure = "曝光关"
        }
        let wb: String
        if !graph.wbEnabled {
            wb = "白平衡关"
        } else if let cct = graph.wbCCT {
            let tint = String(format: "%+.1f", graph.wbTint)
            wb = "\(graph.wbSource.title) \(Int(cct.rounded())) K · 绿品 \(tint)"
        } else {
            wb = graph.wbSource.title
        }
        return "这一套会套到已锁定素材：\(exposure) · \(wb)"
    }

    /// 主路径现在走到哪。顶栏一行，不另开一页。
    var loopStepHint: String {
        if isWritingDeliverables { return "正在写出代理" }
        if openingExportFolder { return "正在打开选文件夹" }
        if clips.isEmpty { return "先拖入或点添加" }
        if !showsProcessLockedButton { return "在右侧检查器选成对 IDT" }
        if canRevealLastExport { return "已写出代理。可再调色，或在状态栏打开 Finder" }
        if pendingClipCount > 0 { return "可调色并写出；待选仍要选 IDT" }
        return "可调色，再点写出"
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
        guard let clip = selectedClip else { return "没有素材" }
        return clip.processSkipReason
    }

    /// Batch: write one ACES2065-1 AP0 proxy EXR sequence per locked clip
    /// and the session Resolve package (XML / DCTL / cube / README).
    /// Unlocked stay listed with a Chinese reason. After the batch,
    /// lastExportNote is 「N 条已写出代理 / M 条待选跳过 / K 条失败」.
    /// Never guess an IDT. 不是一步还原. One process entry point.
    /// Mixed bins are allowed. 整段代理，代理精度.
    func processLockedClips() {
        if isWritingDeliverables {
            openingExportFolder = false
            return
        }
        let locked = clips.filter(\.hasLockedPair)
        let skipped = clips.filter { !$0.hasLockedPair }
        guard !locked.isEmpty else {
            openingExportFolder = false
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
        let format = settings.exportFormat
        let estimate = Self.estimateLockedProxyBytes(urls: locked.map(\.url), format: format)
        // Default ProRes 422 HQ; EXR remains advanced. The size note follows that choice.
        panel.message = Self.folderPickerMessage(format: format) + estimate.pickerSuffix
        if let remembered = settings.lastExportDirectoryURL {
            panel.directoryURL = remembered
        }
        openingExportFolder = true
        let finish: (NSApplication.ModalResponse) -> Void = { [weak self] response in
            guard let self else { return }
            self.openingExportFolder = false
            guard response == .OK, let dest = panel.url else { return }
            _ = dest.startAccessingSecurityScopedResource()
            self.settings.rememberExportDirectory(dest)
            self.writeLockedDeliverables(locked: locked, skippedCount: skipped.count, dest: dest)
        }
        // Stick the panel to this window. A free-floating panel after the
        // write sheet closes is easy to miss, and then nothing is written.
        if let window = Self.exportFolderHostWindow() {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate()
            panel.beginSheetModal(for: window, completionHandler: finish)
        } else {
            panel.begin(completionHandler: finish)
        }
    }

    /// The content window, not a sheet. Nil when AppKit has no host yet.
    static func exportFolderHostWindow() -> NSWindow? {
        let hosts = NSApp.windows.filter { window in
            window.isVisible && window.canBecomeMain && !window.isSheet && window.level == .normal
        }
        if let key = NSApp.keyWindow, hosts.contains(where: { $0 === key }) {
            return key
        }
        if let main = NSApp.mainWindow, hosts.contains(where: { $0 === main }) {
            return main
        }
        return hosts.first
    }

    /// Writes ACES2065-1 AP0 proxy EXR sequences for locked clips only.
    /// After verified sequences, writes the session Resolve package.
    /// Incomplete XML/DCTL/cube/README is 「达芬奇包不完整，未写出」;
    /// the half package and those `_proxy` folders are removed.
    /// Empty `_ACES2065-1_proxy` / 0 frames fail closed (帧数对不上 / 解码失败).
    func writeLockedDeliverables(locked: [Clip], skippedCount: Int, dest: URL) {
        stopPreviewPlayback()
        let exportFormat = settings.exportFormat
        let estimate = Self.estimateLockedProxyBytes(urls: locked.map(\.url), format: exportFormat)
        if let free = destFreeBytesOverride ?? Self.destVolumeFreeBytes(dest),
           free < estimate.neededWithMargin {
            lastExportRevealURLs = []
            lastExportNote = Self.batchSummaryText(
                wrote: 0,
                skipped: skippedCount,
                failed: locked.count,
                reasons: [Self.diskShortStatus]
            )
            return
        }
        let graphCopy = graph
        let clipTotal = locked.count
        writeCancel.reset()
        lastProgressUptime = 0
        lastExportRevealURLs = []
        clearExportChips(for: locked)
        isWritingDeliverables = true
        writingClipID = locked.first?.id
        lastExportNote = Self.exportProgressText(
            clipIndex: 1,
            clipTotal: clipTotal,
            clipName: locked.first?.filename
        )
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
                let frameTotal = Self.knownWriteFrameTotal(for: clip)
                self.publishExportProgress(
                    Self.exportProgressText(
                        clipIndex: clipIndex,
                        clipTotal: clipTotal,
                        clipName: clip.filename
                    ),
                    clipID: clip.id,
                    force: true
                )
                do {
                    let url: URL
                    if exportFormat == .prores422HQ {
                        url = try self.exportLockedProRes(
                            clip: clip,
                            graph: graphCopy,
                            dest: dest
                        ) { frame in
                            self.publishExportProgress(
                                Self.exportProgressText(
                                    clipIndex: clipIndex,
                                    clipTotal: clipTotal,
                                    frame: frame,
                                    frameTotal: frameTotal,
                                    clipName: clip.filename
                                ),
                                clipID: clip.id
                            )
                        }
                    } else {
                        url = try self.exportLockedEXR(
                            clip: clip,
                            graph: graphCopy,
                            dest: dest
                        ) { frame in
                            self.publishExportProgress(
                                Self.exportProgressText(
                                    clipIndex: clipIndex,
                                    clipTotal: clipTotal,
                                    frame: frame,
                                    frameTotal: frameTotal,
                                    clipName: clip.filename
                                ),
                                clipID: clip.id
                            )
                        }
                    }
                    written.append(url)
                    self.setExportChip(
                        clipID: clip.id,
                        Self.wroteProxyChip,
                        writtenName: url.lastPathComponent,
                        writtenPath: url.path
                    )
                } catch is LockedWriteCancel {
                    cancelled = true
                    break
                } catch {
                    let chip = Self.shortExportChip(for: error)
                    errors.append("\(clip.filename)：\(chip)")
                    self.setExportChip(clipID: clip.id, chip)
                }
            }
            if !cancelled && !written.isEmpty {
                do {
                    _ = try ResolveExporter.export(
                        to: dest,
                        clips: locked,
                        includeWBNode: graphCopy.wbEnabled,
                        cct: graphCopy.wbCCT,
                        tint: graphCopy.wbTint,
                        catCCT: graphCopy.effectiveWBCCT,
                        useEffectiveCAT: true,
                        srcCCT: graphCopy.effectiveSrcCCT,
                        srcTint: graphCopy.asShotTint,
                        odtEnabled: graphCopy.odtEnabled,
                        exposureStops: graphCopy.exposureStops,
                        exposureEnabled: graphCopy.exposureEnabled
                    )
                    try ResolveExporter.verifyResolveBundle(at: dest)
            } catch {
                ResolveExporter.removeIncompleteResolveBundle(at: dest)
                let chip = Self.resolveIncompleteChip
                let writtenPaths = Set(written.map { $0.standardizedFileURL.path })
                for clip in locked {
                    let seq = ResolveExporter.deliverableSequenceDirectory(for: clip, in: dest)
                    let mov = ProResWriter.deliverableURL(for: clip, in: dest)
                    let hitSeq = writtenPaths.contains(seq.standardizedFileURL.path)
                    let hitMov = writtenPaths.contains(mov.standardizedFileURL.path)
                    guard hitSeq || hitMov else { continue }
                    if hitSeq {
                        ResolveExporter.removeFailedProxySequence(at: seq)
                    }
                    if hitMov {
                        Self.removeProResDeliverable(mov)
                    }
                    self.setExportChip(clipID: clip.id, chip)
                    errors.append("\(clip.filename)：\(chip)")
                }
                written.removeAll()
            }
            }
            let wrote = written.count
            let failed = locked.count - wrote
            var reasons = errors
            if cancelled {
                reasons.append(Self.cancelledNote)
            }
            // Deleted half-folder is not a success. Do not reveal it.
            let reveal: [URL] = (cancelled || written.isEmpty) ? [] : written
            let destForNote: URL? = (cancelled || written.isEmpty) ? nil : dest
            let note = Self.batchSummaryText(
                wrote: wrote,
                skipped: skippedCount,
                failed: failed,
                reasons: reasons,
                dest: destForNote
            )
            DispatchQueue.main.async {
                self.lastExportNote = note
                self.lastExportRevealURLs = reveal
                self.writingClipID = nil
                self.isWritingDeliverables = false
            }
        }
    }

    /// 「N 条已写出代理 / M 条待选跳过 / K 条失败」 plus 失败原因.
    /// Existing Chinese chips only. Does not invent fps. No dest-disk frame guess.
    static func batchSummaryText(
        wrote: Int,
        skipped: Int,
        failed: Int,
        reasons: [String] = [],
        dest: URL? = nil
    ) -> String {
        var note = "\(wrote) 条已写出代理 / \(skipped) 条待选跳过 / \(failed) 条失败"
        if !reasons.isEmpty {
            note += "。\(failedBucket) " + reasons.joined(separator: " ")
        }
        note += "。整段代理，代理精度。已实现（未验证）。"
        if let dest, wrote > 0 {
            note += " " + shortExportPath(dest)
        }
        return note
    }

    /// One ACES2065-1 AP0 proxy EXR sequence. Source Y′CbCr → float + PreviewColor grade; no ODT.
    /// After write, count EXRs against duration × metadata fps only.
    /// Empty folder / 0 frames / mismatch / missing timing is a Chinese failure;
    /// the folder is removed so it is not 已写出代理.
    /// Not ACEScct. Not a Rec.709 movie. 整段代理，代理精度.
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
                    NSLocalizedDescriptionKey: Self.decodeFailedChip
                ])
            }
            try Self.verifyLockedProxySequence(clip: clip, seqDir: seqDir)
        } catch {
            ResolveExporter.removeFailedProxySequence(at: seqDir)
            throw error
        }
        return seqDir
    }

    /// Same primary button becomes 取消 while writing. Not a second process button.

    /// Rec.709 preview ProRes 422 HQ movie. Same grade as EXR, then ODT.
    /// Editor-ready proxy. 整段代理，代理精度.
    func exportLockedProRes(
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
        let outURL = ProResWriter.deliverableURL(for: clip, in: dest)
        if FileManager.default.fileExists(atPath: outURL.path) {
            try FileManager.default.removeItem(at: outURL)
        }
        let fps = Self.metadataFPS(for: clip) ?? Self.conservativeFPS
        // Writer calls stay on one queue. Frames are not kept for the whole clip.
        let encodeQueue = DispatchQueue(label: "logbridge.prores.encode")
        let box = ProResWriter.SessionBox()
        do {
            let count = try preview.exportGradedAP0Sequence(clip: clip, graph: graph) { _, rgb, w, h in
                if self.writeCancel.isRequested {
                    throw LockedWriteCancel()
                }
                var display = rgb
                PreviewColor.applyODT(rgb: &display)
                var written = 0
                try encodeQueue.sync {
                    if box.session == nil {
                        box.session = try ProResWriter.EncodeSession(width: w, height: h, fps: fps, to: outURL)
                    }
                    try box.session?.append(rgb: display)
                    written = box.session?.writtenFrames ?? 0
                }
                onFrame?(written)
            }
            if count < 1 || box.session == nil {
                throw NSError(domain: "LogBridge", code: 2, userInfo: [
                    NSLocalizedDescriptionKey: Self.decodeFailedChip
                ])
            }
            try encodeQueue.sync {
                try box.session?.finish()
                box.session = nil
            }
        } catch {
            encodeQueue.sync {
                box.session?.cancel()
                box.session = nil
            }
            Self.removeProResDeliverable(outURL)
            throw error
        }
        return outURL
    }

    func cancelLockedDeliverables() {
        writeCancel.request()
    }

    /// Escape while writing: same cancel as the 取消 control.
    /// Idle Escape does nothing (does not clear selection, does not quit).
    /// Sheets / alerts / settings keep Escape.
    @discardableResult
    func cancelWritingFromEscape() -> Bool {
        guard isWritingDeliverables else { return false }
        guard !showSettings, !showImporter, !showDeliverSheet else { return false }
        cancelLockedDeliverables()
        return true
    }

    /// 「写出代理 2/5 · 文件名 · 第 120 / 共 240 帧」.
    /// The name is the source file. Frame total only when this clip already has one.
    /// A still is 1. Missing rate or duration omits the total. Does not invent a rate.
    static func exportProgressText(
        clipIndex: Int,
        clipTotal: Int,
        frame: Int? = nil,
        frameTotal: Int? = nil,
        clipName: String? = nil
    ) -> String {
        var note = "写出代理 \(clipIndex)/\(clipTotal)"
        if let clipName {
            let trimmed = clipName.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty {
                note += " · \(trimmed)"
            }
        }
        if let frame {
            if let frameTotal, frameTotal > 0 {
                note += " · 第 \(frame) / 共 \(frameTotal) 帧"
            } else {
                note += " · 第 \(frame) 帧"
            }
        }
        return note
    }

    /// Frames this write can name. A still is 1. A movie is duration × metadata fps.
    /// Missing rate or duration returns nil. Not the disk-estimate fallback.
    static func knownWriteFrameTotal(for clip: Clip) -> Int? {
        if clip.isStill { return 1 }
        let ext = MediaExtent(
            frameCount: nil,
            durationSeconds: clip.durationSeconds,
            fps: clip.mediaFPS,
            width: clip.pixelWidth,
            height: clip.pixelHeight
        )
        let (count, err) = expectedSourceFrames(ext)
        if err != nil { return nil }
        guard let count, count > 0 else { return nil }
        return count
    }

    /// Cancelled batch. 已取消 + honesty. Partial output is 未完成.
    static func cancelledExportNote(processed: Int, skipped: Int) -> String {
        "处理已锁定片段 — 已取消。\(processed) 条已处理 / \(skipped) 条已跳过（先选择 Log 与色域 / 先选择成对 IDT）。整段代理，代理精度。已实现（未验证）。"
    }

    /// Uncompressed half RGB (3 × 2). Matches color/batch.py. EXR path only.
    static let bytesPerEXRPixel: Int64 = 6
    /// Planning figure for ProRes 422 HQ. Not a measured bitrate. Matches color/export_format.py.
    static let bytesPerProResHQPixel: Int64 = 1
    static let conservativeFPS = 24.0

    /// Metadata fps when present. Never invent; callers may fall back to conservativeFPS for ProRes encode only.
    static func metadataFPS(for clip: Clip) -> Double? {
        let ext = MediaFormat.extent(url: clip.url)
        guard let f = ext.fps, f.isFinite, f > 0 else { return nil }
        return f
    }
    static let conservativeSeconds = 60.0
    static let conservativeWidth = 3840
    static let conservativeHeight = 2160
    static let diskShortStatus = "磁盘空间不足，未写出"
    static let diskEstimateAssumption = "未压缩浮点图"
    static let diskEstimateAssumptionProRes = "ProRes 422 HQ，按每像素 1 字节估算"

    /// Picker copy follows the format about to be written.
    static func folderPickerMessage(format: ExportFormat) -> String {
        switch format {
        case .prores422HQ:
            return UICopy.FOLDER_PICKER_MESSAGE_UI
        case .exrACES2065:
            return UICopy.FOLDER_PICKER_MESSAGE_EXR
        }
    }

    /// Drop a ProRes proxy this batch just wrote. Does not touch other movies.
    static func removeProResDeliverable(_ url: URL) {
        guard url.lastPathComponent.hasSuffix(ProResWriter.proresSuffix) else { return }
        try? FileManager.default.removeItem(at: url)
    }
    static let cancelledNote = "已取消"
    static let skippedBucket = "待选跳过"
    static let failedBucket = "失败原因"

    static func formatProxyBytes(_ n: Int64) -> String {
        let v = max(Int64(0), n)
        if v >= 1_000_000_000 {
            return String(format: "%.1f GB", Double(v) / 1_000_000_000.0)
        }
        if v >= 1_000_000 {
            return String(format: "%.0f MB", Double(v) / 1_000_000.0)
        }
        if v >= 1000 {
            return String(format: "%.0f KB", Double(v) / 1000.0)
        }
        return "\(v) B"
    }

    static func estimatedFrameCount(_ ext: MediaExtent) -> (Int, String) {
        if let n = ext.frameCount, n > 0 { return (n, "known") }
        if let duration = ext.durationSeconds, duration > 0, let fps = ext.fps, fps > 0 {
            return (max(1, Int((duration * fps).rounded(.up))), "duration_fps")
        }
        if let duration = ext.durationSeconds, duration > 0 {
            return (max(1, Int((duration * conservativeFPS).rounded(.up))), "guess")
        }
        if let fps = ext.fps, fps > 0 {
            return (max(1, Int((conservativeSeconds * fps).rounded(.up))), "guess")
        }
        return (max(1, Int((conservativeSeconds * conservativeFPS).rounded(.up))), "guess")
    }

    static func estimatedPixelCount(_ ext: MediaExtent) -> Int {
        if let w = ext.width, let h = ext.height, w > 0, h > 0 { return w * h }
        return conservativeWidth * conservativeHeight
    }

    /// Locked clips only. Pending URLs are not passed in.
    /// ProRes uses 1 byte / pixel. EXR keeps 6. The note says which.
    static func estimateLockedProxyBytes(urls: [URL], format: ExportFormat) -> ProxyDiskEstimate {
        let bytesPerPixel = format == .prores422HQ ? bytesPerProResHQPixel : bytesPerEXRPixel
        let assumption = format == .prores422HQ ? diskEstimateAssumptionProRes : diskEstimateAssumption
        var total: Int64 = 0
        var usedFrameGuess = false
        var usedDurationFps = false
        for url in urls {
            let ext = MediaFormat.extent(url: url)
            let (frames, frameSrc) = estimatedFrameCount(ext)
            let pixels = estimatedPixelCount(ext)
            total += Int64(frames) * Int64(pixels) * bytesPerPixel
            if frameSrc == "guess" { usedFrameGuess = true }
            if frameSrc == "duration_fps" { usedDurationFps = true }
        }
        return ProxyDiskEstimate(
            bytes: total,
            usedFrameGuess: usedFrameGuess,
            usedDurationFps: usedDurationFps,
            assumption: assumption
        )
    }

    /// Size line for the write sheet. Same figure the folder panel and the disk check use.
    var deliverDiskNote: String {
        let estimate = Self.estimateLockedProxyBytes(
            urls: lockedClips.map(\.url),
            format: settings.exportFormat
        )
        return "占用估算：\(estimate.note)。空间不够会停在磁盘空间不足，未写出。"
    }

    static func destVolumeFreeBytes(_ dest: URL) -> Int64? {
        let keys: Set<URLResourceKey> = [
            .volumeAvailableCapacityForImportantUsageKey,
            .volumeAvailableCapacityKey
        ]
        guard let values = try? dest.resourceValues(forKeys: keys) else { return nil }
        if let important = values.volumeAvailableCapacityForImportantUsage, important >= 0 {
            return important
        }
        if let cap = values.volumeAvailableCapacity {
            return Int64(cap)
        }
        return nil
    }

    /// 「磁盘空间不足，未写出」 + honesty. Did not write. 不写已经测准.
    static func diskShortExportNote(estimate: ProxyDiskEstimate) -> String {
        "\(diskShortStatus)。\(estimate.note)。整段代理，代理精度。"
    }

    /// Locked row after a proxy sequence write. Not a finished picture.
    static let wroteProxyChip = "已写出代理"
    static let decodeFailedChip = "解码失败"
    static let writeFailedChip = "写出失败"
    static let stubChip = "未实现"
    static let emptyRGBChip = "RGB 是空的，未写出"
    static let frameMismatchChip = "帧数对不上"
    static let missingFpsChip = "读不到帧率，未核对"
    static let missingDurationChip = "读不到时长，未核对"
    static let missingYCbCrTagsChip = "读不出片源色彩标签，没法写出"
    // Python copy-lock (test_batch_locked): 无法读取片源 Y′CbCr 矩阵/范围，未写出
    static let writeOversizeChip = "片源边长超过 16384，未写出"
    static let resolveIncompleteChip = "达芬奇包不完整，未写出"

    /// Short Chinese sidebar / status error. Failed write is not silent.
    /// Keep the real class (格式不接 / 解码失败 / 读不到元数据). Do not collapse to 解析失败.
    static func shortExportChip(for error: Error) -> String {
        if error is LockedWriteCancel { return writeFailedChip }
        let desc = error.localizedDescription
        if let kept = preservedFailureNote(desc) { return kept }
        if desc == "no IDT" || desc == "IDT is required" { return "先选择成对 IDT" }
        if desc == "empty RGB buffer" { return emptyRGBChip }
        let lower = desc.lowercased()
        if lower.contains("decode") || lower.contains("grade") || lower.contains("parse")
            || desc.contains("解析失败") {
            return Self.decodeFailedChip
        }
        return writeFailedChip
    }

    /// Known Chinese failure notes stay as-is. Never rewrite them to 解析失败 / 写出失败.
    static func preservedFailureNote(_ desc: String) -> String? {
        if desc.hasPrefix("先选择") { return desc }
        if desc.contains("读不到元数据") { return desc }
        if desc == frameMismatchChip || desc == missingFpsChip || desc == missingDurationChip
            || desc == missingYCbCrTagsChip || desc == writeOversizeChip
            || desc == Self.decodeFailedChip || desc == resolveIncompleteChip
            || desc == stubChip || desc == emptyRGBChip {
            return desc
        }
        if desc == MediaFormat.noteCameraRaw || desc == MediaFormat.noteARRIMxf
            || desc == MediaFormat.noteMxfNoTrack
            || desc == MediaFormat.noteUnknownCodec {
            return desc
        }
        if desc.contains("不接") || desc.contains("暂不能处理") || desc.contains("无法读取") {
            return desc
        }
        return nil
    }

    /// Expected EXR count: duration × metadata fps. Never invent a frame rate.
    /// A still (MediaFormat kind `.still`: tif / tiff / dpx / exr) with exactly
    /// one written frame expects 1. A still sequence (written > 1) keeps
    /// duration × fps. Missing fps / duration fail closed.
    static func expectedSourceFrames(
        _ ext: MediaExtent,
        clipURL: URL? = nil,
        written: Int? = nil
    ) -> (Int?, String?) {
        if written == 1, let clipURL,
           MediaFormat.probe(url: clipURL).kind == .still {
            return (1, nil)
        }
        let duration: Double? = {
            guard let d = ext.durationSeconds, d.isFinite, d > 0 else { return nil }
            return d
        }()
        let fps: Double? = {
            guard let f = ext.fps, f.isFinite, f > 0 else { return nil }
            return f
        }()
        if let duration, let fps {
            return (max(1, Int((duration * fps).rounded(.up))), nil)
        }
        if fps == nil {
            return (nil, missingFpsChip)
        }
        return (nil, missingDurationChip)
    }

    /// How many ``.exr`` files are in the proxy folder. Missing folder → 0.
    static func countProxyEXRs(in seqDir: URL) -> Int {
        guard let items = try? FileManager.default.contentsOfDirectory(
            at: seqDir,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) else { return 0 }
        return items.filter { $0.pathExtension.lowercased() == "exr" }.count
    }

    /// Off-by-one: inclusive last frame on duration × fps. Empty is never a match.
    static func framesCountMatches(written: Int, expected: Int) -> Bool {
        if written < 1 || expected < 1 { return false }
        return abs(written - expected) <= 1
    }

    /// Post-write check. Throws a Chinese chip. Caller removes the folder.
    /// Empty `_ACES2065-1_proxy` (no EXRs / 0 frames) fails first as 帧数对不上.
    static func verifyLockedProxySequence(clip: Clip, seqDir: URL) throws {
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: seqDir.path, isDirectory: &isDir),
              isDir.boolValue else {
            throw NSError(domain: "LogBridge", code: 4, userInfo: [
                NSLocalizedDescriptionKey: frameMismatchChip
            ])
        }
        let written = countProxyEXRs(in: seqDir)
        if written < 1 {
            throw NSError(domain: "LogBridge", code: 4, userInfo: [
                NSLocalizedDescriptionKey: frameMismatchChip
            ])
        }
        let (expected, timingErr) = expectedSourceFrames(
            MediaFormat.extent(url: clip.url),
            clipURL: clip.url,
            written: written
        )
        if let timingErr {
            throw NSError(domain: "LogBridge", code: 4, userInfo: [
                NSLocalizedDescriptionKey: timingErr
            ])
        }
        guard let expected, framesCountMatches(written: written, expected: expected) else {
            throw NSError(domain: "LogBridge", code: 4, userInfo: [
                NSLocalizedDescriptionKey: frameMismatchChip
            ])
        }
    }

    /// Re-export clears the chip so a previous 已写出代理 does not linger.
    private func clearExportChips(for locked: [Clip]) {
        let ids = Set(locked.map(\.id))
        for i in clips.indices where ids.contains(clips[i].id) {
            clips[i].exportChip = nil
            clips[i].writtenDeliverableName = nil
            clips[i].writtenRevealPath = nil
        }
    }

    private func setExportChip(
        clipID: UUID,
        _ chip: String?,
        writtenName: String? = nil,
        writtenPath: String? = nil
    ) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let idx = self.clips.firstIndex(where: { $0.id == clipID }) else { return }
            self.clips[idx].exportChip = chip
            if chip == Self.wroteProxyChip {
                self.clips[idx].writtenDeliverableName = writtenName
                self.clips[idx].writtenRevealPath = writtenPath
            } else {
                self.clips[idx].writtenDeliverableName = nil
                self.clips[idx].writtenRevealPath = nil
            }
        }
    }

    /// Status dest path (short). Parent folder name, not a deliverable claim.
    static func shortExportPath(_ url: URL) -> String {
        url.lastPathComponent
    }

    static let revealInFinderLabel = "在 Finder 中显示"

    var canRevealLastExport: Bool { !lastExportRevealURLs.isEmpty }

    /// Finished batch note near the process bar. Not a second process button.
    var showsBatchSummary: Bool {
        !isWritingDeliverables && lastExportNote.contains("条已写出代理")
    }

    /// Opens completed `{stem}_ACES2065-1_proxy` folders. Skips missing paths.
    func revealLastExportInFinder() {
        let existing = lastExportRevealURLs.filter {
            FileManager.default.fileExists(atPath: $0.path)
        }
        guard !existing.isEmpty else { return }
        NSWorkspace.shared.activateFileViewerSelecting(existing)
    }

    /// Last dest + `{stem}_ACES2065-1_proxy`. Success chip only.
    /// Pending / failed / cancelled do not reveal. 未完成.
    static func clipSequenceRevealURL(for clip: Clip, dest: URL) -> URL? {
        guard clip.exportChip == wroteProxyChip else { return nil }
        return ResolveExporter.deliverableSequenceDirectory(for: clip, in: dest)
    }

    /// Last dest + `{stem}_Rec709_proxy.mov`. Success chip only.
    /// Pending / failed / cancelled do not reveal.
    static func clipProResRevealURL(for clip: Clip, dest: URL) -> URL? {
        guard clip.exportChip == wroteProxyChip else { return nil }
        return ProResWriter.deliverableURL(for: clip, in: dest)
    }

    /// Sidebar 「已写出代理」. Opens the file this write made.
    /// Default ProRes is the .mov. Advanced EXR is the proxy folder.
    /// A remembered path wins. Otherwise the last dest is checked for whichever file is there.
    /// Pending / failed / cancelled do not reveal. Does not invent a path.
    func revealClipExportInFinder(_ clip: Clip) {
        guard clip.exportChip == Self.wroteProxyChip else { return }
        if let path = clip.writtenRevealPath, FileManager.default.fileExists(atPath: path) {
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
            return
        }
        guard let dest = settings.lastExportDirectoryURL else { return }
        let prores = Self.clipProResRevealURL(for: clip, dest: dest)
        let sequence = Self.clipSequenceRevealURL(for: clip, dest: dest)
        let ordered: [URL?] = settings.exportFormat == .exrACES2065
            ? [sequence, prores]
            : [prores, sequence]
        guard let url = ordered.compactMap({ $0 }).first(where: {
            FileManager.default.fileExists(atPath: $0.path)
        }) else { return }
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    private func publishExportProgress(_ note: String, clipID: UUID? = nil, force: Bool = false) {
        let now = ProcessInfo.processInfo.systemUptime
        if !force && (now - lastProgressUptime) < 0.12 { return }
        lastProgressUptime = now
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.lastExportNote = note
            if let clipID {
                self.writingClipID = clipID
            }
        }
    }

    /// Primary action alias. Label is "处理已锁定片段" — 不是一步还原.
    func processSelected() {
        processLockedClips()
    }

    /// Same batch as processLockedClips. 不是一步还原. Not a second button.
    func applyGraph() {
        processLockedClips()
    }

    var odtPreviewTitle: String {
        // Real-Mac HDR pane: existing #53 chips, not new copy.
        if graph.odt.isHDR {
            if preview.status == "HDR 预览建不出" {
                return "HDR 预览建不出"
            }
            if preview.status == "屏幕无 EDR，预览被压到 SDR" {
                return "屏幕无 EDR，预览被压到 SDR"
            }
        }
        switch graph.odt {
        case .off:
            return "709 预览关"
        case .rec709:
            return "Rec.709 仅预览"
        case .hlg:
            return "HLG 仅预览（未匹配 709）"
        case .pq:
            return "PQ 仅预览（未匹配 709）"
        }
    }

    var odtPreviewCaption: String {
        // Hover: existing phrases only (#43 / #47 / #53). No new chip.
        if graph.odt.isHDR {
            if preview.status == "HDR 预览建不出" {
                return "HDR 预览建不出"
            }
            if preview.status == "屏幕无 EDR，预览被压到 SDR" {
                return "屏幕无 EDR，预览被压到 SDR"
            }
        }
        switch graph.odt {
        case .off:
            return "709 预览关"
        case .rec709, .hlg, .pq:
            return "仅预览"
        }
    }

    func setIDT(_ id: UUID, _ idt: IDT) {
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return }
        closeSharedGradeStroke()
        clips[idx].idt = idt
        clips[idx].detectedCurve = idt.curve
        clips[idx].detectedGamut = idt.gamut
        clips[idx].detectionSource = .user
        clips[idx].needsUserPicker = false
        clips[idx].detectionNote = "用户选择成对 IDT"
        preview.invalidateIDT(clipID: id)
        // Stay on this clip so the preview shows the pair just chosen.
        // 下一条待选 is explicit. Mid-write does not move selection. Does not lock the next IDT.
        refreshPreview()
    }

    /// After locking the selected pending clip, select the next pending/unlocked
    /// (after current index, else wrap to the first pending that is not the
    /// one just locked). Stay if none remain. Does not lock IDT. Does not write.
    func selectNextPendingAfterLock(lockedID: UUID) {
        guard selectedID == lockedID else { return }
        guard let currentIdx = clips.firstIndex(where: { $0.id == lockedID }) else { return }
        if let next = clips.dropFirst(currentIdx + 1).first(where: { !$0.hasLockedPair }) {
            stopPreviewPlayback()
            selectedID = next.id
            noteSelectionForSharedGrade(next)
            return
        }
        if let wrap = clips.first(where: { $0.id != lockedID && !$0.hasLockedPair }) {
            stopPreviewPlayback()
            selectedID = wrap.id
            noteSelectionForSharedGrade(wrap)
        }
    }

    /// Menu 「下一条待选」. Same move as the inspector button.
    /// Does not lock an IDT. Does not write. Stays put when nothing else is pending.
    var canSelectNextPending: Bool {
        !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
            && selectedClip?.hasLockedPair == true
            && pendingClipCount > 0
    }

    func selectNextPendingFromMenu() {
        guard canSelectNextPending, let clip = selectedClip else { return }
        selectNextPendingAfterLock(lockedID: clip.id)
    }

    private func currentSharedGradeSnapshot() -> SharedGradeSnapshot {
        SharedGradeSnapshot(
            exposureEnabled: graph.exposureEnabled,
            exposureStops: graph.exposureStops,
            wbEnabled: graph.wbEnabled,
            wbCCT: graph.wbCCT,
            wbTint: graph.wbTint,
            wbMethod: graph.wbMethod,
            wbSource: graph.wbSource,
            asShotCCT: graph.asShotCCT,
            asShotTint: graph.asShotTint
        )
    }

    /// Put a snapshot back. Does not record another step, and does not touch IDT or the frame.
    private func applySharedGradeSnapshot(_ snap: SharedGradeSnapshot) {
        touchSharedGrade()
        graph.exposureEnabled = snap.exposureEnabled
        graph.exposureStops = snap.exposureStops
        graph.wbEnabled = snap.wbEnabled
        graph.wbCCT = snap.wbCCT
        graph.wbTint = snap.wbTint
        graph.wbMethod = snap.wbMethod
        graph.wbSource = snap.wbSource
        graph.asShotCCT = snap.asShotCCT
        graph.asShotTint = snap.asShotTint
        persistGraphWBToSelectedClip()
        preview.invalidateWBODT()
        refreshPreview()
    }

    /// Remember the set before a user edit. The same slider stroke does not stack steps.
    /// A nil stroke is one discrete step (a button, a toggle, a grey-card pick).
    private func rememberSharedGrade(stroke: SharedGradeStroke?) {
        if let stroke {
            if openGradeStroke == stroke { return }
            openGradeStroke = stroke
        } else {
            openGradeStroke = nil
        }
        gradeUndoStack.append(currentSharedGradeSnapshot())
        if gradeUndoStack.count > Self.gradeUndoLimit {
            gradeUndoStack.removeFirst(gradeUndoStack.count - Self.gradeUndoLimit)
        }
        gradeRedoStack.removeAll()
    }

    /// End the open slider stroke so the next drag is its own step.
    func closeSharedGradeStroke() {
        openGradeStroke = nil
    }

    /// Sheets, the folder panel, and a write block undo. An empty stack does too.
    var canUndoSharedGrade: Bool {
        !gradeUndoStack.isEmpty && canEditSharedGradeNow
    }

    var canRedoSharedGrade: Bool {
        !gradeRedoStack.isEmpty && canEditSharedGradeNow
    }

    private var canEditSharedGradeNow: Bool {
        !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
            && !openingExportFolder
    }

    /// Back to the previous exposure and white balance. Stops playback. Frame stays.
    @discardableResult
    func undoSharedGrade() -> Bool {
        guard canUndoSharedGrade, let previous = gradeUndoStack.popLast() else { return false }
        closeSharedGradeStroke()
        stopPreviewPlayback()
        gradeRedoStack.append(currentSharedGradeSnapshot())
        if gradeRedoStack.count > Self.gradeUndoLimit {
            gradeRedoStack.removeFirst(gradeRedoStack.count - Self.gradeUndoLimit)
        }
        applySharedGradeSnapshot(previous)
        return true
    }

    /// Forward again after 撤销这一套. Same limits. Does not move the frame.
    @discardableResult
    func redoSharedGrade() -> Bool {
        guard canRedoSharedGrade, let next = gradeRedoStack.popLast() else { return false }
        closeSharedGradeStroke()
        stopPreviewPlayback()
        gradeUndoStack.append(currentSharedGradeSnapshot())
        if gradeUndoStack.count > Self.gradeUndoLimit {
            gradeUndoStack.removeFirst(gradeUndoStack.count - Self.gradeUndoLimit)
        }
        applySharedGradeSnapshot(next)
        return true
    }

    /// ±0.10 stop, or back to 0. Same graph as the inspector slider.
    /// Preview and the monitor readout follow via setExposureStops.
    /// Off while writing or while a sheet is up. Does not turn exposure on.
    var canNudgeExposure: Bool {
        graph.exposureEnabled
            && !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
    }

    func nudgeExposureStops(_ delta: Double) {
        guard canNudgeExposure else { return }
        closeSharedGradeStroke()
        let rounded = ((graph.exposureStops + delta) * 100).rounded() / 100
        setExposureStops(min(8, max(-8, rounded)))
        closeSharedGradeStroke()
    }

    func resetExposureStops() {
        guard canNudgeExposure else { return }
        closeSharedGradeStroke()
        setExposureStops(0)
        closeSharedGradeStroke()
    }

    /// ±100 K on the current CCT. Same graph as the inspector slider.
    /// Empty CCT stays empty — do not start from 6504 or 5600.
    /// Off while writing or while a sheet is up. Does not turn white balance on.
    var canNudgeWB: Bool {
        graph.wbEnabled
            && graph.wbCCT != nil
            && !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
    }

    func nudgeWBCCT(_ delta: Double) {
        guard canNudgeWB, let cct = graph.wbCCT else { return }
        let next = min(10000, max(2000, (cct + delta).rounded()))
        guard next != cct else { return }
        closeSharedGradeStroke()
        setWBParams(cct: next)
        closeSharedGradeStroke()
    }

    /// Back to this clip's as-shot CCT and tint. No as-shot: clear the knobs.
    /// Does not fill a missing camera temperature. Does not turn white balance on.
    var canRestoreAsShotWB: Bool {
        guard graph.wbEnabled,
              !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet
        else { return false }
        if let shot = selectedClip?.asShotCCT {
            let tint = selectedClip?.asShotTint ?? 0
            let atShot = graph.wbSource == .asShot
                && graph.wbCCT == shot
                && abs(graph.wbTint - tint) <= 1e-3
            return !atShot
        }
        let cleared = graph.wbCCT == nil && graph.wbSource == .unknown && abs(graph.wbTint) <= 1e-3
        return !cleared
    }

    /// Writes the selected clip's camera CCT and tint into the one shared set.
    /// Missing camera reading clears the knobs. Does not guess a temperature.
    /// Other clips keep this set until the user edits again.
    func restoreAsShotWB() {
        guard canRestoreAsShotWB else { return }
        rememberSharedGrade(stroke: nil)
        let shot = selectedClip?.asShotCCT
        let shotTint = selectedClip?.asShotTint ?? 0
        if let shot {
            graph.asShotCCT = shot
            graph.asShotTint = shotTint
            graph.wbCCT = shot
            graph.wbTint = shotTint
            graph.wbSource = .asShot
        } else {
            graph.asShotCCT = nil
            graph.asShotTint = 0
            graph.wbCCT = nil
            graph.wbTint = 0
            graph.wbSource = .unknown
        }
        touchSharedGrade()
        persistGraphWBToSelectedClip()
        preview.invalidateWBODT()
        refreshPreview()
    }

    /// Up/Down in the main window: move selected clip in the sidebar list.
    /// Mid-write (#32 / #37) does not change selection. Does not lock IDT. Does not write.
    /// Stops at the ends (no wrap). Inspector numeric / search / text fields keep their arrows.
    @discardableResult
    func selectAdjacentClip(_ delta: Int) -> Bool {
        guard !isWritingDeliverables else { return false }
        guard !showSettings, !showImporter, !showDeliverSheet else { return false }
        guard !Self.isArrowConsumedByTextInput() else { return false }
        guard !clips.isEmpty, delta != 0 else { return false }
        let rows = visibleClips
        guard !rows.isEmpty else { return false }
        let step = delta > 0 ? 1 : -1
        if let id = selectedID, let idx = rows.firstIndex(where: { $0.id == id }) {
            let next = idx + step
            guard rows.indices.contains(next) else { return false }
            stopPreviewPlayback()
            selectedID = rows[next].id
            noteSelectionForSharedGrade(rows[next])
            return true
        }
        let idx = step > 0 ? 0 : rows.count - 1
        stopPreviewPlayback()
        selectedID = rows[idx].id
        noteSelectionForSharedGrade(rows[idx])
        return true
    }

    /// First-frame picture for the list and the inspector.
    /// Camera-log source, not the grade. Skipped while a proxy is being written.
    func requestClipPoster(id: UUID, url: URL) {
        guard !isWritingDeliverables else { return }
        posters.request(id: id, url: url)
    }

    /// Delete / Backspace: drop the selected clip from the SESSION only.
    /// Does not delete, trash, or move the source file. Does not delete an
    /// already-written `_proxy` folder — leave it on disk; just drop the row.
    /// After remove, select next, else previous. Preview chrome follows #33
    /// (`processSkipReason` / `exportChip` on the new selected clip).
    /// #40: evict the removed clip's preview cache.
    /// Mid-write (#32 / #41): ignore — do not change selection, do not cancel
    /// (Escape cancels). Text / numeric / search fields keep Delete.
    /// No confirm sheet. No extra button.
    @discardableResult
    func removeSelectedClipFromSession() -> Bool {
        guard !isWritingDeliverables else { return false }
        guard !showSettings, !showImporter, !showDeliverSheet else { return false }
        guard !Self.isArrowConsumedByTextInput() else { return false }
        guard let id = selectedID, let idx = clips.firstIndex(where: { $0.id == id }) else {
            return false
        }
        // Session list only. Source file and any already-written `_proxy` stay.
        stopPreviewPlayback()
        clips.remove(at: idx)
        preview.evict(clipID: id)
        posters.drop(id: id)
        if clips.indices.contains(idx) {
            selectedID = clips[idx].id
            noteSelectionForSharedGrade(clips[idx])
        } else if idx > 0, clips.indices.contains(idx - 1) {
            selectedID = clips[idx - 1].id
            noteSelectionForSharedGrade(clips[idx - 1])
        } else {
            selectedID = nil
        }
        return true
    }

    /// Arrow keys stay with the focused text / search / numeric control.
    static func isArrowConsumedByTextInput() -> Bool {
        guard let responder = NSApp.keyWindow?.firstResponder else { return false }
        if responder is NSTextView || responder is NSTextField || responder is NSText {
            return true
        }
        if responder is NSSlider || responder is NSStepper || responder is NSSearchField {
            return true
        }
        if responder is NSPopUpButton || responder is NSComboBox {
            return true
        }
        return false
    }

    /// ⌘Z stays with text and the pair search. A slider is not text, so the grade can still step back.
    static func isUndoConsumedByTextInput() -> Bool {
        guard let responder = NSApp.keyWindow?.firstResponder else { return false }
        if responder is NSTextView || responder is NSTextField || responder is NSSearchField || responder is NSText {
            return true
        }
        return false
    }

    /// Space stays with text, sliders, and a focused button (that button already uses Space).
    static func isPlaybackKeyConsumedByControl() -> Bool {
        if isArrowConsumedByTextInput() { return true }
        return NSApp.keyWindow?.firstResponder is NSButton
    }

    /// Sheets / alerts / other key windows keep Escape. Do not steal dismiss.
    static func isEscapeReservedByPresentedUI(event: NSEvent, monitorWindow: NSWindow?) -> Bool {
        if event.window !== monitorWindow { return true }
        if event.window?.attachedSheet != nil { return true }
        if NSApp.modalWindow != nil { return true }
        if let key = NSApp.keyWindow, key !== monitorWindow { return true }
        return false
    }

    /// ±1 green–magenta. Same graph as the inspector slider.
    /// Same gate as the temperature step: needs a color temperature.
    /// Empty CCT stays empty. Does not turn white balance on.
    /// Off while writing or while a sheet is up. Range stays −10 to +10.
    var canNudgeWBTint: Bool { canNudgeWB }

    func nudgeWBTint(_ delta: Double) {
        guard canNudgeWBTint else { return }
        let next = min(10, max(-10, graph.wbTint + delta))
        guard abs(next - graph.wbTint) > 1e-6 else { return }
        closeSharedGradeStroke()
        setWBParams(tint: next)
        closeSharedGradeStroke()
    }

    /// Tint back to 0. Color temperature stays. This is not 回到机内.
    func resetWBTint() {
        guard canNudgeWBTint else { return }
        guard abs(graph.wbTint) > 1e-3 else { return }
        closeSharedGradeStroke()
        setWBParams(tint: 0)
        closeSharedGradeStroke()
    }

    func setExposureEnabled(_ enabled: Bool) {
        guard enabled != graph.exposureEnabled else { return }
        rememberSharedGrade(stroke: nil)
        touchSharedGrade()
        graph.setEnabled(.exposure, enabled)
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setExposureStops(_ stops: Double) {
        guard abs(stops - graph.exposureStops) > 1e-9 else { return }
        rememberSharedGrade(stroke: .exposure)
        touchSharedGrade()
        graph.exposureStops = stops
        preview.invalidateWBODT()
        refreshPreview()
    }

    func setWBEnabled(_ enabled: Bool) {
        guard enabled != graph.wbEnabled else { return }
        rememberSharedGrade(stroke: nil)
        touchSharedGrade()
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
        let cctChanges = cct.map { graph.wbCCT != $0 || graph.wbSource != .user } ?? false
        let tintValueChanges = tint.map { abs($0 - graph.wbTint) > 1e-9 } ?? false
        let tintSourceChanges = tint != nil && graph.wbCCT != nil && graph.wbSource != .user
        let methodChanges = method.map { $0 != graph.wbMethod } ?? false
        guard cctChanges || tintValueChanges || tintSourceChanges || methodChanges else { return }
        if cct != nil {
            rememberSharedGrade(stroke: .cct)
        } else if tint != nil {
            rememberSharedGrade(stroke: .tint)
        } else {
            rememberSharedGrade(stroke: nil)
        }
        touchSharedGrade()
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

    /// Keep one exposure and white-balance set for the whole bin.
    /// A still-factory graph may take the selected clip's camera reading once.
    /// Later selections do not replace the knobs or the CAT reference.
    /// 回到机内 is what copies the current clip's camera reading into the set.
    func noteSelectionForSharedGrade(_ clip: Clip) {
        guard sharedGradeIsFactory else { return }
        applyClipWBToGraph(clip)
        if clip.asShotCCT != nil {
            sharedGradeTouched = true
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
        rememberSharedGrade(stroke: nil)
        touchSharedGrade()
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
        rememberSharedGrade(stroke: nil)
        touchSharedGrade()
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

    /// Global preferences. Does not change the selected clip.
    func presentSettings() {
        guard !openingExportFolder else { return }
        closeSharedGradeStroke()
        stopPreviewPlayback()
        activeSheet = .settings
        showSettings = true
        showDeliverSheet = false
    }

    /// Importer. Held while the folder panel is opening, so that sheet cannot
    /// eat the write that was just confirmed.
    func presentImporter() {
        guard !openingExportFolder else { return }
        closeSharedGradeStroke()
        showImporter = true
    }

    /// Write sheet. Folder panel opens only after this sheet has gone.
    func presentDeliverSheet() {
        guard !isWritingDeliverables, !openingExportFolder else { return }
        closeSharedGradeStroke()
        stopPreviewPlayback()
        activeSheet = .deliver
        showDeliverSheet = true
        showSettings = false
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

    /// How many clips landed, and the next step. Does not assign an IDT.
    /// Zero means the caller still has to say the folder had nothing readable,
    /// or to attach the skip list. Does not invent 5600.
    static func importArrivalNote(imported: Int, needsPicker: Bool) -> String {
        guard imported > 0 else { return "" }
        if needsPicker {
            return "读入 \(imported) 条。在右侧检查器选成对 IDT。"
        }
        return "读入 \(imported) 条。可在监视器看预览，再点写出。"
    }

    /// Dropped path expanded to nothing the bin can list.
    static func importEmptyNote() -> String {
        "没有能读的素材。拖 MOV、MP4、TIFF、DPX、EXR，或含这些的文件夹。"
    }

    /// True when the sidebar filter would hide at least one clip from this drop.
    static func importFilterHidesNewRow(_ filter: ClipListFilter, built: [Clip]) -> Bool {
        switch filter {
        case .all:
            return false
        case .pending:
            return built.contains { $0.hasLockedPair }
        case .locked:
            return built.contains { !$0.hasLockedPair }
        }
    }

    /// Multi-file refuse list. Header when more than one skip. Per-file chips unchanged.
    static func importSkipSummary(_ skipped: [String]) -> String {
        guard skipped.count > 1 else {
            return skipped.joined(separator: "\n")
        }
        return "未导入 \(skipped.count) 条：\n" + skipped.joined(separator: "\n")
    }

    func importURL(_ url: URL) {
        stopPreviewPlayback()
        // Keep the security scope for the session so preview decode can reopen the URL.
        _ = url.startAccessingSecurityScopedResource()
        lastImportNote = "正在读入…"
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
                        skipped.append("\(file.lastPathComponent)：\(MediaFormat.noteMxfNoTrack)")
                        continue
                    }
                }
                let detection = ClipDetector.detect(url: file)
                let extent = MediaFormat.extent(url: file)
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
                    formatNote: probe.note,
                    pixelWidth: extent.width,
                    pixelHeight: extent.height,
                    mediaFPS: extent.fps,
                    durationSeconds: extent.durationSeconds,
                    isStill: probe.kind == .still
                ))
            }
            DispatchQueue.main.async {
                guard let self else { return }
                for clip in built {
                    self.clips.append(clip)
                }
                // After drop/import: first pending/unlocked so 待选 is obvious.
                // All-locked keeps first / existing selection. Does not lock IDT.
                if let pending = built.first(where: { !$0.hasLockedPair }) {
                    self.selectedID = pending.id
                    self.noteSelectionForSharedGrade(pending)
                } else if self.selectedID == nil, let first = built.first {
                    self.selectedID = first.id
                    self.noteSelectionForSharedGrade(first)
                }
                // A 待选 / 已锁定 filter must not hide the rows that just arrived.
                if !built.isEmpty, Self.importFilterHidesNewRow(self.clipListFilter, built: built) {
                    self.clipListFilter = .all
                }
                let needsPicker = built.contains { !$0.hasLockedPair }
                var note = Self.importArrivalNote(imported: built.count, needsPicker: needsPicker)
                if built.isEmpty, skipped.isEmpty {
                    note = Self.importEmptyNote()
                }
                if !skipped.isEmpty {
                    let skips = Self.importSkipSummary(skipped)
                    note = note.isEmpty ? skips : note + "\n" + skips
                }
                self.lastImportNote = note
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
        panel.prompt = "导出"
        panel.message = "已锁定片段写出 Resolve 节点图（XML / DCTL / .cube）。未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。整段代理，代理精度。已实现（未验证）。"
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
                note += "\n已写出 \(written.count) 个文件。\(locked.count) 条已锁定 / \(skipped.count) 条已跳过（先选择 Log 与色域 / 先选择成对 IDT）。已实现（未验证）。整段代理，代理精度。"
                self.lastExportNote = note
            } catch {
                self.lastExportNote = Self.shortExportChip(for: error)
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
