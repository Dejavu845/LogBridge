import SwiftUI
import AppKit
import CoreGraphics
import MetalKit
import QuartzCore

/// Color-managed Rec.709 preview.
///
/// The drawable / layer color space is tagged `CGColorSpace.itur_709`.
/// Rec.709 encoded pixels must NEVER be blit into an untagged layer
/// (AppKit/Metal default to Display P3 on modern Macs, which would
/// silently expand 709 primaries and saturate the image).
struct Rec709PreviewView: View {
    let title: String
    let caption: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            Rec709MetalPreview()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            Text(caption)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(8)
    }
}

/// MTKView subclass whose `colorspace` is Rec.709 (ITU-R BT.709).
final class Rec709MTKView: MTKView {
    override init(frame frameRect: CGRect, device: MTLDevice?) {
        super.init(frame: frameRect, device: device)
        configureRec709()
    }

    required init(coder: NSCoder) {
        super.init(coder: coder)
        configureRec709()
    }

    private func configureRec709() {
        colorPixelFormat = .bgra8Unorm
        // Tag the framebuffer as Rec.709. Do not leave this nil: a nil
        // CAMetalLayer.colorspace is treated as the display's native space
        // (typically Display P3), which is the "blit 709 into untagged P3" bug.
        if let rec709 = CGColorSpace(name: CGColorSpace.itur_709) {
            colorspace = rec709
            if let metalLayer = layer as? CAMetalLayer {
                metalLayer.colorspace = rec709
            }
        }
        colorspaceComment()
    }

    private func colorspaceComment() {
        // Preview pixels must already be Rec.709 encoded (OETF applied in
        // the pipeline). This view only *tags* them. It does not convert
        // 709 → P3, and it does not draw 709 code values into an untagged
        // P3 surface.
    }
}

struct Rec709MetalPreview: NSViewRepresentable {
    func makeNSView(context: Context) -> Rec709MTKView {
        let view = Rec709MTKView(frame: .zero, device: MTLCreateSystemDefaultDevice())
        view.delegate = context.coordinator
        view.enableSetNeedsDisplay = true
        view.isPaused = true
        view.clearColor = MTLClearColorMake(0.09, 0.09, 0.09, 1)
        return view
    }

    func updateNSView(_ nsView: Rec709MTKView, context: Context) {
        nsView.setNeedsDisplay(nsView.bounds)
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MTKViewDelegate {
        func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}

        func draw(in view: MTKView) {
            guard let drawable = view.currentDrawable,
                  let rpd = view.currentRenderPassDescriptor,
                  let device = view.device,
                  let queue = device.makeCommandQueue(),
                  let cmd = queue.makeCommandBuffer(),
                  let enc = cmd.makeRenderCommandEncoder(descriptor: rpd)
            else { return }
            // Placeholder clear. Real decode lands in a later slice.
            // Output of the ODT is Rec.709-encoded; the layer is tagged Rec.709.
            enc.endEncoding()
            cmd.present(drawable)
            cmd.commit()
        }
    }
}
