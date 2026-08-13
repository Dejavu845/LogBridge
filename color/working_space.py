"""Internal working encodings: DaVinci Intermediate and ACEScct.

Default M1 working space is DaVinci Wide Gamut + DaVinci Intermediate
(D65, matches every M1 camera IDT white point). ACEScct (AP1 / ~D60) is
an alternate; converting D65 camera linear into AP1 requires a CAT.
"""

from __future__ import annotations

import numpy as np

# DaVinci Intermediate (Resolve 17 Wide Gamut Intermediate white paper).
DI_A = 0.0075
DI_B = 7.0
DI_C = 0.07329248
DI_M = 10.44426855
DI_LIN_CUT = 0.00262409
DI_LOG_CUT = 0.02740668
DI_18_PERCENT = 0.336043


def davinci_intermediate_encode(lin):
    lin = np.asarray(lin, dtype=np.float64)
    log = (np.log2(lin + DI_A) + DI_B) * DI_C
    linear = lin * DI_M
    return np.where(lin > DI_LIN_CUT, log, linear)


def davinci_intermediate_decode(enc):
    enc = np.asarray(enc, dtype=np.float64)
    lin = np.power(2.0, enc / DI_C - DI_B) - DI_A
    lo = enc / DI_M
    return np.where(enc > DI_LOG_CUT, lin, lo)


# ACEScct (AP1 log). linAP1 <-> ACEScct.
_ACESCCT_LO_S = 10.5402377416545
_ACESCCT_LO_O = 0.0729055341958355
_ACESCCT_BREAK_LIN = 0.0078125
_ACESCCT_BREAK_LOG = _ACESCCT_LO_S * _ACESCCT_BREAK_LIN + _ACESCCT_LO_O  # Y_break


def acescct_encode(lin_ap1):
    lin = np.asarray(lin_ap1, dtype=np.float64)
    return np.where(
        lin <= _ACESCCT_BREAK_LIN,
        _ACESCCT_LO_S * lin + _ACESCCT_LO_O,
        (np.log2(np.maximum(lin, 1e-10)) + 9.72) / 17.52,
    )


def acescct_decode(enc):
    enc = np.asarray(enc, dtype=np.float64)
    return np.where(
        enc <= _ACESCCT_BREAK_LOG,
        (enc - _ACESCCT_LO_O) / _ACESCCT_LO_S,
        np.power(2.0, enc * 17.52 - 9.72),
    )
