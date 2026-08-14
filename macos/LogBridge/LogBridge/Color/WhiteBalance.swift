import Foundation
import simd

/// Scene-linear white-balance node (Bradford CAT, CCT + green-magenta tint).
///
/// Scene-linear ACES2065-1 (AP0) after IDT. Never a CAT on ACEScct-encoded values.
/// This math is applied in AP0 scene-linear RGB, never in log. The node can be
/// toggled off for Resolve export so WB is not baked (disable node 2 = IDT → ACEScct).
enum WhiteBalanceNode {
    /// Bradford cone-response matrix (CIE).
    static let bradford = simd_double3x3(rows: [
        SIMD3(0.8951, 0.2664, -0.1614),
        SIMD3(-0.7502, 1.7135, 0.0367),
        SIMD3(0.0389, -0.0685, 1.0296)
    ])

    static let cat02 = simd_double3x3(rows: [
        SIMD3(0.7328, 0.4296, -0.1624),
        SIMD3(-0.7036, 1.6975, 0.0061),
        SIMD3(0.0030, 0.0136, 0.9834)
    ])

    static let d65 = SIMD2<Double>(0.3127, 0.3290)

    static func xy(cct: Double, tint: Double = 0) -> SIMD2<Double> {
        // Daylight locus at T >= 4000 K so 6504 K ≈ D65 identity.
        // Planckian below 4000 K (tungsten). Full implementation matches color/wb.py.
        let t = max(cct, 1000)
        var x: Double
        var y: Double
        if t >= 4000 {
            let xd: Double
            if t <= 7000 {
                xd = 0.244063 + 0.09911e3 / t + 2.9678e6 / (t * t) - 4.6070e9 / (t * t * t)
            } else {
                xd = 0.237040 + 0.24748e3 / t + 1.9018e6 / (t * t) - 2.0064e9 / (t * t * t)
            }
            x = xd
            y = -3.0 * xd * xd + 2.870 * xd - 0.275
        } else {
            let inv = 1.0e3 / t
            let inv2 = 1.0e6 / (t * t)
            let inv3 = 1.0e9 / (t * t * t)
            x = -0.2661239 * inv3 - 0.2343580 * inv2 + 0.8776956 * inv + 0.179910
            y = -0.9549476 * x * x * x - 1.37418593 * x * x + 2.09137015 * x - 0.16748867
        }
        if tint != 0 {
            let denom = -2.0 * x + 12.0 * y + 3.0
            var u = 4.0 * x / denom
            var v = 6.0 * y / denom
            v += tint * 1.0e-3
            let d = 2.0 * u - 8.0 * v + 4.0
            x = 3.0 * u / d
            y = 2.0 * v / d
        }
        return SIMD2(x, y)
    }

    static func catMatrix(cct: Double, tint: Double = 0, method: String = "bradford") -> simd_double3x3 {
        let src = xy(cct: cct, tint: tint)
        let m = method == "cat02" ? cat02 : bradford
        let srcXYZ = xyToXYZ(src)
        let dstXYZ = xyToXYZ(d65)
        let srcCone = m * srcXYZ
        let dstCone = m * dstXYZ
        let scale = simd_double3x3(diagonal: SIMD3(
            dstCone.x / srcCone.x,
            dstCone.y / srcCone.y,
            dstCone.z / srcCone.z
        ))
        return simd_mul(simd_mul(m.inverse, scale), m)
    }

    /// Apply CAT in scene-linear RGB of a D65 space (XYZ CAT conjugated by RGB<->XYZ).
    static func apply(rgb: SIMD3<Double>, rgbToXYZ: simd_double3x3, cct: Double, tint: Double) -> SIMD3<Double> {
        let cat = catMatrix(cct: cct, tint: tint)
        let xyz = rgbToXYZ * rgb
        let adapted = cat * xyz
        return rgbToXYZ.inverse * adapted
    }

    private static func xyToXYZ(_ xy: SIMD2<Double>) -> SIMD3<Double> {
        SIMD3(xy.x / xy.y, 1.0, (1.0 - xy.x - xy.y) / xy.y)
    }
}
