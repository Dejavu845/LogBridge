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
                    let name = "\(state)-\(size.0)x\(size.1)-\(appearance).png"
                    if let only = onlyShotName, name != only {
                        continue
                    }
                    let app = XCUIApplication()
                    app.launchArguments = [
                        "--logbridge-ui-shot", state,
                        "--logbridge-shot-width", String(size.0),
                        "--logbridge-shot-height", String(size.1),
                        "--logbridge-shot-appearance", appearance,
                    ]
                    app.launch()
                    let window = app.windows.firstMatch
                    XCTAssertTrue(window.waitForExistence(timeout: 20), "\(state) window")
                    let caption = app.staticTexts["CI 离屏渲染·假数据·非真机"]
                    XCTAssertTrue(caption.waitForExistence(timeout: 20), "\(state) \(appearance) caption")
                    // 28066d5 keeps the button inside the content bar, and only
                    // when a clip is locked. That job writes the marker below.
                    if expectsPrimaryToolbar {
                        let primary = app.buttons["处理已锁定片段"]
                        XCTAssertTrue(primary.waitForExistence(timeout: 12), "\(state) primary button")
                        if state == "empty" || state == "dropped-awaiting" {
                            XCTAssertFalse(primary.isEnabled)
                        } else {
                            XCTAssertTrue(primary.isEnabled)
                        }
                        let identified = app.staticTexts.matching(identifier: "nextStepHint")
                        if state == "dropped-awaiting" {
                            let hints = app.staticTexts.matching(
                                NSPredicate(format: "label == %@", "先选成对 Log 与色域")
                            )
                            XCTAssertEqual(hints.count, 1, "pair hint once in \(state)")
                            XCTAssertEqual(identified.count, 1, "nextStepHint once in \(state)")
                        }
                        if state == "locked" || state == "after-write" || state == "empty" {
                            XCTAssertEqual(identified.count, 0, "nextStepHint absent in \(state)")
                        }
                        if state == "empty" {
                            XCTAssertTrue(app.staticTexts["把混源文件夹拖进来"].exists)
                            XCTAssertFalse(app.staticTexts["先选成对 Log 与色域"].exists)
                        }
                    }
                    let settled = expectation(description: "layout")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        settled.fulfill()
                    }
                    wait(for: [settled], timeout: 2)
                    let url = out.appendingPathComponent(name)
                    try window.screenshot().pngRepresentation.write(to: url)
                    app.terminate()
                }
            }
        }
    }

    /// Shell probe writes one filename here so the first launch can fail fast.
    private var onlyShotName: String? {
        let marker = "/tmp/logbridge-ui-shot-only.txt"
        guard let text = try? String(contentsOfFile: marker, encoding: .utf8) else { return nil }
        let line = text.split(whereSeparator: \.isNewline).first.map(String.init) ?? ""
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    /// HEAD requires the window-toolbar button. Baseline sets this marker to 0.
    private var expectsPrimaryToolbar: Bool {
        let marker = "/tmp/logbridge-ui-shot-require-toolbar.txt"
        if let text = try? String(contentsOfFile: marker, encoding: .utf8) {
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            return !trimmed.hasPrefix("0")
        }
        return ProcessInfo.processInfo.environment["SNAPSHOT_REQUIRE_TOOLBAR"] != "0"
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
