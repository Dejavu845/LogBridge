import SwiftUI
import CoreGraphics

/// Display-only bins from the current preview image.
/// Not a waveform, not a grade, not an input to export.
struct PreviewHistogramBins: Equatable {
    static let binCount = 32
    var red: [CGFloat]
    var green: [CGFloat]
    var blue: [CGFloat]

    static let empty = PreviewHistogramBins(
        red: Array(repeating: 0, count: binCount),
        green: Array(repeating: 0, count: binCount),
        blue: Array(repeating: 0, count: binCount)
    )
}

enum PreviewHistogramSampler {
    /// Downsamples for the on-demand histogram. Does not touch the write path.
    static func bins(from image: CGImage?) -> PreviewHistogramBins? {
        guard let image else { return nil }
        let width = 96
        let height = 54
        let bytesPerRow = width * 4
        var pixels = [UInt8](repeating: 0, count: height * bytesPerRow)
        let drew = pixels.withUnsafeMutableBytes { raw -> Bool in
            guard let base = raw.baseAddress,
                  let ctx = CGContext(
                    data: base,
                    width: width,
                    height: height,
                    bitsPerComponent: 8,
                    bytesPerRow: bytesPerRow,
                    space: CGColorSpaceCreateDeviceRGB(),
                    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
                  )
            else { return false }
            ctx.interpolationQuality = .low
            ctx.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard drew else { return nil }

        var red = [Int](repeating: 0, count: PreviewHistogramBins.binCount)
        var green = [Int](repeating: 0, count: PreviewHistogramBins.binCount)
        var blue = [Int](repeating: 0, count: PreviewHistogramBins.binCount)
        var index = 0
        while index + 3 < pixels.count {
            let alpha = Int(pixels[index + 3])
            if alpha >= 8 {
                red[Int(pixels[index]) * PreviewHistogramBins.binCount / 256] += 1
                green[Int(pixels[index + 1]) * PreviewHistogramBins.binCount / 256] += 1
                blue[Int(pixels[index + 2]) * PreviewHistogramBins.binCount / 256] += 1
            }
            index += 4
        }
        func normalize(_ bins: [Int]) -> [CGFloat] {
            let peak = bins.max() ?? 0
            guard peak > 0 else { return bins.map { _ in CGFloat(0) } }
            return bins.map { CGFloat($0) / CGFloat(peak) }
        }
        return PreviewHistogramBins(
            red: normalize(red),
            green: normalize(green),
            blue: normalize(blue)
        )
    }
}

/// Shown only inside 「高级」. 仅预览. Not a scope readout.
struct PreviewHistogramView: View {
    var image: CGImage?
    @State private var bins = PreviewHistogramBins.empty
    @State private var hasImage = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text("直方图")
                    .font(.subheadline.weight(.semibold))
                Text("仅预览")
                    .font(.caption2.weight(.bold))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.primary.opacity(0.08))
                    .clipShape(Capsule())
            }
            Text("按当前预览抽样，不参与写出。不是示波器读数。")
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if hasImage {
                HistogramBars(bins: bins)
                    .frame(height: 88)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            } else {
                Text("有预览画面后，这里才抽样。")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 72, alignment: .leading)
            }
        }
        .padding(10)
        .background(Color.primary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .task(id: image.map(ObjectIdentifier.init)) {
            let sampled = image
            let next = PreviewHistogramSampler.bins(from: sampled)
            bins = next ?? .empty
            hasImage = next != nil
        }
    }
}

private struct HistogramBars: View {
    let bins: PreviewHistogramBins

    var body: some View {
        Canvas { context, size in
            let count = CGFloat(bins.red.count)
            let slot = size.width / max(count, 1)
            fill(bins.red, color: Color.red.opacity(0.75), context: context, size: size, slot: slot)
            fill(bins.green, color: Color.green.opacity(0.55), context: context, size: size, slot: slot)
            fill(bins.blue, color: Color.blue.opacity(0.55), context: context, size: size, slot: slot)
        }
        .background(Color.black.opacity(0.88))
        .accessibilityLabel("直方图，仅预览")
    }

    private func fill(
        _ values: [CGFloat],
        color: Color,
        context: GraphicsContext,
        size: CGSize,
        slot: CGFloat
    ) {
        var path = Path()
        for (index, value) in values.enumerated() {
            let height = max(1, value * size.height)
            path.addRect(CGRect(
                x: CGFloat(index) * slot,
                y: size.height - height,
                width: max(1, slot - 0.4),
                height: height
            ))
        }
        context.fill(path, with: .color(color))
    }
}
