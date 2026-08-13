import Foundation

/// Fixed M1 pipeline. Not a node editor.
///
///   IDT (log → camera scene-linear, manufacturer white paper)
///     → gamut convert to Linear DWG (internal)
///     → optional WB node (Bradford/CAT02, CCT + tint, scene-linear only)
///     → Rec.709 ODT (matrix + BT.709 OETF)
///
/// Resolve export keeps WB as a toggleable node rather than baking it into
/// a Rec.709-only deliverable.
struct FixedPipeline {
    var idt: IDT
    var workingSpace: WorkingSpace = .davinciWideGamutLinear
    var whiteBalance: WhiteBalanceSettings = .identity
    var applyWhiteBalance: Bool = false

    enum WorkingSpace: String {
        case davinciWideGamutLinear = "Linear DWG"
        case davinciIntermediate = "DaVinci Intermediate"
        case acescct = "ACEScct"
    }
}

struct WhiteBalanceSettings {
    var cct: Double
    var tint: Double
    var method: String

    static let identity = WhiteBalanceSettings(cct: 6504, tint: 0, method: "bradford")
}

enum PipelineStage: String, CaseIterable {
    case idt = "IDT"
    case whiteBalance = "WB (scene-linear)"
    case odt = "Rec.709 ODT"
}
