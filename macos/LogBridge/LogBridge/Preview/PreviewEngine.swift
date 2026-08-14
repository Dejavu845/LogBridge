import Foundation
import AppKit
import simd
import AVFoundation
import CoreGraphics
import ImageIO
import VideoToolbox
import Combine

/// Downscaled preview (max 1920 long edge). Not a full-resolution render.
///
/// Cache:
///   - decoded camera/log thumbnail per clip URL
///   - IDT ACES2065-1 linear buffer per clip+IDT (post-IDT linear; no exposure)
/// Invalidate the matching stage only (IDT change drops linear; exposure+WB
/// apply in linear on that cached AP0 buffer).
/// Heavy work runs off the main thread.
final class PreviewEngine: ObservableObject {
    static let maxLongEdge: CGFloat = 1920

    @Published var sourceImage: CGImage?
    @Published var odtImage: CGImage?
    @Published var status: String = "No clip"
    @Published var isWorking = false

    private let queue = DispatchQueue(label: "app.logbridge.preview", qos: .userInitiated)
    private var generation: UInt64 = 0

    private var sourceCache: [UUID: SourceFrame] = [:]
    private var linearCache: [UUID: LinearFrame] = [:]

    struct SourceFrame {
        let url: URL
        let width: Int
        let height: Int
        let rgb: [Float]
        let cgImage: CGImage
    }

    struct LinearFrame {
        let idtID: String
        let width: Int
        let height: Int
        let rgb: [Float]
    }

    func invalidateIDT(clipID: UUID) {
        linearCache[clipID] = nil
    }

    func invalidateWBODT() {
        // Linear IDT buffer is reused; nothing to drop.
    }

    func evict(clipID: UUID) {
        sourceCache[clipID] = nil
        linearCache[clipID] = nil
    }

    func refresh(clip: Clip?, graph: SerialGraph) {
        generation += 1
        let gen = generation
        guard let clip else {
            sourceImage = nil
            odtImage = nil
            status = "No clip"
            isWorking = false
            return
        }
        isWorking = true
        status = "Decoding preview…"
        let graphCopy = graph
        queue.async { [weak self] in
            self?.build(clip: clip, graph: graphCopy, generation: gen)
        }
    }

    private func build(clip: Clip, graph: SerialGraph, generation: UInt64) {
        let source = cachedSource(clip: clip)
        guard let source else {
            publish(generation: generation, source: nil, odt: nil, status: "Could not decode a preview frame")
            return
        }
        guard let idt = clip.idt, !idt.isStub else {
            publish(
                generation: generation,
                source: source.cgImage,
                odt: nil,
                status: clip.needsUserPicker
                    ? "Pick a paired IDT — process and preview ODT stay blocked"
                    : "Stub IDT — no preview process"
            )
            return
        }
        let linear = cachedLinear(clipID: clip.id, idt: idt, source: source)
        var work = linear.rgb
        // Cache is post-IDT linear. Apply exposure then WB in ACES2065-1.
        if graph.exposureEnabled {
            PreviewColor.applyExposure(rgb: &work, stops: graph.exposureStops)
        }
        // As-shot-unmoved and missing CCT are identity — do not guess 5600 or 6504.
        // effectiveWBCCT is nil until the user moves knobs or picks a grey card.
        if graph.wbEnabled, let cct = graph.effectiveWBCCT {
            PreviewColor.applyWB(
                rgb: &work,
                cct: cct,
                tint: graph.wbTint,
                method: graph.wbMethod
            )
        }
        var odtCG: CGImage?
        var note = "Preview proxy (≤ \(Int(Self.maxLongEdge)) px). Not a full render."
        if graph.odt == .rec709 {
            PreviewColor.applyODT(rgb: &work)
            odtCG = PreviewColor.makeCGImage(
                rgb: work,
                width: linear.width,
                height: linear.height,
                colorSpace: CGColorSpace(name: CGColorSpace.itur_709)
            )
        } else if graph.odt.isHDR {
            // No homemade HLG/PQ. Preview does not invent a Rec.2100 transfer.
            note = "\(graph.odt.acesOTNote) 预览·非成片 — preview does not apply a homemade HDR curve."
        } else {
            note = "ODT off — ACEScct deliverable. Rec.709 pane is not tagged."
        }
        publish(generation: generation, source: source.cgImage, odt: odtCG, status: note)
    }

