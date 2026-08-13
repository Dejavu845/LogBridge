"""Serial node graph: IDT → WB (bypassable) → ODT.

Not a node editor. Used by ``pipeline`` and Resolve export.

  1. IDT  — camera log → ACES2065-1, then ACEScct (no WB)
  2. WB   — scene-linear Bradford/CAT02 in ACEScg (AP1), wrapped in ACEScct.
            Bypassable. Disable to restore IDT → ACEScct → optional Rec.709 ODT.
  3. ODT  — ACEScct → Rec.709 encoded (BT.709 OETF, no RRT). Optional later node.

Working space is ACEScct. Do not bake DaVinci Wide Gamut Intermediate.
DWG Intermediate remains an optional named export space only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .gamuts import IDT_PAIRS, aces_to_rec709_matrix
from .rec709 import rec709_oetf
from .wb import apply_white_balance
from .working_space import (
    DEFAULT_WORKING_LINEAR,
    aces2065_to_acescct,
    acescct_decode,
    acescct_encode,
)

NODE_IDT = "IDT"
NODE_WB = "WB"
NODE_ODT = "ODT_Rec709"
GRAPH_NODES = (NODE_IDT, NODE_WB, NODE_ODT)
EXPORT_SLOTS = (
    (1, NODE_IDT, "01_IDT"),
    (2, NODE_WB, "02_WB"),
    (3, NODE_ODT, "03_ODT"),
)

WORKING_SPACE = "ACEScct"
SCENE_LINEAR = "ACES2065-1"


@dataclass
class GraphNode:
    index: int
    name: str
    export_basename: str
    enabled: bool = True
    bypassable: bool = False


@dataclass
class SerialGraph:
    """Fixed three-node graph. WB is the only required bypassable grade node."""

    idt_id: str | None = None
    wb_enabled: bool = False
    wb_cct: float = 6504.0
    wb_tint: float = 0.0
    wb_method: str = "bradford"
    odt_enabled: bool = True

    @property
    def apply_wb(self) -> bool:
        return self.wb_enabled

    @property
    def apply_odt(self) -> bool:
        return self.odt_enabled

    @property
    def cct(self) -> float:
        return self.wb_cct

    @property
    def tint(self) -> float:
        return self.wb_tint

    def nodes(self) -> list[GraphNode]:
        return [
            GraphNode(1, NODE_IDT, "01_IDT", enabled=True, bypassable=False),
            GraphNode(2, NODE_WB, "02_WB", enabled=self.wb_enabled, bypassable=True),
            GraphNode(3, NODE_ODT, "03_ODT", enabled=self.odt_enabled, bypassable=True),
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
            self.wb_enabled = bool(enabled)
        elif index == 3:
            self.odt_enabled = bool(enabled)
        else:
            raise KeyError(index)

    def idt_node(self, log_rgb, idt_id: str | None = None) -> np.ndarray:
        """IDT: camera log → ACEScct. No white balance."""
        from .pipeline import apply_idt

        chosen = idt_id or self.idt_id
        if not chosen:
            raise ValueError("IDT is required")
        aces = apply_idt(log_rgb, chosen)
        return aces2065_to_acescct(aces)

    def wb_node(self, acescct_rgb) -> np.ndarray:
        """WB in ACEScg linear, ACEScct in/out. Identity when disabled."""
        enc = np.asarray(acescct_rgb, dtype=np.float64)
        if not self.wb_enabled:
            return enc
        ap1 = acescct_decode(enc)
        ap1 = apply_white_balance(
            ap1,
            self.wb_cct,
            tint=self.wb_tint,
            rgb_space=DEFAULT_WORKING_LINEAR,
            method=self.wb_method,
        )
        return acescct_encode(ap1)

    def odt_node(self, acescct_rgb) -> np.ndarray:
        """ODT: ACEScct → Rec.709 encoded. No WB."""
        ap1 = acescct_decode(np.asarray(acescct_rgb, dtype=np.float64))
        m = aces_to_rec709_matrix("AP1")
        rec_lin = ap1 @ m.T
        return rec709_oetf(np.clip(rec_lin, 0.0, None))

    def apply(self, log_rgb, idt_id: str | None = None) -> np.ndarray:
        """Run IDT → optional WB → optional Rec.709 ODT."""
        chosen = idt_id or self.idt_id
        if not chosen:
            raise ValueError("IDT is required")
        if chosen not in IDT_PAIRS:
            raise KeyError(f"Unknown IDT {chosen!r}")
        work = self.idt_node(log_rgb, chosen)
        work = self.wb_node(work)
        if self.odt_enabled:
            return self.odt_node(work)
        # ODT off: ACEScg (AP1) scene-linear, not ACEScct and not Rec.709.
        return acescct_decode(work)

    def process(self, log_rgb, idt_id: str) -> np.ndarray:
        """Alias for ``apply`` used by the pipeline."""
        return self.apply(log_rgb, idt_id)


def graph_from_export_args(
    idt_id: str | None = None,
    cct: float = 6504.0,
    tint: float = 0.0,
    include_wb: bool = True,
    odt_enabled: bool = True,
    method: str = "bradford",
) -> SerialGraph:
    """Build a SerialGraph from Resolve-export CLI / Swift flags."""
    return SerialGraph(
        idt_id=idt_id,
        wb_enabled=include_wb,
        wb_cct=cct,
        wb_tint=tint,
        wb_method=method,
        odt_enabled=odt_enabled,
    )
