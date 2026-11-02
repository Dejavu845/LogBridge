import AVFoundation
import CoreVideo
import Foundation

/// Writes Rec.709 preview proxies as ProRes 422 HQ (.mov).
/// Pixel path: graded display RGB 0..1 float → 8-bit BGRA → AVAssetWriter.
/// One frame at a time. No IDT / WB math here. 整段代理，代理精度.
enum ProResWriter {
    static let proresSuffix = "_Rec709_proxy.mov"

    static func deliverableURL(for clip: Clip, in directory: URL) -> URL {
        let stem = clip.url.deletingPathExtension().lastPathComponent
        return directory.appendingPathComponent("\(stem)\(proresSuffix)")
    }

    /// Holds the writer so an escaping frame callback can append without
    /// keeping every frame in memory.
    final class SessionBox {
        var session: EncodeSession?
    }

    /// One ProRes 422 HQ movie. Call append, then finish, from the same queue.
    final class EncodeSession {
        private let writer: AVAssetWriter
        private let input: AVAssetWriterInput
        private let adaptor: AVAssetWriterInputPixelBufferAdaptor
        private let width: Int
        private let height: Int
        private let frameDuration: CMTime
        private let attrs: [String: Any]
        private(set) var writtenFrames = 0
        private var closed = false

        init(width: Int, height: Int, fps: Double, to url: URL) throws {
            if FileManager.default.fileExists(atPath: url.path) {
                try FileManager.default.removeItem(at: url)
            }
            guard width > 0, height > 0 else {
                throw NSError(domain: "LogBridge", code: 2, userInfo: [
                    NSLocalizedDescriptionKey: "解码失败"
                ])
            }
            self.width = width
            self.height = height
            let rate = fps > 0 ? fps : 24.0
            frameDuration = CMTime(value: 1, timescale: CMTimeScale(max(1, Int32(rate.rounded()))))
            guard let writer = try? AVAssetWriter(outputURL: url, fileType: .mov) else {
                throw NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
            self.writer = writer
            let settings: [String: Any] = [
                AVVideoCodecKey: AVVideoCodecType.proRes422HQ,
                AVVideoWidthKey: width,
                AVVideoHeightKey: height
            ]
            let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
            input.expectsMediaDataInRealTime = false
            self.input = input
            attrs = [
                kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA),
                kCVPixelBufferWidthKey as String: width,
                kCVPixelBufferHeightKey as String: height
            ]
            adaptor = AVAssetWriterInputPixelBufferAdaptor(
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
        }

        func append(rgb: [Float]) throws {
            guard !closed else {
                throw NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
            let pixels = width * height
            guard rgb.count >= pixels * 3 else {
                throw NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
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
            let pts = CMTimeMultiply(frameDuration, multiplier: Int32(writtenFrames))
            if !adaptor.append(buffer, withPresentationTime: pts) {
                throw writer.error ?? NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
            writtenFrames += 1
        }

        func finish() throws {
            guard !closed else { return }
            closed = true
            input.markAsFinished()
            let sem = DispatchSemaphore(value: 0)
            writer.finishWriting {
                sem.signal()
            }
            sem.wait()
            if writer.status != .completed {
                throw writer.error ?? NSError(domain: "LogBridge", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "写出失败"
                ])
            }
        }

        func cancel() {
            guard !closed else { return }
            closed = true
            if writer.status == .writing {
                writer.cancelWriting()
            }
        }
    }

    /// Encode one ProRes 422 HQ movie from display-referred RGB frames.
    static func writeRec709ProRes422HQ(
        frames: [[Float]],
        width: Int,
        height: Int,
        fps: Double,
        to url: URL
    ) throws {
        guard !frames.isEmpty else {
            throw NSError(domain: "LogBridge", code: 2, userInfo: [
                NSLocalizedDescriptionKey: "解码失败"
            ])
        }
        let session = try EncodeSession(width: width, height: height, fps: fps, to: url)
        do {
            for frame in frames {
                try session.append(rgb: frame)
            }
            try session.finish()
        } catch {
            session.cancel()
            if FileManager.default.fileExists(atPath: url.path) {
                try? FileManager.default.removeItem(at: url)
            }
            throw error
        }
    }
}
