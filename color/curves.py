"""Manufacturer log curve encode/decode (reference implementations).

When OpenColorIO Python is importable, IDTs with a BuiltinTransform
(LogC4, S-Log3, V-Log, Log3G10, Venice) call that Builtin to ACES2065-1.
These functions stay as the Linux/no-OCIO reference and as the 18% grey
unit-test source. They match the Builtins on documented 18% codes to well
under 0.5%. Do not replace them with invented “more accurate” constants.

F-Log2 and N-Log have no standard Builtin — these papers are the IDT.

Inputs are normalized 0-1 except Nikon N-Log, whose white-paper ``x`` is a
10-bit code value in 0-1023. Do not divide N-Log by 1023 before the curve.

References (public white papers):
- ARRI LogC4 Specification (2025-01-23)
- Sony Technical Summary S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3
- Panasonic VARICAM V-Log/V-Gamut (2014-11-28)
- Fujifilm F-Log2 Data Sheet Ver.1.0 / GFX ETERNA white paper
- Nikon N-Log Specification Document 1.0.0 (2018-09-01)
- RED OPS White Paper on REDWideGamutRGB and Log3G10 (915-0187 Rev-C)
- Canon Log Gamma Curves white paper (revised C-Log2 / C-Log3) / ACES CTL
- Apple Log Profile White Paper (September 2023) — Log 1 curve (Log 2 reuses this)
- ACES ``Lib.Arri.LogC3`` / ``CSC.Arri.LogCv3-EI800_to_ACES.ctl`` (EI800 only)
- ACES ``CSC.Apple.AppleLog2_to_ACES.ctl`` (same Apple Log curve + Apple Wide Gamut)
- DJI White Paper on D-Log and D-Gamut (2017-10-10)
"""

from __future__ import annotations

import numpy as np
