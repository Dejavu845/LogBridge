# LogBridge M1 acceptance gates

Nothing below is claimed as passing. IDTs are **implemented (unverified)**.

## Golden grey-card samples (per log)

Shoot or obtain a grey card (18% reflectance) in each encoding, exposed to the manufacturer’s documented mid-grey code value. Decode with `color/` and confirm scene-linear RGB ≈ 0.18, 0.18, 0.18 (neutral, D65-balanced light).

| Encoding | Documented 18% code | Gate |
| --- | --- | --- |
| ARRI LogC4 | 0.2784 (table: 27.84% IRE / 12-bit full 1140) | pending golden |
| Sony S-Log3 | 420 / 1023 (IRE 20%) | pending golden |
| Panasonic V-Log | 433 / 1023 (IRE 42%) | pending golden |
| Fujifilm F-Log2 | 400 / 1023 | pending golden |
| Nikon N-Log | ~372 / 10-bit (IRE ~35%) | pending golden |
| RED Log3G10 | 1/3 | pending golden |

Sony: one grey card in **S-Gamut3** and one in **S-Gamut3.Cine**. Do not treat Cine as the default.

Unit tests already assert these encodings mathematically. Golden files are a different gate.

## Rec.709 tagged preview

- Metal/AppKit layer `colorspace` is `CGColorSpace.itur_709`.
- Rec.709 ODT pixels are not blit into an untagged (Display P3) surface.
- Split preview shows source vs Rec.709 output placeholders until decode lands.

Gate: screenshot or Instruments/Core Image probe showing the drawable color space is BT.709.

## Resolve export — WB toggle

- Export graph has a **WB node** that can be enabled or bypassed.
- WB is scene-linear Bradford/CAT02 (CCT + tint), not baked only into a Rec.709 file.
- Timeline/working space remains DaVinci Wide Gamut Intermediate when WB is off.

Gate: open the export in Resolve; bypassing the WB node must restore uncorrected camera linear (after IDT).

## Other gates

- Detection ignores QuickTime `nclc` for S-Log3 / LogC4.
- S-Log3 without gamut metadata requires the user picker (never silent Cine).
- Nikon path does not divide 10-bit codes by 1023 before the white-paper curve.
- Canon C-Log2 stub does not ship an invented negative toe.