    private func cachedSource(clip: Clip) -> SourceFrame? {
        if let hit = sourceCache[clip.id], hit.url == clip.url {
            return hit
        }
        guard let cg = Self.decodeDownscaled(url: clip.url, maxLongEdge: Self.maxLongEdge) else {
            return nil
        }
        let rgb = PreviewColor.extractRGB(cg)
        let frame = SourceFrame(
            url: clip.url,
            width: cg.width,
            height: cg.height,
            rgb: rgb,
            cgImage: cg
        )
        sourceCache[clip.id] = frame
        return frame
    }

    private func cachedLinear(clipID: UUID, idt: IDT, source: SourceFrame) -> LinearFrame {
        if let hit = linearCache[clipID], hit.idtID == idt.rawValue,
           hit.width == source.width, hit.height == source.height {
            return hit
        }
        var rgb = source.rgb
        PreviewColor.applyIDT(rgb: &rgb, idt: idt)
        let frame = LinearFrame(idtID: idt.rawValue, width: source.width, height: source.height, rgb: rgb)
        linearCache[clipID] = frame
        return frame
    }

    private func publish(generation: UInt64, source: CGImage?, odt: CGImage?, status: String) {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.generation == generation else { return }
            self.sourceImage = source
            self.odtImage = odt
            self.status = status
            self.isWorking = false
        }
    }

    /// Sample cached post-IDT (post-exposure if enabled) linear AP0 RGB at a normalized point.
    func sampleLinearRGB(clipID: UUID, nx: Double, ny: Double, exposureStops: Double, exposureEnabled: Bool) -> SIMD3<Double>? {
        guard let linear = linearCache[clipID] else { return nil }
        let x = min(max(Int((nx * Double(linear.width)).rounded(.down)), 0), max(linear.width - 1, 0))
        let y = min(max(Int((ny * Double(linear.height)).rounded(.down)), 0), max(linear.height - 1, 0))
        let i = (y * linear.width + x) * 3
        guard i + 2 < linear.rgb.count else { return nil }
        var r = Double(linear.rgb[i])
        var g = Double(linear.rgb[i + 1])
        var b = Double(linear.rgb[i + 2])
        if exposureEnabled && exposureStops != 0 {
            let gain = pow(2.0, exposureStops)
            r *= gain; g *= gain; b *= gain
        }
        return SIMD3(r, g, b)
    }

    /// AVAssetImageGenerator (VideoToolbox) for movies; ImageIO thumbnail for stills.
    static func decodeDownscaled(url: URL, maxLongEdge: CGFloat) -> CGImage? {
        if let src = CGImageSourceCreateWithURL(url as CFURL, nil) {
            let count = CGImageSourceGetCount(src)
            if count > 0 {
                let opts: [CFString: Any] = [
                    kCGImageSourceCreateThumbnailFromImageAlways: true,
                    kCGImageSourceThumbnailMaxPixelSize: maxLongEdge,
                    kCGImageSourceCreateThumbnailWithTransform: true,
                    kCGImageSourceCreateThumbnailFromImageIfAbsent: true
                ]
                if let thumb = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) {
                    return thumb
                }
            }
        }
        let asset = AVURLAsset(url: url)
        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.maximumSize = CGSize(width: maxLongEdge, height: maxLongEdge)
        // VideoToolbox-backed decode of one frame — never the full-res timeline.
        return try? gen.copyCGImage(at: .zero, actualTime: nil)
    }
}

