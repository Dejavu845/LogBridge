"""Fixed M1 pipeline: IDT -> scene-linear WB -> Rec.709 ODT.

Not a node editor. WB is a toggleable node on Resolve export; the Rec.709
preview path may apply WB for viewing without baking it as the only
deliverable.
"""

from __future__ import annotations

import numpy as np

from . import curves
from .gamuts import IDT_PAIRS, rgb_to_rgb_matrix
from .rec709 import rec709_oetf
from .wb import apply_white_balance


def apply_idt(log_rgb, idt_id: str) -> np.ndarray:
    """Camera log RGB -> scene-linear camera RGB.

    Nikon N-Log IDT expects 10-bit code values (0-1023), not 0-1.
    All other IDTs expect normalized 0-1 log.
    """
    curve, _gamut = IDT_PAIRS[idt_id]
    return curves.decode_log(curve, np.asarray(log_rgb, dtype=np.float64))


def camera_linear_to_working(lin_rgb, idt_id: str, working: str = "DWG") -> np.ndarray:
    """Scene-linear camera RGB -> scene-linear working RGB (default DWG)."""
    _curve, gamut = IDT_PAIRS[idt_id]
    m = rgb_to_rgb_matrix(gamut, working)
    rgb = np.asarray(lin_rgb, dtype=np.float64)
    return rgb @ m.T


def apply_odt_rec709(working_lin, working: str = "DWG"):
    """Scene-linear working RGB -> Rec.709 encoded RGB.

    Tags conceptually as Rec.709. No tone-mapping RRT; 18% grey will encode
    near the Rec.709 OETF of 0.18 (~0.409). Implemented (unverified).
    """
    m = rgb_to_rgb_matrix(working, "Rec709")
    rgb = np.asarray(working_lin, dtype=np.float64)
    rec_lin = rgb @ m.T
    return rec709_oetf(np.clip(rec_lin, 0.0, None))


def process_to_rec709(
    log_rgb,
    idt_id: str,
    *,
    apply_wb: bool = False,
    cct: float = 6504.0,
    tint: float = 0.0,
    working: str = "DWG",
    wb_method: str = "bradford",
) -> np.ndarray:
    """Full fixed pipeline to Rec.709 encoded RGB."""
    cam_lin = apply_idt(log_rgb, idt_id)
    work_lin = camera_linear_to_working(cam_lin, idt_id, working=working)
    if apply_wb:
        work_lin = apply_white_balance(
            work_lin, cct, tint=tint, rgb_space=working, method=wb_method
        )
    return apply_odt_rec709(work_lin, working=working)
