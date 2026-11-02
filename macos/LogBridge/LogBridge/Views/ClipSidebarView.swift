import SwiftUI
import AppKit

/// First-frame pictures for the bin and the inspector.
/// Camera-log source only: not the grade, not a deliverable, not written to disk.
/// Separate from the monitor cache, which keeps only the selected clip.
/// Selection and scrub do not replace these. A removed row drops its picture.
final class ClipPosterCache: ObservableObject {
    /// Smaller than the monitor long edge. The list only needs a glance.
    static let longEdge: CGFloat = 160
    /// Visible rows stay. Scrolling back decodes that row again.
    static let keptCount = 80

    @Published private(set) var images: [UUID: CGImage] = [:]
    @Published private(set) var failures: [UUID: String] = [:]

    private let queue = DispatchQueue(label: "app.logbridge.posters", qos: .utility)
    private var inflight: Set<UUID> = []
    private var alive: Set<UUID> = []
    private var order: [UUID] = []

    /// First frame only. In memory. Does not grade and does not write a file.
    func request(id: UUID, url: URL) {
        if images[id] != nil || failures[id] != nil || inflight.contains(id) { return }
        inflight.insert(id)
        alive.insert(id)
        queue.async { [weak self] in
            let outcome = Self.decodeFirstFrame(url: url)
            DispatchQueue.main.async {
                self?.finish(id: id, outcome: outcome)
            }
        }
    }

    func drop(id: UUID) {
        alive.remove(id)
        inflight.remove(id)
        if images[id] != nil {
            var next = images
            next[id] = nil
            images = next
        }
        if failures[id] != nil {
            var next = failures
            next[id] = nil
            failures = next
        }
        order.removeAll { $0 == id }
    }

    private func finish(id: UUID, outcome: Result<CGImage, PosterDecodeFailure>) {
        inflight.remove(id)
        guard alive.contains(id) else { return }
        switch outcome {
        case .success(let image):
            var next = images
            next[id] = image
            images = next
            order.removeAll { $0 == id }
            order.append(id)
            evictIfNeeded()
        case .failure(let failure):
            var next = failures
            next[id] = failure.note
            failures = next
        }
    }

    private func evictIfNeeded() {
        guard order.count > Self.keptCount else { return }
        var next = images
        while order.count > Self.keptCount {
            let old = order.removeFirst()
            next[old] = nil
        }
        images = next
    }

    /// Same first-frame decode as the source pane. frameIndex stays 0, so a
    /// missing frame rate is not invented and the picture does not follow the scrub.
    private static func decodeFirstFrame(url: URL) -> Result<CGImage, PosterDecodeFailure> {
        do {
            guard let image = try PreviewEngine.decodeDownscaled(
                url: url,
                maxLongEdge: longEdge,
                frameIndex: 0
            ) else {
                return .failure(PosterDecodeFailure(note: "解不出预览帧"))
            }
            return .success(image)
        } catch {
            return .failure(PosterDecodeFailure(note: PreviewEngine.userFacingFailureNote(error)))
        }
    }
}

/// Why a list picture did not decode. `Result` needs an `Error`, not a bare string.
private struct PosterDecodeFailure: Error {
    let note: String
}

/// Small source picture. The corner says 源 so it is not read as the grade.
struct ClipSourcePoster: View {
    @ObservedObject var session: SessionModel
    @ObservedObject var posters: ClipPosterCache
    let clip: Clip

    static let help = "这一小图是源（相机 Log）第一帧。静帧就是这一张。不是调色预览，不含曝光和白平衡，不参与写出。"

    var body: some View {
        tile
            .frame(width: 84, height: 48)
            .clipped()
            .clipShape(RoundedRectangle(cornerRadius: 4))
            .help(posters.failures[clip.id] ?? Self.help)
            .onAppear {
                session.requestClipPoster(id: clip.id, url: clip.url)
            }
            .onChange(of: session.isWritingDeliverables) { _, writing in
                if !writing {
                    session.requestClipPoster(id: clip.id, url: clip.url)
                }
            }
    }

    @ViewBuilder
    private var tile: some View {
        if let image = posters.images[clip.id] {
            ZStack(alignment: .bottomLeading) {
                Image(nsImage: NSImage(
                    cgImage: image,
                    size: NSSize(width: CGFloat(image.width), height: CGFloat(image.height))
                ))
                .resizable()
                .scaledToFill()
                Text("源")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 1)
                    .background(.black.opacity(0.55))
            }
        } else if posters.failures[clip.id] != nil {
            Text("没有画面")
                .font(.caption2)
                .foregroundStyle(.orange)
                .multilineTextAlignment(.center)
                .padding(4)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black.opacity(0.85))
        } else {
            Text("源")
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.white.opacity(0.85))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black.opacity(0.85))
        }
    }
}

