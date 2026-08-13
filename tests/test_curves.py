"""Log curve unit tests. Python is the source of truth."""

import numpy as np
import pytest

from color import curves
from color.stubs import (
    apple_log_to_linear,
    clog2_to_linear,
    clog3_to_linear,
    dlog_to_linear,
)


def _roundtrip(encode, decode, lin, rtol=1e-10, atol=1e-12):
    log = encode(lin)
    back = decode(log)
    np.testing.assert_allclose(back, lin, rtol=rtol, atol=atol)


class TestLogC4:
    def test_18_percent_grey(self):
        enc = curves.linear_to_logc4(0.18)
        assert enc == pytest.approx(0.2784, abs=5e-5)
        assert curves.logc4_to_linear(0.2784) == pytest.approx(0.18, rel=1e-3)

    def test_zero_is_slightly_negative_linear(self):
        # ARRI table: LogC4 0.0 -> relative scene linear ~-0.018
        lin = float(curves.logc4_to_linear(0.0))
        assert lin < 0.0
        # Curve-only (relative scene linear at LogC4 0). ARRI table -0.0181 is
        # after AWG4→ACES, not the transfer function itself.
        assert lin == pytest.approx(-0.018057, rel=1e-4)

    def test_negative_linear_extension(self):
        x = np.array([-0.05, -0.01, 0.0, 0.1, 0.2784, 0.5, 1.0])
        _roundtrip(curves.linear_to_logc4, curves.logc4_to_linear, curves.logc4_to_linear(x))

    def test_roundtrip_domain(self):
        lin = np.array([0.0, 0.001, 0.18, 1.0, 10.0, 100.0])
        _roundtrip(curves.linear_to_logc4, curves.logc4_to_linear, lin, rtol=1e-9)


class TestSLog3:
    def test_18_percent_grey(self):
        enc = curves.linear_to_slog3(0.18)
        assert enc == pytest.approx(420.0 / 1023.0, rel=1e-10)
        assert curves.slog3_to_linear(420.0 / 1023.0) == pytest.approx(0.18, rel=1e-10)

    def test_black_and_90_percent(self):
        assert curves.linear_to_slog3(0.0) == pytest.approx(95.0 / 1023.0, rel=1e-10)
        enc90 = curves.linear_to_slog3(0.90)
        # Sony table: 90% -> 10-bit 598
        assert enc90 * 1023.0 == pytest.approx(598.0, abs=0.6)

    def test_shadow_linear_segment(self):
        cut = 171.2102946929 / 1023.0
        # Just below the cut uses the official shadow segment, not the log.
        x = cut * 0.5
        lin = curves.slog3_to_linear(x)
        expected = (x * 1023.0 - 95.0) * 0.01125 / (171.2102946929 - 95.0)
        assert lin == pytest.approx(expected, rel=1e-12)

    def test_roundtrip(self):
        lin = np.array([0.0, 0.001, 0.01125, 0.18, 0.9, 5.0, 20.0])
        _roundtrip(curves.linear_to_slog3, curves.slog3_to_linear, lin, rtol=1e-10)


class TestVLog:
    def test_18_percent_grey(self):
        enc = curves.linear_to_vlog(0.18)
        assert enc == pytest.approx(433.0 / 1023.0, abs=5e-4)
        assert curves.vlog_to_linear(433.0 / 1023.0) == pytest.approx(0.18, rel=2e-3)

    def test_black_and_90(self):
        assert curves.linear_to_vlog(0.0) == pytest.approx(128.0 / 1023.0, abs=5e-4)
        assert curves.linear_to_vlog(0.90) * 1023.0 == pytest.approx(602.0, abs=1.0)

    def test_roundtrip(self):
        lin = np.array([0.0, 0.005, 0.009, 0.18, 0.9, 10.0])
        # Rounded cut1/cut2 are not bit-identical at 0.01; stay off the join.
        _roundtrip(curves.linear_to_vlog, curves.vlog_to_linear, lin, rtol=1e-9)


class TestFLog2:
    def test_a_is_not_flog1(self):
        # F-Log uses a=0.555556; F-Log2 uses a=5.555556. 18% must be ~400/1023.
        enc = curves.linear_to_flog2(0.18)
        assert enc == pytest.approx(400.0 / 1023.0, abs=5e-5)
        assert enc != pytest.approx(0.192, abs=0.01)

    def test_18_percent_grey(self):
        assert curves.flog2_to_linear(400.0 / 1023.0) == pytest.approx(0.18, rel=1e-4)

    def test_black(self):
        assert curves.linear_to_flog2(0.0) * 1023.0 == pytest.approx(95.0, abs=0.5)

    def test_roundtrip(self):
        lin = np.array([0.0, 0.0005, 0.000889, 0.18, 0.9, 16.0])
        _roundtrip(curves.linear_to_flog2, curves.flog2_to_linear, lin, rtol=1e-10)


