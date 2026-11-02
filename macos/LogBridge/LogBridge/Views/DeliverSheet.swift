import SwiftUI

/// 写出是独立一步，不是偏好设置，也不是保存对话框。
/// 确认后由主窗口写出条打开系统选文件夹。本面板只收集确认。
struct DeliverSheet: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("写出代理")
                .font(.title2.weight(.semibold))
            Text("看清楚再选文件夹。未锁定的会跳过，不猜。")
                .font(.body)
                .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 6) {
                Text(session.lockStatusText)
                    .font(.title3.weight(.semibold))
                Text(session.settings.exportFormat.labelZH)
                    .font(.headline)
                Text(session.settings.exportFormat.pickerHelpZH)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.primary.opacity(0.05))
            .clipShape(RoundedRectangle(cornerRadius: 10))

            Text(deliverableNote)
                .font(.body)
                .fixedSize(horizontal: false, vertical: true)
            clipList

            Text(session.sharedGradeWriteLine)
                .font(.body.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            if !session.lockedClips.isEmpty {
                Text(session.deliverDiskNote)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text("每条已锁定素材用自己的成对 IDT。曝光和白平衡用检查器里当前这一套，套到这些素材上。点过别的素材也不会换成那一条自己的曝光或白平衡。")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Text("未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。已实现（未验证）。")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let reason = session.processBlockedReason, !session.showsProcessLockedButton {
                Text(reason)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.orange)
            }

            HStack(spacing: 12) {
                Button("关闭") {
                    session.showDeliverSheet = false
                }
                .controlSize(.large)
                .keyboardShortcut(.cancelAction)
                Spacer()
                Button("选出文件夹并写出") {
                    session.showDeliverSheet = false
                    session.deliverSheetConfirmed = true
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .keyboardShortcut(.defaultAction)
                .disabled(!session.showsProcessLockedButton)
            }
        }
        .padding(24)
        .frame(minWidth: 560, minHeight: 360)
    }

    /// Clips the write will skip. Same rule as the batch: no locked pair.
    private var skippedClips: [Clip] {
        session.clips.filter { !$0.hasLockedPair }
    }

    private var listHeight: CGFloat {
        let headers = (session.lockedClips.isEmpty ? 0 : 1) + (skippedClips.isEmpty ? 0 : 1)
        let estimate = CGFloat(headers) * 28 + CGFloat(session.clips.count) * 44 + 8
        return min(240, max(44, estimate))
    }

    @ViewBuilder
    private var clipList: some View {
        if !session.clips.isEmpty {
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if !session.lockedClips.isEmpty {
                        Text("会写出")
                            .font(.subheadline.weight(.semibold))
                        ForEach(session.lockedClips) { clip in
                            clipLine(
                                name: clip.filename,
                                detail: clip.lockedPairLabel,
                                output: clip.plannedDeliverableName(format: session.settings.exportFormat),
                                willWrite: true
                            )
                        }
                    }
                    if !skippedClips.isEmpty {
                        Text("会跳过")
                            .font(.subheadline.weight(.semibold))
                            .padding(.top, session.lockedClips.isEmpty ? 0 : 4)
                        ForEach(skippedClips) { clip in
                            clipLine(
                                name: clip.filename,
                                detail: clip.processSkipReason ?? "先选择成对 IDT",
                                output: nil,
                                willWrite: false
                            )
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(height: listHeight)
        }
    }

    private func clipLine(name: String, detail: String, output: String?, willWrite: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            RoundedRectangle(cornerRadius: 2)
                .fill(willWrite ? Color.accentColor : Color.yellow.opacity(0.95))
                .frame(width: 4, height: output == nil ? 34 : 48)
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.body)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Text(detail)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                if let output {
                    Text("将得到 \(output)")
                        .font(.caption.monospaced())
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
    }

    private var deliverableNote: String {
        if session.settings.exportFormat == .prores422HQ {
            return UICopy.PROCESS_DELIVERABLE_NOTE_UI
        }
        return "高级格式走 ACES2065-1 EXR 序列。整段代理，代理精度。"
    }
}