/// Media list. Drop zone + rows. Badge is never a finished-picture claim.
/// 待选 / 已锁定 stay glanceable. No lock button — the paired IDT picker locks.
struct ClipSidebarView: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("素材")
                    .font(.title3.weight(.semibold))
                    .help("右键一条，或用菜单「文件」里的「从列表拿掉（不删文件）」，只从这一窗拿掉。源文件留在原处，已经写出的代理也不删。Delete 拿掉当前这条。不改这一套调色，也不改成对 IDT。")
                Text(session.clips.isEmpty ? "没有素材" : "\(session.clips.count) 条")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("添加…") { session.presentImporter() }
                    .controlSize(.regular)
                    .disabled(session.openingExportFolder || session.showImporter)
                Button("设置") { session.presentSettings() }
                    .controlSize(.regular)
                    .disabled(session.showImporter)
            }
            .padding(.horizontal, 12)
            .padding(.top, 12)
            .padding(.bottom, 8)

            DropZone(targeted: session.dropTargeted, empty: session.clips.isEmpty) {
                session.presentImporter()
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)

            if !session.clips.isEmpty {
                Picker("列表", selection: $session.clipListFilter) {
                    ForEach(ClipListFilter.allCases) { item in
                        Text(session.clipListFilterTitle(item)).tag(item)
                    }
                }
                .pickerStyle(.segmented)
                .controlSize(.small)
                .labelsHidden()
                .padding(.horizontal, 12)
                .padding(.bottom, 6)
                .help("每一段写出条数：全部、待选、已锁定。条数是这一窗的素材，查找不改这些数字。筛选只收列表。不改选中，不改这一套调色，不改成对 IDT，不改预览帧，也不参与写出。")
                if let line = session.clipListRemainderLine {
                    Text(line)
                        .font(.callout.weight(session.pendingClipCount > 0 ? .semibold : .regular))
                        .foregroundStyle(session.pendingClipCount > 0 ? Color.orange : Color.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 12)
                        .padding(.bottom, 8)
                        .help("还有待选时，点一条，到右侧选成对 IDT。都已锁定则可调色再写出。条数是这一窗的素材，查找不改这一行。不改选中，不改这一套调色，不改成对 IDT，不改预览帧，也不参与写出。")
                }
            }

            if !session.clips.isEmpty {
                HStack(spacing: 8) {
                    TextField("查找文件名", text: $session.clipListQuery)
                        .textFieldStyle(.roundedBorder)
                    if !listQueryIsBlank {
                        Button("清空") { session.clipListQuery = "" }
                            .controlSize(.regular)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
                .help("只收下面这一列。可输入文件名或所在文件夹。不改选中，不改这一套调色，也不改成对 IDT。在这个框里，上下方向键改文字，不换条。")
            }

            if !session.lastImportNote.isEmpty {
                Text(session.lastImportNote)
                    .font(.callout)
                    .foregroundStyle(importNoteIsProblem ? Color.orange : Color.secondary)
                    .lineLimit(6)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 6)
                    .help(session.lastImportNote)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        if !session.clips.isEmpty && session.visibleClips.isEmpty {
                            Text(emptyListNote)
                                .font(.callout)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 8)
                        }
                        if let clip = session.selectedClip,
                           !session.visibleClips.contains(where: { $0.id == clip.id }) {
                            Text(hiddenSelectionNote)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 4)
                                .padding(.bottom, 4)
                        }
                        ForEach(session.visibleClips) { clip in
                            ClipRow(
                                session: session,
                                clip: clip,
                                selected: session.selectedID == clip.id,
                                writing: session.writingClipID == clip.id,
                                onRevealWritten: { session.revealClipExportInFinder(clip) }
                            )
                            .id(clip.id)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                session.selectedID = clip.id
                                session.refreshPreview()
                            }
                            .contextMenu {
                                Button("从列表拿掉（不删文件）") {
                                    session.removeSelectedClipFromSession(
                                        clipID: clip.id,
                                        respectTextInput: false
                                    )
                                }
                                .disabled(!session.canRemoveClipsFromSession)
                            }
                        }
                    }
                    .padding(.horizontal, 8)
                    .padding(.bottom, 8)
                }
                .onChange(of: session.selectedID) { _, id in
                    if let id {
                        proxy.scrollTo(id, anchor: .center)
                    }
                }
                .onChange(of: session.writingClipID) { _, id in
                    if let id {
                        proxy.scrollTo(id, anchor: .center)
                    }
                }
            }
        }
        .background(Color.primary.opacity(0.02))
    }

    /// Skip and empty-folder notes are the failure of this drop. Arrival stays quiet.
    private var importNoteIsProblem: Bool {
        let note = session.lastImportNote
        return note.contains("未导入") || note.contains("没有能读")
    }

    private var listQueryIsBlank: Bool {
        session.clipListQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// Query wins over the lock filter, so an empty search is not read as 「没有已锁定」.
    private var emptyListNote: String {
        if !listQueryIsBlank {
            return "没有匹配的素材。清空查找再看列表。"
        }
        return session.clipListFilter == .pending
            ? "没有待选。成对 IDT 都已选上。"
            : "没有已锁定。先在检查器选成对 IDT。"
    }

    private var hiddenSelectionNote: String {
        if !listQueryIsBlank {
            return "当前这条不在查找里。监视器不跟着查找换。"
        }
        return "当前这条不在这个筛选里。监视器不跟着筛选换。"
    }
}

