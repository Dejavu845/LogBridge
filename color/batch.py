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
