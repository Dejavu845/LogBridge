"""Locked-IDT batch policy + ACES2065-1 proxy EXR sequence writes. No color-number changes.

A clip is processable only when its paired IDT is chosen / locked.
Batch walks locked clips only. Pending / unlocked stay in the list with a
Chinese reason. Never guess 5600 or 6504. Never invent a second process
button. Auto WB estimate does not write CAT until confirm; grey-card
overrides estimate.

「处理已锁定片段」 writes one ACES2065-1 (AP0 linear) **proxy EXR sequence**
per locked clip (ODT off): ``{stem}_ACES2065-1_proxy/frame_000000.exr``.
The write loop is decode → IDT → exposure → WB → EXR. It uses
``apply_ap0`` (clip-constant CAT via ``ap0_write_setup``), not
``graph.apply``, so a 709 preview ODT is never baked. Preview/scrub
still runs ODT only on the linear cache.
Movie write decode uses source 10-bit / native-depth Y′CbCr → float
(matrix-only; no Rec.709 transfer before IDT). YUV matrix and
full/video range follow the buffer / nclc attachments — not a
hardcoded BT.709 + video-range for every clip. Scale is bit-depth
+ range (video 10-bit is Y 64–940 / C 64–960, not /1023). 8-bit
Y′CbCr is only the fallback when 10-bit is unavailable. Still a
proxy, not camera-original — 整段代理，不是全精度成片. Not ACEScct.
Not a Rec.709 .mov/.mp4. Movie preview first-frame unpack shares the same
nclc/colr/vui matrix+range helper, then quantizes to 8-bit / 1920.
Stills (TIFF / DPX / EXR) stay ImageIO — already RGB, no Y′CbCr unpack.
Write is source pixels 1:1 and source-native bit depth. 16384 is a
refuse ceiling (「片源边长超过 16384，未写出」), not a downsample
target. Do not scale export to 16384 or 1920. Write does not use
the 8-bit preview buffer. Preview/scrub may stay 8-bit-first.
「N 条已处理」 is clips that produced a sequence, or locked clips attempted
with a per-clip error — not a preview refresh. Pending clips in the same
bin do not block.

While writing, progress is 「写出代理 i/N · 第 k 帧」 (「第 k / 共 m 帧」 when total known).
Cancel becomes the same primary button. The in-progress ``_proxy`` folder
is removed so a half sequence is not a finished deliverable; completed
clips stay. Cancelled status says 已取消 and still 整段代理，不是全精度成片.
Partial output is 不是成片. A successful write remembers the dest folder
(UserDefaults) and status offers 「在 Finder 中显示」. Cancel does not
treat a deleted half-folder as success. After a write, locked sidebar
rows show 「已写出代理」 (or a short Chinese error). Clicking that
row or chip reveals that clip's ``{stem}_ACES2065-1_proxy/`` from the
last dest (``deliverable_dir_name``). Pending / failed / cancelled
do not reveal. Pending stay 「先选择 Log 与色域」 / 「先选择成对 IDT」.
A cancelled in-progress clip is not 已写出; completed clips keep
已写出代理. Re-export clears or refreshes the chip. Session-level
「在 Finder 中显示」 stays.

After a locked write, count EXRs in ``{stem}_ACES2065-1_proxy/`` and
compare to source duration × metadata fps only. Off-by-one is accepted
(inclusive last frame). An empty ``_ACES2065-1_proxy`` (no EXRs /
0 frames) is 「帧数对不上」; the folder is removed. Decode that wrote
nothing is 「解码失败」 (no folder). Missing fps is 「读不到帧率，未核对」;
missing duration is 「读不到时长，未核对」 — never default 24 or 30, and do
not reuse the dest-disk 24 fps × 60 s guess. A mismatch is
「帧数对不上」; the folder is removed so it is not 已写出代理.

A successful locked process also writes the session Resolve package
into the same dest (``graph.xml``, DCTL, cube, ``README_RESOLVE.md``)
so the folder is openable. Missing or empty ``graph.xml`` / DCTL / cube
/ ``README_RESOLVE.md`` fail closed with 「达芬奇包不完整，未写出」;
the half package and those ``_proxy`` folders are removed so they are
not 已写出代理. Do not claim ACES OT in that README.
CI 绿不等于达芬奇已验证。不是全精度成片. Not a movie.

When 「处理已锁定片段」 finishes (ok / cancel / disk abort / frame
check), ``lastExportNote`` is one Chinese three-bucket summary:
「N 条已写出代理 / M 条待选跳过 / K 条失败」 plus 失败原因
(existing chips only). Not a second process button. Not a summary page.
Do not reuse the dest-disk 24 fps × 60 s guess in this summary.

Before any EXR is written, estimate dest disk from **locked clips
only**: frame count × pixel count × 12 bytes (uncompressed float32
RGB; EXR header / offset table is covered by a small margin). If
frame count is unknown, use duration×fps, or a conservative 24 fps
× 60 s guess (said in the note). If free space < estimate + margin,
do not start writing. Status: 「磁盘空间不足，未写出」 +
「整段代理，不是全精度成片」.

Swift ``SessionModel.processLockedClips`` mirrors this module. Color is
``SerialGraph.apply`` (existing pipeline). Container is ``exr_write``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path
import shutil
from typing import Callable, Sequence

import numpy as np

from .as_shot import WB_SOURCE_ESTIMATE, WB_SOURCE_GREY
from .exr_write import write_rgb_exr
from .formats import NOTE_ARRI_MXF, NOTE_CAMERA_RAW, NOTE_MXF_NO_TRACK, NOTE_UNKNOWN_CODEC
from .graph import SerialGraph

REASON_PICK_LOG_GAMUT = "先选择 Log 与色域"
REASON_PICK_PAIRED_IDT = "先选择成对 IDT"
# Leftover English failure chips → short Chinese. Copy only.
STUB_CHIP = "未实现"
EMPTY_RGB_CHIP = "RGB 是空的，未写出"
NOTE_DLOG_M = "D-Log M 暂不支持，请用 D-Log + D-Gamut"
NOTE_SLOG3_NO_GAMUT = "S-Log3 没有色域，先选择成对 IDT"
NOTE_SLOG3_NO_GAMUT_VENICE = "S-Log3 没有色域，检测到 Venice，先选择成对 IDT"
NOTE_CLOG2_NO_GAMUT = "C-Log2 没有色域，先选择成对 IDT"
NOTE_CLOG3_NO_GAMUT = "C-Log3 没有色域，先选择成对 IDT"
NOTE_VENICE_PICK = "检测到 Venice，先选择成对 IDT"
# Leftover English success / accept notes → short Chinese. Copy only.
NOTE_FILENAME_SGAMUT3 = "文件名 S-Gamut3"
NOTE_FILENAME_SGAMUT3_CINE = "文件名 S-Gamut3.Cine"
NOTE_FILENAME_LOGC4 = "文件名 LogC4/AWG4"
NOTE_FILENAME_VLOG = "文件名 V-Log"
NOTE_FILENAME_FLOG2 = "文件名 F-Log2"
NOTE_FILENAME_NLOG = "文件名 N-Log"
NOTE_FILENAME_LOG3G10 = "文件名 Log3G10"
NOTE_FILENAME_APPLE_LOG2 = "文件名 Apple Log 2 + Apple Wide Gamut"
NOTE_FILENAME_LOGC3 = "文件名 LogC3 EI800 + AWG3"
NOTE_FILENAME_AWG3 = "文件名 AWG3 (LogC3 EI800 + AWG3)"
NOTE_FILENAME_CLOG2_CGAMUT = "文件名 C-Log2 + Cinema Gamut"
NOTE_FILENAME_CLOG2_BT2020 = "文件名 C-Log2 + BT.2020"
NOTE_FILENAME_CLOG3_CGAMUT = "文件名 C-Log3 + Cinema Gamut"
NOTE_FILENAME_CLOG3_BT2020 = "文件名 C-Log3 + BT.2020"
NOTE_FILENAME_APPLE_LOG = "文件名 Apple Log"
NOTE_FILENAME_DLOG = "文件名 D-Log"
NOTE_MODEL_HINT = "机型提示"
NOTE_META_ARRI_MXF = "元数据 ARRI MXF"
NOTE_META_SONY = "元数据 Sony"
NOTE_META_SONY_VENICE = "元数据 Sony（Venice）"
NOTE_META_CLOG2_CGAMUT = "元数据 C-Log2 + Cinema Gamut"
NOTE_META_CLOG2_BT2020 = "元数据 C-Log2 + BT.2020"
NOTE_META_CLOG3_CGAMUT = "元数据 C-Log3 + Cinema Gamut"
NOTE_META_CLOG3_BT2020 = "元数据 C-Log3 + BT.2020"
NOTE_META_RED_RMD = "元数据 RED RMD"
NOTE_META_FUJI = "元数据 Fujifilm"
NOTE_META_NIKON = "元数据 Nikon"
NOTE_META_PANA = "元数据 Panasonic"
NOTE_META_APPLE_LOG2 = "元数据 Apple Log 2 + Apple Wide Gamut"
NOTE_META_APPLE_LOG = "元数据 Apple Log"
NOTE_META_DLOG = "元数据 D-Log"
NOTE_META_LOGC3 = "元数据 LogC3 EI800 + AWG3"
WROTE_FILES_NOTE = "已写出 {n} 个文件"
# preview.status (Swift PreviewEngine). Existing phrases only. No 精准.
PREVIEW_STATUS_EMPTY = "没有素材"
PREVIEW_STATUS_DECODING = "正在解码预览…"
PREVIEW_STATUS_DECODE_FAIL = "解不出预览帧"
PREVIEW_STATUS_ODT_CACHE_HIT = "只重跑预览输出"
PREVIEW_STATUS_PROXY = "预览代理，不是成片"
PREVIEW_STATUS_NOT_DELIVERABLE = "预览·非成片"
PREVIEW_STATUS_ODT_OFF = "709 预览关"
PREVIEW_STATUS_HDR_BUILD_FAIL = "HDR 预览建不出"
PREVIEW_STATUS_HDR_NO_EDR = "屏幕无 EDR，预览被压到 SDR"
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
    "已锁定片段写出 ACES2065-1 代理 EXR 序列（_ACES2065-1_proxy），不是 mov。"
    "整段代理，不是全精度成片。"
    "未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。"
    "预览·非成片。已实现（未验证）。"
)
PROCESS_DELIVERABLE_NOTE = (
    "写出代理 EXR 序列（_ACES2065-1_proxy），不是 mov。整段代理，不是全精度成片。"
)
PROCESS_BUTTON_HELP = (
    "写出代理 EXR 序列（_ACES2065-1_proxy），不是 mov。"
    "整段代理，不是全精度成片。ACES2065-1 AP0 线性，不是 ACEScct。"
    "待选跳过（先选择 Log 与色域 / 先选择成对 IDT）。"
)
# User-visible Swift copy (trial usability). Python constants above stay
# locked by tests/test_batch_locked.py (owned by PR #63).
PROCESS_BUTTON_HELP_UI = "写出的是图片序列（EXR），不是 mp4/mov"
PROCESS_DELIVERABLE_NOTE_UI = "代理 EXR，不是视频。整段代理，不是全精度成片。"
FOLDER_PICKER_MESSAGE_UI = (
    "每条素材一个 _ACES2065-1_proxy 夹，里面逐帧图片，给达芬奇用。"
    "整段代理，不是全精度成片。"
    "未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。"
    "预览·非成片。已实现（未验证）。"
)
PROGRESS_STATUS_HELP = "按每一帧出一张图，不是一条视频"
EMPTY_STATE_STEP_1 = "把混源文件夹拖进来"
EMPTY_STATE_STEP_2 = "每条选成对 Log 与色域"
EMPTY_STATE_STEP_3 = "点处理已锁定片段。得到的是 EXR 图序列，不是视频。"
EMPTY_STATE_STEPS = (
    "1 把混源文件夹拖进来  2 每条选成对 Log 与色域  "
    "3 点处理已锁定片段。得到的是 EXR 图序列，不是视频。"
)
USER_PICKED_IDT_NOTE = "用户选择成对 IDT"
MISSING_YCBCR_TAGS_CHIP_UI = "读不出片源色彩标签，没法写出"
ADVANCED_EXPORT_HELP = (
    "只处理已锁定片段。待选跳过。709 预览。预览·非成片。不必全部锁定。"
)
ADVANCED_DISCLOSURE_HELP = "节点与导出 ACEScct / EXR。默认收起。预览·非成片。"
CANCEL_BUTTON = "取消"
CANCELLED_NOTE = "已取消"
PROGRESS_PREFIX = "写出代理"
CANCELLED_STATUS_TEMPLATE = (
    "处理已锁定片段 — 已取消。"
    "{processed} 条已处理 / {skipped} 条已跳过"
    "（先选择 Log 与色域 / 先选择成对 IDT）。"
    "整段代理，不是全精度成片。预览·非成片。已实现（未验证）。"
)
# Folder of per-frame EXRs. Names must include _proxy so this is not a 成片 claim.
DELIVERABLE_DIR_SUFFIX = "_ACES2065-1_proxy"
DELIVERABLE_SUFFIX = DELIVERABLE_DIR_SUFFIX
SEQUENCE_FRAME_PREFIX = "frame"
SEQUENCE_FRAME_WIDTH = 6
REVEAL_IN_FINDER = "在 Finder 中显示"
LAST_EXPORT_DIRECTORY_KEY = "logbridge.lastExportDirectory"
WRITTEN_CHIP = "已写出代理"
WRITE_FAILED_CHIP = "写出失败"
DECODE_FAILED_CHIP = "解码失败"
GENERIC_PARSE_FAILED = "解析失败"
FRAME_MISMATCH_CHIP = "帧数对不上"
MISSING_FPS_CHIP = "读不到帧率，未核对"
MISSING_DURATION_CHIP = "读不到时长，未核对"
MISSING_YCBCR_TAGS_CHIP = "无法读取片源 Y′CbCr 矩阵/范围，未写出"
WRITE_LONG_EDGE_CEILING = 16384
WRITE_OVERSIZE_CHIP = "片源边长超过 16384，未写出"
DISK_SHORT_STATUS = "磁盘空间不足，未写出"
RESOLVE_INCOMPLETE_CHIP = "达芬奇包不完整，未写出"
# Openable Resolve set. XML + DCTL + cube + README. Not 01_IDT_*.
RESOLVE_REQUIRED_XML = "graph.xml"
RESOLVE_REQUIRED_README = "README_RESOLVE.md"
RESOLVE_REQUIRED_DCTL = "03_WB.dctl"
RESOLVE_REQUIRED_CUBE = "03_WB.cube"
RESOLVE_REQUIRED_NAMES = (
    RESOLVE_REQUIRED_XML,
    RESOLVE_REQUIRED_README,
    RESOLVE_REQUIRED_DCTL,
    RESOLVE_REQUIRED_CUBE,
)
# Session package files (not ``_ACES2065-1_proxy`` folders).
RESOLVE_BUNDLE_FILENAMES = (
    "README_RESOLVE.md",
    "graph.xml",
    "graph.dot",
    "02_Exposure.cube",
    "02_Exposure.dctl",
    "03_WB.cdl",
    "03_WB.ccc",
    "03_WB.dctl",
    "03_WB.cube",
    "04_ODT_Rec709.cube",
)
# Uncompressed float32 RGB scanline payload (3 × 4). Not ZIP/PIZ.
# Header + offset table are not per-pixel; DISK_MARGIN covers them.
BYTES_PER_EXR_PIXEL = 12
DISK_MARGIN_RATIO = 0.10
DISK_MARGIN_MIN_BYTES = 64 * 1024 * 1024
CONSERVATIVE_FPS = 24.0
CONSERVATIVE_SECONDS = 60.0
CONSERVATIVE_WIDTH = 3840
CONSERVATIVE_HEIGHT = 2160
DISK_ESTIMATE_ASSUMPTION = "未压缩浮点图"
DISK_SHORT_STATUS_TEMPLATE = (
    "磁盘空间不足，未写出。整段代理，不是全精度成片。"
)
SKIPPED_BUCKET = "待选跳过"
FAILED_BUCKET = "失败原因"
BATCH_SUMMARY_TEMPLATE = "{wrote} 条已写出代理 / {skipped} 条待选跳过 / {failed} 条失败"

# Y′CbCr → R′G′B′ matrix-only. Coefficients follow the source matrix
# (BT.601 / BT.709 / BT.2020). Write path does not apply a Rec.709 transfer.
YCBCR_MATRIX_COEFFS = {
    "bt709": (1.5748, 0.1873, 0.4681, 1.8556),
    "bt601": (1.402, 0.344136, 0.714136, 1.772),
    "bt2020": (1.4746, 0.164553, 0.571353, 1.8814),
}
YCBCR_BT709_RV, YCBCR_BT709_GU, YCBCR_BT709_GV, YCBCR_BT709_BU = YCBCR_MATRIX_COEFFS[
    "bt709"
]
# Video-range 8/10-bit legal spans (ITU). Not a literal 1023 for every 10-bit clip.
YCBCR_OFF_8 = (16.0, 219.0, 128.0, 224.0)
YCBCR_OFF_10 = (64.0, 876.0, 512.0, 896.0)


def ycbcr_range_offsets(bit_depth: int, sample_range: str):
    """Y/C offsets from bit-depth AND full/video. Never always /1023.

    Video n-bit: Y 16<<(n-8) … 235<<(n-8), C 16<<(n-8) … 240<<(n-8).
    10-bit video is 64–940 / 64–960, not 0–1023. Full n-bit is 0…2^n-1.
    N-Log 10-bit video-range codes are wrong if blindly divided by 1023.
    """
    if int(bit_depth) < 8:
        raise ValueError(f"bit_depth must be >= 8, got {bit_depth}")
    max_code = float((1 << int(bit_depth)) - 1)
    mid = float(1 << (int(bit_depth) - 1))
    kind = str(sample_range).lower()
    if kind == "full":
        return (0.0, max_code, mid, max_code)
    if kind != "video":
        raise ValueError(f"sample_range must be video or full, got {sample_range}")
    shift = int(bit_depth) - 8
    y_off = float(16 << shift)
    y_span = float((235 << shift) - (16 << shift))
    c_span = float((240 << shift) - (16 << shift))
    return (y_off, y_span, mid, c_span)


def ycbcr_to_rgb_float(
    y,
    cb,
    cr,
    *,
    bit_depth: int,
    sample_range: str,
    matrix: str,
):
    """Source-code Y′CbCr → float R′G′B′. Matrix-only. No 8-bit RGB quantize.

    ``matrix`` / ``sample_range`` follow the source (attachments / nclc).
    No Rec.709 OETF/EOTF. Superwhite / superblack may leave 0-1.
    Still 整段代理，不是全精度成片.
    """
    key = str(matrix).lower().replace(".", "")
    if key not in YCBCR_MATRIX_COEFFS:
        raise ValueError(f"matrix must be bt709 / bt601 / bt2020, got {matrix}")
    rv, g_u, gv, bu = YCBCR_MATRIX_COEFFS[key]
    y_off, y_span, c_off, c_span = ycbcr_range_offsets(bit_depth, sample_range)
    yp = (float(y) - y_off) / y_span
    pbv = (float(cb) - c_off) / c_span
    prv = (float(cr) - c_off) / c_span
    return (yp + rv * prv, yp - g_u * pbv - gv * prv, yp + bu * pbv)


def _normalize_ycbcr_matrix(value) -> str | None:
    """Map nclc/colr/vui matrix to bt709 / bt601 / bt2020. Unspecified → None."""
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip().lower().replace(".", "").replace(" ", "")
        if raw in YCBCR_MATRIX_COEFFS:
            return raw
        if "2020" in raw:
            return "bt2020"
        if "601" in raw or "240m" in raw:
            return "bt601"
        if "709" in raw:
            return "bt709"
        if raw.isdigit():
            return _matrix_from_code(int(raw))
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _matrix_from_code(int(value))
    return None


def _matrix_from_code(code: int) -> str | None:
    """ITU/H.273 matrix_coefficients. 0/2 unspecified → None (no 709 default)."""
    if code == 1:
        return "bt709"
    if code in (4, 5, 6, 7):
        return "bt601"
    if code in (9, 10):
        return "bt2020"
    return None


def _nclc_triplet(value) -> tuple[int, int, int] | None:
    """nclc / nclx / colr as primaries-transfer-matrix. Do not use P/T for IDT."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (int(value[0]), int(value[1]), int(value[2]))
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        parts = value.replace(",", "-").replace(":", "-").split("-")
        if len(parts) >= 3:
            try:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                return None
    return None


