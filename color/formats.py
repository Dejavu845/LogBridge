"""Container / codec policy. Decode only — no color numbers.

Tried: MOV/MP4 ProRes / H.264 / HEVC; stills TIFF/DPX/EXR via ImageIO.
MXF: try if the system recognizes ProRes/AVC/HEVC. ARRI MXF (ARRIRAW) is refused.
Never claim 全格式已支持.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ACCEPT = "accept"
TRY = "try"
REFUSE = "refuse"

MOVIE_CONTAINERS = frozenset({"mov", "mp4", "m4v"})
STILL_CONTAINERS = frozenset({"tif", "tiff", "dpx", "exr"})
MXF_CONTAINER = "mxf"

# Seen in a drop, then refused with a note. Not "全格式已支持".
REFUSED_CONTAINERS = frozenset(
    {"r3d", "braw", "ari", "arx", "avi", "mkv", "dng", "bmd", "crm"}
)

# ProRes 422 family + 4444 / XQ. Not ProRes RAW.
PRORES_FOURCC = frozenset({"apcn", "apch", "apcs", "apco", "ap4h", "ap4x"})
H264_FOURCC = frozenset({"avc1", "avc3", "ai5p", "ai5q"})
HEVC_FOURCC = frozenset({"hvc1", "hev1", "dvhe", "dvh1"})

PRORES_NAMES = frozenset(
    {
        "prores",
        "apple prores",
        "prores 422",
        "prores 422 hq",
        "prores 422 lt",
        "prores 422 proxy",
        "prores 4444",
        "prores 4444 xq",
    }
)
H264_NAMES = frozenset({"h264", "h.264", "avc", "x264"})
HEVC_NAMES = frozenset({"hevc", "h.265", "h265", "x265"})

ACCEPTED_CODECS = PRORES_FOURCC | H264_FOURCC | HEVC_FOURCC | PRORES_NAMES | H264_NAMES | HEVC_NAMES

ARRI_MXF_MARKERS = frozenset({"arri", "arriraw", "arri raw", "ari", "arx"})

# Folder expand lists these so a refuse note can fire. Not a support claim.
EXPAND_EXTENSIONS = (
    MOVIE_CONTAINERS | STILL_CONTAINERS | {MXF_CONTAINER} | REFUSED_CONTAINERS
)


@dataclass(frozen=True)
class FormatDecision:
    action: str
    container: str
    codec: str | None
    note: str
    kind: str  # movie | still | mxf | refuse


def _norm_codec(codec: str | None) -> str | None:
    if codec is None:
        return None
    return codec.strip().lower().replace("_", " ")


def classify(path: str | Path, codec: str | None = None) -> FormatDecision:
    """Classify a dropped file. Does not decode. Does not guess an IDT."""
    ext = Path(path).suffix.lower().lstrip(".")
    codec_n = _norm_codec(codec)

    if ext in REFUSED_CONTAINERS:
        return FormatDecision(
            action=REFUSE,
            container=ext,
            codec=codec_n,
            note=_refuse_note(ext),
            kind="refuse",
        )

    if ext in STILL_CONTAINERS:
        return FormatDecision(
            action=ACCEPT,
            container=ext,
            codec=codec_n,
            note=f"静帧 {ext.upper()} 走 ImageIO。不是成片。",
            kind="still",
        )

    if ext in MOVIE_CONTAINERS:
        if codec_n and not _codec_ok(codec_n):
            return FormatDecision(
                action=REFUSE,
                container=ext,
                codec=codec_n,
                note=f"{ext.upper()} 里的 {codec_n} 不接。能试的是 ProRes / H.264 / HEVC。",
                kind="movie",
            )
        return FormatDecision(
            action=ACCEPT if (codec_n is None or _codec_ok(codec_n)) else REFUSE,
            container=ext,
            codec=codec_n,
            note="MOV/MP4：ProRes / H.264 / HEVC 走 AVAssetReader Y′CbCr。不走 copyCGImage。",
            kind="movie",
        )

    if ext == MXF_CONTAINER:
        if codec_n and _is_arri_mxf(codec_n):
            return FormatDecision(
                action=REFUSE,
                container=ext,
                codec=codec_n,
                note="ARRI MXF（ARRIRAW）不接。",
                kind="mxf",
            )
        if codec_n and not _codec_ok(codec_n):
            return FormatDecision(
                action=REFUSE,
                container=ext,
                codec=codec_n,
                note=f"MXF 里的 {codec_n} 不接。只试系统认得出的 ProRes / AVC / HEVC。",
                kind="mxf",
            )
        return FormatDecision(
            action=TRY,
            container=ext,
            codec=codec_n,
            note="MXF 只试系统认得出的 ProRes / AVC / HEVC。ARRI MXF 不接。认不出就跳过。",
            kind="mxf",
        )

    return FormatDecision(
        action=REFUSE,
        container=ext or "unknown",
        codec=codec_n,
        note="这个容器不接。不写「全格式已支持」。",
        kind="refuse",
    )


def _codec_ok(codec: str) -> bool:
    if codec in ACCEPTED_CODECS:
        return True
    return any(token in codec for token in ("prores", "h.264", "h264", "avc", "hevc", "h.265", "h265"))


def _is_arri_mxf(codec: str) -> bool:
    return any(m in codec for m in ARRI_MXF_MARKERS)


def _refuse_note(ext: str) -> str:
    if ext in {"r3d"}:
        return "R3D 不接。"
    if ext in {"braw", "bmd"}:
        return "BRAW 不接。"
    if ext in {"ari", "arx"}:
        return "ARRIRAW（.ari/.arx）不接。"
    if ext == "dng":
        return "CinemaDNG 不接。"
    if ext in {"avi", "mkv"}:
        return f"{ext.upper()} 不接。请用 MOV/MP4。"
    return f".{ext} 不接。不写「全格式已支持」。"


def empty_metadata_note() -> str:
    """No camera-private metadata → paired IDT picker. Do not guess."""
    return "读不到元数据，先选择 Log 与色域"
