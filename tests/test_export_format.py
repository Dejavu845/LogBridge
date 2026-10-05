"""Default export is ProRes 422 HQ; EXR stays an advanced option."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from color.batch import (
    BatchClip,
    PROCESS_BUTTON_HELP_UI,
    PROCESS_DELIVERABLE_NOTE_UI,
    deliverable_path_name,
    estimate_locked_proxy_bytes,
    process_locked_writes,
)
from color.export_format import (
    DEFAULT_EXPORT_FORMAT,
    ExportFormat,
    parse_export_format,
    prores_mov_name,
)
from color.prores_write import ffmpeg_bin, write_rgb_prores_422_hq


ROOT = Path(__file__).resolve().parents[1]
SWIFT = ROOT / "macos" / "LogBridge" / "LogBridge"


def test_default_export_format_is_prores_422_hq():
    assert DEFAULT_EXPORT_FORMAT is ExportFormat.PRORES_422_HQ
    assert parse_export_format(None) is ExportFormat.PRORES_422_HQ
    assert parse_export_format("exr") is ExportFormat.EXR_ACES2065


def test_deliverable_names_differ_by_format():
    assert prores_mov_name("clip.mov") == "clip_Rec709_proxy.mov"
    assert deliverable_path_name("clip.mov") == "clip_Rec709_proxy.mov"
    assert deliverable_path_name("clip.mov", ExportFormat.EXR_ACES2065).endswith(
        "_ACES2065-1_proxy"
    )


def test_ui_copy_names_prores_default():
    assert "ProRes" in PROCESS_BUTTON_HELP_UI
    assert "ProRes" in PROCESS_DELIVERABLE_NOTE_UI
    assert "EXR" in PROCESS_BUTTON_HELP_UI  # still mentions EXR as contrast


def test_swift_default_is_prores_and_writer_exists():
    settings = (SWIFT / "Models" / "AppSettings.swift").read_text(encoding="utf-8")
    writer = (SWIFT / "Export" / "ProResWriter.swift").read_text(encoding="utf-8")
    clip = (SWIFT / "Models" / "Clip.swift").read_text(encoding="utf-8")
    fmt = (SWIFT / "Models" / "ExportFormat.swift").read_text(encoding="utf-8")
    assert "prores422HQ" in fmt or "prores_422_hq" in fmt
    assert "exportFormat" in settings
    assert "AVVideoCodecType.proRes422HQ" in writer
    assert "exportLockedProRes" in clip
    assert "exportLockedEXR" in clip  # advanced path kept


def test_disk_estimate_prores_smaller_than_exr():
    clips = [
        BatchClip(
            name="a.mov",
            idt="sony_slog3_sgamut3",
            width=1920,
            height=1080,
            fps=24.0,
            duration_seconds=1.0,
        )
    ]
    # Synthetic one frame
    frames = {"a.mov": np.zeros((1080, 1920, 3), dtype=np.float32)}
    prores = estimate_locked_proxy_bytes(
        clips, frames=frames, export_format=ExportFormat.PRORES_422_HQ
    )
    exr = estimate_locked_proxy_bytes(
        clips, frames=frames, export_format=ExportFormat.EXR_ACES2065
    )
    assert prores.bytes < exr.bytes



def _stub_resolve(dest, clips, graph, lut_size):
    dest = Path(dest)
    (dest / "graph.xml").write_text("<g/>")
    (dest / "README_RESOLVE.md").write_text("x")
    (dest / "03_WB.dctl").write_text("//")
    (dest / "03_WB.cube").write_text("0")


@pytest.mark.skipif(ffmpeg_bin() is None, reason="ffmpeg required for ProRes encode")
def test_default_write_makes_prores_mov(tmp_path: Path):
    clips = [
        BatchClip(name="locked.mov", idt="sony_slog3_sgamut3", width=16, height=8, fps=24.0, duration_seconds=2/24, frame_count=2),
    ]
    rgb = np.full((8, 16, 3), 0.18, dtype=np.float32)
    report = process_locked_writes(
        clips,
        tmp_path,
        frames={"locked.mov": [rgb, rgb]},
        resolve_write_fn=_stub_resolve,
    )
    mov = tmp_path / "locked_Rec709_proxy.mov"
    assert mov.is_file(), (report.errors, list(tmp_path.iterdir()))
    assert not (tmp_path / "locked_ACES2065-1_proxy").exists()
    assert report.wrote_count == 1


@pytest.mark.skipif(ffmpeg_bin() is None, reason="ffmpeg required for ProRes encode")
def test_explicit_exr_still_writes_sequence(tmp_path: Path):
    clips = [
        BatchClip(name="locked.mov", idt="sony_slog3_sgamut3", width=8, height=4, fps=24.0, duration_seconds=1/24, frame_count=1),
    ]
    rgb = np.full((4, 8, 3), 0.1, dtype=np.float32)
    report = process_locked_writes(
        clips,
        tmp_path,
        frames={"locked.mov": [rgb]},
        resolve_write_fn=_stub_resolve,
        export_format=ExportFormat.EXR_ACES2065,
    )
    seq = tmp_path / "locked_ACES2065-1_proxy"
    assert seq.is_dir(), report.errors
    assert list(seq.glob("*.exr"))
    assert not (tmp_path / "locked_Rec709_proxy.mov").exists()


@pytest.mark.skipif(ffmpeg_bin() is None, reason="ffmpeg required")
def test_prores_writer_roundtrip(tmp_path: Path):
    frames = [np.full((4, 6, 3), 0.5, dtype=np.float32) for _ in range(2)]
    out = write_rgb_prores_422_hq(tmp_path / "t.mov", frames, fps=24.0)
    assert out.is_file() and out.stat().st_size > 32
