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
///   - IDT ACES / ACEScct buffer per clip+IDT
/// Invalidate the matching stage only (IDT change drops linear; WB/ODT reuse it).
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
                    ? "Pick curve and gamut — preview ODT waits for a locked IDT"
                    : "Stub IDT — no preview process"
            )
            return
        }
        let linear = cachedLinear(clipID: clip.id, idt: idt, source: source)
        var work = linear.rgb
        if graph.wbEnabled {
            PreviewColor.applyWB(
                rgb: &work,
                cct: graph.wbCCT,
                tint: graph.wbTint,
                method: graph.wbMethod
            )
        }
        var odtCG: CGImage?
        var note = "Preview proxy (≤ \(Int(Self.maxLongEdge)) px). Not a full render."
        if graph.odtEnabled {
            PreviewColor.applyODT(rgb: &work)
            odtCG = PreviewColor.makeCGImage(
                rgb: work,
                width: linear.width,
                height: linear.height,
                colorSpace: CGColorSpace(name: CGColorSpace.itur_709)
            )
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
        guard let m = cameraToDWG(idt) else { return }
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

    static func applyWB(rgb: inout [Float], cct: Double, tint: Double, method: String) {
        let cat = WhiteBalanceNode.catMatrix(cct: cct, tint: tint, method: method)
        let m = dwgToXYZ.inverse * cat * dwgToXYZ
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
            let v = dwgToRec709 * SIMD3(Double(rgb[i * 3 + 0]), Double(rgb[i * 3 + 1]), Double(rgb[i * 3 + 2]))
            rgb[i * 3 + 0] = Float(rec709OETF(v.x))
            rgb[i * 3 + 1] = Float(rec709OETF(v.y))
            rgb[i * 3 + 2] = Float(rec709OETF(v.z))
        }
    }

    // MARK: Matrices / curves — copied from ResolveExporter (do not edit numbers)

    private static let dwgToXYZ = simd_double3x3(rows: [
        SIMD3(0.700622392094, 0.148774815123, 0.101058719835),
        SIMD3(0.274118510907, 0.873631895940, -0.147750406847),
        SIMD3(-0.098962912883, -0.137895325076, 1.325915988719)
    ])

    private static let dwgToRec709 = simd_double3x3(rows: [
        SIMD3(1.898614899306, -0.792176183404, -0.106438715902),
        SIMD3(-0.168948786476, 1.488975754118, -0.320026967642),
        SIMD3(-0.121539160604, -0.315675853052, 1.437215013657)
    ])

    private static let rec709Beta = 0.018053968510807
    private static let rec709Alpha = 1.09929682680944

    private static func rec709OETF(_ lin: Double) -> Double {
        if lin < rec709Beta { return 4.5 * lin }
        return rec709Alpha * pow(max(lin, 0.0), 0.45) - (rec709Alpha - 1.0)
    }

    private static func cameraToDWG(_ idt: IDT) -> simd_double3x3? {
        switch idt {
        case .arriLogC4AWG4:
            return simd_double3x3(rows: [
                SIMD3(0.997395939837, -0.023165014815, 0.025769074977),
                SIMD3(-0.009183081266, 0.917632034596, 0.091551046670),
                SIMD3(0.073487991967, 0.093704798362, 0.832807209671)
            ])
        case .sonySLog3SGamut3:
            return simd_double3x3(rows: [
                SIMD3(0.996650041836, -0.026739524102, 0.030089482265),
                SIMD3(0.008962001489, 0.925300630159, 0.065737368353),
                SIMD3(0.068020421169, 0.097704868626, 0.834274710205)
            ])
        case .sonySLog3SGamut3Cine:
            return simd_double3x3(rows: [
                SIMD3(0.852787225200, 0.132475794312, 0.014736980487),
                SIMD3(-0.014981188523, 0.987029009978, 0.027952178545),
                SIMD3(0.037907848534, 0.091678874858, 0.870413276608)
            ])
        case .panasonicVLogVGamut:
            return simd_double3x3(rows: [
                SIMD3(0.958788766787, 0.013416877789, 0.027794355424),
                SIMD3(0.008621548181, 0.898149016914, 0.093229434905),
                SIMD3(0.065436425015, 0.090930238374, 0.843633336611)
            ])
        case .fujiFLog2BT2020, .nikonNLogBT2020:
            return simd_double3x3(rows: [
                SIMD3(0.892112120946, 0.024369175871, 0.083518703182),
                SIMD3(0.032616601764, 0.786137516904, 0.181245881332),
                SIMD3(0.069977051186, 0.104749491904, 0.825273456911)
            ])
        case .redLog3G10RWG:
            return simd_double3x3(rows: [
                SIMD3(1.046183501418, -0.082175324998, 0.035991823580),
                SIMD3(0.002998821038, 0.962281459766, 0.034719719196),
                SIMD3(0.018301335409, -0.168020759769, 1.149719424360)
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
        default:
            return x
        }
    }
}
