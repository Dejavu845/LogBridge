"""Locked-IDT batch: walk locked clips only. Unlocked stay listed."""

from pathlib import Path

import numpy as np

from color.as_shot import WB_SOURCE_AS_SHOT, WB_SOURCE_ESTIMATE, WB_SOURCE_GREY
from color.batch import (
    ADVANCED_DISCLOSURE,
    DELIVERABLE_DIR_SUFFIX,
    DELIVERABLE_SUFFIX,
    FOLDER_PICKER_MESSAGE,
    HONEST_PROXY_NOTE,
    PROCESS_BUTTON,
    PROCESS_BUTTON_HELP,
    PROCESSED_STATUS_TEMPLATE,
    REASON_PICK_LOG_GAMUT,
    REASON_PICK_PAIRED_IDT,
    BatchClip,
    confirm_auto_wb,
    deliverable_dir_name,
    deliverable_name,
    estimate_chip_lit,
    has_locked_idt,
    never_guess_cct,
    plan_locked_batch,
    process_locked_names,
    process_locked_writes,
    processed_status_text,
    propose_auto_wb,
    sequence_frame_name,
    skip_reason,
)
from color.curves import linear_to_slog3
from color.exr_write import read_rgb_exr
from color.graph import SerialGraph

ROOT = Path(__file__).resolve().parents[1]
SWIFT_ROOT = ROOT / "macos"
CLIP = SWIFT_ROOT / "LogBridge/LogBridge/Models/Clip.swift"
CONTENT = SWIFT_ROOT / "LogBridge/LogBridge/ContentView.swift"
INSPECTOR = SWIFT_ROOT / "LogBridge/LogBridge/Views/InspectorView.swift"
SIDEBAR = SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _all_swift() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SWIFT_ROOT.rglob("*.swift"))


def test_batch_walks_locked_only_skips_unlocked():
    clips = [
        BatchClip("locked.mov", idt="sony_slog3_sgamut3"),
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
        BatchClip("empty.mov"),
        BatchClip("stub.mov", idt="future", is_stub=True),
    ]
    plan = plan_locked_batch(clips)
    assert process_locked_names(clips) == ["locked.mov"]
    assert plan.locked_count == 1
    assert plan.pending_count == 3
    assert plan.lock_status_text == "1 条已锁定 / 3 条待选"
    assert plan.shows_process_button is True
    reasons = {c.name: reason for c, reason in plan.skipped}
    assert reasons["pending.mov"] == REASON_PICK_PAIRED_IDT
    assert reasons["empty.mov"] == REASON_PICK_LOG_GAMUT
    assert reasons["stub.mov"] == REASON_PICK_PAIRED_IDT
    assert skip_reason(clips[0]) is None
    assert has_locked_idt(clips[1]) is False


def test_no_process_button_when_nothing_locked():
    clips = [
        BatchClip("a.mov"),
        BatchClip("b.mov", detected_curve="C-Log2", needs_user_picker=True),
    ]
    plan = plan_locked_batch(clips)
    assert plan.shows_process_button is False
    assert process_locked_names(clips) == []
    assert plan.lock_status_text == "0 条已锁定 / 2 条待选"


def test_needs_picker_even_with_idt_is_skipped():
    clip = BatchClip("half.mov", idt="sony_slog3_sgamut3", needs_user_picker=True)
    assert has_locked_idt(clip) is False
    assert skip_reason(clip) == REASON_PICK_PAIRED_IDT


def test_estimate_chip_lights_only_after_confirm():
    state = {"wb_source": WB_SOURCE_AS_SHOT, "wb_cct": 3200.0, "auto_wb_cct": None}
    proposed = propose_auto_wb(state, 4100.0, 0.2)
    assert proposed["auto_wb_cct"] == 4100.0
    assert proposed["wb_source"] == WB_SOURCE_AS_SHOT
    assert proposed["wb_cct"] == 3200.0
    assert estimate_chip_lit(proposed["wb_source"]) is False
    confirmed = confirm_auto_wb(proposed)
    assert confirmed["wb_source"] == WB_SOURCE_ESTIMATE
    assert confirmed["wb_cct"] == 4100.0
    assert estimate_chip_lit(confirmed["wb_source"]) is True


