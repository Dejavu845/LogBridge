# LogBridge M1 + M2-start acceptance gates

Nothing below is claimed as passing. IDTs and HDR OTs are **implemented (unverified)**.

Default language is **ACEScct** / **ACES2065-1**. Rec.709 is preview only. Rec.2100 HLG / PQ are ACES Output Transform / BT.2100 (unverified). WB is ACES2065-1 (AP0) scene-linear. Implemented (unverified). Not supported. Not 一键精准.

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
| Canon C-Log2 | ~0.39825 | pending golden |
| Canon C-Log3 | ~0.34339 | pending golden |
| Apple Log 1 | ~0.48827 | pending golden |
| DJI D-Log | ~0.39876 | pending golden |

Sony: one grey card in **S-Gamut3** and one in **S-Gamut3.Cine**. Do not treat Cine as the default.

Unit tests already assert these encodings mathematically. Golden files are a different gate.

## Rec.709 tagged preview

- **ODT / processed pane only:** Metal/AppKit layer `colorspace` is `CGColorSpace.itur_709`.
- **Source pane is not Rec.709-tagged.** It stays camera/log or working-space / untagged so the split is a real comparison.
- Rec.709 ODT pixels are not blit into an untagged (Display P3) surface, and are not shown in the source pane.

Both preview panes overlay **预览·非成片**. 8-bit thumbnail is not a deliverable.

Gate: screenshot or Instruments/Core Image probe showing the *ODT* drawable color space is BT.709 and the source drawable is not. Overlay badge text includes 预览·非成片.

## Serial node graph (M1 + M2-start ODT)

- UI shows four serial slots: IDT → Exposure → WB → ODT (`color/graph.py` `SerialGraph`).
- Locked order: IDT → Exposure (stops) → WB → ACEScct → preview ODT (709 / HLG / PQ).
- Exposure is stops (default 0). Internally after IDT, in ACES2065-1 linear: `rgb * (2 ** stops)`. Not a log-code add. Bypassable / zeroable. Own export node (1D / gain) — not baked into IDT or WB when stops=0.
- ODT selector: Off (ACEScct deliverable) | Rec.709 preview | Rec.2100 HLG | Rec.2100 PQ. Default Off.
- Click a node to inspect parameters. Exposure inspector when Exposure is selected. WB / Exposure / ODT are bypassable; IDT is not.
- WB off = IDT → Exposure → ACEScct, no bake in preview and in Resolve export (`graph.xml` `enabled="false"`).
- WB CAT runs in ACES2065-1 (AP0) scene-linear, never on ACEScct-encoded values. Preview cache stores post-IDT linear; exposure + WB apply in linear.
- **As-shot writes only the existing linear AP0 CAT node** (knobs / UI only). Camera-private CCT + tint (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD, Apple/DJI if present). Not QuickTime nclc. Never a CAT on camera-log or ACEScct-encoded values. Log IDTs assume already white-balanced; **default CAT is identity**. Do not treat as-shot 5600/6504 as an illuminant (double WB). Apply CAT only when the user moves CCT/tint away from as-shot, or on a grey-card override. User can still change CCT/tint or bypass WB.
- **Missing CCT/tint → knobs empty / pending / identity.** Do not guess 5600 or 6504.
- **Grey-card pick** samples **after IDT in ACES2065-1 (AP0) linear**, sets CCT/tint, and **that is a real CAT** (override; identity only if sampled D65). Implemented (unverified).
- Rec.709 ODT is preview only, off by default. Off = ACEScct deliverable. UI must not imply grading on the 709 pane as a finished picture (预览·非成片).
- Rec.2100 HLG / PQ: HDR OT via ACES/BT.2100 BuiltinTransform (unverified). No homemade HLG/PQ curve. Not supported.
- Not a general node editor. No sat / unlisted grade nodes.

## Resolve export — WB toggle

- Export is a Resolve-importable graph (`graph.xml` / `graph.dot`) plus `01_IDT_*.cube`, `02_Exposure.{cube,dctl}`, `03_WB.{cube,cdl,ccc,dctl}`, `04_ODT_Rec709.cube` — not a prose sidecar only.
- **Exposure is its own 1D/gain node** (Color page serial node 2). **WB is its own corrector/node** (Color page serial node 3). Disable it, or tick DCTL **Bypass WB**, or skip `02_WB.cube` / the CDL.
- WB is a linear AP0 Bradford/CAT02 3×3 (or DI-free DCTL on ACES2065-1 / ACEScct-decoded-to-linear), not baked into the IDT or Rec.709 cubes.
- Standard deliverable is **ACEScct or ACES2065-1 EXR / ACES workflow** (**导出 ACEScct / EXR**). Rec.709 is preview only (node 3 off by default). Rec.2100 HLG/PQ are optional ACES/BT.2100 OT (unverified). Remaining graph when WB is off: IDT → ACEScct, no bake.

