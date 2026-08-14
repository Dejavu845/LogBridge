import Foundation

/// Fixed M1 pipeline. Not a node editor.
///
///   IDT (log → ACES2065-1 via OCIO Builtin or white-paper reference)
///     → optional WB node (Bradford/CAT02, CCT + tint, ACES2065-1 / AP0)
///     → ACEScct encode for timeline / grading display
///     → optional Rec.709 preview ODT (matrix + BT.709 OETF)
///
/// Resolve export keeps WB as a toggleable AP0 matrix rather than baking it.
/// Standard deliverable: ACEScct or ACES2065-1 EXR / ACES workflow.
/// Rec.709 is preview only.
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
