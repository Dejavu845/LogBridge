"""White-balance CAT tests. WB is scene-linear only."""

import numpy as np
import pytest

from color.gamuts import D65_XY, rgb_to_xyz_matrix
from color.wb import (
    apply_white_balance,
    bradford_cat_matrix,
    cct_to_xy,
    white_balance_matrix,
)


def test_6504k_is_d65():
    xy = cct_to_xy(6504.0)
    np.testing.assert_allclose(xy, D65_XY, atol=5e-4)


def test_6504k_bradford_is_identity():
    m = bradford_cat_matrix(cct_to_xy(6504.0), D65_XY)
    np.testing.assert_allclose(m, np.eye(3), atol=5e-3)


def test_6504k_rgb_matrix_is_identity_on_aces_working_space():
    m = white_balance_matrix(6504.0, tint=0.0, rgb_space="AP1")
    np.testing.assert_allclose(m, np.eye(3), atol=5e-3)
    rgb = np.array([0.18, 0.18, 0.18])
    out = apply_white_balance(rgb, 6504.0, rgb_space="AP1")
    np.testing.assert_allclose(out, rgb, atol=1e-3)


def test_3200k_is_not_identity():
    m = white_balance_matrix(3200.0, rgb_space="AP1")
    diff = np.linalg.norm(m - np.eye(3))
    assert diff > 0.05
    rgb = np.array([0.18, 0.18, 0.18])
    out = apply_white_balance(rgb, 3200.0, rgb_space="AP1")
    assert not np.allclose(out, rgb, atol=1e-3)


def test_cat02_also_identity_at_6504k():
    m = white_balance_matrix(6504.0, rgb_space="Rec709", method="cat02")
    np.testing.assert_allclose(m, np.eye(3), atol=5e-3)


def test_tint_shifts_off_locus():
    m0 = white_balance_matrix(5600.0, tint=0.0, rgb_space="AP1")
    mg = white_balance_matrix(5600.0, tint=5.0, rgb_space="AP1")
    assert not np.allclose(m0, mg, atol=1e-6)


def test_wb_is_linear_operator():
    """Doubling scene-linear RGB doubles the result (no log-domain WB)."""
    rgb = np.array([0.04, 0.08, 0.16])
    a = apply_white_balance(rgb, 3200.0, rgb_space="AWG4")
    b = apply_white_balance(2.0 * rgb, 3200.0, rgb_space="AWG4")
    np.testing.assert_allclose(b, 2.0 * a, rtol=1e-12)
