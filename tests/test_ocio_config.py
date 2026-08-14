"""OCIO config presence and IDT coverage. Full PyOpenColorIO is optional."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "ocio" / "config.ocio"


def test_config_exists():
    assert CONFIG.is_file()
    text = CONFIG.read_text(encoding="utf-8")
    assert "ocio_profile_version" in text


def test_roles_scene_linear_and_rec709():
    text = CONFIG.read_text(encoding="utf-8")
    assert "scene_linear:" in text
    assert "rec709:" in text or "color_picking:" in text


def test_six_idts_declared():
    text = CONFIG.read_text(encoding="utf-8")
    for name in (
        "ARRI LogC4 AWG4",
        "Sony S-Log3 S-Gamut3",
        "Sony S-Log3 S-Gamut3.Cine",
        "Panasonic V-Log V-Gamut",
        "Fujifilm F-Log2 BT.2020",
        "Nikon N-Log BT.2020",
        "RED Log3G10 REDWideGamutRGB",
    ):
        assert name in text


def test_sony_does_not_default_cine():
    text = CONFIG.read_text(encoding="utf-8")
    # Both gamuts exist as distinct colorspaces.
    assert "Sony S-Log3 S-Gamut3.Cine" in text
    assert "Sony S-Log3 S-Gamut3" in text
    # The non-Cine name must appear as its own colorspace, not only as a prefix.
    assert "name: Sony S-Log3 S-Gamut3\n" in text or 'name: "Sony S-Log3 S-Gamut3"' in text


def test_nlog_comment_about_10bit():
    text = CONFIG.read_text(encoding="utf-8")
    assert "1023" in text
    assert "N-Log" in text


def test_canon_stub_points_at_ocio_builtin():
    text = CONFIG.read_text(encoding="utf-8")
    assert "CURVE - CANON_CLOG2_to_LINEAR" in text


def test_supporting_luts_exist():
    luts = ROOT / "ocio" / "luts"
    expected = [
        "LogC4_to_lin.spi1d",
        "SLog3_to_lin.spi1d",
        "VLog_to_lin.spi1d",
        "FLog2_to_lin.spi1d",
        "NLog_to_lin.spi1d",
        "Log3G10_to_lin.spi1d",
    ]
    for name in expected:
        assert (luts / name).is_file(), name
