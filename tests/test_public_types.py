"""P1-types: public helpers declare returns. Numbers unchanged.

Cycle 14: pipeline / working_space / curve dispatch.
Cycle 15: formats + detect + rec709 + odt.apply_odt.
Cycle 16: every public curves encode/decode.
Cycle 17: as_shot + exposure public returns.
"""

from __future__ import annotations

import inspect

from color import as_shot, curves, detect, exposure, formats, odt, pipeline, rec709, working_space


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
