import AppKit
import SwiftUI

// Screenshot baseline for the macOS CI runner.
// Renders the real ContentView with injected sample clips (no footage, no personal info).
// Capture is an NSHostingView in an NSWindow: layout, several runloop turns
// (~0.5s), then bitmapImageRepForCachingDisplay + cacheDisplay.
// If that bitmap is still the prohibited placeholder or a blank field, try
// CGWindowListCreateImage on the same window. The shell falls back to XCUITest
// when every AppKit capture is still unusable.
// One state is one child process. The shell's checker fails the job.

enum SampleState: String, CaseIterable {
    case empty
    case droppedAwaiting = "dropped-awaiting"
    case locked
    case afterWrite = "after-write"
}

enum SampleAppearance: String, CaseIterable {
    case light
    case dark

    var colorScheme: ColorScheme {
        switch self {
        case .light: return .light
        case .dark: return .dark
        }
    }

    var nsAppearance: NSAppearance.Name {
        switch self {
        case .light: return .aqua
        case .dark: return .darkAqua
        }
    }
}

struct ShotSize {
    let width: Int
    let height: Int
    var label: String { "\(width)x\(height)" }
}

let shotSizes = [
    ShotSize(width: 1440, height: 900),
    ShotSize(width: 1280, height: 800),
]

/// Corner caption baked into every PNG at render time. Not a real-device capture.
let offscreenCaption = "CI 离屏渲染·假数据·非真机"

enum SnapshotError: Error, CustomStringConvertible {
    case noBitmap(String)

    var description: String {
        switch self {
        case .noBitmap(let detail): return detail
        }
    }
}

@main
struct UISnapshotTool {
    static func main() {
        let args = Array(CommandLine.arguments.dropFirst())
        if args.contains("--child") {
            let code = MainActor.assumeIsolated {
                renderChild(args)
            }
            exit(code)
        }
        let code = renderAll(args)
        exit(code)
    }
}

private func renderAll(_ args: [String]) -> Int32 {
    guard let outDir = argument("--out", in: args) else {
        fputs("ui-screenshots: missing --out\n", stderr)
        return 0
    }
    let outURL = URL(fileURLWithPath: outDir, isDirectory: true)
    do {
        try FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)
    } catch {
        fputs("ui-screenshots: cannot create \(outDir): \(error)\n", stderr)
        return 0
    }

    var produced: [String] = []
    var failed: [String] = []
    let exe = URL(fileURLWithPath: CommandLine.arguments[0])

    for state in SampleState.allCases {
        for size in shotSizes {
            for appearance in SampleAppearance.allCases {
                let name = "\(state.rawValue)-\(size.label)-\(appearance.rawValue).png"
                let dest = outURL.appendingPathComponent(name)
                let ok = runChild(
                    exe: exe,
                    state: state,
                    size: size,
                    appearance: appearance,
                    dest: dest
                )
                if ok {
                    produced.append(name)
                } else {
                    failed.append(name)
                    try? FileManager.default.removeItem(at: dest)
                }
            }
        }
    }

    writeManifest(outURL: outURL, produced: produced, failed: failed)
    print("ui-screenshots produced (\(produced.count)):")
    if produced.isEmpty {
        print("  (none)")
    } else {
        for name in produced {
            print("  \(name)")
        }
    }
    print("ui-screenshots failed (\(failed.count)):")
    if failed.isEmpty {
        print("  (none)")
    } else {
        for name in failed {
            print("  \(name)")
        }
    }
    if !failed.isEmpty {
        return 1
    }
    return 0
}

private func runChild(
    exe: URL,
    state: SampleState,
    size: ShotSize,
    appearance: SampleAppearance,
    dest: URL
) -> Bool {
    let process = Process()
    process.executableURL = exe
    process.arguments = [
        "--child",
        "--state", state.rawValue,
        "--width", String(size.width),
        "--height", String(size.height),
        "--appearance", appearance.rawValue,
        "--out", dest.path,
    ]
    let sem = DispatchSemaphore(value: 0)
    process.terminationHandler = { _ in sem.signal() }
    do {
        try process.run()
    } catch {
        fputs("ui-screenshots: failed to start \(dest.lastPathComponent): \(error)\n", stderr)
        return false
    }
    let wait = sem.wait(timeout: .now() + 45)
    if wait == .timedOut {
        process.terminate()
        _ = sem.wait(timeout: .now() + 5)
        fputs("ui-screenshots: timed out \(dest.lastPathComponent)\n", stderr)
        return false
    }
    guard process.terminationStatus == 0 else {
        fputs(
            "ui-screenshots: \(dest.lastPathComponent) exit \(process.terminationStatus)\n",
            stderr
        )
        return false
    }
    guard FileManager.default.fileExists(atPath: dest.path) else {
        fputs("ui-screenshots: missing file \(dest.lastPathComponent)\n", stderr)
        return false
    }
    let byteCount = fileByteCount(dest.path)
    if byteCount <= 500 {
        fputs("ui-screenshots: \(dest.lastPathComponent) too small (\(byteCount) bytes)\n", stderr)
        return false
    }
    return true
}

