import AppKit
import SwiftUI

/// CI-only sample session. A normal launch never reads these arguments.
/// The screenshot tool keeps its own copy of the same four states so it can
/// compile against an older tree that does not contain this file.
enum UIShotLaunch {
    static let shotArg = "--logbridge-ui-shot"
    static let widthArg = "--logbridge-shot-width"
    static let heightArg = "--logbridge-shot-height"
    static let appearanceArg = "--logbridge-shot-appearance"
    static let caption = "CI 离屏渲染·假数据·非真机"

    static var stateName: String? { value(after: shotArg) }

    static var isActive: Bool { stateName != nil }

    static var shotWidth: Int { intValue(after: widthArg) ?? 1440 }

    static var shotHeight: Int { intValue(after: heightArg) ?? 900 }

    static var wantsDark: Bool { value(after: appearanceArg) == "dark" }

    static func prepareProcessIfNeeded() {
        guard isActive else { return }
        let name: NSAppearance.Name = wantsDark ? .darkAqua : .aqua
        NSApp.appearance = NSAppearance(named: name)
        UserDefaults.standard.removeObject(forKey: "logbridge.advancedPanelExpanded")
    }

    /// Nil on a normal launch, so ContentView keeps its default session.
    static func sessionIfRequested() -> SessionModel? {
        guard let name = stateName else { return nil }
        return makeSession(named: name)
    }

    static func makeSession(named name: String) -> SessionModel? {
        let session = SessionModel()
        switch name {
        case "empty":
            return session
        case "dropped-awaiting":
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
            return session
        case "locked":
            let clip = lockedSample(chip: nil)
            session.clips = [clip]
            session.selectedID = clip.id
            return session
        case "after-write":
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
            return session
        default:
            return nil
        }
    }

    static func applyWindow() {
        guard isActive else { return }
        let appearance = NSAppearance(named: wantsDark ? .darkAqua : .aqua)
        NSApp.appearance = appearance
        guard let window = NSApp.windows.first(where: { $0.contentView != nil }) else { return }
        window.appearance = appearance
        window.styleMask.formUnion([.titled, .closable, .miniaturizable, .resizable])
        window.toolbarStyle = .unified
        window.setContentSize(NSSize(width: shotWidth, height: shotHeight))
        window.setFrameOrigin(NSPoint(x: 40, y: 40))
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        window.makeMain()
    }

    private static func value(after flag: String) -> String? {
        let args = ProcessInfo.processInfo.arguments
        guard let index = args.firstIndex(of: flag), index + 1 < args.count else { return nil }
        let value = args[index + 1]
        if value.hasPrefix("-") { return nil }
        return value
    }

    private static func intValue(after flag: String) -> Int? {
        guard let raw = value(after: flag), let number = Int(raw), number > 0 else { return nil }
        return number
    }

    private static func lockedSample(chip: String?) -> Clip {
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

    private static func sampleClip(
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
}

/// Caption and window size for a shot launch. A normal launch leaves the view untouched.
struct UIShotChrome: ViewModifier {
    func body(content: Content) -> some View {
        content
            .overlay(alignment: .bottomTrailing) {
                Text(UIShotLaunch.caption)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Color.white)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 4)
                    .background(Color.black.opacity(0.82), in: RoundedRectangle(cornerRadius: 4))
                    .padding(8)
                    .allowsHitTesting(false)
            }
            .onAppear {
                DispatchQueue.main.async {
                    UIShotLaunch.applyWindow()
                }
            }
    }
}
