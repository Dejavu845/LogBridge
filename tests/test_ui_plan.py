"""UI plan: single-window grade/delivery, no personal data, scopes stay advanced."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "ui-plan.md"
CONTENT = ROOT / "macos" / "LogBridge" / "LogBridge" / "ContentView.swift"
SETTINGS = ROOT / "macos" / "LogBridge" / "LogBridge" / "Views" / "SettingsView.swift"
DELIVER = ROOT / "macos" / "LogBridge" / "LogBridge" / "Views" / "DeliverSheet.swift"
HISTOGRAM = ROOT / "macos" / "LogBridge" / "LogBridge" / "Views" / "PreviewHistogramView.swift"

BANNED_CONTACT = (
    "@",
    "微信",
    "WeChat",
    "weixin",
    "Dejavu",
    "Phillip",
    "Hopkins",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ui_plan_records_layout_and_stays_private():
    text = _read(PLAN)
    assert "没有剪辑时间线" in text
    assert "示波器" in text
    assert "全局偏好" in text
    assert "检查器" in text
    assert "整段代理" in text
    assert "LogBridge contributors" not in text or "MIT" in _read(ROOT / "README.md")
    for token in BANNED_CONTACT:
        assert token not in text, token
    for token in ("支持", "一键", "精准", "成片", "成品"):
        assert token not in text, token


def test_histogram_stays_inside_advanced_panel():
    content = _read(CONTENT)
    advanced = content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    assert "PreviewHistogramView" in advanced
    assert "PreviewHistogramView" not in content.split("struct AdvancedPanel")[0]
    histogram = _read(HISTOGRAM)
    assert "不是示波器读数" in histogram
    assert "不参与写出" in histogram


def test_settings_apply_immediately_without_save_cancel():
    settings = _read(SETTINGS)
    assert "改完即生效" in settings
    assert 'Button("保存"' not in settings
    assert 'Button("取消"' not in settings
    assert "默认写出格式" in settings


def test_deliver_sheet_is_separate_from_preferences():
    deliver = _read(DELIVER)
    content = _read(CONTENT)
    assert "选出文件夹并写出" in deliver
    assert "processLockedClips" not in deliver
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "processLockedClips" in bar
    assert "showDeliverSheet" in bar
    assert "attachedSheet" in bar
    assert "下一步：在右侧检查器选成对 IDT" in bar
    assert "DeliverSheet" not in _read(SETTINGS)
