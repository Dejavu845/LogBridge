"""macOS CI screenshot baseline. Fake sample state only. No footage."""

import subprocess
from pathlib import Path

from PIL import Image

from scripts.check_ui_screenshots import (
    analyze_image,
    check_directory,
    is_blank_capture,
    is_prohibited_placeholder,
    toolbar_region_present,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/test.yml"
TOOL = ROOT / "scripts/ui_snapshot.swift"
SCRIPT = ROOT / "scripts/ui_snapshot.sh"
BASELINE = ROOT / "scripts/ui_snapshot_baseline.sh"
CHECK = ROOT / "scripts/check_ui_screenshots.py"
CONTENT = ROOT / "macos/LogBridge/LogBridge/ContentView.swift"
APP = ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift"
SHOT = ROOT / "macos/LogBridge/LogBridge/UIShotLaunch.swift"
XCTEST = ROOT / "macos/LogBridge/LogBridgeUITests/LogBridgeUIShots.swift"


def test_macos_workflow_uploads_ui_screenshots_artifact():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    macos = workflow.split("macos:", 1)[1]
    assert "bash scripts/ui_snapshot.sh" in macos
    assert "uses: actions/upload-artifact@v4" in macos
    assert "name: ui-screenshots" in macos
    assert "ui-screenshots/*.png" in macos
    assert "ui-screenshots/README.txt" in macos
    assert "if-no-files-found: warn" in macos
    assert "if: always()" in macos
    assert "name: ui-screenshots-baseline" in workflow
    assert "bash scripts/ui_snapshot_baseline.sh" in workflow
    assert "28066d5" in workflow
    assert "fetch-depth: 0" in workflow


def test_snapshot_tool_covers_sizes_appearances_and_states():
    tool = TOOL.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "empty",
        "dropped-awaiting",
        "locked",
        "after-write",
        "1440",
        "900",
        "1280",
        "800",
        "light",
        "dark",
        "NSWindow",
        "NSHostingController",
        "NSHostingView",
        "superview",
        "bitmapImageRepForCachingDisplay",
        "cacheDisplay",
        "spinRunLoop",
        "CGWindowListCreateImage",
        "ContentView(session:",
        "sample-a.mov",
        "sample-locked.mov",
        "CI 离屏渲染·假数据·非真机",
        ".overlay(alignment: .bottomTrailing)",
        "0.5",
    ):
        assert token in tool, token
    assert "ImageRenderer" not in tool
    assert "for _ in 0..<10" in tool
    assert "CI 离屏渲染·假数据·非真机" in script
    assert "README.txt" in script
    assert "commit:" in script
    assert "return 0" in tool
    assert "return 1" in tool
    assert "LogBridgeApp.swift" in script
    assert "check_ui_screenshots.py" in script
    assert "exit 1" in script
    assert "-only-testing:LogBridgeUITests" in script
    assert "XCUITest fallback" in script
    assert "SNAPSHOT_REQUIRE_TOOLBAR" in script
    assert "logbridge-ui-shot-require-toolbar.txt" in script
    assert TOOL.relative_to(ROOT).parts[0] == "scripts"
    xctest = XCTEST.read_text(encoding="utf-8")
    assert "windows.firstMatch" in xctest
    assert "XCUIApplication()" in xctest
    assert "screenshot()" in xctest
    assert "--logbridge-ui-shot" in xctest
    assert "expectsPrimaryToolbar" in xctest
    assert 'app.buttons["处理已锁定片段"]' in xctest
    baseline = BASELINE.read_text(encoding="utf-8")
    assert "28066d5" in baseline
    assert "ui-screenshots-baseline" in baseline
    assert "worktree" in baseline
    assert "wire_baseline_shot_launch.py" in baseline
    assert "SNAPSHOT_REQUIRE_TOOLBAR=0" in baseline