class TestNLog:
    def test_x_is_10bit_code_not_normalized(self):
        # White paper x=372-ish is 18% grey. Treating 0.18 as x would be wrong.
        grey = curves.nlog_to_linear(curves.NLOG_18_PERCENT_10BIT)
        assert grey == pytest.approx(0.18, rel=1e-10)
        # If someone incorrectly passed 0-1, 0.18 is near black, not 18%.
        wrong = float(curves.nlog_to_linear(0.18))
        assert wrong < 0.0 or wrong < 0.01

    def test_do_not_divide_by_1023(self):
        # Dividing 372 by 1023 before the curve must not yield 0.18.
        divided = 372.0 / 1023.0
        assert curves.nlog_to_linear(divided) != pytest.approx(0.18, abs=0.05)
        assert curves.nlog_to_linear(372.0) == pytest.approx(0.18, abs=5e-3)

    def test_18_percent_near_documented_372(self):
        cv = float(curves.linear_to_nlog(0.18))
        assert cv == pytest.approx(372.0, abs=0.2)
        # Nikon technical guide: 18% grey ~ 10-bit 372 / IRE 35%.

    def test_inverse_uses_natural_log(self):
        lin = 1.0  # above 0.328 cut
        cv = curves.linear_to_nlog(lin)
        # x = 150*ln(y)+619
        assert float(cv) == pytest.approx(150.0 * np.log(1.0) + 619.0)

    def test_roundtrip(self):
        # Spec cuts x=452 and y=0.328 are not an exact inverse pair; stay off the join.
        lin = np.array([0.01, 0.18, 0.30, 0.5, 1.0, 4.0])
        _roundtrip(curves.linear_to_nlog, curves.nlog_to_linear, lin, rtol=1e-10)
        lin0 = float(curves.nlog_to_linear(0.0))
        assert float(curves.linear_to_nlog(lin0)) == pytest.approx(0.0, abs=1e-9)

    def test_normalized_wrapper_matches_10bit(self):
        cv = np.array([0.0, 95.0, 372.0, 452.0, 700.0, 1023.0])
        np.testing.assert_allclose(
            curves.nlog_normalized_to_linear(cv / 1023.0),
            curves.nlog_to_linear(cv),
        )


class TestLog3G10:
    def test_18_percent_is_one_third(self):
        enc = curves.linear_to_log3g10(0.18)
        assert enc == pytest.approx(1.0 / 3.0, abs=1e-6)
        assert curves.log3g10_to_linear(1.0 / 3.0) == pytest.approx(0.18, rel=1e-5)

    def test_white_paper_mapping_table(self):
        assert curves.linear_to_log3g10(-0.01) == pytest.approx(0.0, abs=1e-6)
        assert curves.linear_to_log3g10(0.0) == pytest.approx(0.091551, abs=5e-6)
        assert curves.linear_to_log3g10(1.0) == pytest.approx(0.493449, abs=5e-6)
        assert curves.linear_to_log3g10(184.322) == pytest.approx(1.0, abs=5e-5)

    def test_negative_extension(self):
        x = np.array([-0.05, -0.01, 0.0, 0.091551, 1.0 / 3.0, 1.0])
        _roundtrip(
            curves.linear_to_log3g10,
            curves.log3g10_to_linear,
            curves.log3g10_to_linear(x),
            rtol=1e-9,
        )

    def test_roundtrip(self):
        lin = np.array([-0.009, 0.0, 0.18, 1.0, 10.0, 184.32])
        _roundtrip(curves.linear_to_log3g10, curves.log3g10_to_linear, lin, rtol=1e-9)


class TestDispatch:
    def test_idt_names_cover_six_cameras_and_sony_two_gamuts(self):
        names = curves.IDT_NAMES
        assert any("LogC4" in n and "AWG4" in n for n in names)
        assert any("S-Gamut3" in n and "Cine" not in n for n in names)
        assert any("S-Gamut3.Cine" in n for n in names)
        assert any("V-Log" in n for n in names)
        assert any("F-Log2" in n for n in names)
        assert any("N-Log" in n for n in names)
        assert any("Log3G10" in n for n in names)

    def test_unknown_curve_raises(self):
        with pytest.raises(KeyError):
            curves.decode_log("bogus", 0.18)


class TestStubs:
    def test_clog2_refuses_invented_toe(self):
        with pytest.raises(NotImplementedError, match="CANON_CLOG2_to_LINEAR"):
            clog2_to_linear(0.18)

    def test_other_stubs(self):
        for fn in (clog3_to_linear, apple_log_to_linear, dlog_to_linear):
            with pytest.raises(NotImplementedError):
                fn(0.18)
