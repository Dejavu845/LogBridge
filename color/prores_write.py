"""ProRes 422 HQ writer via ffmpeg (Linux CI / Python batch path).

Swift on macOS uses AVAssetWriter; this module keeps policy + tests green
without OpenEXR-style hand-rolled containers. Requires ``ffmpeg`` with
``prores_ks`` (profile 3 = 422 HQ).

Input frames are display-referred Rec.709 (0..1 float RGB) after the
preview ODT — not ACES2065-1 linear. Container only aside from the
encode; no IDT/WB math here.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

# ffmpeg prores_ks profiles: 0=Proxy 1=LT 2=422 3=HQ 4=4444 5=4444XQ
PRORES_KS_PROFILE_422_HQ = "3"


def ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def as_rgb_u16(rgb) -> np.ndarray:
    """Clamp 0..1 float RGB → uint16 RGB planar-ready (H, W, 3)."""
    arr = np.asarray(rgb, dtype=np.float32)
    if arr.ndim == 1 and arr.shape[0] == 3:
        arr = arr.reshape(1, 1, 3)
    if arr.ndim == 2 and arr.shape[-1] == 3:
        arr = arr.reshape(1, arr.shape[0], 3)
    if arr.ndim != 3 or arr.shape[-1] != 3:
        raise ValueError(f"RGB must be (H,W,3), got {arr.shape}")
    clipped = np.clip(arr, 0.0, 1.0)
    return (clipped * 65535.0 + 0.5).astype(np.uint16)


def write_rgb_prores_422_hq(
    path,
    frames,
    *,
    fps: float = 24.0,
    ffmpeg: str | None = None,
) -> Path:
    """Write a ProRes 422 HQ .mov from Rec.709 float frames.

    ``frames``: sequence of (H,W,3) float32 arrays in 0..1.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    seq = [as_rgb_u16(f) for f in frames]
    if not seq:
        raise ValueError("no frames to encode")
    h, w, _ = seq[0].shape
    for i, frame in enumerate(seq):
        if frame.shape != (h, w, 3):
            raise ValueError(f"frame {i} shape {frame.shape} != {(h, w, 3)}")
    rate = float(fps) if fps and fps > 0 else 24.0
    bin_path = ffmpeg or ffmpeg_bin()
    if not bin_path:
        raise RuntimeError("ffmpeg not found (needed for ProRes encode on this host)")
    # rgb48le = little-endian 16-bit planar? Actually packed RGB48LE.
    cmd = [
        bin_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb48le",
        "-s",
        f"{w}x{h}",
        "-r",
        f"{rate:.6f}".rstrip("0").rstrip("."),
        "-i",
        "pipe:0",
        "-c:v",
        "prores_ks",
        "-profile:v",
        PRORES_KS_PROFILE_422_HQ,
        "-pix_fmt",
        "yuv422p10le",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    raw = b"".join(f.tobytes(order="C") for f in seq)
    proc = subprocess.run(cmd, input=raw, capture_output=True)
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 32:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"ffmpeg ProRes encode failed: {err or proc.returncode}")
    return dest


def verify_prores_mov(path) -> tuple[bool, str | None]:
    """Cheap existence + non-empty check. Not a decode proof."""
    p = Path(path)
    if not p.is_file():
        return False, "解码失败"
    if p.stat().st_size < 32:
        return False, "帧数对不上"
    if p.suffix.lower() != ".mov":
        return False, "解码失败"
    return True, None
