"""Extension-point stubs for IDTs not in M1.

Canon C-Log2 has a negative toe. Do not invent a mirrored-toe analytic
curve. Use the official OCIO builtin or ACES CLF:

    CURVE - CANON_CLOG2_to_LINEAR

Apple Log and DJI D-Log are placeholders only.
Status: not implemented. Do not mark these cameras as supported.
"""

from __future__ import annotations

CANON_CLOG2_OCIO_BUILTIN = "CURVE - CANON_CLOG2_to_LINEAR"
CANON_CLOG3_OCIO_BUILTIN = "CURVE - CANON_CLOG3_to_LINEAR"

STUB_IDTS = (
    {
        "id": "canon_clog2",
        "curve": "clog2",
        "gamut": "Cinema Gamut / BT.2020 (unspecified until IDT lands)",
        "status": "stub",
        "note": (
            "C-Log2 negative toe: use OCIO builtin "
            f"{CANON_CLOG2_OCIO_BUILTIN} or the ACES CLF. "
            "Do not invent a mirrored toe."
        ),
    },
    {
        "id": "canon_clog3",
        "curve": "clog3",
        "gamut": "Cinema Gamut / BT.2020 (unspecified until IDT lands)",
        "status": "stub",
        "note": f"Use OCIO builtin {CANON_CLOG3_OCIO_BUILTIN} or ACES CLF when landing this IDT.",
    },
    {
        "id": "apple_log",
        "curve": "apple_log",
        "gamut": "BT.2020 (typical; unverified)",
        "status": "stub",
        "note": "Apple Log IDT is out of scope for M1.",
    },
    {
        "id": "dji_dlog",
        "curve": "dlog",
        "gamut": "DJI D-Gamut (unspecified until IDT lands)",
        "status": "stub",
        "note": "DJI D-Log IDT is out of scope for M1.",
    },
)


def clog2_to_linear(_x):
    """Not implemented. C-Log2 negative toe must come from OCIO/ACES CLF."""
    raise NotImplementedError(
        "Canon C-Log2 is a stub. Use OCIO "
        f"{CANON_CLOG2_OCIO_BUILTIN} / ACES CLF; do not invent a mirrored toe."
    )


def clog3_to_linear(_x):
    raise NotImplementedError(
        "Canon C-Log3 is a stub. Use OCIO "
        f"{CANON_CLOG3_OCIO_BUILTIN} / ACES CLF."
    )


def apple_log_to_linear(_x):
    raise NotImplementedError("Apple Log IDT is a stub (out of scope for M1).")


def dlog_to_linear(_x):
    raise NotImplementedError("DJI D-Log IDT is a stub (out of scope for M1).")
