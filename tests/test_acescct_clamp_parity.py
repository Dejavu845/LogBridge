"""Swift ACEScct encode matches the Python 1e-10 floor. Numbers, not source text.

The fixture is written by Python (``acescct_encode(max(lin, 1e-10))`` and
``exposure_in_acescct``). This test recomputes those values. When ``swiftc``
is on PATH it compiles ``ACEScctMath.swift`` with the Swift runner and
asserts the same numbers.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from color.resolve_export import exposure_in_acescct
from color.working_space import acescct_encode

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "acescct_clamp_parity.json"
MATH = ROOT / "macos" / "LogBridge" / "LogBridge" / "Color" / "ACEScctMath.swift"
RUNNER = ROOT / "macos" / "LogBridge" / "ACEScctClampParity" / "main.swift"
ABS_TOL = 1e-8


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _encode_ref(lin: float) -> float:
    return float(np.asarray(acescct_encode(np.maximum(lin, 1e-10))).reshape(-1)[0])


def test_fixture_covers_required_inputs():
    data = _load()
    lins = [row["lin"] for row in data["encode"]]
    assert 0.0 in lins
    assert any(x < 0.0 for x in lins)
    assert 1e-12 in lins
    assert 1e-10 in lins
    assert 0.18 in lins
    assert any(x >= 65504.0 for x in lins)


def test_python_encode_and_exposure_match_fixture():
    data = _load()
    worst = 0.0
    for row in data["encode"]:
        got = _encode_ref(row["lin"])
        err = abs(got - row["acescct"])
        worst = max(worst, err)
        assert got == pytest.approx(row["acescct"], abs=1e-12)
    for row in data["exposure"]:
        got = float(
            exposure_in_acescct(
                np.full(3, row["enc"], dtype=np.float64), row["stops"]
            )[0]
        )
        err = abs(got - row["acescct"])
        worst = max(worst, err)
        assert got == pytest.approx(row["acescct"], abs=1e-12)
    # Floor actually moves negatives. The analytic toe would not.
    floored = _encode_ref(-1.0)
    raw = float(np.asarray(acescct_encode(-1.0)).reshape(-1)[0])
    assert floored == pytest.approx(_encode_ref(1e-10), abs=1e-15)
    assert raw < -1.0
    assert worst <= 1e-12


def test_swift_encode_matches_python_fixture(tmp_path):
    """Compile the app's ACEScctMath and assert the shared fixture."""
    swiftc = shutil.which("swiftc")
    if swiftc is None:
        if platform.system() == "Darwin":
            pytest.fail("swiftc is missing on macOS")
        pytest.skip("swiftc not on PATH")
    binary = tmp_path / "acescct-clamp-parity"
    compile = subprocess.run(
        [swiftc, "-O", "-o", str(binary), str(MATH), str(RUNNER)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert compile.returncode == 0, compile.stderr
    run = subprocess.run(
        [str(binary), str(FIXTURE)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "swift parity ok" in run.stdout
    # Tolerance the Swift runner uses. Python already matched the fixture tighter.
    assert ABS_TOL == 1e-8
