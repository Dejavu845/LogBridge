import SwiftUI

/// Paired IDT for the selected clip. Lives in the inspector column, always visible.
/// Visible during write; picker is not swappable mid-write.
/// Do not bury this in 「高级」. Unlocked IDT blocks / skips process.
struct PairedIDTBar: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("成对 IDT")
                    .font(.headline)
                Spacer(minLength: 8)
                if let clip = session.selectedClip {
                    Text(clip.verificationBadge)
                        .font(.caption.weight(clip.isPending ? .regular : .semibold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(clip.isPending ? Color.yellow.opacity(0.28) : Color.orange.opacity(0.2))
                        .clipShape(Capsule())
                }
            }
            Text("本片色彩。先选 Log 与色域，才能处理。")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if let clip = session.selectedClip {
                // One column of complete pairs. Never two independent curve/gamut dropdowns.
                PairedIDTChoices(session: session, clip: clip)
                    .help("S-Log3 + S-Gamut3 或 S-Log3 + S-Gamut3.Cine。C-Log2 / C-Log3 + Cinema Gamut 或 BT.2020。Venice 对仅在检测到时出现。点一行才锁定。")
                HStack(spacing: 8) {
                    Text("来源：\(clip.detectionSource.title)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if clip.veniceDetected {
                        Text("检测到 Venice")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                if let reason = clip.processSkipReason {
                    Text(reason)
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Text(clip.detectionNote)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .lineLimit(2)
                if clip.hasLockedPair, session.pendingClipCount > 0 {
                    VStack(alignment: .leading, spacing: 8) {
                        Button("下一条待选") {
                            session.selectNextPendingAfterLock(lockedID: clip.id)
                        }
                        .controlSize(.regular)
                        .disabled(session.isExporting)
                        .help("这条留在列表里。去下一条还没选成对 IDT 的素材，不替你选。")
                        Button("这一对给下一条待选") {
                            session.applyLockedPairToNextPending()
                        }
                        .controlSize(.regular)
                        .disabled(!session.canApplyLockedPairToNextPending)
                        .help("把当前这一对写到下一条还没锁定的素材上，而且这一对已经在它的成对列表里。然后停在那一条看预览。不改曝光和白平衡。下一条的列表里没有这一对时不起作用，也不跳去更后面的一条。⇧⌘] 和菜单「调色」是同一套。")
                    }
                    if let note = session.applyPairToNextPendingNote {
                        Text(note)
                            .font(.caption)
                            .foregroundStyle(.orange)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            } else {
                Text("先点一条素材。读不到元数据就在这里选成对 IDT，不猜。")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.03))
    }
}

/// Visible paired-IDT rows. A click locks that pair and stays on this clip.
/// Search only hides rows. One remaining match does not lock itself.
private struct PairedIDTChoices: View {
    @ObservedObject var session: SessionModel
    let clip: Clip
    @State private var pairQuery = ""

    private var pairs: [IDT] { clip.pickerPairs }

    private var showSearch: Bool { pairs.count > IDT.pairListShowsSearchAfter }

    private var shown: [IDT] {
        showSearch ? IDT.filteredPairs(pairs, query: pairQuery) : pairs
    }

    private var queryIsBlank: Bool {
        pairQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("点一行锁定。选完停在这条看预览。")
                .font(.caption)
                .foregroundStyle(.secondary)
            if showSearch {
                HStack(spacing: 8) {
                    TextField("查找 Log 或色域", text: $pairQuery)
                        .textFieldStyle(.roundedBorder)
                        .disabled(session.isExporting)
                    if !queryIsBlank {
                        Button("清空") { pairQuery = "" }
                            .controlSize(.regular)
                            .disabled(session.isExporting)
                    }
                }
                .help("只收下面这一列。可输入索尼、Sony、LogC、佳能。不会因为只剩一对就替你选。")
            }
            if let current = clip.idt, showSearch, !queryIsBlank, !shown.contains(current) {
                Text("当前这一对不在查找里。清空后仍是 \(current.pairLabel)。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if shown.isEmpty {
                Text("没有匹配的成对 IDT。清空查找再点一行。")
                    .font(.callout)
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            } else if shown.count > 6 {
                ScrollView {
                    pairRows
                }
                .frame(maxHeight: 180)
            } else {
                pairRows
            }
        }
        .onChange(of: session.selectedID) { _, _ in
            pairQuery = ""
        }
    }

    private var pairRows: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(shown) { pair in
                Button {
                    if clip.idt != pair {
                        session.setIDT(clip.id, pair)
                    }
                } label: {
                    HStack(spacing: 8) {
                        Text(pair.pairLabel)
                            .font(.body)
                            .foregroundStyle(.primary)
                            .multilineTextAlignment(.leading)
                            .lineLimit(2)
                        Spacer(minLength: 8)
                        if clip.idt == pair {
                            Text("当前")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(Color.accentColor)
                        }
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(clip.idt == pair ? Color.accentColor.opacity(0.16) : Color.primary.opacity(0.04))
                    )
                }
                .buttonStyle(.plain)
                .disabled(session.isExporting)
                .help(clip.idt == pair
                      ? "已经是这一对。预览按这一对。"
                      : "点这一行锁定成对 IDT。停在这条看预览，不替下一条选。")
            }
        }
    }
}

/// Right inspector: Exposure + WB, folded sections, follow the selection.
/// IDT stays above this view — not in 「高级」. Changes apply immediately.
struct InspectorView: View {
    @ObservedObject var session: SessionModel
    @State private var exposureOpen = true
    @State private var wbOpen = true

    var body: some View {
        // 外层检查器已整栏滚动，这里不再套一层，避免矮窗口里滚不动。
        VStack(alignment: .leading, spacing: 12) {
            DisclosureGroup(isExpanded: $exposureOpen) {
                ExposureInspector(session: session)
                    .padding(.top, 6)
            } label: {
                Text("曝光")
                    .font(.headline)
            }
            DisclosureGroup(isExpanded: $wbOpen) {
                WBInspector(session: session)
                    .padding(.top, 6)
            } label: {
                Text("白平衡")
                    .font(.headline)
            }
        }
        .disabled(session.isExporting)
        .opacity(session.isExporting ? 0.45 : 1)
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.02))
    }
}