def test_grey_card_overrides_estimate_and_no_5600_guess():
    grey = {
        "wb_source": WB_SOURCE_GREY,
        "wb_cct": 4800.0,
        "auto_wb_cct": 4100.0,
    }
    assert confirm_auto_wb(grey)["wb_source"] == WB_SOURCE_GREY
    assert confirm_auto_wb(grey)["wb_cct"] == 4800.0
    empty = propose_auto_wb({"wb_source": WB_SOURCE_AS_SHOT}, None)
    assert empty["auto_wb_cct"] is None
    assert confirm_auto_wb(empty)["wb_source"] == WB_SOURCE_AS_SHOT
    assert "wb_cct" not in confirm_auto_wb(empty)
    assert never_guess_cct(None) is True
    assert never_guess_cct(5600) is False


def test_swift_mirrors_locked_batch_and_one_button():
    clip = _read(CLIP)
    content = _read(CONTENT)
    inspector = _read(INSPECTOR)
    sidebar = _read(SIDEBAR)
    swift = _all_swift()
    assert "func processLockedClips()" in clip
    assert "processLockedClips()" in clip.split("func processSelected()")[1]
    assert "processLockedClips()" in clip.split("func applyGraph()")[1]
    assert "lockedClipCount" in clip
    assert "lockStatusText" in clip
    assert "showsProcessLockedButton" in clip
    assert "processSkipReason" in clip
    assert "先选择成对 IDT" in clip
    assert "先选择 Log 与色域" in clip
    assert "条已锁定" in clip and "条待选" in clip
    assert 'Button("处理已锁定片段")' in content
    assert "showsProcessLockedButton" in content
    assert "ProcessLockedBar" in content
    assert content.count("处理已锁定片段") >= 1
    assert 'Button("处理已锁定片段")' not in content.split("struct StatusBar")[1]
    assert 'Button("导出 ACEScct / EXR")' in content.split("struct AdvancedPanel")[1]
    assert ADVANCED_DISCLOSURE in content
    assert 'DisclosureGroup("高级"' in content
    assert "showAdvanced = false" in content
    assert "PairedIDTBar" in content
    assert "InspectorView" in content
    assert PROCESS_BUTTON in swift
    assert "机内 as-shot" in inspector
    assert "白平衡（估计）" in inspector
    assert "灰卡" in inspector
    assert "on: session.graph.wbSource == .estimate" in inspector
    assert "proposeAutoWB" in inspector
    assert "确认估计" in inspector
    assert "processSkipReason" in sidebar
    assert "一键还原" not in content or "Never 一键还原" in content


def test_inspector_is_exposure_and_wb_only():
    inspector = _read(INSPECTOR)
    content = _read(CONTENT)
    assert "ExposureInspector" in inspector
    assert "WBInspector" in inspector
    assert "struct InspectorView" in inspector
    body = inspector.split("struct InspectorView")[1].split("struct WBInspector")[0]
    assert "ExposureInspector" in body
    assert "WBInspector" in body
    assert "IDTInspector" not in body
    assert "ODTInspector" not in body
    advanced = content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    assert "NodeStripView" in advanced
    assert "导出 ACEScct / EXR" in advanced
    assert "ODTInspector" not in advanced
    assert "PairedIDTBar" not in advanced
    assert "成对 IDT" not in advanced


def _slog3_grey(shape=(2, 2, 3)):
    return np.full(shape, float(linear_to_slog3(0.18)), dtype=np.float64)


def test_unlocked_never_write_locked_writes_and_counter(tmp_path: Path):
    clips = [
        BatchClip("locked.mov", idt="sony_slog3_sgamut3"),
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
        BatchClip("empty.mov"),
        BatchClip("stub.mov", idt="future", is_stub=True),
    ]
    grey = _slog3_grey()
    frames = {c.name: grey for c in clips}
    called: list[str] = []

    def spy(path: Path, rgb) -> None:
        called.append(Path(path).name)
        path.write_bytes(b"x")

    report = process_locked_writes(clips, tmp_path, frames=frames, write_fn=spy)
    assert called == [sequence_frame_name(0)]
    assert report.processed_count == 1
    assert report.skipped_count == 3
    assert "1 条已处理" in report.processed_status_text
    assert "3 条已跳过" in report.processed_status_text
    assert processed_status_text(1, 3) == report.processed_status_text
    assert (tmp_path / deliverable_name("locked.mov")).is_file()
    assert not (tmp_path / deliverable_dir_name("pending.mov")).exists()
    assert not (tmp_path / deliverable_dir_name("empty.mov")).exists()
    assert not (tmp_path / deliverable_dir_name("stub.mov")).exists()
    assert list(tmp_path.glob("*" + DELIVERABLE_DIR_SUFFIX)) == [
        tmp_path / deliverable_dir_name("locked.mov")
    ]


