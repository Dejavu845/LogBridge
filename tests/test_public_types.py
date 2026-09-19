"""P1-types: public helpers declare returns. Numbers unchanged.

Cycle 14: pipeline / working_space / curve dispatch.
Cycle 15: formats + detect + rec709 + odt.apply_odt.
Cycle 16: every public curves encode/decode.
Cycle 17: as_shot + exposure public returns.
Cycle 18: remaining public color modules except unrestored batch.py.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from color import (
    as_shot,
    auto_wb,
    curves,
    detect,
    exposure,
    exr_write,
    formats,
    gamuts,
    graph,
    ocio_builtins,
    odt,
    pipeline,
    rec709,
    resolve_export,
    stubs,
    wb,
    working_space,
)


def _public(mod):
    return [
        name
        for name, obj in inspect.getmembers(mod, inspect.isfunction)
        if not name.startswith("_") and obj.__module__ == mod.__name__
    ]


def test_pipeline_public_return_annotations():
    for name in _public(pipeline):
        fn = getattr(pipeline, name)
        assert "return" in fn.__annotations__, name


def test_working_space_public_return_annotations():
    for name in _public(working_space):
        fn = getattr(working_space, name)
        assert "return" in fn.__annotations__, name


def test_curves_dispatch_return_annotations():
    assert "return" in curves.decode_log.__annotations__
    assert "return" in curves.encode_log.__annotations__


def test_curves_public_return_annotations():
    for name in _public(curves):
        fn = getattr(curves, name)
        assert "return" in fn.__annotations__, name


def test_formats_public_return_annotations():
    for name in _public(formats):
        fn = getattr(formats, name)
        assert "return" in fn.__annotations__, name


def test_detect_public_return_annotations():
    for name in _public(detect):
        fn = getattr(detect, name)
        assert "return" in fn.__annotations__, name


def test_rec709_public_return_annotations():
    for name in _public(rec709):
        fn = getattr(rec709, name)
        assert "return" in fn.__annotations__, name


def test_odt_apply_return_annotation():
    assert "return" in odt.apply_odt.__annotations__


def test_as_shot_public_return_annotations():
    for name in _public(as_shot):
        fn = getattr(as_shot, name)
        assert "return" in fn.__annotations__, name


def test_exposure_public_return_annotations():
    for name in _public(exposure):
        fn = getattr(exposure, name)
        assert "return" in fn.__annotations__, name


def test_remaining_color_modules_public_return_annotations():
    for mod in (auto_wb, exr_write, gamuts, graph, ocio_builtins, resolve_export, stubs, wb):
        for name in _public(mod):
            fn = getattr(mod, name)
            assert "return" in fn.__annotations__, f"{mod.__name__}.{name}"


def test_batch_ycbcr_helpers_annotated_when_restored():
    """Local 1350-line batch.py. Remote 1006-line stub skips. Do not weaken ≥1340."""
    root = Path(__file__).resolve().parents[1]
    batch_py = root / "color" / "batch.py"
    nlines = len(batch_py.read_text(encoding="utf-8").splitlines())
    if nlines < 1340:
        pytest.skip(f"batch.py unrestored ({nlines} lines)")
    from color import batch

    for name in (
        "ycbcr_range_offsets",
        "ycbcr_to_rgb_float",
        "ycbcr_to_preview_u8",
        "preview_u8_promoted_float",
    ):
        assert "return" in getattr(batch, name).__annotations__, name
