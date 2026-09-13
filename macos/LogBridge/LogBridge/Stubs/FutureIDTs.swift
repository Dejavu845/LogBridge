import Foundation

/// Extension points for IDTs that stay unimplemented.
///
/// LogC3 EI800 + AWG3 and Apple Log 2 + Apple Wide Gamut are implemented
/// (unverified). This remains a stub:
///
/// - DJI D-Log M (unsupported; 2017 D-Log + D-Gamut only)
///
/// Cycle 21 lock: do not invent a D-Log M transfer or a Venice-specific
/// D-Log M pair. `dLogMIsSupported()` stays false until papers + 18%
/// tests + a paired picker exist.
enum FutureIDTs {
    static let notes: [(String, String)] = [
        ("DJI D-Log M", "Unsupported. Use D-Log + D-Gamut (2017 white paper).")
    ]

    /// Cycle 21 lock. D-Log M is not an IDT pair.
    static func dLogMIsSupported() -> Bool { false }
}