def test_locked_exr_is_aces2065_and_mixed_bin_writes(tmp_path: Path):
    clips = [
        BatchClip("locked.mov", idt="sony_slog3_sgamut3"),
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
    ]
    report = process_locked_writes(
        clips, tmp_path, frames={"locked.mov": _slog3_grey(), "pending.mov": _slog3_grey()}
    )
    assert report.processed_count == 1
    assert "1 条已处理" in report.processed_status_text
    path = tmp_path / deliverable_name("locked.mov")
    assert path.is_file()
    rgb = read_rgb_exr(path)
    assert rgb.shape == (2, 2, 3)
    np.testing.assert_allclose(rgb[0, 0], 0.18, atol=5e-3)
    assert not (tmp_path / deliverable_dir_name("pending.mov")).exists()


def test_wb_off_identity_still_writes_exr(tmp_path: Path):
    """Existing WB toggle: off / identity must still write. Never required."""
    clips = [BatchClip("locked.mov", idt="sony_slog3_sgamut3")]
    frames = {"locked.mov": _slog3_grey()}
    off = SerialGraph(wb_enabled=False, wb_cct=None)
    assert off.wb_enabled is False
    report = process_locked_writes(clips, tmp_path / "off", frames=frames, graph=off)
    assert report.processed_count == 1
    assert len(report.written) == 1
    off_rgb = read_rgb_exr(Path(report.written[0].path) / sequence_frame_name(0))
    on = SerialGraph(wb_enabled=True, wb_cct=3200.0, wb_source=WB_SOURCE_GREY)
    report_on = process_locked_writes(clips, tmp_path / "on", frames=frames, graph=on)
    assert report_on.processed_count == 1
    on_rgb = read_rgb_exr(Path(report_on.written[0].path) / sequence_frame_name(0))
    assert not np.allclose(on_rgb, off_rgb, atol=1e-3)
    assert HONEST_PROXY_NOTE in report.processed_status_text
    _assert_chengpian_not_a_deliverable_claim(report.processed_status_text)


def test_write_error_counts_as_processed_no_file(tmp_path: Path):
    clips = [BatchClip("locked.mov", idt="sony_slog3_sgamut3")]
    report = process_locked_writes(clips, tmp_path, frames={})
    assert report.processed_count == 1
    assert report.written == ()
    assert report.errors[0].name == "locked.mov"
    assert "1 条已处理" in report.processed_status_text
    assert list(tmp_path.glob("*.exr")) == []
    assert list(tmp_path.glob("*" + DELIVERABLE_DIR_SUFFIX)) == []


def test_swift_process_writes_exr_and_counter_is_writes():
    clip = _read(CLIP)
    content = _read(CONTENT)
    exporter = _read(SWIFT_ROOT / "LogBridge/LogBridge/Export/ResolveExporter.swift")
    engine = _read(SWIFT_ROOT / "LogBridge/LogBridge/Preview/PreviewEngine.swift")
    body = clip.split("func processLockedClips()")[1].split("func processSelected()")[0]
    assert "writeLockedDeliverables" in body
    assert "条已处理" in body or "条已处理" in clip.split("func writeLockedDeliverables")[1]
    write_body = clip.split("func writeLockedDeliverables")[1].split("func exportLockedEXR")[0]
    assert "written.count + errors.count" in write_body
    assert "locked.count" not in write_body
    assert HONEST_PROXY_NOTE in write_body
    assert HONEST_PROXY_NOTE in body
    _assert_chengpian_not_a_deliverable_claim(write_body)
    _assert_chengpian_not_a_deliverable_claim(body)
    assert "exportLockedEXR" in clip
    assert "writeACES2065EXR" in clip
    assert "exportGradedAP0Sequence" in clip
    assert "_ACES2065-1_proxy" in exporter
    assert "frame_%06d.exr" in exporter
    assert "_proxy_frame0.exr" not in exporter
    assert "ACES2065-1.exr\"" not in exporter
    assert "exportGradedAP0" in engine
    assert "exportGradedAP0Sequence" in engine
    assert "decodeMovieAllFrames" in engine
    assert "while let sample = output.copyNextSampleBuffer()" in engine
    _assert_export_sequence_tries_10bit_first(engine)
    grade = engine.split("func gradeAP0")[1].split("func exportGradedAP0(")[0]
    assert "applyODT" not in grade
    assert "if graph.wbEnabled" in grade
    export_seq = engine.split("func exportGradedAP0Sequence")[1].split("func decodeAllSourceFrames")[0]
    assert "applyODT" not in export_seq
    assert "gradeAP0" in export_seq
    export_body = clip.split("func exportLockedEXR")[1].split("func processSelected()")[0]
    assert "writeACES2065EXR" in export_body
    assert "sequenceFrameURL" in export_body
    assert "AVAssetExport" not in export_body
    assert "AVAssetWriter" not in export_body
    can = clip.split("var canProcess")[1].split("var canProcessSelected")[0]
    assert "pendingPickerCount == 0" not in can
    assert "lockedClipCount" in can
    export = clip.split("func exportResolve()")[1]
    assert "lockedClips" in export.split("panel.begin")[0]
    assert "clips: locked" in export or "clips: lockedClips" in export
    assert "先选择成对 IDT" in export
    assert "先选择 Log 与色域" in export
    assert "hasLockedPair" in exporter.split("func uniqueImplementedIDTs")[1]
    assert "matrixCCT = nil" in exporter
    assert "709 预览" in exporter
    assert "not ACES OT" in exporter
    assert HONEST_PROXY_NOTE in content
    assert "不是 ACEScct" in content
    assert "Does not require the whole bin" in content
    _assert_chengpian_not_a_deliverable_claim(content)


