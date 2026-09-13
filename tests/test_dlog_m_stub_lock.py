"""Cycle 21: Swift FutureIDTs keeps D-Log M as an unsupported stub.

Does not implement a transfer. Does not add dji_dlog_m to IDT_PAIRS.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUTURE = ROOT / "macos" / "LogBridge" / "LogBridge" / "Stubs" / "FutureIDTs.swift"


def test_future_idts_dlog_m_stays_unsupported():
    text = FUTURE.read_text(encoding="utf-8")
    assert FUTURE.stat().st_size >= 200
    assert "DJI D-Log M" in text
    assert "Unsupported" in text
    assert "2017" in text
    assert "dLogMIsSupported" in text
    assert "-> Bool { false }" in text
    assert "pow(" not in text
    assert "log2" not in text.lower()
    assert "return linear" not in text.lower()


def test_picker_never_offers_dlog_m():
    """Cycle 22: the paired picker must not list the stub camera."""
    from color.detect import picker_pairs

    assert "dji_dlog_m" not in picker_pairs()
    assert "dji_dlog_m" not in picker_pairs(venice_detected=True)
    assert "dji_dlog_m" not in picker_pairs(curve="s-log3", needs_picker=True)
    assert "dji_dlog_m" not in picker_pairs(curve="c-log3", needs_picker=True)


def test_swift_idt_picker_excludes_stub():
    """Cycle 23: Swift pickerPairs uses implemented (no stubs), not allCases."""
    idt = ROOT / "macos" / "LogBridge" / "LogBridge" / "Models" / "IDT.swift"
    text = idt.read_text(encoding="utf-8")
    assert "allCases.filter { !$0.isStub }" in text
    start = text.find("static func pickerPairs")
    assert start > 0
    end = text.find("static func isSLog3", start)
    chunk = text[start:end]
    assert "allCases" not in chunk
    assert ".djiDLogMStub" not in chunk
    assert "implemented.filter" in chunk


def test_swift_python_curve_picker_ids_match():
    """Cycle 24: Swift pickerPairs case lists match Python pair tuples."""
    from color.detect import CLOG2_PAIRS, CLOG3_PAIRS, SLOG3_PAIRS, SLOG3_VENICE_PAIRS

    idt = ROOT / "macos" / "LogBridge" / "LogBridge" / "Models" / "IDT.swift"
    text = idt.read_text(encoding="utf-8")
    start = text.find("static func pickerPairs")
    end = text.find("static func isSLog3", start)
    chunk = text[start:end]
    assert "[.sonySLog3SGamut3, .sonySLog3SGamut3Cine]" in chunk
    assert "[.sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice]" in chunk
    assert "[.canonCLog2CGamut, .canonCLog2BT2020]" in chunk
    assert "[.canonCLog3CGamut, .canonCLog3BT2020]" in chunk
    assert SLOG3_PAIRS == ("sony_slog3_sgamut3", "sony_slog3_sgamut3cine")
    assert SLOG3_VENICE_PAIRS == (
        "sony_slog3_sgamut3_venice",
        "sony_slog3_sgamut3cine_venice",
    )
    assert CLOG2_PAIRS == ("canon_clog2_cgamut", "canon_clog2_bt2020")
    assert CLOG3_PAIRS == ("canon_clog3_cgamut", "canon_clog3_bt2020")
    for raw in (*SLOG3_PAIRS, *SLOG3_VENICE_PAIRS, *CLOG2_PAIRS, *CLOG3_PAIRS):
        assert f'= "{raw}"' in text


def test_swift_implemented_non_venice_matches_python():
    """Cycle 25: Swift implemented (minus Venice, minus stub) == Python table."""
    import re

    from color.detect import IMPLEMENTED_NON_VENICE
    from color.gamuts import IDT_PAIRS, VENICE_IDTS

    idt = ROOT / "macos" / "LogBridge" / "LogBridge" / "Models" / "IDT.swift"
    text = idt.read_text(encoding="utf-8")
    raws = re.findall(r'case \w+ = "([a-z0-9_]+)"', text)
    assert "dji_dlog_m" in raws
    implemented = [r for r in raws if r != "dji_dlog_m"]
    non_venice = [r for r in implemented if r not in VENICE_IDTS]
    assert set(non_venice) == set(IMPLEMENTED_NON_VENICE)
    assert set(implemented) == set(IDT_PAIRS)
    assert "dji_dlog_m" not in IDT_PAIRS


def test_can_one_click_never_for_stub_id():
    from color.detect import Detection, can_one_click_process

    d = Detection("dji_dlog_m", "dlog_m", None, "test", False, "D-Log M")
    assert can_one_click_process(d) is False


def test_dlog_m_still_absent_from_idt_pairs():
    from color.gamuts import IDT_PAIRS
    from color.stubs import STUB_IDTS, dlog_m_to_linear

    assert "dji_dlog_m" not in IDT_PAIRS
    assert any(s["id"] == "dji_dlog_m" for s in STUB_IDTS)
    try:
        dlog_m_to_linear(0.18)
    except NotImplementedError as exc:
        assert "D-Log M" in str(exc)
        assert "unsupported" in str(exc).lower()
    else:
        raise AssertionError("D-Log M must stay unimplemented")
