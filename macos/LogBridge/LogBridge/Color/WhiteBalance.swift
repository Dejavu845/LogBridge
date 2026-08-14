import Foundation
import simd

/// Scene-linear white-balance node (Bradford CAT, CCT + green-magenta tint).
///
/// Scene-linear ACES2065-1 (AP0) after IDT. Never a CAT on ACEScct-encoded values.
/// This math is applied in AP0 scene-linear RGB, never in log. The node can be
/// toggled off for Resolve export so WB is not baked (disable WB = IDT → Exposure → ACEScct).
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

    /// ACES2065-1 (AP0) → XYZ. Matches color/gamuts.py / PreviewColor.
    static let ap0ToXYZ = simd_double3x3(rows: [
        SIMD3(0.952552395938186, 0.000000000000000, 0.000093678631660),
        SIMD3(0.343966449765075, 0.728166096613486, -0.072132546378561),
        SIMD3(0.000000000000000, 0.000000000000000, 1.008825184351586)
    ])

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

    /// XYZ CAT taking src white to dst white (Bradford / CAT02).
    static func catMatrix(srcXY: SIMD2<Double>, dstXY: SIMD2<Double>, method: String = "bradford") -> simd_double3x3 {
        let m = method == "cat02" ? cat02 : bradford
        let srcXYZ = xyToXYZ(srcXY)
        let dstXYZ = xyToXYZ(dstXY)
        let srcCone = m * srcXYZ
        let dstCone = m * dstXYZ
        let scale = simd_double3x3(diagonal: SIMD3(
            dstCone.x / srcCone.x,
            dstCone.y / srcCone.y,
            dstCone.z / srcCone.z
        ))
        return simd_mul(simd_mul(m.inverse, scale), m)
    }

    static func catMatrix(cct: Double, tint: Double = 0, method: String = "bradford") -> simd_double3x3 {
        catMatrix(srcXY: xy(cct: cct, tint: tint), dstXY: d65, method: method)
    }

    /// Relative: CAT(user→D65)·inv(CAT(as→D65)) == CAT(user→as).
    /// 3200 as-shot → 5600 user warms (in-camera Kelvin).
    /// Not CAT(as→user), not CAT(user→D65) alone.
    static func relativeCatMatrix(
        srcCCT: Double,
        dstCCT: Double,
        srcTint: Double = 0,
        dstTint: Double = 0,
        method: String = "bradford"
    ) -> simd_double3x3 {
        let mUser = catMatrix(cct: dstCCT, tint: dstTint, method: method)
        let mShot = catMatrix(cct: srcCCT, tint: srcTint, method: method)
        return simd_mul(mUser, mShot.inverse)
    }

    /// Apply CAT in scene-linear RGB of a D65 space (XYZ CAT conjugated by RGB<->XYZ).
    /// `cct == nil` is pending / identity — do not guess 5600 or 6504.
    static func apply(rgb: SIMD3<Double>, rgbToXYZ: simd_double3x3, cct: Double?, tint: Double) -> SIMD3<Double> {
        guard let cct else { return rgb }
        let cat = catMatrix(cct: cct, tint: tint)
        let xyz = rgbToXYZ * rgb
        let adapted = cat * xyz
        return rgbToXYZ.inverse * adapted
    }

    private static func xyToXYZ(_ xy: SIMD2<Double>) -> SIMD3<Double> {
        SIMD3(xy.x / xy.y, 1.0, (1.0 - xy.x - xy.y) / xy.y)
    }

    private static func xyToUV(_ xy: SIMD2<Double>) -> SIMD2<Double> {
        let denom = -2.0 * xy.x + 12.0 * xy.y + 3.0
        return SIMD2(4.0 * xy.x / denom, 6.0 * xy.y / denom)
    }

    /// Invert the same locus as `xy(cct:tint:)`. Grey-card / pick-neutral.
    static func cctTint(fromXY xy: SIMD2<Double>) -> (cct: Double, tint: Double) {
        let uv = xyToUV(xy)
        func err(_ cct: Double) -> Double {
            let lu = xyToUV(Self.xy(cct: cct, tint: 0))
            let du = uv.x - lu.x
            let dv = uv.y - lu.y
            return du * du + dv * dv
        }
        var best = 6504.0
        var bestE = err(best)
        var c = 1000.0
        while c <= 20000.0 {
            let e = err(c)
            if e < bestE {
                bestE = e
                best = c
            }
            c += 50.0
        }
        var lo = max(1000.0, best - 50.0)
        var hi = min(20000.0, best + 50.0)
        let phi = (1.0 + 5.0.squareRoot()) / 2.0
        for _ in 0..<40 {
            let a = hi - (hi - lo) / phi
            let b = lo + (hi - lo) / phi
            if err(a) < err(b) { hi = b } else { lo = a }
        }
        let cct = 0.5 * (lo + hi)
        let locusUV = xyToUV(Self.xy(cct: cct, tint: 0))
        let tint = (uv.y - locusUV.y) / 1.0e-3
        return (cct, tint)
    }

    /// Grey-card: sample after IDT in ACES2065-1 (AP0) linear. Overrides metadata.
    static func pickNeutral(linearRGB: SIMD3<Double>, rgbToXYZ: simd_double3x3) -> (cct: Double, tint: Double)? {
        let xyz = rgbToXYZ * linearRGB
        let s = xyz.x + xyz.y + xyz.z
        guard s > 1e-12 else { return nil }
        return cctTint(fromXY: SIMD2(xyz.x / s, xyz.y / s))
    }
}