@MainActor
private func renderChild(_ args: [String]) -> Int32 {
    guard
        let stateRaw = argument("--state", in: args),
        let state = SampleState(rawValue: stateRaw),
        let widthRaw = argument("--width", in: args),
        let heightRaw = argument("--height", in: args),
        let width = Int(widthRaw), width > 0,
        let height = Int(heightRaw), height > 0,
        let appearanceRaw = argument("--appearance", in: args),
        let appearance = SampleAppearance(rawValue: appearanceRaw),
        let outPath = argument("--out", in: args)
    else {
        fputs("ui-screenshots: bad child arguments\n", stderr)
        return 2
    }
    do {
        let image = try renderImage(state: state, width: width, height: height, appearance: appearance)
        try writePNG(image, to: URL(fileURLWithPath: outPath))
        return 0
    } catch {
        fputs("ui-screenshots: \(state.rawValue) \(width)x\(height) \(appearance.rawValue) failed: \(error)\n", stderr)
        return 2
    }
}

@MainActor
private func renderImage(
    state: SampleState,
    width: Int,
    height: Int,
    appearance: SampleAppearance
) throws -> NSImage {
    resetSampleDefaults()
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    NSApp.appearance = NSAppearance(named: appearance.nsAppearance)

    let session = makeSampleSession(state)
    let view = snapshotRoot(session: session, width: width, height: height, appearance: appearance)
    return try renderWithHostingView(
        view,
        width: width,
        height: height,
        appearance: appearance
    )
}

@MainActor
private func snapshotRoot(session: SessionModel, width: Int, height: Int, appearance: SampleAppearance) -> some View {
    ContentView(session: session)
        .frame(width: CGFloat(width), height: CGFloat(height))
        .background(Color(nsColor: .windowBackgroundColor))
        .preferredColorScheme(appearance.colorScheme)
        .environment(\.colorScheme, appearance.colorScheme)
        .overlay(alignment: .bottomTrailing) {
            Text(offscreenCaption)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(Color.white)
                .padding(.horizontal, 7)
                .padding(.vertical, 4)
                .background(Color.black.opacity(0.82), in: RoundedRectangle(cornerRadius: 4))
                .padding(8)
                .allowsHitTesting(false)
        }
}

@MainActor
private func renderWithHostingView<V: View>(
    _ view: V,
    width: Int,
    height: Int,
    appearance: SampleAppearance
) throws -> NSImage {
    let host = NSHostingView(rootView: view)
    let size = NSSize(width: width, height: height)
    host.frame = NSRect(origin: .zero, size: size)
    host.appearance = NSAppearance(named: appearance.nsAppearance)
    let window = NSWindow(
        contentRect: NSRect(origin: .zero, size: size),
        styleMask: [.borderless],
        backing: .buffered,
        defer: false
    )
    window.isReleasedWhenClosed = false
    window.isOpaque = true
    window.backgroundColor = .windowBackgroundColor
    window.appearance = host.appearance
    window.contentView = host
    host.autoresizingMask = [.width, .height]
    // Off the visible desktop first. List/Table still need a real window
    // and several runloop turns before cacheDisplay has their cells.
    window.setFrame(NSRect(x: -20000, y: -20000, width: width, height: height), display: true)
    window.orderFrontRegardless()

    spinRunLoop(host: host)
    var best = cacheDisplayRep(host: host)
    if best == nil || bitmapIsUnusable(best!) {
        window.setFrameOrigin(NSPoint(x: 40, y: 40))
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        spinRunLoop(host: host)
        if let again = cacheDisplayRep(host: host), betterCapture(again, than: best) {
            best = again
        }
    }
    if best == nil || bitmapIsUnusable(best!) {
        if let windowRep = windowImageRep(window: window), betterCapture(windowRep, than: best) {
            best = windowRep
        }
    }
    window.orderOut(nil)
    window.close()
    guard let rep = best else {
        throw SnapshotError.noBitmap("NSHostingView cacheDisplay and CGWindowListCreateImage produced no bitmap")
    }
    let image = NSImage(size: NSSize(width: rep.pixelsWide, height: rep.pixelsHigh))
    image.addRepresentation(rep)
    return image
}

