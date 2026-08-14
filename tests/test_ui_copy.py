"""Review locks: pending process/export, preview badge, paired IDT picker."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWIFT_ROOT = ROOT / "macos"
INSPECTOR = SWIFT_ROOT / "LogBridge/LogBridge/Views/InspectorView.swift"
CONTENT = SWIFT_ROOT / "LogBridge/LogBridge/ContentView.swift"
PREVIEW = SWIFT_ROOT / "LogBridge/LogBridge/Color/Rec709PreviewView.swift"
CLIP = SWIFT_ROOT / "LogBridge/LogBridge/Models/Clip.swift"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _all_swift() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SWIFT_ROOT.rglob("*.swift"))


def test_primary_button_is_locked_chinese():
    content = _read(CONTENT)
    assert "处理已锁定片段" in content
    assert "先选择 Log 与色域" in content
    assert "导出 ACEScct / EXR" in content
    assert "预览·非成片" in content
    assert 'Button("一键还原")' not in content
    assert 'Button("一键还原")' not in _all_swift()
    assert "一键精准" not in _all_swift() or "Not 一键精准" in _all_swift()
    swift = _all_swift()
    assert "处理已锁定片段" in swift
    assert "先选择 Log 与色域" in swift
    assert "导出 ACEScct / EXR" in swift


def test_preview_overlay_badge_feichengpian():
    preview = _read(PREVIEW)
    assert "预览·非成片" in preview
    assert "8-bit thumbnail is not a deliverable" in preview
    assert "PreviewNotDeliverableBadge" in preview


def test_paired_idt_picker_not_two_dropdowns():
    inspector = _read(INSPECTOR)
    assert "Paired IDT" in inspector
    assert 'Picker("Paired IDT"' in inspector
    assert 'Picker("Curve"' not in inspector
    assert 'Picker("Gamut"' not in inspector
    assert "S-Log3 + S-Gamut3" in inspector
    assert "S-Log3 + S-Gamut3.Cine" in inspector
    assert "Venice pair only if detected" in inspector


def test_pending_clips_block_process_and_export():
    clip = _read(CLIP)
    assert "isPending" in clip
    assert "canProcess" in clip
    assert "canProcessSelected" in clip
    assert "func processSelected()" in clip
    assert "func applyGraph()" in clip
    assert "pending" in clip
    content = _read(CONTENT)
    assert ".disabled(!session.canProcessSelected)" in content
    assert ".disabled(!session.canProcess)" in content


def test_docs_name_the_review_locks():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "ACCEPTANCE.md").read_text(encoding="utf-8")
    blob = readme + "\n" + acceptance
    assert "预览·非成片" in blob
    assert "8-bit thumbnail is not a deliverable" in blob
    assert "处理已锁定片段" in blob
    assert "先选择 Log 与色域" in blob
    assert "导出 ACEScct / EXR" in blob
    assert "Apply graph" in blob
    assert "一键还原" in blob  # forbidden label is named so reviewers can grep
    assert "pending" in blob.lower()
    assert "paired IDT" in blob or "paired IDT" in blob
    assert "Rec.2100 HLG" in blob
    assert "Rec.2100 PQ" in blob
