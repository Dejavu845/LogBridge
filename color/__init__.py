"""LogBridge color science (M1).

Internal: ACEScct (grading) after every IDT lands in ACES2065-1.
OCIO BuiltinTransform is used when PyOpenColorIO is importable and a
Builtin exists. Otherwise white-paper reference implementations (18% codes).
config.ocio always names the Builtins so Mac OCIO uses them.

Status of every IDT: implemented (unverified) until golden grey-card samples
are measured. Do not describe cameras as "supported".
"""

from .curves import (
    IDT_NAMES,
    decode_log,
    encode_log,
    logc4_to_linear,
    linear_to_logc4,
    slog3_to_linear,
    linear_to_slog3,
    vlog_to_linear,
    linear_to_vlog,
    flog2_to_linear,
    linear_to_flog2,
    nlog_to_linear,
    linear_to_nlog,
    log3g10_to_linear,
    linear_to_log3g10,
)
from .gamuts import GAMUTS, primaries_xy, rgb_to_xyz_matrix
from .pipeline import apply_idt, apply_odt_rec709, process_to_rec709
from .wb import bradford_cat_matrix, white_balance_matrix

__all__ = [
    "IDT_NAMES",
    "decode_log",
    "encode_log",
    "logc4_to_linear",
    "linear_to_logc4",
    "slog3_to_linear",
    "linear_to_slog3",
    "vlog_to_linear",
    "linear_to_vlog",
    "flog2_to_linear",
    "linear_to_flog2",
    "nlog_to_linear",
    "linear_to_nlog",
    "log3g10_to_linear",
    "linear_to_log3g10",
    "GAMUTS",
    "primaries_xy",
    "rgb_to_xyz_matrix",
    "apply_idt",
    "apply_odt_rec709",
    "process_to_rec709",
    "bradford_cat_matrix",
    "white_balance_matrix",
]

__version__ = "0.1.0"