/// Preview-only color apply. Constants must match ResolveExporter / color/*.py.
/// Do not "improve" manufacturer numbers here — color science is audited separately.
enum PreviewColor {
    static func extractRGB(_ image: CGImage) -> [Float] {
        let w = image.width
        let h = image.height
        var rgba = [UInt8](repeating: 0, count: w * h * 4)
        let cs = CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue
        guard let ctx = CGContext(
            data: &rgba,
            width: w,
            height: h,
            bitsPerComponent: 8,
            bytesPerRow: w * 4,
            space: cs,
            bitmapInfo: info
        ) else {
            return [Float](repeating: 0, count: w * h * 3)
        }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        var rgb = [Float](repeating: 0, count: w * h * 3)
        for i in 0..<(w * h) {
            rgb[i * 3 + 0] = Float(rgba[i * 4 + 0]) / 255
            rgb[i * 3 + 1] = Float(rgba[i * 4 + 1]) / 255
            rgb[i * 3 + 2] = Float(rgba[i * 4 + 2]) / 255
        }
        return rgb
    }

    static func makeCGImage(rgb: [Float], width: Int, height: Int, colorSpace: CGColorSpace?) -> CGImage? {
        var rgba = [UInt8](repeating: 255, count: width * height * 4)
        for i in 0..<(width * height) {
            rgba[i * 4 + 0] = u8(rgb[i * 3 + 0])
            rgba[i * 4 + 1] = u8(rgb[i * 3 + 1])
            rgba[i * 4 + 2] = u8(rgb[i * 3 + 2])
        }
        let cs = colorSpace ?? CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue
        guard let ctx = CGContext(
            data: &rgba,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: cs,
            bitmapInfo: info
        ) else { return nil }
        return ctx.makeImage()
    }

    private static func u8(_ x: Float) -> UInt8 {
        UInt8(clamping: Int((min(max(x, 0), 1) * 255).rounded()))
    }

    static func applyIDT(rgb: inout [Float], idt: IDT) {
        guard let m = cameraToAP0(idt) else { return }
        let n = rgb.count / 3
        for i in 0..<n {
            let r = decodeLog(Double(rgb[i * 3 + 0]), idt: idt)
            let g = decodeLog(Double(rgb[i * 3 + 1]), idt: idt)
            let b = decodeLog(Double(rgb[i * 3 + 2]), idt: idt)
            let v = m * SIMD3(r, g, b)
            rgb[i * 3 + 0] = Float(v.x)
            rgb[i * 3 + 1] = Float(v.y)
            rgb[i * 3 + 2] = Float(v.z)
        }
    }

    static func applyExposure(rgb: inout [Float], stops: Double) {
        // ACES2065-1 linear: rgb * (2 ** stops). Not a log-code add.
        if stops == 0 { return }
        let gain = Float(pow(2.0, stops))
        for i in 0..<rgb.count {
            rgb[i] *= gain
        }
    }

    static func applyWB(rgb: inout [Float], cct: Double, tint: Double, method: String) {
        // CAT in ACES2065-1 (AP0) scene-linear. Preview cache is AP0 after IDT.
        let cat = WhiteBalanceNode.catMatrix(cct: cct, tint: tint, method: method)
        let m = ap0ToXYZ.inverse * cat * ap0ToXYZ
        let n = rgb.count / 3
        for i in 0..<n {
            let v = m * SIMD3(Double(rgb[i * 3 + 0]), Double(rgb[i * 3 + 1]), Double(rgb[i * 3 + 2]))
            rgb[i * 3 + 0] = Float(v.x)
            rgb[i * 3 + 1] = Float(v.y)
            rgb[i * 3 + 2] = Float(v.z)
        }
    }

