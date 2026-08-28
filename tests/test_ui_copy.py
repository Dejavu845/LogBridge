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
    assert "预览·非成片" in _all_swift()
    assert 'Button("一键还原")' not in content
    assert 'Button("一键还原")' not in _all_swift()
    assert "一键精准" not in _all_swift() or "Not 一键精准" in _all_swift()
    swift = _all_swift()
    assert "处理已锁定片段" in swift
    assert "先选择 Log 与色域" in swift
    assert "导出 ACEScct / EXR" in swift
    assert "先选择成对 IDT" in swift
    assert "处理已锁定片段" in content
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "取消" in bar
    assert "isWritingDeliverables" in bar
    assert "cancelLockedDeliverables" in bar


def test_preview_overlay_badge_feichengpian():
    preview = _read(PREVIEW)
    assert "预览·非成片" in preview
    assert "8-bit thumbnail is not a deliverable" in preview
    assert "PreviewNotDeliverableBadge" in preview
    badge = preview.split("struct PreviewNotDeliverableBadge")[1].split("struct Rec709TaggedHost")[0]
    assert 'Text("预览·非成片")' in badge
    assert 'Text("8-bit thumbnail is not a deliverable")' not in badge


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
    assert "func processLockedClips()" in clip
    assert "pending" in clip
    content = _read(CONTENT)
    assert "showsProcessLockedButton" in content
    assert ".disabled(!session.canProcess)" in content
    assert "lockedClipCount" in clip
    assert "processSkipReason" in clip
    can = clip.split("var canProcess")[1].split("var canProcessSelected")[0]
    assert "pendingPickerCount == 0" not in can
    assert "lockedClipCount" in can
    assert "writeACES2065EXR" in clip
    assert "条已写出代理" in clip
    assert "待选跳过" in clip
    assert "失败原因" in clip
    assert "writeLockedDeliverables" in clip
    assert "整段代理，不是全精度成片" in clip
    assert "已写出代理" in clip
    assert "exportChip" in clip
    assert "revealClipExportInFinder" in clip
    assert "clipSequenceRevealURL" in clip
    assert "_proxy" in _read(
        SWIFT_ROOT / "LogBridge/LogBridge/Export/ResolveExporter.swift"
    )
    assert "_ACES2065-1_proxy" in _read(
        SWIFT_ROOT / "LogBridge/LogBridge/Export/ResolveExporter.swift"
    )
    assert "frame_%06d.exr" in _read(
        SWIFT_ROOT / "LogBridge/LogBridge/Export/ResolveExporter.swift"
    )


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
    assert "高级" in blob
    assert "条已锁定" in blob
    assert "待选" in blob and "已锁定" in blob
    assert "先选择成对 IDT" in blob
    assert "整段代理，不是全精度成片" in blob
    assert "已写出代理" in blob
    assert "待选跳过" in blob
    assert "失败原因" in blob
    assert "帧数对不上" in blob
    assert "读不到帧率，未核对" in blob
    assert "_proxy" in blob
    assert "ACEScct 成片" not in blob
    assert "_ACES2065-1_proxy/frame_000000.exr" in blob
    assert "709 预览" in blob
    assert "先选择成对 IDT" in blob


def test_exposure_inspector_and_preview_not_finished_picture():
    inspector = _read(INSPECTOR)
    assert "ExposureInspector" in inspector
    assert "Stops" in inspector
    assert "2^stops" in inspector or "2 ** stops" in inspector or "rgb × (2^stops)" in inspector
    assert "Do not add/subtract Log code values" in inspector
    swift = _all_swift()
    assert "case exposure" in swift or "case .exposure" in swift
    assert "applyExposure" in swift
    assert "02_Exposure" in swift
    assert "not a finished" in (inspector + swift).lower() or "not a finished picture" in inspector
    assert "预览·非成片" in inspector


