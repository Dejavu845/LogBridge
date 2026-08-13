import SwiftUI

/// LogBridge M1 — serial node graph: IDT → WB → Rec.709 ODT.
/// Not a general node editor. IDTs are implemented (unverified) until golden samples.
@main
struct LogBridgeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .defaultSize(width: 1440, height: 900)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
