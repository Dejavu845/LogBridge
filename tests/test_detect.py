"""Detection order: metadata -> filename/model -> user picker.

Never trust QuickTime nclc. Never default S-Log3 to S-Gamut3.Cine.
"""

from color.detect import detect_clip, detect_from_filename, detect_from_metadata


def test_arri_mxf_metadata_wins():
    d = detect_clip(
        "clip.mov",
        metadata={"arri_mxf_color_space": "ARRI LogC4 / AWG4", "nclc": "1-1-1"},
        model="anything",
        user_idt="sony_slog3_sgamut3cine",
    )
    # Metadata wins over filename, model, user, and nclc.
    assert d.idt_id == "arri_logc4_awg4"
    assert d.source == "metadata"


def test_nclc_is_never_used_for_slog3_or_logc4():
    d = detect_clip(
        "unknown.mov",
        metadata={"nclc": "1-1-1", "quicktime_nclc": "S-Log3"},
    )
    assert d.idt_id is None
    assert d.needs_user_picker
    assert d.source == "unresolved"


def test_sony_acquisition_sgamut3_not_cine():
    d = detect_from_metadata(
        {
            "sony_acquisition_gamma": "S-Log3",
            "sony_acquisition_gamut": "S-Gamut3",
        }
    )
    assert d.idt_id == "sony_slog3_sgamut3"
    assert d.gamut == "SGamut3"


def test_sony_slog3_without_gamut_does_not_default_cine():
    d = detect_from_metadata({"sony_acquisition_gamma": "S-Log3"})
    assert d.curve == "slog3"
    assert d.gamut is None
    assert d.needs_user_picker
    assert "Cine" in d.note or "cine" in d.note.lower()


def test_filename_slog3_without_gamut_needs_picker():
    d = detect_from_filename("A001_SLog3_take.mov")
    assert d.curve == "slog3"
    assert d.gamut is None
    assert d.needs_user_picker


def test_filename_sgamut3_cine_is_explicit():
    d = detect_from_filename("A001_SLog3_SGamut3.Cine.mov")
    assert d.idt_id == "sony_slog3_sgamut3cine"


def test_filename_sgamut3_without_cine():
    d = detect_from_filename("A001_SLog3_SGamut3.mov")
    assert d.idt_id == "sony_slog3_sgamut3"


def test_red_rmd():
    d = detect_clip("clip.rmd", metadata={"red_rmd_gamma": "Log3G10", "red_rmd_colorspace": "REDWideGamutRGB"})
    assert d.idt_id == "red_log3g10_rwg"
    assert d.source == "metadata"


def test_user_picker_when_unresolved():
    d = detect_clip("plain.mov", user_idt="fujifilm_flog2_bt2020")
    assert d.idt_id == "fujifilm_flog2_bt2020"
    assert d.source == "user"


def test_model_hint_alexa35():
    d = detect_clip("plain.mxf", model="ARRI ALEXA 35")
    assert d.idt_id == "arri_logc4_awg4"
    assert d.source == "model"


def test_canon_metadata_is_stub_not_a_real_idt():
    d = detect_from_metadata({"canon_vendor_gamma": "C-Log2"})
    assert d.idt_id is None
    assert d.needs_user_picker
    assert "CANON_CLOG2" in d.note
