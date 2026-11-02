import SwiftUI

/// 写出是独立一步，不是偏好设置，也不是保存对话框。
/// 确认后由主窗口写出条打开系统选文件夹。本面板只收集确认。
/// 当前这一条标出来。会跳过的一条可以去选成对 IDT，不替你选。
/// 选好后，检查器标题可以回到这份说明，不开始写文件。滚到曝光时这一下还在。
/// 确认和关闭留在下面，说明长了中间自己滚。
struct DeliverSheet: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text("写出代理")
                    .font(.title2.weight(.semibold))
                Text("看清楚再选文件夹。未锁定的会跳过，不猜。会跳过的一条可以去选成对 IDT。选好后可在检查器标题回到这份说明。当前这条会标出来。确认和关闭留在下面。")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
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
                    deliverPreviewGlance
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
                    Text("确认后说明收起，选文件夹贴在这个窗口上。选好才开始写出。取消则不写出。")
                        .font(.body.weight(.semibold))
                        .fixedSize(horizontal: false, vertical: true)
                    Text(session.exportFolderOpenNote)
                        .font(.body)
                        .fixedSize(horizontal: false, vertical: true)
                        .help("只写文件夹的名字，不写整条路径。那个文件夹还在才用。不在设置里，没有保存按钮。取消则不写出。不改这一套曝光和白平衡，也不改成对 IDT。")

                    if let reason = session.processBlockedReason, !session.showsProcessLockedButton {
                        Text(reason)
                            .font(.body.weight(.semibold))
                            .foregroundStyle(.orange)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 480)

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
                .help("留在说明下面。回车是这一下。说明收起后才选文件夹，选好才开始写文件。不改这一套曝光和白平衡，也不改成对 IDT。")
            }
        }
        .padding(24)
        .frame(minWidth: 560, minHeight: 360, maxHeight: 720)
    }

    /// Clips the write will skip. Same rule as the batch: no locked pair.
    private var skippedClips: [Clip] {
        session.clips.filter { !$0.hasLockedPair }
    }

    private var listHeight: CGFloat {
        let headers = (session.lockedClips.isEmpty ? 0 : 1) + (skippedClips.isEmpty ? 0 : 1)
        let estimate = CGFloat(headers) * 28 + CGFloat(session.clips.count) * 62 + 8
        return min(240, max(44, estimate))
    }

    @ViewBuilder
    private var clipList: some View {
        if !session.clips.isEmpty {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        if !session.lockedClips.isEmpty {
                            Text("会写出")
                                .font(.subheadline.weight(.semibold))
                            ForEach(session.lockedClips) { clip in
                                clipLine(
                                    clipID: clip.id,
                                    name: clip.filename,
                                    detail: clip.lockedPairLabel,
                                    fact: clip.mediaFactLine,
                                    output: clip.plannedDeliverableName(format: session.settings.exportFormat),
                                    willWrite: true,
                                    current: clip.id == session.selectedID
                                )
                                .id(clip.id)
                            }
                        }
                        if !skippedClips.isEmpty {
                            Text("会跳过")
                                .font(.subheadline.weight(.semibold))
                                .padding(.top, session.lockedClips.isEmpty ? 0 : 4)
                            Text("点「去选成对 IDT」关掉说明，停在那一条。不替你选，也不开始写文件。选好后，检查器标题可以回到这份说明。滚到曝光时这一下还在。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                            ForEach(skippedClips) { clip in
                                clipLine(
                                    clipID: clip.id,
                                    name: clip.filename,
                                    detail: clip.processSkipReason ?? "先选择成对 IDT",
                                    fact: clip.mediaFactLine,
                                    output: nil,
                                    willWrite: false,
                                    current: clip.id == session.selectedID
                                )
                                .id(clip.id)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: listHeight)
                .onAppear {
                    revealCurrentClip(with: proxy)
                }
            }
        }
    }

    /// The monitor's clip, inside this list. Does not change the selection or the grade.
    private func revealCurrentClip(with proxy: ScrollViewProxy) {
        guard let id = session.selectedID else { return }
        DispatchQueue.main.async {
            proxy.scrollTo(id, anchor: .center)
        }
    }

    private func clipLine(clipID: UUID, name: String, detail: String, fact: String?, output: String?, willWrite: Bool, current: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            RoundedRectangle(cornerRadius: 2)
                .fill(willWrite ? Color.accentColor : Color.yellow.opacity(0.95))
                .frame(width: 4, height: accentHeight(fact: fact, output: output, willWrite: willWrite))
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 8) {
                    Text(name)
                        .font(.body)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    if current {
                        Text("当前这条")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Color.accentColor)
                            .layoutPriority(1)
                            .help("和监视器是同一条。会写出或会跳过都标。不改选中，不改这一套曝光和白平衡，不改成对 IDT，也不开始写文件。")
                    }
                }
                Text(detail)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                if let fact {
                    Text(fact)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .help("和左侧列表同一行。片源尺寸、帧率、时长。缺的不写，不猜帧率。不参与写出。")
                }
                if let output {
                    Text("将得到 \(output)")
                        .font(.caption.monospaced())
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                if !willWrite {
                    Button("去选成对 IDT") {
                        session.focusSkippedClipFromWriteSheet(clipID)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.regular)
                    .help("关掉写出说明，停在这一条，滚到成对 IDT。不替你选，也不开始写文件。已经是当前这条时，预览帧留着。换到另一条时，和点列表一样，预览回到那一条的开头。筛选或查找挡着就让这一条回到列表。选好后，检查器标题里「回到写出说明」只重新打开说明。锁上最后一条并滚到曝光时，这一下留在标题。不改这一套曝光和白平衡，也不改成对 IDT。")
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, current ? 4 : 0)
        .padding(.horizontal, current ? 4 : 0)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(current ? Color.accentColor.opacity(0.12) : Color.clear)
        )
        .accessibilityElement(children: willWrite ? .combine : .contain)
    }

    /// Skip rows add the button. Locked rows stay the name, the pair, and the file.
    private func accentHeight(fact: String?, output: String?, willWrite: Bool) -> CGFloat {
        let base: CGFloat = output == nil ? (fact == nil ? 34 : 50) : (fact == nil ? 48 : 64)
        return willWrite ? base : base + 32
    }

    /// Current frame of the selected clip, only when it is the Rec.709 look
    /// default ProRes bakes. 调色前 / HDR / EXR stay words. Not written to disk.
    @ViewBuilder
    private var deliverPreviewGlance: some View {
        let glance = session.deliverPreviewGlance
        VStack(alignment: .leading, spacing: 8) {
            if let image = session.preview.odtImage, glance.showStill {
                VStack(alignment: .leading, spacing: 4) {
                    Text(session.deliverPreviewFrameLabel)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Image(decorative: image, scale: 1)
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: 280, maxHeight: 158)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .overlay(alignment: .topLeading) {
                            Text("仅预览")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(.black.opacity(0.55))
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                                .padding(6)
                        }
                        .help("和监视器当前这一帧同一幅。预览长边会缩小，写出是片源尺寸。不另存一套调色。")
                }
            }
            Text(glance.sheetNote)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var deliverableNote: String {
        if session.settings.exportFormat == .prores422HQ {
            return UICopy.PROCESS_DELIVERABLE_NOTE_UI
        }
        return "高级格式走 ACES2065-1 EXR 序列。整段代理，代理精度。"
    }
}
