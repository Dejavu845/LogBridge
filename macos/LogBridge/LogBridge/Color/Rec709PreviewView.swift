import SwiftUI
import AppKit
import CoreGraphics
import MetalKit
import QuartzCore

/// Runner Swift overlay: CALayer has no `colorspace` (CAMetalLayer does).
/// KVC writes the same CALayer key. 709 tag / untagged source unchanged.
private func setAppKitLayerColorSpace(_ layer: CALayer?, _ space: CGColorSpace?) {
    layer?.setValue(space, forKey: "colorspace")
}

/// Monitor magnification. Fit is the existing whole-frame aspect fit.
/// 100% is one image pixel per screen pixel. 200% is twice that.
/// Drag pans inside the pane. Display only: grade numbers and the write stay put.
enum MonitorZoom: String, CaseIterable, Identifiable {
    case fit
    case actual
    case doubled

    var id: String { rawValue }

    var label: String {
        switch self {
        case .fit: return "适应"
        case .actual: return "100%"
        case .doubled: return "200%"
        }
    }
}

func previewScreenScale(of view: NSView) -> CGFloat {
    if let window = view.window, window.backingScaleFactor > 0 {
        return window.backingScaleFactor
    }
    if let scale = NSScreen.main?.backingScaleFactor, scale > 0 {
        return scale
    }
    return 2
}

/// Shared drag offset so the source pane and the grade pane move together.
/// Display only. Not the grade, and not the write.
final class MonitorPanBus {
    private(set) var pan = CGPoint.zero
    private var listeners: [ObjectIdentifier: () -> Void] = [:]

    func observe(_ owner: AnyObject, _ body: @escaping () -> Void) {
        listeners[ObjectIdentifier(owner)] = body
    }

    func unobserve(_ owner: AnyObject) {
        listeners.removeValue(forKey: ObjectIdentifier(owner))
    }

    func setPan(_ pan: CGPoint) {
        self.pan = pan
        for body in Array(listeners.values) {
            body()
        }
    }

    func reset() {
        guard pan != .zero else { return }
        setPan(.zero)
    }
}

/// Places one preview layer. Fit fills the pane. 100% / 200% stay centered
/// until a drag, then clamp so the frame does not slide into empty black
/// when the picture is already larger than the pane.
struct PreviewMagnifier {
    private(set) var zoom: MonitorZoom = .fit
    var bus: MonitorPanBus?
    private var dragOrigin: CGPoint?
    private var panAtDrag = CGPoint.zero
    private var pixelSize = CGSize.zero

    var showsHand: Bool { zoom != .fit }

    mutating func setZoom(_ next: MonitorZoom) {
        zoom = next
    }

    /// A missing frame does not clear the drag. A new width or height recenters.
    mutating func noteImage(_ image: CGImage?) {
        guard let image else { return }
        let next = CGSize(width: image.width, height: image.height)
        if pixelSize != .zero, next != pixelSize {
            bus?.reset()
            dragOrigin = nil
        }
        pixelSize = next
    }

    mutating func mouseDown(_ event: NSEvent) {
        guard showsHand else { return }
        dragOrigin = event.locationInWindow
        panAtDrag = bus?.pan ?? .zero
    }

    mutating func mouseDragged(
        _ event: NSEvent,
        image: CGImage?,
        bounds: CGRect,
        screenScale: CGFloat
    ) {
        guard showsHand, let dragOrigin else { return }
        let point = event.locationInWindow
        var next = CGPoint(
            x: panAtDrag.x + (point.x - dragOrigin.x),
            y: panAtDrag.y + (point.y - dragOrigin.y)
        )
        if let image {
            let limit = panLimit(image: image, bounds: bounds, screenScale: screenScale)
            next.x = min(max(next.x, -limit.x), limit.x)
            next.y = min(max(next.y, -limit.y), limit.y)
        }
        bus?.setPan(next)
    }

    func place(
        imageLayer: CALayer,
        image: CGImage?,
        bounds: CGRect,
        screenScale: CGFloat
    ) {
        guard zoom != .fit, let image, bounds.width > 1, bounds.height > 1 else {
            imageLayer.contentsGravity = .resizeAspect
            imageLayer.frame = bounds
            return
        }
        let fitted = fittedSize(image: image, screenScale: screenScale)
        let limit = panLimit(image: image, bounds: bounds, screenScale: screenScale)
        let stored = bus?.pan ?? .zero
        let pan = CGPoint(
            x: min(max(stored.x, -limit.x), limit.x),
            y: min(max(stored.y, -limit.y), limit.y)
        )
        imageLayer.contentsGravity = .resize
        imageLayer.frame = CGRect(
            x: (bounds.width - fitted.width) / 2 + pan.x,
            y: (bounds.height - fitted.height) / 2 + pan.y,
            width: fitted.width,
            height: fitted.height
        )
    }

