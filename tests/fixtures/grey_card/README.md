# 灰卡 golden 空槽

方法（仍未验证）：

- 拍 18% 灰卡
- 曝光对齐各厂家中灰码
- 机内 LUT 关
- 过 IDT 之后，AP0 RGB 应接近 0.18

没有样片，对应 pytest 槽就 skip：不失败，也不用假数当过。
不编金数。不把白皮书 18% 码写进 golden 文件。
不把相机样片、白皮书 PDF、官方 LUT 放进仓库。

本目录只挂空槽。本机若要量，把相机 log RGB 放到下面的文件名（二选一）：

| 槽 | 文件名 | IDT |
| --- | --- | --- |
| Sony S-Log3 + S-Gamut3 | `sony_slog3_sgamut3.exr` 或 `.npy` | `sony_slog3_sgamut3` |
| Sony S-Log3 + S-Gamut3.Cine | `sony_slog3_sgamut3cine.exr` 或 `.npy` | `sony_slog3_sgamut3cine` |
| ARRI LogC3 EI800 + AWG3 | `arri_logc3_ei800_awg3.exr` 或 `.npy` | `arri_logc3_ei800_awg3` |
| Apple Log 2 + Apple Wide Gamut | `apple_log2_awg.exr` 或 `.npy` | `apple_log2_awg` |

`.npy` / `.exr` 是相机 log RGB（H×W×3 或 1×1）。不是 AP0 期望值表。
`.json` / `.txt` / `.csv` 里的 0.18 或厂家中灰码不算样片。

本刀不加 D-Log M，不加 R3D / BRAW，不加其他 EI 的 LogC3，不加 Apple Log 2 + BT.2020。
Sony 的 S-Gamut3 与 S-Gamut3.Cine 各一槽，不把 Cine 当默认。
