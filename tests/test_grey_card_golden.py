"""灰卡 golden 空槽。

方法（仍未验证）：
- 拍 18% 灰卡
- 曝光对齐各厂家中灰码
- 机内 LUT 关
- 过 IDT 之后，AP0 RGB 应接近 0.18

没有样片就 skip：不失败，也不用假数当过。
不编金数。不把白皮书 18% 码写进 golden 文件。
不把相机样片、白皮书 PDF、官方 LUT 放进仓库。

本模块只挂空槽，不改 IDT 数学、709 预览、HDR ColorSync 预览、写出 1:1。
本刀只有 Sony S-Gamut3 / S-Gamut3.Cine、LogC3 EI800+AWG3、Apple Log 2 AWG。
不加 D-Log M，不加 R3D / BRAW。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from color.exr_write import read_rgb_exr
from color.gamuts import IDT_PAIRS
from color.pipeline import apply_idt

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "grey_card"

# 样片：相机 log RGB。不是白皮书码表，也不是期望 AP0 数字。
SAMPLE_SUFFIXES = (".exr", ".npy")
# 数字 sidecar 不是样片；有它们也不算“文件已在”。
NON_SAMPLE_SUFFIXES = (".json", ".txt", ".csv", ".md", ".pdf", ".cube")

# IDT 之后 AP0 接近 0.18。这是方法，不是仓库里的金数文件。
AP0_NEAR_018 = 0.02

FORBIDDEN_SLOT_IDS = (
    "dji_dlog_m",
    "dji_dlog_dgamut",
    "apple_log_bt2020",
    "apple_log2_bt2020",
    "arri_logc3_ei1600_awg3",
    "arri_logc4_awg4",
    "sony_slog3_sgamut3_venice",
    "sony_slog3_sgamut3cine_venice",
    "r3d",
    "braw",
)


@dataclass(frozen=True)
class GreyCardSlot:
    idt_id: str
    stem: str
    label: str


# 本刀只这四对。Sony 两槽分开，不把 Cine 当默认。
SLOTS: tuple[GreyCardSlot, ...] = (
    GreyCardSlot("sony_slog3_sgamut3", "sony_slog3_sgamut3", "Sony S-Log3 + S-Gamut3"),
    GreyCardSlot(
        "sony_slog3_sgamut3cine",
        "sony_slog3_sgamut3cine",
        "Sony S-Log3 + S-Gamut3.Cine",
    ),
    GreyCardSlot(
        "arri_logc3_ei800_awg3",
        "arri_logc3_ei800_awg3",
        "ARRI LogC3 EI800 + AWG3",
    ),
    GreyCardSlot("apple_log2_awg", "apple_log2_awg", "Apple Log 2 + Apple Wide Gamut"),
)


def find_optional_sample(slot: GreyCardSlot, directory: Path | None = None) -> Path | None:
    """Return the first optional sample file, or None if the slot is empty."""
    root = Path(directory) if directory is not None else FIXTURE_DIR
    for suffix in SAMPLE_SUFFIXES:
        path = root / f"{slot.stem}{suffix}"
        if path.is_file():
            return path
    return None


def load_camera_log_rgb(path: Path) -> np.ndarray:
    """Load camera-log RGB. Missing file is handled by the slot, not here."""
    suffix = path.suffix.lower()
    if suffix == ".npy":
        rgb = np.load(path)
    elif suffix == ".exr":
        rgb = read_rgb_exr(path)
    else:
        raise AssertionError(f"灰卡槽不读这种后缀：{path.name}")
    arr = np.asarray(rgb, dtype=np.float64)
    if arr.ndim == 1 and arr.shape == (3,):
        return arr
    if arr.ndim >= 2 and arr.shape[-1] == 3:
        return arr
    raise AssertionError(f"灰卡样片必须是 RGB，得到 {arr.shape}")


def center_mean_rgb(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image, dtype=np.float64)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        return arr.mean(axis=0)
    height, width = arr.shape[:2]
    y0, y1 = height // 3, height - height // 3
    x0, x1 = width // 3, width - width // 3
    if y1 <= y0 or x1 <= x0:
        return arr.reshape(-1, 3).mean(axis=0)
    return arr[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)


def measure_grey_card_slot(slot: GreyCardSlot, directory: Path | None = None) -> np.ndarray:
    """Skip if the sample is missing. Do not invent a passing AP0 number."""
    path = find_optional_sample(slot, directory)
    if path is None:
        pytest.skip(f"灰卡样片不存在，跳过：{slot.stem}")
    log_rgb = load_camera_log_rgb(path)
    ap0 = apply_idt(log_rgb, slot.idt_id)
    patch = center_mean_rgb(ap0)
    np.testing.assert_allclose(patch, 0.18, atol=AP0_NEAR_018)
    return patch


def test_method_is_documented_in_chinese():
    readme = (FIXTURE_DIR / "README.md").read_text(encoding="utf-8")
    module = Path(__file__).read_text(encoding="utf-8")
    for blob in (readme, module):
        assert "18% 灰卡" in blob
        assert "曝光对齐各厂家中灰码" in blob
        assert "机内 LUT 关" in blob
        assert "AP0 RGB 应接近 0.18" in blob
        assert "未验证" in blob
        assert "完善" not in blob
        assert "精准" not in blob
        assert "成片" not in blob


def test_slot_table_is_only_these_pairs():
    assert [s.idt_id for s in SLOTS] == [
        "sony_slog3_sgamut3",
        "sony_slog3_sgamut3cine",
        "arri_logc3_ei800_awg3",
        "apple_log2_awg",
    ]
    for slot in SLOTS:
        assert slot.idt_id in IDT_PAIRS
        assert slot.idt_id not in FORBIDDEN_SLOT_IDS
    assert IDT_PAIRS["sony_slog3_sgamut3"] == ("slog3", "SGamut3")
    assert IDT_PAIRS["sony_slog3_sgamut3cine"] == ("slog3", "SGamut3Cine")
    assert IDT_PAIRS["arri_logc3_ei800_awg3"] == ("logc3_ei800", "AWG3")
    assert IDT_PAIRS["apple_log2_awg"] == ("apple_log", "AppleWideGamut")
    assert IDT_PAIRS["apple_log2_awg"][1] != "BT2020"
    assert "dji_dlog_m" not in {s.idt_id for s in SLOTS}
    assert not any("r3d" in s.idt_id or "braw" in s.idt_id for s in SLOTS)
    assert not any("ei" in s.idt_id and "ei800" not in s.idt_id for s in SLOTS)


def test_repo_slot_dir_has_no_samples_or_numeric_goldens():
    """干净树只留 README / gitignore。本机已放文件时让给真实槽，不在这里失败。"""
    allowed = {"README.md", ".gitignore"}
    extras = sorted(p.name for p in FIXTURE_DIR.iterdir() if p.name not in allowed)
    if extras:
        pytest.skip("本机 fixtures/grey_card 有本地文件，空槽检查让给真实槽")
    for slot in SLOTS:
        assert find_optional_sample(slot) is None
        for suffix in NON_SAMPLE_SUFFIXES:
            assert not (FIXTURE_DIR / f"{slot.stem}{suffix}").is_file()


def test_harness_skips_when_sample_missing(tmp_path: Path):
    with pytest.raises(pytest.skip.Exception, match="灰卡样片不存在"):
        measure_grey_card_slot(SLOTS[0], directory=tmp_path)


def test_numeric_sidecar_is_not_a_sample(tmp_path: Path):
    """白皮书 18% 码写进 json/txt 也不算样片，槽仍 skip。"""
    slot = SLOTS[0]
    (tmp_path / f"{slot.stem}.json").write_text('{"ap0": [0.18, 0.18, 0.18]}\n')
    (tmp_path / f"{slot.stem}.txt").write_text("0.18\n")
    assert find_optional_sample(slot, tmp_path) is None
    with pytest.raises(pytest.skip.Exception, match="灰卡样片不存在"):
        measure_grey_card_slot(slot, directory=tmp_path)


def test_harness_does_not_skip_or_fake_pass_when_sample_exists(tmp_path: Path):
    """有文件就必须跑 IDT，不能 skip，也不能拿假 0.18 当过。"""
    slot = SLOTS[0]
    np.save(tmp_path / f"{slot.stem}.npy", np.zeros((2, 2, 3), dtype=np.float64))
    with pytest.raises(AssertionError):
        measure_grey_card_slot(slot, directory=tmp_path)


@pytest.mark.parametrize("slot", SLOTS, ids=lambda s: s.idt_id)
def test_grey_card_golden_slot(slot: GreyCardSlot):
    measure_grey_card_slot(slot)
