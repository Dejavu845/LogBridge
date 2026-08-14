# LogBridge

macOS batch tool: mixed-camera Log → ACES2065-1 (IDT) → Exposure (stops, linear gain) → WB in ACES2065-1 linear (AP0) → ACEScct timeline / optional ODT (Rec.709 preview | Rec.2100 HLG | Rec.2100 PQ).

M1 is a **serial node graph** (IDT → Exposure → WB → selectable ODT), not a general node editor and not a Resolve-like grade. Every IDT and ODT is **implemented (unverified)** until golden grey-card samples are measured. This project does not describe cameras or HDR outputs as “supported”. There is no 一键精准.

M2-start adds optional **Rec.2100 HLG** and **Rec.2100 PQ** ODT nodes via **ACES Output Transform / BT.2100** (OCIO BuiltinTransform, or config-aces names if present). Prefer those Builtins over any handwritten transfer. There is no homemade HLG/PQ curve. HDR OT is unverified — not a one-click accurate path.

Internal working encoding: **ACEScct** (AP1 log). Scene-linear interchange / `roles.scene_linear`: **ACES2065-1** (Linear AP0). `roles.color_timing`: ACEScct. White balance is Bradford (or CAT02) chromatic adaptation in ACES2065-1 (AP0) scene-linear only — never a CAT on ACEScct. DaVinci Wide Gamut Intermediate is **not** the default internal or deliverable.

## Usability

- **Empty state:** drag-and-drop a folder of mixed clips is the primary action (big drop zone, short copy: “Drop a folder of mixed clips”). Choosing files is secondary. **No bundled camera manufacturer demo clips** — drop your own files.
- **Paired IDT picker:** when metadata cannot lock a curve+gamut pair, the UI shows locked pairs — e.g. `S-Log3 + S-Gamut3` and `S-Log3 + S-Gamut3.Cine` — **not** two independent dropdowns (curve vs gamut).
- **Block process:** **处理已锁定片段** stays disabled until every clip has a locked pair. Pending label: **先选择 Log 与色域**. No silent IDT.
- **S-Log3:** never silently default to S-Gamut3.Cine. Both pairs are offered; the user must pick one.
- **Venice:** `S-Log3 + S-Gamut3 (Venice)` and `S-Log3 + S-Gamut3.Cine (Venice)` appear **only if** a Venice body is detected.
- **Copy / badges:** “implemented (unverified)” — never “supported”, never 一键精准.
- **Graph:** inspector + node strip: IDT → Exposure (stops, default 0) → bypassable WB → ODT selector: **Off (ACEScct deliverable)** | Rec.709 preview | Rec.2100 HLG | Rec.2100 PQ. Default Off. Rec.709 / HLG / PQ panes are 预览·非成片 — not a finished picture.
- **Primary button:** **处理已锁定片段** (never 一键还原). Pending: **先选择 Log 与色域** (disabled).
- **Preview badge:** **预览·非成片**
- **Export:** **导出 ACEScct / EXR**

## OpenColorIO

Mac OpenColorIO uses **BuiltinTransform** styles named in `ocio/config.ocio` (`ARRI_LOGC4_to_ACES2065-1`, `SONY_SLOG3-SGAMUT3_to_ACES2065-1`, `SONY_SLOG3-SGAMUT3.CINE_to_ACES2065-1`, `PANASONIC_VLOG-VGAMUT_to_ACES2065-1`, `RED_LOG3G10-RWG_to_ACES2065-1`, `CANON_CLOG2-CGAMUT_to_ACES2065-1`, `CANON_CLOG3-CGAMUT_to_ACES2065-1`, `APPLE_LOG_to_ACES2065-1`). Venice Builtins are detect-only, never a silent S-Log3 default.

Linux tests use `color/` white-paper **reference encode/decode for 18% codes only**. They do not require PyOpenColorIO. F-Log2, N-Log, C-Log3+BT.2020, and D-Log have no full IDT Builtin — those papers stay handwritten. C-Log2 / C-Log3+Cinema Gamut / Apple Log use BuiltinTransform when present.

Rec.2100 HLG / PQ colorspaces in `ocio/config.ocio` name ACES Output Transform BuiltinTransform styles (`ACES-OUTPUT - ACES2065-1_to_CIE-XYZ-D65 - HDR-VIDEO-1000nits-15nits-HLG_1.1` + `DISPLAY - CIE-XYZ-D65_to_REC.2100-HLG`, and the ST2084 / Rec.2100-PQ pair) plus config-aces aliases (`Output - Rec.2100-HLG - 1000 nit`, `Output - Rec.2100-Rec.2020-ST2084 - 1000 nit`). Applying HDR requires OCIO. No homemade HLG/PQ LUT. HDR OT via ACES/BT.2100 is **implemented (unverified)**.

Python curves in `color/` are the source of truth for 18% tests. Regenerating OCIO assets:

```bash
python3 scripts/generate_ocio_assets.py
```

## Open in Xcode (macOS)

