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
                    .controlSize(.regular)
                Button("设置") { session.showSettings = true }
                    .controlSize(.regular)
            }
            .padding(.horizontal, 14)
            .padding(.top, 12)
            .padding(.bottom, 8)

            DropZone(targeted: session.dropTargeted, empty: session.clips.isEmpty) {
                session.showImporter = true
            }
            .padding(.horizontal, 14)
            .padding(.bottom, session.clips.isEmpty ? 10 : 8)

            Text("1 把混源文件夹拖进来  2 每条选成对 Log 与色域  3 点处理已锁定片段。得到的是 EXR 图序列，不是视频。")
                .font(session.clips.isEmpty ? .caption : .caption2)
                .foregroundStyle(session.clips.isEmpty ? Color.secondary : Color.secondary.opacity(0.55))
                .lineLimit(session.clips.isEmpty ? 6 : 2)
                .padding(.horizontal, 14)
                .padding(.bottom, session.clips.isEmpty ? 10 : 6)

            if !session.lastImportNote.isEmpty {
                Text(session.lastImportNote)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 14)
                    .padding(.bottom, 6)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(session.clips) { clip in
                            ClipRow(
                                clip: clip,
                                selected: session.selectedID == clip.id,
                                timingLine: clip.timingSidebarLine(settings: session.settings),
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
        .background(LBChrome.controlMaterial)
    }
}

private struct DropZone: View {
    let targeted: Bool
    let empty: Bool
    let onTap: () -> Void

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: "square.and.arrow.down")
                .font(empty ? .title3 : .caption)
                .foregroundStyle(LBChrome.locked)
            Text(empty ? "把混源文件夹拖进来" : "把文件夹拖进来")
                .font(empty ? .subheadline.weight(.semibold) : .caption.weight(.medium))
                .foregroundStyle(.primary)
            if empty {
                Text("每条选成对 Log 与色域")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Text("已实现（未验证）")
                    .font(.caption2.weight(.medium))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(LBChrome.pending.opacity(0.14))
                    .foregroundStyle(LBChrome.pending)
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(empty ? 16 : 8)
        .background(LBChrome.controlMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(targeted ? LBChrome.locked.opacity(0.16) : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(
                    targeted ? LBChrome.locked.opacity(0.7) : LBChrome.hairline,
                    style: StrokeStyle(lineWidth: 1, dash: empty ? [] : [4])
                )
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
    var timingLine: String = ""
    var onRevealWritten: (() -> Void)? = nil

    private var accent: Color {
        if clip.exportChip == SessionModel.wroteProxyChip {
            return LBChrome.written
        }
        return clip.isPending ? LBChrome.pending : LBChrome.locked
    }

    var body: some View {
        LBChrome.clipRowSlot(selected: selected, accent: accent) {
            HStack(alignment: .center, spacing: 8) {
                RoundedRectangle(cornerRadius: 1)
                    .fill(accent)
                    .frame(width: 3)
                VStack(alignment: .leading, spacing: 1) {
                    HStack(spacing: 6) {
                        Text(clip.filename)
                            .font(clip.isPending ? .callout : .callout.weight(.semibold))
                            .foregroundStyle(clip.isPending ? Color.secondary : Color.primary)
                            .lineLimit(1)
                        Spacer(minLength: 4)
                        Text(clip.isPending ? "待选" : "已锁定")
                            .font(.caption2.weight(clip.isPending ? .regular : .semibold))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 1)
                            .background(clip.isPending ? LBChrome.pending.opacity(0.16) : LBChrome.locked.opacity(0.16))
                            .foregroundStyle(clip.isPending ? LBChrome.pending : LBChrome.locked)
                            .clipShape(Capsule())
                    }
                    Text(clip.lockedPairLabel)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                    if !timingLine.isEmpty {
                        Text(timingLine)
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.tertiary)
                            .lineLimit(1)
                    }
                    if let reason = clip.processSkipReason {
                        Text(reason)
                            .font(.caption2)
                            .foregroundStyle(LBChrome.warn)
                            .lineLimit(1)
                    } else if let chip = clip.exportChip {
                        // 已写出代理 after a proxy write; failed write is a short Chinese error
                        if chip == SessionModel.wroteProxyChip {
                            Button(chip) { onRevealWritten?() }
                                .buttonStyle(.plain)
                                .font(.caption2.weight(.medium))
                                .padding(.horizontal, 6)
                                .padding(.vertical, 1)
                                .background(LBChrome.written.opacity(0.16))
                                .foregroundStyle(LBChrome.written)
                                .clipShape(Capsule())
                                .lineLimit(1)
                        } else {
                            Text(chip)
                                .font(.caption2)
                                .foregroundStyle(LBChrome.warn)
                                .lineLimit(1)
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 10)
    }
}
