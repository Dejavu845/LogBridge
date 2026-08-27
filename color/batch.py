"""Locked-IDT batch policy + ACES2065-1 proxy EXR sequence writes. No color-number changes.

A clip is processable only when its paired IDT is chosen / locked.
Batch walks locked clips only. Pending / unlocked stay in the list with a
Chinese reason. Never guess 5600 or 6504. Never invent a second process
button. Auto WB estimate does not write CAT until confirm; grey-card
overrides estimate.

「处理已锁定片段」 writes one ACES2065-1 (AP0 linear) **proxy EXR sequence**
per locked clip (ODT off): ``{stem}_ACES2065-1_proxy/frame_000000.exr``.
Decode is still the preview path (8-bit Y′CbCr upconverted to float) —
整段代理，不是全精度成片. Not ACEScct. Not a Rec.709 .mov/.mp4.
「N 条已处理」 is clips that produced a sequence, or locked clips attempted
with a per-clip error — not a preview refresh. Pending clips in the same
bin do not block.

Swift ``SessionModel.processLockedClips`` mirrors this module. Color is
``SerialGraph.apply`` (existing pipeline). Container is ``exr_write``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Callable, Sequence

import numpy as np

from .as_shot import WB_SOURCE_ESTIMATE, WB_SOURCE_GREY
from .exr_write import write_rgb_exr
from .graph import SerialGraph

REASON_PICK_LOG_GAMUT = "先选择 Log 与色域"
REASON_PICK_PAIRED_IDT = "先选择成对 IDT"
PROCESS_BUTTON = "处理已锁定片段"
ADVANCED_DISCLOSURE = "高级"
LOCK_STATUS_TEMPLATE = "{locked} 条已锁定 / {pending} 条待选"
HONEST_PROXY_NOTE = "整段代理，不是全精度成片"
PROCESSED_STATUS_TEMPLATE = (
    "处理已锁定片段 — {processed} 条已处理 / {skipped} 条已跳过"
    "（先选择 Log 与色域 / 先选择成对 IDT）。"
    "整段代理，不是全精度成片。预览·非成片。已实现（未验证）。"
)
FOLDER_PICKER_MESSAGE = (
    "已锁定片段写出 ACES2065-1 代理 EXR 序列（AP0 线性）。"
    "整段代理，不是全精度成片。"
    "未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。"
    "预览·非成片。已实现（未验证）。"
)
PROCESS_BUTTON_HELP = (
    "整段代理，不是全精度成片。ACES2065-1 AP0 线性，不是 ACEScct。"
    " Unlocked stay listed (先选择 Log 与色域 / 先选择成对 IDT). Never 一键还原."
)
# Folder of per-frame EXRs. Names must include _proxy so this is not a 成片 claim.
DELIVERABLE_DIR_SUFFIX = "_ACES2065-1_proxy"
DELIVERABLE_SUFFIX = DELIVERABLE_DIR_SUFFIX
SEQUENCE_FRAME_PREFIX = "frame"
SEQUENCE_FRAME_WIDTH = 6


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
    if clip.detected_curve or clip.is_stub or clip.needs_user_picker or clip.idt:
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


def deliverable_dir_name(clip_name: str) -> str:
    """Sequence folder. ``{stem}_ACES2065-1_proxy`` — proxy, not 成片."""
    return f"{Path(clip_name).stem}{DELIVERABLE_DIR_SUFFIX}"


def sequence_frame_name(index: int) -> str:
    """One sequence frame: ``frame_000000.exr``. Zero-based."""
    return f"{SEQUENCE_FRAME_PREFIX}_{index:0{SEQUENCE_FRAME_WIDTH}d}.exr"


def deliverable_name(clip_name: str, index: int = 0) -> str:
    """Relative path of one proxy sequence frame. Not a lone ``_frame0`` file."""
    return f"{deliverable_dir_name(clip_name)}/{sequence_frame_name(index)}"


def as_frame_sequence(value) -> list[np.ndarray]:
    """Normalize a clip's pixels to a list of RGB frames.

    Accepts one RGB array (still / 1-frame), a sequence of RGB arrays, or
    an ``(N, H, W, 3)`` stack. Empty / missing → no frames.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [np.asarray(frame) for frame in value]
    arr = np.asarray(value)
    if arr.ndim == 4 and arr.shape[-1] == 3:
        return [arr[i] for i in range(arr.shape[0])]
    if arr.size == 0:
        return []
    return [arr]


