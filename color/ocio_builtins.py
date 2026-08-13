"""OCIO BuiltinTransform helpers.

config.ocio names Academy/vendor BuiltinTransform styles so Mac OpenColorIO
uses them. Python calls the same builtins when PyOpenColorIO is importable.

On Linux, system Python is often missing OCIO (externally-managed env; the
pytest command does not install it). Then color/ uses white-paper reference
implementations that match the documented 18% codes. Those references match
the builtins on 18% grey to well under 0.5%; they are not a second, more
accurate IDT.

F-Log2 and N-Log have no standard Builtin — keep the manufacturer papers.
Venice Builtins are used only when a Venice camera is detected, never as a
silent S-Log3 default.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

# Locked IDT -> OCIO BuiltinTransform style (camera log RGB -> ACES2065-1).
IDT_BUILTINS: dict[str, str] = {
    "arri_logc4_awg4": "ARRI_LOGC4_to_ACES2065-1",
    "sony_slog3_sgamut3": "SONY_SLOG3-SGAMUT3_to_ACES2065-1",
    "sony_slog3_sgamut3cine": "SONY_SLOG3-SGAMUT3.CINE_to_ACES2065-1",
    "sony_slog3_sgamut3_venice": "SONY_SLOG3-SGAMUT3-VENICE_to_ACES2065-1",
    "sony_slog3_sgamut3cine_venice": "SONY_SLOG3-SGAMUT3.CINE-VENICE_to_ACES2065-1",
    "panasonic_vlog_vgamut": "PANASONIC_VLOG-VGAMUT_to_ACES2065-1",
    "red_log3g10_rwg": "RED_LOG3G10-RWG_to_ACES2065-1",
}

# No standard Builtin (checked against BuiltinTransformRegistry).
HANDWRITTEN_IDTS = frozenset(
    {
        "fujifilm_flog2_bt2020",
        "nikon_nlog_bt2020",
    }
)

WORKING_BUILTIN_ACESCCT = "ACEScct_to_ACES2065-1"
WORKING_BUILTIN_ACESCG = "ACEScg_to_ACES2065-1"
ACES_AP0_TO_XYZ_D65 = "UTILITY - ACES-AP0_to_CIE-XYZ-D65_BFD"
ACES_AP1_TO_REC709 = "UTILITY - ACES-AP1_to_LINEAR-REC709_BFD"
CANON_CLOG2_CURVE = "CURVE - CANON_CLOG2_to_LINEAR"
CANON_CLOG2_IDT = "CANON_CLOG2-CGAMUT_to_ACES2065-1"

_OCIO = None
_OCIO_TRIED = False


def _import_ocio():
    global _OCIO, _OCIO_TRIED
    if _OCIO_TRIED:
        return _OCIO
    _OCIO_TRIED = True
    try:
        import PyOpenColorIO as ocio  # type: ignore
    except ImportError:
        try:
            import OpenColorIO as ocio  # type: ignore
        except ImportError:
            _OCIO = None
            return None
    _OCIO = ocio
    return _OCIO


def ocio_available() -> bool:
    """True when PyOpenColorIO/OpenColorIO imports and has BuiltinTransform."""
    ocio = _import_ocio()
    return ocio is not None and hasattr(ocio, "BuiltinTransform")


def builtin_style_for(idt_id: str) -> str | None:
    return IDT_BUILTINS.get(idt_id)


def list_registry() -> list[tuple[str, str]]:
    """Return (style, description) pairs from BuiltinTransformRegistry, or []."""
    ocio = _import_ocio()
    if ocio is None or not hasattr(ocio, "BuiltinTransformRegistry"):
        return []
    reg = ocio.BuiltinTransformRegistry()
    out: list[tuple[str, str]] = []
    for item in reg.getBuiltins():
        if isinstance(item, (tuple, list)) and len(item) >= 1:
            style = str(item[0])
            desc = str(item[1]) if len(item) > 1 else ""
            out.append((style, desc))
        else:
            out.append((str(item), ""))
    return out


def registry_styles() -> set[str]:
    return {style for style, _desc in list_registry()}


def apply_builtin(style: str, rgb, *, inverse: bool = False) -> np.ndarray:
    """Apply an OCIO BuiltinTransform to RGB (..., 3). Requires OCIO."""
    ocio = _import_ocio()
    if ocio is None:
        raise RuntimeError("OpenColorIO Python is not importable")
    arr = np.asarray(rgb, dtype=np.float32)
    shape = arr.shape
    flat = np.ascontiguousarray(arr.reshape(-1, 3))
    cfg = ocio.Config()
    cfg.setMajorVersion(2)
    bt = ocio.BuiltinTransform()
    bt.setStyle(style)
    if inverse:
        direction = getattr(ocio, "TRANSFORM_DIR_INVERSE", None)
        if direction is None:
            td = ocio.TransformDirection
            direction = getattr(td, "INVERSE", None) or getattr(td, "inverse", None)
        if direction is not None:
            bt.setDirection(direction)
    proc = cfg.getProcessor(bt).getDefaultCPUProcessor()
    proc.applyRGB(flat)
    return flat.reshape(shape).astype(np.float64)


def apply_builtin_idt(log_rgb, style: str) -> np.ndarray:
    """Camera log RGB (0-1, or already in the Builtin's domain) -> ACES2065-1."""
    return apply_builtin(style, log_rgb, inverse=False)


def print_registry(stream=None) -> None:
    """Print BuiltinTransformRegistry contents (or a missing-OCIO note)."""
    import sys

    out = stream or sys.stdout
    styles = list_registry()
    if not styles:
        print("OpenColorIO BuiltinTransformRegistry: none (OCIO Python not importable)", file=out)
        return
    ocio = _import_ocio()
    print(f"OpenColorIO {getattr(ocio, '__version__', '?')} BuiltinTransformRegistry ({len(styles)}):", file=out)
    for style, desc in styles:
        print(f"  {style}" + (f"  # {desc}" if desc else ""), file=out)


if __name__ == "__main__":
    print_registry()