    private func fittedSize(image: CGImage, screenScale: CGFloat) -> CGSize {
        let factor: CGFloat = zoom == .doubled ? 2 : 1
        let scale = max(screenScale, 1)
        return CGSize(
            width: CGFloat(image.width) / scale * factor,
            height: CGFloat(image.height) / scale * factor
        )
    }

    private func panLimit(image: CGImage, bounds: CGRect, screenScale: CGFloat) -> CGPoint {
        let fitted = fittedSize(image: image, screenScale: screenScale)
        return CGPoint(
            x: max(0, (fitted.width - bounds.width) / 2),
            y: max(0, (fitted.height - bounds.height) / 2)
        )
    }
}

func bindMonitorPan(
    _ bus: MonitorPanBus?,
    to view: NSView,
    previous: inout MonitorPanBus?,
    onChange: @escaping () -> Void
) {
    guard previous !== bus else { return }
    previous?.unobserve(view)
    previous = bus
    bus?.observe(view, onChange)
}

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
    var image: CGImage? = nil
    var zoom: MonitorZoom = .fit
    var panBus: MonitorPanBus? = nil
    var pickingNeutral: Bool = false
    var onPick: ((Double, Double) -> Void)? = nil

    var body: some View {
        ZStack(alignment: .topLeading) {
            Rec709TaggedHost(image: image, zoom: zoom, panBus: panBus)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            PreviewNotDeliverableBadge()
            PreviewPaneTitle(title: title)
        }
        .help(caption)
        .overlay {
            GeometryReader { geo in
                Color.clear
                    .contentShape(Rectangle())
                    .allowsHitTesting(pickingNeutral)
                    .gesture(
                        DragGesture(minimumDistance: 0).onEnded { value in
                            guard pickingNeutral, let onPick else { return }
                            let w = max(geo.size.width, 1)
                            let h = max(geo.size.height, 1)
                            let nx = min(max(value.location.x / w, 0), 1)
                            let ny = min(max(value.location.y / h, 0), 1)
                            onPick(nx, ny)
                        }
                    )
            }
        }
    }
}

/// Overlay on every preview pane. 仅预览.
struct PreviewNotDeliverableBadge: View {
    var body: some View {
        Text("仅预览")
            .font(.caption2.weight(.bold))
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(.black.opacity(0.72))
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 5))
            .padding(6)
            .accessibilityLabel("仅预览")
            .help("仅预览")
    }
}

/// AppKit host: layer.colorspace is itur_709. Never used for the source pane.
struct Rec709TaggedHost: NSViewRepresentable {
    var image: CGImage?
    var zoom: MonitorZoom = .fit
    var panBus: MonitorPanBus? = nil

    func makeNSView(context: Context) -> Rec709ImageHost {
        Rec709ImageHost()
    }

    func updateNSView(_ nsView: Rec709ImageHost, context: Context) {
        nsView.setPanBus(panBus)
        nsView.setImage(image)
        nsView.setZoom(zoom)
    }
}

final class Rec709ImageHost: NSView {
    private let imageLayer = CALayer()
    private var magnifier = PreviewMagnifier()
    private var panBus: MonitorPanBus?
    private var image: CGImage?

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        let rec709 = CGColorSpace(name: CGColorSpace.itur_709)
        layer = CALayer()
        layer?.masksToBounds = true
        setAppKitLayerColorSpace(layer, rec709)
        layer?.backgroundColor = CGColor(gray: 0.09, alpha: 1)
        imageLayer.contentsGravity = .resizeAspect
        setAppKitLayerColorSpace(imageLayer, rec709)
        layer?.addSublayer(imageLayer)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var acceptsFirstResponder: Bool { true }

    func setPanBus(_ bus: MonitorPanBus?) {
        magnifier.bus = bus
        bindMonitorPan(bus, to: self, previous: &panBus) { [weak self] in
            self?.needsLayout = true
        }
    }

    func setImage(_ img: CGImage?) {
        image = img
        imageLayer.contents = img
        magnifier.noteImage(img)
        needsLayout = true
    }

