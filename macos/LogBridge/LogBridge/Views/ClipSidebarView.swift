import SwiftUI

/// Media list. Drop zone + rows. Badge is never a finished-picture claim.
/// 待选 / 已锁定 stay glanceable. No lock button — the paired IDT picker locks.
struct ClipSidebarView: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("素材")
                    .font(.title3.weight(.semibold))
                Text(session.clips.isEmpty ? "没有素材" : "\(session.clips.count) 条")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("添加…") { session.presentImporter() }
                    .controlSize(.regular)
                    .disabled(session.openingExportFolder)
                Button("设置") { session.presentSettings() }
                    .controlSize(.regular)
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
                        Text(item.label).tag(item)
                    }
                }
                .pickerStyle(.segmented)
                .controlSize(.small)
                .labelsHidden()
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
                .help("全部 \(session.clips.count) 条，待选 \(session.pendingClipCount) 条，已锁定 \(session.lockedClipCount) 条。筛选只收列表，不改当前这一套调色。")
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
                            Text(session.clipListFilter == .pending
                                 ? "没有待选。成对 IDT 都已选上。"
                                 : "没有已锁定。先在检查器选成对 IDT。")
                                .font(.callout)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 8)
                        } else if let clip = session.selectedClip,
                                  !session.visibleClips.contains(where: { $0.id == clip.id }) {
                            Text("当前这条不在这个筛选里。监视器不跟着筛选换。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 4)
                                .padding(.bottom, 4)
                        }
                        ForEach(session.visibleClips) { clip in
                            ClipRow(
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
    }
}

struct ClipRow: View {
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
