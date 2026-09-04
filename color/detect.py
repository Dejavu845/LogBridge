"""Clip curve+gamut detection order (Python mirror of the macOS detector).

Order:
  1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
  2. Filename / model hint
  3. User picker (paired IDTs; one-click process blocked until chosen)

NEVER trust QuickTime ``nclc`` to identify S-Log3 or LogC4.
NEVER default S-Log3 to S-Gamut3.Cine — if only S-Log3 is known, gamut is
unresolved and the user picker is required.
NEVER default C-Log2 or C-Log3 to Cinema Gamut — if only the curve is known,
gamut is unresolved and the user picker is required.
D-Log M stays unsupported. Apple Log 2 locks to Apple Wide Gamut (not
BT.2020). LogC3 locks to the EI800 + AWG3 pair only — never a bare LogC3.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .as_shot import AsShotWB, read_as_shot_wb
from .batch import (
    NOTE_CLOG2_NO_GAMUT,
    NOTE_CLOG3_NO_GAMUT,
    NOTE_DLOG_M,
    NOTE_FILENAME_APPLE_LOG,
    NOTE_FILENAME_APPLE_LOG2,
    NOTE_FILENAME_AWG3,
    NOTE_FILENAME_CLOG2_BT2020,
    NOTE_FILENAME_CLOG2_CGAMUT,
    NOTE_FILENAME_CLOG3_BT2020,
    NOTE_FILENAME_CLOG3_CGAMUT,
    NOTE_FILENAME_DLOG,
    NOTE_FILENAME_FLOG2,
    NOTE_FILENAME_LOG3G10,
    NOTE_FILENAME_LOGC3,
    NOTE_FILENAME_LOGC4,
    NOTE_FILENAME_NLOG,
    NOTE_FILENAME_SGAMUT3,
    NOTE_FILENAME_SGAMUT3_CINE,
    NOTE_FILENAME_VLOG,
    NOTE_META_APPLE_LOG,
    NOTE_META_APPLE_LOG2,
    NOTE_META_ARRI_MXF,
    NOTE_META_CLOG2_BT2020,
    NOTE_META_CLOG2_CGAMUT,
    NOTE_META_CLOG3_BT2020,
    NOTE_META_CLOG3_CGAMUT,
    NOTE_META_DLOG,
    NOTE_META_FUJI,
    NOTE_META_LOGC3,
    NOTE_META_NIKON,
    NOTE_META_PANA,
    NOTE_META_RED_RMD,
    NOTE_META_SONY,
    NOTE_META_SONY_VENICE,
    NOTE_MODEL_HINT,
    NOTE_SLOG3_NO_GAMUT,
    NOTE_SLOG3_NO_GAMUT_VENICE,
    NOTE_VENICE_PICK,
)
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
    ("apple log 2", "apple_log2_awg"),
    ("applelog2", "apple_log2_awg"),
    ("apple-log-2", "apple_log2_awg"),
    ("apple log", "apple_log_bt2020"),
    ("applelog", "apple_log_bt2020"),
    ("logc3", "arri_logc3_ei800_awg3"),
    ("logc 3", "arri_logc3_ei800_awg3"),
    ("awg3", "arri_logc3_ei800_awg3"),
    ("d-gamut", "dji_dlog_dgamut"),
    ("dgamut", "dji_dlog_dgamut"),
    ("d-log", "dji_dlog_dgamut"),
    ("dlog", "dji_dlog_dgamut"),
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
    "canon_clog2_cgamut": "C-Log2 + Cinema Gamut",
    "canon_clog2_bt2020": "C-Log2 + BT.2020",
    "canon_clog3_cgamut": "C-Log3 + Cinema Gamut",
    "canon_clog3_bt2020": "C-Log3 + BT.2020",
    "apple_log_bt2020": "Apple Log + BT.2020",
    "apple_log2_awg": "Apple Log 2 + Apple Wide Gamut",
    "dji_dlog_dgamut": "D-Log + D-Gamut",
    "arri_logc3_ei800_awg3": "LogC3 EI800 + AWG3",
}

SLOG3_PAIRS = ("sony_slog3_sgamut3", "sony_slog3_sgamut3cine")
SLOG3_VENICE_PAIRS = ("sony_slog3_sgamut3_venice", "sony_slog3_sgamut3cine_venice")
CLOG2_PAIRS = ("canon_clog2_cgamut", "canon_clog2_bt2020")
CLOG3_PAIRS = ("canon_clog3_cgamut", "canon_clog3_bt2020")
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
    as_shot_cct: float | None = None
    as_shot_tint: float = 0.0


_FILENAME_NOTE_BY_IDT = {
    "sony_slog3_sgamut3cine": NOTE_FILENAME_SGAMUT3_CINE,
    "sony_slog3_sgamut3cine_venice": NOTE_FILENAME_SGAMUT3_CINE,
    "sony_slog3_sgamut3": NOTE_FILENAME_SGAMUT3,
    "sony_slog3_sgamut3_venice": NOTE_FILENAME_SGAMUT3,
    "arri_logc4_awg4": NOTE_FILENAME_LOGC4,
    "panasonic_vlog_vgamut": NOTE_FILENAME_VLOG,
    "fujifilm_flog2_bt2020": NOTE_FILENAME_FLOG2,
    "nikon_nlog_bt2020": NOTE_FILENAME_NLOG,
    "red_log3g10_rwg": NOTE_FILENAME_LOG3G10,
    "apple_log2_awg": NOTE_FILENAME_APPLE_LOG2,
    "arri_logc3_ei800_awg3": NOTE_FILENAME_LOGC3,
    "apple_log_bt2020": NOTE_FILENAME_APPLE_LOG,
    "dji_dlog_dgamut": NOTE_FILENAME_DLOG,
    "canon_clog2_cgamut": NOTE_FILENAME_CLOG2_CGAMUT,
    "canon_clog2_bt2020": NOTE_FILENAME_CLOG2_BT2020,
    "canon_clog3_cgamut": NOTE_FILENAME_CLOG3_CGAMUT,
    "canon_clog3_bt2020": NOTE_FILENAME_CLOG3_BT2020,
}


def _filename_success_note(idt_id: str, token: str) -> str:
    if token == "awg3":
        return NOTE_FILENAME_AWG3
    if "cine" in token:
        return NOTE_FILENAME_SGAMUT3_CINE
    return _FILENAME_NOTE_BY_IDT.get(idt_id, f"文件名 {token}")


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


def _with_as_shot(d: Detection, as_shot: AsShotWB) -> Detection:
    """Attach camera-private as-shot CCT/tint. nclc never contributes."""
    return replace(d, as_shot_cct=as_shot.cct, as_shot_tint=float(as_shot.tint))


def _is_slog3(curve: str | None) -> bool:
    if not curve:
        return False
    c = curve.lower().replace("_", "-")
    return c in {"slog3", "s-log3"}


def _is_clog2(curve: str | None) -> bool:
    if not curve:
        return False
    c = curve.lower().replace("_", "-")
    return c in {"clog2", "c-log2"}


def _is_clog3(curve: str | None) -> bool:
    if not curve:
        return False
    c = curve.lower().replace("_", "-")
    return c in {"clog3", "c-log3"}


def picker_pairs(
    *,
    curve: str | None = None,
    venice_detected: bool = False,
    needs_picker: bool = True,
) -> list[str]:
    """Paired IDTs for the user picker. Never two independent lists.

    Venice pairs appear only if ``venice_detected``. S-Log3 without a locked
    gamut offers both S-Gamut3 and S-Gamut3.Cine — never a silent Cine default.
    C-Log2 / C-Log3 without a locked gamut offer Cinema Gamut and BT.2020 —
    never a silent Cinema Gamut default.
    """
    if needs_picker and _is_slog3(curve):
        return list(SLOG3_VENICE_PAIRS if venice_detected else SLOG3_PAIRS)
    if needs_picker and _is_clog2(curve):
        # Never a silent Cinema Gamut default.
        return list(CLOG2_PAIRS)
    if needs_picker and _is_clog3(curve):
        # Never a silent Cinema Gamut default.
        return list(CLOG3_PAIRS)
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


def _detect_from_metadata_idt(meta: dict) -> Detection | None:
    """Camera-private metadata only. Ignores QuickTime nclc / nclx / colr."""
    if not meta:
        return None
    # Explicitly ignore QuickTime tags even if present.
    forbidden = {"nclc", "nclx", "colr", "quicktime_nclc", "qt_nclc"}
    # A caller might pass nclc thinking it identifies LogC4/S-Log3. Drop it.
    cleaned = {k: v for k, v in meta.items() if k.lower() not in forbidden}

    arri = str(cleaned.get("arri_mxf_color_space", cleaned.get("arri_color_space", ""))).lower()
    if "logc4" in arri or "awg4" in arri or "wide gamut 4" in arri:
        return _pair("arri_logc4_awg4", "metadata", NOTE_META_ARRI_MXF)

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
                NOTE_META_SONY_VENICE if venice else NOTE_META_SONY,
            )
        if "s-gamut3" in sony or "sgamut3" in sony:
            return _pair(
                _sony_pair(False, venice),
                "metadata",
                NOTE_META_SONY_VENICE if venice else NOTE_META_SONY,
            )
        # Curve known, gamut not: do not default to Cine or Venice.
        return Detection(
            None,
            "slog3",
            None,
            "metadata",
            True,
            NOTE_SLOG3_NO_GAMUT_VENICE if venice else NOTE_SLOG3_NO_GAMUT,
            venice_detected=venice,
        )

    canon = str(cleaned.get("canon_vendor_gamma", cleaned.get("canon_log", ""))).lower()
    canon_gamut = str(
        cleaned.get("canon_vendor_gamut", cleaned.get("canon_gamut", ""))
    ).lower()
    if "c-log2" in canon or "clog2" in canon:
        if "cinema" in canon_gamut or "cgamut" in canon_gamut or "c-gamut" in canon_gamut:
            return _pair("canon_clog2_cgamut", "metadata", NOTE_META_CLOG2_CGAMUT)
        if "2020" in canon_gamut or "bt.2020" in canon_gamut or "bt2020" in canon_gamut:
            return _pair("canon_clog2_bt2020", "metadata", NOTE_META_CLOG2_BT2020)
        return Detection(
            None,
            "clog2",
            None,
            "metadata",
            True,
            NOTE_CLOG2_NO_GAMUT,
        )
    if "c-log3" in canon or "clog3" in canon:
        if "cinema" in canon_gamut or "cgamut" in canon_gamut or "c-gamut" in canon_gamut:
            return _pair("canon_clog3_cgamut", "metadata", NOTE_META_CLOG3_CGAMUT)
        if "2020" in canon_gamut or "bt.2020" in canon_gamut or "bt2020" in canon_gamut:
            return _pair("canon_clog3_bt2020", "metadata", NOTE_META_CLOG3_BT2020)
        return Detection(
            None,
            "clog3",
            None,
            "metadata",
            True,
            NOTE_CLOG3_NO_GAMUT,
        )

    rmd = str(cleaned.get("red_rmd_colorspace", cleaned.get("red_color_space", ""))).lower()
    rmd_gamma = str(cleaned.get("red_rmd_gamma", "")).lower()
    if "log3g10" in rmd or "log3g10" in rmd_gamma or "redwidegamut" in rmd:
        return _pair("red_log3g10_rwg", "metadata", NOTE_META_RED_RMD)

    fuji = str(cleaned.get("fuji_film_simulation", cleaned.get("fuji_log", ""))).lower()
    if "f-log2" in fuji or "flog2" in fuji:
        return _pair("fujifilm_flog2_bt2020", "metadata", NOTE_META_FUJI)

    nikon = str(cleaned.get("nikon_gamma", cleaned.get("nikon_nlog", ""))).lower()
    if "n-log" in nikon or "nlog" in nikon:
        return _pair("nikon_nlog_bt2020", "metadata", NOTE_META_NIKON)

    pana = str(cleaned.get("panasonic_gamma", "")).lower()
    if "v-log" in pana or "vlog" in pana:
        return _pair("panasonic_vlog_vgamut", "metadata", NOTE_META_PANA)

    apple = str(cleaned.get("apple_log", cleaned.get("apple_gamma", ""))).lower()
    if "apple log 2" in apple or "applelog2" in apple:
        return _pair(
            "apple_log2_awg",
            "metadata",
            NOTE_META_APPLE_LOG2,
        )
    if "apple log" in apple or "applelog" in apple:
        return _pair("apple_log_bt2020", "metadata", NOTE_META_APPLE_LOG)

    dji = str(cleaned.get("dji_gamma", cleaned.get("dji_log", ""))).lower()
    if "d-log m" in dji or "dlog m" in dji or "dlogm" in dji or "d-logm" in dji:
        return Detection(
            None,
            None,
            None,
            "metadata",
            True,
            NOTE_DLOG_M,
        )
    if "d-log" in dji or "dlog" in dji:
        return _pair("dji_dlog_dgamut", "metadata", NOTE_META_DLOG)

    arri_logc3 = str(cleaned.get("arri_mxf_color_space", cleaned.get("arri_color_space", ""))).lower()
    if "logc3" in arri_logc3 and "logc4" not in arri_logc3:
        return _pair(
            "arri_logc3_ei800_awg3",
            "metadata",
            NOTE_META_LOGC3,
        )

    return None


def _unsupported_filename(name: str) -> Detection | None:
    """D-Log M stays unresolved — never a silent IDT. No public decode/xy."""
    if "d-log m" in name or "dlog m" in name or "dlogm" in name or "d-logm" in name:
        return Detection(
            None,
            None,
            None,
            "filename",
            True,
            NOTE_DLOG_M,
        )
    return None


def detect_from_filename(path: str) -> Detection | None:
    name = Path(path).name.lower()
    blocked = _unsupported_filename(name)
    if blocked is not None:
        return blocked
    # C-Log2 / C-Log3 are paired — lock only when a gamut token is present.
    if "c-log2" in name or "clog2" in name:
        if "cinema" in name or "cgamut" in name or "c-gamut" in name:
            return _pair("canon_clog2_cgamut", "filename", NOTE_FILENAME_CLOG2_CGAMUT)
        if "bt.2020" in name or "bt2020" in name or "rec2020" in name or "rec.2020" in name:
            return _pair("canon_clog2_bt2020", "filename", NOTE_FILENAME_CLOG2_BT2020)
        return Detection(
            None,
            "clog2",
            None,
            "filename",
            True,
            NOTE_CLOG2_NO_GAMUT,
        )
    if "c-log3" in name or "clog3" in name:
        if "cinema" in name or "cgamut" in name or "c-gamut" in name:
            return _pair("canon_clog3_cgamut", "filename", NOTE_FILENAME_CLOG3_CGAMUT)
        if "bt.2020" in name or "bt2020" in name or "rec2020" in name or "rec.2020" in name:
            return _pair("canon_clog3_bt2020", "filename", NOTE_FILENAME_CLOG3_BT2020)
        return Detection(
            None,
            "clog3",
            None,
            "filename",
            True,
            NOTE_CLOG3_NO_GAMUT,
        )
    # Check more specific tokens first (already ordered).
    venice = _venice_hit(name)
    for token, idt_id in _FILENAME_HINTS:
        if token in name:
            if token in ("sgamut3", "s-gamut3") and "cine" in name:
                continue  # let the cine tokens win; they are listed first
            if "cine" in token:
                return _pair(
                    _sony_pair(True, venice),
                    "filename",
                    _filename_success_note(_sony_pair(True, venice), token),
                )
            if idt_id in ("sony_slog3_sgamut3", "sony_slog3_sgamut3cine"):
                pair = _sony_pair(False, venice)
                return _pair(pair, "filename", _filename_success_note(pair, token))
            return _pair(idt_id, "filename", _filename_success_note(idt_id, token))
    # S-Log3 without gamut token: do not assume Cine or Venice.
    if "s-log3" in name or "slog3" in name:
        return Detection(
            None,
            "slog3",
            None,
            "filename",
            True,
            NOTE_SLOG3_NO_GAMUT_VENICE if venice else NOTE_SLOG3_NO_GAMUT,
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
            NOTE_VENICE_PICK,
            venice_detected=True,
        )
    for token, idt_id in _MODEL_HINTS:
        if token in m:
            return _pair(idt_id, "model", NOTE_MODEL_HINT)
    return None


def detect_clip(
    path: str,
    metadata: dict | None = None,
    model: str | None = None,
    user_idt: str | None = None,
) -> Detection:
    """Full detection order. User picker is last and always honored if set.

    As-shot CCT/tint is read from camera-private metadata only (never nclc)
    and attached even when the IDT pair comes from filename/model/user.
    """
    as_shot = read_as_shot_wb(metadata or {})
    hit = detect_from_metadata(metadata or {})
    if hit is not None and not hit.needs_user_picker:
        return _with_as_shot(hit, as_shot)
    # Partial metadata (e.g. S-Log3 without gamut) still tries filename/model
    # for the missing piece, but never nclc.
    fn = detect_from_filename(path)
    if fn is not None and not fn.needs_user_picker:
        return _with_as_shot(fn, as_shot)
    md = detect_from_model(model or "")
    if md is not None:
        return _with_as_shot(md, as_shot)
    if user_idt:
        if user_idt not in IDT_PAIRS:
            raise KeyError(f"Unknown IDT {user_idt!r}")
        return _with_as_shot(_pair(user_idt, "user", "用户选择成对 IDT"), as_shot)
    # Prefer the most specific partial result so the UI can lock the curve.
    for partial in (hit, fn):
        if partial is not None:
            return _with_as_shot(partial, as_shot)
    return _with_as_shot(
        Detection(
            None,
            None,
            None,
            "unresolved",
            True,
            "读不到元数据，先选择 Log 与色域。",
        ),
        as_shot,
    )


def _attach_as_shot_from_meta(d: Detection | None, meta: dict | None) -> Detection | None:
    if d is None:
        return None
    return _with_as_shot(d, read_as_shot_wb(meta or {}))


def detect_from_metadata(meta: dict) -> Detection | None:
    """Camera-private metadata only. Ignores QuickTime nclc / nclx / colr.

    Attaches as-shot CCT/tint from the same camera-private keys (never nclc).
    """
    hit = _detect_from_metadata_idt(meta)
    if hit is None:
        return None
    return _with_as_shot(hit, read_as_shot_wb(meta))
