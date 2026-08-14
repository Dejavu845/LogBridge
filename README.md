# LogBridge

macOS batch tool: mixed-camera Log → scene-linear (manufacturer white paper) → white balance in linear → Rec.709.

M1 is a **fixed pipeline**, not a node editor. Every IDT is **implemented (unverified)** until golden grey-card samples are measured. This project does not describe cameras as “supported”.

Internal working space: **DaVinci Wide Gamut** (scene-linear) / **DaVinci Intermediate** (log encoding). **ACEScct** is an alternate named space. White balance is Bradford (or CAT02) chromatic adaptation in scene-linear only.

## Open in Xcode (macOS)

1. Copy this tree to a Mac.
2. Open `macos/LogBridge/LogBridge.xcodeproj` in Xcode 15+ (macOS 14 deployment target).
3. Select the **LogBridge** scheme, destination **My Mac**, and Run.

Split preview: the **source** pane is camera/log (untagged working-space dump) and is **not** tagged Rec.709. Only the processed/ODT pane tags `CGColorSpace.itur_709`. Rec.709 pixels are never blit into an untagged Display P3 surface.

Python curves in `color/` are the source of truth. Regenerating OCIO assets:

```bash
python3 scripts/generate_ocio_assets.py
```

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

Sony S-Log3 is **two locked pairs**. Metadata or the user picks the gamut. LogBridge never defaults S-Log3 to S-Gamut3.Cine.

Nikon N-Log white-paper `x` is a **10-bit code value 0–1023**. Do not divide by 1023 before the curve. The OCIO LUT is sampled on 0–1 = code/1023 so image buffers stay normalized; the Python API takes 10-bit codes.

## Detection order

1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
2. Filename / model hint
3. User picker

QuickTime `nclc` / `nclx` / `colr` is **never** used to identify S-Log3 or LogC4.

## Pipeline

`IDT` → optional **WB node** (scene-linear Bradford/CAT02, CCT + green-magenta tint) → **Rec.709 ODT**.

### Resolve export — bypass WB

Export writes a serial **node graph**, not a prose sidecar: `graph.xml`, `graph.dot`, `01_IDT_<idt>.cube`, `02_WB.cube` / `.cdl` / `.ccc` / `.dctl`, `03_ODT_Rec709.cube`, `README_RESOLVE.md`.

Timeline: **DaVinci Wide Gamut / DaVinci Intermediate** (D65).

1. **IDT** — LUT or Resolve Color Space Transform (camera log → DWG Intermediate). No WB.
2. **WB** — own corrector (Bradford/CAT02 in scene-linear DWG, wrapped in DI). Disable this node in the Color page (or DCTL **Bypass WB**) to restore IDT → working space → optional Rec.709 ODT.
3. **Rec.709 ODT** — later LUT/CST. Not the only deliverable.

Python: `from color.resolve_export import export_resolve_bundle`. Swift: `ResolveExporter.export(to:clips:...)`. Status: implemented (unverified).

## Verification status

No golden samples have been measured. Do not claim accuracy. See `ACCEPTANCE.md`.

## Out of scope (M1)

- Full node editor / grading
- ACES RRT / a display rendering transform beyond a simple Rec.709 OETF
- Canon C-Log2 / C-Log3, Apple Log, DJI D-Log (stubs only)
- C-Log2 negative toe: use OCIO `CURVE - CANON_CLOG2_to_LINEAR` or ACES CLF; do not invent a mirrored toe
- Camera-protocol reverse engineering, marketplace integrations
- Treating QuickTime nclc as log identity

## Layout

```
color/          Python source of truth (curves, WB, pipeline, detection)
tests/          pytest (must pass on Linux)
ocio/           config.ocio + SPI1D LUTs + SPIMTX matrices
macos/LogBridge Xcode / SwiftUI scaffold
scripts/        LUT/config generator
```
