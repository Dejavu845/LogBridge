"""Per-node .cube range, lattice size, chain vs combined preview, interpolation.

Every node cube samples the default [0, 1] lattice and writes no DOMAIN
or INPUT_RANGE header. ACEScct encode floors linear at 1e-10 (code about
0.0729). Exposure output may exceed 1. ACEScct 1.0 is linear 2**7.8 ≈ 223,
about 10.3 stops above 18% grey; the next cube clips that input to 1.0.

The neutral axis is r = g = b, uniform, several hundred points, on
0.15–0.50 (the ACEScct band that approaches the Rec.709 white point).
That gate is max absolute error. LogC4 18% grey stays a max gate.

Saturated and overexposed gates are mean and p99. Their max is printed
and not gated. On the Rec.709 node that tail comes from hard clipping at
[0, 1] (no tone mapping). Tighten the max once 709 tone mapping lands.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from color.curves import linear_to_logc4, linear_to_slog3
from color.gamuts import IDT_PAIRS
from color.rec709 import rec709_oetf
from color.resolve_export import (
    ACESCCT_CUBE_MIN,
    CUBE_SIZE_33,
    DEFAULT_CUBE_SIZE,
    clip_to_next_cube,
    combined_preview709_cube_bytes,
    combined_preview709_rgb,
    exposure_cube_bytes,
    exposure_in_acescct,
    idt_cube_bytes,
    idt_cube_rgb,
    odt_cube_bytes,
    odt_from_acescct,
    wb_cube_bytes,
    wb_in_acescct,
)
from color.batch import process_locked_writes
from color.resolve_export import export_resolve_bundle

# Seed for every random lattice probe in this file.
INTERP_SEED = 20261003

# Neutral axis: r=g=b, uniform, on the ACEScct band 0.15–0.50.
# Several hundred points so the approach to the 709 white point is covered.
# Gates are measured max + about 15% under the default 0–1 lattice, size 17.
# LogC4 18% grey keeps its max gate.
NEUTRAL_LO = 0.15
NEUTRAL_HI = 0.50
NEUTRAL_COUNT = 401
# Measured max on the 401-point axis, then about +15%:
#   idt 0.023256 → 0.027
#   exposure 0.000416 → 0.00048
#   wb 0.004599 → 0.0053
#   odt 0.029580 → 0.034
#   chain 0.120331 → 0.138
# LogC4 18% grey measured max 0.024237; the gate stays 0.04.
TOL_NEUTRAL_MAX = {
    "idt": 0.027,
    "exposure": 0.00048,
    "wb": 0.0053,
    "odt": 0.034,
}
TOL_CHAIN_NEUTRAL_MAX = 0.138
TOL_CHAIN_GREY_MAX = 0.04

# Saturated / overexposed: mean and p99 of flattened |lookup − direct|.
# About 15% above the INTERP_SEED measurement on the 0–1 lattice.
# Max is logged, not gated.
# Measured (mean, p99, max):
#   idt sat       0.006955  0.085903  0.293769
#   exposure sat  0.000086  0.002164  0.003605
#   wb sat        0.004716  0.044600  0.142387
#   odt sat       0.004897  0.092700  0.127500
#   chain sat     0.030640  0.725727  1.000000
#   idt over      0.002974  0.037435  0.049899
#   exposure over 0.000000  0.000000  0.000000
#   wb over       0.001352  0.016914  0.027477
#   odt over      0.059262  0.523777  0.616791
# Exposure over measured 0; the gate is a 1e-6 / 1e-5 cushion.
# Chain saturated p99 includes samples the next cube clips at ACEScct 1.0.
# Saturated and overexposed error on the Rec.709 node comes from Rec.709
# hard clipping at [0, 1] (no tone mapping). Tighten the max once 709 tone
# mapping lands.
TOL_SATURATED_MEAN = {
    "idt": 0.0080,
    "exposure": 0.00010,
    "wb": 0.0055,
    "odt": 0.0057,
}
TOL_SATURATED_P99 = {
    "idt": 0.099,
    "exposure": 0.0025,
    "wb": 0.052,
    "odt": 0.107,
}
TOL_OVER_MEAN = {
    "idt": 0.0035,
    "exposure": 1e-6,
    "wb": 0.0016,
    "odt": 0.069,
}
TOL_OVER_P99 = {
    "idt": 0.044,
    "exposure": 1e-5,
    "wb": 0.020,
    "odt": 0.61,
}
TOL_CHAIN_SATURATED_MEAN = 0.036
TOL_CHAIN_SATURATED_P99 = 0.84
# +3 stops along r=g=b on [0, 1], codes that stay ≤ ACEScct 1.0.
# Exposure lookup max 0.026724 → 0.031. Graded WB of that output max
# 0.071833 → 0.083.
TOL_PLUS3_BELOW_EXPOSURE_MAX = 0.031
TOL_PLUS3_BELOW_WB_MAX = 0.083

def _assert_no_range_header(text: str) -> None:
    """No DOMAIN_* header and no *_INPUT_RANGE header. Comments may name them."""
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("TITLE") or s.startswith("LUT_"):
            continue
        assert not s.startswith("DOMAIN_"), s
        assert "INPUT_RANGE" not in s, s


def _rgb_rows(text: str) -> np.ndarray:
    rows = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("TITLE") or s.startswith("LUT_") or s.startswith("DOMAIN"):
            continue
        parts = s.split()
        if len(parts) == 3:
            rows.append([float(x) for x in parts])
    return np.asarray(rows, dtype=np.float64)


def as_bgr_table(samples: np.ndarray, size: int) -> np.ndarray:
    """File order is R-fastest. Reshape to [b, g, r, 3]."""
    return np.asarray(samples, dtype=np.float64).reshape(size, size, size, 3)


def trilinear_cube(table: np.ndarray, x, lo: float, hi: float) -> np.ndarray:
    """Trilinear lookup. ``table`` is [b, g, r, 3]. ``x`` is (N, 3) rgb."""
    n = table.shape[0]
    span = float(hi) - float(lo)
    t = (np.asarray(x, dtype=np.float64) - lo) / span * (n - 1)
    t = np.clip(t, 0.0, n - 1)
    i0 = np.floor(t).astype(np.int32)
    i1 = np.minimum(i0 + 1, n - 1)
    f = t - i0
    r0, g0, b0 = i0[:, 0], i0[:, 1], i0[:, 2]
    r1, g1, b1 = i1[:, 0], i1[:, 1], i1[:, 2]
    fr, fg, fb = f[:, 0:1], f[:, 1:2], f[:, 2:3]

    def corner(bi, gi, ri):
        return table[bi, gi, ri]

    c00 = corner(b0, g0, r0) * (1.0 - fr) + corner(b0, g0, r1) * fr
    c01 = corner(b1, g0, r0) * (1.0 - fr) + corner(b1, g0, r1) * fr
    c10 = corner(b0, g1, r0) * (1.0 - fr) + corner(b0, g1, r1) * fr
    c11 = corner(b1, g1, r0) * (1.0 - fr) + corner(b1, g1, r1) * fr
    c0 = c00 * (1.0 - fg) + c10 * fg
    c1 = c01 * (1.0 - fg) + c11 * fg
    return c0 * (1.0 - fb) + c1 * fb


def lerp_1d(curve: np.ndarray, x, lo: float, hi: float) -> np.ndarray:
    """Per-channel lerp of a 1D curve. ``curve`` is (n,) or (n, 3)."""
    curve = np.asarray(curve, dtype=np.float64)
    if curve.ndim == 2:
        curve = curve[:, 0]
    n = len(curve)
    t = (np.asarray(x, dtype=np.float64) - lo) / (float(hi) - float(lo)) * (n - 1)
    t = np.clip(t, 0.0, n - 1)
    i0 = np.floor(t).astype(np.int32)
    i1 = np.minimum(i0 + 1, n - 1)
    f = t - i0
    return curve[i0] * (1.0 - f) + curve[i1] * f


def _neutral_axis(count: int = NEUTRAL_COUNT) -> np.ndarray:
    """Uniform r=g=b on 0.15–0.50. Several hundred points, not a 24-draw sample."""
    column = np.linspace(NEUTRAL_LO, NEUTRAL_HI, int(count))
    return np.repeat(column.reshape(-1, 1), 3, axis=1)


def _inside_cells(values: np.ndarray, lo: float, hi: float, size: int) -> np.ndarray:
    """Push each coordinate into the interior of its lattice cell."""
    ncell = size - 1
    t = (values - lo) / (hi - lo) * ncell
    i0 = np.clip(np.floor(t), 0, ncell - 1)
    frac = np.clip(t - i0, 0.15, 0.85)
    return lo + (i0 + frac) / ncell * (hi - lo)


def _between(rng: np.random.Generator, count: int, size: int, kind: str) -> np.ndarray:
    """Saturated or overexposed points strictly inside a [0, 1] lattice cell."""
    lo, hi = 0.0, 1.0
    if kind == "over":
        start = lo + 0.80 * (hi - lo)
        values = rng.uniform(start, hi - 1e-4, size=(count, 3))
    else:
        values = rng.uniform(lo + 1e-3, hi - 1e-3, size=(count, 3))
    return _inside_cells(values, lo, hi, size)


def _err_stats(a, b) -> dict[str, float]:
    """Mean, p99, and max of flattened absolute channel error.

    p99 uses NumPy's default linear quantile. Max is the same number the
    old max-error gate used.
    """
    err = np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)).reshape(-1)
    return {
        "mean": float(np.mean(err)),
        "p99": float(np.quantile(err, 0.99)),
        "max": float(np.max(err)),
    }


def test_default_cube_size_is_17_and_33_still_selectable(tmp_path):
    """Python default matches Swift / the combined cube. 33 remains a choice."""
    assert DEFAULT_CUBE_SIZE == 17
    assert CUBE_SIZE_33 == 33
    assert inspect.signature(export_resolve_bundle).parameters["lut_size"].default == 17
    assert inspect.signature(process_locked_writes).parameters["resolve_lut_size"].default == 17
    assert "LUT_3D_SIZE 17" in idt_cube_bytes("sony_slog3_sgamut3")
    assert "LUT_3D_SIZE 17" in odt_cube_bytes()
    assert "LUT_3D_SIZE 17" in wb_cube_bytes(None)
    assert "LUT_3D_SIZE 33" in wb_cube_bytes(3200.0, size=CUBE_SIZE_33)
    assert "LUT_3D_SIZE 33" in idt_cube_bytes("arri_logc4_awg4", size=CUBE_SIZE_33)
    export_resolve_bundle(tmp_path, idt_ids=["sony_slog3_sgamut3"], include_wb=False)
    idt_text = (tmp_path / "01_IDT_sony_slog3_sgamut3.cube").read_text(encoding="utf-8")
    odt_text = (tmp_path / "04_ODT_Rec709.cube").read_text(encoding="utf-8")
    combined = (tmp_path / "00_Combined_Preview709_sony_slog3_sgamut3.cube").read_text(
        encoding="utf-8"
    )
    assert "LUT_3D_SIZE 17" in idt_text
    assert "LUT_3D_SIZE 17" in odt_text
    assert "LUT_3D_SIZE 17" in combined


def test_per_node_cubes_have_no_domain_header_and_sample_unit_interval():
    """No DOMAIN or INPUT_RANGE header. Lattice is the default [0, 1].

    The 1e-10 floor keeps ACEScct output at about 0.0729 or above.
    Exposure output is not limited to 1. The Rec.709 table is.
    """
    for idt in IDT_PAIRS:
        text = idt_cube_bytes(idt, size=DEFAULT_CUBE_SIZE)
        rgb = _rgb_rows(text)
        _assert_no_range_header(text)
        assert rgb.min() >= ACESCCT_CUBE_MIN - 1e-8, idt
        assert "1e-10" in text
        assert "LUT_3D_SIZE 17" in text

    for stops in (0.0, -2.0, 2.0, 4.0, 3.0):
        text = exposure_cube_bytes(stops)
        rgb = _rgb_rows(text)
        _assert_no_range_header(text)
        assert rgb.min() >= ACESCCT_CUBE_MIN - 1e-8
        assert "LUT_1D_SIZE" in text
        if stops > 0.0:
            assert rgb.max() > 1.0

    for cct, tint in ((None, 0.0), (3200.0, 0.4), (6504.0, -0.2)):
        text = wb_cube_bytes(cct, tint, size=DEFAULT_CUBE_SIZE)
        rgb = _rgb_rows(text)
        _assert_no_range_header(text)
        assert rgb.min() >= ACESCCT_CUBE_MIN - 1e-8
        assert np.isfinite(rgb).all()

    odt = odt_cube_bytes(size=DEFAULT_CUBE_SIZE)
    odt_rgb = _rgb_rows(odt)
    _assert_no_range_header(odt)
    assert odt_rgb.min() >= 0.0
    assert odt_rgb.max() <= 1.0

    _assert_no_range_header(combined_preview709_cube_bytes("arri_logc4_awg4"))


def _baked_chain(log, idt, stops, cct, tint):
    """Per-node functions. No allocation clip; the 1e-10 floor is inside the IDT cube."""
    enc = idt_cube_rgb(log, idt)
    enc = exposure_in_acescct(enc, stops)
    enc = wb_in_acescct(enc, cct, tint=tint)
    return np.clip(odt_from_acescct(enc), 0.0, 1.0)


@pytest.mark.parametrize(
    "idt,stops,cct,tint",
    [
        ("arri_logc4_awg4", 0.0, None, 0.0),
        ("arri_logc4_awg4", 0.5, 3200.0, 0.25),
        ("sony_slog3_sgamut3", 0.0, None, 0.0),
        ("red_log3g10_rwg", 1.0, 4500.0, -0.1),
        ("nikon_nlog_bt2020", -0.5, None, 0.0),
        ("apple_log2_awg", 2.0, 3200.0, 0.4),
    ],
)
def test_node_function_chain_matches_combined_cube(idt, stops, cct, tint):
    """Ranged per-node functions match the combined preview, including corners.

    The combined file still samples the analytic IDT. Flooring linear at
    1e-10 inside the IDT cube does not move the clipped Rec.709 result.
    """
    xs = np.linspace(0.0, 1.0, 5)
    b, g, r = np.meshgrid(xs, xs, xs, indexing="ij")
    logs = np.stack([r, g, b], axis=-1).reshape(-1, 3)
    baked = _baked_chain(logs, idt, stops, cct, tint)
    combined = combined_preview709_rgb(
        logs, idt, exposure_stops=stops, cct=cct, tint=tint
    )
    np.testing.assert_allclose(baked, combined, atol=1e-6, rtol=0)


def test_eighteen_percent_grey_stays_near_rec709_oetf():
    """Combined preview and the per-node function chain keep 18% grey."""
    ref = float(np.asarray(rec709_oetf(0.18)).reshape(-1)[0])
    assert ref == pytest.approx(0.409, abs=0.002)
    samples = (
        ("arri_logc4_awg4", float(linear_to_logc4(0.18))),
        ("sony_slog3_sgamut3", float(linear_to_slog3(0.18))),
    )
    for idt, code in samples:
        grey = np.full((1, 3), code)
        combined = combined_preview709_rgb(grey, idt, exposure_stops=0.0, cct=None)
        chained = _baked_chain(grey, idt, 0.0, None, 0.0)
        assert combined[0, 0] == pytest.approx(0.409, abs=0.002)
        np.testing.assert_allclose(chained, combined, atol=1e-8, rtol=0)
        np.testing.assert_allclose(combined, ref, atol=0.002, rtol=0)


def test_exposure_plus_3_clips_above_acescct_one_into_next_node():
    """+3 stops, then the next node (WB).

    ACEScct 1.0 is linear 2**7.8 ≈ 222.86, about 10.3 stops above 18% grey.
    The exposure cube may write a code above 1. The next cube only samples
    [0, 1], so that code is clipped to 1.0 on entry. Codes that stay at or
    below 1 are not clipped and stay within the gates.
    """
    from color.working_space import acescct_encode

    lin_at_one = 2.0 ** 7.8
    assert lin_at_one == pytest.approx(222.86, abs=0.02)
    code = float(np.asarray(acescct_encode(lin_at_one)).reshape(-1)[0])
    assert code == pytest.approx(1.0, abs=1e-6)
    assert float(np.log2(lin_at_one / 0.18)) == pytest.approx(10.3, abs=0.05)

    xs = np.linspace(0.0, 1.0, NEUTRAL_COUNT)
    x = np.repeat(xs.reshape(-1, 1), 3, axis=1)
    direct = exposure_in_acescct(x, 3.0)
    looked = lerp_1d(_rgb_rows(exposure_cube_bytes(3.0)), x, 0.0, 1.0)
    above = direct[:, 0] > 1.0
    below = ~above
    assert int(above.sum()) > 50
    assert int(below.sum()) > 200
    # Clip point is ACEScct 1.0 on the way into the next cube.
    entered = clip_to_next_cube(looked)
    assert np.all(entered[above] == 1.0)
    assert np.all(entered[below, 0] < 1.0)
    below_err = float(np.max(np.abs(looked[below] - direct[below])))
    assert below_err <= TOL_PLUS3_BELOW_EXPOSURE_MAX, below_err

    wb_tab = as_bgr_table(_rgb_rows(wb_cube_bytes(3200.0, 0.25, size=17)), 17)
    wb_look = trilinear_cube(wb_tab, entered, 0.0, 1.0)
    wb_direct = wb_in_acescct(direct, 3200.0, tint=0.25)
    wb_err = float(np.max(np.abs(wb_look[below] - wb_direct[below])))
    assert wb_err <= TOL_PLUS3_BELOW_WB_MAX, wb_err
    wb_at_one = wb_in_acescct(np.ones((1, 3)), 3200.0, tint=0.25)
    np.testing.assert_allclose(wb_look[above], np.broadcast_to(wb_at_one, wb_look[above].shape), atol=1e-6, rtol=0)


def _interp_errors(idt: str = "arri_logc4_awg4", size: int = 17, stops: float = 0.5, cct: float = 3200.0, tint: float = 0.25):
    """Mean, p99, and max |lookup − direct| for each node and sample class.

    Neutral probes are the uniform 0.15–0.50 axis. Saturated and overexposed
    probes stay inside cells of the default [0, 1] lattice.
    """
    rng = np.random.default_rng(INTERP_SEED)
    idt_text = idt_cube_bytes(idt, size=size)
    idt_table = as_bgr_table(_rgb_rows(idt_text), size)
    exp_text = exposure_cube_bytes(stops)
    exp_rows = _rgb_rows(exp_text)
    wb_text = wb_cube_bytes(cct, tint, size=size)
    wb_table = as_bgr_table(_rgb_rows(wb_text), size)
    odt_text = odt_cube_bytes(size=size)
    odt_table = as_bgr_table(_rgb_rows(odt_text), size)

    def idt_direct(x):
        return idt_cube_rgb(x, idt)

    def exp_direct(x):
        return exposure_in_acescct(x, stops)

    def wb_direct(x):
        return wb_in_acescct(x, cct, tint=tint)

    def odt_direct(x):
        return np.clip(odt_from_acescct(x), 0.0, 1.0)

    out = {}
    neutral = _neutral_axis()
    out[("idt", "neutral")] = _err_stats(trilinear_cube(idt_table, neutral, 0.0, 1.0), idt_direct(neutral))
    out[("exposure", "neutral")] = _err_stats(lerp_1d(exp_rows, neutral, 0.0, 1.0), exp_direct(neutral))
    out[("wb", "neutral")] = _err_stats(trilinear_cube(wb_table, neutral, 0.0, 1.0), wb_direct(neutral))
    out[("odt", "neutral")] = _err_stats(trilinear_cube(odt_table, neutral, 0.0, 1.0), odt_direct(neutral))

    probes = {"neutral": neutral}
    for kind, count in (("saturated", 36), ("over", 24)):
        cam = _between(rng, count, size, kind)
        probes[kind] = cam
        out[("idt", kind)] = _err_stats(trilinear_cube(idt_table, cam, 0.0, 1.0), idt_direct(cam))
        exp_x = _between(rng, count, 65, kind)
        out[("exposure", kind)] = _err_stats(lerp_1d(exp_rows, exp_x, 0.0, 1.0), exp_direct(exp_x))
        wb_x = _between(rng, count, size, kind)
        out[("wb", kind)] = _err_stats(trilinear_cube(wb_table, wb_x, 0.0, 1.0), wb_direct(wb_x))
        odt_x = _between(rng, count, size, kind)
        out[("odt", kind)] = _err_stats(trilinear_cube(odt_table, odt_x, 0.0, 1.0), odt_direct(odt_x))

    def chain_lookup(log, exp_curve, wb_tab):
        # Each following cube covers [0, 1]. ACEScct 1.0 (linear 2**7.8 ≈ 223)
        # is clipped to 1.0 on entry.
        enc = trilinear_cube(idt_table, log, 0.0, 1.0)
        enc = clip_to_next_cube(enc)
        enc = lerp_1d(exp_curve, enc, 0.0, 1.0)
        enc = clip_to_next_cube(enc)
        enc = trilinear_cube(wb_tab, enc, 0.0, 1.0)
        enc = clip_to_next_cube(enc)
        return trilinear_cube(odt_table, enc, 0.0, 1.0)

    # Neutral axis of the preview: 0 stops, identity WB.
    exp0 = _rgb_rows(exposure_cube_bytes(0.0))
    wb0 = as_bgr_table(_rgb_rows(wb_cube_bytes(None, 0.0, size=size)), size)
    neutral_log = probes["neutral"]
    out[("chain", "neutral")] = _err_stats(
        chain_lookup(neutral_log, exp0, wb0),
        combined_preview709_rgb(neutral_log, idt, exposure_stops=0.0, cct=None),
    )
    sat_log = probes["saturated"]
    out[("chain", "saturated")] = _err_stats(
        chain_lookup(sat_log, exp_rows, wb_table),
        combined_preview709_rgb(
            sat_log, idt, exposure_stops=stops, cct=cct, tint=tint
        ),
    )
    grey = np.full((1, 3), float(linear_to_logc4(0.18)))
    out[("chain", "grey")] = _err_stats(
        chain_lookup(grey, exp0, wb0),
        combined_preview709_rgb(grey, idt, exposure_stops=0.0, cct=None),
    )
    return out


def test_cube_trilinear_matches_direct_function_between_nodes():
    """Real lattice lookup, not the function compared with itself.

    Neutral (r=g=b) and LogC4 18% grey are gated on max absolute error.
    Saturated and overexposed groups are gated on mean and p99. Their max
    is logged and not gated.

    Saturated and overexposed error on the Rec.709 nodes comes from Rec.709
    hard clipping at [0, 1] (no tone mapping). Tighten the max once 709
    tone mapping lands. Size stays the default 17.
    """
    err = _interp_errors()
    logged = []
    for node, tol in TOL_NEUTRAL_MAX.items():
        seen = err[(node, "neutral")]["max"]
        assert seen <= tol, f"{node} neutral: max {seen:.6f} > tol {tol}"
    assert err[("chain", "neutral")]["max"] <= TOL_CHAIN_NEUTRAL_MAX
    assert err[("chain", "grey")]["max"] <= TOL_CHAIN_GREY_MAX

    # Saturated / overexposed: mean and p99 only. Max is recorded below.
    for node, tol in TOL_SATURATED_MEAN.items():
        seen = err[(node, "saturated")]
        assert seen["mean"] <= tol, f"{node} saturated mean {seen['mean']:.6f} > {tol}"
        p99 = TOL_SATURATED_P99[node]
        assert seen["p99"] <= p99, f"{node} saturated p99 {seen['p99']:.6f} > {p99}"
        logged.append(
            f"{node} saturated mean={seen['mean']:.6f} p99={seen['p99']:.6f} max={seen['max']:.6f}"
        )
    for node, tol in TOL_OVER_MEAN.items():
        seen = err[(node, "over")]
        assert seen["mean"] <= tol, f"{node} over mean {seen['mean']:.6f} > {tol}"
        p99 = TOL_OVER_P99[node]
        assert seen["p99"] <= p99, f"{node} over p99 {seen['p99']:.6f} > {p99}"
        logged.append(
            f"{node} over mean={seen['mean']:.6f} p99={seen['p99']:.6f} max={seen['max']:.6f}"
        )
    chain_sat = err[("chain", "saturated")]
    assert chain_sat["mean"] <= TOL_CHAIN_SATURATED_MEAN
    assert chain_sat["p99"] <= TOL_CHAIN_SATURATED_P99
    logged.append(
        "chain saturated mean={mean:.6f} p99={p99:.6f} max={max:.6f}".format(**chain_sat)
    )
    # Logged, not gated. pytest -s shows these lines; a failure of mean/p99
    # does not depend on max.
    print("\n".join(logged))


def test_interpolation_tolerances_are_documented():
    """Mean and p99 gates sit just above the measured tail. Neutral stays max."""
    for node in TOL_SATURATED_MEAN:
        assert TOL_SATURATED_MEAN[node] < TOL_SATURATED_P99[node]
        assert TOL_OVER_MEAN[node] < TOL_OVER_P99[node]
        assert node in TOL_NEUTRAL_MAX
    assert TOL_CHAIN_SATURATED_MEAN < TOL_CHAIN_SATURATED_P99
    assert TOL_CHAIN_GREY_MAX <= TOL_CHAIN_NEUTRAL_MAX
