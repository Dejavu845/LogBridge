"""Write-path perf lock: long locked-clip EXR reads the movie sequentially."""

from pathlib import Path

from color.batch import DELIVERABLE_DIR_SUFFIX, HONEST_PROXY_NOTE

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "macos/LogBridge/LogBridge/Preview/PreviewEngine.swift"
CLIP = ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift"
EXPORTER = ROOT / "macos/LogBridge/LogBridge/Export/ResolveExporter.swift"
SWIFT_ROOT = ROOT / "macos"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _all_swift() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SWIFT_ROOT.rglob("*.swift"))


def _assert_no_seek_per_frame(blob: str) -> None:
    """Export decode must not random-access or step time by duration."""
    assert "copyCGImage(" not in blob
    assert "AVAssetImageGenerator" not in blob
    assert "requestedTime" not in blob
    assert "seek(" not in blob
    assert "CMTimeMultiply" not in blob
    assert "CMTimeAdd" not in blob
    assert "copyCGImagesAsynchronously" not in blob
    assert "generateCGImagesAsynchronously" not in blob
    assert "copyCGImage(at:" not in blob


def test_export_decode_is_sequential_no_seek_per_frame():
    """#19/#34 write already walks copyNextSampleBuffer. Lock: no seek-per-frame."""
    engine = _read(ENGINE)
    clip = _read(CLIP)
    exporter = _read(EXPORTER)
    swift = _all_swift()

    export_seq = engine.split("func exportGradedAP0Sequence")[1].split(
        "func decodeAllSourceFrames"
    )[0]
    decode_all = engine.split("func decodeAllSourceFrames")[1].split(
        "func decodeFirstSourceRGB"
    )[0]
    movie = engine.split("func decodeMovieAllFrames")[1].split(
        "func readAllYpCbCrFrames"
    )[0]
    read_all = engine.split("func readAllYpCbCrFrames")[1].split(
        "func readFirstYpCbCrRGB"
    )[0]
    export_body = clip.split("func exportLockedEXR")[1].split(
        "func cancelLockedDeliverables"
    )[0]

    assert "while let sample = output.copyNextSampleBuffer()" in read_all
    assert "AVAssetReader" in read_all
    assert "startReading" in read_all
    assert read_all.index("startReading") < read_all.index("copyNextSampleBuffer")
    assert "decodeMovieAllFrames" in decode_all
    assert "decodeAllSourceFrames" in export_seq
    assert "readAllYpCbCrFrames" in movie
    assert "exportGradedAP0Sequence" in export_body
    assert "exportGradedAP0(" not in export_body
    assert "Sequential ``copyNextSampleBuffer`` — do not seek randomly." in engine

    for blob in (export_seq, decode_all, movie, read_all, export_body):
        _assert_no_seek_per_frame(blob)
        assert "beginPreviewRequest" not in blob
        assert "isCurrentPreview" not in blob
        assert "retainPreviewCaches" not in blob
        assert "refreshODT" not in blob
        assert "decodeMovieVideoToolbox" not in blob
        assert "decodeDownscaled" not in blob

    assert "AVAssetImageGenerator" not in swift
    assert "copyCGImage(" not in swift
    assert "requestedTime" not in engine
    assert "AVAssetImageGenerator" not in engine

    assert DELIVERABLE_DIR_SUFFIX == "_ACES2065-1_proxy"
    assert "_ACES2065-1_proxy" in exporter
    assert "_proxy" in DELIVERABLE_DIR_SUFFIX
    assert HONEST_PROXY_NOTE == "整段代理，不是全精度成片"
    assert HONEST_PROXY_NOTE in engine


def test_docs_name_sequential_write_no_seek():
    """Reviewers grep docs: write is sequential, still 代理."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "ACCEPTANCE.md").read_text(encoding="utf-8")
    blob = readme + "\n" + acceptance
    assert "copyNextSampleBuffer" in blob
    assert "seek" in blob.lower()
    assert "整段代理，不是全精度成片" in blob
    assert "_ACES2065-1_proxy/frame_000000.exr" in blob
    assert "AVAssetImageGenerator" in blob or "copyCGImage" in blob
