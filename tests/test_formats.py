"""Container / codec policy. No color numbers. Never 全格式已支持."""

from pathlib import Path

from color.formats import (
    ACCEPT,
    REFUSE,
    TRY,
    classify,
    empty_metadata_note,
    NOTE_ARRI_MXF,
    NOTE_CAMERA_RAW,
    NOTE_UNKNOWN_CODEC,
)
from color.batch import (
    DECODE_FAILED_CHIP,
    GENERIC_PARSE_FAILED,
    MISSING_YCBCR_TAGS_CHIP,
    MISSING_YCBCR_TAGS_CHIP_UI,
    user_facing_failure_note,
    short_export_chip,
)

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "macos/LogBridge/LogBridge/Preview/PreviewEngine.swift"
CLIP = ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift"
MEDIA = ROOT / "macos/LogBridge/LogBridge/Models/MediaFormat.swift"
DETECTOR = ROOT / "macos/LogBridge/LogBridge/Detection/ClipDetector.swift"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_mov_mp4_prores_h264_hevc_accept():
    assert classify("A.mov").action == ACCEPT
    assert classify("A.mp4", "avc1").action == ACCEPT
    assert classify("A.m4v", "hvc1").action == ACCEPT
    assert classify("A.mov", "apch").action == ACCEPT
    assert classify("A.mov", "ap4x").action == ACCEPT
    assert classify("A.mp4", "hevc").action == ACCEPT


def test_stills_tiff_dpx_exr_accept():
    for name in ("plate.tif", "plate.tiff", "plate.dpx", "plate.exr"):
        d = classify(name)
        assert d.action == ACCEPT
        assert d.kind == "still"
        assert "ImageIO" in d.note


def test_stills_preview_and_write_skip_ycbcr_unpack():
    """TIFF / DPX / EXR are already RGB. ImageIO only. #31 unpack is movies."""
    engine = _read(ENGINE)
    media = _read(MEDIA)
    assert 'stillExt: Set<String> = ["tif", "tiff", "dpx", "exr"]' in media
    assert "静帧" in media
    assert "ImageIO" in media
    down = engine.split("func decodeDownscaled")[1].split(
        "return try decodeMovieVideoToolbox"
    )[0]
    assert "decodeStillImageIO" in down
    assert "requireSourceYCbCrUnpack" not in down
    still = engine.split("func decodeStillImageIO")[1].split("enum PreviewColor")[0]
    assert "Already RGB" in still or "already RGB" in engine
    assert "requireSourceYCbCrUnpack" not in still
    assert "CGImageSourceCreateThumbnailAtIndex" in still
    full = engine.split("func decodeStillFullImageIO")[1].split(
        "/// Preview stills thumbnail"
    )[0]
    assert "CGImageSourceCreateImageAtIndex" in full
    assert "Thumbnail" not in full
    assert "maxLongEdge" not in full
    write_stills = engine.split("func decodeAllSourceFrames")[1].split(
        "func decodeFirstSourceRGB"
    )[0]
    assert "decodeStillFullImageIO" in write_stills
    assert "decodeStillImageIO(" not in write_stills


def test_arri_mxf_refused():
    d = classify("A001C001.mxf", "ARRIRAW")
    assert d.action == REFUSE
    assert d.note == "ARRI MXF：暂不支持，请导出 MOV ProRes 再拖入"


def test_mxf_known_codec_is_try_not_claim():
    d = classify("clip.mxf", "apcn")
    assert d.action == TRY
    assert "ARRI MXF" in d.note
    d2 = classify("clip.mxf")
    assert d2.action == TRY


NOTE_RAW = "R3D / BRAW：暂不支持，请在相机软件转 ProRes / EXR"
NOTE_ARRI = "ARRI MXF：暂不支持，请导出 MOV ProRes 再拖入"


def test_refused_containers():
    for name in ("clip.r3d", "clip.braw", "clip.crm", "clip.dng", "clip.nev", "clip.xocn"):
        d = classify(name)
        assert d.action == REFUSE, name
        assert d.note == NOTE_RAW
    for name in ("clip.ari", "clip.arx"):
        d = classify(name)
        assert d.action == REFUSE, name
        assert d.note == NOTE_RAW
    for name, token in (("clip.avi", "AVI"), ("clip.mkv", "MKV")):
        d = classify(name)
        assert d.action == REFUSE, name
        assert token in d.note


def test_crm_xocn_nraw_prores_raw_same_r3d_copy():
    for path, codec in (
        ("clip.crm", None),
        ("clip.mxf", "xocn"),
        ("clip.mov", "nraw"),
        ("clip.mov", "aprn"),
        ("clip.mov", "ProRes RAW"),
        ("clip.mov", "aprh"),
    ):
        d = classify(path, codec)
        assert d.action == REFUSE, (path, codec)
        assert d.note == NOTE_RAW


def test_unknown_codec_in_mov_refused():
    d = classify("weird.mov", "r210")
    assert d.action == REFUSE
    assert d.note == "这个编码不接。能试的是 ProRes / H.264 / HEVC。"
    assert "R3D" not in d.note
    assert "BRAW" not in d.note


