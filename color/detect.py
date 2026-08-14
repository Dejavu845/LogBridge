"""Clip curve+gamut detection order (Python mirror of the macOS detector).

Order:
  1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
  2. Filename / model hint
  3. User picker

NEVER trust QuickTime ``nclc`` to identify S-Log3 or LogC4.
NEVER default S-Log3 to S-Gamut3.Cine — if only S-Log3 is known, gamut is
unresolved and the user picker is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .gamuts import IDT_PAIRS

# Filename tokens that hint a locked pair. Lowercase matching.
_FILENAME_HINTS = (
    ("logc4", "arri_logc4_awg4"),
    ("logc 4", "arri_logc4_awg4"),
    ("awg4", "arri_logc4_awg4"),
    ("sgamut3.cine", "sony_slog3_sgamut3cine"),
    ("s-gamut3.cine", "sony_slog3_sgamut3cine"),
    ("sgamut3cine", "sony_slog3_sgamut3cine"),
    ("sgamut3_cine", "sony_slog3_sgamut3cine"),
    ("s-gamut3.cine", "sony_slog3_sgamut3cine"),
    ("sgamut3", "sony_slog3_sgamut3"),
    ("s-gamut3", "sony_slog3_sgamut3"),
    ("v-log", "panasonic_vlog_vgamut"),
    ("vlog", "panasonic_vlog_vgamut"),
    ("vgamut", "panasonic_vlog_vgamut"),
    ("f-log2", "fujifilm_flog2_bt2020"),
    ("flog2", "fujifilm_flog2_bt2020"),
    ("n-log", "nikon_nlog_bt2020"),
    ("nlog", "nikon_nlog_bt2020"),
    ("log3g10", "red_log3g10_rwg"),
    ("redwidegamut", "red_log3g10_rwg"),
    ("rwg", "red_log3g10_rwg"),
)

# Model tokens. S-Log3 cameras do not imply Cine gamut.
_MODEL_HINTS = (
    ("alexa 35", "arri_logc4_awg4"),
    ("alexa35", "arri_logc4_awg4"),
    ("alexa 265", "arri_logc4_awg4"),
    ("varicam", "panasonic_vlog_vgamut"),
    ("komodo", "red_log3g10_rwg"),
    ("v-raptor", "red_log3g10_rwg"),
    ("dsmc2", "red_log3g10_rwg"),
)


@dataclass(frozen=True)
class Detection:
    idt_id: str | None
    curve: str | None
    gamut: str | None
    source: str  # metadata | filename | model | user | unresolved
    needs_user_picker: bool
    note: str


def _pair(idt_id: str, source: str, note: str) -> Detection:
    curve, gamut = IDT_PAIRS[idt_id]
    return Detection(idt_id, curve, gamut, source, False, note)


def detect_from_metadata(meta: dict) -> Detection | None:
    """Camera-private metadata only. Ignores QuickTime nclc / nclx / colr."""
    if not meta:
        return None
    # Explicitly ignore QuickTime tags even if present.
    forbidden = {"nclc", "nclx", "colr", "quicktime_nclc", "qt_nclc"}
    # A caller might pass nclc thinking it identifies LogC4/S-Log3. Drop it.
    cleaned = {k: v for k, v in meta.items() if k.lower() not in forbidden}

    arri = str(cleaned.get("arri_mxf_color_space", cleaned.get("arri_color_space", ""))).lower()
    if "logc4" in arri or "awg4" in arri or "wide gamut 4" in arri:
        return _pair("arri_logc4_awg4", "metadata", "ARRI MXF color space")

    sony = str(
        cleaned.get("sony_acquisition_gamut", cleaned.get("sony_color_gamut", ""))
    ).lower()
    sony_curve = str(cleaned.get("sony_acquisition_gamma", "")).lower()
    if "s-log3" in sony_curve or "slog3" in sony_curve or "s-log3" in sony:
        if "cine" in sony:
            return _pair(
                "sony_slog3_sgamut3cine", "metadata", "Sony Acquisition metadata"
            )
        if "s-gamut3" in sony or "sgamut3" in sony:
            return _pair("sony_slog3_sgamut3", "metadata", "Sony Acquisition metadata")
        # Curve known, gamut not: do not default to Cine.
        return Detection(
            None,
            "slog3",
            None,
            "metadata",
            True,
            "S-Log3 from Sony metadata without gamut; user must pick S-Gamut3 or S-Gamut3.Cine",
        )

    canon = str(cleaned.get("canon_vendor_gamma", cleaned.get("canon_log", ""))).lower()
    if "c-log2" in canon or "clog2" in canon or "c-log3" in canon or "clog3" in canon:
        return Detection(
            None,
            None,
            None,
            "metadata",
            True,
            "Canon C-Log detected; IDT is a stub (use OCIO CURVE - CANON_CLOG2_to_LINEAR)",
        )

    rmd = str(cleaned.get("red_rmd_colorspace", cleaned.get("red_color_space", ""))).lower()
    rmd_gamma = str(cleaned.get("red_rmd_gamma", "")).lower()
    if "log3g10" in rmd or "log3g10" in rmd_gamma or "redwidegamut" in rmd:
        return _pair("red_log3g10_rwg", "metadata", "RED RMD")

    fuji = str(cleaned.get("fuji_film_simulation", cleaned.get("fuji_log", ""))).lower()
    if "f-log2" in fuji or "flog2" in fuji:
        return _pair("fujifilm_flog2_bt2020", "metadata", "Fujifilm metadata")

    nikon = str(cleaned.get("nikon_gamma", cleaned.get("nikon_nlog", ""))).lower()
    if "n-log" in nikon or "nlog" in nikon:
        return _pair("nikon_nlog_bt2020", "metadata", "Nikon metadata")

    pana = str(cleaned.get("panasonic_gamma", "")).lower()
    if "v-log" in pana or "vlog" in pana:
        return _pair("panasonic_vlog_vgamut", "metadata", "Panasonic metadata")

    return None


def detect_from_filename(path: str) -> Detection | None:
    name = Path(path).name.lower()
    # Check more specific tokens first (already ordered).
    for token, idt_id in _FILENAME_HINTS:
        if token in name:
            if token in ("sgamut3", "s-gamut3") and "cine" in name:
                continue  # let the cine tokens win; they are listed first
            return _pair("sony_slog3_sgamut3cine" if "cine" in token else idt_id, "filename", f"filename token {token!r}")
    # S-Log3 without gamut token: do not assume Cine.
    if "s-log3" in name or "slog3" in name:
        return Detection(
            None,
            "slog3",
            None,
            "filename",
            True,
            "S-Log3 in filename without gamut; user must pick S-Gamut3 or S-Gamut3.Cine (never default Cine)",
        )
    return None


def detect_from_model(model: str) -> Detection | None:
    m = (model or "").lower()
    for token, idt_id in _MODEL_HINTS:
        if token in m:
            return _pair(idt_id, "model", f"camera model {token!r}")
    return None


def detect_clip(
    path: str,
    metadata: dict | None = None,
    model: str | None = None,
    user_idt: str | None = None,
) -> Detection:
    """Full detection order. User picker is last and always honored if set."""
    hit = detect_from_metadata(metadata or {})
    if hit is not None and not hit.needs_user_picker:
        return hit
    # Partial metadata (e.g. S-Log3 without gamut) still tries filename/model
    # for the missing piece, but never nclc.
    fn = detect_from_filename(path)
    if fn is not None and not fn.needs_user_picker:
        return fn
    md = detect_from_model(model or "")
    if md is not None:
        return md
    if user_idt:
        if user_idt not in IDT_PAIRS:
            raise KeyError(f"Unknown IDT {user_idt!r}")
        return _pair(user_idt, "user", "user picker")
    # Prefer the most specific partial result so the UI can lock the curve.
    for partial in (hit, fn):
        if partial is not None:
            return partial
    return Detection(
        None,
        None,
        None,
        "unresolved",
        True,
        "No camera-private metadata or filename/model hint; user picker required. QuickTime nclc is never used.",
    )
