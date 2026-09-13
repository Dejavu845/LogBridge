# LogBridge engineering handbook

Durable engineering notes for humans and Cloud Agents. Product copy, IDT tables, and acceptance gates stay in `README.md` and `ACCEPTANCE.md`.

**Honesty:** every IDT and HDR OT is **implemented (unverified)** / **已实现（未验证）**. Not “supported”. Not 一键精准. **CI 绿不等于达芬奇已验证。** 整段代理，不是全精度成片.

## Tech stack

| Layer | Path | Notes |
| --- | --- | --- |
| Python color science | `color/` | Source of truth for 18% grey tests, WB CAT policy, serial graph, locked-IDT batch, Resolve export strings. |
| Packaging | `pyproject.toml` | Package name `logbridge-color`. Runtime: numpy. Test extra: pytest. |
| OCIO assets | `ocio/` | `config.ocio` names BuiltinTransform styles. Linux pytest does **not** require PyOpenColorIO. |
| macOS app | `macos/LogBridge/` | SwiftUI. Xcode 15+, macOS 14. Preview + paired IDT + **处理已锁定片段**. |
| Tests | `tests/` | pytest. Many tests read `.swift` to lock Chinese UI copy. |
| CI | `.github/workflows/test.yml` | Ubuntu pytest + `macos-15` `xcodebuild` of the existing LogBridge scheme. |
| Cloud Agents | `.cursor/environment.json` | Linux: Python 3.12 (fallback ≥3.10) + pytest. **Do not require Xcode.** |
| Scripts | `scripts/` | `generate_ocio_assets.py`; `cloud-agent-install.sh`; `clear-app-quarantine.sh` (quarantine only, not notarization). |

Internal working encoding: **ACEScct** (timeline). Scene-linear interchange: **ACES2065-1** (AP0). WB is Bradford/CAT02 in AP0 linear only. DaVinci Wide Gamut Intermediate is not the default.

## UI principles

Do not regress these without updating the locked tests (`tests/test_ui_copy.py`, `tests/test_settings_zh.py`).

1. **One path.** Drop a mixed-source folder → pick a **paired** Log+gamut IDT → **处理已锁定片段**. Node strip + **导出 ACEScct / EXR** stay behind **高级**.
2. **Paired IDTs.** One list, not two dropdowns. Never silent S-Gamut3.Cine. Never silent Cinema Gamut. Venice pairs only if a Venice body is detected.
3. **Pending stays pending.** Unlocked clips show **先选择 Log 与色域** / **先选择成对 IDT** and produce no `_proxy` folder. Mixed bins are allowed.
4. **Proxy, not a finished picture.** Write is `{stem}_ACES2065-1_proxy/` EXR sequences. Preview badge **预览·非成片**. Rec.709 / HLG / PQ panes are preview.
5. **Chinese settings.** **默认预览** / **导入后提示估计白平衡** / **未锁 IDT 挡住处理** (cannot turn off). No 精准 / 一键还原 / 全自动校准 in UI copy.
6. **WB honesty.** As-shot CCT fills knobs only. Default CAT is identity. Do not guess 5600 K. **白平衡（估计）** is propose-then-confirm.
7. **Fail closed, existing chips.** Prefer the already-defined Chinese notes (`磁盘空间不足，未写出`, `读不出片源色彩标签，没法写出`, `HDR 预览建不出`, …). Do not invent a second process button.

## Coding standards

- **Python 3.10+** locally; **3.12** in CI and Cloud Agents. `from __future__ import annotations` is the existing style.
- **Do not change** curve constants, gamut matrices, IDT pair tables, OCIO Builtin names, or WB CAT unless you have a failing test that cites a white paper mismatch. 18% codes live in `color/curves.py` and `FORMULAS.md`.
- **Do not add cameras.** D-Log M stays a stub (`color/stubs.py`, `FutureIDTs.swift`).
- **Do not add manufacturer demo clips.** Grey-card slots under `tests/fixtures/grey_card/` stay empty in git.
- **Copy contracts.** User-visible Chinese strings are duplicated in Swift and `color/batch.py` / `color/formats.py` on purpose. Change both, then run pytest. Never replace a known chip with generic **解析失败** / **解码失败**.
- **Status language.** “implemented (unverified)” in Python/docs; **已实现（未验证）** in the app. Never “supported” as a camera/HDR claim.
- **Imports.** No unused imports. New code should have type hints on public functions.
- **Tests.** New behavior needs a pytest. Do not skip a missing grey-card by writing a fake 0.18 file.

