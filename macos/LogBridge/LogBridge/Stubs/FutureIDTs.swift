import Foundation

/// Extension points for IDTs that stay unimplemented.
///
/// C-Log2 / C-Log3 / Apple Log 1 / D-Log are implemented (unverified).
/// These remain stubs:
///
/// - Apple Log 2 (out of scope)
/// - DJI D-Log M (unsupported; 2017 D-Log + D-Gamut only)
/// - ARRI LogC3 (unsupported; use LogC4)
enum FutureIDTs {
    static let notes: [(String, String)] = [
        ("Apple Log 2", "Unsupported. Out of scope. Apple Log 1 + BT.2020 is implemented (unverified)."),
        ("DJI D-Log M", "Unsupported. Use D-Log + D-Gamut (2017 white paper)."),
        ("ARRI LogC3", "Unsupported. Use LogC4 + AWG4.")
    ]
}
