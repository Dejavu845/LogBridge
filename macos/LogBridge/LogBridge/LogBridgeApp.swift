import SwiftUI

/// LogBridge — serial node graph: IDT → WB → Off / Rec.709 preview / Rec.2100 HLG / PQ.
/// Not a general node editor. IDTs are implemented (unverified) until golden samples.
/// SessionFocus lives in ContentView so the screenshot tool can compile without this @main file.

@main
struct LogBridgeApp: App {
    init() {
        UIShotLaunch.prepareProcessIfNeeded()
    }

    var body: some Scene {
        WindowGroup {
            if UIShotLaunch.isActive {
                ContentView(session: UIShotLaunch.sessionIfRequested())
                    .modifier(UIShotChrome())
            } else {
                ContentView()
            }
        }
        .defaultSize(width: 1520, height: 940)
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
                sessionFocus?.session?.showSettings = true
            }
            .keyboardShortcut(",")
        }
    }
}
