"""Fixed-pipeline and gamut-matrix tests."""

import numpy as np
import pytest

from color.curves import linear_to_logc4, linear_to_nlog, linear_to_slog3
from color.gamuts import (
    ARRI_AWG4_TO_XYZ,
    IDT_PAIRS,
    PANASONIC_VGAMUT_TO_XYZ,
    rgb_to_xyz_matrix,
)
from color.pipeline import apply_idt, process_to_rec709
from color.working_space import (
    DI_18_PERCENT,
    acescct_decode,
    acescct_encode,
    davinci_intermediate_decode,
    davinci_intermediate_encode,
)


def test_awg4_matrix_matches_arri_published():
    computed = rgb_to_xyz_matrix("AWG4")
    np.testing.assert_allclose(computed, ARRI_AWG4_TO_XYZ, atol=2e-4)


def test_vgamut_matrix_near_panasonic_published():
    computed = rgb_to_xyz_matrix("VGamut")
    np.testing.assert_allclose(computed, PANASONIC_VGAMUT_TO_XYZ, atol=5e-3)


def test_idt_pairs_are_locked():
    assert IDT_PAIRS["sony_slog3_sgamut3"] == ("slog3", "SGamut3")
    assert IDT_PAIRS["sony_slog3_sgamut3cine"] == ("slog3", "SGamut3Cine")
    # No implicit Cine default in the pair table.
    assert "SGamut3Cine" not in IDT_PAIRS["sony_slog3_sgamut3"]


def test_nlog_idt_uses_10bit_codes():
    cv = np.full(3, float(linear_to_nlog(0.18)))
    lin = apply_idt(cv, "nikon_nlog_bt2020")
    np.testing.assert_allclose(lin, 0.18, rtol=1e-10)


def test_logc4_idt_18_percent():
    log = np.full(3, float(linear_to_logc4(0.18)))
    lin = apply_idt(log, "arri_logc4_awg4")
    np.testing.assert_allclose(lin, 0.18, rtol=1e-9)


def test_process_to_rec709_neutral_grey_positive():
    log = np.full(3, float(linear_to_slog3(0.18)))
    out = process_to_rec709(log, "sony_slog3_sgamut3", apply_wb=False)
    assert np.all(out > 0.0)
    # Neutral stays neutral through D65->D65.
    assert out[0] == pytest.approx(out[1], rel=1e-5)
    assert out[1] == pytest.approx(out[2], rel=1e-5)


def test_wb_toggle_changes_tungsten_not_d65():
    log = np.array(
        [
            float(linear_to_logc4(0.10)),
            float(linear_to_logc4(0.18)),
            float(linear_to_logc4(0.30)),
        ]
    )
    a = process_to_rec709(log, "arri_logc4_awg4", apply_wb=True, cct=6504.0)
    b = process_to_rec709(log, "arri_logc4_awg4", apply_wb=False)
    np.testing.assert_allclose(a, b, atol=2e-3)
    c = process_to_rec709(log, "arri_logc4_awg4", apply_wb=True, cct=3200.0)
    assert not np.allclose(c, b, atol=1e-3)


def test_davinci_intermediate_18_percent():
    enc = davinci_intermediate_encode(0.18)
    assert enc == pytest.approx(DI_18_PERCENT, abs=5e-6)
    assert davinci_intermediate_decode(enc) == pytest.approx(0.18, rel=1e-6)


def test_acescct_roundtrip():
    lin = np.array([0.001, 0.0078125, 0.18, 1.0, 16.0])
    np.testing.assert_allclose(
        acescct_decode(acescct_encode(lin)), lin, rtol=1e-10, atol=1e-12
    )