def test_dropped_awaiting_is_the_not_locked_screenshot_state():
    """Clips imported, none locked: the visible hint is in that render."""
    tool = TOOL.read_text(encoding="utf-8")
    content = CONTENT.read_text(encoding="utf-8")
    awaiting = tool.split("case .droppedAwaiting:")[1].split("case .locked:")[0]
    locked = tool.split("case .locked:")[1].split("case .afterWrite:")[0]
    assert "idt: nil" in awaiting
    assert "先选成对 Log 与色域" in awaiting
    assert "lockedSample" in locked
    assert "sonySLog3SGamut3" in tool.split("private func lockedSample")[1]
    button = content.split("struct ProcessLockedToolbarButton")[1].split("struct ProcessLockedButtonHelp")[0]
    assert "if session.clips.isEmpty" in button
    assert 'Text("把混源文件夹拖进来")' in button
    pair = button.split("else if session.lockedClipCount == 0")[1]
    assert 'Text("先选成对 Log 与色域")' in pair
    window = content.split("struct ContentView")[1].split("struct ClipListArrowMonitor")[0]
    assert "UnlockedPairHint()" not in window


def test_snapshot_compile_can_see_session_focus():
    """LogBridgeApp.swift is excluded (@main). SessionFocus must live in ContentView."""
    script = SCRIPT.read_text(encoding="utf-8")
    content = CONTENT.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "! -name 'LogBridgeApp.swift'" in script
    assert "struct SessionFocus" in content
    assert "var logBridgeSession" in content
    assert "struct SessionFocus" not in app
    assert "@main" in app


def test_content_view_accepts_injected_session_and_app_uses_default():
    content = CONTENT.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    shot = SHOT.read_text(encoding="utf-8")
    assert "init(session: SessionModel? = nil)" in content
    assert "ContentView()" in app
    assert "if UIShotLaunch.isActive" in app
    assert "UIShotLaunch.sessionIfRequested()" in app
    assert "prepareProcessIfNeeded()" in app
    # Normal launch does not build a sample session.
    assert "guard isActive else { return }" in shot
    for token in (
        "dropped-awaiting",
        "after-write",
        "sample-a.mov",
        "sample-locked.mov",
        "wroteProxyChip",
        "batchSummaryText",
        "CI 离屏渲染·假数据·非真机",
    ):
        assert token in shot
        assert token in TOOL.read_text(encoding="utf-8")


