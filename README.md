# LogBridge

macOS batch tool: mixed-camera Log → ACES2065-1 (IDT) → ACEScct (WB / preview) → Rec.709 ODT.

M1 is a **serial node graph** (IDT → WB → ODT Rec.709), not a general node editor and not a Resolve-like grade. Every IDT is **implemented (unverified)** until golden grey-card samples are measured. This project does not describe cameras as “supported”. There is no 一键精准.

Internal working encoding: **ACEScct** (AP1 log). Scene-linear interchange / `roles.scene_linear`: **ACES2065-1** (Linear AP0). `roles.color_timing`: ACEScct. White balance is Bradford (or CAT02) chromatic adaptation in ACEScg (AP1) scene-linear only. DaVinci Wide Gamut Intermediate is **not** the default internal or deliverable.

## OpenColorIO

Mac OpenColorIO uses **BuiltinTransform** styles named in `ocio/config.ocio` (`ARRI_LOGC4_to_ACES2065-1`, `SONY_SLOG3-SGAMUT3_to_ACES2065-1`, `SONY_SLOG3-SGAMUT3.CINE_to_ACES2065-1`, `PANASONIC_VLOG-VGAMUT_to_ACES2065-1`, `RED_LOG3G10-RWG_to_ACES2065-1`). Venice Builtins are detect-only, never a silent S-Log3 default.

Linux tests use `color/` white-paper **reference encode/decode for 18% codes only**. They do not require PyOpenColorIO. F-Log2 and N-Log have no standard Builtin — those papers stay handwritten.

Python curves in `color/` are the source of truth for 18% tests. Regenerating OCIO assets:

```bash
python3 scripts/generate_ocio_assets.py
```

## Open in Xcode (macOS)

1. Copy this tree to a Mac.
2. Open `macos/LogBridge/LogBridge.xcodeproj` in Xcode 15+ (macOS 14 deployment target).
3. Select the **LogBridge** scheme, destination **My Mac**, and Run.

Layout: drop zone + clip list (LazyVStack) | split preview | node strip | inspector.

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

Sony S-Log3 is **two locked pairs**. Metadata or the user picks the gamut. LogBridge never defaults S-Log3 to S-Gamut3.Cine. Missing metadata opens a **curve and gamut** picker — no silent IDT.

Nikon N-Log white-paper `x` is a **10-bit code value 0–1023**. Do not divide by 1023 before the curve. 452 is the breakpoint, not 18% grey (~372). The OCIO LUT is sampled on 0–1 = code/1023 so image buffers stay normalized; the Python API takes 10-bit codes.

Fujifilm F-Log2 uses Data Sheet 1.0 + BT.2020 (`a=5.555556`). Not an F-Log1 LUT.

## Detection order

1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
2. Filename / model hint
3. User picker

QuickTime `nclc` / `nclx` / `colr` is **never** used to identify S-Log3 or LogC4.

## Node workflow (M1, serial only)

Visible graph, three slots — `color/graph.py` `SerialGraph`, used by `color/pipeline.py` and Resolve export:

1. **IDT** (`01_IDT`) — locked curve+gamut pair → ACES2065-1 → ACEScct. Not bypassable.
2. **WB** (`02_WB`) — scene-linear Bradford/CAT02 in ACEScg, CCT + green-magenta tint. **Bypassable.** Node 2 off = no bake in preview or export (XML `enabled="false"`; disable the Resolve corrector / DCTL **Bypass WB**).
3. **ODT Rec.709** (`03_ODT`) — optional. Off = ACEScct / ACES2065-1 working-space deliverable (timeline stays ACEScct). Preview tags `CGColorSpace.itur_709` only when this node is on.

Click a node in the strip to inspect its parameters. No extra grade nodes (exposure/sat).

Python: `from color.graph import SerialGraph`. Swift: `SerialGraph` + `NodeSlot` in `Models/NodeGraph.swift`. Status: implemented (unverified).

### Resolve export — bypass WB

Export writes a serial **node graph**, not a prose sidecar: `graph.xml`, `graph.dot`, `01_IDT_<idt>.cube`, `02_WB.cube` / `.cdl` / `.ccc` / `.dctl`, `03_ODT_Rec709.cube`, `README_RESOLVE.md`.

Timeline: **ACEScct**, ACES workflow. Scene-linear interchange: **ACES2065-1**. Do not bake DWG Intermediate as the default deliverable.

Python: `from color.resolve_export import export_resolve_bundle` (pass `graph=` or `include_wb=`). Swift: `ResolveExporter.export(to:clips:...)`. Status: implemented (unverified).

## Preview vs full render

The macOS split preview is **not** a full-resolution render:

- One downscaled frame per clip (long edge ≤ 1920) via ImageIO thumbnail or `AVAssetImageGenerator` (VideoToolbox).
- Cached per clip: decoded camera/log buffer + IDT ACES / ACEScct buffer. IDT change invalidates linear; WB/ODT reuse it. Clip change reuses the decode if the URL is unchanged.
- Color apply runs off the main thread. 8-bit thumbnails are a viewing proxy — do not judge IDT accuracy from the preview.
- Source pane is untagged camera/log. Rec.709 ODT pane is tagged `CGColorSpace.itur_709` only when the ODT node is on.
- Clip list is a `LazyVStack` (virtualized).

Full-quality output is the Resolve export graph (or a future offline render), not the preview.

## Verification status

No golden samples have been measured. Do not claim accuracy. See `ACCEPTANCE.md`.

## Out of scope (M1)

- Full node editor / grading (serial three-slot graph only)
- ACES RRT / a display rendering transform beyond a simple Rec.709 OETF
- Canon C-Log2 / C-Log3, Apple Log, DJI D-Log (stubs only)
- C-Log2 negative toe: use OCIO `CURVE - CANON_CLOG2_to_LINEAR` or ACES CLF; do not invent a mirrored toe
- Camera-protocol reverse engineering, marketplace integrations
- Treating QuickTime nclc as log identity
- Using the preview as a substitute for a full render

## Layout

```
color/          Python source of truth (curves, WB, serial graph, pipeline, detection)
tests/          pytest (must pass on Linux)
ocio/           config.ocio (BuiltinTransform) + handwritten F-Log2 / N-Log LUTs
macos/LogBridge Xcode / SwiftUI (node strip, inspector, cached preview)
scripts/        LUT/config generator
```