private struct DropZone: View {
    let targeted: Bool
    let empty: Bool
    let onTap: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: "square.and.arrow.down")
                    .font(empty ? .title2 : .body)
                Text(empty ? "把混源文件夹拖进来" : "把文件夹拖进来，或点这里添加")
                    .font(empty ? .headline : .caption.weight(.semibold))
            }
            if empty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("1  \(UICopy.EMPTY_STATE_STEP_1)")
                    Text("2  \(UICopy.EMPTY_STATE_STEP_2)")
                    Text("3  \(UICopy.EMPTY_STATE_STEP_3)")
                }
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                Text("已实现（未验证）")
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.orange.opacity(0.2))
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(empty ? 16 : 10)
        .background(targeted ? Color.accentColor.opacity(0.16) : Color.primary.opacity(0.04))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [6]))
                .foregroundStyle(targeted ? Color.accentColor : Color.secondary.opacity(0.45))
        )
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .contentShape(Rectangle())
        .onTapGesture {
            onTap()
        }
        .help("点这里或顶栏「添加…」，面板贴在这个窗口上，从上次的文件夹打开。取消则不读入。同一文件再拖一次，不另加一行。源文件留在原处。不改这一套调色，也不改成对 IDT。")
    }
}

struct ClipRow: View {
    @ObservedObject var session: SessionModel
    let clip: Clip
    var selected: Bool = false
    var writing: Bool = false
    var onRevealWritten: (() -> Void)? = nil

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            RoundedRectangle(cornerRadius: 2)
                .fill(clip.isPending ? Color.yellow.opacity(0.95) : Color.accentColor)
                .frame(width: 4)
                .padding(.vertical, 2)
            ClipSourcePoster(session: session, posters: session.posters, clip: clip)
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(clip.filename)
                        .font(clip.isPending ? .body : .body.weight(.semibold))
                        .foregroundStyle(clip.isPending ? Color.secondary : Color.primary)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    Text(clip.isPending ? "待选" : "已锁定")
                        .font(.caption.weight(clip.isPending ? .regular : .semibold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(clip.isPending ? Color.yellow.opacity(0.28) : Color.accentColor.opacity(0.16))
                        .foregroundStyle(clip.isPending ? Color.primary : Color.accentColor)
                        .clipShape(Capsule())
                }
                if !clip.folderName.isEmpty {
                    Text(clip.folderName)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .help("所在文件夹的名字。查找可按这个名字收列表。不是整条路径，不参与写出。")
                }
                Text(clip.lockedPairLabel)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                if let fact = clip.mediaFactLine {
                    Text(fact)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .help("片源读到的画面尺寸、帧率和时长。缺的不写，不猜帧率。静帧写静帧。不是预览缩小后的尺寸，不参与写出。")
                }
                if writing {
                    Text("正在写出")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.accentColor)
                        .lineLimit(1)
                        .help("这一条正在写出代理。监视器下那一行是同一条的文件名和帧数。不改这一套调色。")
                }
                if let reason = clip.processSkipReason {
                    Text(reason)
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .lineLimit(2)
                } else if let chip = clip.exportChip {
                    // 已写出代理 after a proxy write; failed write is a short Chinese error
                    if chip == SessionModel.wroteProxyChip {
                        Button(chip) { onRevealWritten?() }
                            .buttonStyle(.plain)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Color.secondary)
                            .lineLimit(1)
                            .help("在 Finder 中显示刚写出的代理。默认是 Rec.709 ProRes。高级 EXR 打开代理夹。失败的不打开。")
                        if let name = clip.writtenDeliverableName {
                            Text(name)
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                                .truncationMode(.middle)
                                .help("刚写出的文件名。点「已写出代理」在 Finder 中显示。整段代理，代理精度。")
                        }
                    } else {
                        Text(chip)
                            .font(.caption)
                            .foregroundStyle(Color.orange)
                            .lineLimit(2)
                    }
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(selected ? Color.accentColor.opacity(0.16) : Color.clear)
        )
    }
}
