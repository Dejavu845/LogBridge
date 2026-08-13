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
                    Text("Curve")
                        .font(.caption.weight(.semibold))
                    Picker("Curve", selection: Binding(
                        get: { clip.displayCurve ?? "" },
                        set: { session.setCurve(clip.id, curve: $0) }
                    )) {
                        Text("— pick —").tag("")
                        ForEach(IDT.implementedCurves, id: \.self) { curve in
                            Text(curve).tag(curve)
                        }
                    }
                    .labelsHidden()
                    .frame(maxWidth: 200)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Gamut")
                        .font(.caption.weight(.semibold))
                    let curve = clip.displayCurve ?? ""
                    let gamuts = IDT.gamuts(forCurve: curve)
                    Picker("Gamut", selection: Binding(
                        get: { clip.displayGamut ?? "" },
                        set: { session.setGamut(clip.id, gamut: $0) }
                    )) {
                        Text(gamuts.isEmpty ? "— pick curve first —" : "— pick gamut —").tag("")
                        ForEach(gamuts, id: \.self) { g in
                            Text(g).tag(g)
                        }
                    }
                    .labelsHidden()
                    .frame(maxWidth: 220)
                    .disabled(curve.isEmpty)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Status")
                        .font(.caption.weight(.semibold))
                    Text(clip.verificationBadge)
                        .font(.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.orange.opacity(0.2))
                        .clipShape(Capsule())
                    Text("source: \(clip.detectionSource.rawValue)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            if clip.displayCurve == "S-Log3", clip.idt == nil {
                Text("S-Log3 requires an explicit gamut. LogBridge never defaults to S-Gamut3.Cine.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
        } else {
            Text("Select a clip. Missing metadata needs a curve and a gamut — no silent default.")
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
        Text("Scene-linear Bradford/CAT02 in ACEScg. Disable this node in Resolve (or DCTL Bypass WB) to restore IDT → ACEScct → optional Rec.709 ODT.")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}

private struct ODTInspector: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        Toggle("Enable Rec.709 ODT (node 3). Off = ACEScct deliverable.", isOn: Binding(
            get: { session.graph.odtEnabled },
            set: { session.setODTEnabled($0) }
        ))
        Text("ODT preview is tagged CGColorSpace.itur_709 only when this node is on. Source stays untagged. No RRT. Implemented (unverified).")
            .font(.caption)
            .foregroundStyle(.secondary)
        Text("Working space: \(session.graph.workingSpace.rawValue). Timeline export is ACEScct (ACES2065-1 interchange).")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}
