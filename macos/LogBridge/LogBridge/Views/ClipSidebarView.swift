import SwiftUI

/// Drop zone + virtualized clip list. Badge is never "supported".
struct ClipSidebarView: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("素材")
                    .font(.headline)
                Spacer()
                Button("添加…") { session.showImporter = true }
                Button("设置") { session.showSettings = true }
            }
            .padding(.horizontal, 12)
            .padding(.top, 10)
            .padding(.bottom, 6)

            DropZone(targeted: session.dropTargeted, empty: session.clips.isEmpty)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)

            Text("拖入 → 锁 IDT → 曝光/WB → 处理已锁定片段。未锁定的跳过，不猜。")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)
                .padding(.bottom, 6)

            if !session.lastImportNote.isEmpty {
                Text(session.lastImportNote)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 6)
            }

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(session.clips) { clip in
                        ClipRow(
                            clip: clip,
                            selected: session.selectedID == clip.id,
                            onRevealWritten: { session.revealClipExportInFinder(clip) }
                        )
                        .contentShape(Rectangle())
                        .onTapGesture {
                            session.selectedID = clip.id
                            session.refreshPreview()
                            session.revealClipExportInFinder(clip)
                        }
                    }
                }
            }
        }
    }
}

private struct DropZone: View {
    let targeted: Bool
    let empty: Bool

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: "square.and.arrow.down")
                .font(empty ? .title2 : .body)
            Text(empty ? "把混源文件夹拖进来" : "把文件夹拖进来")
                .font(empty ? .subheadline.weight(.semibold) : .caption)
                .foregroundStyle(.primary)
            if empty {
                Text("拖入自己的 Log，不内置厂商样片 — no bundled manufacturer demos")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Text("已实现（未验证）")
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.orange.opacity(0.2))
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(empty ? 28 : 8)
        .background(targeted ? Color.accentColor.opacity(0.15) : Color.primary.opacity(0.04))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [5]))
                .foregroundStyle(targeted ? Color.accentColor : Color.secondary.opacity(0.4))
        )
    }
}

struct ClipRow: View {
    let clip: Clip
    var selected: Bool = false
    var onRevealWritten: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(clip.filename)
                .font(.body)
                .lineLimit(1)
            HStack(spacing: 6) {
                Text(clip.lockedPairLabel)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Spacer()
                Text(clip.verificationBadge)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(clip.isPending ? Color.yellow.opacity(0.25) : Color.orange.opacity(0.2))
                    .clipShape(Capsule())
            }
            if let reason = clip.processSkipReason {
                Text(reason)
                    .font(.caption2)
                    .foregroundStyle(.orange)
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
                    Text(chip)
                        .font(.caption2)
                        .foregroundStyle(Color.orange)
                        .lineLimit(1)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(selected ? Color.accentColor.opacity(0.12) : Color.clear)
    }
}
