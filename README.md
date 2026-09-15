# LogBridge

macOS batch tool: mixed-camera Log → ACES2065-1 (IDT) → Exposure (stops, linear gain) → WB in ACES2065-1 linear (AP0) → ACEScct timeline / optional ODT (Rec.709 preview | Rec.2100 HLG | Rec.2100 PQ).

M1 is a **serial node graph** (IDT → Exposure → WB → selectable ODT), not a general node editor and not a Resolve-like grade. Every IDT and ODT is **implemented (unverified)** until golden grey-card samples are measured. This project does not describe cameras or HDR outputs as “supported”. There is no 一键精准.

M2-start adds optional **Rec.2100 HLG** and **Rec.2100 PQ** ODT nodes via **ACES Output Transform / BT.2100** (OCIO BuiltinTransform, or config-aces names if present). Prefer those Builtins over any handwritten transfer. There is no homemade HLG/PQ curve. HDR OT is unverified — not a one-click accurate path.

Internal working encoding: **ACEScct** (AP1 log). Scene-linear interchange / `roles.scene_linear`: **ACES2065-1** (Linear AP0). `roles.color_timing`: ACEScct. White balance is Bradford (or CAT02) chromatic adaptation in ACES2065-1 (AP0) scene-linear only — never a CAT on ACEScct. DaVinci Wide Gamut Intermediate is **not** the default internal or deliverable.