def _assert_export_sequence_tries_10bit_first(engine: str) -> None:
    """Export sequence prefers 10-bit Y′CbCr; preview/scrub stays 8-bit-first."""
    export_decode = engine.split("func decodeMovieAllFrames")[1].split(
        "func readAllYpCbCrFrames"
    )[0]
    preview_decode = engine.split("func decodeMovieVideoToolbox")[1].split(
        "func readFirstYpCbCrFrame"
    )[0]
    ten = "kCVPixelFormatType_420YpCbCr10BiPlanarVideoRange"
    eight_420 = "kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange"
    eight_422 = "kCVPixelFormatType_422YpCbCr8"
    assert export_decode.index(ten) < export_decode.index(eight_420)
    assert export_decode.index(eight_420) < export_decode.index(eight_422)
    assert preview_decode.index(eight_420) < preview_decode.index(eight_422)
    assert preview_decode.index(eight_422) < preview_decode.index(ten)
    assert "copyCGImage(" not in export_decode
    assert "AVVideoColorPropertiesKey:" not in export_decode
    assert HONEST_PROXY_NOTE in engine


def _assert_chengpian_not_a_deliverable_claim(text: str) -> None:
    """成片 may only appear as 预览·非成片 / 不是全精度成片 / 不是整段成片 / 不是成片."""
    cleaned = (
        text.replace("预览·非成片", "")
        .replace("不是全精度成片", "")
        .replace("不是整段成片", "")
        .replace("不是成片", "")
        .replace("成片预览关", "")
    )
    assert "成片" not in cleaned


def test_export_sequence_prefers_10bit_ycbcr():
    engine = _read(SWIFT_ROOT / "LogBridge/LogBridge/Preview/PreviewEngine.swift")
    assert HONEST_PROXY_NOTE in engine
    _assert_export_sequence_tries_10bit_first(engine)
    assert "writeMatrixRGB" in engine
    ten_block = engine.split("kCVPixelFormatType_420YpCbCr10BiPlanarVideoRange")[-1]
    assert "writeMatrixRGB" in ten_block.split("func writeMatrixRGB")[0]
    matrix = engine.split("func writeMatrixRGB")[1]
    assert "1.5748" in matrix
    assert "0.1873" in matrix
    assert "0.4681" in matrix
    assert "1.8556" in matrix


