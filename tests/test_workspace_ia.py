"""Team B workspace IA. Product copy stays locked. No second process path."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWIFT_ROOT = ROOT / "macos"
CONTENT = SWIFT_ROOT / "LogBridge/LogBridge/ContentView.swift"
CHROME = SWIFT_ROOT / "LogBridge/LogBridge/Views/WorkspaceChrome.swift"
SIDEBAR = SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift"
INSPECTOR = SWIFT_ROOT / "LogBridge/LogBridge/Views/InspectorView.swift"
CLIP = SWIFT_ROOT / "LogBridge/LogBridge/Models/Clip.swift"
DESIGN = ROOT / "DESIGN.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code_without_comments(src: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


def test_design_doc_is_plain_chinese():
    design = _read(DESIGN)
    assert "把混源文件夹拖进来" in design
    assert "处理已锁定片段" in design
    assert "预览·非成片" in design
    assert "整段代理，不是全精度成片" in design
    assert "CI 绿不等于达芬奇已验证" in design
    assert "一键还原" not in design or "没改" in design
    assert "精准" not in design
    assert "#132" in design


def test_empty_window_is_full_canvas_not_three_empty_columns():
    content = _read(CONTENT)
    chrome = _read(CHROME)
    ui = _code_without_comments(content)
    assert "WorkspaceHeader(session: session)" in content
    assert "EmptyPreviewStage(session: session)" in content
    assert "if session.clips.isEmpty" in ui
    assert ui.index("EmptyPreviewStage") < ui.index("HSplitView")
    assert "把混源文件夹拖进来" in chrome
    assert "点处理已锁定片段。得到的是 EXR 图序列，不是视频。" in chrome
    assert "session.showImporter = true" in chrome
    assert 'Button("处理已锁定片段")' not in chrome
    assert 'Button("一键还原")' not in chrome


def test_header_has_three_steps_and_preview_output():
    chrome = _read(CHROME)
    clip = _read(CLIP)
    assert "struct WorkspaceHeader" in chrome
    assert "struct WorkspaceStepStrip" in chrome
    assert 'return "导入"' in chrome
    assert 'return "选对"' in chrome
    assert 'return "写出代理"' in chrome
    assert "把混源文件夹拖进来" in chrome
    assert "每条选成对 Log 与色域" in chrome
    assert "点处理已锁定片段" in chrome
    assert 'Picker("预览输出"' in chrome
    assert "session.setODT" in chrome
    assert "workspaceStep" in clip
    assert "pendingClipCount" in clip.split("var workspaceStep")[1].split("var sidebarClips")[0]
    assert 'Picker("ODT"' not in chrome


def test_core_path_still_one_process_button():
    content = _read(CONTENT)
    inspector = _read(INSPECTOR)
    sidebar = _read(SIDEBAR)
    center = content.split("VStack(spacing: 0)")[1].split(".frame(minWidth: 520)")[0]
    assert "SplitPreview" in center
    assert "PairedIDTBar" in center
    assert "ProcessLockedBar" in center
    assert center.index("SplitPreview") < center.index("PairedIDTBar")
    assert center.index("PairedIDTBar") < center.index("ProcessLockedBar")
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "处理已锁定片段" in bar
    assert "取消" in bar
    assert "showsProcessLockedButton" in bar
    assert "这一步：每条选成对 Log 与色域" in inspector
    assert 'Picker("用户选择成对 IDT"' in inspector
    assert 'Button("锁 IDT")' not in sidebar
    assert "sidebarClips" in sidebar
    assert "ClipSidebarFilter" in sidebar


def test_no_marketing_and_no_resolve_verified_claim():
    chrome = _read(CHROME)
    design = _read(DESIGN)
    content = _read(CONTENT)
    for chunk in (chrome, design, content):
        assert "达芬奇已验证" not in chunk
        assert "一键精准" not in chunk
        assert 'Button("一键还原")' not in chunk
