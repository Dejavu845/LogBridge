"""Extension-point stubs for IDTs that stay unimplemented.

Second-batch implemented IDTs (C-Log2 / C-Log3 / Apple Log 1 / D-Log) live
in ``color.curves``. These remain stubs:

- Apple Log 2 (out of scope)
- DJI D-Log M (unsupported; 2017 D-Log + D-Gamut only)
- ARRI LogC3 (explicitly unsupported; M1 is LogC4)

Status: not implemented. Do not mark these cameras as supported.
"""

from __future__ import annotations

STUB_IDTS = (
    {
        "id": "apple_log2",
        "curve": "apple_log2",
        "gamut": "BT.2020 (typical; unverified)",
        "status": "stub",
        "note": "Apple Log 2 is out of scope. Apple Log 1 + BT.2020 is implemented (unverified).",
    },
    {
        "id": "dji_dlog_m",
        "curve": "dlog_m",
        "gamut": "DJI (unspecified)",
        "status": "stub",
        "note": "D-Log M is unsupported. DJI D-Log + D-Gamut (2017 white paper) is implemented (unverified).",
    },
    {
        "id": "arri_logc3",
        "curve": "logc3",
        "gamut": "AWG3 (unspecified)",
        "status": "stub",
        "note": "ARRI LogC3 is explicitly unsupported. Use LogC4 + AWG4.",
    },
)


def apple_log2_to_linear(_x):
    raise NotImplementedError(
        "Apple Log 2 is unsupported (out of scope). Use Apple Log 1 + BT.2020."
    )


def dlog_m_to_linear(_x):
    raise NotImplementedError(
        "DJI D-Log M is unsupported. Use D-Log + D-Gamut (2017 white paper)."
    )


def logc3_to_linear(_x):
    raise NotImplementedError(
        "ARRI LogC3 is unsupported. Use ARRI LogC4 + AWG4."
    )