def parse_source_ycbcr_matrix(tags) -> str | None:
    """Matrix from nclc / colr / vui only. Missing or unspecified → None."""
    if not isinstance(tags, dict):
        return None
    for key in (
        "ycbcr_matrix",
        "YCbCrMatrix",
        "vui_matrix",
        "matrix_coefficients",
        "nclc_matrix",
    ):
        if key in tags:
            got = _normalize_ycbcr_matrix(tags[key])
            if got:
                return got
            return None
    for key in ("nclc", "nclx", "colr"):
        trip = _nclc_triplet(tags.get(key))
        if trip is not None:
            return _matrix_from_code(trip[2])
    return None


def parse_source_ycbcr_range(tags) -> str | None:
    """Full/video from nclc/nclx/vui. Missing → None (not video by default)."""
    if not isinstance(tags, dict):
        return None
    for key in (
        "full_range",
        "FullRangeVideo",
        "video_full_range_flag",
        "nclx_full_range",
        "sample_range",
    ):
        if key not in tags:
            continue
        value = tags[key]
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("full", "1", "true", "yes"):
                return "full"
            if low in ("video", "limited", "tv", "0", "false", "no"):
                return "video"
            return None
        if value is True or value == 1:
            return "full"
        if value is False or value == 0:
            return "video"
        return None
    return None


