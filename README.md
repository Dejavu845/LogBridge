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

## 本机打开试用

Linux 上不能编出 `.app`。在 Mac 上：

1. 安装 Xcode 15 或更新。
2. 打开 `macos/LogBridge/LogBridge.xcodeproj`。
3. Scheme 选 **LogBridge**，按 ▶ 运行。或 Product → Archive → Distribute App → Copy App，得到本地 `.app`。
4. 试用包未公证。若被拦住，右键打开。可看 `scripts/clear-app-quarantine.sh`。
5. 窗口是素材列表、大预览、右侧检查器。没有素材时按回车，或点「添加…」，或把自备的混源 Log 文件夹拖进来。待选时按回车滚到成对 IDT，点一行锁定，不替你选。这一窗没有别的待选时，锁上后检查器滚到曝光，不改数字；还有待选时不滚。已锁定时按回车滚到曝光，拖滑条看预览，数字不会被回车改掉。分屏时监视器旁写「V 切换」，按 V 在分屏和预览之间换；正在看源或对照时，V 不改画面。监视器下滑条下面写出将得到的文件名，和写出说明同一个；待选不写这一行。能点时句尾写「点这一行打开写出说明，再选文件夹。」，点这一行也打开写出说明，不开始写文件。设置或选文件夹开着时，这一行只留名字。点「写出」或按 ⌘E 仍是同一套。写出说明里，当前这一条标「当前这条」，确认和关闭留在下面，说明长了中间自己滚。会跳过的一条可以点「去选成对 IDT」，说明关掉并滚到成对 IDT，不替你选，也不开始写文件。检查器标题随后有「回到写出说明」，点一下重新打开说明，不选文件夹，也不开始写文件。锁上最后一条并滚到曝光时，这一下留在标题，不跟着滚走。菜单「文件」是同一句，不是从说明过来时是灰的。不是从说明过来时，标题里没有这一下。当前这条已锁定、后面连续几条的列表里已有这一对时，「这一对给后面连续的待选」或 ⌃⌘] 写上这些条，碰到没有这一对的就停，不往回写，不改曝光和白平衡。当前这条被筛选或查找收掉时，点「显示这条」让它回到列表，不改这一套调色。⌘, 是全局偏好。仓库不带厂商样片。

细节和点击顺序在 `docs/ui-plan.md`。

## Quick start (Mac)

1. Install **Xcode 15+** (App Store).
2. Open `macos/LogBridge/LogBridge.xcodeproj`.
3. Select the **LogBridge** scheme → Run (▶), or Product → Archive → Distribute App → **Copy App** for a local `.app`.
4. Drop a folder of mixed Log clips (MOV/MP4 ProRes / H.264 / HEVC; TIFF/DPX/EXR stills).
5. For each **待选** clip, pick a paired Log + gamut IDT in the right inspector. The row stays selected so the preview updates. When that list is only the two rows for S-Log3, C-Log2, or C-Log3, the keys 1 and 2 lock that row. A long catalog has no number keys, so 1 does not lock the first row. **下一条待选** moves to the next unlocked clip. **这一对给后面连续的待选** (⌃⌘]) writes the current pair onto each later pending clip whose own list already contains it, and stops on the first that does not. It does not wrap backward and does not change exposure or white balance.
6. While a locked clip is selected and nothing is writing, the line under the monitor names the file that clip will get — the same name as the write sheet. When that line can open the write sheet, it says so, and a click opens the sheet without picking a folder or starting the write. While settings, add, the write sheet, or the folder panel is up, the line keeps the name and is not a button. A clip that still needs an IDT does not show that line. Click **处理已锁定片段**. The write sheet lists each locked file with its paired IDT, each skipped file with the reason, and the exposure and white balance that will be applied to the locked clips. It also names the folder the panel will open in: the last export folder's name when that folder is still there, or the system location when it is not. The full path stays off the sheet. The row for the clip on the monitor is marked 当前这条, in either the write list or the skip list, and that list scrolls to it. A skipped row has 去选成对 IDT: the sheet closes, that clip stays selected, and the inspector scrolls to the paired list. It does not pick a pair and does not start the write. The same clip keeps its preview frame. Another clip starts at that clip's first frame, the same as a list tap. A filter or query that hides the row is widened. Locked rows do not show that button. After that leave, the inspector title shows **回到写出说明**. Locking the last pending clip still scrolls the column to exposure and leaves the numbers alone; the button stays in the title. The File menu item is the same action and stays disabled until that leave. It reopens the same sheet and does not pick a folder or start the write. It is absent unless you came from that button, and it goes away once the sheet is open again. **选出文件夹并写出** and **关闭** stay under the notes while the notes scroll. Return still confirms. Escape still closes. After it closes, the window says **正在打开选文件夹**, the folder panel is attached to this window, and that panel uses the same sentence. Cancel writes nothing.

The window is one screen: media list, large preview (badge 仅预览), inspector for the selected clip. Under the title, four steps mark where you are: 导入, 选 IDT, 调色, 写出. 导入 is the add panel. 选 IDT scrolls to the pair list, or moves to the next clip that still needs one, and does not pick for you. 调色 only reveals exposure and white balance. 写出 opens the write sheet. Return follows that step except write: an empty bin opens the add panel, a pending clip scrolls to the paired IDT without picking, and a locked clip reveals exposure and white balance without changing the numbers. Once the bin has clips, Return does not open the add panel again. Text fields keep Return. The monitor keeps exposure and white balance visible when the filename is long. The monitor defaults to a split; choose **预览** to enlarge the grade, or press V (the label **V 切换**) to move between that split and the enlarged grade. V does nothing while **源** or **对照** is showing. **对照** still sees the picture without exposure and white balance beside this shared set (preview only; the write still uses the inspector). A line under the monitor title shows the current clip, exposure, and white balance, including 绿品 when a color temperature is set (same numbers as the inspector and the write sheet, preview only). Exposure has **−0.10 / 归零 / +0.10**, and a field to type a stop (`+0.50`). White balance has **−100 K / 回到机内 / +100 K** when a color temperature is already set, and a field to type Kelvin (`4500`) even when the temperature was empty. A value outside the slider range is refused. Switching clips does not replace this set; 回到机内 copies the current clip's camera reading into it, or clears the knobs when that reading is missing. Green–magenta has **−1 / 绿品归零 / +1**; 绿品归零 sets tint to 0 and leaves the temperature. When a movie has a frame range and a metadata frame rate, the scrub line shows a preview clock (frame index divided by that rate) and **回到开头 / 到结尾**. **倒放** (or J) steps backward from the current frame at that same rate and stops on the first frame unless loop is on. It does not change exposure or white balance. The list can show 全部, 待选, or 已锁定. The **调色** menu repeats those steps and **下一条待选**. The inspector title stays put. Once a pair is locked, that title keeps the pair name while exposure and white balance scroll. A pending clip does not show a pair there. IDT, exposure, and white balance still scroll together when the window is short. ⌘, is global preferences (they apply immediately). **高级** adds a luma waveform under the histogram; it is preview-only and stays collapsed. There is no editing timeline. Details and the Mac click-through are in `docs/ui-plan.md`.

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

Default ProRes uses about **1 byte** per pixel per frame for that same check (a planning figure, not a measured bitrate). It does not reuse the 6-byte EXR figure, so a normal movie is not refused before it starts. The write sheet and the folder panel show the figure for the format you picked. ProRes frames are encoded as they are graded. If the Resolve package in the same folder is incomplete, that ProRes file is removed and the status is **达芬奇包不完整，未写出**.
