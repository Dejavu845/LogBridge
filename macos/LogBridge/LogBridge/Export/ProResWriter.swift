import AVFoundation
import CoreVideo
import Foundation

/// Writes Rec.709 preview proxies as ProRes 422 HQ (.mov).
/// Pixel path: graded display RGB 0..1 float → 16-bit → AVAssetWriter.
/// No IDT / WB math here. 整段代理，代理精度.
enum ProResWriter {
    static let proresSuffix = "_Rec709_proxy.mov"

    static func deliverableURL(for clip: Clip, in directory: URL) -> URL {
        let stem = clip.url.deletingPathExtension().lastPathComponent
        return directory.appendingPathComponent("\(stem)\(proresSuffix)")
    }

    /// Encode one ProRes 422 HQ movie from display-referred RGB frames.
    static func writeRec709ProRes422HQ(
        frames: [[Float]],
        width: Int,
        height: Int,
        fps: Double,
        to url: URL
    ) throws {
        if FileManager.default.fileExists(atPath: url.path) {
            try FileManager.default.removeItem(at: url)
        }
        guard width > 0, height > 0, !frames.isEmpty else {
            throw NSError(domain: "LogBridge", code: 2, userInfo: [
                NSLocalizedDescriptionKey: "解码失败"
            ])
        }
        let rate = fps > 0 ? fps : 24.0
        guard let writer = try? AVAssetWriter(outputURL: url, fileType: .mov) else {
            throw NSError(domain: "LogBridge", code: 3, userInfo: [
                NSLocalizedDescriptionKey: "写出失败"
            ])
        }
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.proRes422HQ,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = false
        let attrs: [String: Any] = [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA),
            kCVPixelBufferWidthKey as String: width,
            kCVPixelBufferHeightKey as String: height
        ]
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(
            assetWriterInput: input,
            sourcePixelBufferAttributes: attrs
        )
        guard writer.canAdd(input) else {
            throw NSError(domain: "LogBridge", code: 3, userInfo: [
                NSLocalizedDescriptionKey: "写出失败"
            ])
        }
        writer.add(input)
        guard writer.startWriting() else {
            throw writer.error ?? NSError(domain: "LogBridge", code: 3, userInfo: [
                NSLocalizedDescriptionKey: "写出失败"
            ])
        }
        writer.startSession(atSourceTime: .zero)
        let frameDuration = CMTime(value: 1, timescale: CMTimeScale(max(1, Int32(rate.rounded()))))
        for (index, rgb) in frames.enumerated() {
            while !input.isReadyForMoreMediaData {
                Thread.sleep(forTimeInterval: 0.002)
            }
            var pixelBuffer: CVPixelBuffer?
            let status = CVPixelBufferCreate(
                kCFAllocatorDefault,
                width,
                height,
                kCVPixelFormatType_32BGRA,
                attrs as CFDictionary,
                &pixelBuffer
            )
            guard status == kCVReturnSuccess, let buffer = pixelBuffer else {
                throw NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
            CVPixelBufferLockBaseAddress(buffer, [])
            defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
            guard let base = CVPixelBufferGetBaseAddress(buffer) else {
                throw NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
            let stride = CVPixelBufferGetBytesPerRow(buffer)
            let ptr = base.assumingMemoryBound(to: UInt8.self)
            let pixels = width * height
            for p in 0..<pixels {
                let r = max(0.0, min(1.0, Double(rgb[p * 3 + 0])))
                let g = max(0.0, min(1.0, Double(rgb[p * 3 + 1])))
                let b = max(0.0, min(1.0, Double(rgb[p * 3 + 2])))
                let row = p / width
                let col = p % width
                let o = row * stride + col * 4
                ptr[o + 0] = UInt8(b * 255.0 + 0.5)
                ptr[o + 1] = UInt8(g * 255.0 + 0.5)
                ptr[o + 2] = UInt8(r * 255.0 + 0.5)
                ptr[o + 3] = 255
            }
            let pts = CMTimeMultiply(frameDuration, multiplier: Int32(index))
            if !adaptor.append(buffer, withPresentationTime: pts) {
                throw writer.error ?? NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
        }
        input.markAsFinished()
        let finished = writer.finishWriting()
        if !finished || writer.status != .completed {
            throw writer.error ?? NSError(domain: "LogBridge", code: 3, userInfo: [
                NSLocalizedDescriptionKey: "写出失败"
            ])
        }
    }
}