def test_empty_metadata_prompts_paired_idt():
    note = empty_metadata_note()
    assert note == "先选择 Log 与色域"
    assert "5600" not in note


def test_never_claim_all_formats():
    blob = (
        _read(ROOT / "README.md")
        + _read(ROOT / "ACCEPTANCE.md")
        + _read(MEDIA)
        + _read(ENGINE)
        + _read(CLIP)
    )
    # Phrase is named so reviewers can grep. Only allowed as a prohibition.
    for i, line in enumerate(blob.splitlines()):
        if "全格式已支持" in line:
            assert any(tok in line for tok in ("不写", "Not ", "never", "Never", "Do **not**", "Claiming")), line
    assert "ARRI MXF" in blob
    assert "不接" in blob


def test_swift_probe_and_decode_locks():
    media = _read(MEDIA)
    engine = _read(ENGINE)
    clip = _read(CLIP)
    detector = _read(DETECTOR)
    assert "enum MediaFormat" in media
    assert "ARRI MXF：暂不支持，请导出 MOV ProRes 再拖入" in media
    assert "R3D / BRAW：暂不支持，请在相机软件转 ProRes / EXR" in media
    assert "aprn" in media
    assert "这个编码不接。能试的是 ProRes / H.264 / HEVC。" in media
    assert "ImageIO" in media
    assert "AVAssetReader" in engine
    assert "YpCbCr" in engine
    decode = engine.split("decodeMovieVideoToolbox")[1].split("decodeStillImageIO")[0]
    assert "copyCGImage(" not in decode
    assert "Never copyCGImage" in decode or "no copyCGImage" in decode
    assert "AVVideoColorPropertiesKey:" not in engine
    assert "Never set AVVideoColorPropertiesKey" in engine
    assert "MediaFormat.probe" in clip
    assert "lastImportNote" in clip
    assert "读不到元数据，先选择 Log 与色域" in detector
    assert "D-Log M" in detector
    assert "Apple Log 2" in detector
    down = engine.split("func decodeDownscaled")[1].split(
        "return try decodeMovieVideoToolbox"
    )[0]
    assert "decision == .refuse" in down
    assert "probe.note" in down
    assert "return nil" not in down.split("if probe.decision == .refuse")[1].split("if probe.kind")[0]


def _swift_ui() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "macos").rglob("*.swift")
    )


def _python_ui() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "color").glob("*.py")
    )


