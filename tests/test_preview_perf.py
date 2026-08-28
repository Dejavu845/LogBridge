"""Preview perf locks: VT decode, Metal same matrices, scrub ODT-only."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "macos/LogBridge/LogBridge/Preview/PreviewEngine.swift"
CLIP = ROOT / "macos/LogBridge/LogBridge/Models/Clip.swift"
SOURCE = ROOT / "macos/LogBridge/LogBridge/Color/Rec709PreviewView.swift"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_vt_decode_not_709():
    engine = _read(ENGINE)
    assert "import VideoToolbox" in engine
    assert "decodeMovieVideoToolbox" in engine
    assert "do not let VT emit Rec.709" in engine or "No VT color convert to 709" in engine
    assert "AVAssetReader" in engine
    assert "YpCbCr" in engine
    assert "no 709 transfer" in engine
    decode = engine.split("decodeMovieVideoToolbox")[1].split("decodeStillImageIO")[0]
    assert "copyCGImage(" not in decode
    assert "Never copyCGImage" in decode or "no copyCGImage" in decode
    assert "MediaFormat.probe" in engine
    assert "AVVideoColorPropertiesKey:" not in engine
    assert "Never set AVVideoColorPropertiesKey" in engine


def test_metal_same_locked_matrices():
    engine = _read(ENGINE)
    assert "enum PreviewMetal" in engine
    assert "applyMatrix" in engine
    assert "0.018053968510807" in engine
    assert "1.09929682680944" in engine
    assert "No Core Image" in engine or "no Core Image" in engine.lower()
    assert "Display P3" in engine


def test_graded_cache_scrub_skips_idt():
    engine = _read(ENGINE)
    clip = _read(CLIP)
    assert "gradedCache" in engine
    assert "refreshODT" in engine
    assert "Scrub does not re-run IDT" in engine
    assert "func refreshODTOnly()" in clip
    assert "setODT" in clip
    assert "refreshODTOnly()" in clip


def test_source_not_tagged_709_extract_device_rgb():
    engine = _read(ENGINE)
    source = _read(SOURCE)
    assert "Device RGB" in engine
    assert "not Display P3" in engine
    assert "itur_709" in engine
    assert "Never `CGColorSpace.itur_709`" in source or "Never CGColorSpace.itur_709" in source


def test_preview_decode_stays_8bit_first_and_scrub_odt_only():
    """Preview may stay 8-bit. Write-path 10-bit float must not steal scrub caches."""
    engine = _read(ENGINE)
    preview = engine.split("func decodeMovieVideoToolbox")[1].split(
        "func readFirstYpCbCrFrame"
    )[0]
    eight_420 = "kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange"
    eight_422 = "kCVPixelFormatType_422YpCbCr8"
    ten = "kCVPixelFormatType_420YpCbCr10BiPlanarVideoRange"
    assert preview.index(eight_420) < preview.index(eight_422)
    assert preview.index(eight_422) < preview.index(ten)
    cached = engine.split("func cachedSource")[1].split("func cachedLinear")[0]
    assert "decodeDownscaled" in cached
    assert "extractRGB" in cached
    assert "maxLongEdge: Self.maxLongEdge" in cached
    assert "gradedCache" in engine
    assert "Scrub does not re-run IDT" in engine
    assert "rgbFloatFromLogPixelBuffer" not in cached
