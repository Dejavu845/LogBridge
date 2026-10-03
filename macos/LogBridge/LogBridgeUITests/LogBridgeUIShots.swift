import XCTest

/// Launches the real app with an injected sample session and saves PNGs.
/// Used only when NSHostingView + cacheDisplay still draws a placeholder or a blank field.
final class LogBridgeUIShots: XCTestCase {
    private let states = ["empty", "dropped-awaiting", "locked", "after-write"]
    private let sizes = [(1440, 900), (1280, 800)]
    private let appearances = ["light", "dark"]

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        executionTimeAllowance = 1200
    }

    func testCaptureInjectedSampleStates() throws {
        let out = outputDirectory()
        try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        for state in states {
            for appearance in appearances {
                for size in sizes {
                    let app = XCUIApplication()
                    app.launchArguments = [
                        "--logbridge-ui-shot", state,
                        "--logbridge-shot-width", String(size.0),
                        "--logbridge-shot-height", String(size.1),
                        "--logbridge-shot-appearance", appearance,
                    ]
                    app.launch()
                    let caption = app.staticTexts["CI 离屏渲染·假数据·非真机"]
                    XCTAssertTrue(caption.waitForExistence(timeout: 20), "\(state) \(appearance) caption")
                    let settled = expectation(description: "layout")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        settled.fulfill()
                    }
                    wait(for: [settled], timeout: 2)
                    let name = "\(state)-\(size.0)x\(size.1)-\(appearance).png"
                    let url = out.appendingPathComponent(name)
                    try app.screenshot().pngRepresentation.write(to: url)
                    app.terminate()
                }
            }
        }
    }

    private func outputDirectory() -> URL {
        let env = ProcessInfo.processInfo.environment["UI_SCREENSHOT_OUT"] ?? ""
        if !env.isEmpty {
            return URL(fileURLWithPath: env, isDirectory: true)
        }
        let marker = URL(fileURLWithPath: "/tmp/logbridge-ui-screenshot-out.txt")
        if let text = try? String(contentsOf: marker, encoding: .utf8) {
            let line = text.split(whereSeparator: \.isNewline).first.map(String.init) ?? ""
            if !line.isEmpty {
                return URL(fileURLWithPath: line, isDirectory: true)
            }
        }
        return URL(fileURLWithPath: "/tmp/logbridge-ui-shots", isDirectory: true)
    }
}