    static func applyODT(rgb: inout [Float]) {
        let n = rgb.count / 3
        for i in 0..<n {
            let v = ap0ToRec709 * SIMD3(Double(rgb[i * 3 + 0]), Double(rgb[i * 3 + 1]), Double(rgb[i * 3 + 2]))
            rgb[i * 3 + 0] = Float(rec709OETF(v.x))
            rgb[i * 3 + 1] = Float(rec709OETF(v.y))
            rgb[i * 3 + 2] = Float(rec709OETF(v.z))
        }
    }

    // MARK: Matrices / curves — copied from ResolveExporter (do not edit numbers)

    private static let ap0ToXYZ = simd_double3x3(rows: [
        SIMD3(0.952552395938186, 0.000000000000000, 0.000093678631660),
        SIMD3(0.343966449765075, 0.728166096613486, -0.072132546378561),
        SIMD3(0.000000000000000, 0.000000000000000, 1.008825184351586)
    ])

    private static let ap0ToRec709 = simd_double3x3(rows: [
        SIMD3(2.521686186743882, -1.134130988239719, -0.387555198504164),
        SIMD3(-0.276479914229922, 1.372719087668256, -0.096239173438334),
        SIMD3(-0.015378064966034, -0.152975335867399, 1.168353400833433)
    ])

    private static let rec709Beta = 0.018053968510807
    private static let rec709Alpha = 1.09929682680944

    private static func rec709OETF(_ lin: Double) -> Double {
        if lin < rec709Beta { return 4.5 * lin }
        return rec709Alpha * pow(max(lin, 0.0), 0.45) - (rec709Alpha - 1.0)
    }

    private static func cameraToAP0(_ idt: IDT) -> simd_double3x3? {
        switch idt {
        case .arriLogC4AWG4:
            return simd_double3x3(rows: [
                SIMD3(0.751244868485, 0.143007909499, 0.105747222016),
                SIMD3(0.001403392600, 1.005384442231, -0.006787834830),
                SIMD3(-0.000803152607, 0.003263851374, 0.997539301233)
            ])
        case .sonySLog3SGamut3:
            return simd_double3x3(rows: [
                SIMD3(0.753230840311, 0.141947913791, 0.104821245898),
                SIMD3(0.022234917350, 1.013293794080, -0.035528711431),
                SIMD3(-0.009600262790, 0.007505931314, 1.002094331476)
            ])
        case .sonySLog3SGamut3Cine:
            return simd_double3x3(rows: [
                SIMD3(0.639008308411, 0.270840678932, 0.090151012656),
                SIMD3(-0.003450727728, 1.085955398170, -0.082504670442),
                SIMD3(-0.030074188115, -0.021937342610, 1.052011530726)
            ])
        case .panasonicVLogVGamut:
            return simd_double3x3(rows: [
                SIMD3(0.724616704132, 0.166915288194, 0.108468007675),
                SIMD3(0.021390245413, 0.984908155703, -0.006298401116),
                SIMD3(-0.009235562871, -0.001056905639, 1.010292468510)
            ])
        case .fujiFLog2BT2020, .nikonNLogBT2020:
            return simd_double3x3(rows: [
                SIMD3(0.679085634707, 0.157700914643, 0.163213450650),
                SIMD3(0.046002003080, 0.859054673003, 0.094943323917),
                SIMD3(-0.000573943188, 0.028467768408, 0.972106174780)
            ])
        case .redLog3G10RWG:
            return simd_double3x3(rows: [
                SIMD3(0.785058804068, 0.083858756544, 0.131082439388),
                SIMD3(0.023173834845, 1.087897549192, -0.111071384038),
                SIMD3(-0.073760435368, -0.314590072290, 1.388350507658)
            ])
        case .canonCLog2CGamut, .canonCLog3CGamut:
            return simd_double3x3(rows: [
                SIMD3(0.763342923317, 0.147229267219, 0.089427809463),
                SIMD3(0.004230590136, 1.104451311582, -0.108681901718),
                SIMD3(-0.009670967662, -0.213042645554, 1.222713613216)
            ])
        case .canonCLog2BT2020, .canonCLog3BT2020, .appleLogBT2020:
            return simd_double3x3(rows: [
                SIMD3(0.679085634707, 0.157700914643, 0.163213450650),
                SIMD3(0.046002003080, 0.859054673003, 0.094943323917),
                SIMD3(-0.000573943188, 0.028467768408, 0.972106174780)
            ])
        case .djiDLogDGamut:
            return simd_double3x3(rows: [
                SIMD3(0.691430323906, 0.212906283248, 0.095663392846),
                SIMD3(0.066597281331, 1.009546581651, -0.076143862983),
                SIMD3(-0.017243534539, -0.072986432766, 1.090229967305)
            ])
        default:
            return nil
        }
    }

