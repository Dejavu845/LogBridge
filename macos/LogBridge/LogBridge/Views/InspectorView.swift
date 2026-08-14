import SwiftUI

/// Parameters for the selected serial node. WB bypass matches Resolve export.
struct InspectorView: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(session.selectedNode.title)
                    .font(.headline)
                Text(session.selectedNode.exportBasename)
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                Spacer()
            }
            switch session.selectedNode {
            case .idt:
                IDTInspector(session: session)
            case .exposure:
                ExposureInspector(session: session)
            case .wb:
                WBInspector(session: session)
            case .odt:
                ODTInspector(session: session)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.03))
    }
}

private struct IDTInspector: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        if let clip = session.selectedClip {
            Text(clip.filename)
                .font(.subheadline)
            Text(clip.detectionNote)
                .font(.caption)
                .foregroundStyle(.secondary)
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Paired IDT")
                        .font(.caption.weight(.semibold))
                    // One locked pair per row. Never two independent curve/gamut dropdowns.
                    Picker("Paired IDT", selection: Binding(
                        get: { clip.idt },
                        set: { newValue in
                            if let idt = newValue {
                                session.setIDT(clip.id, idt)
                            }
                        }
                    )) {
                        Text("— pick a paired IDT —").tag(Optional<IDT>.none)
                        ForEach(clip.pickerPairs) { pair in
                            Text(pair.pairLabel).tag(Optional(pair))
                        }
                    }
                    .labelsHidden()
                    .frame(maxWidth: 320)
                    Text("S-Log3 + S-Gamut3 vs S-Log3 + S-Gamut3.Cine. C-Log2 / C-Log3 + Cinema Gamut vs BT.2020. Venice pair only if detected.")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Status")
                        .font(.caption.weight(.semibold))
                    Text(clip.verificationBadge)
                        .font(.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(clip.isPending ? Color.yellow.opacity(0.28) : Color.orange.opacity(0.2))
                        .clipShape(Capsule())
                    Text("source: \(clip.detectionSource.rawValue)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    if clip.veniceDetected {
                        Text("Venice detected")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            if clip.isPending {
                Text("先选择 Log 与色域. This clip is pending. Process selected / Apply graph and export are blocked until a locked pair is chosen. Never a silent S-Gamut3.Cine default.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
        } else {
            Text("Select a clip. Missing metadata needs a paired IDT — no silent default, no two dropdowns.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

private struct WBInspector: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        Toggle("Enable WB (node 3). Off = bypass, no bake in preview or Resolve export.", isOn: Binding(
            get: { session.graph.wbEnabled },
            set: { session.setWBEnabled($0) }
        ))
        HStack(spacing: 6) {
            WBStateChip(title: "机内 as-shot", on: session.graph.wbSource == .asShot)
            WBStateChip(title: "白平衡（估计）", on: session.graph.wbSource == .estimate || session.graph.autoWBCCT != nil)
            WBStateChip(title: "灰卡", on: session.graph.wbSource == .grey)
            if session.graph.asShotUnknown {
                Text("as-shot unknown")
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.yellow.opacity(0.28))
                    .clipShape(Capsule())
            }
        }
        if session.graph.asShotUnknown {
            Text("No camera-private CCT. WB stays pending / identity — do not guess 5600 or 6504. Pick a grey card (after IDT, AP0 linear) or set CCT.")
                .font(.caption)
                .foregroundStyle(.orange)
        }
        Button(session.pickingNeutral ? "Click preview to pick neutral…" : "Pick neutral") {
            session.pickingNeutral.toggle()
        }
        .help("Grey-card click: sample after IDT in ACES2065-1 (AP0) linear; overrides metadata. Writes the existing CAT node.")
        Button("估计白平衡") {
            session.proposeAutoWB()
        }
        .help("白平衡（估计）: SoG p=6 in ACEScg after IDT. Does not write CAT. Low confidence stays empty. Not 精准.")
        if session.graph.autoWBCCT != nil {
            Text("白平衡（估计） \(Int(session.graph.autoWBCCT ?? 0)) K — confirm to write absolute CAT")
                .font(.caption)
            Button("确认估计") {
                session.confirmAutoWB()
            }
        }
        if session.graph.wbEnabled {
            HStack {
                Text("CCT")
                    .frame(width: 40, alignment: .leading)
                Slider(
                    value: Binding(
                        get: { session.graph.wbCCTDisplay },
                        set: { session.setWBParams(cct: $0) }
                    ),
                    in: 2000...10000,
                    step: 10
                )
                Text(session.graph.wbCCT.map { "\(Int($0)) K" } ?? "as-shot unknown")
                    .monospacedDigit()
                    .frame(width: 88, alignment: .trailing)
            }
            HStack {
                Text("Tint")
                    .frame(width: 40, alignment: .leading)
                Slider(
                    value: Binding(
                        get: { session.graph.wbTint },
                        set: { session.setWBParams(tint: $0) }
                    ),
                    in: -10...10,
                    step: 0.1
                )
                Text(String(format: "%.1f", session.graph.wbTint))
                    .monospacedDigit()
                    .frame(width: 64, alignment: .trailing)
            }
            Picker("CAT", selection: Binding(
                get: { session.graph.wbMethod },
                set: { session.setWBParams(method: $0) }
            )) {
                Text("Bradford").tag("bradford")
                Text("CAT02").tag("cat02")
            }
            .frame(maxWidth: 220)
        }
        Text("As-shot CCT/tint fills these knobs (UI only). Log IDTs assume already white-balanced — default CAT is identity. Do not treat as-shot 5600/6504 as an illuminant (double WB). Moving CCT/tint away from as-shot is relative CAT(user→D65)·inv(CAT(as→D65)) = CAT(user→as); raising Kelvin warms (in-camera). Not CAT(as→user), not CAT(user→D65) alone. First typed CCT with no as-shot is a label (identity). Grey-card (after IDT, ACES2065-1 (AP0) linear) is an absolute CAT. Missing CCT/tint is pending / identity — do not guess 5600 or 6504. Implemented (unverified). Disable this node in Resolve (or DCTL Bypass WB) = IDT → Exposure → ACEScct, no bake.")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}

private struct WBStateChip: View {
    let title: String
    let on: Bool
    var body: some View {
        Text(title)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(on ? Color.accentColor.opacity(0.18) : Color.primary.opacity(0.05))
            .foregroundStyle(on ? Color.accentColor : Color.secondary)
            .clipShape(Capsule())
    }
}

private struct ODTInspector: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        Picker("ODT", selection: Binding(
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
            Text("Rec.709 is preview only, not the standard deliverable. Tagged CGColorSpace.itur_709 only when this node is Rec.709. No RRT. Implemented (unverified).")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        if session.graph.odt.isHDR {
            Text("HDR OT via ACES/BT.2100 BuiltinTransform. 预览·非成片，未与 709 匹配. No homemade HLG/PQ curve. Implemented (unverified). Not supported. Not 一键精准.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        Text("Working space: \(session.graph.workingSpace.rawValue). 导出 ACEScct / EXR is the timeline deliverable. Rec.709 / HLG / PQ panes are 预览·非成片 — not a finished grade.")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}

private struct ExposureInspector: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        Toggle("Enable Exposure (node 2). Off / 0 stops = identity, not baked into IDT or WB.", isOn: Binding(
            get: { session.graph.exposureEnabled },
            set: { session.setExposureEnabled($0) }
        ))
        if session.graph.exposureEnabled {
            HStack {
                Text("Stops")
                    .frame(width: 48, alignment: .leading)
                Slider(
                    value: Binding(
                        get: { session.graph.exposureStops },
                        set: { session.setExposureStops($0) }
                    ),
                    in: -8...8,
                    step: 0.05
                )
                Text(String(format: "%+.2f st", session.graph.exposureStops))
                    .monospacedDigit()
                    .frame(width: 72, alignment: .trailing)
            }
            Text(String(format: "Linear gain 2^stops = %.4f", pow(2.0, session.graph.exposureStops)))
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
        }
        Text("User-facing unit is stops. After IDT, in ACES2065-1 linear: rgb × (2^stops). Do not add/subtract Log code values. Preview cache stores post-IDT linear; exposure applies in linear before WB.")
            .font(.caption)
            .foregroundStyle(.secondary)
        Text("预览·非成片 — Rec.709 / HLG / PQ are preview only, not a finished picture.")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}
