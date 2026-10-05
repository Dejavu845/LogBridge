# LogBridge

macOS tool for mixed-camera Log footage: pick a paired IDT per clip, then write an editor-ready proxy.

## What you get (default)

**ProRes 422 HQ** (Rec.709 preview baked), one `.mov` per locked clip:

```text
{stem}_Rec709_proxy.mov
```

Why **422 HQ** (not 4444) as the first default:

- Hardware path on Apple Silicon; opens everywhere in Final Cut / Premiere / Resolve
- No alpha needed for this proxy
- Smaller than 4444 at the same size; still 10-bit 4:2:2

ACES2065-1 half **EXR** sequences remain an **advanced** option (VFX / ACES interchange).

Either way this is a **proxy** (整段代理，代理精度) — implemented, **unverified** against grey-card goldens. Not a one-click “finished grade”.

## Import into an editor

1. Run **处理已锁定片段** and pick an output folder.
2. Drag the `*_Rec709_proxy.mov` files onto a Rec.709 timeline:
   - **Final Cut Pro** — import media, edit
   - **Premiere Pro** — import, edit (Rec.709 sequence)
   - **DaVinci Resolve** — Media Pool → timeline (Rec.709)
3. Optional: open the Resolve package in the same folder (`graph.xml` / cube / DCTL / README) if you want node-side ACEScct work. Studio is required for third-party DCTL.

## Advanced: EXR sequence

In **高级**, switch 写出格式 to **ACES2065-1 EXR 序列（高级）**. Output layout:

```text
{stem}_ACES2065-1_proxy/frame_000000.exr
```

Uncompressed half RGB. Large on disk (~6 bytes/pixel). Prefer ProRes unless you need linear EXR.

## Quick start (Mac)

1. Install **Xcode 15+** (App Store).
2. Open `macos/LogBridge/LogBridge.xcodeproj`.
3. Select the **LogBridge** scheme → Run (▶), or Product → Archive → Distribute App → **Copy App** for a local `.app`.
4. Drop a folder of mixed Log clips (MOV/MP4 ProRes / H.264 / HEVC; TIFF/DPX/EXR stills).
5. For each **待选** clip, pick a paired Log + gamut IDT.
6. Click **处理已锁定片段**.

Trial copy is not notarized. Gatekeeper may require right-click → Open.

## What it does / does not

| Does | Does not |
|------|----------|
| Paired IDT → exposure (stops) → AP0 WB → proxy | Guess an IDT when metadata is missing |
| Default ProRes 422 HQ for editors | Claim “supported / one-click / precise / finished picture” |
| Optional EXR + Resolve graph package | Ingest R3D / BRAW / ARRIRAW / D-Log M yet |
| Preview Rec.709 / optional HLG·PQ | Replace a full grade in Resolve |

Color math lives in `color/` (Python source of truth) with a Swift parity path for the app.

## Develop / test

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

CI (`.github/workflows/test.yml`): Ubuntu pytest + macOS compile of the LogBridge scheme + the same pytest. Metal / Finder / real encode feel still need a Mac.

UI copy: `locale/ui_zh.json` (+ Swift `UICopy.swift`). Do not add per-phrase “Chinese must appear in Swift source” locks — see `tests/test_ui_copy.py`.

## License

MIT — Copyright (c) 2026 LogBridge contributors.


## Honesty glossary (do not weaken)

Status chips and failure notes stay Chinese and specific:

- **已写出代理** / **在 Finder 中显示** / **待选跳过** / **失败原因** / **写出代理** / **已取消**
- **帧数对不上** / **解码失败** / **读不到帧率，未核对** / **读不到时长，未核对**
- **磁盘空间不足，未写出** / **达芬奇包不完整，未写出** / **片源边长超过 16384，未写出**
- empty `_ACES2065-1_proxy` (no EXRs / 0 frames) fails closed — not 已写出代理
- Frame check **never guesses 24 or 30** fps (dest-disk estimate may still use a conservative guess, and says so)
- After a batch: **N 条已写出代理 / M 条待选跳过 / K 条失败** plus 失败原因
- Write uses **source pixels 1:1** (16384 refuse ceiling, not a downsample). Not the **preview 8-bit path promoted** to float.
- Preview stays 8-bit / long-edge 1920.
- **整段代理，代理精度.** Implemented (**未验证**). **CI 绿不等于达芬奇已验证.**


Disk estimate (EXR advanced): **未压缩浮点图**, **6 bytes** / pixel, **24 fps × 60 s** guess when needed. **磁盘空间不足，未写出**.
