"""Serial node graph: IDT → Exposure → WB (bypassable) → selectable ODT.

Not a node editor. Used by ``pipeline`` and Resolve export.

  1. IDT       — camera log → ACES2065-1 (AP0 scene-linear). No WB, no exposure.
  2. Exposure  — stops (default 0). In ACES2065-1 linear: rgb * (2 ** stops).
                 Not a log-code add. Bypassable / zeroable. Own export node
                 (1D / gain); not baked into IDT or WB when stops=0.
  3. WB        — Bradford/CAT02 in ACES2065-1 scene-linear (AP0). Never a CAT
                 on ACEScct-encoded values. Bypassable. Disable WB =
                 IDT → Exposure → ACEScct (timeline), no bake.
  4. ODT       — Off (ACEScct deliverable, default) | Rec.709 preview |
                 Rec.2100 HLG | Rec.2100 PQ. Rec.709 is preview only (DIY
                 BT.709 OETF, no RRT). HLG/PQ are ACES Output Transform /
                 BT.2100 OCIO Builtins — no homemade HLG/PQ curve.

Locked order: IDT → Exposure → WB → ACEScct → preview ODT.
Uniform gain and CAT commute; the order is still locked.
Working / deliverable: ACEScct timeline or ACES2065-1 EXR / ACES workflow.
Rec.709 is preview only. HLG/PQ are implemented (unverified). Not supported.
Do not bake DaVinci Wide Gamut Intermediate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .gamuts import IDT_PAIRS, aces_to_rec709_matrix
from .odt import (
    HDR_ODTS,
    ODT_CHOICES,
    ODT_DEFAULT,
    ODT_HLG,
    ODT_OFF,
    ODT_PQ,
    ODT_REC709,
    apply_hdr_odt,
)
from .exposure import apply_exposure, stops_to_gain
from .rec709 import rec709_oetf
from .wb import apply_white_balance
from .working_space import (
    aces2065_to_acescct,
    acescct_to_aces2065,
)

NODE_IDT = "IDT"
NODE_EXPOSURE = "Exposure"
NODE_WB = "WB"
NODE_ODT = "ODT_Rec709"
NODE_ODT_HLG = "ODT_Rec2100_HLG"
NODE_ODT_PQ = "ODT_Rec2100_PQ"
GRAPH_NODES = (NODE_IDT, NODE_EXPOSURE, NODE_WB, NODE_ODT)
# ODT slot selector. Default Off = ACEScct deliverable.
ODT_OFF = ODT_OFF
ODT_REC709 = ODT_REC709
ODT_HLG = ODT_HLG
ODT_PQ = ODT_PQ
ODT_CHOICES = ODT_CHOICES
ODT_DEFAULT = ODT_DEFAULT
EXPORT_SLOTS = (
    (1, NODE_IDT, "01_IDT"),
    (2, NODE_EXPOSURE, "02_Exposure"),
    (3, NODE_WB, "03_WB"),
    (4, NODE_ODT, "04_ODT"),
)

WORKING_SPACE = "ACEScct"
SCENE_LINEAR = "ACES2065-1"
WB_LINEAR_SPACE = "AP0"


@dataclass
class GraphNode:
    index: int
    name: str
    export_basename: str
    enabled: bool = True
    bypassable: bool = False


def odt_node_name(odt: str) -> str:
    """Export / graph name for the ODT slot. Default slot stays ODT_Rec709."""
    if odt == ODT_HLG:
        return NODE_ODT_HLG
    if odt == ODT_PQ:
        return NODE_ODT_PQ
    return NODE_ODT


@dataclass
class SerialGraph:
    """Fixed four-node graph: IDT → Exposure → WB → ODT.

    Exposure is stop-based linear gain in ACES2065-1 (default 0 = identity).
    WB is bypassable. ``odt`` selects Off | Rec.709 preview | Rec.2100 HLG |
    Rec.2100 PQ. ``odt_enabled=True`` (legacy) means Rec.709 preview when
    ``odt`` is Off.
    """

    idt_id: str | None = None
    exposure_stops: float = 0.0
    exposure_enabled: bool = True
    wb_enabled: bool = False
    wb_cct: float = 6504.0
    wb_tint: float = 0.0
    wb_method: str = "bradford"
    odt_enabled: bool = False
    odt: str = ODT_OFF

    def __post_init__(self) -> None:
        if self.odt not in ODT_CHOICES:
            raise ValueError(f"Unknown ODT {self.odt!r} (use {ODT_CHOICES})")
        if self.odt != ODT_OFF:
            self.odt_enabled = True
        elif self.odt_enabled:
            self.odt = ODT_REC709

    @property
    def apply_wb(self) -> bool:
        return self.wb_enabled

    @property
    def apply_odt(self) -> bool:
        return self.odt != ODT_OFF

    @property
    def cct(self) -> float:
        return self.wb_cct

    @property
    def tint(self) -> float:
        return self.wb_tint

    def odt_slot_name(self) -> str:
        return odt_node_name(self.odt)

    def nodes(self) -> list[GraphNode]:
        return [
            GraphNode(1, NODE_IDT, "01_IDT", enabled=True, bypassable=False),
            GraphNode(
                2,
                NODE_EXPOSURE,
                "02_Exposure",
                enabled=self.exposure_enabled,
                bypassable=True,
            ),
            GraphNode(3, NODE_WB, "03_WB", enabled=self.wb_enabled, bypassable=True),
            GraphNode(
                4,
                self.odt_slot_name(),
                "04_ODT",
                enabled=self.odt_enabled,
                bypassable=True,
            ),
        ]

    def node(self, index: int) -> GraphNode:
        for n in self.nodes():
            if n.index == index:
                return n
        raise KeyError(index)

    def set_enabled(self, index: int, enabled: bool) -> None:
        if index == 1:
            raise ValueError("IDT is not bypassable")
        if index == 2:
            self.exposure_enabled = bool(enabled)
        elif index == 3:
            self.wb_enabled = bool(enabled)
        elif index == 4:
            if enabled:
                if self.odt == ODT_OFF:
                    self.odt = ODT_REC709
                self.odt_enabled = True
            else:
                self.odt = ODT_OFF
                self.odt_enabled = False
        else:
            raise KeyError(index)

    def set_exposure_stops(self, stops: float) -> None:
        self.exposure_stops = float(stops)

    @property
    def exposure_gain(self) -> float:
        if not self.exposure_enabled:
            return 1.0
        return stops_to_gain(self.exposure_stops)

    def set_odt(self, odt: str) -> None:
        if odt not in ODT_CHOICES:
            raise ValueError(f"Unknown ODT {odt!r} (use {ODT_CHOICES})")
        self.odt = odt
        self.odt_enabled = odt != ODT_OFF

    def idt_node(self, log_rgb, idt_id: str | None = None) -> np.ndarray:
        """IDT: camera log → ACES2065-1 linear (AP0). No WB, no exposure.

        Preview cache stores this buffer. Exposure + WB apply in linear
        on top of it. ACEScct encode is only for grading / preview
        display / the Resolve timeline.
        """
        from .pipeline import apply_idt

        chosen = idt_id or self.idt_id
        if not chosen:
            raise ValueError("IDT is required")
        return apply_idt(log_rgb, chosen)

    def idt_to_acescct(self, log_rgb, idt_id: str | None = None) -> np.ndarray:
        """IDT then ACEScct encode (timeline / grading). No WB."""
        return aces2065_to_acescct(self.idt_node(log_rgb, idt_id))

    def exposure_node(self, aces_ap0) -> np.ndarray:
        """Exposure: uniform gain in ACES2065-1 linear. Identity at 0 / bypass.

        ``rgb * (2 ** stops)``. Not an add/subtract on log code values.
        """
        rgb = np.asarray(aces_ap0, dtype=np.float64)
        if not self.exposure_enabled or self.exposure_stops == 0.0:
            return rgb
        return apply_exposure(rgb, self.exposure_stops)

    def wb_node(self, aces_ap0) -> np.ndarray:
        """WB CAT in ACES2065-1 (AP0) scene-linear. Identity when disabled.

        Input must be ACES2065-1 linear, not ACEScct-encoded.
        """
        rgb = np.asarray(aces_ap0, dtype=np.float64)
        if not self.wb_enabled:
            return rgb
        return apply_white_balance(
            rgb,
            self.wb_cct,
            tint=self.wb_tint,
            rgb_space=WB_LINEAR_SPACE,
            method=self.wb_method,
        )

    def wb_on_acescct(self, acescct_rgb) -> np.ndarray:
        """ACEScct in/out wrapper: decode → AP0 CAT → encode. Not a CAT on log."""
        enc = np.asarray(acescct_rgb, dtype=np.float64)
        if not self.wb_enabled:
            return enc
        ap0 = acescct_to_aces2065(enc)
        ap0 = self.wb_node(ap0)
        return aces2065_to_acescct(ap0)

    def odt_node(self, aces_ap0) -> np.ndarray:
        """Preview ODT: ACES2065-1 → Rec.709 encoded. Not the deliverable."""
        m = aces_to_rec709_matrix("AP0")
        rec_lin = np.asarray(aces_ap0, dtype=np.float64) @ m.T
        return rec709_oetf(np.clip(rec_lin, 0.0, None))

    def apply(self, log_rgb, idt_id: str | None = None) -> np.ndarray:
        """Run IDT → Exposure (AP0 linear) → optional WB (AP0) → optional ODT.

        ODT off: ACES2065-1 scene-linear (ACEScct deliverable when encoded
        for the Resolve timeline). Rec.709 is preview only. HLG/PQ use
        ACES Output Transform / BT.2100 (OCIO Builtin; no homemade curve).
        """
        chosen = idt_id or self.idt_id
        if not chosen:
            raise ValueError("IDT is required")
        if chosen not in IDT_PAIRS:
            raise KeyError(f"Unknown IDT {chosen!r}")
        work = self.idt_node(log_rgb, chosen)
        work = self.exposure_node(work)
        work = self.wb_node(work)
        if self.odt == ODT_REC709:
            return self.odt_node(work)
        if self.odt in HDR_ODTS:
            return apply_hdr_odt(work, self.odt)
        return work

    def process(self, log_rgb, idt_id: str) -> np.ndarray:
        """Alias for ``apply`` used by the pipeline."""
        return self.apply(log_rgb, idt_id)


def graph_from_export_args(
    idt_id: str | None = None,
    cct: float = 6504.0,
    tint: float = 0.0,
    include_wb: bool = True,
    odt_enabled: bool = False,
    method: str = "bradford",
    odt: str | None = None,
    exposure_stops: float = 0.0,
    exposure_enabled: bool = True,
) -> SerialGraph:
    """Build a SerialGraph from Resolve-export CLI / Swift flags.

    ODT defaults Off (ACEScct deliverable). Rec.709 is preview only.
    HLG/PQ are ACES Output Transform / BT.2100 (unverified).
    Exposure is its own node (default 0 stops = identity gain).
    """
    chosen = odt if odt is not None else (ODT_REC709 if odt_enabled else ODT_OFF)
    return SerialGraph(
        idt_id=idt_id,
        exposure_stops=exposure_stops,
        exposure_enabled=exposure_enabled,
        wb_enabled=include_wb,
        wb_cct=cct,
        wb_tint=tint,
        wb_method=method,
        odt_enabled=odt_enabled,
        odt=chosen,
    )