def test_honest_proxy_copy_and_filename():
    assert HONEST_PROXY_NOTE == "整段代理，不是全精度成片"
    assert DELIVERABLE_SUFFIX == "_ACES2065-1_proxy"
    assert DELIVERABLE_DIR_SUFFIX == "_ACES2065-1_proxy"
    assert "proxy" in DELIVERABLE_SUFFIX
    assert "_proxy" in DELIVERABLE_SUFFIX
    assert "acescct" not in DELIVERABLE_SUFFIX.lower()
    assert deliverable_name("clip.mov") == "clip_ACES2065-1_proxy/frame_000000.exr"
    assert sequence_frame_name(1) == "frame_000001.exr"
    assert "_proxy" in deliverable_name("clip.mov")
    status = processed_status_text(2, 1)
    assert HONEST_PROXY_NOTE in status
    assert "整段代理，不是全精度成片" in status
    assert "预览·非成片" in status
    assert "已实现（未验证）" in status
    assert "2 条已处理" in status
    _assert_chengpian_not_a_deliverable_claim(status)
    assert HONEST_PROXY_NOTE in PROCESSED_STATUS_TEMPLATE
    assert HONEST_PROXY_NOTE in FOLDER_PICKER_MESSAGE
    assert "整段代理，不是全精度成片" in FOLDER_PICKER_MESSAGE
    assert "ACES2065-1" in FOLDER_PICKER_MESSAGE
    assert "ACEScct" not in FOLDER_PICKER_MESSAGE
    assert HONEST_PROXY_NOTE in PROCESS_BUTTON_HELP
    assert "不是 ACEScct" in PROCESS_BUTTON_HELP
    clip = _read(CLIP)
    content = _read(CONTENT)
    exporter = _read(SWIFT_ROOT / "LogBridge/LogBridge/Export/ResolveExporter.swift")
    assert FOLDER_PICKER_MESSAGE in clip
    assert processed_status_text(0, 0).replace("0 条已处理 / 0 条已跳过", "") in clip or HONEST_PROXY_NOTE in clip
    assert HONEST_PROXY_NOTE in content
    assert "_ACES2065-1_proxy" in exporter
    assert "frame_%06d.exr" in exporter
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "ACCEPTANCE.md").read_text(encoding="utf-8")
    assert HONEST_PROXY_NOTE in readme
    assert HONEST_PROXY_NOTE in acceptance
    assert "_ACES2065-1_proxy/frame_000000.exr" in readme
    _assert_chengpian_not_a_deliverable_claim(readme)
    _assert_chengpian_not_a_deliverable_claim(acceptance)
    _assert_chengpian_not_a_deliverable_claim(clip)
    _assert_chengpian_not_a_deliverable_claim(content)


def test_unlocked_never_writes_sequence(tmp_path: Path):
    clips = [
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
        BatchClip("empty.mov"),
        BatchClip("stub.mov", idt="future", is_stub=True),
    ]
    stack = np.stack([_slog3_grey(), _slog3_grey()], axis=0)
    frames = {c.name: stack for c in clips}
    report = process_locked_writes(clips, tmp_path, frames=frames)
    assert report.processed_count == 0
    assert report.written == ()
    assert report.skipped_count == 3
    assert list(tmp_path.glob("**/*.exr")) == []
    assert list(tmp_path.glob("*" + DELIVERABLE_DIR_SUFFIX)) == []


def test_locked_writes_more_than_one_frame(tmp_path: Path):
    clips = [
        BatchClip("locked.mov", idt="sony_slog3_sgamut3"),
        BatchClip("pending.mov", detected_curve="S-Log3", needs_user_picker=True),
    ]
    frame_a = _slog3_grey()
    frame_b = np.full((2, 2, 3), float(linear_to_slog3(0.09)), dtype=np.float64)
    report = process_locked_writes(
        clips,
        tmp_path,
        frames={"locked.mov": [frame_a, frame_b], "pending.mov": [frame_a, frame_b]},
    )
    assert report.processed_count == 1
    assert report.written[0].frame_count == 2
    seq = tmp_path / deliverable_dir_name("locked.mov")
    assert seq.is_dir()
    assert (seq / sequence_frame_name(0)).is_file()
    assert (seq / sequence_frame_name(1)).is_file()
    assert not (seq / sequence_frame_name(2)).exists()
    rgb0 = read_rgb_exr(seq / sequence_frame_name(0))
    rgb1 = read_rgb_exr(seq / sequence_frame_name(1))
    np.testing.assert_allclose(rgb0[0, 0], 0.18, atol=5e-3)
    assert not np.allclose(rgb0, rgb1, atol=1e-3)
    assert not (tmp_path / deliverable_dir_name("pending.mov")).exists()
    assert "_proxy" in seq.name
    assert HONEST_PROXY_NOTE in report.processed_status_text
    assert "整段代理，不是全精度成片" in report.processed_status_text
    _assert_chengpian_not_a_deliverable_claim(report.processed_status_text)
    assert list(tmp_path.glob("**/*.mov")) == []
    assert list(tmp_path.glob("**/*.mp4")) == []
