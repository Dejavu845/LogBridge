"""Chinese settings page. No color numbers. No 精准 / 一键还原 / 全自动校准."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "macos/LogBridge/LogBridge/Views/SettingsView.swift"
APP = ROOT / "macos/LogBridge/LogBridge/Models/AppSettings.swift"
CLIP = ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift"
SIDEBAR = ROOT / "macos/LogBridge/LogBridge/Views/ClipSidebarView.swift"


SETTINGS_PREVIEW_HELP = (
    "默认 Rec.709（角标预览·非成片）。不是成片，未与 HDR 匹配。导出仍是 ACEScct / EXR。"
)
SETTINGS_PREVIEW_SCRUB_HELP = (
    "预览窗下拖时间轴。轴按片源时长。默认落到片源帧率对应的那一帧；设置里指定了工作帧率就落到那个。读不到时长或帧率（又没指定）就不做轴，不猜帧率。静帧没有时间轴。命中缓存只重跑预览输出。预览·非成片。"
)
SETTINGS_FPS_HELP = (
    "默认只用片源帧率。导入读数、时间轴、预览落帧都按这个。读不到片源帧率就不做轴；写出核对也不做，不猜帧率。选「用户指定」并选定一个数之后，时间轴和预览用这个数。片源读不到帧率时，写出核对才用这个数。写出仍是片源一帧一张 EXR，不是转帧。指定不是检测。静帧没有帧率。预览·非成片。"
)
SETTINGS_WB_HELP = (
    "默认关。打开后只提示「白平衡（估计）」，不会自动写入白平衡，不猜 5600。确认后才写。灰卡覆盖估计。不是校准。"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code_without_comments(src: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


_SETTINGS_DISCLAIMER_LINES = {
    "/// 设置页。中文。不写精准 / 一键还原 / 全自动校准。",
    'Text("已实现（未验证）。不写精准 / 一键还原 / 全自动校准。")',
}


def _settings_minus_disclaimers(settings: str) -> str:
    return "\n".join(
        ln for ln in settings.splitlines() if ln.strip() not in _SETTINGS_DISCLAIMER_LINES
    )


def test_settings_copy_is_chinese():
    s = _read(SETTINGS)
    ui = _code_without_comments(s)
    assert "默认预览" in s
    assert "Rec.709 预览·非成片" in s
    assert "Rec.2100 HLG 预览·非成片" in s
    assert "Rec.2100 PQ 预览·非成片" in s
    assert 'Text("Rec.709 预览·非成片").tag(ODTMode.rec709)' in s
    assert 'Text("Rec.2100 HLG 预览·非成片").tag(ODTMode.hlg)' in s
    assert 'Text("Rec.2100 PQ 预览·非成片").tag(ODTMode.pq)' in s
    assert SETTINGS_PREVIEW_HELP in s
    assert SETTINGS_PREVIEW_SCRUB_HELP in s
    assert f'Text("{SETTINGS_PREVIEW_SCRUB_HELP}")' in s
    assert SETTINGS_FPS_HELP in s
    assert f'Text("{SETTINGS_FPS_HELP}")' in s
    assert 'Text("帧率")' in s
    assert "policy.menuLabel" in s
    assert "rate.menuLabel" in s
    assert "只用片源帧率" in _read(ROOT / "macos/LogBridge/LogBridge/Models/FrameRate.swift")
    assert "用户指定（未核对）" in _read(ROOT / "macos/LogBridge/LogBridge/Models/FrameRate.swift")
    assert SETTINGS_WB_HELP in s
    assert f'Text("{SETTINGS_WB_HELP}")' in s
    assert "不写入 CAT" not in SETTINGS_WB_HELP
    assert "CAT" not in SETTINGS_WB_HELP
    assert "预览·非成片" in s
    assert "角标预览·非成片" in s
    assert "DIY OETF" not in ui
    assert "DIY" not in ui
    assert "导入后提示估计白平衡" in s
    assert "未锁 IDT 挡住处理" in s
    assert "不能关" in s
    assert "不猜 5600" in s
    assert "不是校准" in s
    assert "完善" not in s
    scanned = _settings_minus_disclaimers(s)
    assert "精准" not in scanned
    assert "一键还原" not in scanned
    assert "全自动校准" not in scanned
    assert "达芬奇已验证" not in s
    assert "已实现（未验证）" in s
    assert "implemented (unverified)" not in s.lower()


def test_settings_defaults_locked():
    app = _read(APP)
    clip = _read(CLIP)
    assert "defaultPreviewODT" in app
    assert ".rec709" in app
    assert "promptEstimateWBOnImport" in app
    assert "blockUnlockedIDT: Bool = true" in app
    assert "lastExportDirectoryPath" in app
    assert "logbridge.lastExportDirectory" in app
    assert "rememberExportDirectory" in app
    assert "frameRatePolicy" in app
    assert "userFrameRate" in app
    assert "userWorkingFPS" in app
    assert "logbridge.frameRatePolicy" in app
    assert "?? .source" in app
    assert "userFrameRate = nil" in app
    assert "applyFrameRateSettings" in clip
    assert "graph.odt = settings.defaultPreviewODT" in clip
    assert "promptEstimateWBOnImport" in clip
    assert "confirmAutoWB" not in clip.split("promptEstimateWBOnImport")[1].split("refreshPreview")[0]
    assert "5600" in clip
    assert "showSettings" in clip


def test_settings_button_and_block_cannot_disable():
    sidebar = _read(SIDEBAR)
    settings = _read(SETTINGS)
    clip = _read(CLIP)
    assert 'Button("设置")' in sidebar
    assert ".disabled(true)" in settings
    assert "canProcess" in clip
    assert "hasLockedPair" in clip
    assert "先选择 Log 与色域" in clip
