"""Design grid: spacing, hues, grey fills, and opacity levels."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ui_metrics.py"


def test_ui_metrics_print_stated_baseline_and_pass():
    """28066d5 numbers are the stated baseline. After counts must meet the grid."""
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    text = result.stdout + result.stderr
    assert "before 28066d5 stated: non-grid 79/115, hues 3, grey blocks 20, opacity levels 9" in text
    assert "non-grid 0/" in text
    assert "opacity levels 2" in text
    assert "grey blocks 2" in text
    assert "guidance allow 「先选成对 Log 与色域」" in text
    assert "「用户选择成对 IDT」" in text
    assert "「— 先选择成对 IDT —」" in text
    script = SCRIPT.read_text(encoding="utf-8")
    assert "git show" not in script
    workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    assert "python3 scripts/check_ui_metrics.py" in workflow
    assert result.returncode == 0, text
