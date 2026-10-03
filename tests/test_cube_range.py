"""Per-node .cube range, lattice size, chain vs combined preview, interpolation.

Scene-referred tables (IDT, exposure, WB) stay inside the ACEScct allocation.
The Rec.709 table stays inside [0, 1]. Analytic ``idt_to_acescct`` is not
rewritten; the combined preview of 18% grey stays on the Rec.709 OETF.

Interpolation tolerances (absolute, Rec.709 or ACEScct code, size 17):

- Neutral axis means r = g = b, sampled in the interior of a lattice cell.
- Overexposed samples sit in the top fifth of that node's input domain.
- Saturated samples use independent random channels, same seed.

Neutral-axis and LogC4 18% grey gates are max absolute error.
Saturated and overexposed gates are mean and p99 of the same absolute
channel error. The max of those groups is printed and not gated.

Saturated and overexposed error on the Rec.709 nodes comes from Rec.709
hard clipping at [0, 1] (no tone mapping). Tighten the max once 709 tone
mapping lands.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from color.curves import linear_to_logc4, linear_to_slog3
from color.gamuts import IDT_PAIRS
from color.rec709 import rec709_oetf
from color.resolve_export import (
    ACESCCT_CUBE_MAX,
    ACESCCT_CUBE_MIN,
    CUBE_SIZE_33,
    DEFAULT_CUBE_SIZE,
    clip_acescct_cube,
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

# Absolute error on size 17. Neutral is r=g=b inside the grading band
# (camera log 0.15–0.50, or ACEScct 0.18–0.45), and each sample sits
# inside a lattice cell rather than on a node. Saturated uses independent
# channels across the whole input domain. Overexposed is the top fifth.
# Seed INTERP_SEED, LogC4, exposure +0.5 stop, WB 3200 K tint +0.25.
# The neutral/grey chain is 0 stops and identity WB.
#
# Neutral axis and LogC4 18% grey stay on max |Δ|. Measured max:
#   idt 0.019175  exposure 0.000000  wb 0.004751  odt 0.048723
#   chain neutral 0.225839  chain grey 0.012877
TOL_NEUTRAL_MAX = {
    "idt": 0.04,
    "exposure": 0.001,
    "wb": 0.02,
    "odt": 0.08,
}
TOL_CHAIN_NEUTRAL_MAX = 0.30
TOL_CHAIN_GREY_MAX = 0.04

# Saturated / overexposed: mean and p99 of flattened |lookup − direct|.
# About 15% above the INTERP_SEED measurement. Max is logged, not gated.
# Measured (mean, p99, max):
#   idt sat       0.003581  0.060945  0.092038
#   exposure sat  0.000018  0.000648  0.000783
#   wb sat        0.010665  0.162845  0.314497
#   odt sat       0.013575  0.383491  0.414236
#   chain sat     0.025661  0.405312  0.415366
#   idt over      0.002000  0.019807  0.022275
#   exposure over 0.000325  0.003987  0.004643
#   wb over       0.051386  0.611761  0.678737
#   odt over      0.090785  0.674138  0.722500
# Saturated and overexposed error on the Rec.709 nodes (ODT and the
# combined chain) comes from Rec.709 hard clipping at [0, 1] (no tone
# mapping). Tighten the max once 709 tone mapping lands.
TOL_SATURATED_MEAN = {
    "idt": 0.0042,
    "exposure": 0.000030,
    "wb": 0.013,
    "odt": 0.016,
}
TOL_SATURATED_P99 = {
    "idt": 0.071,
    "exposure": 0.00080,
    "wb": 0.19,
    "odt": 0.45,
}
TOL_OVER_MEAN = {
    "idt": 0.0024,
    "exposure": 0.00040,
    "wb": 0.060,
    "odt": 0.11,
}
TOL_OVER_P99 = {
    "idt": 0.024,
    "exposure": 0.0048,
    "wb": 0.71,
    "odt": 0.78,
}
TOL_CHAIN_SATURATED_MEAN = 0.030
TOL_CHAIN_SATURATED_P99 = 0.47

# IRIDAS header keywords the writers emit. Not LUT_3D_INPUT_RANGE.
# Scene-node input domains, 10 decimal places except the 0/1 edges.
SCENE_DOMAIN_MIN_LINE = "DOMAIN_MIN 0.0729055352 0.0729055352 0.0729055352"
SCENE_DOMAIN_MAX_LINE = "DOMAIN_MAX 1.4679963120 1.4679963120 1.4679963120"


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


def _domain(text: str, key: str) -> tuple[float, float, float]:
    for ln in text.splitlines():
        if ln.startswith(key + " "):
            nums = [float(x) for x in ln.split()[1:]]
            assert len(nums) == 3
            return (nums[0], nums[1], nums[2])
    raise AssertionError(f"missing {key}")


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


def _grading_band(lo: float, hi: float) -> tuple[float, float]:
    """Where a neutral ramp is still a picture, not the allocation shoulder.

    Camera log is the unit interval, and 18% sits near 0.28–0.41.
    ACEScct's allocation runs up to ~1.47; 18% grey is code ~0.414, and
    the Rec.709 OETF is already hard-clipped well before the top.
    """
    if hi <= 1.0 + 1e-6 and lo >= -1e-9:
        return (0.15, 0.50)
    return (0.18, 0.45)


def _inside_cells(values: np.ndarray, lo: float, hi: float, size: int) -> np.ndarray:
    """Push each coordinate into the interior of its lattice cell."""
    ncell = size - 1
    t = (values - lo) / (hi - lo) * ncell
    i0 = np.clip(np.floor(t), 0, ncell - 1)
    frac = np.clip(t - i0, 0.15, 0.85)
    return lo + (i0 + frac) / ncell * (hi - lo)


def _between(rng: np.random.Generator, count: int, size: int, lo: float, hi: float, kind: str) -> np.ndarray:
    """Points strictly inside a lattice cell (not on a node)."""
    if kind == "neutral":
        a, b = _grading_band(lo, hi)
        a = max(a, lo + 1e-4)
        b = min(b, hi - 1e-4)
        column = rng.uniform(a, b, size=(count, 1))
        values = np.repeat(column, 3, axis=1)
    elif kind == "over":
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


def test_per_node_cubes_stay_inside_declared_range():
    """IDT / exposure / WB inside the ACEScct allocation. Rec.709 inside [0, 1]."""
    for idt in IDT_PAIRS:
        text = idt_cube_bytes(idt, size=DEFAULT_CUBE_SIZE)
        rgb = _rgb_rows(text)
        assert rgb.min() >= ACESCCT_CUBE_MIN - 1e-8, idt
        assert rgb.max() <= ACESCCT_CUBE_MAX + 1e-8, idt
        assert "DOMAIN_MIN 0.0 0.0 0.0" in text
        assert "DOMAIN_MAX 1.0 1.0 1.0" in text
        assert "LUT_3D_INPUT_RANGE" not in text
        assert "1e-10" in text

    for stops in (0.0, -2.0, 2.0, 4.0):
        text = exposure_cube_bytes(stops)
        rgb = _rgb_rows(text)
        assert rgb.min() >= ACESCCT_CUBE_MIN - 1e-8
        assert rgb.max() <= ACESCCT_CUBE_MAX + 1e-8
        assert SCENE_DOMAIN_MIN_LINE in text
        assert SCENE_DOMAIN_MAX_LINE in text
        assert "LUT_1D_INPUT_RANGE" not in text
        lo = _domain(text, "DOMAIN_MIN")
        hi = _domain(text, "DOMAIN_MAX")
        assert lo[0] == pytest.approx(ACESCCT_CUBE_MIN, abs=5e-10)
        assert hi[0] == pytest.approx(ACESCCT_CUBE_MAX, abs=5e-10)

    for cct, tint in ((None, 0.0), (3200.0, 0.4), (6504.0, -0.2)):
        text = wb_cube_bytes(cct, tint, size=DEFAULT_CUBE_SIZE)
        rgb = _rgb_rows(text)
        assert rgb.min() >= ACESCCT_CUBE_MIN - 1e-8
        assert rgb.max() <= ACESCCT_CUBE_MAX + 1e-8
        assert SCENE_DOMAIN_MIN_LINE in text
        assert SCENE_DOMAIN_MAX_LINE in text
        assert "LUT_3D_INPUT_RANGE" not in text
        lo = _domain(text, "DOMAIN_MIN")
        hi = _domain(text, "DOMAIN_MAX")
        assert lo[0] == pytest.approx(ACESCCT_CUBE_MIN, abs=5e-10)
        assert hi[0] == pytest.approx(ACESCCT_CUBE_MAX, abs=5e-10)

    odt = odt_cube_bytes(size=DEFAULT_CUBE_SIZE)
    odt_rgb = _rgb_rows(odt)
    assert odt_rgb.min() >= 0.0
    assert odt_rgb.max() <= 1.0
    assert SCENE_DOMAIN_MIN_LINE in odt
    assert SCENE_DOMAIN_MAX_LINE in odt
    assert "LUT_3D_INPUT_RANGE" not in odt
    assert _domain(odt, "DOMAIN_MIN")[0] == pytest.approx(ACESCCT_CUBE_MIN, abs=5e-10)
    assert _domain(odt, "DOMAIN_MAX")[0] == pytest.approx(ACESCCT_CUBE_MAX, abs=5e-10)


def _baked_chain(log, idt, stops, cct, tint):
    """Per-node cube functions, including the allocation clip."""
    enc = idt_cube_rgb(log, idt)
    enc = clip_acescct_cube(exposure_in_acescct(enc, stops))
    enc = clip_acescct_cube(wb_in_acescct(enc, cct, tint=tint))
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


def _interp_errors(idt: str = "arri_logc4_awg4", size: int = 17, stops: float = 0.5, cct: float = 3200.0, tint: float = 0.25):
    """Mean, p99, and max |lookup − direct| for each node and sample class."""
    rng = np.random.default_rng(INTERP_SEED)
    idt_text = idt_cube_bytes(idt, size=size)
    idt_table = as_bgr_table(_rgb_rows(idt_text), size)
    exp_text = exposure_cube_bytes(stops)
    exp_rows = _rgb_rows(exp_text)
    exp_lo = _domain(exp_text, "DOMAIN_MIN")[0]
    exp_hi = _domain(exp_text, "DOMAIN_MAX")[0]
    wb_text = wb_cube_bytes(cct, tint, size=size)
    wb_table = as_bgr_table(_rgb_rows(wb_text), size)
    wb_lo = _domain(wb_text, "DOMAIN_MIN")[0]
    wb_hi = _domain(wb_text, "DOMAIN_MAX")[0]
    odt_text = odt_cube_bytes(size=size)
    odt_table = as_bgr_table(_rgb_rows(odt_text), size)
    odt_lo = _domain(odt_text, "DOMAIN_MIN")[0]
    odt_hi = _domain(odt_text, "DOMAIN_MAX")[0]

    def idt_direct(x):
        return idt_cube_rgb(x, idt)

    def exp_direct(x):
        return clip_acescct_cube(exposure_in_acescct(x, stops))

    def wb_direct(x):
        return clip_acescct_cube(wb_in_acescct(x, cct, tint=tint))

    def odt_direct(x):
        return np.clip(odt_from_acescct(x), 0.0, 1.0)

    out = {}
    probes = {}
    for kind, count in (("neutral", 24), ("saturated", 36), ("over", 24)):
        cam = _between(rng, count, size, 0.0, 1.0, kind)
        probes[kind] = cam
        out[("idt", kind)] = _err_stats(trilinear_cube(idt_table, cam, 0.0, 1.0), idt_direct(cam))
        exp_x = _between(rng, count, 65, exp_lo, exp_hi, kind)
        out[("exposure", kind)] = _err_stats(lerp_1d(exp_rows, exp_x, exp_lo, exp_hi), exp_direct(exp_x))
        wb_x = _between(rng, count, size, wb_lo, wb_hi, kind)
        out[("wb", kind)] = _err_stats(trilinear_cube(wb_table, wb_x, wb_lo, wb_hi), wb_direct(wb_x))
        odt_x = _between(rng, count, size, odt_lo, odt_hi, kind)
        out[("odt", kind)] = _err_stats(trilinear_cube(odt_table, odt_x, odt_lo, odt_hi), odt_direct(odt_x))

    def chain_lookup(log, exp_curve, wb_tab):
        enc = trilinear_cube(idt_table, log, 0.0, 1.0)
        enc = np.clip(enc, exp_lo, exp_hi)
        enc = lerp_1d(exp_curve, enc, exp_lo, exp_hi)
        enc = np.clip(enc, wb_lo, wb_hi)
        enc = trilinear_cube(wb_tab, enc, wb_lo, wb_hi)
        enc = np.clip(enc, odt_lo, odt_hi)
        return trilinear_cube(odt_table, enc, odt_lo, odt_hi)

    # Neutral axis of the preview: 0 stops, identity WB. Graded WB would
    # leave the diagonal and is covered by the saturated gate.
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