def test_no_bundled_manufacturer_demos():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "ACCEPTANCE.md").read_text(encoding="utf-8")
    blob = readme + "\n" + acceptance
    assert "No bundled camera manufacturer demo" in blob or "does **not** bundle camera manufacturer demo" in blob
    assert "drop your own" in blob.lower() or "drops their own" in blob.lower()
    sidebar = _read(SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift")
    assert "no bundled manufacturer demos" in sidebar.lower()
    assert "把混源文件夹拖进来" in sidebar


def test_as_shot_wb_copy_and_no_5600_guess():
    inspector = _read(INSPECTOR)
    assert "as-shot" in inspector.lower() or "As-shot" in inspector
    assert "Pick neutral" in inspector
    assert "5600" in inspector  # named so we can say we do not guess it
    assert "6504" in inspector
    assert "不猜 5600" in inspector
    assert "ACES2065-1 (AP0)" in inspector
    assert "after IDT" in inspector
    assert "已实现（未验证）" in inspector
    assert "CAT(user→D65)·inv(CAT(as→D65))" in inspector
    assert "单位阵" in inspector
    assert "3200→5600 变暖" in inspector
    swift = _all_swift()
    assert "pickNeutral" in swift or "Pick neutral" in swift
    assert "asShotUnknown" in swift or "as-shot unknown" in swift
    assert "WBSource" in swift
    assert "handlePreviewPick" in swift
    assert "sampleLinearRGB" in swift
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "ACCEPTANCE.md").read_text(encoding="utf-8")
    blob = readme + "\n" + acceptance
    assert "as-shot" in blob.lower()
    assert "do not guess 5600 or 6504" in blob.lower()
    assert "after IDT" in blob and "ACES2065-1 (AP0)" in blob
    assert "Grey-card" in blob or "grey-card" in blob
    assert "nclc" in blob.lower()
    assert "pending / identity" in blob.lower()


