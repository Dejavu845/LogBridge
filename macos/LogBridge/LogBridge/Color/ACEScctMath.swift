import Foundation

/// ACEScct encode shared by Resolve cubes and the numeric parity test.
///
/// Linear is floored at 1e-10 before the branch. That is the same floor as
/// Python ``_acescct_encode_lut`` / ``acescct_encode(maximum(lin, 1e-10))``.
/// The analytic toe (negatives kept) stays in ``acescct_encode`` on the
/// Python side; cube tables and this Swift encode do not use it.
enum ACEScctMath {
    static let linFloor = 1e-10
    /// Half-float max. ACEScct of this value is the allocation top.
    static let linCeil = 65504.0

    private static let loS = 10.5402377416545
    private static let loO = 0.0729055341958355
    private static let breakLin = 0.0078125
    private static let breakLog = loS * breakLin + loO

    /// Floor at ``linFloor``, then the ACEScct piecewise encode.
    static func encode(_ lin: Double) -> Double {
        let v = max(lin, linFloor)
        if v <= breakLin {
            return loS * v + loO
        }
        return (log2(v) + 9.72) / 17.52
    }

    static func decode(_ enc: Double) -> Double {
        if enc <= breakLog {
            return (enc - loO) / loS
        }
        return pow(2.0, enc * 17.52 - 9.72)
    }

    /// Decode → gain → encode. The gained linear value is floored at 1e-10.
    static func exposureChannel(_ enc: Double, stops: Double) -> Double {
        let gained = decode(enc) * pow(2.0, stops)
        return encode(max(gained, linFloor))
    }

    static var cubeMin: Double { encode(linFloor) }
    static var cubeMax: Double { encode(linCeil) }
}