/// Ten turns, 0.05s each: about 0.5s total, so lazy Table/List can fill in.
@MainActor
private func spinRunLoop(host: NSView) {
    for _ in 0..<10 {
        host.needsLayout = true
        host.needsDisplay = true
        host.layoutSubtreeIfNeeded()
        host.displayIfNeeded()
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.025))
        RunLoop.current.run(mode: .common, before: Date().addingTimeInterval(0.025))
    }
}

@MainActor
private func cacheDisplayRep(host: NSView) -> NSBitmapImageRep? {
    guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { return nil }
    host.cacheDisplay(in: host.bounds, to: rep)
    return rep
}

@MainActor
private func windowImageRep(window: NSWindow) -> NSBitmapImageRep? {
    let windowID = CGWindowID(window.windowNumber)
    guard windowID != 0 else { return nil }
    guard let image = CGWindowListCreateImage(
        CGRect.null,
        .optionIncludingWindow,
        windowID,
        [.boundsIgnoreFraming, .nominalResolution]
    ) else { return nil }
    return NSBitmapImageRep(cgImage: image)
}

/// Matches scripts/check_ui_screenshots.py: yellow #FFCC00 and red #FF3B30
/// together above 2%, or a flat field. Stride keeps the child inside its timeout.
private func bitmapIsUnusable(_ rep: NSBitmapImageRep) -> Bool {
    let stats = bitmapStats(rep)
    guard stats.total > 0 else { return true }
    let yellowFrac = Double(stats.yellow) / Double(stats.total)
    let redFrac = Double(stats.red) / Double(stats.total)
    if yellowFrac > 0, redFrac > 0, yellowFrac + redFrac > 0.02 {
        return true
    }
    let mean = stats.sum / Double(stats.total)
    let variance = max(0, stats.sumSq / Double(stats.total) - mean * mean)
    return variance.squareRoot() < 1
}

private func betterCapture(_ candidate: NSBitmapImageRep, than current: NSBitmapImageRep?) -> Bool {
    guard let current else { return true }
    if bitmapIsUnusable(current), !bitmapIsUnusable(candidate) { return true }
    if !bitmapIsUnusable(current), bitmapIsUnusable(candidate) { return false }
    return bitmapStats(candidate).yellow + bitmapStats(candidate).red
        < bitmapStats(current).yellow + bitmapStats(current).red
}

private struct BitmapStats {
    var yellow: Int
    var red: Int
    var total: Int
    var sum: Double
    var sumSq: Double
}

private func bitmapStats(_ rep: NSBitmapImageRep) -> BitmapStats {
    var stats = BitmapStats(yellow: 0, red: 0, total: 0, sum: 0, sumSq: 0)
    let width = rep.pixelsWide
    let height = rep.pixelsHigh
    guard
        width > 0,
        height > 0,
        rep.bitsPerSample == 8,
        rep.samplesPerPixel >= 3,
        let raw = rep.bitmapData
    else { return stats }
    let spp = rep.samplesPerPixel
    let bpr = rep.bytesPerRow
    guard bpr >= width * spp else { return stats }
    let channel = rep.bitmapFormat.contains(.alphaFirst) ? 1 : 0
    let stride = 4
    var y = 0
    while y < height {
        let row = raw.advanced(by: y * bpr)
        var x = 0
        while x < width {
            let px = row.advanced(by: x * spp)
            let ri = Int(px[channel])
            let gi = Int(px[channel + 1])
            let bi = Int(px[channel + 2])
            if abs(ri - 255) <= 8, abs(gi - 204) <= 8, abs(bi - 0) <= 8 {
                stats.yellow += 1
            }
            if abs(ri - 255) <= 8, abs(gi - 59) <= 8, abs(bi - 48) <= 8 {
                stats.red += 1
            }
            let lum = Double(ri + gi + bi) / 3
            stats.sum += lum
            stats.sumSq += lum * lum
            stats.total += 1
            x += stride
        }
        y += stride
    }
    return stats
}

