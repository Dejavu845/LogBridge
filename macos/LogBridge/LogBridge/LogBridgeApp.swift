import SwiftUI

/// LogBridge M1 — fixed Log → scene-linear → WB → Rec.709 pipeline.
/// Not a node editor. IDTs are implemented (unverified) until golden samples.
@main
struct LogBridgeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .defaultSize(width: 1280, height: 800)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
