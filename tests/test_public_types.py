"""P1-types: public helpers in pipeline / working_space / curves declare returns.

Does not change CAT / IDT / curve numbers. Cycle 14 only annotates existing
functions that already returned ndarrays.
"""

from __future__ import annotations

import inspect

from color import curves, pipeline, working_space


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
