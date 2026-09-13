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