    private static func decodeLog(_ x: Double, idt: IDT) -> Double {
        switch idt {
        case .arriLogC4AWG4:
            let a = (pow(2.0, 18.0) - 16.0) / 117.45
            let b = (1023.0 - 95.0) / 1023.0
            let c = 95.0 / 1023.0
            let p = 14.0 * (x - c) / b + 6.0
            return (pow(2.0, p) - 64.0) / a
        case .sonySLog3SGamut3, .sonySLog3SGamut3Cine:
            let cut = 171.2102946929 / 1023.0
            let cv = x * 1023.0
            if x >= cut {
                return pow(10.0, (cv - 420.0) / 261.5) * (0.18 + 0.01) - 0.01
            }
            return (cv - 95.0) * 0.01125000 / (171.2102946929 - 95.0)
        case .panasonicVLogVGamut:
            if x >= 0.181 {
                return pow(10.0, (x - 0.598206) / 0.241514) - 0.00873
            }
            return (x - 0.125) / 5.6
        case .fujiFLog2BT2020:
            let a = 5.555556
            if x >= 0.100686685370811 {
                return pow(10.0, (x - 0.384316) / 0.245281) / a - 0.064829 / a
            }
            return (x - 0.092864) / 8.799461
        case .nikonNLogBT2020:
            let cv = x * 1023.0
            if cv < 452.0 {
                return pow(cv / 650.0, 3.0) - 0.0075
            }
            return exp((cv - 619.0) / 150.0)
        case .redLog3G10RWG:
            if x >= 0.0 {
                return (pow(10.0, x / 0.224282) - 1.0) / 155.975327 - 0.01
            }
            return x / 15.1927 - 0.01
        case .canonCLog2CGamut, .canonCLog2BT2020:
            let cut = 0.092864125
            let c1 = 0.24136077
            let c2 = 87.099375
            if x >= cut {
                return 0.9 * (pow(10.0, (x - cut) / c1) - 1.0) / c2
            }
            return -0.9 * (pow(10.0, (cut - x) / c1) - 1.0) / c2
        case .canonCLog3CGamut, .canonCLog3BT2020:
            let a = 0.36726845
            let b = 14.98325
            let ire: Double
            if x < 0.097465473 {
                ire = -(pow(10.0, (0.12783901 - x) / a) - 1.0) / b
            } else if x <= 0.15277891 {
                ire = (x - 0.12512219) / 1.9754798
            } else {
                ire = (pow(10.0, (x - 0.12240537) / a) - 1.0) / b
            }
            return ire * 0.9
        case .appleLogBT2020:
            let r0 = -0.05641088
            let c = 47.28711236
            let beta = 0.00964052
            let gamma = 0.08550479
            let delta = 0.69336945
            let pt = c * pow(0.01 - r0, 2.0)
            if x >= pt {
                return pow(2.0, (x - delta) / gamma) - beta
            }
            if x >= 0.0 {
                return sqrt(x / c) + r0
            }
            return r0
        case .djiDLogDGamut:
            if x > 0.14 {
                return (pow(10.0, 3.89616 * x - 2.27752) - 0.0108) / 0.9892
            }
            return (x - 0.0929) / 6.025
        default:
            return x
        }
    }
}
