import Foundation

/// Fixed M1 pipeline. Not a node editor.
///
///   IDT (log → ACES2065-1 via OCIO Builtin or white-paper reference)
///     → ACEScct (Academy grading; WB / preview)
///     → optional WB node (Bradford/CAT02, CCT + tint, scene-linear ACEScg)
///     → Rec.709 ODT (matrix + BT.709 OETF)
///
/// Resolve export keeps WB as a toggleable node rather than baking it into
/// a Rec.709-only deliverable. Export ACEScct or ACES2065-1 EXR / ACES workflow.
/// Do not bake DaVinci Wide Gamut Intermediate.
struct FixedPipeline {
    var idt: IDT
    var workingSpace: WorkingSpace = .acescct
    var whiteBalance: WhiteBalanceSettings = .identity
    var applyWhiteBalance: Bool = false

    enum WorkingSpace: String {
        case acescct = "ACEScct"
        case aces2065 = "ACES2065-1"
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
