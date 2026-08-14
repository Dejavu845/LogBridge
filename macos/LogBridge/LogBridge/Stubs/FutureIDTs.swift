import Foundation

/// Extension points for IDTs not in M1. Stubs only.
///
/// Canon C-Log2 has a negative toe. Do **not** invent a mirrored-toe analytic
/// curve. Use the official OCIO builtin or ACES CLF:
///
///     CURVE - CANON_CLOG2_to_LINEAR
enum FutureIDTs {
    static let canonCLog2Builtin = "CURVE - CANON_CLOG2_to_LINEAR"
    static let canonCLog2IDTBuiltin = "CANON_CLOG2-CGAMUT_to_ACES2065-1"
    static let canonCLog3Builtin = "CURVE - CANON_CLOG3_to_LINEAR"

    static let notes: [(String, String)] = [
        ("Canon C-Log2", "Stub. Negative toe: use OCIO \(canonCLog2Builtin) / \(canonCLog2IDTBuiltin) / ACES CLF. Do not invent a mirrored toe."),
        ("Canon C-Log3", "Stub. Use OCIO \(canonCLog3Builtin) / ACES CLF."),
        ("Apple Log", "Stub. Out of scope for M1."),
        ("DJI D-Log", "Stub. Out of scope for M1.")
    ]
}