struct WBInspector: View {
    @ObservedObject var session: SessionModel
    @State private var cctDraft = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle("启用白平衡（可旁路，不烘焙）", isOn: Binding(
                get: { session.graph.wbEnabled },
                set: { session.setWBEnabled($0) }
            ))
            .controlSize(.regular)
            if let clip = session.selectedClip {
                Text(cameraReadingLine(clip))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            // Three states only. Estimate chip lights AFTER confirm, never on propose.
            // 机内 / 估计确认才写 / 灰卡 — distinct tone + weight at a glance.
            HStack(spacing: 4) {
                WBStateChip(title: "机内", on: session.graph.wbSource == .asShot, kind: .asShot)
                WBStateChip(title: "估计确认才写", on: session.graph.wbSource == .estimate,
                    pending: session.graph.autoWBCCT != nil
                        && session.graph.wbSource != .estimate
                        && session.graph.wbSource != .grey,
                    kind: .estimate)
                WBStateChip(title: "灰卡", on: session.graph.wbSource == .grey, kind: .grey)
            }
            if session.graph.asShotUnknown {
                Text("机内未知")
                    .font(.caption2.weight(.semibold))
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(Color.yellow.opacity(0.28))
                    .clipShape(Capsule())
                Text("读不到机内色温。保持未填、单位阵，不猜 5600 或 6504。点灰卡或手填。已实现（未验证）。")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }
            HStack(spacing: 6) {
                Button(session.pickingNeutral ? "在预览上点灰卡…" : "点灰卡") {
                    session.pickingNeutral.toggle()
                }
                .controlSize(.regular)
                .help("点灰卡：在 IDT 之后的线性预览上取样，覆盖元数据并写入白平衡。不是校准。")
                Button("估计白平衡") {
                    session.proposeAutoWB()
                }
                .controlSize(.regular)
                .help("白平衡（估计）：给出估计色温，确认后才写入；把握不够就空着。不猜 5600。不是校准。")
            }
            if session.graph.autoWBCCT != nil {
                HStack(spacing: 6) {
                    Text("白平衡（估计） \(Int(session.graph.autoWBCCT ?? 0)) K — 确认后才写入，一点不会写入")
                        .font(.caption2)
                        .lineLimit(2)
                    Spacer(minLength: 4)
                    Button("确认估计") {
                        session.confirmAutoWB()
                    }
                    .controlSize(.regular)
                }
            }
            if session.graph.wbEnabled {
                HStack {
                    Text("色温")
                        .font(.caption)
                        .frame(width: 36, alignment: .leading)
                    Slider(
                        value: Binding(
                            get: { session.graph.wbCCTDisplay },
                            set: { session.setWBParams(cct: $0) }
                        ),
                        in: 2000...10000,
                        step: 10
                    )
                    .controlSize(.regular)
                    Text(session.graph.wbCCT.map { "\(Int($0)) K" } ?? "机内未知")
                        .font(.caption.monospacedDigit())
                        .frame(width: 72, alignment: .trailing)
                }
                HStack(spacing: 8) {
                    TextField("如 4500", text: $cctDraft)
                        .textFieldStyle(.roundedBorder)
                        .font(.body.monospacedDigit())
                        .frame(width: 96)
                        .disabled(!session.canTypeWBCCT)
                        .onSubmit { commitCCT() }
                    Button("写入色温") { commitCCT() }
                        .disabled(!session.canTypeWBCCT)
                }
                .controlSize(.regular)
                .onAppear { syncCCTDraft() }
                .onChange(of: session.graph.wbCCT) { _, _ in
                    syncCCTDraft()
                }
                .help("写入这一套色温。4500 或 4500 K，收到整数。色温空着时也可以写入，这是你填的，不猜。超出 2000 到 10000 不改数字。和滑条是同一套，写出仍用这一套。一次写入算一步，可撤销。")
                if !session.typedCCTNote.isEmpty {
                    Text(session.typedCCTNote)
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack(spacing: 8) {
                    Button("−100 K") { session.nudgeWBCCT(-100) }
                        .disabled(!session.canNudgeWB || (session.graph.wbCCT ?? 2000) <= 2000)
                    Button("回到机内") { session.restoreAsShotWB() }
                        .disabled(!session.canRestoreAsShotWB)
                    Button("+100 K") { session.nudgeWBCCT(100) }
                        .disabled(!session.canNudgeWB || (session.graph.wbCCT ?? 10000) >= 10000)
                }
                .controlSize(.regular)
                .help("每次 100 K。回到机内把当前这条的机内色温和绿品写入这一套。没有机内读数就清空，不猜 5600。换一条素材不会自己改掉这一套。空值不能步进。菜单「调色」是同一套。仅预览。")
                HStack {
                    Text("绿品")
                        .font(.caption)
                        .frame(width: 36, alignment: .leading)
                    Slider(
                        value: Binding(
                            get: { session.graph.wbTint },
                            set: { session.setWBParams(tint: $0) }
                        ),
                        in: -10...10,
                        step: 0.1
                    )
                    .controlSize(.regular)
                    Text(String(format: "%.1f", session.graph.wbTint))
                        .font(.caption.monospacedDigit())
                        .frame(width: 52, alignment: .trailing)
                }
                HStack(spacing: 8) {
                    Button("−1") { session.nudgeWBTint(-1) }
                        .disabled(!session.canNudgeWBTint || session.graph.wbTint <= -10)
                    Button("绿品归零") { session.resetWBTint() }
                        .disabled(!session.canNudgeWBTint || abs(session.graph.wbTint) < 0.001)
                    Button("+1") { session.nudgeWBTint(1) }
                        .disabled(!session.canNudgeWBTint || session.graph.wbTint >= 10)
                }
                .controlSize(.regular)
                .help("每次 1，或把绿品收到 0。色温不动。色温空着时不能步进。回到机内才把当前这条的机内绿品写入这一套。菜单「调色」是同一套。仅预览。")
                Picker("适应方法", selection: Binding(
                    get: { session.graph.wbMethod },
                    set: { session.setWBParams(method: $0) }
                )) {
                    Text("Bradford").tag("bradford")
                    Text("CAT02").tag("cat02")
                }
                .controlSize(.regular)
                .frame(maxWidth: .infinity)
            }
            Text("机内色温只填旋钮，默认是单位阵。只有你改色温才做相对校正（例如 3200→5600 变暖）。灰卡是绝对校正；读不到就保持单位阵，不猜 5600。这一套不跟素材换。")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
    }

    private func syncCCTDraft() {
        if let cct = session.graph.wbCCT {
            cctDraft = String(Int(cct.rounded()))
        } else {
            cctDraft = ""
        }
    }

    /// A refused string stays in the field so it can be corrected.
    private func commitCCT() {
        if session.applyTypedWBCCT(cctDraft) {
            syncCCTDraft()
        }
    }

    /// Camera reading for the selected clip. Not the shared knobs.
    private func cameraReadingLine(_ clip: Clip) -> String {
        if let cct = clip.asShotCCT {
            let tint = String(format: "%+.1f", clip.asShotTint)
            return "这条机内 \(Int(cct.rounded())) K · 绿品 \(tint)。换一条不会改这一套。回到机内才换成这条。"
        }
        return "这条读不到机内色温。换一条不会改这一套。回到机内会清空，不猜 5600。"
    }
}

/// Glanceable WB state. Same three chips — distinct tone, not extra widgets.
/// Estimate pending (proposed, not confirmed) is outline-only; confirm fills it.
private enum WBChipKind {
    case asShot, estimate, grey
}

private struct WBStateChip: View {
    let title: String
    let on: Bool
    var pending: Bool = false
    var kind: WBChipKind = .asShot