def test_placeholder_colors_fail_and_small_accents_do_not():
    assert is_prohibited_placeholder(0.03, 0.01) is True
    assert is_prohibited_placeholder(0.005, 0.004) is False
    assert is_prohibited_placeholder(0.05, 0.0) is False
    assert is_blank_capture(0.2) is True
    assert is_blank_capture(4.0) is False

    prohibited = Image.new("RGB", (100, 100), (240, 240, 240))
    pixels = prohibited.load()
    for i in range(300):
        pixels[i % 100, i // 100] = (255, 204, 0)
    for i in range(300):
        pixels[i % 100, 10 + i // 100] = (255, 59, 48)
    stats = analyze_image(prohibited)
    assert is_prohibited_placeholder(stats.yellow_frac, stats.red_frac)

    accent = Image.new("RGB", (100, 100), (236, 236, 236))
    accent.putpixel((0, 0), (255, 204, 0))
    accent.putpixel((1, 0), (255, 59, 48))
    accent_stats = analyze_image(accent)
    assert not is_prohibited_placeholder(accent_stats.yellow_frac, accent_stats.red_frac)

    blank = Image.new("RGB", (80, 80), (236, 236, 236))
    assert is_blank_capture(analyze_image(blank).stddev)
    assert toolbar_region_present(960, 900) is True
    assert toolbar_region_present(900, 900) is False
    assert toolbar_region_present(840, 800) is True


def test_after_write_must_not_match_locked_bytes(tmp_path: Path):
    def write(name: str, color: tuple[int, int, int]) -> None:
        height = int(name.split("-")[-2].split("x")[1])
        width = int(name.split("-")[-2].split("x")[0])
        Image.new("RGB", (width, height + 48), color).save(tmp_path / name)

    for size in ("1440x900", "1280x800"):
        for appearance in ("light", "dark"):
            write(f"empty-{size}-{appearance}.png", (230, 230, 230))
            write(f"dropped-awaiting-{size}-{appearance}.png", (220, 220, 225))
            write(f"locked-{size}-{appearance}.png", (210, 210, 210))
            write(f"after-write-{size}-{appearance}.png", (200, 205, 210))
    # Solid fields are blank captures. Recolor with a text-like mark so the
    # hash check is what this fixture is about.
    for path in tmp_path.glob("*.png"):
        image = Image.open(path).convert("RGB")
        for x in range(40):
            image.putpixel((x, 10), (20, 20, 20))
        image.save(path)
    assert check_directory(tmp_path) == []
    locked = tmp_path / "locked-1440x900-light.png"
    wrote = tmp_path / "after-write-1440x900-light.png"
    wrote.write_bytes(locked.read_bytes())
    errors = check_directory(tmp_path)
    assert any("after-write matches locked for 1440x900 light" in line for line in errors)


def test_baseline_wire_patches_28066d5_without_committing(tmp_path: Path):
    """Uses files copied from 28066d5. A shallow CI clone does not contain that commit."""
    work = tmp_path / "baseline"
    (work / "macos/LogBridge/LogBridge").mkdir(parents=True)
    project = work / "macos/LogBridge/LogBridge.xcodeproj"
    scheme_dir = project / "xcshareddata/xcschemes"
    scheme_dir.mkdir(parents=True)
    fixture = ROOT / "tests/fixtures/ui_baseline_28066d5"
    project_text = (fixture / "project.pbxproj").read_text(encoding="utf-8")
    scheme_text = (fixture / "LogBridge.xcscheme").read_text(encoding="utf-8")
    app_text = (fixture / "LogBridgeApp.swift").read_text(encoding="utf-8")
    (project / "project.pbxproj").write_text(project_text, encoding="utf-8")
    (scheme_dir / "LogBridge.xcscheme").write_text(scheme_text, encoding="utf-8")
    (work / "macos/LogBridge/LogBridge/LogBridgeApp.swift").write_text(app_text, encoding="utf-8")
    subprocess.check_call(
        ["python3", str(ROOT / "scripts/wire_baseline_shot_launch.py"), str(work), str(ROOT)],
        cwd=ROOT,
    )
    wired = (project / "project.pbxproj").read_text(encoding="utf-8")
    app = (work / "macos/LogBridge/LogBridge/LogBridgeApp.swift").read_text(encoding="utf-8")
    scheme = (scheme_dir / "LogBridge.xcscheme").read_text(encoding="utf-8")
    assert "UIShotLaunch.swift" in wired
    assert "LogBridgeUITests" in wired
    assert wired.count("isa = PBXNativeTarget") == 2
    assert app.count("{") == app.count("}")
    assert "UIShotLaunch.isActive" in app
    assert "ContentView()" in app
    assert "LogBridgeUITests.xctest" in scheme
    assert (work / "macos/LogBridge/LogBridge/UIShotLaunch.swift").is_file()
    assert (work / "macos/LogBridge/LogBridgeUITests/LogBridgeUIShots.swift").is_file()
    # Second run stays a no-op rather than duplicating the target.
    subprocess.check_call(
        ["python3", str(ROOT / "scripts/wire_baseline_shot_launch.py"), str(work), str(ROOT)],
        cwd=ROOT,
    )
    again = (project / "project.pbxproj").read_text(encoding="utf-8")
    assert again.count("isa = PBXNativeTarget") == 2
    # The real tree stays on the current app entry. The fixture checkout is disposable.
    real_app = (ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift").read_text(encoding="utf-8")
    assert "UIShotLaunch.isActive" in real_app
    assert "LogBridgeCommands" in real_app
