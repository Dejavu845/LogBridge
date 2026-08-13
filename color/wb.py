"""White balance in scene-linear: Bradford (default) or CAT02.

Given a source CCT (and optional green-magenta tint), build a CAT that
adapts that illuminant to D65. Apply only to scene-linear RGB.

6504 K on the CIE daylight locus is D65, so the CAT is ~identity.
3200 K (Planckian / tungsten) is not identity.
"""

from __future__ import annotations

import numpy as np

from .gamuts import D65_XY, rgb_to_xyz_matrix, xy_to_xyz, xyz_to_rgb_matrix

BRADFORD = np.array(
    [
        [0.8951, 0.2664, -0.1614],
        [-0.7502, 1.7135, 0.0367],
        [0.0389, -0.0685, 1.0296],
    ],
    dtype=np.float64,
)

CAT02 = np.array(
    [
        [0.7328, 0.4296, -0.1624],
        [-0.7036, 1.6975, 0.0061],
        [0.0030, 0.0136, 0.9834],
    ],
    dtype=np.float64,
)

D65_CCT = 6504.0


def _daylight_xy(cct: float) -> np.ndarray:
    """CIE D-series chromaticity (4000-25000 K)."""
    t = float(cct)
    if t <= 7000.0:
        xd = (
            0.244063
            + 0.09911e3 / t
            + 2.9678e6 / t**2
            - 4.6070e9 / t**3
        )
    else:
        xd = (
            0.237040
            + 0.24748e3 / t
            + 1.9018e6 / t**2
            - 2.0064e9 / t**3
        )
    yd = -3.0 * xd**2 + 2.870 * xd - 0.275
    return np.array([xd, yd], dtype=np.float64)


def _planckian_xy(cct: float) -> np.ndarray:
    """Kang 2002 approximation of the Planckian locus (xy)."""
    t = float(cct)
    inv = 1.0e3 / t
    inv2 = 1.0e6 / t**2
    inv3 = 1.0e9 / t**3
    if t < 4000.0:
        x = -0.2661239 * inv3 - 0.2343580 * inv2 + 0.8776956 * inv + 0.179910
    else:
        x = -3.0258469 * inv3 + 2.1070379 * inv2 + 0.2226347 * inv + 0.240390
    if t < 2222.0:
        y = -1.1063814 * x**3 - 1.34811020 * x**2 + 2.18555832 * x - 0.20219683
    elif t < 4000.0:
        y = -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867
    else:
        y = 3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483
    return np.array([x, y], dtype=np.float64)


def cct_to_xy(cct: float, tint: float = 0.0) -> np.ndarray:
    """Illuminant xy from CCT (kelvin) and optional green-magenta tint.

    Daylight locus is used at T >= 4000 K so that 6504 K is D65.
    Planckian locus is used below 4000 K (tungsten).

    ``tint`` is a CIE 1960 uv shift along the isotherm: positive is greener
    (higher v'). Units are 1e-3 in uv (similar to a mild CC gel).
    """
    if cct >= 4000.0:
        xy = _daylight_xy(cct)
    else:
        xy = _planckian_xy(cct)
    if tint == 0.0:
        return xy
    x, y = xy
    # CIE 1960 UCS.
    denom = -2.0 * x + 12.0 * y + 3.0
    u = 4.0 * x / denom
    v = 6.0 * y / denom
    # Isotherm is perpendicular to the locus; a +tint increases v (green).
    v = v + tint * 1.0e-3
    d = 2.0 * u - 8.0 * v + 4.0
    x = 1.5 * u / d * 2.0  # inverse UCS
    # Standard inverse: x = 3u / (2u - 8v + 4), y = 2v / (2u - 8v + 4)
    x = 3.0 * u / d
    y = 2.0 * v / d
    return np.array([x, y], dtype=np.float64)


def chromatic_adaptation_matrix(
    src_xy, dst_xy=D65_XY, method: str = "bradford"
) -> np.ndarray:
    """3x3 XYZ CAT taking src white to dst white."""
    m = BRADFORD if method == "bradford" else CAT02
    src_cone = m @ xy_to_xyz(src_xy)
    dst_cone = m @ xy_to_xyz(dst_xy)
    scale = np.diag(dst_cone / src_cone)
    return np.linalg.inv(m) @ scale @ m


def bradford_cat_matrix(src_xy, dst_xy=D65_XY) -> np.ndarray:
    return chromatic_adaptation_matrix(src_xy, dst_xy, method="bradford")


def white_balance_matrix(
    cct: float,
    tint: float = 0.0,
    rgb_space: str = "AP1",
    method: str = "bradford",
    dst_xy=D65_XY,
) -> np.ndarray:
    """Scene-linear RGB CAT: adapt ``cct`` (+tint) to ``dst_xy`` (default D65).

    Identity (within numerical tolerance) at 6504 K, tint 0 (CAT is identity; AP1 conjugation stays identity).
    """
    src_xy = cct_to_xy(cct, tint)
    cat = chromatic_adaptation_matrix(src_xy, dst_xy, method=method)
    to_xyz = rgb_to_xyz_matrix(rgb_space)
    to_rgb = xyz_to_rgb_matrix(rgb_space)
    return to_rgb @ cat @ to_xyz


def apply_white_balance(
    rgb,
    cct: float,
    tint: float = 0.0,
    rgb_space: str = "AP1",
    method: str = "bradford",
) -> np.ndarray:
    """Apply CCT+tint CAT to scene-linear RGB (..., 3)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    m = white_balance_matrix(cct, tint, rgb_space=rgb_space, method=method)
    return rgb @ m.T
