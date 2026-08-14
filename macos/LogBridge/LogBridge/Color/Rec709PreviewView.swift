import SwiftUI
import AppKit
import CoreGraphics
import MetalKit
import QuartzCore

// MARK: - Rec.709 ODT pane
//
// Only this pane tags CGColorSpace.itur_709. Rec.709 encoded pixels must
// NEVER be blit into an untagged layer (AppKit/Metal default to Display P3
// on modern Macs, which would silently expand 709 primaries).

/// Color-managed Rec.709 *output* preview (processed / ODT pane).
///
/// The drawable / layer color space is tagged `CGColorSpace.itur_709`.
/// Do not use this view for the source/log pane.
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
        // P3 surface. The source pane must not use this class.
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

// MARK: - Source pane (camera log / working space)
//
// NOT tagged Rec.709. Source stays camera/log or working-space / untagged
// so the split is a real comparison against the 709 ODT pane.

/// Source / camera-log preview. Color space is untagged (or working-space
/// when linear DWG is shown later). Never `CGColorSpace.itur_709`.
struct SourcePreviewView: View {
    let title: String
    let caption: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            SourceMetalPreview()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            Text(caption)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(8)
    }
}

/// MTKView for camera log / working-space pixels. Explicitly not Rec.709.
final class SourceMTKView: MTKView {
    override init(frame frameRect: CGRect, device: MTLDevice?) {
        super.init(frame: frameRect, device: device)
        configureSource()
    }

    required init(coder: NSCoder) {
        super.init(coder: coder)
        configureSource()
    }

    private func configureSource() {
        colorPixelFormat = .bgra8Unorm
        // Camera/log code values (or later: scene-linear working space).
        // Do NOT tag itur_709 — that tag is reserved for the ODT pane.
        // Untagged: we are not claiming Rec.709 primaries/transfer.
        // Do not blit Rec.709-encoded pixels into this surface.
        colorspace = nil
        if let metalLayer = layer as? CAMetalLayer {
            metalLayer.colorspace = nil
        }
    }
}

struct SourceMetalPreview: NSViewRepresentable {
    func makeNSView(context: Context) -> SourceMTKView {
        let view = SourceMTKView(frame: .zero, device: MTLCreateSystemDefaultDevice())
        view.delegate = context.coordinator
        view.enableSetNeedsDisplay = true
        view.isPaused = true
        view.clearColor = MTLClearColorMake(0.06, 0.06, 0.07, 1)
        return view
    }

    func updateNSView(_ nsView: SourceMTKView, context: Context) {
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
            // Placeholder. Source pixels are camera/log, not Rec.709 ODT.
            enc.endEncoding()
            cmd.present(drawable)
            cmd.commit()
        }
    }
}