private func writePNG(_ image: NSImage, to url: URL) throws {
    guard
        let tiff = image.tiffRepresentation,
        let rep = NSBitmapImageRep(data: tiff),
        let data = rep.representation(using: .png, properties: [:])
    else {
        throw SnapshotError.noBitmap("PNG encode failed")
    }
    try data.write(to: url)
}

private func writeManifest(outURL: URL, produced: [String], failed: [String]) {
    var lines = ["produced (\(produced.count)):"]
    lines.append(contentsOf: produced.isEmpty ? ["(none)"] : produced)
    lines.append("failed (\(failed.count)):")
    lines.append(contentsOf: failed.isEmpty ? ["(none)"] : failed)
    let text = lines.joined(separator: "\n") + "\n"
    let url = outURL.appendingPathComponent("manifest.txt")
    try? text.write(to: url, atomically: true, encoding: .utf8)
}

private func fileByteCount(_ path: String) -> Int {
    guard
        let attrs = try? FileManager.default.attributesOfItem(atPath: path),
        let number = attrs[.size] as? NSNumber
    else { return 0 }
    return number.intValue
}

private func argument(_ name: String, in args: [String]) -> String? {
    guard let index = args.firstIndex(of: name), index + 1 < args.count else { return nil }
    return args[index + 1]
}

private func resetSampleDefaults() {
    let keys = [
        "logbridge.defaultPreviewODT",
        "logbridge.promptEstimateWBOnImport",
        "logbridge.lastExportDirectory",
        "logbridge.advancedPanelExpanded",
    ]
    for key in keys {
        UserDefaults.standard.removeObject(forKey: key)
    }
}

private func makeSampleSession(_ state: SampleState) -> SessionModel {
    let session = SessionModel()
    switch state {
    case .empty:
        break
    case .droppedAwaiting:
        // Not locked. Neither sample has a paired IDT, so the window
        // keeps the visible line 先选成对 Log 与色域.
        let unresolved = sampleClip(
            id: UUID(uuidString: "00000000-0000-4000-8000-000000000001")!,
            name: "sample-a.mov",
            idt: nil,
            curve: nil,
            gamut: nil,
            source: .unresolved,
            note: "读不到",
            needsPicker: false,
            chip: nil
        )
        let hinted = sampleClip(
            id: UUID(uuidString: "00000000-0000-4000-8000-000000000002")!,
            name: "sample-b.mov",
            idt: nil,
            curve: "S-Log3",
            gamut: nil,
            source: .filename,
            note: "读不到",
            needsPicker: true,
            chip: nil
        )
        session.clips = [unresolved, hinted]
        session.selectedID = unresolved.id
    case .locked:
        let clip = lockedSample(chip: nil)
        session.clips = [clip]
        session.selectedID = clip.id
    case .afterWrite:
        let clip = lockedSample(chip: SessionModel.wroteProxyChip)
        session.clips = [clip]
        session.selectedID = clip.id
        session.isWritingDeliverables = false
        session.lastExportNote = SessionModel.batchSummaryText(
            wrote: 1,
            skipped: 0,
            failed: 0,
            reasons: [],
            dest: nil
        )
    }
    return session
}

private func lockedSample(chip: String?) -> Clip {
    let idt = IDT.sonySLog3SGamut3
    return sampleClip(
        id: UUID(uuidString: "00000000-0000-4000-8000-000000000003")!,
        name: "sample-locked.mov",
        idt: idt,
        curve: idt.curve,
        gamut: idt.gamut,
        source: .user,
        note: "用户选择成对 IDT",
        needsPicker: false,
        chip: chip
    )
}

private func sampleClip(
    id: UUID,
    name: String,
    idt: IDT?,
    curve: String?,
    gamut: String?,
    source: DetectionSource,
    note: String,
    needsPicker: Bool,
    chip: String?
) -> Clip {
    Clip(
        id: id,
        url: URL(fileURLWithPath: "/tmp/logbridge-ui-sample/\(name)", isDirectory: false),
        idt: idt,
        detectedCurve: curve,
        detectedGamut: gamut,
        detectionSource: source,
        needsUserPicker: needsPicker,
        detectionNote: note,
        veniceDetected: false,
        asShotCCT: nil,
        asShotTint: 0,
        wbSource: .unknown,
        wbCCT: nil,
        wbTint: 0,
        formatNote: "",
        exportChip: chip
    )
}
