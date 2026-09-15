import Foundation

/// Working-rate policy. Default is source metadata only.
/// A named rate applies only after the user picks one. Never a silent 24/30.
enum FrameRatePolicy: String, CaseIterable, Identifiable {
    case source
    case user

    var id: String { rawValue }

    var menuLabel: String {
        switch self {
        case .source: return "只用片源帧率"
        case .user: return "用户指定（未核对）"
        }
    }
}

/// Menu rates. Fractions are NTSC (24000/1001 …). Labels are not “detected”.
enum NamedFrameRate: String, CaseIterable, Identifiable {
    case p23976
    case p24
    case p25
    case p2997
    case p30
    case p50
    case p5994
    case p60

    var id: String { rawValue }

    var fps: Double {
        switch self {
        case .p23976: return 24000.0 / 1001.0
        case .p24: return 24
        case .p25: return 25
        case .p2997: return 30000.0 / 1001.0
        case .p30: return 30
        case .p50: return 50
        case .p5994: return 60000.0 / 1001.0
        case .p60: return 60
        }
    }

    var menuLabel: String {
        switch self {
        case .p23976: return "23.976"
        case .p24: return "24"
        case .p25: return "25"
        case .p2997: return "29.97"
        case .p30: return "30"
        case .p50: return "50"
        case .p5994: return "59.94"
        case .p60: return "60"
        }
    }
}

enum WorkingFrameRate {
    /// Timeline / preview land-on-frame rate. User pick wins only when chosen.
    static func timelineFPS(
        source: Double?,
        policy: FrameRatePolicy,
        user: NamedFrameRate?
    ) -> Double? {
        if policy == .user, let user {
            return user.fps
        }
        return published(source)
    }

    /// Export verify: source metadata first. User pick only fills a missing rate.
    static func verifyFPS(
        source: Double?,
        policy: FrameRatePolicy,
        user: NamedFrameRate?
    ) -> Double? {
        if let src = published(source) { return src }
        if policy == .user, let user { return user.fps }
        return nil
    }

    /// Disk estimate: same as verify — do not reuse the dest-disk guess here.
    static func estimateFPS(
        source: Double?,
        policy: FrameRatePolicy,
        user: NamedFrameRate?
    ) -> Double? {
        verifyFPS(source: source, policy: policy, user: user)
    }

    static func format(_ fps: Double) -> String {
        for named in NamedFrameRate.allCases {
            if abs(fps - named.fps) < 0.02 {
                return named.menuLabel
            }
        }
        return String(format: "%.3f", fps)
    }

    private static func published(_ value: Double?) -> Double? {
        guard let value, value.isFinite, value > 0 else { return nil }
        return value
    }
}