def test_user_visible_english_leftovers_are_chinese():
    """P2 leftovers: user-visible English must not return; Chinese copy is required."""
    preview = _read(SWIFT_ROOT / "LogBridge/LogBridge/Preview/PreviewEngine.swift")
    content = _read(CONTENT)
    inspector = _read(INSPECTOR)
    sidebar = _read(SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift")
    settings = _read(SWIFT_ROOT / "LogBridge/LogBridge/Views/SettingsView.swift")
    clip = _read(CLIP)

    assert '"没有素材"' in preview
    assert '"正在解码预览…"' in preview
    assert '"解不出预览帧"' in preview
    assert '"先选择成对 Log 与色域"' in preview
    assert '"预览代理，不是成片"' in preview
    assert '"No clip"' not in preview
    assert "Decoding preview" not in preview
    assert "Could not decode a preview frame" not in preview
    assert "Pick a paired IDT" not in preview
    assert "Preview proxy" not in preview

    status = content.split("struct StatusBar")[1]
    assert "已实现（未验证）" in status
    assert "serial graph" not in status
    assert "implemented (unverified)" not in status.lower()

    assert 'Text("已实现（未验证）")' in sidebar
    assert 'Text("implemented (unverified)")' not in sidebar

    wb = inspector.split("struct WBInspector")[1].split("struct ODTInspector")[0]
    assert 'Text("绿品")' in wb
    assert 'Text("Tint")' not in wb
    assert "机内色温只填旋钮，默认 CAT 是单位阵。" in wb
    assert "用户改色温才做相对变换 CAT(user→D65)·inv(CAT(as→D65))，3200→5600 变暖。" in wb
    assert "灰卡是绝对 CAT；读不到就保持单位阵，不猜 5600。" in wb
    assert "As-shot CCT/tint fills these knobs" not in wb
    assert "do not guess 5600 or 6504" not in wb.lower()
    assert "implemented (unverified)" not in wb.lower()

    assert "已实现（未验证）" in settings
    assert "implemented (unverified)" not in settings.lower()

    export_fn = clip.split("func exportResolve()")[1]
    assert 'panel.prompt = "导出"' in export_fn
    assert 'panel.prompt = "Export"' not in export_fn


def test_inspector_cat_three_sentences_review_lock():
    """As-shot default is 单位阵. Relative CAT only on user move. No 机内白转到 D65."""
    inspector = _read(INSPECTOR)
    wb = inspector.split("struct WBInspector")[1].split("struct ODTInspector")[0]
    assert "机内色温只填旋钮，默认 CAT 是单位阵。" in wb
    assert "用户改色温才做相对变换 CAT(user→D65)·inv(CAT(as→D65))，3200→5600 变暖。" in wb
    assert "灰卡是绝对 CAT；读不到就保持单位阵，不猜 5600。" in wb
    assert "单位阵" in wb
    assert "CAT(user→D65)·inv(CAT(as→D65))" in wb
    assert "3200→5600 变暖" in wb
    stripped = wb.replace("CAT(user→D65)·inv(CAT(as→D65))", "")
    assert "CAT(as→D65)" not in stripped
    assert "机内白转到 D65" not in wb
    clip = _read(CLIP)
    assert "已写出代理" in clip
    assert "待选跳过" in clip
    assert "失败原因" in clip


def test_idt_bar_always_visible_no_hidden_picker():
    content = _read(CONTENT)
    inspector = _read(INSPECTOR)
    strip = _read(SWIFT_ROOT / "LogBridge/LogBridge/Views/NodeStripView.swift")
    assert "PairedIDTBar" in content
    assert "成对 IDT" in inspector
    assert 'Button("Apply graph")' not in strip
    assert "确认估计" in inspector
    assert "估计白平衡" in inspector
    assert "高级" in content
    # Main path: preview → paired IDT → process. Not inside 高级.
    center = content.split("VStack(spacing: 0)")[1].split(".frame(minWidth: 520)")[0]
    assert "SplitPreview" in center
    assert center.index("PairedIDTBar") < center.index("AdvancedPanel")
    assert "PairedIDTBar" not in content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    advanced = content.split("struct AdvancedPanel")[1].split("struct SplitPreview")[0]
    assert "NodeStripView" in advanced
    assert "导出 ACEScct / EXR" in advanced
    assert "ODTInspector" not in advanced
    assert 'Picker("Paired IDT"' not in advanced
    assert "成对 IDT" not in advanced
    assert "layoutPriority(1)" in center
    inspector_frame = content.split("InspectorView(session: session)")[1].split("}")[0]
    assert "maxWidth: 260" in inspector_frame
    assert "maxWidth: 380" not in inspector_frame
    sidebar_frame = content.split("ClipSidebarView(session: session)")[1].split("VStack")[0]
    assert "maxWidth: 280" in sidebar_frame
    assert "处理已锁定片段" not in inspector.split("struct InspectorView")[1].split("struct WBInspector")[0]


def test_sidebar_pending_and_locked_are_glanceable():
    """待选 / 已锁定 are two visual states. No extra lock button."""
    sidebar = _read(SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift")
    row = sidebar.split("struct ClipRow")[1]
    assert "clip.isPending" in row
    assert '"待选"' in row
    assert '"已锁定"' in row
    assert "weight(.semibold)" in row
    assert "frame(width: 3)" in row
    assert 'Button("锁 IDT")' not in sidebar
    assert 'Button("锁定")' not in sidebar
    assert 'Button("锁定 IDT")' not in sidebar
    assert "处理已锁定片段" not in row
    assert "精准" not in sidebar


def test_write_progress_on_preview_inspector_locks():
    """While writing: one progress line on preview; inspector/IDT locked; one cancel."""
    content = _read(CONTENT)
    inspector = _read(INSPECTOR)
    clip = _read(CLIP)

    assert "var isExporting" in clip
    assert "isWritingDeliverables" in clip
    assert "isExporting: Bool { isWritingDeliverables }" in clip

    preview = content.split("struct SplitPreview")[1].split("struct StatusBar")[0]
    assert "WriteProgressLine" in preview
    assert "isExporting" in preview
    assert "lastExportNote" in preview
    assert "ProgressView" not in preview
    assert 'Button(' not in preview
    assert "取消" not in preview
    assert "处理已锁定片段" not in preview
    assert "精准" not in preview
    line = content.split("struct WriteProgressLine")[1].split("struct StatusBar")[0]
    assert line.count("Button(") == 0
    assert "ProgressView" not in line
    assert "Text(text)" in line

    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "取消" in bar
    assert "isWritingDeliverables" in bar
    assert "cancelLockedDeliverables" in bar
    assert bar.count("lastExportNote") == 1
    assert "showsBatchSummary" in bar
    assert "WriteProgressLine" not in bar

    status = content.split("struct StatusBar")[1]
    assert 'Button("处理已锁定片段")' not in status
    assert "取消" not in status
    assert "WriteProgressLine" not in status
    assert "isWritingDeliverables" not in status
    assert "isExporting" in status
    assert "preview.isWorking" in status
    working = status.split("if session.preview.isWorking")[1].split("{")[0]
    assert "isWritingDeliverables" not in working
    assert "isExporting" not in working

    insp = inspector.split("struct InspectorView")[1].split("struct WBInspector")[0]
    assert "ExposureInspector" in insp
    assert "WBInspector" in insp
    assert "isExporting" in insp
    assert ".disabled(" in insp
    assert 'Button("处理已锁定片段")' not in insp
    assert "精准" not in insp

    idt = inspector.split("struct PairedIDTBar")[1].split("struct InspectorView")[0]
    assert "成对 IDT" in idt
    assert 'Picker("Paired IDT"' in idt
    assert ".disabled(" in idt
    assert "isExporting" in idt
    assert "if session.isExporting" not in idt
    assert "处理已锁定片段" not in idt

    center = content.split("VStack(spacing: 0)")[1].split(".frame(minWidth: 520)")[0]
    assert "PairedIDTBar" in center
    assert center.index("SplitPreview") < center.index("PairedIDTBar")
    assert "整段代理，不是全精度成片" in content
    assert "预览·非成片" in _all_swift()


def test_import_lands_on_first_pending():
    """Mixed drop selects first pending/unlocked. All-locked keeps first/existing. No new button."""
    clip = _read(CLIP)
    import_fn = clip.split("func importURL")[1].split("private static let clipExtensions")[0]
    assert "built.first(where:" in import_fn
    assert "!$0.hasLockedPair" in import_fn
    assert "selectedID" in import_fn
    assert "selectedID == nil" in import_fn
    assert "setIDT" not in import_fn
    assert "processLockedClips" not in import_fn
    assert "processSelected" not in import_fn
    assert "exportResolve" not in import_fn
    assert "精准" not in import_fn
    cap = clip.split("var previewCaption")[1].split("var displayCurve")[0]
    assert "processSkipReason ?? exportChip" in cap
    assert 'return "先选择 Log 与色域"' not in cap
    assert 'return "先选择成对 IDT"' not in cap
    content = _read(CONTENT)
    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "PairedIDTBar" in content
    assert "isExporting" in clip
    assert "isWritingDeliverables" in clip


def test_selected_clip_glanceable_on_preview():
    """Selected clip 待选 / 失败 / 已写出代理 on preview chrome. No new buttons."""
    content = _read(CONTENT)
    clip = _read(CLIP)
    sidebar = _read(SWIFT_ROOT / "LogBridge/LogBridge/Views/ClipSidebarView.swift")

    cap = clip.split("var previewCaption")[1].split("var displayCurve")[0]
    assert "processSkipReason ?? exportChip" in cap
    assert 'return "先选择 Log 与色域"' not in cap
    assert 'return "先选择成对 IDT"' not in cap
    assert '"先选择 Log 与色域"' not in cap
    assert '"先选择成对 IDT"' not in cap
    skip = clip.split("var processSkipReason")[1].split("var verificationBadge")[0]
    assert "先选择成对 IDT" in skip
    assert "先选择 Log 与色域" in skip
    assert "exportChip" in cap
    assert "已写出代理" in clip
    assert "重试" not in cap
    assert "精准" not in cap

    preview = content.split("struct SplitPreview")[1].split("struct StatusBar")[0]
    assert "previewCaption" in preview
    assert "WriteProgressLine" in preview
    assert "isExporting" in preview
    assert "lastExportNote" in preview
    assert preview.index("isExporting") < preview.index("previewCaption")
    assert 'Button(' not in preview
    assert "重试" not in preview
    assert "取消" not in preview
    assert "处理已锁定片段" not in preview
    assert "精准" not in preview
    line = content.split("struct WriteProgressLine")[1].split("struct StatusBar")[0]
    assert line.count("Button(") == 0
    assert "重试" not in line
    assert "ProgressView" not in line
    assert "Text(text)" in line

    bar = content.split("struct ProcessLockedBar")[1].split("struct AdvancedPanel")[0]
    assert bar.count("Button(") == 1
    assert "showsProcessLockedButton" in bar
    assert "lockedClipCount" in clip
    assert "重试" not in bar

    row = sidebar.split("struct ClipRow")[1]
    assert "exportChip" in row
    assert "已写出代理" in row
    assert 'Button("重试")' not in sidebar
    assert "精准" not in sidebar

    assert "整段代理，不是全精度成片" in content
    assert "预览·非成片" in _all_swift()
    assert "成片预览关" in clip or "预览·非成片" in clip or "不是成片" in clip


def test_forbidden_marketing_copy_stays_forbidden():
    swift = _all_swift()
    docs = (ROOT / "README.md").read_text(encoding="utf-8") + (ROOT / "ACCEPTANCE.md").read_text(
        encoding="utf-8"
    )
    tests = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("*.py"))
    for token in ("一键还原", "一键校准", "全自动校准", "全格式已支持"):
        assert token in tests  # prohibition named in tests
        if token in swift:
            assert "不写" in swift or "never" in swift.lower() or "Never" in swift
    assert "精准" in tests
    assert "全格式已支持" in docs  # named as out of scope / do not write
