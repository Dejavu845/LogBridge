import Foundation

/// Serial M1 graph: IDT → WB → optional Rec.709 preview. Not a general node editor.
///
/// Slots match `color/graph.py` and Resolve export (01_IDT / 02_WB / 03_ODT).
/// Node 2 (WB) off = IDT → ACEScct, no bake. Node 3 (ODT) off = ACEScct deliverable
/// (preview only when on; not tagged Rec.709 when off).
enum NodeSlot: Int, CaseIterable, Identifiable, Hashable {
    case idt = 1
    case wb = 2
    case odt = 3

    var id: Int { rawValue }

    var title: String {
        switch self {
        case .idt: return "IDT"
        case .wb: return "WB"
        case .odt: return "ODT Rec.709"
        }
    }

    var exportBasename: String {
        switch self {
        case .idt: return "01_IDT"
        case .wb: return "02_WB"
        case .odt: return "03_ODT"
        }
    }

    var subtitle: String {
        switch self {
        case .idt: return "curve + gamut"
        case .wb: return "scene-linear CAT"
        case .odt: return "preview only"
        }
    }

    var isBypassable: Bool {
        self != .idt
    }
}

/// Session-level WB / ODT. IDT lives on the selected clip.
struct SerialGraph: Equatable {
    var wbEnabled: Bool = false
    var wbCCT: Double = 6504
    var wbTint: Double = 0
    var wbMethod: String = "bradford"
    var odtEnabled: Bool = false
    var workingSpace: FixedPipeline.WorkingSpace = .acescct

    func isEnabled(_ slot: NodeSlot) -> Bool {
        switch slot {
        case .idt: return true
        case .wb: return wbEnabled
        case .odt: return odtEnabled
        }
    }

    mutating func setEnabled(_ slot: NodeSlot, _ enabled: Bool) {
        switch slot {
        case .idt:
            break
        case .wb:
            wbEnabled = enabled
        case .odt:
            odtEnabled = enabled
        }
    }
}
