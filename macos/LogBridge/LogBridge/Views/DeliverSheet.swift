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
            Text("每条已锁定素材用自己的成对 IDT。曝光和白平衡用检查器里当前这一套，套到这些素材上。")
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
        .frame(minWidth: 520, minHeight: 320)
    }

    private var deliverableNote: String {
        if session.settings.exportFormat == .prores422HQ {
            return UICopy.PROCESS_DELIVERABLE_NOTE_UI
        }
        return "高级格式走 ACES2065-1 EXR 序列。整段代理，代理精度。"
    }
}