    var body: some View {
        Text(title)
            .font(.caption2.weight(on || pending ? .semibold : .regular))
            .lineLimit(1)
            .minimumScaleFactor(0.85)
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .frame(maxWidth: .infinity)
            .background(fill)
            .foregroundStyle(ink)
            .overlay(
                Capsule()
                    .strokeBorder(pending && !on ? Color.orange.opacity(0.85) : Color.clear, lineWidth: 1)
            )
            .clipShape(Capsule())
    }

    private var fill: Color {
        if on {
            switch kind {
            case .asShot: return Color.primary.opacity(0.14)
            case .estimate: return Color.orange.opacity(0.22)
            case .grey: return Color.accentColor.opacity(0.18)
            }
        }
        if pending { return Color.orange.opacity(0.08) }
        return Color.primary.opacity(0.05)
    }

    private var ink: Color {
        if on {
            switch kind {
            case .asShot: return Color.primary
            case .estimate: return Color.orange
            case .grey: return Color.accentColor
            }
        }
        if pending { return Color.orange }
        return Color.secondary
    }
}

struct ODTInspector: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("输出")
                .font(.subheadline.weight(.semibold))
            Picker("预览输出", selection: Binding(
                get: { session.graph.odt },
                set: { session.setODT($0) }
            )) {
                ForEach(ODTMode.allCases) { mode in
                    Text(mode.title).tag(mode)
                }
            }
            .frame(maxWidth: 280)
            Text(session.graph.odt.acesOTNote)
                .font(.caption)
                .foregroundStyle(.secondary)
            if session.graph.odt == .rec709 {
                Text("Rec.709 仅预览")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if session.graph.odt.isHDR {
                Text("系统 HDR 预览（HLG/PQ）。仅预览，未与 709 匹配。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("工作空间：\(session.graph.workingSpace.rawValue)")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("导出 ACEScct / EXR：整段代理，代理精度，并写出 cube 节点。")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct ExposureInspector: View {
    @ObservedObject var session: SessionModel
    @State private var exposureDraft = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle("启用曝光（0 档 = 不动）", isOn: Binding(
                get: { session.graph.exposureEnabled },
                set: { session.setExposureEnabled($0) }
            ))
            .controlSize(.regular)
            if session.graph.exposureEnabled {
                HStack(spacing: 6) {
                    Text("档")
                        .font(.caption)
                        .frame(width: 56, alignment: .leading)
                    Slider(
                        value: Binding(
                            get: { session.graph.exposureStops },
                            set: { session.setExposureStops($0) }
                        ),
                        in: -8...8,
                        step: 0.05
                    )
                    .controlSize(.regular)
                    Text(String(format: "%+.2f 档", session.graph.exposureStops))
                        .font(.body.monospacedDigit())
                        .frame(width: 78, alignment: .trailing)
                }
                HStack(spacing: 8) {
                    TextField("如 +0.50", text: $exposureDraft)
                        .textFieldStyle(.roundedBorder)
                        .font(.body.monospacedDigit())
                        .frame(width: 96)
                        .disabled(!session.canNudgeExposure)
                        .onSubmit { commitExposure() }
                    Button("写入档") { commitExposure() }
                        .disabled(!session.canNudgeExposure)
                }
                .controlSize(.regular)
                .onAppear { syncExposureDraft() }
                .onChange(of: session.graph.exposureStops) { _, _ in
                    syncExposureDraft()
                }
                .help("写入这一套曝光。+0.50、0.5 或 0.5档，按 0.01 档收。超出 −8 到 +8 不改数字。和滑条、步进是同一套，写出仍用这一套。一次写入算一步，可撤销。不把曝光打开。")
                if !session.typedExposureNote.isEmpty {
                    Text(session.typedExposureNote)
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack(spacing: 8) {
                    Button("−0.10") { session.nudgeExposureStops(-0.10) }
                        .disabled(session.graph.exposureStops <= -8)
                    Button("归零") { session.resetExposureStops() }
                        .disabled(abs(session.graph.exposureStops) < 0.001)
                    Button("+0.10") { session.nudgeExposureStops(0.10) }
                        .disabled(session.graph.exposureStops >= 8)
                }
                .controlSize(.regular)
                .help("每次 0.10 档，或归零。预览和监视器读数一起变。菜单「调色」是同一套。仅预览。")
                Text(String(format: "线性增益 = %.4f", pow(2.0, session.graph.exposureStops)))
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.tertiary)
            }
            Text("单位是档。曝光按线性增益作用（不加减 Log 码值）；在 IDT 之后、白平衡之前。整段代理，代理精度。")
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .lineLimit(2)
            Text("仅预览")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
    }

    private func syncExposureDraft() {
        exposureDraft = String(format: "%+.2f", session.graph.exposureStops)
    }

    /// A refused string stays in the field so it can be corrected.
    private func commitExposure() {
        if session.applyTypedExposureStops(exposureDraft) {
            syncExposureDraft()
        }
    }
}
