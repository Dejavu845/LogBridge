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
                    Text("S-Log3 + S-Gamut3 vs S-Log3 + S-Gamut3.Cine. Venice pair only if detected.")
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
                Text("This clip is pending. Process selected / Apply graph and export are blocked until a locked pair is chosen. Never a silent S-Gamut3.Cine default.")
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
        Toggle("Enable WB (node 2). Off = bypass, no bake in preview or Resolve export.", isOn: Binding(
            get: { session.graph.wbEnabled },
            set: { session.setWBEnabled($0) }
        ))
        if session.graph.wbEnabled {
            HStack {
                Text("CCT")
                    .frame(width: 40, alignment: .leading)
                Slider(
                    value: Binding(
                        get: { session.graph.wbCCT },
                        set: { session.setWBParams(cct: $0) }
                    ),
                    in: 2000...10000,
                    step: 10
                )
                Text("\(Int(session.graph.wbCCT)) K")
                    .monospacedDigit()
                    .frame(width: 64, alignment: .trailing)
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
        Text("Scene-linear Bradford/CAT02 in ACES2065-1 (AP0). Disable this node in Resolve (or DCTL Bypass WB) = IDT → ACEScct, no bake.")
            .font(.caption)
            .foregroundStyle(.secondary)
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
            Text("HDR OT via ACES/BT.2100 BuiltinTransform. No homemade HLG/PQ curve. Implemented (unverified). Not supported. Not 一键精准.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        Text("Working space: \(session.graph.workingSpace.rawValue). 导出 ACEScct / EXR is the timeline deliverable.")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}
