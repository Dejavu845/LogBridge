import SwiftUI

/// LogBridge — local grade and delivery. Single window, not an editor.
/// Serial graph: IDT → exposure → WB → Off / Rec.709 preview / Rec.2100 HLG / PQ.
/// Not a general node editor. IDTs are implemented (unverified) until golden samples.

/// The window's session, published for menu commands.
/// Sidebar buttons call the same `showImporter` / `showSettings` flags.
/// A focused-scene value keeps working when that sidebar is not in the tree,
/// and still targets only the focused window.
struct SessionFocus: Hashable {
    weak var session: SessionModel?

    static func == (lhs: SessionFocus, rhs: SessionFocus) -> Bool {
        lhs.session === rhs.session
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(session.map { ObjectIdentifier($0) })
    }
}

private struct LogBridgeSessionKey: FocusedValueKey {
    typealias Value = SessionFocus
}

extension FocusedValues {
    var logBridgeSession: SessionFocus? {
        get { self[LogBridgeSessionKey.self] }
        set { self[LogBridgeSessionKey.self] = newValue }
    }
}

@main
struct LogBridgeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .defaultSize(width: 1440, height: 900)
        .commands {
            LogBridgeCommands()
        }
    }
}

/// App menu, not the sidebar. ⌘, stays on this command (no Settings scene),
/// so the existing settings sheet is the only presentation.
private struct LogBridgeCommands: Commands {
    @FocusedValue(\.logBridgeSession) private var sessionFocus

    var body: some Commands {
        CommandGroup(replacing: .newItem) {
            Button("添加…") {
                sessionFocus?.session?.showImporter = true
            }
            .keyboardShortcut("o")
        }
        CommandGroup(replacing: .appSettings) {
            Button("设置…") {
                sessionFocus?.session?.presentSettings()
            }
            .keyboardShortcut(",")
        }
        CommandGroup(after: .newItem) {
            Button("写出…") {
                guard let session = sessionFocus?.session,
                      session.showsProcessLockedButton,
                      !session.isWritingDeliverables else { return }
                session.presentDeliverSheet()
            }
            .keyboardShortcut("e")
            .disabled(sessionFocus?.session?.showsProcessLockedButton != true
                      || sessionFocus?.session?.isWritingDeliverables == true)
        }
        CommandMenu("调色") {
            Button("曝光 +0.10") {
                sessionFocus?.session?.nudgeExposureStops(0.10)
            }
            .keyboardShortcut("=", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeExposure != true)
            Button("曝光 −0.10") {
                sessionFocus?.session?.nudgeExposureStops(-0.10)
            }
            .keyboardShortcut("-", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeExposure != true)
            Button("曝光归零") {
                sessionFocus?.session?.resetExposureStops()
            }
            .keyboardShortcut("0", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeExposure != true)
            Divider()
            Button("色温 +100") {
                sessionFocus?.session?.nudgeWBCCT(100)
            }
            .keyboardShortcut("]", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWB != true)
            Button("色温 −100") {
                sessionFocus?.session?.nudgeWBCCT(-100)
            }
            .keyboardShortcut("[", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWB != true)
            Button("回到机内") {
                sessionFocus?.session?.restoreAsShotWB()
            }
            .keyboardShortcut("9", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canRestoreAsShotWB != true)
            Divider()
            Button("绿品 +1") {
                sessionFocus?.session?.nudgeWBTint(1)
            }
            .keyboardShortcut(".", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWBTint != true)
            Button("绿品 −1") {
                sessionFocus?.session?.nudgeWBTint(-1)
            }
            .keyboardShortcut(";", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWBTint != true)
            Button("绿品归零") {
                sessionFocus?.session?.resetWBTint()
            }
            .keyboardShortcut("'", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWBTint != true)
            Divider()
            Button("下一条待选") {
                sessionFocus?.session?.selectNextPendingFromMenu()
            }
            .keyboardShortcut("]", modifiers: [.command])
            .disabled(sessionFocus?.session?.canSelectNextPending != true)
            Divider()
            Button("上一帧") {
                sessionFocus?.session?.stepPreviewFrame(-1)
            }
            .disabled(sessionFocus?.session?.canStepPreviewBackward != true)
            Button("下一帧") {
                sessionFocus?.session?.stepPreviewFrame(1)
            }
            .disabled(sessionFocus?.session?.canStepPreviewForward != true)
            Button(sessionFocus?.session?.isPreviewPlaying == true ? "暂停预览" : "播放预览") {
                sessionFocus?.session?.togglePreviewPlayback()
            }
            .disabled(sessionFocus?.session?.canTogglePreviewPlayback != true)
            Divider()
            Button(sessionFocus?.session?.previewShowsGradeBefore == true ? "回到调色" : "看调色前") {
                sessionFocus?.session?.togglePreviewGradeBefore()
            }
            .keyboardShortcut("\\", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canTogglePreviewGradeBefore != true)
        }
    }
}
