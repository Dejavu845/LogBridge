"""Locked-IDT batch policy. No color-number changes.

A clip is processable only when its paired IDT is chosen / locked.
Batch walks locked clips only. Pending / unlocked stay in the list with a
Chinese reason. Never guess 5600 or 6504. Never invent a second process
button. Auto WB estimate does not write CAT until confirm; grey-card
overrides estimate.

Swift ``SessionModel.processLockedClips`` mirrors this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .as_shot import WB_SOURCE_ESTIMATE, WB_SOURCE_GREY

REASON_PICK_LOG_GAMUT = "先选择 Log 与色域"
REASON_PICK_PAIRED_IDT = "先选择成对 IDT"
PROCESS_BUTTON = "处理已锁定片段"
ADVANCED_DISCLOSURE = "高级"
LOCK_STATUS_TEMPLATE = "{locked} 条已锁定 / {pending} 条待选"


@dataclass(frozen=True)
class BatchClip:
    name: str
    idt: str | None = None
    needs_user_picker: bool = False
    is_stub: bool = False
    detected_curve: str | None = None


@dataclass(frozen=True)
class BatchPlan:
    locked: tuple[BatchClip, ...]
    skipped: tuple[tuple[BatchClip, str], ...]

    @property
    def locked_count(self) -> int:
        return len(self.locked)

    @property
    def pending_count(self) -> int:
        return len(self.skipped)

    @property
    def lock_status_text(self) -> str:
        return LOCK_STATUS_TEMPLATE.format(
            locked=self.locked_count, pending=self.pending_count
        )

    @property
    def shows_process_button(self) -> bool:
        return self.locked_count > 0


def has_locked_idt(clip: BatchClip) -> bool:
    """Processable only when a non-stub paired IDT is locked."""
    if not clip.idt or clip.is_stub or clip.needs_user_picker:
        return False
    return True


def skip_reason(clip: BatchClip) -> str | None:
    """Chinese reason for unlocked / pending clips. None when locked."""
    if has_locked_idt(clip):
        return None
    if clip.detected_curve or clip.is_stub:
        return REASON_PICK_PAIRED_IDT
    return REASON_PICK_LOG_GAMUT


def plan_locked_batch(clips: Sequence[BatchClip]) -> BatchPlan:
    """Walk locked clips only. Unlocked stay listed; never guessed."""
    locked: list[BatchClip] = []
    skipped: list[tuple[BatchClip, str]] = []
    for clip in clips:
        if has_locked_idt(clip):
            locked.append(clip)
        else:
            skipped.append((clip, skip_reason(clip) or REASON_PICK_LOG_GAMUT))
    return BatchPlan(locked=tuple(locked), skipped=tuple(skipped))


def process_locked_names(clips: Sequence[BatchClip]) -> list[str]:
    """Names the batch would process. Unlocked are omitted, not invented."""
    return [c.name for c in plan_locked_batch(clips).locked]


def estimate_chip_lit(wb_source: str) -> bool:
    """Estimate chip lights only AFTER confirm (wb_source == estimate)."""
    return wb_source == WB_SOURCE_ESTIMATE


def propose_auto_wb(state: dict, cct: float | None, tint: float = 0.0) -> dict:
    """Propose only. Does not write CAT / wb_source. Empty stays empty."""
    out = dict(state)
    out["auto_wb_cct"] = cct
    out["auto_wb_tint"] = tint
    return out


def confirm_auto_wb(state: dict) -> dict:
    """Write estimate CAT only after confirm. Grey-card wins. No 5600 guess."""
    out = dict(state)
    if out.get("wb_source") == WB_SOURCE_GREY:
        return out
    cct = out.get("auto_wb_cct")
    if cct is None:
        return out
    out["wb_cct"] = cct
    out["wb_tint"] = out.get("auto_wb_tint", 0.0)
    out["wb_source"] = WB_SOURCE_ESTIMATE
    return out


def never_guess_cct(cct: float | None) -> bool:
    """Missing CCT stays empty. Never fill 5600 or 6504."""
    return cct is None