1. Copy this tree to a Mac.
2. Open `macos/LogBridge/LogBridge.xcodeproj` in Xcode 15+ (macOS 14 deployment target).
3. Select the **LogBridge** scheme, destination **My Mac**, and Run.

Layout: empty-state drop zone (folder of mixed clips) → clip list (LazyVStack) | split preview | node strip | inspector.

Split preview: the **source** pane is camera/log (untagged working-space dump) and is **not** tagged Rec.709. Only the processed/ODT pane tags `CGColorSpace.itur_709`, and only when the ODT node is on. Rec.709 pixels are never blit into an untagged Display P3 surface.

## Run tests (Linux or macOS)

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest -q
```

Or without install:

```bash
python3 -m pip install numpy pytest
PYTHONPATH=. python3 -m pytest -q
```

CI: `.github/workflows/test.yml` runs pytest on Ubuntu.

## Input IDTs (M1)

| IDT | Curve | Gamut | 18% grey (spec) | Status |
| --- | --- | --- | --- | --- |
| ARRI LogC4 / AWG4 | LogC4 | AWG4 / D65 | 0.2784 normalized | implemented (unverified) |
| Sony S-Log3 / S-Gamut3 | S-Log3 | S-Gamut3 / D65 | 420 / 1023 | implemented (unverified) |
| Sony S-Log3 / S-Gamut3.Cine | S-Log3 | S-Gamut3.Cine / D65 | 420 / 1023 | implemented (unverified) |
| Panasonic V-Log / V-Gamut | V-Log | V-Gamut / D65 | 433 / 1023 | implemented (unverified) |
| Fujifilm F-Log2 / BT.2020 | F-Log2 | BT.2020 / D65 | 400 / 1023 | implemented (unverified) |
| Nikon N-Log / BT.2020 | N-Log | BT.2020 / D65 | ~372 / 10-bit | implemented (unverified) |
| RED Log3G10 / REDWideGamutRGB | Log3G10 | RWG / D65 | 1/3 | implemented (unverified) |
| Canon C-Log2 / Cinema Gamut | C-Log2 | Cinema Gamut / D65 | ~0.39825 | implemented (unverified) |
| Canon C-Log3 / Cinema Gamut | C-Log3 | Cinema Gamut / D65 | ~0.34339 | implemented (unverified) |
| Canon C-Log3 / BT.2020 | C-Log3 | BT.2020 / D65 | ~0.34339 | implemented (unverified) |
| Apple Log / BT.2020 | Apple Log 1 | BT.2020 / D65 | ~0.48827 | implemented (unverified) |
| DJI D-Log / D-Gamut | D-Log (2017) | D-Gamut / D65 | ~0.39876 | implemented (unverified) |

Canon C-Log3 is **two locked pairs**. Metadata or the user picks **C-Log3 + Cinema Gamut** vs **C-Log3 + BT.2020**. LogBridge never defaults C-Log3 to Cinema Gamut.

**Explicitly unsupported:** DJI D-Log M, Apple Log 2, ARRI LogC3.

Sony S-Log3 is **two locked pairs**. Metadata or the user picks a **paired IDT** (S-Log3 + S-Gamut3 vs S-Log3 + S-Gamut3.Cine) — not two dropdowns. LogBridge never defaults S-Log3 to S-Gamut3.Cine. Clips without a locked pair stay **pending**. **处理已锁定片段** / **Apply graph** and **导出 ACEScct / EXR** are blocked for those clips (pending button: **先选择 Log 与色域**). The primary button is never 一键还原. Venice pairs appear only if a Venice body is detected.

Nikon N-Log white-paper `x` is a **10-bit code value 0–1023**. Do not divide by 1023 before the curve. 452 is the breakpoint, not 18% grey (~372). The OCIO LUT is sampled on 0–1 = code/1023 so image buffers stay normalized; the Python API takes 10-bit codes.

Fujifilm F-Log2 uses Data Sheet 1.0 + BT.2020 (`a=5.555556`). Not an F-Log1 LUT.

## Detection order

1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
2. Filename / model hint
3. User picker (paired IDTs; clip stays pending until chosen)

QuickTime `nclc` / `nclx` / `colr` is **never** used to identify S-Log3 or LogC4.

## Node workflow (serial only)

Visible graph, four slots — `color/graph.py` `SerialGraph`, used by `color/pipeline.py` and Resolve export.

Locked order: **IDT → Exposure → WB → ACEScct → preview ODT (709 / HLG / PQ)**.

1. **IDT** (`01_IDT`) — locked curve+gamut pair → ACES2065-1. Preview cache stores this AP0 linear buffer. Not bypassable.
2. **Exposure** (`02_Exposure`) — user-facing **stops** (default 0). After IDT, in ACES2065-1 linear: `rgb * (2 ** stops)`. Not a log-code add. **Bypassable / zeroable.** Own 1D / gain export node — not baked into IDT or WB when stops=0. Preview applies exposure in linear on the cached post-IDT buffer.
3. **WB** (`03_WB`) — Bradford/CAT02 in **ACES2065-1 (AP0)** scene-linear, CCT + green-magenta tint. Never a CAT on ACEScct-encoded values. **Bypassable.** WB off = IDT → Exposure → ACEScct, no bake (XML `enabled="false"`; DCTL **Bypass WB**). Export WB is a linear AP0 3×3 (or DI-free DCTL on ACES2065-1 / ACEScct-decoded-to-linear). Uniform gain and CAT commute; the order is still locked.
4. **ODT** (`04_ODT`) — selector, default **Off** (ACEScct deliverable / ACES2065-1 EXR):
   - **Off** — ACEScct timeline deliverable.
   - **Rec.709 preview** — DIY BT.709 OETF, no RRT. Preview only, unverified. Tags `CGColorSpace.itur_709` only in this mode.
   - **Rec.2100 HLG** — ACES Output Transform / BT.2100 (`ACES-OUTPUT … HLG_1.1` + `DISPLAY … REC.2100-HLG`, or ACES 2.0 Rec.2100-HLG style if present). Implemented (unverified).
   - **Rec.2100 PQ** — ACES Output Transform / BT.2100 (`ACES-OUTPUT … ST2084_1.1` + `DISPLAY … REC.2100-REC2020-ST2084`). Implemented (unverified).
   - HLG/PQ are **not** “supported” and not 一键精准. No homemade HLG/PQ curve.

Click a node in the strip to inspect its parameters. Exposure control is in the inspector when the Exposure node is selected. No sat / extra grade nodes. The Rec.709 pane is 预览·非成片 — do not treat it as a finished picture.

Python: `from color.graph import SerialGraph`. Swift: `SerialGraph` + `NodeSlot` in `Models/NodeGraph.swift`. Status: implemented (unverified).

### Resolve export — bypass WB

Export writes a serial **node graph**, not a prose sidecar: `graph.xml`, `graph.dot`, `01_IDT_<idt>.cube`, `02_Exposure.cube` / `.dctl`, `03_WB.cube` / `.cdl` / `.ccc` / `.dctl`, `04_ODT_Rec709.cube`, `README_RESOLVE.md`.

Export default: **ACEScct** timeline / **ACES2065-1** (**导出 ACEScct / EXR**). Rec.709 ODT is an optional preview node (off by default). Rec.2100 HLG/PQ are optional ACES/BT.2100 OT nodes (unverified). Export is blocked while any clip is pending (no locked IDT pair). Implemented (unverified).

Python: `from color.resolve_export import export_resolve_bundle` (pass `graph=` or `include_wb=`). Swift: `ResolveExporter.export(to:clips:...)`. Status: implemented (unverified).

## Preview vs full render

The macOS split preview is **not** a full-resolution render. Both panes show a **预览·非成片** badge (8-bit thumbnail is not a deliverable).

- One downscaled frame per clip (long edge ≤ 1920) via ImageIO thumbnail or `AVAssetImageGenerator` (VideoToolbox).
- Cached per clip: decoded camera/log buffer + IDT **ACES2065-1 linear** buffer (post-IDT, no exposure). IDT change invalidates linear; exposure + WB apply in linear on that AP0 buffer. Clip change reuses the decode if the URL is unchanged.
- Color apply runs off the main thread. 8-bit thumbnails are a viewing proxy — do not judge IDT accuracy from the preview.
- Source pane is untagged camera/log. Rec.709 ODT pane is tagged `CGColorSpace.itur_709` only when the ODT node is on.
- Clip list is a `LazyVStack` (virtualized).

Full-quality output is the Resolve export graph (or a future offline render), not the preview.

## Verification status

No golden samples have been measured. Do not claim accuracy. See `ACCEPTANCE.md`.

## Out of scope (M1)

- Full node editor / grading (serial four-slot graph only: IDT → Exposure → WB → ODT)
- Treating the DIY Rec.709 OETF as a standard deliverable (it is preview only)
- Homemade HLG/PQ curves (HDR OT is ACES/BT.2100 Builtin only)
- Apple Log 2, DJI D-Log M, ARRI LogC3 (explicitly unsupported)
- Inventing a C-Log2 mirrored toe (use OCIO `CURVE - CANON_CLOG2_to_LINEAR` / `CANON_CLOG2-CGAMUT_to_ACES2065-1` / ACES CTL)
- Camera-protocol reverse engineering, marketplace integrations
- Treating QuickTime nclc as log identity
- Using the preview as a substitute for a full render
- 一键还原 / claiming a one-click restore (primary action is 处理已锁定片段; pending is 先选择 Log 与色域)

## Layout

```
color/          Python source of truth (curves, WB, serial graph, pipeline, detection)
tests/          pytest (must pass on Linux)
ocio/           config.ocio (BuiltinTransform) + handwritten F-Log2 / N-Log LUTs
macos/LogBridge Xcode / SwiftUI (node strip, inspector, cached preview)
scripts/        LUT/config generator
```
