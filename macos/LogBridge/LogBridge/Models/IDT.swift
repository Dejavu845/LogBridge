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
        case .sonySLog3SGamut3, .sonySLog3SGamut3Cine: return "S-Log3"
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
        case .sonySLog3SGamut3: return "S-Gamut3"
        case .sonySLog3SGamut3Cine: return "S-Gamut3.Cine"
        case .panasonicVLogVGamut: return "V-Gamut"
        case .fujiFLog2BT2020, .nikonNLogBT2020: return "BT.2020"
        case .redLog3G10RWG: return "REDWideGamutRGB"
        case .canonCLog2Stub, .canonCLog3Stub: return "(stub)"
        case .appleLogStub: return "(stub)"
        case .djiDLogStub: return "(stub)"
        }
    }

    var menuLabel: String {
        if isStub {
            return "\(curve) / \(gamut) — stub, not implemented"
        }
        return "\(curve) / \(gamut) — implemented (unverified)"
    }

    /// OCIO colorspace name in ocio/config.ocio.
    var ocioName: String {
        switch self {
        case .arriLogC4AWG4: return "ARRI LogC4 AWG4"
        case .sonySLog3SGamut3: return "Sony S-Log3 S-Gamut3"
        case .sonySLog3SGamut3Cine: return "Sony S-Log3 S-Gamut3.Cine"
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
}
