"""Clip curve+gamut detection order (Python mirror of the macOS detector).

Order:
  1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
  2. Filename / model hint
  3. User picker (paired IDTs; one-click process blocked until chosen)

NEVER trust QuickTime ``nclc`` to identify S-Log3 or LogC4.
NEVER default S-Log3 to S-Gamut3.Cine — if only S-Log3 is known, gamut is
unresolved and the user picker is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .gamuts import IDT_PAIRS, VENICE_IDTS


def _venice_hit(*parts: str) -> bool:
    """True only when a Venice camera token is present. Never a silent default."""
    blob = " ".join(p or "" for p in parts).lower()
    return "venice" in blob


def _sony_pair(gamut_cine: bool, venice: bool) -> str:
    if venice:
        return "sony_slog3_sgamut3cine_venice" if gamut_cine else "sony_slog3_sgamut3_venice"
    return "sony_slog3_sgamut3cine" if gamut_cine else "sony_slog3_sgamut3"

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


# UI labels for the paired IDT picker (never two independent lists).
IDT_PAIR_LABELS = {
    "arri_logc4_awg4": "LogC4 + AWG4",
    "sony_slog3_sgamut3": "S-Log3 + S-Gamut3",
    "sony_slog3_sgamut3cine": "S-Log3 + S-Gamut3.Cine",
    "sony_slog3_sgamut3_venice": "S-Log3 + S-Gamut3 (Venice)",
    "sony_slog3_sgamut3cine_venice": "S-Log3 + S-Gamut3.Cine (Venice)",
    "panasonic_vlog_vgamut": "V-Log + V-Gamut",
    "fujifilm_flog2_bt2020": "F-Log2 + BT.2020",
    "nikon_nlog_bt2020": "N-Log + BT.2020",
    "red_log3g10_rwg": "Log3G10 + REDWideGamutRGB",
}

SLOG3_PAIRS = ("sony_slog3_sgamut3", "sony_slog3_sgamut3cine")
SLOG3_VENICE_PAIRS = ("sony_slog3_sgamut3_venice", "sony_slog3_sgamut3cine_venice")
IMPLEMENTED_NON_VENICE = tuple(k for k in IDT_PAIRS if k not in VENICE_IDTS)


@dataclass(frozen=True)
class Detection:
    idt_id: str | None
    curve: str | None
    gamut: str | None
    source: str  # metadata | filename | model | user | unresolved
    needs_user_picker: bool
    note: str
    venice_detected: bool = False


def _pair(idt_id: str, source: str, note: str) -> Detection:
    curve, gamut = IDT_PAIRS[idt_id]
    return Detection(
        idt_id,
        curve,
        gamut,
        source,
        False,
        note,
        venice_detected=idt_id in VENICE_IDTS,
    )


def _is_slog3(curve: str | None) -> bool:
    if not curve:
        return False
    c = curve.lower().replace("_", "-")
    return c in {"slog3", "s-log3"}


def picker_pairs(
    *,
    curve: str | None = None,
    venice_detected: bool = False,
    needs_picker: bool = True,
) -> list[str]:
    """Paired IDTs for the user picker. Never two independent lists.

    Venice pairs appear only if ``venice_detected``. S-Log3 without a locked
    gamut offers both S-Gamut3 and S-Gamut3.Cine — never a silent Cine default.
    """
    if needs_picker and _is_slog3(curve):
        return list(SLOG3_VENICE_PAIRS if venice_detected else SLOG3_PAIRS)
    out = list(IMPLEMENTED_NON_VENICE)
    if venice_detected:
        try:
            i = out.index("sony_slog3_sgamut3cine") + 1
            out[i:i] = list(SLOG3_VENICE_PAIRS)
        except ValueError:
            out.extend(SLOG3_VENICE_PAIRS)
    return out


def picker_pairs_for_detection(d: Detection) -> list[str]:
    return picker_pairs(
        curve=d.curve,
        venice_detected=d.venice_detected,
        needs_picker=d.needs_user_picker,
    )


def picker_labels(ids: list[str] | None = None, **kwargs) -> list[tuple[str, str]]:
    """``(idt_id, 'Curve + Gamut')`` rows for the paired picker."""
    if ids is None:
        ids = picker_pairs(**kwargs)
    return [(i, IDT_PAIR_LABELS[i]) for i in ids]


def can_one_click_process(detection: Detection) -> bool:
    """False until a locked implemented pair exists. Block silent defaults."""
    if detection.needs_user_picker or not detection.idt_id:
        return False
    return detection.idt_id in IDT_PAIRS


def can_one_click_process_all(detections: list[Detection]) -> bool:
    return bool(detections) and all(can_one_click_process(d) for d in detections)


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
    venice = _venice_hit(
        sony,
        sony_curve,
        str(cleaned.get("sony_camera_model", "")),
        str(cleaned.get("camera_model", "")),
        str(cleaned.get("sony_model", "")),
    )
    if "s-log3" in sony_curve or "slog3" in sony_curve or "s-log3" in sony:
        if "cine" in sony:
            return _pair(
                _sony_pair(True, venice),
                "metadata",
                "Sony Acquisition metadata" + (" (Venice)" if venice else ""),
            )
        if "s-gamut3" in sony or "sgamut3" in sony:
            return _pair(
                _sony_pair(False, venice),
                "metadata",
                "Sony Acquisition metadata" + (" (Venice)" if venice else ""),
            )
        # Curve known, gamut not: do not default to Cine or Venice.
        return Detection(
            None,
            "slog3",
            None,
            "metadata",
            True,
            "S-Log3 from Sony metadata without gamut; pick a paired IDT "
            "(S-Log3 + S-Gamut3 or S-Log3 + S-Gamut3.Cine). Never default Cine"
            + (" (Venice pairs offered — Venice body detected)" if venice else ""),
            venice_detected=venice,
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
    venice = _venice_hit(name)
    for token, idt_id in _FILENAME_HINTS:
        if token in name:
            if token in ("sgamut3", "s-gamut3") and "cine" in name:
                continue  # let the cine tokens win; they are listed first
            if "cine" in token:
                return _pair(_sony_pair(True, venice), "filename", f"filename token {token!r}")
            if idt_id in ("sony_slog3_sgamut3", "sony_slog3_sgamut3cine"):
                return _pair(_sony_pair(False, venice), "filename", f"filename token {token!r}")
            return _pair(idt_id, "filename", f"filename token {token!r}")
    # S-Log3 without gamut token: do not assume Cine or Venice.
    if "s-log3" in name or "slog3" in name:
        return Detection(
            None,
            "slog3",
            None,
            "filename",
            True,
            "S-Log3 in filename without gamut; pick a paired IDT "
            "(S-Log3 + S-Gamut3 or S-Log3 + S-Gamut3.Cine). Never default Cine"
            + (" (Venice pairs offered)" if venice else ""),
            venice_detected=venice,
        )
    return None


def detect_from_model(model: str) -> Detection | None:
    m = (model or "").lower()
    if _venice_hit(m):
        # Venice body is not an IDT by itself — gamut still required. Never default.
        return Detection(
            None,
            "slog3",
            None,
            "model",
            True,
            "Venice camera detected; pick a paired IDT "
            "(S-Log3 + S-Gamut3 (Venice) or S-Log3 + S-Gamut3.Cine (Venice)). Never default.",
            venice_detected=True,
        )
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