def processed_status_text(processed: int, skipped: int) -> str:
    """「N 条已处理」 is sequence writes / attempts, not preview refresh."""
    return PROCESSED_STATUS_TEMPLATE.format(processed=processed, skipped=skipped)


@dataclass(frozen=True)
class ClipWrite:
    name: str
    path: str | None = None
    error: str | None = None
    frame_count: int = 0


@dataclass(frozen=True)
class BatchWriteReport:
    written: tuple[ClipWrite, ...]
    skipped: tuple[tuple[BatchClip, str], ...]
    errors: tuple[ClipWrite, ...]

    @property
    def processed_count(self) -> int:
        """N in 「N 条已处理」: sequences written + per-clip write errors."""
        return len(self.written) + len(self.errors)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def processed_status_text(self) -> str:
        return processed_status_text(self.processed_count, self.skipped_count)

    @property
    def written_paths(self) -> tuple[str, ...]:
        return tuple(w.path for w in self.written if w.path)


def process_locked_writes(
    clips: Sequence[BatchClip],
    dest,
    frames: dict[str, np.ndarray | Sequence[np.ndarray]] | None = None,
    graph: SerialGraph | None = None,
    write_fn: Callable[[Path, np.ndarray], None] | None = None,
) -> BatchWriteReport:
    """Write an ACES2065-1 proxy EXR sequence for locked clips only.

    Unlocked / pending stay listed and never produce a folder. A mixed bin
    (some locked, some pending) still writes the locked ones. ``graph`` is
    the existing serial graph (ODT off = ACES2065-1). ``frames`` maps clip
    name → one RGB array or a sequence of arrays. Missing pixels or a write
    failure count as processed (per-clip error), not as a skip reason.

    Output layout (DaVinci image sequence)::

        {stem}_ACES2065-1_proxy/frame_000000.exr
        {stem}_ACES2065-1_proxy/frame_000001.exr
        ...

    This is still a **proxy** sequence (preview decode). Not a Rec.709 movie.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    plan = plan_locked_batch(clips)
    frames = frames or {}
    graph = graph if graph is not None else SerialGraph()
    writer = write_fn or (lambda path, rgb: write_rgb_exr(path, rgb))

    written: list[ClipWrite] = []
    errors: list[ClipWrite] = []
    for clip in plan.locked:
        seq_dir = dest / deliverable_dir_name(clip.name)
        rgb_frames = as_frame_sequence(frames.get(clip.name))
        if not rgb_frames:
            errors.append(ClipWrite(name=clip.name, error="no pixels"))
            continue
        if not clip.idt:
            errors.append(ClipWrite(name=clip.name, error="no IDT"))
            continue
        try:
            if seq_dir.exists():
                shutil.rmtree(seq_dir)
            seq_dir.mkdir(parents=True, exist_ok=True)
            for index, rgb in enumerate(rgb_frames):
                out = seq_dir / sequence_frame_name(index)
                linear = graph.apply(rgb, clip.idt)
                writer(out, np.asarray(linear, dtype=np.float32))
                if write_fn is None and not out.is_file():
                    raise OSError("write produced no file")
            written.append(
                ClipWrite(name=clip.name, path=str(seq_dir), frame_count=len(rgb_frames))
            )
        except Exception as exc:  # noqa: BLE001 — per-clip error, keep going
            if seq_dir.exists():
                shutil.rmtree(seq_dir)
            errors.append(ClipWrite(name=clip.name, error=str(exc)))
    return BatchWriteReport(
        written=tuple(written),
        skipped=plan.skipped,
        errors=tuple(errors),
    )