def require_source_ycbcr_tags(tags) -> tuple[str, str]:
    """Write unpack: both matrix and range from tags, or Chinese failure.

    No silent BT.709 + video-range default. Does not read primaries/transfer
    to change an IDT or to apply a 709 curve.
    """
    matrix = parse_source_ycbcr_matrix(tags)
    sample_range = parse_source_ycbcr_range(tags)
    if matrix is None or sample_range is None:
        raise ValueError(MISSING_YCBCR_TAGS_CHIP)
    return matrix, sample_range


def ycbcr_to_preview_u8(y, cb, cr, *, bit_depth: int = 10, sample_range: str = "video", matrix: str = "bt709"):
    """Preview 8-bit path: matrix, then clamp and quantize to 0-255.

    Swift preview reads matrix+range from nclc/colr/vui (same helper as
    write). No silent 709-video default. ``extractRGB`` later does
    ``u8 / 255``. Write must not use this.
    """
    r, g, b = ycbcr_to_rgb_float(
        y, cb, cr, bit_depth=bit_depth, sample_range=sample_range, matrix=matrix
    )

    def _u8(x: float) -> int:
        return max(0, min(255, int(round(min(max(x, 0.0), 1.0) * 255.0))))

    return (_u8(r), _u8(g), _u8(b))
