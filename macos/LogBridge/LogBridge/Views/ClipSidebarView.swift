import SwiftUI

/// Drop zone + virtualized clip list. Badge is never "supported".
/// 待选 / 已锁定 are two glanceable states (type, weight, chip, left accent).
/// No lock button — existing paired-IDT picker stays the lock flow.
struct ClipSidebarView: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("素材")
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Button("添加…") { session.showImporter = true }
                    .controlSize(.small)
                Button("设置") { session.showSettings = true }
                    .controlSize(.small)
            }
            .padding(.horizontal, 12)
            .padding(.top, 12)
            .padding(.bottom, 8)

            DropZone(targeted: session.dropTargeted, empty: session.clips.isEmpty) {
                session.showImporter = true
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)

            Text("1 把混源文件夹拖进来  2 每条选成对 Log 与色域  3 点处理已锁定片段。得到的是 EXR 图序列，不是视频。")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)

            if !session.clips.isEmpty {
                Picker("列表", selection: $session.sidebarFilter) {
                    ForEach(ClipSidebarFilter.allCases) { filter in
                        Text(filter.title).tag(filter)
                    }
                }
                .pickerStyle(.segmented)
                .controlSize(.small)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)

                Text(session.lockStatusText)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 4)
            }

            if !session.lastImportNote.isEmpty {
                Text(session.lastImportNote)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 4)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(session.sidebarClips) { clip in
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
                }
                .onChange(of: session.selectedID) { _, id in
                    if let id {
                        proxy.scrollTo(id, anchor: .center)
                    }
                }
            }
        }
        .background(Color.primary.opacity(0.12))
    }
}

private struct DropZone: View {
    let targeted: Bool
    let empty: Bool
    let onTap: () -> Void

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: "square.and.arrow.down")
                .font(empty ? .title2 : .body)
            Text(empty ? "把混源文件夹拖进来" : "把文件夹拖进来")
                .font(empty ? .subheadline.weight(.semibold) : .caption)
                .foregroundStyle(.primary)
            if empty {
                Text("每条选成对 Log 与色域")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Text("已实现（未验证）")
                    .font(.caption2)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.accentColor.opacity(0.12))
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(empty ? 24 : 8)
        .background(targeted ? Color.accentColor.opacity(0.12) : Color.clear)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [5]))
                .foregroundStyle(targeted ? Color.accentColor : Color.secondary.opacity(0.72))
        )
        .contentShape(Rectangle())
        .onTapGesture {
            if empty {
                onTap()
            }
        }
    }
}

struct ClipRow: View {
    let clip: Clip
    var selected: Bool = false
    var onRevealWritten: (() -> Void)? = nil

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            RoundedRectangle(cornerRadius: 1)
                .fill(clip.isPending ? Color.accentColor.opacity(0.72) : Color.accentColor)
                .frame(width: 3)
                .padding(.vertical, 4)
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(clip.filename)
                        .font(clip.isPending ? .callout : .callout.weight(.semibold))
                        .foregroundStyle(clip.isPending ? Color.secondary : Color.primary)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    Text(clip.isPending ? "待选" : "已锁定")
                        .font(.caption2.weight(clip.isPending ? .regular : .semibold))
                        .padding(.horizontal, 4)
                        .padding(.vertical, 4)
                        .background(clip.isPending ? Color.accentColor.opacity(0.12) : Color.accentColor.opacity(0.72))
                        .foregroundStyle(clip.isPending ? Color.primary : Color.accentColor)
                        .clipShape(Capsule())
                }
                Text(clip.lockedPairLabel)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
                if let reason = clip.processSkipReason {
                    Text(reason)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                } else if let chip = clip.exportChip {
                    // 已写出代理 after a proxy write; failed write is a short Chinese error
                    if chip == SessionModel.wroteProxyChip {
                        Button(chip) { onRevealWritten?() }
                            .buttonStyle(.plain)
                            .font(.caption2)
                            .foregroundStyle(Color.secondary)
                            .lineLimit(1)
                    } else {
                        // 错误：写出失败。
                        Text(chip)
                            .font(.caption2)
                            .foregroundStyle(Color.orange)
                            .lineLimit(1)
                    }
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(selected ? Color.accentColor.opacity(0.12) : Color.clear)
    }
}
