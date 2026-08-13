"""Manufacturer log curve encode/decode (reference implementations).

When OpenColorIO Python is importable, IDTs with a BuiltinTransform
(LogC4, S-Log3, V-Log, Log3G10, Venice) call that Builtin to ACES2065-1.
These functions stay as the Linux/no-OCIO reference and as the 18% grey
unit-test source. They match the Builtins on documented 18% codes to well
under 0.5%. Do not replace them with invented “more accurate” constants.

F-Log2 and N-Log have no standard Builtin — these papers are the IDT.

Inputs are normalized 0-1 except Nikon N-Log, whose white-paper ``x`` is a
10-bit code value in 0-1023. Do not divide N-Log by 1023 before the curve.

References (public white papers):
- ARRI LogC4 Specification (2025-01-23)
- Sony Technical Summary S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3
- Panasonic VARICAM V-Log/V-Gamut (2014-11-28)
- Fujifilm F-Log2 Data Sheet Ver.1.0 / GFX ETERNA white paper
- Nikon N-Log Specification Document 1.0.0 (2018-09-01)
- RED OPS White Paper on REDWideGamutRGB and Log3G10 (915-0187 Rev-C)
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# ARRI LogC4 (EI-independent). Spec 2025-01-23 CTL reference.
# ---------------------------------------------------------------------------
_LOGC4_A = (2.0**18 - 16.0) / 117.45
_LOGC4_B = (1023.0 - 95.0) / 1023.0
_LOGC4_C = 95.0 / 1023.0
# Inverse slope at threshold t, and relative-scene-linear threshold.
# Linear extension for negative LogC4 (post-production may introduce them).
_LOGC4_S = (7.0 * np.log(2.0) * (2.0 ** (7.0 - 14.0 * _LOGC4_C / _LOGC4_B))) / (
    _LOGC4_A * _LOGC4_B
)
_LOGC4_T = (2.0 ** (14.0 * (-_LOGC4_C / _LOGC4_B) + 6.0) - 64.0) / _LOGC4_A

# 18% grey from ARRI conversion table (normalized LogC4).
LOGC4_18_PERCENT = 0.2784


def logc4_to_linear(x):
    """Decode ARRI LogC4 (normalized 0-1, negatives allowed) to scene linear."""
    x = np.asarray(x, dtype=np.float64)
    p = 14.0 * (x - _LOGC4_C) / _LOGC4_B + 6.0
    lin_pos = (np.power(2.0, p) - 64.0) / _LOGC4_A
    lin_neg = x * _LOGC4_S + _LOGC4_T
    return np.where(x >= 0.0, lin_pos, lin_neg)


def linear_to_logc4(lin):
    """Encode relative scene linear to ARRI LogC4."""
    lin = np.asarray(lin, dtype=np.float64)
    log_pos = (np.log2(_LOGC4_A * lin + 64.0) - 6.0) / 14.0 * _LOGC4_B + _LOGC4_C
    log_neg = (lin - _LOGC4_T) / _LOGC4_S
    return np.where(lin >= _LOGC4_T, log_pos, log_neg)


# ---------------------------------------------------------------------------
# Sony S-Log3 (normalized 0-1, 10-bit equivalent). Reflection encoding.
# ---------------------------------------------------------------------------
_SLOG3_CUT = 171.2102946929 / 1023.0
_SLOG3_A = 0.01125000
SLOG3_18_PERCENT = 420.0 / 1023.0  # documented 10-bit 18% grey
SLOG3_0_PERCENT = 95.0 / 1023.0
SLOG3_90_PERCENT = 598.0 / 1023.0  # 10-bit 598 for 90% reflectance


def slog3_to_linear(x):
    """Decode Sony S-Log3 (normalized 0-1) to scene-linear reflectance."""
    x = np.asarray(x, dtype=np.float64)
    cv = x * 1023.0
    lin_hi = (10.0 ** ((cv - 420.0) / 261.5)) * (0.18 + 0.01) - 0.01
    lin_lo = (cv - 95.0) * _SLOG3_A / (171.2102946929 - 95.0)
    return np.where(x >= _SLOG3_CUT, lin_hi, lin_lo)


def linear_to_slog3(lin):
    """Encode scene-linear reflectance to Sony S-Log3 (normalized 0-1)."""
    lin = np.asarray(lin, dtype=np.float64)
    log_hi = (420.0 + np.log10((lin + 0.01) / (0.18 + 0.01)) * 261.5) / 1023.0
    log_lo = (lin * (171.2102946929 - 95.0) / _SLOG3_A + 95.0) / 1023.0
    return np.where(lin >= _SLOG3_A, log_hi, log_lo)


# ---------------------------------------------------------------------------
# Panasonic V-Log (normalized 0-1).
# ---------------------------------------------------------------------------
_VLOG_CUT1 = 0.01
_VLOG_CUT2 = 0.181
_VLOG_B = 0.00873
_VLOG_C = 0.241514
_VLOG_D = 0.598206
VLOG_18_PERCENT = 433.0 / 1023.0  # white paper 10-bit 18% grey
VLOG_0_PERCENT = 128.0 / 1023.0
VLOG_90_PERCENT = 602.0 / 1023.0


def vlog_to_linear(x):
    """Decode Panasonic V-Log (normalized 0-1) to scene-linear reflectance."""
    x = np.asarray(x, dtype=np.float64)
    lin_hi = np.power(10.0, (x - _VLOG_D) / _VLOG_C) - _VLOG_B
    lin_lo = (x - 0.125) / 5.6
    return np.where(x >= _VLOG_CUT2, lin_hi, lin_lo)


def linear_to_vlog(lin):
    """Encode scene-linear reflectance to Panasonic V-Log."""
    lin = np.asarray(lin, dtype=np.float64)
    log_hi = _VLOG_C * np.log10(lin + _VLOG_B) + _VLOG_D
    log_lo = 5.6 * lin + 0.125
    return np.where(lin >= _VLOG_CUT1, log_hi, log_lo)


# ---------------------------------------------------------------------------
# Fujifilm F-Log2 (normalized 0-1). a=5.555556 (NOT F-Log's 0.555556).
# ---------------------------------------------------------------------------
_FLOG2_A = 5.555556
_FLOG2_B = 0.064829
_FLOG2_C = 0.245281
_FLOG2_D = 0.384316
_FLOG2_E = 8.799461
_FLOG2_F = 0.092864
_FLOG2_CUT1 = 0.000889
_FLOG2_CUT2 = 0.100686685370811
FLOG2_18_PERCENT = 400.0 / 1023.0  # white paper 10-bit 18% grey
FLOG2_0_PERCENT = 95.0 / 1023.0


def flog2_to_linear(x):
    """Decode Fujifilm F-Log2 (normalized 0-1) to scene-linear reflectance."""
    x = np.asarray(x, dtype=np.float64)
    lin_hi = np.power(10.0, (x - _FLOG2_D) / _FLOG2_C) / _FLOG2_A - _FLOG2_B / _FLOG2_A
    lin_lo = (x - _FLOG2_F) / _FLOG2_E
    return np.where(x >= _FLOG2_CUT2, lin_hi, lin_lo)


def linear_to_flog2(lin):
    """Encode scene-linear reflectance to Fujifilm F-Log2."""
    lin = np.asarray(lin, dtype=np.float64)
    log_hi = _FLOG2_C * np.log10(_FLOG2_A * lin + _FLOG2_B) + _FLOG2_D
    log_lo = _FLOG2_E * lin + _FLOG2_F
    return np.where(lin >= _FLOG2_CUT1, log_hi, log_lo)


# ---------------------------------------------------------------------------
# Nikon N-Log. White-paper x is a 10-bit code value 0-1023, NOT 0-1.
# Inverse uses natural log (pairs with exp in the decode).
# ---------------------------------------------------------------------------
NLOG_18_PERCENT_10BIT = 650.0 * (0.18 + 0.0075) ** (1.0 / 3.0)  # ~372
NLOG_CUT_X = 452.0
NLOG_CUT_Y = 0.328


def nlog_to_linear(x):
    """Decode Nikon N-Log 10-bit code value (0-1023) to reflectance.

    ``x`` is the 10-bit code, not a 0-1 normalized value. Dividing by 1023
    before this function is incorrect per the Nikon N-Log Specification.
    """
    x = np.asarray(x, dtype=np.float64)
    lin_lo = (x / 650.0) ** 3.0 - 0.0075
    lin_hi = np.exp((x - 619.0) / 150.0)
    return np.where(x < NLOG_CUT_X, lin_lo, lin_hi)


def linear_to_nlog(lin):
    """Encode reflectance to Nikon N-Log 10-bit code value (0-1023)."""
    lin = np.asarray(lin, dtype=np.float64)
    # Spec: log is natural log because decode uses exp.
    # np.where evaluates both branches; keep the log argument positive.
    cv_lo = 650.0 * np.power(np.maximum(lin + 0.0075, 0.0), 1.0 / 3.0)
    cv_hi = 150.0 * np.log(np.maximum(lin, 1e-30)) + 619.0
    return np.where(lin < NLOG_CUT_Y, cv_lo, cv_hi)


def nlog_normalized_to_linear(x01):
    """Convenience: decode N-Log stored as 0-1 (code/1023) by expanding to 10-bit.

    OCIO image buffers are 0-1; this wrapper multiplies by 1023 then calls
    :func:`nlog_to_linear`. The curve itself still sees 10-bit codes.
    """
    x01 = np.asarray(x01, dtype=np.float64)
    return nlog_to_linear(x01 * 1023.0)


def linear_to_nlog_normalized(lin):
    """Encode reflectance to N-Log stored as 0-1 (code/1023)."""
    return linear_to_nlog(lin) / 1023.0


# ---------------------------------------------------------------------------
# RED Log3G10 (normalized 0-1). 18% grey maps to 1/3.
# ---------------------------------------------------------------------------
_L3G10_A = 0.224282
_L3G10_B = 155.975327
_L3G10_C = 0.01
_L3G10_G = 15.1927
LOG3G10_18_PERCENT = 1.0 / 3.0
LOG3G10_ZERO = 0.091551  # white-paper mapping of linear 0
LOG3G10_MAX_LIN = 0.18 * (2.0**10)  # 184.32, encodes to 1.0


def log3g10_to_linear(x):
    """Decode RED Log3G10 (normalized, 0 is the break) to scene linear."""
    x = np.asarray(x, dtype=np.float64)
    lin_pos = (np.power(10.0, x / _L3G10_A) - 1.0) / _L3G10_B - _L3G10_C
    lin_neg = x / _L3G10_G - _L3G10_C
    return np.where(x >= 0.0, lin_pos, lin_neg)


def linear_to_log3g10(lin):
    """Encode scene linear to RED Log3G10.

    Matches the white-paper C: offset by c, then linear slope if the offset
    signal is negative, else a*log10(x*b+1).
    """
    lin = np.asarray(lin, dtype=np.float64)
    x = lin + _L3G10_C
    log_neg = x * _L3G10_G
    log_pos = _L3G10_A * np.log10(x * _L3G10_B + 1.0)
    return np.where(x < 0.0, log_neg, log_pos)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
# Curve names used by locked clip pairs. Sony has one curve, two gamuts.
CURVE_LOGC4 = "logc4"
CURVE_SLOG3 = "slog3"
CURVE_VLOG = "vlog"
CURVE_FLOG2 = "flog2"
CURVE_NLOG = "nlog"
CURVE_LOG3G10 = "log3g10"

IDT_NAMES = (
    "ARRI LogC4 / AWG4",
    "Sony S-Log3 / S-Gamut3",
    "Sony S-Log3 / S-Gamut3.Cine",
    "Panasonic V-Log / V-Gamut",
    "Fujifilm F-Log2 / BT.2020",
    "Nikon N-Log / BT.2020",
    "RED Log3G10 / REDWideGamutRGB",
    "Sony S-Log3 / S-Gamut3 (Venice)",
    "Sony S-Log3 / S-Gamut3.Cine (Venice)",
)

_DECODE = {
    CURVE_LOGC4: logc4_to_linear,
    CURVE_SLOG3: slog3_to_linear,
    CURVE_VLOG: vlog_to_linear,
    CURVE_FLOG2: flog2_to_linear,
    CURVE_NLOG: nlog_to_linear,
    CURVE_LOG3G10: log3g10_to_linear,
}

_ENCODE = {
    CURVE_LOGC4: linear_to_logc4,
    CURVE_SLOG3: linear_to_slog3,
    CURVE_VLOG: linear_to_vlog,
    CURVE_FLOG2: linear_to_flog2,
    CURVE_NLOG: linear_to_nlog,
    CURVE_LOG3G10: linear_to_log3g10,
}


def decode_log(curve: str, x):
    """Decode a named camera log curve to scene linear."""
    try:
        fn = _DECODE[curve]
    except KeyError as exc:
        raise KeyError(f"Unknown curve {curve!r}") from exc
    return fn(x)


def encode_log(curve: str, lin):
    """Encode scene linear to a named camera log curve."""
    try:
        fn = _ENCODE[curve]
    except KeyError as exc:
        raise KeyError(f"Unknown curve {curve!r}") from exc
    return fn(lin)
