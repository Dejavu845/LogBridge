"""Working frame-rate settings. Source by default. User pick is 用户指定（未核对）。"""

from pathlib import Path

from color.batch import (
    MISSING_DURATION_CHIP,
    MISSING_FPS_CHIP,
    BatchClip,
    expected_source_frames,
    timeline_fps,
    verify_fps,
)

ROOT = Path(__file__).resolve().parents[1]
SWIFT = ROOT / "macos/LogBridge/LogBridge"
FRAME = SWIFT / "Models/FrameRate.swift"
APP = SWIFT / "Models/AppSettings.swift"
SETTINGS = SWIFT / "Views/SettingsView.swift"
CLIP = SWIFT / "Models/Clip.swift"
ENGINE = SWIFT / "Preview/PreviewEngine.swift"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_timeline_uses_source_until_user_picks():
    assert timeline_fps(25.0, "source") == 25.0
    assert timeline_fps(25.0, "source", 24.0) == 25.0
    assert timeline_fps(25.0, "user", None) == 25.0
    assert timeline_fps(25.0, "user", 23.976) == 23.976
    assert timeline_fps(None, "source") is None
    assert timeline_fps(None, "user", None) is None
    assert timeline_fps(None, "user", 25.0) == 25.0


def test_verify_keeps_source_when_present():
    assert verify_fps(25.0, "user", 24.0) == 25.0
    assert verify_fps(None, "user", 25.0) == 25.0
    assert verify_fps(None, "source", 24.0) is None
    assert verify_fps(None, "source") is None


def test_expected_source_frames_accepts_working_fps_without_inventing():
    missing = BatchClip("a.mov", duration_seconds=2.0)
    n, err = expected_source_frames(missing)
    assert n is None
    assert err == MISSING_FPS_CHIP

    n, err = expected_source_frames(missing, working_fps=25.0)
    assert err is None
    assert n == 50

    source = BatchClip("b.mov", duration_seconds=2.0, fps=25.0)
    n, err = expected_source_frames(source, working_fps=24.0)
    assert err is None
    assert n == 48

    no_dur = BatchClip("c.mov", fps=25.0)
    n, err = expected_source_frames(no_dur, working_fps=24.0)
    assert n is None
    assert err == MISSING_DURATION_CHIP

    src = _read(ROOT / "color/batch.py").split("def expected_source_frames")[1].split(
        "def count_proxy_exrs"
    )[0]
    assert "CONSERVATIVE" not in src
    assert "24" not in src
    assert "30" not in src


def test_swift_frame_rate_settings_are_source_default_and_wired():
    frame = _read(FRAME)
    app = _read(APP)
    settings = _read(SETTINGS)
    clip = _read(CLIP)
    engine = _read(ENGINE)
    assert "case source" in frame
    assert "case user" in frame
    assert "只用片源帧率" in frame
    assert "用户指定（未核对）" in frame
    assert "func timelineFPS" in frame
    assert "func verifyFPS" in frame
    assert "24000.0 / 1001.0" in frame
    assert "30000.0 / 1001.0" in frame
    assert "frameRatePolicy" in app
    assert "userFrameRate" in app
    assert "userWorkingFPS" in app
    assert "?? .source" in app
    assert "userFrameRate = nil" in app
    assert 'Picker("工作帧率"' in settings
    assert 'Text("帧率")' in settings
    assert "applyFrameRateSettings" in clip
    assert "WorkingFrameRate.timelineFPS" in clip
    assert "WorkingFrameRate.verifyFPS" in clip
    assert "timingSidebarLine" in clip
    assert "sourceFPS" in clip
    assert "decodeFPSOverride" in engine
    assert "fpsOverride" in engine
    assert "MediaFormat.extent" in engine.split("func decodeMovieVideoToolbox")[1].split(
        "func readFirstYpCbCrFrame"
    )[0]


def test_preview_and_verify_do_not_hardcode_rates():
    clip = _read(CLIP)
    reset = clip.split("func resetPreviewScrub()")[1].split("var pendingPickerCount")[0]
    set_fn = clip.split("func setPreviewFrame")[1].split("func resetPreviewScrub")[0]
    expected = clip.split("static func expectedSourceFrames")[1].split(
        "static func countProxyEXRs"
    )[0]
    for chunk in (reset, set_fn, expected):
        assert "24" not in chunk
        assert "30" not in chunk
        assert "conservativeFPS" not in chunk