    func setZoom(_ zoom: MonitorZoom) {
        magnifier.setZoom(zoom)
        needsLayout = true
        window?.invalidateCursorRects(for: self)
    }

    deinit {
        panBus?.unobserve(self)
    }

    override func layout() {
        super.layout()
        magnifier.place(
            imageLayer: imageLayer,
            image: image,
            bounds: bounds,
            screenScale: previewScreenScale(of: self)
        )
    }

    override func mouseDown(with event: NSEvent) {
        if magnifier.showsHand {
            magnifier.mouseDown(event)
        } else {
            super.mouseDown(with: event)
        }
    }

    override func mouseDragged(with event: NSEvent) {
        guard magnifier.showsHand else {
            super.mouseDragged(with: event)
            return
        }
        magnifier.mouseDragged(
            event,
            image: image,
            bounds: bounds,
            screenScale: previewScreenScale(of: self)
        )
    }

    override func resetCursorRects() {
        addCursorRect(bounds, cursor: magnifier.showsHand ? .openHand : .arrow)
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
/// when ACEScct / ACES2065-1 is shown later). Never `CGColorSpace.itur_709`.
struct SourcePreviewView: View {
    let title: String
    let caption: String
    var image: CGImage? = nil
    var zoom: MonitorZoom = .fit
    var panBus: MonitorPanBus? = nil

    var body: some View {
        ZStack(alignment: .topLeading) {
            SourceUntaggedHost(image: image, zoom: zoom, panBus: panBus)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            PreviewNotDeliverableBadge()
            PreviewPaneTitle(title: title)
        }
        .help(caption)
    }
}

/// Thin title over the image so the pane itself stays the preview.
private struct PreviewPaneTitle: View {
    let title: String

    var body: some View {
        Text(title)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(.black.opacity(0.55))
            .clipShape(RoundedRectangle(cornerRadius: 5))
            .padding(6)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
    }
}

/// Untagged source host. Never CGColorSpace.itur_709.
struct SourceUntaggedHost: NSViewRepresentable {
    var image: CGImage?
    var zoom: MonitorZoom = .fit
    var panBus: MonitorPanBus? = nil

    func makeNSView(context: Context) -> SourceImageHost {
        SourceImageHost()
    }

    func updateNSView(_ nsView: SourceImageHost, context: Context) {
        nsView.setPanBus(panBus)
        nsView.setImage(image)
        nsView.setZoom(zoom)
    }
}

final class SourceImageHost: NSView {
    private let imageLayer = CALayer()
    private var magnifier = PreviewMagnifier()
    private var panBus: MonitorPanBus?
    private var image: CGImage?

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer = CALayer()
        layer?.masksToBounds = true
        setAppKitLayerColorSpace(layer, nil)
        layer?.backgroundColor = CGColor(gray: 0.06, alpha: 1)
        imageLayer.contentsGravity = .resizeAspect
        setAppKitLayerColorSpace(imageLayer, nil)
        layer?.addSublayer(imageLayer)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var acceptsFirstResponder: Bool { true }

    func setPanBus(_ bus: MonitorPanBus?) {
        magnifier.bus = bus
        bindMonitorPan(bus, to: self, previous: &panBus) { [weak self] in
            self?.needsLayout = true
        }
    }

    func setImage(_ img: CGImage?) {
        image = img
        imageLayer.contents = img
        magnifier.noteImage(img)
        needsLayout = true
    }

    func setZoom(_ zoom: MonitorZoom) {
        magnifier.setZoom(zoom)
        needsLayout = true
        window?.invalidateCursorRects(for: self)
    }

    deinit {
        panBus?.unobserve(self)
    }

    override func layout() {
        super.layout()
        magnifier.place(
            imageLayer: imageLayer,
            image: image,
            bounds: bounds,
            screenScale: previewScreenScale(of: self)
        )
    }

    override func mouseDown(with event: NSEvent) {
        if magnifier.showsHand {
            magnifier.mouseDown(event)
        } else {
            super.mouseDown(with: event)
        }
    }

    override func mouseDragged(with event: NSEvent) {
        guard magnifier.showsHand else {
            super.mouseDragged(with: event)
            return
        }
        magnifier.mouseDragged(
            event,
            image: image,
            bounds: bounds,
            screenScale: previewScreenScale(of: self)
        )
    }

    override func resetCursorRects() {
        addCursorRect(bounds, cursor: magnifier.showsHand ? .openHand : .arrow)
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
        // Camera/log code values (or later: ACEScct / ACES2065-1 working space).
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
