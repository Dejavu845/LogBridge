import SwiftUI

/// LogBridge — serial node graph: IDT → WB → Off / Rec.709 preview / Rec.2100 HLG / PQ.
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
                sessionFocus?.session.showImporter = true
            }
            .keyboardShortcut("o")
        }
        CommandGroup(replacing: .appSettings) {
            Button("设置…") {
                sessionFocus?.session.showSettings = true
            }
            .keyboardShortcut(",")
        }
    }
}
