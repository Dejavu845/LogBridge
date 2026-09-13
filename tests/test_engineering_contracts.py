"""Engineering contracts: docs honesty, Cloud Agent env, CI gates, failure copy.

No new cameras. No golden numbers. Does not change IDT / WB / OCIO math.
"""

from __future__ import annotations

import json
from pathlib import Path

from color.batch import (
    CANCELLED_NOTE,
    DISK_SHORT_STATUS,
    DISK_SHORT_STATUS_TEMPLATE,
    WRITE_FAILED_CHIP,
    WRITE_OVERSIZE_CHIP,
    preserved_failure_note,
    user_facing_failure_note,
)
from color.stubs import STUB_IDTS, dlog_m_to_linear

ROOT = Path(__file__).resolve().parents[1]
ENGINEERING = ROOT / "docs" / "ENGINEERING.md"
OPTIMIZATIONS = ROOT / "docs" / "OPTIMIZATIONS.md"
ENV_JSON = ROOT / ".cursor" / "environment.json"
INSTALL = ROOT / "scripts" / "cloud-agent-install.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
PYPROJECT = ROOT / "pyproject.toml"
COLOR_INIT = ROOT / "color" / "__init__.py"


def test_engineering_docs_exist_and_stay_honest():
    assert ENGINEERING.is_file()
    assert OPTIMIZATIONS.is_file()
    blob = ENGINEERING.read_text(encoding="utf-8") + "\n" + OPTIMIZATIONS.read_text(
        encoding="utf-8"
    )
    assert "implemented (unverified)" in blob
    assert "已实现（未验证）" in blob
    assert "CI 绿不等于达芬奇已验证" in blob
    assert "整段代理，不是全精度成片" in blob
    assert "一键精准" in blob  # named as forbidden
    assert "Not “supported”" in blob or 'Not "supported"' in blob
    assert "python -m pytest -q" in blob
    assert "macos/LogBridge/LogBridge.xcodeproj" in blob
    assert "处理已锁定片段" in blob
    assert "先选择 Log 与色域" in blob
    assert "No Xcode on Linux" in blob or "Do not require Xcode" in blob
    assert "never 一键还原" in blob or "一键还原 added" in blob
    assert "hlg/pq supported" not in blob.lower()
    assert "全格式已支持" not in blob


def test_optimizations_records_cycles_and_leaves_p1():
    text = OPTIMIZATIONS.read_text(encoding="utf-8")
    assert "Cycle 1" in text
    assert "Cycle 3" in text
    assert "Cycle 4" in text
    assert "Cycle 5" in text
    assert "Cycle 6" in text
    assert "Cycle 7" in text
    assert "Cycle 8" in text
    assert "Cycle 9" in text
    assert "Cycle 10" in text
    assert "Cycle 11" in text
    assert "Cycle 12" in text
    assert "Cycle 13" in text
    assert "Cycle 14" in text
    assert "Cycle 15" in text
    assert "Cycle 16" in text
    assert "test_swift_file_floor.py" in text
    assert "test_public_types.py" in text
    assert "P0-batch-floor" in text
    assert "test_batch_file_floor.py" in text
    assert "LB-01" in text
    assert "P1-ruff-style" in text
    assert "P1-types" in text
    assert "P2-cameras" in text
    assert "D-Log M" in text
    assert "environment.json" in text
    assert "test_engineering_contracts.py" in text


def test_cursor_environment_is_linux_pytest_without_xcode():
    assert ENV_JSON.is_file()
    data = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    assert data["name"]
    assert "install" in data
    assert "xcodebuild" not in json.dumps(data)
    assert "Xcode" not in json.dumps(data)
    install = data["install"]
    assert "cloud-agent-install.sh" in install
    script = INSTALL.read_text(encoding="utf-8")
    assert "Does not require Xcode" in script or "does not require Xcode" in script
    assert "python3.12" in script
    assert ".[test,lint]" in script
    assert "xcodebuild" not in script


def test_ci_pins_python_312_caches_and_fails_if_tests_missing():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'python-version: "3.12"' in text
    assert "cache: pip" in text
    assert "Guard pytest suite present" in text
    assert "scripts/ci-guard-tests.sh" in text
    assert "test_*.py" in (ROOT / "scripts" / "ci-guard-tests.sh").read_text(
        encoding="utf-8"
    )
    assert 'pip install -e ".[test,lint]"' in text
    assert "ruff check" in text
    assert "xcodebuild" in text  # macos job only
    assert "CI 绿不等于达芬奇已验证" in text


def test_pyproject_hygiene_and_ruff_is_lightweight():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'name = "logbridge-color"' in text
    assert 'license = {text = "MIT"}' in text
    assert 'Homepage = "https://github.com/Dejavu845/LogBridge"' in text
    assert 'test = ["pytest>=7.0"]' in text
    assert 'lint = ["ruff>=0.6"]' in text
    assert 'select = ["E9", "F63", "F7", "F82"]' in text
    assert "testpaths = [\"tests\"]" in text


def test_python_package_doc_forbids_supported_camera_claims():
    doc = COLOR_INIT.read_text(encoding="utf-8")
    assert "implemented (unverified)" in doc
    assert 'Do not describe cameras as "supported"' in doc


def test_dlog_m_stays_stub_not_an_idt_pair():
    from color.gamuts import IDT_PAIRS

    assert "dji_dlog_m" not in IDT_PAIRS
    assert any(s["id"] == "dji_dlog_m" for s in STUB_IDTS)
    try:
        dlog_m_to_linear(0.18)
    except NotImplementedError as exc:
        assert "D-Log M" in str(exc)
        assert "unsupported" in str(exc).lower()
    else:
        raise AssertionError("D-Log M must stay unimplemented")


def test_known_chinese_write_failures_are_not_rewritten_to_decode():
    """Existing chips stay. Generic English still maps to 解码失败."""
    from color.batch import DECODE_FAILED_CHIP, GENERIC_PARSE_FAILED

    assert user_facing_failure_note(DISK_SHORT_STATUS) == DISK_SHORT_STATUS
    assert preserved_failure_note(DISK_SHORT_STATUS) == DISK_SHORT_STATUS
    assert user_facing_failure_note(DISK_SHORT_STATUS_TEMPLATE) == DISK_SHORT_STATUS_TEMPLATE
    assert user_facing_failure_note(WRITE_FAILED_CHIP) == WRITE_FAILED_CHIP
    assert user_facing_failure_note(CANCELLED_NOTE) == CANCELLED_NOTE
    assert user_facing_failure_note(WRITE_OVERSIZE_CHIP) == WRITE_OVERSIZE_CHIP
    assert user_facing_failure_note(GENERIC_PARSE_FAILED) == DECODE_FAILED_CHIP
    assert user_facing_failure_note("mystery english") == DECODE_FAILED_CHIP
    assert "精准" not in DISK_SHORT_STATUS
    assert "精准" not in WRITE_FAILED_CHIP


def test_pytest_suite_is_present_for_the_ci_guard():
    # Same recursive count as scripts/ci-guard-tests.sh (`find tests -name 'test_*.py'`).
    modules = list((ROOT / "tests").rglob("test_*.py"))
    assert len(modules) >= 10
    names = {p.name for p in modules}
    assert "test_ui_copy.py" in names
    assert "test_settings_zh.py" in names
    assert "test_engineering_contracts.py" in names
    assert "test_batch_file_floor.py" in names
