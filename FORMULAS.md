# OCIO Builtins (M1 lock)

config.ocio uses BuiltinTransform for LogC4, S-Log3 (SG3 / SG3.Cine / Venice), V-Log, and Log3G10. The curve constants below remain the Linux/no-OCIO reference and the 18% unit-test source. They match the Builtins on documented 18% grey to well under 0.5%. Do not invent replacement constants.

F-Log2 and N-Log have no standard Builtin.

# Formula verification (M1)

Public white papers were fetched where possible. **No manufacturer constant from the research notes was replaced.** Gaps that the notes left as “official segment” were filled from the same papers.

## Unchanged vs research notes

- **ARRI LogC4** decode for `in >= 0` matches the 2025-01-23 spec CTL. `a=(2**18-16)/117.45`, `b=(1023-95)/1023`, `c=95/1023`. AWG4 xy confirmed. 18% grey → 0.2784 (ARRI table).
- **Sony S-Log3** log segment matches. `cut = 171.2102946929/1023`.
- **Panasonic V-Log** decode matches. V-Gamut xy confirmed (R 0.730/0.280, G 0.165/0.840, B 0.100/−0.030, D65). 18% → 433/1023.
- **Fujifilm F-Log2** `a=5.555556` (not F-Log’s `0.555556`). Decode `(10**((in-d)/c))/a - b/a` confirmed in the F-Log2 / GFX ETERNA white paper. 18% → 400/1023.
- **Nikon N-Log** `x` is 10-bit code 0–1023. Do not divide by 1023. 18% → ~372.
- **RED Log3G10** decode matches 915-0187 Rev-C. 18% → 1/3. RWG xy confirmed.

## Filled in (not a constant change)

1. **LogC4 negatives** — research: “linear extension”. Implemented official `s`, `t` from the spec CTL (`E' * s + t` for `E' < 0`; encode uses `Escene < t`).
2. **S-Log3 shadow** — research: “else the official shadow linear segment”. Decode: `(in*1023-95)*0.01125/(171.2102946929-95)`. Encode uses `in >= 0.01125` for the log piece. 0% → 95/1023, 90% → 598/1023.
3. **V-Log encode** — `cut1=0.01`: `5.6*in+0.125` else `c*log10(in+b)+d`.
4. **F-Log2 encode** — `cut1=0.000889`: `e*in+f` else `c*log10(a*in+b)+d`.
5. **N-Log inverse** — spec `log` is **natural log** (pairs with `exp` in decode): `x = 150*ln(y)+619` above the cut.
6. **Log3G10 encode** — white-paper C: `x = lin + c`; if `x < 0` then `x*g` else `a*log10(x*b+1)`.
7. **S-Gamut3 primaries** — Sony states they match conventional S-Gamut: (0.73, 0.28), (0.14, 0.855), (0.10, −0.05). **S-Gamut3.Cine** from the widely used colour-science / ACES set: (0.766, 0.275), (0.225, 0.800), (0.089, −0.087). Sony has not published Cine xy in the Technical Summary; these are community-standard, **implemented (unverified)**. Never the S-Log3 default.

Third-party pages sometimes list F-Log2 `a=0.555556` (that is F-Log). LogBridge keeps `a=5.555556`.


# HDR ODT (M2-start)

Rec.2100 HLG and Rec.2100 PQ are **ACES Output Transform / BT.2100** OCIO BuiltinTransform paths. Do not invent homemade HLG/PQ constants or a DIY Rec.2100 OETF like the Rec.709 preview curve. Apply only via OCIO (`ACES-OUTPUT - ACES2065-1_to_CIE-XYZ-D65 - HDR-VIDEO-1000nits-15nits-HLG_1.1` + `DISPLAY - CIE-XYZ-D65_to_REC.2100-HLG`, and the ST2084 / Rec.2100-PQ pair). Implemented (unverified).


# Exposure (ACES2065-1 linear)

User-facing control is **stops**. After IDT, in ACES2065-1 (AP0) scene-linear:

    rgb_out = rgb_in * (2 ** stops)

- 0 stops is identity (`gain = 1`).
- +1 stop doubles scene-linear RGB.
- Do **not** add or subtract from camera-log or ACEScct code values.
- Then WB / CAT in the same linear AP0 domain. Uniform gain and CAT commute; the locked order is still IDT → Exposure → WB.
- Rec.709 / HLG / PQ remain preview only. ACEScct / EXR is the deliverable.
