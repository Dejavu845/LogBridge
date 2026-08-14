"""Detection order: metadata -> filename/model -> user picker.

Never trust QuickTime nclc. Never default S-Log3 to S-Gamut3.Cine.
"""

from color.detect import (
    SLOG3_PAIRS,
    SLOG3_VENICE_PAIRS,
    can_one_click_process,
    can_one_click_process_all,
    detect_clip,
    detect_from_filename,
    detect_from_metadata,
    picker_labels,
    picker_pairs,
    picker_pairs_for_detection,
)
from color.gamuts import VENICE_IDTS as GAMUT_VENICE


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


def test_venice_filename_with_sgamut3_is_venice_idt():
    d = detect_from_filename("A001_Venice_SLog3_SGamut3.mov")
    assert d.idt_id == "sony_slog3_sgamut3_venice"
    assert d.needs_user_picker is False


def test_venice_model_alone_does_not_default_gamut():
    d = detect_clip("plain.mov", model="Sony VENICE 2")
    assert d.idt_id is None
    assert d.needs_user_picker
    assert d.curve == "slog3"


def test_slog3_without_venice_is_not_venice():
    d = detect_from_filename("A001_SLog3_SGamut3.mov")
    assert d.idt_id == "sony_slog3_sgamut3"

def test_picker_slog3_without_venice_is_two_paired_idts():
    pairs = picker_pairs(curve="slog3", venice_detected=False, needs_picker=True)
    assert pairs == list(SLOG3_PAIRS)
    assert "sony_slog3_sgamut3cine_venice" not in pairs
    labels = [lab for _, lab in picker_labels(pairs)]
    assert labels == ["S-Log3 + S-Gamut3", "S-Log3 + S-Gamut3.Cine"]
    # Never a silent Cine default: both pairs offered, Cine is not first.
    assert pairs[0] == "sony_slog3_sgamut3"


def test_picker_slog3_venice_only_if_detected():
    pairs = picker_pairs(curve="slog3", venice_detected=True, needs_picker=True)
    assert pairs == list(SLOG3_VENICE_PAIRS)
    assert set(pairs) <= set(GAMUT_VENICE)
    labels = [lab for _, lab in picker_labels(pairs)]
    assert labels == [
        "S-Log3 + S-Gamut3 (Venice)",
        "S-Log3 + S-Gamut3.Cine (Venice)",
    ]


def test_picker_unresolved_excludes_venice():
    pairs = picker_pairs(curve=None, venice_detected=False, needs_picker=True)
    assert "sony_slog3_sgamut3" in pairs
    assert "sony_slog3_sgamut3cine" in pairs
    assert not (set(pairs) & set(GAMUT_VENICE))
    # Labels are paired, not split curve/gamut.
    for _, lab in picker_labels(pairs):
        assert " + " in lab


def test_picker_unresolved_includes_venice_only_when_detected():
    pairs = picker_pairs(curve=None, venice_detected=True, needs_picker=True)
    assert "sony_slog3_sgamut3_venice" in pairs
    assert "sony_slog3_sgamut3cine_venice" in pairs


def test_one_click_blocked_until_pair_chosen():
    pending = detect_from_filename("A001_SLog3_take.mov")
    assert pending.needs_user_picker
    assert pending.idt_id is None
    assert can_one_click_process(pending) is False
    locked = detect_from_filename("A001_SLog3_SGamut3.mov")
    assert can_one_click_process(locked) is True
    assert can_one_click_process_all([pending, locked]) is False
    assert can_one_click_process_all([locked]) is True


def test_filename_venice_slog3_without_gamut_offers_venice_pairs():
    d = detect_from_filename("A001_Venice_SLog3_take.mov")
    assert d.needs_user_picker
    assert d.venice_detected
    assert d.idt_id is None
    assert can_one_click_process(d) is False
    pairs = picker_pairs_for_detection(d)
    assert pairs == list(SLOG3_VENICE_PAIRS)


def test_filename_slog3_without_venice_does_not_offer_venice_pairs():
    d = detect_from_filename("A001_SLog3_take.mov")
    assert d.venice_detected is False
    pairs = picker_pairs_for_detection(d)
    assert pairs == list(SLOG3_PAIRS)
    assert not (set(pairs) & set(GAMUT_VENICE))


def test_metadata_slog3_venice_body_without_gamut():
    d = detect_from_metadata(
        {
            "sony_acquisition_gamma": "S-Log3",
            "sony_camera_model": "VENICE 2",
        }
    )
    assert d.needs_user_picker
    assert d.venice_detected
    assert d.gamut is None
    assert can_one_click_process(d) is False
    assert picker_pairs_for_detection(d) == list(SLOG3_VENICE_PAIRS)


def test_user_pick_locks_pair_and_unblocks_process():
    pending = detect_clip("A001_SLog3_take.mov")
    assert can_one_click_process(pending) is False
    chosen = detect_clip("A001_SLog3_take.mov", user_idt="sony_slog3_sgamut3")
    assert chosen.idt_id == "sony_slog3_sgamut3"
    assert chosen.source == "user"
    assert can_one_click_process(chosen) is True
