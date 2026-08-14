import Foundation

/// Locked curve + gamut pair. Sony S-Log3 has two gamuts; never default to Cine.
enum IDT: String, CaseIterable, Identifiable, Hashable {
    case arriLogC4AWG4 = "arri_logc4_awg4"
    case sonySLog3SGamut3 = "sony_slog3_sgamut3"
    case sonySLog3SGamut3Cine = "sony_slog3_sgamut3cine"
    case panasonicVLogVGamut = "panasonic_vlog_vgamut"
    case fujiFLog2BT2020 = "fujifilm_flog2_bt2020"
    case nikonNLogBT2020 = "nikon_nlog_bt2020"
    case redLog3G10RWG = "red_log3g10_rwg"
    case sonySLog3SGamut3Venice = "sony_slog3_sgamut3_venice"
    case sonySLog3SGamut3CineVenice = "sony_slog3_sgamut3cine_venice"
    // Stubs — shown in the picker as unimplemented.
    case canonCLog2Stub = "canon_clog2"
    case canonCLog3Stub = "canon_clog3"
    case appleLogStub = "apple_log"
    case djiDLogStub = "dji_dlog"

    var id: String { rawValue }

    var isStub: Bool {
        switch self {
        case .canonCLog2Stub, .canonCLog3Stub, .appleLogStub, .djiDLogStub:
            return true
        default:
            return false
        }
    }

    var curve: String {
        switch self {
        case .arriLogC4AWG4: return "LogC4"
        case .sonySLog3SGamut3, .sonySLog3SGamut3Cine, .sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice: return "S-Log3"
        case .panasonicVLogVGamut: return "V-Log"
        case .fujiFLog2BT2020: return "F-Log2"
        case .nikonNLogBT2020: return "N-Log"
        case .redLog3G10RWG: return "Log3G10"
        case .canonCLog2Stub: return "C-Log2"
        case .canonCLog3Stub: return "C-Log3"
        case .appleLogStub: return "Apple Log"
        case .djiDLogStub: return "D-Log"
        }
    }

    var gamut: String {
        switch self {
        case .arriLogC4AWG4: return "AWG4"
        case .sonySLog3SGamut3, .sonySLog3SGamut3Venice: return "S-Gamut3"
        case .sonySLog3SGamut3Cine, .sonySLog3SGamut3CineVenice: return "S-Gamut3.Cine"
        case .panasonicVLogVGamut: return "V-Gamut"
        case .fujiFLog2BT2020, .nikonNLogBT2020: return "BT.2020"
        case .redLog3G10RWG: return "REDWideGamutRGB"
        case .canonCLog2Stub, .canonCLog3Stub: return "(stub)"
        case .appleLogStub: return "(stub)"
        case .djiDLogStub: return "(stub)"
        }
    }

    var isVenice: Bool {
        switch self {
        case .sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice:
            return true
        default:
            return false
        }
    }

    /// Paired picker row. Never split into independent curve / gamut menus.
    var pairLabel: String {
        switch self {
        case .sonySLog3SGamut3Venice:
            return "S-Log3 + S-Gamut3 (Venice)"
        case .sonySLog3SGamut3CineVenice:
            return "S-Log3 + S-Gamut3.Cine (Venice)"
        default:
            return "\(curve) + \(gamut)"
        }
    }

    var menuLabel: String {
        if isStub {
            return "\(pairLabel) — stub, not implemented"
        }
        return "\(pairLabel) — implemented (unverified)"
    }

    /// OCIO colorspace name in ocio/config.ocio.
    var ocioName: String {
        switch self {
        case .arriLogC4AWG4: return "ARRI LogC4 AWG4"
        case .sonySLog3SGamut3: return "Sony S-Log3 S-Gamut3"
        case .sonySLog3SGamut3Cine: return "Sony S-Log3 S-Gamut3.Cine"
        case .sonySLog3SGamut3Venice: return "Sony S-Log3 S-Gamut3 Venice"
        case .sonySLog3SGamut3CineVenice: return "Sony S-Log3 S-Gamut3.Cine Venice"
        case .panasonicVLogVGamut: return "Panasonic V-Log V-Gamut"
        case .fujiFLog2BT2020: return "Fujifilm F-Log2 BT.2020"
        case .nikonNLogBT2020: return "Nikon N-Log BT.2020"
        case .redLog3G10RWG: return "RED Log3G10 REDWideGamutRGB"
        case .canonCLog2Stub: return "Canon C-Log2 (stub)"
        case .canonCLog3Stub: return "Canon C-Log3 (stub)"
        case .appleLogStub: return "Apple Log (stub)"
        case .djiDLogStub: return "DJI D-Log (stub)"
        }
    }

    /// Implemented (unverified) IDTs only — never stubs, never "supported".
    static var implemented: [IDT] {
        allCases.filter { !$0.isStub }
    }

    static var implementedCurves: [String] {
        var seen: [String] = []
        for idt in implemented where !idt.isVenice && !seen.contains(idt.curve) {
            seen.append(idt.curve)
        }
        return seen
    }

    static func pairs(forCurve curve: String, veniceDetected: Bool = false) -> [IDT] {
        pickerPairs(curveHint: curve, veniceDetected: veniceDetected, needsPicker: true)
    }

    static func gamuts(forCurve curve: String, veniceDetected: Bool = false) -> [String] {
        pairs(forCurve: curve, veniceDetected: veniceDetected).map(\.gamut)
    }

    /// Locked pair only. Nil if the curve+gamut combination is not an M1 IDT.
    /// Prefers the non-Venice pair unless `veniceDetected`.
    static func match(curve: String, gamut: String, veniceDetected: Bool = false) -> IDT? {
        let hits = implemented.filter { $0.curve == curve && $0.gamut == gamut }
        if veniceDetected {
            return hits.first(where: { $0.isVenice }) ?? hits.first
        }
        return hits.first(where: { !$0.isVenice }) ?? hits.first
    }

    /// Paired IDTs for the picker. Venice rows appear only if Venice is detected.
    /// S-Log3 needing a pick offers both gamuts — never a silent Cine default.
    static func pickerPairs(curveHint: String?, veniceDetected: Bool, needsPicker: Bool) -> [IDT] {
        let slog3 = Self.isSLog3(curveHint)
        if needsPicker && slog3 {
            return veniceDetected
                ? [.sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice]
                : [.sonySLog3SGamut3, .sonySLog3SGamut3Cine]
        }
        var pairs = implemented.filter { !$0.isVenice }
        if veniceDetected {
            if let idx = pairs.firstIndex(of: .sonySLog3SGamut3Cine) {
                pairs.insert(contentsOf: [.sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice], at: pairs.index(after: idx))
            } else {
                pairs.append(contentsOf: [.sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice])
            }
        }
        return pairs
    }

    static func isSLog3(_ curve: String?) -> Bool {
        guard let curve else { return false }
        let c = curve.lowercased().replacingOccurrences(of: "_", with: "-")
        return c == "slog3" || c == "s-log3"
    }
}
