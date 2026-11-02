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

    /// Parent folder name, so two files with the same name can be told apart.
    /// Not the full path. Not a grade and not a deliverable.
    var folderName: String {
        url.deletingLastPathComponent().lastPathComponent
    }

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

    /// Frame for a typed preview clock, a number of seconds, or 「第 N 帧」.
    /// N is the 1-based readout. A clock lands on the nearest frame at this rate.
    /// Past either end clamps. Nil when the text or the rate cannot be read.
    /// Does not fill in a rate. Not camera timecode.
    static func previewFrameIndex(forClock text: String, fps: Double?, lastFrame: Int) -> Int? {
        guard lastFrame >= 0, let fps, fps.isFinite, fps > 0 else { return nil }
        var trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        trimmed = trimmed.replacingOccurrences(of: "：", with: ":")
        if trimmed.contains("帧") {
            guard let display = previewDisplayFrame(trimmed) else { return nil }
            return min(display - 1, lastFrame)
        }
        if trimmed.hasSuffix("秒") {
            trimmed.removeLast()
            trimmed = trimmed.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        guard let seconds = previewClockSeconds(trimmed), seconds.isFinite, seconds >= 0 else { return nil }
        let raw = (seconds * fps).rounded()
        guard raw.isFinite, raw >= 0 else { return nil }
        if raw > Double(lastFrame) { return lastFrame }
        return Int(raw)
    }

    /// 「第 12 帧」 and 「12帧」. 1-based, matching the readout. Nil if it is not a frame.
    private static func previewDisplayFrame(_ text: String) -> Int? {
        guard text.contains("帧") else { return nil }
        let stripped = text
            .replacingOccurrences(of: "第", with: "")
            .replacingOccurrences(of: "帧", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let n = Int(stripped), n >= 1 else { return nil }
        return n
    }

    /// `m:ss.mmm`, `h:mm:ss.mmm`, or a plain number of seconds. Nil when it is not a clock.
    /// The right-hand fields stay under a minute. The leftmost field may run long.
    private static func previewClockSeconds(_ text: String) -> Double? {
        let parts = text.split(separator: ":", omittingEmptySubsequences: false).map {
            String($0).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        guard (1...3).contains(parts.count) else { return nil }
        func number(_ part: String) -> Double? {
            guard !part.isEmpty, let value = Double(part), value.isFinite, value >= 0 else { return nil }
            return value
        }
        func whole(_ value: Double) -> Bool {
            value.rounded() == value
        }
        if parts.count == 1 {
            return number(parts[0])
        }
        if parts.count == 2 {
            guard let minutes = number(parts[0]), let seconds = number(parts[1]) else { return nil }
            guard whole(minutes), seconds < 60 else { return nil }
            return minutes * 60 + seconds
        }
        guard let hours = number(parts[0]), let minutes = number(parts[1]), let seconds = number(parts[2]) else {
            return nil
        }
        guard whole(hours), whole(minutes), minutes < 60, seconds < 60 else { return nil }
        let hour = 60.0
        return hours * hour * hour + minutes * hour + seconds
    }

    /// Frames in about one second at this clip's rate. Nearest whole frame.
    /// Nil when the rate is missing or rounds to nothing. Does not fill in a rate.
    static func previewSecondFrameCount(fps: Double?) -> Int? {
        guard let fps, fps.isFinite, fps > 0 else { return nil }
        let frames = Int(fps.rounded())
        guard frames >= 1 else { return nil }
        return frames
    }

    /// Next frame while the preview is playing. Nil means stop.
    /// Forward loop returns to the first frame only when this range has more than one frame.
    /// Backward stops on the first frame, or returns to the last when loop is on.
    /// Does not invent a rate, and does not move exposure or white balance.
    static func previewPlayNextFrame(index: Int, last: Int, loops: Bool, backward: Bool = false) -> Int? {
        guard last >= 0, index >= 0, index <= last else { return nil }
        if backward {
            if index > 0 { return index - 1 }
            if loops, last > 0 { return last }
            return nil
        }
        if index < last { return index + 1 }
        if loops, last > 0 { return 0 }
        return nil
    }

    /// Frame shown when playback starts. Nil means it cannot start.
    /// Forward loop at the last frame begins again at the first. Otherwise stay here.
    /// Backward at the first frame begins at the last only when loop is on.
    /// The end frame without a loop does not start. Does not invent a rate.
    static func previewPlayStartFrame(index: Int, last: Int, loops: Bool, backward: Bool = false) -> Int? {
        guard last >= 0, index >= 0, index <= last else { return nil }
        if backward {
            if index > 0 { return index }
            if loops, last > 0 { return last }
            return nil
        }
        if index < last { return index }
        if loops, last > 0 { return 0 }
        return nil
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

/// A typed exposure, color temperature, or green–magenta.
/// Out of range does not clamp into a guess.
private enum TypedGradeField {
    case empty
    case unrecognized
    case outOfRange
    case value(Double)
}

/// What the write sheet may show of the monitor. The still is not a second grade.
struct DeliverPreviewGlance {
    var showStill: Bool
    var sheetNote: String
    var barCaution: String?
}

final class SessionModel: ObservableObject {
    @Published var clips: [Clip] = []
    /// 全部 / 待选 / 已锁定. The monitor keeps the current clip until selection moves.
    @Published var clipListFilter: ClipListFilter = .all
    /// Filename or parent-folder query. Narrows the list only. Blank keeps every filtered row.
    @Published var clipListQuery: String = ""
    /// Bumps after 「显示这条」 puts the selected row back. The list scrolls to it.
    /// Does not change the selection, the grade, or the frame.
    @Published var listRevealToken = 0
    @Published var selectedID: UUID? {
        didSet {
            if selectedID != oldValue, !keepingFollowingPairNote, !followingPairApplyNote.isEmpty {
                followingPairApplyNote = ""
            }
        }
    }
    /// Bumps when a loop step asks the inspector to scroll. The target is the anchor.
    /// Selection changes do not use this. Does not change the grade or the frame.
    @Published var inspectorScrollToken = 0
    var inspectorScrollTarget: String?
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
    /// Shown under the typed exposure field. Empty after a value is accepted.
    @Published var typedExposureNote: String = ""
    /// Shown under the typed color-temperature field. Empty after a value is accepted.
    @Published var typedCCTNote: String = ""
    /// Shown under the typed green–magenta field. Empty after a value is accepted.
    @Published var typedTintNote: String = ""
    /// After 「这一对给后面连续的待选」. Cleared when the selection moves another way.
    @Published var followingPairApplyNote: String = ""
    /// Selection changes inside that action must keep the note.
    private var keepingFollowingPairNote = false
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
    /// 分屏 / 对照 / 源 / 预览。对照左幅不含曝光和白平衡，右幅是这一套。
    @Published var monitorLayout: MonitorLayout = .split
    /// Layout to restore when 对照 is turned off from the menu.
    private var monitorLayoutBeforeCompare: MonitorLayout = .split
    /// Last index (duration × metadata fps − 1). Nil: still, or no clip, or fail.
    @Published var previewScrubLastFrame: Int? = nil
    /// 「读不到帧率，未核对」 / 「读不到时长，未核对」. No slider. No 24/30 guess.
    @Published var previewScrubFail: String? = nil
    /// Metadata fps captured with the scrub range. Nil when there is nothing to play.
    /// Playback uses this. It does not probe again, and it does not invent a rate.
    @Published var previewPlaybackFPS: Double? = nil
    /// Preview transport. Picture only. Forward stops at the last frame unless loop is on.
    /// Backward stops at the first frame unless loop is on.
    @Published var isPreviewPlaying = false
    /// True only while the current playback is stepping toward the first frame.
    /// Cleared on stop. Not a grade, and not a write input.
    @Published var previewPlaysBackward = false
    /// Playback wraps at the end of the range. Off keeps stop-at-end. Not an in/out.
    /// Switching clips keeps this. It does not change the shared grade or the write.
    @Published var previewLoops = false
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

    /// Preview frames publish on `preview`, not on this model. Forward them
    /// or the monitor stays on the last session change and a finished frame
    /// never appears. Does not change the grade or the write.
    private var previewChangeForward: AnyCancellable?

    init() {
        graph.odt = settings.defaultPreviewODT
        previewChangeForward = preview.objectWillChange.sink { [weak self] _ in
            self?.objectWillChange.send()
        }
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

    /// How many rows a filter names. Counts are the whole bin, not the filename query.
    /// Does not move the selection, lock an IDT, or change the shared grade.
    static func clipListFilterCount(filter: ClipListFilter, clipCount: Int, pendingCount: Int, lockedCount: Int) -> Int {
        switch filter {
        case .all: return clipCount
        case .pending: return pendingCount
        case .locked: return lockedCount
        }
    }

    /// Segment title: 「待选 3」. The number is the bin count, not the search.
    static func clipListFilterTitle(filter: ClipListFilter, count: Int) -> String {
        "\(filter.label) \(count)"
    }

    /// One line under the filter. Pending stays the next step. All locked can be graded.
    /// Nil when the bin is empty. Does not change the selection, the grade, or the frame.
    static func clipListRemainderLine(pendingCount: Int, lockedCount: Int) -> String? {
        if pendingCount > 0 {
            return "还有 \(pendingCount) 条待选。点一条，到右侧选成对 IDT。"
        }
        if lockedCount > 0 {
            return "成对 IDT 都已选上。可调色，再写出。"
        }
        return nil
    }

    /// 「全部 12」. The number is this bin, not the filename query.
    func clipListFilterTitle(_ filter: ClipListFilter) -> String {
        Self.clipListFilterTitle(
            filter: filter,
            count: Self.clipListFilterCount(
                filter: filter,
                clipCount: clips.count,
                pendingCount: pendingClipCount,
                lockedCount: lockedClipCount
            )
        )
    }

    /// Next step under the filter. Empty bin stays on the drop zone.
    var clipListRemainderLine: String? {
        Self.clipListRemainderLine(pendingCount: pendingClipCount, lockedCount: lockedClipCount)
    }

    /// Rows the sidebar is showing. Arrow keys move inside this list.
    /// The lock filter runs first. A filename query only narrows that list.
    var visibleClips: [Clip] {
        clips.filter { clip in
            Self.clipMatchesListFilter(clip, filter: clipListFilter)
                && Self.clipMatchesListQuery(clip, query: clipListQuery)
        }
    }

    /// True when this row stays under 全部 / 待选 / 已锁定.
    /// Does not look at the filename query. Does not lock an IDT or move the selection.
    static func clipMatchesListFilter(_ clip: Clip, filter: ClipListFilter) -> Bool {
        switch filter {
        case .all:
            return true
        case .pending:
            return !clip.hasLockedPair
        case .locked:
            return clip.hasLockedPair
        }
    }

    /// True when this row stays in the bin search. A blank query keeps the row.
    /// Matches the filename or the parent folder name. Does not lock an IDT,
    /// move the selection, or change the shared grade.
    static func clipMatchesListQuery(_ clip: Clip, query: String) -> Bool {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if needle.isEmpty { return true }
        if clip.filename.localizedStandardContains(needle) { return true }
        let folder = clip.folderName
        if !folder.isEmpty, folder.localizedStandardContains(needle) { return true }
        return false
    }

    /// What 「显示这条」 changes. Nil when there is no selection, or the row is already showing.
    /// clearFilter returns the filter to 全部. clearQuery empties the filename query.
    /// Does not move the selection, the grade, the pair, or the frame.
    static func listRevealAdjustments(
        hasSelection: Bool,
        matchesFilter: Bool,
        matchesQuery: Bool
    ) -> (clearFilter: Bool, clearQuery: Bool)? {
        guard hasSelection, !(matchesFilter && matchesQuery) else { return nil }
        return (!matchesFilter, !matchesQuery)
    }

    /// Put the selected row back in the list.
    /// A filter that hides it returns to 全部. A query that hides it is cleared.
    /// Both, when both hide it. Already visible does nothing.
    /// Playback, the grade, the pair, and the frame stay. Does not write.
    @discardableResult
    func revealSelectedClipInList() -> Bool {
        guard let clip = selectedClip else { return false }
        guard let adjust = Self.listRevealAdjustments(
            hasSelection: true,
            matchesFilter: Self.clipMatchesListFilter(clip, filter: clipListFilter),
            matchesQuery: Self.clipMatchesListQuery(clip, query: clipListQuery)
        ) else { return false }
        if adjust.clearFilter {
            clipListFilter = .all
        }
        if adjust.clearQuery {
            clipListQuery = ""
        }
        listRevealToken += 1
        return true
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

    /// 对照左幅。同一成对 IDT、同一次预览，曝光和白平衡关掉。
    /// Nil unless the monitor is on 对照 and this clip has a locked pair.
    /// Does not replace `graph`, and does not guess a color temperature.
    var graphForCompareBefore: SerialGraph? {
        guard monitorLayout == .compare else { return nil }
        guard selectedClip?.hasLockedPair == true else { return nil }
        guard !previewShowsGradeBefore else { return nil }
        var copy = graph
        copy.exposureEnabled = false
        copy.wbEnabled = false
        return copy
    }

    /// Turn the compare on only after a paired IDT is locked.
    /// Turn it off whenever a clip is selected. Sheets, write, and grey-card
    /// sampling keep the current picture. 对照 already shows that picture beside the grade.
    var canTogglePreviewGradeBefore: Bool {
        guard monitorLayout != .compare else { return false }
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !pickingNeutral
        else { return false }
        if previewShowsGradeBefore { return selectedClip != nil }
        return selectedClip?.hasLockedPair == true
    }

    /// 对照 opens after a paired IDT is locked. Closing it does not need a lock.
    /// Sheets, write, and grey-card sampling leave the layout alone.
    var canTogglePreviewCompare: Bool {
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder,
              !pickingNeutral
        else { return false }
        if monitorLayout == .compare { return true }
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

    /// Name the next write will create for the selected locked clip.
    /// Same suffix as the write sheet. A pending clip is skipped, so it gets nil.
    /// A write in progress yields the progress line instead. No full path.
    /// When the write sheet can open, the sentence says this line opens it.
    /// A sheet or the folder panel keeps the name and drops that sentence.
    /// Does not change exposure, white balance, the pair, or the frame.
    static func monitorWillWriteLine(
        selectedLocked: Bool,
        exporting: Bool,
        deliverableName: String,
        lockedCount: Int,
        pendingCount: Int,
        canOpenSheet: Bool
    ) -> String? {
        guard selectedLocked, !exporting, lockedCount > 0 else { return nil }
        let name = deliverableName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else { return nil }
        let action: String? = canOpenSheet ? "点这一行打开写出说明，再选文件夹。" : nil
        if lockedCount == 1 && pendingCount == 0 {
            if let action {
                return "将得到 \(name)。\(action)"
            }
            return "将得到 \(name)。"
        }
        if pendingCount > 0 {
            let base = "已锁定 \(lockedCount) 条会写出，待选 \(pendingCount) 条会跳过。这一条将得到 \(name)"
            if let action {
                return "\(base)。\(action)"
            }
            return base
        }
        let base = "已锁定 \(lockedCount) 条都会写出。这一条将得到 \(name)"
        if let action {
            return "\(base)。\(action)"
        }
        return base
    }

    /// Why one monitor pane is still black. A picture that is up gets nothing.
    /// The grade pane of a clip that still needs a paired IDT stays quiet:
    /// that next step is already on the monitor. Does not change the grade
    /// or the write, and does not invent a frame rate.
    static func monitorPaneGapNote(
        imageMissing: Bool,
        isWorking: Bool,
        status: String,
        waitingOnPair: Bool
    ) -> String? {
        guard imageMissing, !waitingOnPair else { return nil }
        if isWorking { return "正在解码预览…" }
        if status == "解不出预览帧" || status == "解码失败" {
            return status
        }
        return nil
    }

    func refreshPreview() {
        // Selected clip (or grade) changed. PreviewEngine keeps only this
        // clip's preview source/linear/graded and drops a stale first-frame
        // if selection already moved on. Write path is not this cache.
        if selectedID != previewScrubClipID {
            stopPreviewPlayback()
            resetPreviewScrub()
        }
        preview.refresh(clip: selectedClip, graph: graphForPreview, frameIndex: previewFrameIndex, compareBefore: graphForCompareBefore)
    }

    /// ODT / scrub: do not invalidate graded linear (IDT+exposure+WB).
    func refreshODTOnly() {
        preview.refreshODT(
            clip: selectedClip,
            graph: graphForPreview,
            frameIndex: previewFrameIndex,
            compareBefore: graphForCompareBefore
        )
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
        preview.scrub(
            clip: selectedClip,
            graph: graphForPreview,
            frameIndex: next,
            compareBefore: graphForCompareBefore
        )
    }

    /// V and the 调色 menu. 分屏 and 预览 only.
    /// 源 and 对照 stay on the segmented control and on ⌥⌘/. Nil means V does nothing.
    /// Does not edit exposure, white balance, the paired IDT, or the preview frame.
    static func toggledSplitAndGradeLayout(_ current: MonitorLayout) -> MonitorLayout? {
        switch current {
        case .split: return .grade
        case .grade: return .split
        case .source, .compare: return nil
        }
    }

    /// Off on 源 and 对照, and while a sheet, the folder panel, a write, or a grey-card pick is up.
    var canToggleSplitAndGrade: Bool {
        guard Self.toggledSplitAndGradeLayout(monitorLayout) != nil else { return false }
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder,
              !pickingNeutral
        else { return false }
        return true
    }

    /// Enlarge the grade, or go back to the source | grade split. Same pictures.
    @discardableResult
    func toggleSplitAndGrade() -> Bool {
        guard canToggleSplitAndGrade, let next = Self.toggledSplitAndGradeLayout(monitorLayout) else {
            return false
        }
        setMonitorLayout(next)
        return true
    }

    /// Segmented monitor control. Entering 对照 turns off 看调色前 so the
    /// right pane stays this shared set. Does not edit exposure, white balance,
    /// the paired IDT, or the preview frame.
    func setMonitorLayout(_ layout: MonitorLayout) {
        guard monitorLayout != layout else { return }
        let touchesCompare = layout == .compare || monitorLayout == .compare
        if touchesCompare, !canTogglePreviewCompare { return }
        let wasCompare = monitorLayout == .compare
        let wasGradeBefore = previewShowsGradeBefore
        if layout == .compare, !wasCompare {
            monitorLayoutBeforeCompare = monitorLayout
            previewShowsGradeBefore = false
        }
        monitorLayout = layout
        if wasCompare, layout != .compare {
            preview.compareBeforeImage = nil
        }
        if layout == .compare || wasCompare || (wasGradeBefore && !previewShowsGradeBefore) {
            refreshPreview()
        }
    }

    /// Menu and ⌥⌘/. Off returns to the layout from before 对照.
    func togglePreviewCompare() {
        guard canTogglePreviewCompare else { return }
        if monitorLayout == .compare {
            let back = monitorLayoutBeforeCompare == .compare ? MonitorLayout.split : monitorLayoutBeforeCompare
            setMonitorLayout(back)
        } else {
            setMonitorLayout(.compare)
        }
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
    /// Stills, missing rate, grey-card pick, sheets, and write stay stopped.
    /// The last frame stays stopped unless loop is on, and a one-frame range never loops.
    var canPlayPreview: Bool {
        guard !pickingNeutral else { return false }
        guard let fps = previewPlaybackFPS, fps.isFinite, fps > 0 else { return false }
        guard let last = previewScrubLastFrame, last >= 0 else { return false }
        if previewLoops {
            guard canStepPreviewFrame, last > 0 else { return false }
            return true
        }
        return canStepPreviewForward
    }

    /// Space and the scrub button. Pause is allowed until a sheet or a write takes the window.
    var canTogglePreviewPlayback: Bool {
        if isPreviewPlaying {
            return canStepPreviewFrame && !pickingNeutral
        }
        return canPlayPreview
    }

    /// Reverse uses the same rate as forward. One frame cannot reverse.
    /// Without loop, the first frame cannot start backward.
    var canReversePreview: Bool {
        guard !pickingNeutral else { return false }
        guard let fps = previewPlaybackFPS, fps.isFinite, fps > 0 else { return false }
        guard let last = previewScrubLastFrame, last >= 0 else { return false }
        if previewLoops {
            guard canStepPreviewFrame, last > 0 else { return false }
            return true
        }
        return canStepPreviewBackward
    }

    /// 倒放 button. Already reversing can pause. Otherwise it must be able to start.
    var canTogglePreviewReverse: Bool {
        if isPreviewPlaying, previewPlaysBackward {
            return canStepPreviewFrame && !pickingNeutral
        }
        return canReversePreview
    }

    /// Start or stop preview playback. Does not move exposure, white balance, or the write.
    /// At the last frame this jumps back only when loop is on.
    @discardableResult
    func togglePreviewPlayback() -> Bool {
        if isPreviewPlaying {
            stopPreviewPlayback()
            return true
        }
        return startPreviewPlayback()
    }

    /// The loop control is there only for a real rate and more than one frame.
    var showsPreviewLoop: Bool {
        guard let last = previewScrubLastFrame, last > 0 else { return false }
        guard let fps = previewPlaybackFPS, fps.isFinite, fps > 0 else { return false }
        return true
    }

    /// Same sheet and write gates as a frame step. Grey-card sampling stays put.
    var canTogglePreviewLoop: Bool {
        showsPreviewLoop && canStepPreviewFrame && !pickingNeutral
    }

    /// Turn loop on or off. Does not move the frame, the shared grade, or the write.
    /// Playback keeps going; the next end either wraps or stops.
    @discardableResult
    func togglePreviewLoop() -> Bool {
        guard canTogglePreviewLoop else { return false }
        previewLoops.toggle()
        return true
    }

    /// One frame per tick, at the metadata rate. Waits out a preview that is still drawing.
    /// Does not skip ahead, and does not invent a frame rate.
    /// Loop at the last frame begins at the first before the timer starts.
    /// Backward at the first frame begins at the last only when loop is on.
    @discardableResult
    func startPreviewPlayback(backward: Bool = false) -> Bool {
        let allowed = backward ? canReversePreview : canPlayPreview
        guard allowed, let fps = previewPlaybackFPS, let last = previewScrubLastFrame else { return false }
        guard let start = Clip.previewPlayStartFrame(
            index: previewFrameIndex,
            last: last,
            loops: previewLoops,
            backward: backward
        ) else { return false }
        stopPreviewPlayback()
        if start != previewFrameIndex {
            setPreviewFrame(start)
        }
        if previewPlaysBackward != backward {
            previewPlaysBackward = backward
        }
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
        if previewPlaysBackward {
            previewPlaysBackward = false
        }
    }

    private func advancePreviewPlayback() {
        guard isPreviewPlaying else { return }
        if preview.isWorking { return }
        guard !pickingNeutral, let last = previewScrubLastFrame else {
            stopPreviewPlayback()
            return
        }
        guard let next = Clip.previewPlayNextFrame(
            index: previewFrameIndex,
            last: last,
            loops: previewLoops,
            backward: previewPlaysBackward
        ) else {
            stopPreviewPlayback()
            return
        }
        setPreviewFrame(next, keepPlaying: true)
    }

    /// 倒放. Already reversing pauses. Forward playback switches to reverse.
    /// Does not change exposure, white balance, or the write.
    @discardableResult
    func playPreviewBackward() -> Bool {
        if isPreviewPlaying, previewPlaysBackward {
            guard canTogglePreviewReverse else { return false }
            stopPreviewPlayback()
            return true
        }
        return startPreviewPlayback(backward: true)
    }

    /// K. Pauses whichever direction is running. Does nothing when already stopped.
    @discardableResult
    func pausePreviewPlayback() -> Bool {
        guard isPreviewPlaying, canStepPreviewFrame, !pickingNeutral else { return false }
        stopPreviewPlayback()
        return true
    }

    /// Typed clock, seconds, or 第 N 帧. Same rate as the readout. No invented rate.
    var canJumpPreviewToClock: Bool {
        guard canStepPreviewFrame else { return false }
        guard let fps = previewPlaybackFPS, fps.isFinite, fps > 0 else { return false }
        return true
    }

    /// Nearest frame at this clip's rate. Clamps to the scrub ends.
    /// Stops playback. Does not change exposure, white balance, or the write.
    @discardableResult
    func jumpPreview(toClock text: String) -> Bool {
        guard canJumpPreviewToClock, let last = previewScrubLastFrame else { return false }
        guard let index = Clip.previewFrameIndex(forClock: text, fps: previewPlaybackFPS, lastFrame: last) else {
            return false
        }
        if index == previewFrameIndex {
            stopPreviewPlayback()
            return true
        }
        setPreviewFrame(index)
        return true
    }

    var lockedClips: [Clip] { clips.filter(\.hasLockedPair) }
    var lockedClipCount: Int { lockedClips.count }
    var pendingClipCount: Int { clips.filter { !$0.hasLockedPair }.count }

    /// 「N 条已锁定 / M 条待选」
    var lockStatusText: String {
        "\(lockedClipCount) 条已锁定 / \(pendingClipCount) 条待选"
    }

    /// 监视器下、滑条下面。当前这条已锁定时，写出将得到的名字。
    /// 和写出说明是同一个。只写文件名或文件夹名。待选不出现。正在写出时让给进度。
    /// 能打开写出说明时，句尾让人点这一行。设置、添加、写出说明或选文件夹开着时只留名字。
    /// 不改这一套曝光和白平衡，不改成对 IDT，也不改预览帧。
    var monitorWillWriteLine: String? {
        guard let clip = selectedClip else { return nil }
        return Self.monitorWillWriteLine(
            selectedLocked: clip.hasLockedPair,
            exporting: isWritingDeliverables,
            deliverableName: clip.plannedDeliverableName(format: settings.exportFormat),
            lockedCount: lockedClipCount,
            pendingCount: pendingClipCount,
            canOpenSheet: canStartWriteFromLoop
        )
    }

    /// Scroll id for the paired-IDT block. Pending selection returns here.
    static let inspectorPairedIDTAnchor = "paired-idt"
    /// Scroll id for exposure. 调色 asks for this, and so does the last lock.
    /// Changing clips does not. Does not change the grade or the frame.
    static let inspectorExposureAnchor = "exposure"

    /// A pending clip needs the paired-IDT list, which sits above the grade.
    /// A locked clip keeps the scroll, so exposure and white balance stay put.
    /// Nil means do not scroll. Does not change the grade, the pair, or the frame.
    static func inspectorScrollAnchor(selectedIsPending: Bool) -> String? {
        selectedIsPending ? inspectorPairedIDTAnchor : nil
    }

    /// After a pair is locked on the clip being previewed.
    /// Nothing else is still pending: reveal exposure, same as 调色.
    /// Another clip is still pending: stay, so 下一条待选 remains in view.
    /// A sheet or a write in progress does not scroll.
    /// Nil means do not scroll. Does not change the grade, the pair, or the frame.
    static func inspectorScrollAfterLock(pendingRemain: Bool, blocked: Bool) -> String? {
        if blocked || pendingRemain { return nil }
        return inspectorExposureAnchor
    }

    /// Pair name pinned under the inspector title. Only a locked pair.
    /// Pending returns nil, so the header does not invent a pair.
    /// Does not change the grade, the frame, or the write.
    static func inspectorPinnedPairLine(hasLockedPair: Bool, pairLabel: String) -> String? {
        guard hasLockedPair else { return nil }
        let trimmed = pairLabel.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return trimmed
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
        if showImporter { return "正在打开添加" }
        if clips.isEmpty { return "先拖入或点添加。按回车也是添加。" }
        if !showsProcessLockedButton { return "在右侧检查器选成对 IDT。按回车滚到这一列，不替你选。" }
        if canRevealLastExport { return "已写出代理。可再调色，或在状态栏打开 Finder" }
        if pendingClipCount > 0 {
            return "可调色并写出；待选仍要选 IDT。待选时按回车滚到成对 IDT；已锁定时按回车滚到曝光，不改数字。"
        }
        return "可调色，再点写出。按回车滚到曝光，不改数字。"
    }

    /// 写出说明、监视器下那一行、选文件夹面板共用。只写文件夹名。
    /// 文件夹不在了就不写名字。不在 ⌘, 里。不改这一套调色。
    var exportFolderOpenNote: String {
        Self.exportFolderOpenNote(
            folderName: Self.exportFolderResumeName(from: settings.lastExportDirectoryURL)
        )
    }

    /// Primary button is shown only when at least one paired IDT is locked.
    var showsProcessLockedButton: Bool {
        settings.blockUnlockedIDT && lockedClipCount > 0
    }

    /// 0 导入，1 选 IDT，2 调色，3 写出。
    /// Writing or the folder panel is the write step.
    /// An empty bin, or the add panel, is import.
    /// No locked pair yet, or the selected clip still pending, is pick IDT.
    /// Otherwise the selected clip can be graded. The write button stays beside that.
    /// Does not assign an IDT and does not move exposure or white balance.
    static func loopStepIndex(
        clipsEmpty: Bool,
        importing: Bool,
        openingFolder: Bool,
        writing: Bool,
        lockedCount: Int,
        selectedPending: Bool
    ) -> Int {
        if writing || openingFolder { return 3 }
        if clipsEmpty || importing { return 0 }
        if lockedCount == 0 || selectedPending { return 1 }
        return 2
    }

    var loopStepIndex: Int {
        Self.loopStepIndex(
            clipsEmpty: clips.isEmpty,
            importing: showImporter,
            openingFolder: openingExportFolder,
            writing: isWritingDeliverables,
            lockedCount: lockedClipCount,
            selectedPending: selectedClip?.isPending == true
        )
    }

    /// What Return does. "none" leaves the key alone.
    /// import opens the add panel. idt scrolls to this clip's paired list.
    /// grade reveals exposure. Write stays on ⌘E.
    /// A pending clip wins over locked, so Return does not skip the pair list.
    /// Does not lock a pair and does not edit the shared grade.
    static func loopReturnAction(
        blocked: Bool,
        clipsEmpty: Bool,
        selectedPending: Bool,
        selectedLocked: Bool
    ) -> String {
        if blocked { return "none" }
        if clipsEmpty { return "import" }
        if selectedPending { return "idt" }
        if selectedLocked { return "grade" }
        return "none"
    }

    var canFollowLoopWithReturn: Bool {
        Self.loopReturnAction(
            blocked: returnLoopBlocked,
            clipsEmpty: clips.isEmpty,
            selectedPending: selectedClip?.isPending == true,
            selectedLocked: selectedClip?.hasLockedPair == true
        ) != "none"
    }

    /// Sheets, the add panel, and a write in progress keep Return.
    private var returnLoopBlocked: Bool {
        isWritingDeliverables
            || openingExportFolder
            || showSettings
            || showImporter
            || showDeliverSheet
    }

    /// Same gate as 「添加…」. Cancel still reads nothing.
    var canOpenImporter: Bool {
        !openingExportFolder
            && !showImporter
            && !showSettings
            && !showDeliverSheet
            && !isWritingDeliverables
    }

    /// There is a pending clip, and a sheet is not covering the window.
    var canFocusPendingIDT: Bool {
        pendingClipCount > 0
            && !isWritingDeliverables
            && !openingExportFolder
            && !showSettings
            && !showImporter
            && !showDeliverSheet
    }

    /// Current clip already has a pair. Scrolling does not edit the grade.
    var canFocusGradeControls: Bool {
        selectedClip?.hasLockedPair == true
            && !isWritingDeliverables
            && !openingExportFolder
            && !showSettings
            && !showImporter
            && !showDeliverSheet
    }

    /// Opens the write sheet. Does not start writing by itself.
    var canStartWriteFromLoop: Bool {
        showsProcessLockedButton
            && !isWritingDeliverables
            && !openingExportFolder
            && !showImporter
            && !showSettings
            && !showDeliverSheet
    }

    /// Pending clip: scroll to the paired list. Locked clip: the existing next-pending move.
    /// Does not lock a pair. Does not change exposure or white balance.
    func focusPendingIDT() {
        guard canFocusPendingIDT else { return }
        if selectedClip?.isPending == true {
            requestInspectorScroll(Self.inspectorPairedIDTAnchor)
            return
        }
        if canSelectNextPending {
            selectNextPendingFromMenu()
            return
        }
        guard let pending = clips.first(where: { $0.isPending }) else { return }
        stopPreviewPlayback()
        selectedID = pending.id
        noteSelectionForSharedGrade(pending)
    }

    /// Show exposure and white balance. Numbers, the frame, and the pair stay.
    func focusGradeControls() {
        guard canFocusGradeControls else { return }
        requestInspectorScroll(Self.inspectorExposureAnchor)
    }

    /// Return follows the marked step, except 写出.
    /// Empty bin: same as 添加…. Pending: scroll to the pair list, do not lock.
    /// Locked: reveal exposure and white balance, do not change the numbers.
    /// Text fields keep Return. Does not open the write sheet.
    @discardableResult
    func followLoopWithReturn() -> Bool {
        switch Self.loopReturnAction(
            blocked: returnLoopBlocked,
            clipsEmpty: clips.isEmpty,
            selectedPending: selectedClip?.isPending == true,
            selectedLocked: selectedClip?.hasLockedPair == true
        ) {
        case "import":
            presentImporter()
            return true
        case "idt":
            requestInspectorScroll(Self.inspectorPairedIDTAnchor)
            return true
        case "grade":
            focusGradeControls()
            return true
        default:
            return false
        }
    }

    func requestInspectorScroll(_ anchor: String) {
        inspectorScrollTarget = anchor
        inspectorScrollToken += 1
    }

    /// 写出说明上的当前预览帧，和监视器同一幅时才放。
    /// 看调色前、HDR、709 关、高级 EXR 都不把监视器那一幅当成将写出的画面。
    /// 不另存一套调色，不猜色温，不猜帧率。
    var deliverPreviewGlance: DeliverPreviewGlance {
        Self.makeDeliverPreviewGlance(
            hasSelection: selectedClip != nil,
            selectedLocked: selectedClip?.hasLockedPair == true,
            gradeBefore: previewShowsGradeBefore,
            comparing: monitorLayout == .compare,
            odt: graph.odt,
            format: settings.exportFormat,
            hasPicture: preview.odtImage != nil
        )
    }

    /// 小图下的文件名和帧数。静帧不写帧率。读不到范围时只写第几帧，不猜 24 或 30。
    var deliverPreviewFrameLabel: String {
        guard let clip = selectedClip else { return "" }
        return Self.deliverPreviewFrameLabel(
            filename: clip.filename,
            isStill: clip.isStill,
            frameIndex: previewFrameIndex,
            lastFrame: previewScrubLastFrame
        )
    }

    static func deliverPreviewFrameLabel(
        filename: String,
        isStill: Bool,
        frameIndex: Int,
        lastFrame: Int?
    ) -> String {
        if isStill {
            return "\(filename) · 静帧"
        }
        let shown = frameIndex + 1
        if let lastFrame {
            return "\(filename) · 第 \(shown) / 共 \(lastFrame + 1) 帧"
        }
        return "\(filename) · 第 \(shown) 帧"
    }

    /// The write sheet may show the monitor frame only when that frame is the
    /// Rec.709 picture default ProRes bakes. 调色前 drops exposure and white
    /// balance. HDR and a closed 709 pane are a different picture. EXR is
    /// ACES2065-1 with this grade, not the monitor. Does not guess a temperature.
    static func makeDeliverPreviewGlance(
        hasSelection: Bool,
        selectedLocked: Bool,
        gradeBefore: Bool,
        comparing: Bool,
        odt: ODTMode,
        format: ExportFormat,
        hasPicture: Bool
    ) -> DeliverPreviewGlance {
        if !hasSelection {
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "先点一条。写出仍用检查器里这一套。",
                barCaution: nil
            )
        }
        if !selectedLocked {
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "当前这条还没锁定，不会写出。已锁定的会套上上面这一套。",
                barCaution: nil
            )
        }
        if gradeBefore {
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "监视器正在看调色前，这一幅不含曝光和白平衡。写出仍用上面这一套，不是调色前。",
                barCaution: "监视器在看调色前。写出仍是检查器里这一套。"
            )
        }
        if format == .exrACES2065 {
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "高级 EXR 写出的是套上这一套的 ACES2065-1，不是监视器上这一幅。仅预览。",
                barCaution: "高级 EXR 不是监视器这一幅。写出的是套上这一套的 ACES2065-1。"
            )
        }
        if odt.isHDR {
            let name = odt == .hlg ? "HLG" : "PQ"
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "这次监视器是 \(name)。默认 ProRes 仍按 Rec.709 写出这一套，不是这一幅 HDR。仅预览。",
                barCaution: "这次是 \(name) 预览。ProRes 仍按 Rec.709 写出这一套。"
            )
        }
        if odt == .off {
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "709 预览关。写出的 ProRes 仍按 Rec.709 套上这一套。仅预览。",
                barCaution: "709 预览关。ProRes 仍按 Rec.709 写出这一套。"
            )
        }
        if comparing {
            let note = hasPicture
                ? "对照时这一小图是右幅。写出按这一套的 Rec.709，不是左幅调色前。已锁定的每一条都套这一套，每条仍用自己的成对 IDT。预览长边会缩小，写出是片源尺寸。仅预览。"
                : "对照时右幅才是这一套，这一帧还没有画面。写出按这一套的 Rec.709，不是左幅调色前。"
            return DeliverPreviewGlance(
                showStill: hasPicture,
                sheetNote: note,
                barCaution: "对照时写出是右幅这一套，不是左幅调色前。"
            )
        }
        if !hasPicture {
            return DeliverPreviewGlance(
                showStill: false,
                sheetNote: "这一帧还没有画面。写出仍用上面这一套。预览长边会缩小，写出是片源尺寸。仅预览。",
                barCaution: nil
            )
        }
        return DeliverPreviewGlance(
            showStill: true,
            sheetNote: "当前这条这一帧，和监视器同一幅。默认 ProRes 按这一套的 Rec.709 写出。已锁定的每一条都套这一套，每条仍用自己的成对 IDT。预览长边会缩小，写出是片源尺寸。仅预览，不是最终画面。",
            barCaution: nil
        )
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

    /// Last path component only. The write sheet names the folder, not the whole path.
    /// Nil when nothing was remembered. Does not invent a folder name.
    static func exportFolderResumeName(from url: URL?) -> String? {
        guard let url else { return nil }
        let name = url.lastPathComponent
        if name.isEmpty || name == "/" || name == "." || name == ".." { return nil }
        return name
    }

    /// Where the next folder panel opens. A missing name means the system location.
    /// The caller still says cancel writes nothing. Does not change the grade.
    static func exportFolderOpenNote(folderName: String?) -> String {
        if let folderName, !folderName.isEmpty {
            return "选文件夹会从上次写出的文件夹打开：\(folderName)。"
        }
        return "还没有上次写出的文件夹，或那个文件夹已经不在了。选文件夹从系统给出的位置打开。"
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
        // Same folder the sheet just named. Gone folders stay nil, so the name is not invented.
        let remembered = settings.lastExportDirectoryURL
        let resumeName = Self.exportFolderResumeName(from: remembered)
        // Default ProRes 422 HQ; EXR remains advanced. The size note follows that choice.
        panel.message = Self.folderPickerMessage(format: format)
            + estimate.pickerSuffix
            + "\n"
            + Self.exportFolderOpenNote(folderName: resumeName)
            + "取消则不写出。"
        if let remembered {
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
        guard assignLockedPair(id, idt) else { return }
        // Stay on this clip so the preview shows the pair just chosen.
        // 下一条待选 is explicit. Mid-write does not move selection. Does not lock the next IDT.
        refreshPreview()
        // Last pending clip in this window: the next step is the grade.
        // Other pending clips stay on the pair list. Numbers and the frame stay.
        if id == selectedID,
           let anchor = Self.inspectorScrollAfterLock(
            pendingRemain: pendingClipCount > 0,
            blocked: isWritingDeliverables
                || openingExportFolder
                || showSettings
                || showImporter
                || showDeliverSheet
           ) {
            requestInspectorScroll(anchor)
        }
    }

    /// Writes this pair onto one clip. Does not move the selection or the frame,
    /// and does not refresh the monitor. A run of clips calls this, then refreshes once.
    /// Does not change exposure or white balance.
    @discardableResult
    private func assignLockedPair(_ id: UUID, _ idt: IDT) -> Bool {
        guard let idx = clips.firstIndex(where: { $0.id == id }) else { return false }
        closeSharedGradeStroke()
        clips[idx].idt = idt
        clips[idx].detectedCurve = idt.curve
        clips[idx].detectedGamut = idt.gamut
        clips[idx].detectionSource = .user
        clips[idx].needsUserPicker = false
        clips[idx].detectionNote = "用户选择成对 IDT"
        preview.invalidateIDT(clipID: id)
        if !keepingFollowingPairNote, !followingPairApplyNote.isEmpty {
            followingPairApplyNote = ""
        }
        return true
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

    /// Short paired lists only: no search field, at most ``IDT.pairListShowsSearchAfter`` rows.
    /// That is the detected S-Log3 / C-Log2 / C-Log3 choice, not the whole catalog.
    /// Digit 1…n locks that row and stays on this clip. A longer list has no digit,
    /// so 1 never locks the first row of the full table and does not guess a pair.
    /// Does not edit exposure, white balance, or the preview frame.
    /// Already this pair: leave playback and the frame. A new pair stops playback.
    func canLockShortListPair(at oneBased: Int) -> Bool {
        guard oneBased >= 1, oneBased <= IDT.pairListShowsSearchAfter else { return false }
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder,
              let clip = selectedClip
        else { return false }
        let pairs = clip.pickerPairs
        guard pairs.count <= IDT.pairListShowsSearchAfter, oneBased <= pairs.count else { return false }
        return !pairs[oneBased - 1].isStub
    }

    /// Same lock as clicking that short-list row. Text fields keep the digits.
    @discardableResult
    func lockShortListPair(at oneBased: Int) -> Bool {
        guard canLockShortListPair(at: oneBased), let clip = selectedClip else { return false }
        let pair = clip.pickerPairs[oneBased - 1]
        if clip.idt == pair, clip.hasLockedPair { return true }
        stopPreviewPlayback()
        setIDT(clip.id, pair)
        return true
    }

    /// Next pending clip after this one, wrapping once. Does not lock an IDT.
    private func nextPendingClip(after id: UUID) -> Clip? {
        guard let currentIdx = clips.firstIndex(where: { $0.id == id }) else { return nil }
        if let next = clips.dropFirst(currentIdx + 1).first(where: { !$0.hasLockedPair }) {
            return next
        }
        return clips.first(where: { $0.id != id && !$0.hasLockedPair })
    }

    /// Shown when the next pending clip's own pair list does not contain this pair.
    /// Does not skip ahead to a later clip, and does not pick for it.
    var applyPairToNextPendingNote: String? {
        guard !canApplyLockedPairToNextPending else { return nil }
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder,
              selectedClip?.hasLockedPair == true,
              pendingClipCount > 0
        else { return nil }
        return "下一条待选的列表里没有这一对。不替它选。"
    }

    /// The current locked pair may be written onto the next pending clip
    /// only when that clip's picker already lists the pair.
    var canApplyLockedPairToNextPending: Bool {
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder,
              let clip = selectedClip,
              clip.hasLockedPair,
              let idt = clip.idt,
              !idt.isStub,
              let next = nextPendingClip(after: clip.id)
        else { return false }
        return next.pickerPairs.contains(idt)
    }

    /// Write this pair onto the next pending clip and stay there for the preview.
    /// Does not change exposure or white balance. Does not skip a clip whose list lacks the pair.
    func applyLockedPairToNextPending() {
        guard canApplyLockedPairToNextPending,
              let clip = selectedClip,
              let idt = clip.idt,
              let next = nextPendingClip(after: clip.id)
        else { return }
        stopPreviewPlayback()
        selectedID = next.id
        noteSelectionForSharedGrade(next)
        setIDT(next.id, idt)
    }

    struct FollowingPairRow {
        var id: UUID
        var pending: Bool
        var listsPair: Bool
    }

    struct FollowingPairApplyPlan {
        var lockIDs: [UUID]
        var landOn: UUID?
    }

    /// Clips after this one, in list order. Already-locked rows are skipped.
    /// A pending row is included only while its own list contains this pair.
    /// The first pending row that does not stops the run. Does not wrap.
    /// An empty lock list means do not move. Does not guess a pair.
    static func followingPairApply(rows: [FollowingPairRow], after start: UUID) -> FollowingPairApplyPlan {
        guard let startIndex = rows.firstIndex(where: { $0.id == start }) else {
            return FollowingPairApplyPlan(lockIDs: [], landOn: nil)
        }
        var lockIDs: [UUID] = []
        var index = startIndex + 1
        while index < rows.count {
            let row = rows[index]
            if !row.pending {
                index += 1
                continue
            }
            if row.listsPair {
                lockIDs.append(row.id)
                index += 1
                continue
            }
            if lockIDs.isEmpty {
                return FollowingPairApplyPlan(lockIDs: [], landOn: nil)
            }
            return FollowingPairApplyPlan(lockIDs: lockIDs, landOn: row.id)
        }
        guard let last = lockIDs.last else {
            return FollowingPairApplyPlan(lockIDs: [], landOn: nil)
        }
        return FollowingPairApplyPlan(lockIDs: lockIDs, landOn: last)
    }

    /// The plan for the selected clip's locked pair. Empty when it cannot run.
    private func currentFollowingPairApply() -> FollowingPairApplyPlan {
        guard let clip = selectedClip,
              clip.hasLockedPair,
              let idt = clip.idt,
              !idt.isStub
        else {
            return FollowingPairApplyPlan(lockIDs: [], landOn: nil)
        }
        let rows = clips.map { item in
            FollowingPairRow(
                id: item.id,
                pending: !item.hasLockedPair,
                listsPair: item.pickerPairs.contains(idt)
            )
        }
        return Self.followingPairApply(rows: rows, after: clip.id)
    }

    /// Same gates as writing the pair onto the next pending clip.
    /// Enabled only when at least one later pending clip already lists this pair,
    /// with no pending clip in between whose list lacks it.
    var canApplyLockedPairToFollowingPending: Bool {
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder
        else { return false }
        return !currentFollowingPairApply().lockIDs.isEmpty
    }

    /// Why the forward run is grey while the single next-clip action may still work.
    /// Nil when the next pending clip itself lacks the pair: that note already says so.
    /// Does not guess a pair and does not wrap backward.
    var followingPairApplyBlockedNote: String? {
        guard !isWritingDeliverables,
              !showSettings,
              !showImporter,
              !showDeliverSheet,
              !openingExportFolder,
              selectedClip?.hasLockedPair == true,
              pendingClipCount > 0,
              !canApplyLockedPairToFollowingPending
        else { return nil }
        guard applyPairToNextPendingNote == nil else { return nil }
        return "后面没有待选。这一对不往回写。"
    }

    /// Write this pair onto each later pending clip whose own list contains it,
    /// until one does not. Stay on the last clip written, or on the clip that stopped
    /// the run. Does not wrap. Does not change exposure or white balance.
    /// Does not start a write. Playback stops. The landed clip's preview starts over.
    func applyLockedPairToFollowingPending() {
        guard canApplyLockedPairToFollowingPending,
              let clip = selectedClip,
              let idt = clip.idt,
              !idt.isStub
        else { return }
        let plan = currentFollowingPairApply()
        guard !plan.lockIDs.isEmpty, let land = plan.landOn else { return }
        keepingFollowingPairNote = true
        defer { keepingFollowingPairNote = false }
        stopPreviewPlayback()
        for id in plan.lockIDs {
            _ = assignLockedPair(id, idt)
        }
        selectedID = land
        if let landed = clips.first(where: { $0.id == land }) {
            noteSelectionForSharedGrade(landed)
        }
        revealSelectedClipInList()
        refreshPreview()
        if clips.first(where: { $0.id == land })?.hasLockedPair == true,
           let anchor = Self.inspectorScrollAfterLock(
            pendingRemain: pendingClipCount > 0,
            blocked: isWritingDeliverables
                || openingExportFolder
                || showSettings
                || showImporter
                || showDeliverSheet
           ) {
            requestInspectorScroll(anchor)
        }
        let count = plan.lockIDs.count
        if clips.first(where: { $0.id == land })?.hasLockedPair == true {
            followingPairApplyNote = "已把这一对写到后面 \(count) 条。停在最后这一条看预览。"
        } else {
            followingPairApplyNote = "已把这一对写到后面 \(count) 条。这一条的列表里没有这一对，停在这里，不替它选。"
        }
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

    /// `+0.50`, `0.5`, or `0.5档`. Rounded to 0.01. Outside −8…+8 is refused.
    /// Does not invent a stop, and does not turn exposure on.
    /// File-private: the result type stays private to this file.
    fileprivate static func parseTypedExposureStops(_ text: String) -> TypedGradeField {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return .empty }
        var body = trimmed
        if body.hasSuffix("档") {
            body = String(body.dropLast()).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        if body.isEmpty { return .unrecognized }
        guard let value = Double(body), value.isFinite else { return .unrecognized }
        let rounded = (value * 100).rounded() / 100
        if rounded < -8 || rounded > 8 { return .outOfRange }
        return .value(rounded)
    }

    /// One step on the shared exposure. Same graph as the slider.
    /// A bad string leaves the stops alone. Playback frame stays.
    @discardableResult
    func applyTypedExposureStops(_ text: String) -> Bool {
        guard canNudgeExposure else { return false }
        switch Self.parseTypedExposureStops(text) {
        case .empty:
            typedExposureNote = "先写出档，如 +0.50"
            return false
        case .unrecognized:
            typedExposureNote = "认不出这个档"
            return false
        case .outOfRange:
            typedExposureNote = "档要在 −8 到 +8"
            return false
        case .value(let stops):
            typedExposureNote = ""
            closeSharedGradeStroke()
            setExposureStops(stops)
            closeSharedGradeStroke()
            return true
        }
    }

    /// White balance is on, and no sheet is up. An empty temperature can still be typed.
    /// Does not turn white balance on, and does not start from a stand-in temperature.
    var canTypeWBCCT: Bool {
        graph.wbEnabled
            && !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
    }

    /// `4500` or `4500 K`, nearest integer. Outside 2000…10000 is refused.
    /// File-private: the result type stays private to this file.
    fileprivate static func parseTypedWBCCT(_ text: String) -> TypedGradeField {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return .empty }
        var body = trimmed
        if body.hasSuffix("K") || body.hasSuffix("k") {
            body = String(body.dropLast()).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        if body.isEmpty { return .unrecognized }
        guard let value = Double(body), value.isFinite else { return .unrecognized }
        let rounded = value.rounded()
        if rounded < 2000 || rounded > 10000 { return .outOfRange }
        return .value(rounded)
    }

    /// One step on the shared color temperature. Same graph as the slider.
    /// Filling an empty temperature is the typed number, not a guess.
    /// The same number again does not change the source chip.
    @discardableResult
    func applyTypedWBCCT(_ text: String) -> Bool {
        guard canTypeWBCCT else { return false }
        switch Self.parseTypedWBCCT(text) {
        case .empty:
            typedCCTNote = "先写出色温，如 4500"
            return false
        case .unrecognized:
            typedCCTNote = "认不出这个色温"
            return false
        case .outOfRange:
            typedCCTNote = "色温要在 2000 到 10000"
            return false
        case .value(let cct):
            typedCCTNote = ""
            if graph.wbCCT == cct { return true }
            closeSharedGradeStroke()
            setWBParams(cct: cct)
            closeSharedGradeStroke()
            return true
        }
    }

    /// Green–magenta can be typed only when a color temperature is already set.
    /// Same gate as the tint step. Does not turn white balance on, and does not invent a temperature.
    var canTypeWBTint: Bool { canNudgeWBTint }

    /// `+1.5`, `1.5`, or `1.5绿品`. Rounded to 0.1. Outside −10…+10 is refused.
    /// Does not invent a tint, and does not turn white balance on.
    /// File-private: the result type stays private to this file.
    fileprivate static func parseTypedWBTint(_ text: String) -> TypedGradeField {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return .empty }
        var body = trimmed
        if body.hasSuffix("绿品") {
            body = String(body.dropLast(2)).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        if body.isEmpty { return .unrecognized }
        guard let value = Double(body), value.isFinite else { return .unrecognized }
        let rounded = (value * 10).rounded() / 10
        if rounded < -10 || rounded > 10 { return .outOfRange }
        return .value(rounded)
    }

    /// One step on the shared tint. Color temperature stays.
    /// The same number again does not change the source chip.
    /// A bad string leaves the tint alone. Playback frame stays.
    @discardableResult
    func applyTypedWBTint(_ text: String) -> Bool {
        guard canTypeWBTint else { return false }
        switch Self.parseTypedWBTint(text) {
        case .empty:
            typedTintNote = "先写出绿品，如 +1.5"
            return false
        case .unrecognized:
            typedTintNote = "认不出这个绿品"
            return false
        case .outOfRange:
            typedTintNote = "绿品要在 −10 到 +10"
            return false
        case .value(let tint):
            typedTintNote = ""
            if abs(graph.wbTint - tint) <= 1e-9 { return true }
            closeSharedGradeStroke()
            setWBParams(tint: tint)
            closeSharedGradeStroke()
            return true
        }
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

    /// List edits are closed while writing, while a sheet is up, or while the
    /// folder panel is on its way. The source file is never touched.
    var canRemoveClipsFromSession: Bool {
        !clips.isEmpty
            && !isWritingDeliverables
            && !showSettings
            && !showImporter
            && !showDeliverSheet
            && !openingExportFolder
    }

    /// File menu. Needs a selected row. Same gate as taking any row off the list.
    var canRemoveSelectedClip: Bool {
        canRemoveClipsFromSession && selectedID != nil
    }

    /// Delete / Backspace, the File menu, or the row menu: drop a clip from
    /// the SESSION only. Does not trash or move the source file. Does not
    /// remove an already-written `_proxy` — leave it on disk; just drop the row.
    /// `clipID` nil drops the selected row. Another row leaves the selection.
    /// Dropping the selected row selects next, else previous.
    /// #40: evict that clip's preview cache. The list picture goes with the row.
    /// Mid-write: ignore — do not change selection, do not cancel
    /// (Escape cancels). Text / numeric / search fields keep Delete
    /// unless the menu set `respectTextInput` to false.
    /// No confirm sheet. No extra button in the row chrome.
    /// Does not edit the shared grade or any paired IDT.
    @discardableResult
    func removeSelectedClipFromSession(clipID: UUID? = nil, respectTextInput: Bool = true) -> Bool {
        if respectTextInput, Self.isArrowConsumedByTextInput() { return false }
        guard canRemoveClipsFromSession else { return false }
        guard let id = clipID ?? selectedID, let idx = clips.firstIndex(where: { $0.id == id }) else {
            return false
        }
        let removedWasSelected = selectedID == id
        // Session list only. Source file and any already-written `_proxy` stay.
        if removedWasSelected {
            stopPreviewPlayback()
        }
        clips.remove(at: idx)
        preview.evict(clipID: id)
        posters.drop(id: id)
        guard removedWasSelected else { return true }
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
        typedExposureNote = ""
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
            typedCCTNote = ""
            graph.wbCCT = cct
            graph.wbSource = .user
        }
        if let tint {
            typedTintNote = ""
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
        guard !openingExportFolder, !showImporter else { return }
        closeSharedGradeStroke()
        stopPreviewPlayback()
        activeSheet = .settings
        showSettings = true
        showDeliverSheet = false
    }

    /// Add panel, stuck to this window. Starts in the last imported folder.
    /// Cancel reads nothing and leaves the list, the selection, and the grade.
    /// The same flag blocks the write sheet from opening on top of it.
    func presentImporter() {
        guard !openingExportFolder, !showImporter, !showSettings, !showDeliverSheet, !isWritingDeliverables else {
            return
        }
        closeSharedGradeStroke()
        showImporter = true
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        panel.canCreateDirectories = false
        panel.prompt = "添加"
        panel.message = "选素材或文件夹。面板贴在这个窗口上。取消则不读入。同一文件不会另加一行。"
        if let remembered = settings.lastImportDirectoryURL {
            panel.directoryURL = remembered
        }
        let finish: (NSApplication.ModalResponse) -> Void = { [weak self] response in
            guard let self else { return }
            self.showImporter = false
            guard response == .OK else { return }
            let urls = panel.urls
            guard !urls.isEmpty else { return }
            self.handleImporter(.success(urls))
        }
        if let window = Self.exportFolderHostWindow() {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate()
            panel.beginSheetModal(for: window, completionHandler: finish)
        } else {
            panel.begin(completionHandler: finish)
        }
    }

    /// A skipped row on the write sheet can leave for that clip's paired list.
    /// A locked row, a write in progress, and the folder panel stay on the sheet.
    /// Does not pick a pair and does not start writing.
    static func canLeaveWriteSheetForSkippedClip(
        sheetOpen: Bool,
        writing: Bool,
        openingFolder: Bool,
        hasLockedPair: Bool
    ) -> Bool {
        sheetOpen && !writing && !openingFolder && !hasLockedPair
    }

    /// Close the write sheet and stay on this skipped clip.
    /// The inspector scrolls to the paired list. This does not lock a pair.
    /// The same clip keeps its preview frame. Another clip follows the list tap:
    /// the preview starts at that clip's first frame. A filter or query that hides
    /// the row is widened, same as 「显示这条」. Does not start writing.
    @discardableResult
    func focusSkippedClipFromWriteSheet(_ id: UUID) -> Bool {
        guard let clip = clips.first(where: { $0.id == id }) else { return false }
        guard Self.canLeaveWriteSheetForSkippedClip(
            sheetOpen: showDeliverSheet,
            writing: isWritingDeliverables,
            openingFolder: openingExportFolder,
            hasLockedPair: clip.hasLockedPair
        ) else { return false }
        deliverSheetConfirmed = false
        showDeliverSheet = false
        stopPreviewPlayback()
        selectedID = id
        requestInspectorScroll(Self.inspectorPairedIDTAnchor)
        revealSelectedClipInList()
        return true
    }

    /// The line under the monitor. Same sheet as 写出 and ⌘E.
    /// Does not open the folder panel and does not start writing.
    /// Playback stops. The frame, the pair, and this grade stay.
    @discardableResult
    func openWriteSheetFromMonitorLine() -> Bool {
        guard canStartWriteFromLoop, selectedClip?.hasLockedPair == true else { return false }
        presentDeliverSheet()
        return true
    }

    /// Write sheet. Folder panel opens only after this sheet has gone.
    func presentDeliverSheet() {
        guard !isWritingDeliverables, !openingExportFolder, !showImporter else { return }
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

    /// True when the filename query would hide at least one clip from this drop.
    static func importQueryHidesNewRow(_ query: String, built: [Clip]) -> Bool {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if needle.isEmpty { return false }
        return built.contains { !clipMatchesListQuery($0, query: needle) }
    }

    /// Multi-file refuse list. Header when more than one skip. Per-file chips unchanged.
    static func importSkipSummary(_ skipped: [String]) -> String {
        guard skipped.count > 1 else {
            return skipped.joined(separator: "\n")
        }
        return "未导入 \(skipped.count) 条：\n" + skipped.joined(separator: "\n")
    }

    /// One file, one row. A symlink and its target share this path.
    /// Does not assign an IDT and does not touch the grade.
    static func clipIdentityPath(_ url: URL) -> String {
        url.standardizedFileURL.resolvingSymlinksInPath().path
    }

    /// True when this path is already in the window, or already accepted in this drop.
    static func importPathIsAlreadyKept(
        _ url: URL,
        existingPaths: Set<String>,
        acceptedThisDrop: Set<String>
    ) -> Bool {
        let path = clipIdentityPath(url)
        return existingPaths.contains(path) || acceptedThisDrop.contains(path)
    }

    /// Sidebar line when a drop repeats a file that is staying in the list.
    /// Empty when nothing was repeated. Does not invent a color temperature.
    static func importDuplicateNote(count: Int) -> String {
        guard count > 0 else { return "" }
        return "同一文件 \(count) 条已经在列表里，没有另加一行。"
    }

    func importURL(_ url: URL) {
        stopPreviewPlayback()
        // Keep the security scope for the session so preview decode can reopen the URL.
        _ = url.startAccessingSecurityScopedResource()
        if let dir = Self.directoryToRememberAfterImport(url) {
            settings.rememberImportDirectory(dir)
        }
        lastImportNote = "正在读入…"
        let existingPaths = Set(clips.map { Self.clipIdentityPath($0.url) })
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let files = Self.expandToClipURLs(url)
            var skipped: [String] = []
            var built: [Clip] = []
            var alreadyListed = 0
            var acceptedThisDrop: Set<String> = []
            var refusedThisDrop: Set<String> = []
            for file in files {
                let path = Self.clipIdentityPath(file)
                if Self.importPathIsAlreadyKept(
                    file,
                    existingPaths: existingPaths,
                    acceptedThisDrop: acceptedThisDrop
                ) {
                    alreadyListed += 1
                    continue
                }
                // A second copy of a file this drop already refused stays one chip.
                if refusedThisDrop.contains(path) {
                    continue
                }
                let probe = MediaFormat.probe(url: file)
                if probe.decision == .refuse {
                    refusedThisDrop.insert(path)
                    skipped.append("\(file.lastPathComponent)：\(probe.note)")
                    continue
                }
                if probe.decision == .tryDecode {
                    // MXF: only keep if the system can open a video track.
                    if MediaFormat.codecFourCC(url: file) == nil {
                        refusedThisDrop.insert(path)
                        skipped.append("\(file.lastPathComponent)：\(MediaFormat.noteMxfNoTrack)")
                        continue
                    }
                }
                let detection = ClipDetector.detect(url: file)
                let extent = MediaFormat.extent(url: file)
                // Never silently assign an IDT. S-Log3 without gamut stays nil.
                let shot = detection.asShotCCT
                acceptedThisDrop.insert(path)
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
                // A parallel drop may have listed this path while we were probing.
                var kept = Set(self.clips.map { Self.clipIdentityPath($0.url) })
                var added: [Clip] = []
                var repeated = alreadyListed
                for clip in built {
                    let path = Self.clipIdentityPath(clip.url)
                    if kept.contains(path) {
                        repeated += 1
                        continue
                    }
                    kept.insert(path)
                    self.clips.append(clip)
                    added.append(clip)
                }
                // After drop/import: first pending/unlocked so 待选 is obvious.
                // All-locked keeps first / existing selection. Does not lock IDT.
                // A drop that only repeats files leaves the selection where it is.
                if let pending = added.first(where: { !$0.hasLockedPair }) {
                    self.selectedID = pending.id
                    self.noteSelectionForSharedGrade(pending)
                } else if self.selectedID == nil, let first = added.first {
                    self.selectedID = first.id
                    self.noteSelectionForSharedGrade(first)
                }
                // A 待选 / 已锁定 filter must not hide the rows that just arrived.
                if !added.isEmpty, Self.importFilterHidesNewRow(self.clipListFilter, built: added) {
                    self.clipListFilter = .all
                }
                // A filename query must not hide them either. A query that still
                // matches every new row stays, so the list does not jump open.
                if !added.isEmpty, Self.importQueryHidesNewRow(self.clipListQuery, built: added) {
                    self.clipListQuery = ""
                }
                let needsPicker = added.contains { !$0.hasLockedPair }
                var note = Self.importArrivalNote(imported: added.count, needsPicker: needsPicker)
                if added.isEmpty, skipped.isEmpty, repeated == 0 {
                    note = Self.importEmptyNote()
                }
                if repeated > 0 {
                    let dup = Self.importDuplicateNote(count: repeated)
                    note = note.isEmpty ? dup : note + "\n" + dup
                }
                if !skipped.isEmpty {
                    let skips = Self.importSkipSummary(skipped)
                    note = note.isEmpty ? skips : note + "\n" + skips
                }
                self.lastImportNote = note
                if self.settings.promptEstimateWBOnImport {
                    let locked = added.contains { $0.hasLockedPair }
                    let hint = "可点「估计白平衡」查看估计，确认后才写入。不是校准，不猜 5600。"
                    if locked {
                        self.lastImportNote = (self.lastImportNote.isEmpty ? hint : self.lastImportNote + "\n" + hint)
                    }
                }
                // Repeats do not decode again, so the current frame stays up.
                if !added.isEmpty {
                    self.refreshPreview()
                }
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

    /// Where the next 添加 panel opens. A folder is kept as itself.
    /// A file keeps its parent. A missing path keeps nothing.
    /// Does not assign an IDT and does not touch the grade.
    static func directoryToRememberAfterImport(_ url: URL) -> URL? {
        let standard = url.standardizedFileURL
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: standard.path, isDirectory: &isDir) else {
            return nil
        }
        if isDir.boolValue {
            return standard
        }
        let parent = standard.deletingLastPathComponent()
        var parentIsDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: parent.path, isDirectory: &parentIsDir),
              parentIsDir.boolValue else {
            return nil
        }
        return parent
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
