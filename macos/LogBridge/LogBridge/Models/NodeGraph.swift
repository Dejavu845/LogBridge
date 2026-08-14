import Foundation

/// Serial graph: IDT → WB → selectable ODT. Not a general node editor.
///
/// Slots match `color/graph.py` and Resolve export (01_IDT / 02_WB / 03_ODT).
/// Node 2 (WB) off = IDT → ACEScct, no bake. Node 3 ODT: Off (ACEScct) |
/// Rec.709 preview | Rec.2100 HLG | Rec.2100 PQ. Default Off.
enum NodeSlot: Int, CaseIterable, Identifiable, Hashable {
    case idt = 1
    case wb = 2
    case odt = 3

    var id: Int { rawValue }

    var title: String {
        switch self {
        case .idt: return "IDT"
        case .wb: return "WB"
        case .odt: return "ODT"
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
        case .odt: return "Off / 709 / HLG / PQ"
        }
    }

    var isBypassable: Bool {
        self != .idt
    }
}

/// ODT slot selector. Default Off = ACEScct deliverable.
enum ODTMode: String, CaseIterable, Identifiable, Hashable {
    case off = "off"
    case rec709 = "rec709"
    case hlg = "hlg"
    case pq = "pq"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .off: return "Off (ACEScct)"
        case .rec709: return "Rec.709 preview"
        case .hlg: return "Rec.2100 HLG"
        case .pq: return "Rec.2100 PQ"
        }
    }

    var isPreviewOnly: Bool { self == .rec709 }
    var isHDR: Bool { self == .hlg || self == .pq }
    var isEnabled: Bool { self != .off }

    /// ACES Output Transform / BT.2100 BuiltinTransform (no homemade curve).
    var acesOTNote: String {
        switch self {
        case .off:
            return "ACEScct timeline / ACES2065-1 EXR deliverable."
        case .rec709:
            return "Rec.709 preview only (DIY BT.709 OETF, no RRT). Implemented (unverified)."
        case .hlg:
            return "Rec.2100 HLG via ACES Output Transform / BT.2100. Implemented (unverified). Not supported."
        case .pq:
            return "Rec.2100 PQ via ACES Output Transform / BT.2100. Implemented (unverified). Not supported."
        }
    }
}

/// Session-level WB / ODT. IDT lives on the selected clip.
struct SerialGraph: Equatable {
    var wbEnabled: Bool = false
    var wbCCT: Double = 6504
    var wbTint: Double = 0
    var wbMethod: String = "bradford"
    var odt: ODTMode = .off
    var workingSpace: FixedPipeline.WorkingSpace = .acescct

    var odtEnabled: Bool {
        get { odt != .off }
        set { odt = newValue ? (odt == .off ? .rec709 : odt) : .off }
    }

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
