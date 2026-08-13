# LogBridge M1 acceptance gates

Nothing below is claimed as passing. IDTs are **implemented (unverified)**.

Default language is **ACEScct** / **ACES2065-1**, not DaVinci Wide Gamut Intermediate.

## Golden grey-card samples (per log)

Shoot or obtain a grey card (18% reflectance) in each encoding, exposed to the manufacturer’s documented mid-grey code value. Decode with `color/` and confirm ACES scene-linear RGB ≈ 0.18, 0.18, 0.18 after IDT.

| Encoding | Documented 18% code | Gate |
| --- | --- | --- |
| ARRI LogC4 | 0.2784 (table: 27.84% IRE / 12-bit full 1140) | pending golden |
| Sony S-Log3 | 420 / 1023 (IRE 20%) | pending golden |
| Panasonic V-Log | 433 / 1023 (IRE 42%) | pending golden |
| Fujifilm F-Log2 | 400 / 1023 | pending golden |
| Nikon N-Log | ~372 / 10-bit (IRE ~35%; 452 is the breakpoint) | pending golden |
| RED Log3G10 | 1/3 | pending golden |

Sony: one grey card in **S-Gamut3** and one in **S-Gamut3.Cine**. Do not treat Cine as the default.

Unit tests already assert these encodings mathematically. Golden files are a different gate.

## Rec.709 tagged preview

- **ODT / processed pane only:** Metal/AppKit layer `colorspace` is `CGColorSpace.itur_709`.
- **Source pane is not Rec.709-tagged.** It stays camera/log or working-space / untagged so the split is a real comparison.
- Rec.709 ODT pixels are not blit into an untagged (Display P3) surface, and are not shown in the source pane.

Gate: screenshot or Instruments/Core Image probe showing the *ODT* drawable color space is BT.709 and the source drawable is not.

## Serial node graph (M1)

- UI shows three serial slots: IDT → WB → ODT Rec.709 (`color/graph.py` `SerialGraph`).
- Click a node to inspect parameters. WB / ODT are bypassable; IDT is not.
- Node 2 off = no WB bake in preview and in Resolve export (`graph.xml` `enabled="false"`).
- Not a general node editor. No extra grade nodes.

## Resolve export — WB toggle

- Export is a Resolve-importable graph (`graph.xml` / `graph.dot`) plus `01_IDT_*.cube`, `02_WB.{cube,cdl,ccc,dctl}`, `03_ODT_Rec709.cube` — not a prose sidecar only.
- **WB is its own corrector/node** (Color page serial node 2). Disable it, or tick DCTL **Bypass WB**, or skip `02_WB.cube` / the CDL.
- WB is scene-linear Bradford/CAT02 (CCT + tint) in ACEScg, not baked into the IDT or Rec.709 ODT cubes.
- Timeline/working space remains **ACEScct** (ACES workflow; scene-linear **ACES2065-1**) when WB is off. Remaining graph: IDT → ACEScct → optional Rec.709 ODT.
- Do not bake DaVinci Wide Gamut Intermediate as the default deliverable.

Gate: open the export in Resolve; bypassing the WB node must restore uncorrected camera linear (after IDT). Implemented (unverified).

## Other gates

- Detection ignores QuickTime `nclc` for S-Log3 / LogC4.
- S-Log3 without gamut metadata requires the user picker (never silent Cine).
- Nikon path does not divide 10-bit codes by 1023 before the white-paper curve.
- Canon C-Log2 stub does not ship an invented negative toe.
- `ocio/config.ocio` names BuiltinTransform styles; Linux 18% tests use reference curves only.