## Local development (Linux or Mac)

Python color tests do not need Xcode or OCIO:

```bash
git clone https://github.com/Dejavu845/LogBridge.git
cd LogBridge
python3 -m pip install -e ".[test]"
python3 -m pytest -q
```

Without install:

```bash
python3 -m pip install numpy pytest
PYTHONPATH=. python3 -m pytest -q
```

Optional OCIO asset regen (does not change 18% Python references):

```bash
python3 scripts/generate_ocio_assets.py
```

Cloud Agent / Linux bootstrap (idempotent, no Xcode):

```bash
bash scripts/cloud-agent-install.sh
python3 -m pytest -q
```

## Tests

| Command | What it covers |
| --- | --- |
| `python -m pytest -q` | Full Linux-runnable suite (curves, WB, graph, batch, formats, Swift copy locks). |
| `python -m pytest tests/test_ui_copy.py tests/test_settings_zh.py -q` | Chinese UI / settings contracts. |
| `python -m ruff check color tests scripts` | Syntax + undefined names only (see `[tool.ruff]`). |

Grey-card goldens: empty slots **skip**. Do not commit camera frames. See `tests/fixtures/grey_card/README.md`.

## Xcode run (macOS only)

Linux Cloud Agents **cannot** do this. Humans on a Mac:

1. Open `macos/LogBridge/LogBridge.xcodeproj`.
2. Scheme **LogBridge**, destination **My Mac** (not a simulator).
3. **Product → Run** (⌘R) for a Debug trial.
4. **Product → Archive** then Copy App for a local `.app`. Do **not** notarize, do not use App Store / Developer ID.

Gatekeeper / quarantine: `./scripts/clear-app-quarantine.sh /path/to/LogBridge.app` — `xattr` only, not notarization.

Trial reminder: drag your own mixed Log folder. Output is an EXR **picture sequence**, not a video. 整段代理，不是全精度成片.

## CI

`.github/workflows/test.yml`:

- **pytest** job (`ubuntu-latest`, Python 3.12): pip cache, `pip install -e ".[test]"`, fail if `tests/test_*.py` modules are missing, pytest, Ruff syntax gate.
- **macos** job (`macos-15`): `xcodebuild` the existing LogBridge scheme (`CODE_SIGNING_ALLOWED=NO`) then the same pytest.

Not covered in Actions: Metal GPU, Finder reveal, real EXR writes from the app, DaVinci. **CI 绿不等于达芬奇已验证。**

## PR checklist

- [ ] `python -m pytest -q` green.
- [ ] No secrets in the diff.
- [ ] No new manufacturer clips.
- [ ] Chinese UI strings still match Swift ↔ Python (copy tests).
- [ ] No “supported” / 一键精准 / 一键还原 added to user-facing copy.
- [ ] Color/OCIO/WB/IDT math unchanged unless a test proves a paper bug.
- [ ] README / ACCEPTANCE honesty sentences still present if those files were edited.

Do not rsync a macOS `out/` tree; this is not a static-export web app.

## Acceptance

Nothing in `ACCEPTANCE.md` is claimed as passing. Human Resolve checklist is in that file under **真机达芬奇验收**.

If any of Mac `.app` / Resolve / owner-supplied mixed Log is missing, record:

`真机达芬奇验收：未跑（缺：Mac.app / Resolve / 自备片）。CI 绿不等于达芬奇已验证。整段代理，不是全精度成片.`

Do not write “已验”.

## Related files

- `README.md` — product behavior, IDT table, local trial.
- `ACCEPTANCE.md` — gates, including 真机达芬奇.
- `FORMULAS.md` — curve constants (do not invent replacements).
- `docs/OPTIMIZATIONS.md` — P0/P1/P2 backlog and what Cycle 1 implemented.
