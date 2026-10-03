"""macOS CI screenshot baseline. Fake sample state only. No footage."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/test.yml"
TOOL = ROOT / "scripts/ui_snapshot.swift"
SCRIPT = ROOT / "scripts/ui_snapshot.sh"
CONTENT = ROOT / "macos/LogBridge/LogBridge/ContentView.swift"
APP = ROOT / "macos/LogBridge/LogBridge/LogBridgeApp.swift"


def test_macos_workflow_uploads_ui_screenshots_artifact():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    macos = workflow.split("macos:", 1)[1]
    assert "bash scripts/ui_snapshot.sh" in macos
    assert "uses: actions/upload-artifact@v4" in macos
    assert "name: ui-screenshots" in macos
    assert "ui-screenshots/*.png" in macos
    assert "if-no-files-found: warn" in macos
    assert "if: always()" in macos


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
        "ImageRenderer",
        "NSHostingView",
        "ContentView(session:",
        "sample-a.mov",
        "sample-locked.mov",
    ):
        assert token in tool
    assert "return 0" in tool
    assert "LogBridgeApp.swift" in script
    assert "exit 0" in script
    # Runner stays outside macos/ so UI copy locks do not see this tool.
    assert TOOL.relative_to(ROOT).parts[0] == "scripts"


def test_content_view_accepts_injected_session_and_app_uses_default():
    content = CONTENT.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "init(session: SessionModel? = nil)" in content
    assert "ContentView()" in app