Gate: open the export in Resolve; bypassing the WB node must restore uncorrected camera linear (after IDT). Implemented (unverified).

## HDR OT via ACES/BT.2100 (M2-start)

- Rec.2100 HLG and Rec.2100 PQ are declared ODT paths using OCIO **ACES Output Transform / BT.2100** naming (`ACES-OUTPUT … HLG_1.1` / `… ST2084_1.1` + `DISPLAY … REC.2100-*`, or ACES 2.0 Rec.2100 styles if the registry has them; config-aces aliases `Output - Rec.2100-HLG - 1000 nit` / `Output - Rec.2100-Rec.2020-ST2084 - 1000 nit`).
- Prefer OCIO Builtin / ACES OT. Do not invent a homemade HLG/PQ curve.
- Status: **implemented (unverified)** until golden samples. Not “supported”. Not 一键精准.
- Applying HDR without OCIO must not fall back to a DIY transfer.

## Other gates

- Detection ignores QuickTime `nclc` for S-Log3 / LogC4 and for as-shot CCT/tint.
- S-Log3 without gamut metadata requires the paired IDT picker (never silent Cine, never two dropdowns). Venice pairs appear only if Venice is detected.
- Nikon path does not divide 10-bit codes by 1023 before the white-paper curve.
- C-Log2 negative toe is OCIO / ACES CTL (not an invented mirrored toe).
- C-Log2 without gamut requires the paired picker (never silent Cinema Gamut).
- C-Log3 without gamut requires the paired picker (never silent Cinema Gamut).
- D-Log M, Apple Log 2, and ARRI LogC3 stay unsupported.
- `ocio/config.ocio` names BuiltinTransform styles; Linux 18% tests use reference curves only.

## Pending IDT / process lock

- Clips without a locked curve+gamut pair stay **pending**.
- **处理已锁定片段** / **Apply graph** and **导出 ACEScct / EXR** are blocked for pending clips.
- Primary button is **处理已锁定片段** — never 一键还原. Pending (disabled): **先选择 Log 与色域**.
- Main path: drop → lock IDT → exposure/WB → 处理已锁定片段. One primary process button.
- WB inspector shows three states: 机内 as-shot / 白平衡（估计） / 灰卡. Estimate needs confirm. Grey-card overrides.
- HDR preview titles say 预览·非成片 and 未匹配 709. Do not present HLG/PQ as matched to Rec.709.
- IDT picker is one paired list (S-Log3 + S-Gamut3 vs S-Log3 + S-Gamut3.Cine), not two dropdowns.
- Venice pairs appear only if a Venice body is detected.

## As-shot white balance

- As-shot CCT + tint from camera-private metadata fills the WB knobs (UI only).
- Default CAT is identity. Log IDTs assume the image is already white-balanced.
- Do **not** treat as-shot 5600/6504 as an illuminant and CAT toward D65 (double WB).
- Apply AP0 CAT only when the user moves CCT/tint away from as-shot, or on a grey-card override.
- User move is relative: `CAT(user→D65)·inv(CAT(as→D65))` == `CAT(user→as)` in AP0. 3200→5600 warms. Not `CAT(as→user)`, not `CAT(user→D65)` alone. First typed CCT with no as-shot is a label (identity).
- Missing CCT does **not** apply 5600 K. Knobs empty / pending / identity.
- Grey-card / pick-neutral overrides as-shot and **is** an absolute CAT of the sampled white to D65 (identity only if sampled D65). Golden grey-card samples are still required. Labels stay **implemented (unverified)**.
- Auto WB is **白平衡（估计）**, not 精准 / 一键校准. SoG p=6 in linear ACEScg after IDT; confirm writes an absolute AP0 CAT. Residual <2°, mixed-light tile angle >5°, or valid pixels <15% stay empty. Never guess 5600. Never read Rec.709 pixels. Grey-card overrides the estimate. As-shot default stays identity.

## Media (no manufacturer demos)

- LogBridge does **not** ship camera manufacturer demo clips (no ARRI / Sony / RED / Panasonic / Nikon / Fujifilm sample reels).
- The user drops their own Log files or folders. Empty-state copy: drop a folder of mixed clips.