def test_failure_notes_name_the_class_not_bare_parse_failed():
    """Detect / IDT / decode / format failures name the class.

    「解析失败」 is not the only (or any) user-facing string for these paths.
    R3D / BRAW keep the existing refuse note.
    """
    assert GENERIC_PARSE_FAILED == "解析失败"
    assert DECODE_FAILED_CHIP == "解码失败"
    assert NOTE_CAMERA_RAW == "R3D / BRAW：暂不支持，请在相机软件转 ProRes / EXR"
    assert NOTE_ARRI_MXF == "ARRI MXF：暂不支持，请导出 MOV ProRes 再拖入"
    assert NOTE_UNKNOWN_CODEC == "这个编码不接。能试的是 ProRes / H.264 / HEVC。"
    assert empty_metadata_note() == "先选择 Log 与色域"
    assert MISSING_YCBCR_TAGS_CHIP == "无法读取片源 Y′CbCr 矩阵/范围，未写出"
    assert MISSING_YCBCR_TAGS_CHIP_UI == "读不出片源色彩标签，没法写出"

    assert classify("clip.r3d").note == NOTE_CAMERA_RAW
    assert classify("clip.braw").note == NOTE_CAMERA_RAW
    assert classify("A001C001.mxf", "ARRIRAW").note == NOTE_ARRI_MXF
    assert classify("weird.mov", "r210").note == NOTE_UNKNOWN_CODEC

    assert user_facing_failure_note("decode/grade failed") == DECODE_FAILED_CHIP
    assert user_facing_failure_note(GENERIC_PARSE_FAILED) == DECODE_FAILED_CHIP
    assert user_facing_failure_note("Could not decode a preview frame") == DECODE_FAILED_CHIP
    assert user_facing_failure_note(MISSING_YCBCR_TAGS_CHIP) == MISSING_YCBCR_TAGS_CHIP
    assert user_facing_failure_note(NOTE_CAMERA_RAW) == NOTE_CAMERA_RAW
    assert user_facing_failure_note(NOTE_ARRI_MXF) == NOTE_ARRI_MXF
    assert user_facing_failure_note(NOTE_UNKNOWN_CODEC) == NOTE_UNKNOWN_CODEC
    assert user_facing_failure_note("读不到元数据，先选择 Log 与色域") == (
        "读不到元数据，先选择 Log 与色域"
    )
    assert user_facing_failure_note(empty_metadata_note()) == empty_metadata_note()
    assert user_facing_failure_note(DECODE_FAILED_CHIP) == DECODE_FAILED_CHIP
    assert user_facing_failure_note(GENERIC_PARSE_FAILED) != GENERIC_PARSE_FAILED

    assert short_export_chip(NOTE_CAMERA_RAW) == NOTE_CAMERA_RAW
    assert short_export_chip(NOTE_ARRI_MXF) == NOTE_ARRI_MXF
    assert short_export_chip(NOTE_UNKNOWN_CODEC) == NOTE_UNKNOWN_CODEC
    assert short_export_chip(DECODE_FAILED_CHIP) == DECODE_FAILED_CHIP
    assert short_export_chip(MISSING_YCBCR_TAGS_CHIP) == MISSING_YCBCR_TAGS_CHIP
    assert short_export_chip(GENERIC_PARSE_FAILED) == DECODE_FAILED_CHIP
    assert short_export_chip(GENERIC_PARSE_FAILED) != GENERIC_PARSE_FAILED
    from color.batch import EMPTY_RGB_CHIP, REASON_PICK_PAIRED_IDT

    assert short_export_chip("empty RGB buffer") == EMPTY_RGB_CHIP
    assert short_export_chip(EMPTY_RGB_CHIP) == EMPTY_RGB_CHIP
    assert short_export_chip("no IDT") == REASON_PICK_PAIRED_IDT
    assert user_facing_failure_note("empty RGB buffer") == EMPTY_RGB_CHIP
    assert user_facing_failure_note("no IDT") == REASON_PICK_PAIRED_IDT

    swift = _swift_ui()
    python = _python_ui()
    engine = _read(ENGINE)
    clip = _read(CLIP)
    detector = _read(DETECTOR)
    media = _read(MEDIA)

    assert 'NSLocalizedDescriptionKey: "decode/grade failed"' not in swift
    assert "decode/grade failed" not in swift
    assert "Export failed" not in clip
    assert "No clip selected" not in clip
    assert "NSLocalizedDescriptionKey: Self.decodeFailedChip" in engine
    assert "NSLocalizedDescriptionKey: Self.decodeFailedChip" in clip
    export_seq = engine.split("func exportGradedAP0Sequence")[1].split(
        "func decodeAllSourceFrames"
    )[0]
    assert "Self.decodeFailedChip" in export_seq
    export_exr = clip.split("func exportLockedEXR")[1].split(
        "func cancelLockedDeliverables"
    )[0]
    assert "Self.decodeFailedChip" in export_exr
    assert ": decodeFailedChip" not in export_seq.replace("Self.decodeFailedChip", "")
    assert ": decodeFailedChip" not in export_exr.replace("Self.decodeFailedChip", "")
    assert "userFacingFailureNote" in engine
    assert "preservedFailureNote" in clip
    assert "decodeFailedChip" in clip.split("static func shortExportChip")[1]
    assert "noteCameraRaw" in clip.split("static func preservedFailureNote")[1]
    assert "noteARRIMxf" in clip.split("static func preservedFailureNote")[1]
    assert NOTE_CAMERA_RAW in media
    assert NOTE_ARRI_MXF in media
    assert NOTE_UNKNOWN_CODEC in media
    assert NOTE_CAMERA_RAW in clip or NOTE_CAMERA_RAW in media
    assert "读不到元数据，先选择 Log 与色域" in detector
    assert DECODE_FAILED_CHIP in engine
    assert DECODE_FAILED_CHIP in clip
    assert MISSING_YCBCR_TAGS_CHIP in engine
    assert f'static let missingYCbCrTagsChip = "{MISSING_YCBCR_TAGS_CHIP_UI}"' in engine
    assert f'static let missingYCbCrTagsChip = "{MISSING_YCBCR_TAGS_CHIP_UI}"' in clip
    assert "probe.note" in engine.split("func decodeDownscaled")[1].split(
        "func decodeMovieVideoToolbox"
    )[0]
    movie = engine.split("func decodeMovieVideoToolbox")[1].split(
        "func readFirstYpCbCrFrame"
    )[0]
    assert "decodeFailedChip" in movie
    assert "return nil" not in movie
    build = engine.split("private func build(")[1].split("private static func gradeKey")[0]
    assert "userFacingFailureNote" in build
    assert "localizedDescription" not in build
    import_fn = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert "probe.note" in import_fn
    assert NOTE_CAMERA_RAW.split("：")[0] in media
    assert GENERIC_PARSE_FAILED not in import_fn
    assert GENERIC_PARSE_FAILED not in build

    for blob in (swift, python):
        assert NOTE_CAMERA_RAW in blob
        assert DECODE_FAILED_CHIP in blob
        assert "读不到元数据" in blob or "先选择 Log 与色域" in blob
        cleaned = blob
        for tok in (
            f'GENERIC_PARSE_FAILED = "{GENERIC_PARSE_FAILED}"',
            f'contains("{GENERIC_PARSE_FAILED}")',
            "error == GENERIC_PARSE_FAILED",
        ):
            cleaned = cleaned.replace(tok, "")
        assert f'"{GENERIC_PARSE_FAILED}"' not in cleaned
