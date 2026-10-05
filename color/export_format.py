"""Locked-batch export format policy.

Default deliverable is **ProRes 422 HQ** (Rec.709 preview baked) so the
file drops into Final Cut / Premiere / Resolve as a normal movie.

Why 422 HQ (not 4444) for the first default:
- Hardware-accelerated and universally accepted on Apple Silicon editors
- No alpha channel (this proxy has none)
- Smaller than 4444 at the same resolution; still 10-bit 4:2:2
- Stable AVAssetWriter / ffmpeg ``prores_ks`` profile path

ACES2065-1 half EXR sequences remain an **advanced** option for VFX /
ACES interchange. Not a finished master either way — 整段代理，代理精度.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class ExportFormat(str, Enum):
    PRORES_422_HQ = "prores_422_hq"
    EXR_ACES2065 = "exr_aces2065"


DEFAULT_EXPORT_FORMAT = ExportFormat.PRORES_422_HQ

# Approximate payload for dest-disk estimates (bytes / pixel / frame).
# ProRes 422 HQ is variable-rate; 1.0 B/px is a conservative upper bound
# vs uncompressed half EXR at 6 B/px.
BYTES_PER_PRORES_HQ_PIXEL = 1
BYTES_PER_EXR_PIXEL = 6

PRORES_DIR_SUFFIX = "_Rec709_proxy"  # stem only; file is .mov
PRORES_FILE_SUFFIX = ".mov"
EXR_DIR_SUFFIX = "_ACES2065-1_proxy"

EXPORT_FORMAT_LABELS = {
    ExportFormat.PRORES_422_HQ: "ProRes 422 HQ（Rec.709 预览）",
    ExportFormat.EXR_ACES2065: "ACES2065-1 EXR 序列（高级）",
}

DEFAULT_FORMAT_HELP = (
    "默认写出 ProRes 422 HQ（Rec.709 预览代理）。"
    "EXR 序列在高级选项。整段代理，代理精度。"
)

FOLDER_PICKER_PRORES = (
    "每条素材一个 Rec.709 预览代理 .mov（ProRes 422 HQ）。"
    "整段代理，代理精度。"
    "未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。"
    "已实现（未验证）。"
)

PROCESS_BUTTON_HELP_PRORES = (
    "写出的是 ProRes 视频（422 HQ），不是 EXR 图序列。"
    "整段代理，代理精度。"
)

PROCESS_DELIVERABLE_NOTE_PRORES = (
    "代理 ProRes，可直接拖进剪辑软件。整段代理，代理精度。"
)

EMPTY_STATE_STEP_3_PRORES = (
    "点处理已锁定片段。得到的是 ProRes 视频，不是 EXR 图序列。"
)

ADVANCED_EXPORT_HELP_PRORES = (
    "只处理已锁定片段。待选跳过。"
    "默认 ProRes 422 HQ；高级可选 ACES2065-1 EXR。"
    "不必全部锁定。"
)

ADVANCED_DISCLOSURE_HELP_PRORES = (
    "节点与导出。默认 ProRes；EXR 为高级选项。展开状态会记住。整段代理，代理精度。"
)


def parse_export_format(value) -> ExportFormat:
    if isinstance(value, ExportFormat):
        return value
    if value is None or value == "":
        return DEFAULT_EXPORT_FORMAT
    text = str(value).strip().lower()
    for item in ExportFormat:
        if text == item.value or text == item.name.lower():
            return item
    if text in {"prores", "prores422", "prores_422", "mov", "422hq", "422_hq"}:
        return ExportFormat.PRORES_422_HQ
    if text in {"exr", "aces", "aces2065", "aces2065-1", "sequence"}:
        return ExportFormat.EXR_ACES2065
    raise ValueError(f"unknown export format: {value!r}")


def is_default_prores(fmt: ExportFormat | None = None) -> bool:
    return parse_export_format(fmt) is ExportFormat.PRORES_422_HQ


def deliverable_stem_suffix(fmt: ExportFormat) -> str:
    fmt = parse_export_format(fmt)
    if fmt is ExportFormat.PRORES_422_HQ:
        return PRORES_DIR_SUFFIX
    return EXR_DIR_SUFFIX


def prores_mov_name(clip_name: str) -> str:
    stem = Path(clip_name).stem
    return f"{stem}{PRORES_DIR_SUFFIX}{PRORES_FILE_SUFFIX}"


def bytes_per_pixel(fmt: ExportFormat) -> int:
    fmt = parse_export_format(fmt)
    if fmt is ExportFormat.PRORES_422_HQ:
        return BYTES_PER_PRORES_HQ_PIXEL
    return BYTES_PER_EXR_PIXEL
