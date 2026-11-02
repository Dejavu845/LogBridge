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
                Button("添加…") { session.showImporter = true }
                    .controlSize(.regular)
                Button("设置") { session.presentSettings() }
                    .controlSize(.regular)
            }
            .padding(.horizontal, 12)
            .padding(.top, 12)
            .padding(.bottom, 8)

            DropZone(targeted: session.dropTargeted, empty: session.clips.isEmpty) {
                session.showImporter = true
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)

            if !session.lastImportNote.isEmpty {
                Text(session.lastImportNote)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 6)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        ForEach(session.clips) { clip in
                            ClipRow(
                                clip: clip,
                                selected: session.selectedID == clip.id,
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
            }
        }
        .background(Color.primary.opacity(0.02))
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
