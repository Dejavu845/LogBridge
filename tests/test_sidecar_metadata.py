"""Sidecar `{stem}.json` uses the same keys as color/detect.py and color/as_shot.py.

Clip `foo.mov` reads `foo.json` (`appendingPathExtension("json")`).
Python `detect_from_metadata` / `read_as_shot_wb` parse that object.
`fps` is `BatchClip.fps`. Missing or bad fps stays empty — never 24 or 30.
S-Log3 without a gamut does not become S-Gamut3.Cine.
"""

import json
import re
from pathlib import Path

import pytest

from color.as_shot import _CCT_KEYS, _TINT_KEYS, read_as_shot_wb
from color.batch import (
    NOTE_CLOG2_NO_GAMUT,
    NOTE_CLOG3_NO_GAMUT,
    NOTE_DLOG_M,
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
    NOTE_SLOG3_NO_GAMUT,
    NOTE_SLOG3_NO_GAMUT_VENICE,
    BatchClip,
)
from color.detect import detect_from_metadata

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sidecar"
DETECTOR = ROOT / "macos/LogBridge/LogBridge/Detection/ClipDetector.swift"
DETECT_PY = ROOT / "color/detect.py"

_BANNED_COPY = ("支持", "一键", "精准", "成片")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(src: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


def parse_sidecar_fps(value):
    """Positive finite `fps` only. Missing, bool, or junk stays None.

    Matches ClipDetector.parsePositiveRate. A camera that wrote 24 is kept.
    A missing key is not filled with 24 or 30.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if number != number or number <= 0:
        return None
    return number


def _detect_get_keys() -> list[str]:
    src = DETECT_PY.read_text(encoding="utf-8")
    fn = src.split("def _detect_from_metadata_idt")[1].split("\ndef ")[0]
    return re.findall(r'\.get\(\s*"([^"]+)"', fn)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_sidecar_filename_is_stem_json_and_keys_match_python():
    detector = _read(DETECTOR)
    assert 'appendingPathExtension("json")' in detector
    assert "func sidecarJSONURL" in detector
    assert "deletingPathExtension()" in detector.split("func sidecarJSONURL")[1].split("func ")[0]

    keys = _detect_get_keys()
    assert "sony_acquisition_gamma" in keys
    assert "sony_acquisition_gamut" in keys
    assert "arri_mxf_color_space" in keys
    for key in keys:
        assert f'"{key}"' in detector, key
    for key in _CCT_KEYS:
        assert f'"{key}"' in detector, key
    for key in _TINT_KEYS:
        assert f'"{key}"' in detector, key
    assert "fps" in BatchClip.__dataclass_fields__
    rate = detector.split("func readSidecarFrameRate")[1].split("private static func")[0]
    assert 'meta["fps"]' in rate
    code = _code(rate)
    assert "24" not in code
    assert "30" not in code
    assert "var fps: Double? = nil" in detector
    assert "result.fps = readSidecarFrameRate" in detector


def test_metadata_notes_match_python_and_skip_banned_words():
    detector = _read(DETECTOR)
    notes = (
        NOTE_META_ARRI_MXF,
        NOTE_META_SONY,
        NOTE_META_SONY_VENICE,
        NOTE_META_CLOG2_CGAMUT,
        NOTE_META_CLOG2_BT2020,
        NOTE_META_CLOG3_CGAMUT,
        NOTE_META_CLOG3_BT2020,
        NOTE_META_RED_RMD,
        NOTE_META_FUJI,
        NOTE_META_NIKON,
        NOTE_META_PANA,
        NOTE_META_APPLE_LOG2,
        NOTE_META_APPLE_LOG,
        NOTE_META_DLOG,
        NOTE_META_LOGC3,
        NOTE_SLOG3_NO_GAMUT,
        NOTE_SLOG3_NO_GAMUT_VENICE,
        NOTE_CLOG2_NO_GAMUT,
        NOTE_CLOG3_NO_GAMUT,
        NOTE_DLOG_M,
    )
    for note in notes:
        assert note in detector
    literals = re.findall(r'note: "([^"]+)"', detector)
    for note in literals:
        if note == NOTE_DLOG_M:
            continue
        for word in _BANNED_COPY:
            assert word not in note, note


def test_sony_sgamut3_fixture_locks_pair_not_cine():
    meta = _load("sony_slog3_sgamut3.json")
    d = detect_from_metadata(meta)
    assert d.idt_id == "sony_slog3_sgamut3"
    assert d.gamut == "SGamut3"
    assert d.needs_user_picker is False
    assert d.note == NOTE_META_SONY
    assert d.as_shot_cct == pytest.approx(5600)
    assert d.as_shot_tint == pytest.approx(1.5)
    assert parse_sidecar_fps(meta["fps"]) == pytest.approx(25)
    assert d.idt_id != "sony_slog3_sgamut3cine"
    # nclc is in the file and is not the IDT.
    assert meta["nclc"] == "1-1-1"


def test_explicit_cine_venice_is_the_venice_cine_pair():
    meta = _load("sony_slog3_sgamut3cine_venice.json")
    d = detect_from_metadata(meta)
    assert d.idt_id == "sony_slog3_sgamut3cine_venice"
    assert d.venice_detected is True
    assert d.note == NOTE_META_SONY_VENICE
    shot = read_as_shot_wb(meta)
    assert shot.cct == pytest.approx(3200)
    assert shot.tint == pytest.approx(-0.25)
    assert parse_sidecar_fps(meta["fps"]) == pytest.approx(23.976)


def test_slog3_without_gamut_does_not_default_cine_or_fps():
    meta = _load("sony_slog3_no_gamut.json")
    d = detect_from_metadata(meta)
    assert d.idt_id is None
    assert d.gamut is None
    assert d.needs_user_picker is True
    assert d.note == NOTE_SLOG3_NO_GAMUT
    assert d.venice_detected is False
    assert d.as_shot_cct == pytest.approx(4500)
    assert "fps" not in meta
    assert parse_sidecar_fps(meta.get("fps")) is None
    assert parse_sidecar_fps(meta.get("fps")) not in (24, 30, 24.0, 30.0)

    detector = _read(DETECTOR)
    sony = detector.split("func readSonyAcquisition")[1].split("private static func")[0]
    assert sony.index('contains("cine")') < sony.index('contains("s-gamut3")')
    assert "idt: nil" in sony
    assert ".sonySLog3SGamut3Cine" in sony.split('contains("cine")')[1].split('contains("s-gamut3")')[0]


def test_nclc_alone_does_not_lock_slog3():
    meta = _load("nclc_only.json")
    assert detect_from_metadata(meta) is None
    shot = read_as_shot_wb(meta)
    assert shot.cct is None
    assert parse_sidecar_fps(meta.get("fps")) is None


def test_arri_and_canon_and_red_fixtures_match_python():
    logc4 = _load("arri_logc4.json")
    d = detect_from_metadata(logc4)
    assert d.idt_id == "arri_logc4_awg4"
    assert d.note == NOTE_META_ARRI_MXF
    assert d.as_shot_cct == pytest.approx(3200)
    assert d.as_shot_tint == pytest.approx(-0.5)
    # 24 is what this camera wrote. It is not a fallback.
    assert parse_sidecar_fps(logc4["fps"]) == pytest.approx(24)
    assert logc4["fps"] == 24

    logc3 = _load("arri_logc3.json")
    d3 = detect_from_metadata(logc3)
    assert d3.idt_id == "arri_logc3_ei800_awg3"
    assert d3.note == NOTE_META_LOGC3
    assert d3.as_shot_cct == pytest.approx(5000)
    assert parse_sidecar_fps(logc3["fps"]) == pytest.approx(48)

    canon = _load("canon_clog3_no_gamut.json")
    dc = detect_from_metadata(canon)
    assert dc.idt_id is None
    assert dc.gamut is None
    assert dc.needs_user_picker is True
    assert dc.note == NOTE_CLOG3_NO_GAMUT
    assert dc.as_shot_cct == pytest.approx(4500)
    assert parse_sidecar_fps(canon.get("fps")) is None

    red = _load("red_log3g10.json")
    dr = detect_from_metadata(red)
    assert dr.idt_id == "red_log3g10_rwg"
    assert dr.note == NOTE_META_RED_RMD
    assert dr.as_shot_cct == pytest.approx(5600)
    assert parse_sidecar_fps(red["fps"]) == pytest.approx(96)

    pana = _load("panasonic_vlog.json")
    dp = detect_from_metadata(pana)
    assert dp.idt_id == "panasonic_vlog_vgamut"
    assert dp.note == NOTE_META_PANA
    assert parse_sidecar_fps(pana["fps"]) == pytest.approx(50)


def test_empty_and_broken_sidecar_do_not_guess():
    empty = _load("empty.json")
    assert detect_from_metadata(empty) is None
    assert read_as_shot_wb(empty).cct is None
    assert parse_sidecar_fps(empty.get("fps")) is None

    with pytest.raises(json.JSONDecodeError):
        json.loads((FIXTURES / "broken.json").read_text(encoding="utf-8"))

    detector = _read(DETECTOR)
    loader = detector.split("func loadSidecarJSON")[1].split("static func readAsShotWB(url:")[0]
    assert "try? JSONSerialization.jsonObject" in loader
    assert "return nil" in loader
    assert "24" not in _code(loader)
    assert "30" not in _code(loader)

    for bad in (None, True, False, 0, -1, "fast", "24 fps", {}, []):
        assert parse_sidecar_fps(bad) is None


def test_swift_readers_no_longer_ignore_the_sidecar():
    detector = _read(DETECTOR)
    for name in ("func readARRIColorSpace", "func readSonyAcquisition", "func readCanonVendor"):
        body = detector.split(name)[1].split("private static func")[0]
        assert "_ = url" not in body
        assert "loadSidecarJSON" in body
    assert "locked(.redLog3G10RWG, source: .metadata" not in detector
    rmd = detector.split("func readREDRMD")[1].split("}")[0]
    assert "needsUserPicker: true" in rmd
    assert "检测到 RED RMD，先选择成对 IDT" in rmd
    assert "locked(.redLog3G10RWG" not in rmd
