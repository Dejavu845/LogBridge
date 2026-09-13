# LogBridge optimizations backlog

Prioritized engineering backlog. Color science, IDT pairs, WB CAT, and node-graph order are **out of scope** unless a tested bug is found.

Every IDT / HDR OT stays **implemented (unverified)**. Not “supported”. Not 一键精准. **CI 绿不等于达芬奇已验证。** 整段代理，不是全精度成片.

## Cycle 1 (this cycle) — implemented

| ID | Item | What landed |
| --- | --- | --- |
| P0-docs | Engineering handbook + this backlog | `docs/ENGINEERING.md`, `docs/OPTIMIZATIONS.md` |
| P0-env | Cloud Agent environment | `.cursor/environment.json` + `scripts/cloud-agent-install.sh`. Python 3.12 preferred (≥3.10), numpy + pytest. **No Xcode on Linux.** |
| P0-ci | CI must not go green on an empty suite | `.github/workflows/test.yml`: pip cache, `pip install -e ".[test]"`, fail if `tests/test_*.py` count &lt; 10, Ruff syntax/undefined-name gate on Linux |
| P0-pkg | Packaging hygiene | `pyproject.toml` license, URLs, lint extra, Ruff config. `requirements.txt` still matches runtime+test deps. |
| P1-copy | Keep existing Chinese failure chips | `preserved_failure_note` keeps **磁盘空间不足，未写出** / **写出失败** / **已取消** / any `未写出` chip instead of rewriting them to **解码失败** |
| P1-dead | Unused imports | Drop unused `apply_white_balance` / `DEFAULT_WORKING_LINEAR` from `color/pipeline.py` |
| P1-tests | Contract tests (no new cameras) | `tests/test_engineering_contracts.py` locks docs honesty, env/CI gates, packaging, and the failure-copy preserve |

## P0 — still open (next cycle if needed)

None of the P0 engineering-quality items above are left unfinished on purpose. Remaining P0 **product** gates are **not** coding work for a Linux agent:

- Golden grey-card samples still pending (`tests/fixtures/grey_card/` empty slots). Do not invent numbers.
- 真机达芬奇验收: **未跑** unless a Mac `.app`, Resolve, and owner-supplied mixed Log exist. Do not fake-pass.

## Cycle 3 — implemented

| ID | Item | What landed |
| --- | --- | --- |
| P0-batch-floor | Catch truncated `color/batch.py` | `scripts/ci-guard-tests.sh` + `tests/test_batch_file_floor.py` require ≥1340 `splitlines()` and key helpers. Does **not** rewrite `batch.py`. |

## Cycle 4 — implemented

| ID | Item | What landed |
| --- | --- | --- |
| LB-01 | Venice silent-IDT in preview | `PreviewEngine.cameraToAP0` / `decodeLog` now include both Venice cases (same non-Venice S-Gamut3 pair as `ResolveExporter` / `color/pipeline.py`). No invented Venice matrix. **Local tree only until a human pushes PreviewEngine.swift.** |
| LB-05 | LogC4 `x<0` | Swift `decodeLog` mirrors `color/curves.py` `_LOGC4_S` / `_LOGC4_T`. Still unverified. **Local tree only until PreviewEngine / ResolveExporter are pushed.** |
| LB-04 | Swift↔Python parity | `tests/test_swift_parity.py` locks every non-stub IDT case, Preview==Exporter matrices, and Python `camera_to_aces2065_matrix`. |
| LB-07 | OCIO drift + stale DWG | `generate_ocio_assets.py --out/--check`; delete unreferenced `*_to_DWG` / leftover XYZ matrices. |
| LB-08 | README copy inventory | `tests/test_readme_copy.py` — CJK constants must be in README/ACCEPTANCE or listed in `KNOWN_DESYNC` (65 of 93 sit in `KNOWN_DESYNC`; the rest are pinned. The list is a ratchet, not a sync claim). |

## Cycle 5 — Opus C3 follow-up

| ID | Item | What landed |
| --- | --- | --- |
| P0-batch-floor | Same statement, same counter | `ci-guard-tests.sh` now uses `splitlines()` (not `wc -l`). Floor is 1340 (10-line slack on 1350). Helper-name asserts live in `tests/test_batch_file_floor.py` so a SyntaxError in `batch.py` still prints the intended message (that module does not `import color.batch`). |

## Cycle 6 — Opus C4 follow-up

| ID | Item | What landed |
| --- | --- | --- |
| H1 | LogC4 numeric lock | `test_swift_parity.py` evaluates Swift `let s` / `let t` and compares to `_LOGC4_S` / `_LOGC4_T` at 1e-12. A comment naming those tokens no longer passes. |
| M1/M2 | Copy gate | `.help` / `navigationTitle` / `Label` / …; ban-quote allowlist is the two SettingsView disclaimer lines, not a `不写` substring. |
| M3 | `--check` globals | `check_against` restores `LUT_DIR` / `MTX_DIR` / `CONFIG` in `finally`. |
| M4 | Dead AP0 `.spimtx` | Stop emitting / delete `BT2020_to_AP0`, `DGamut_to_AP0`, `AppleWideGamut_to_AP0`. `config.ocio` already inlines those matrices; the files were unreferenced. |
| M5 | Handbook | `docs/ENGINEERING.md` documents `--check`. |

## Cycle 7 — Opus C6 follow-up

| ID | Item | What landed |
| --- | --- | --- |
| M1 | Live-code LogC4 lock | `_live_code_lines` drops `//` comments; requires live `if x < 0.0 { return x * s + t }`; first `let` wins so a later comment/case cannot shadow. |
| N1 | Trailing `//` on `let s` | Split before `eval` (same as MagicPad `test-protocol.py`). |
| M2 | CJK `不写` hatch | `test_readme_copy.py` CJK constants no longer exempt a needle because the value also contains `不写`. Cycle 7 called this the last hatch; it was not — see Cycle 8. |
| N2 | Empty matrices dir | `generate_matrices()` is a true no-op (no `mkdir`). |

## Cycle 8 — Opus C7 follow-up

| ID | Item | What landed |
| --- | --- | --- |
| M1 | Case-scoped LogC4 lock | Chunk is the `arriLogC4AWG4` case body (next `case `), not 800 characters. `_live_code_lines` strips `/* */`. Live `#if` / `if false` rejected. |
| M2 | Settings `不写` hatches | `test_ui_copy.py` / `test_settings_zh.py` scan SettingsView with the two allowlisted disclaimer lines removed. Tree-wide `一键精准` / HDR `精准` bans have no `Not 一键精准` disjunct. |
| M3 | False matrices print | Drop `Wrote matrices in …` and unused `write_spimtx`. `generate_matrices()` stays a no-op. |

## Cycle 9 — Opus C7 leftover M4 / nits

| ID | Item | What landed |
| --- | --- | --- |
| M4 | Assigned CJK literals | `test_readme_copy.py` flags `let` / `var` / `static let` string assignments that contain a banned phrase, not only UI constructors. |
| N1 | LogC4 pin comment | One-line pin next to both Swift `if x < 0.0 { return x * s + t }` (local Swift; same human push as Venice). |
| N3 | Stale MARK | `ResolveExporter` MARK no longer points at deleted `ocio/matrices/*.spimtx`. |

## Cycle 10 — C7 M4 concat residual

| ID | Item | What landed |
| --- | --- | --- |
| M4 | Joined quotes | `Text("一键" + "精准校准")` is caught by joining every `"…"` on a UI constructor line. |

## Cycle 11 — C7 M4 multiline residual

| ID | Item | What landed |
| --- | --- | --- |
| M4 | Split constructor | `Text(` on one line and a banned quoted phrase on the next is caught. |

## Cycle 12 — C7 M4 assignment/ctor continuation

| ID | Item | What landed |
| --- | --- | --- |
| M4 | Assignment / ctor spans | `let x = "一键"` ↵ `+ "精准校准"` and `Text(` ↵ `"一键"` ↵ `+ "精准校准"` join up to 8 lines. Synthetic cases in `test_readme_copy.py`. |

## Cycle 13 — Swift file floors

| ID | Item | What landed |
| --- | --- | --- |
| LB-floor | Preview / Exporter | `tests/test_swift_file_floor.py` + `ci-guard-tests.sh` require ≥1700 / ≥900 lines, `Venice`, and the live LogC4 `if x < 0.0 { return x * s + t }`. Does **not** rewrite those Swift files. Remote truncated PreviewEngine stays red until a human push. |

## Cycle 14 — P1-types return annotations

| ID | Item | What landed |
| --- | --- | --- |
| P1-types | Return annotations | `pipeline.apply_odt_rec709` / `apply_selected_odt`, all public `working_space` helpers, and `curves.decode_log` / `encode_log` now declare `-> np.ndarray`. Numbers unchanged. `tests/test_public_types.py` locks the annotations. |

## Cycle 15 — P1-types formats / detect / rec709 / ODT

| ID | Item | What landed |
| --- | --- | --- |
| P1-types | More return annotations | Public `formats` / `detect` already declared returns; the lock now requires them. `rec709` helpers and `odt.apply_odt` declare `-> np.ndarray`. Numbers unchanged. |

## Cycle 16 — P1-types individual log curves

| ID | Item | What landed |
| --- | --- | --- |
| P1-types | Curve pair returns | Every public function in `color/curves.py` now declares `-> np.ndarray` (encode/decode pairs plus dispatch). Numbers unchanged. `test_curves_public_return_annotations` locks them. |

## Cycle 17 — P1-types as-shot / exposure

| ID | Item | What landed |
| --- | --- | --- |
| P1-types | as_shot / exposure | `write_as_shot_to_graph` declares a return. Public `as_shot` and `exposure` helpers are locked. CAT/IDT numbers unchanged. `batch.py` still unrestored on remote. |

## Cycle 34 — QuickTime nclc never identifies an IDT

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | nclc | `NCLC_KEYS` matches `as_shot._NCLC_KEYS`. Metadata IDT path drops those keys. Swift still discards nclc. Color math unchanged. |

## Cycle 33 — D-Log M tokens never lock D-Gamut

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | D-Log M | `dlog_m_token_hit` / Swift `filenameIsDLogMStub`. Filename and metadata D-Log M stay stub. Plain D-Log still locks D-Gamut. Color math unchanged. |

## Cycle 32 — C-Log2 / C-Log3 without gamut stay on the picker

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | C-Log filename | `clog2_filename_needs_picker` / `clog3_filename_needs_picker` + Swift `filenameNeedsCLog2Picker` / `filenameNeedsCLog3Picker`. Bare C-Log never locks Cinema Gamut. Color math unchanged. |

## Cycle 31 — S-Log3 without gamut stays on the picker

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | S-Log3 filename | `slog3_filename_needs_picker` / Swift `filenameNeedsSLog3Picker`. Bare `slog3` never locks Cine. `sgamut3` still locks the pair. IDT.swift comment no longer contains the banned one-click overclaim substring. Color math unchanged. |

## Cycle 30 — filename hints stay locked pairs

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Filename | Apple Log 2 → AWG (not BT.2020). LogC3 → EI800+AWG3. D-Log → D-Gamut, never D-Log M. Swift `ClipDetector.detectFilename` matches. Color math unchanged. |

## Cycle 29 — live picker UI copy

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Live UI | Inspector uses `pair.pairLabel`. `verificationBadge` is 已实现（未验证）/待选/未实现. `hasLockedPair` requires `!isStub` and `!needsUserPicker`. Color math unchanged. |

## Cycle 28 — one-click blocked while picker is up

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | One-click | `can_one_click_process` stays false when `needs_user_picker` even if `idt_id` is a real pair. Color math unchanged. |

## Cycle 27 — menuLabel never says supported

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Status copy | Swift `implementedStatus` / `stubStatus` + Python mirrors. menuLabel interpolates those tokens. Never “supported”. Color math unchanged. |

## Cycle 26 — Venice rows never silent

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Venice gate | `venice_rows_allowed` / Swift `allowsVeniceRows`. Filename/model hints never emit Venice IDs. `FutureIDTs.veniceIsSilentDefault()` is false. Color math unchanged. |

## Cycle 25 — Swift implemented set == Python IDT_PAIRS

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | IDT set | Swift `IDT` raw values minus stub equal `IDT_PAIRS`. Non-Venice implemented set equals `IMPLEMENTED_NON_VENICE`. |

## Cycle 24 — Swift/Python picker ID parity

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Picker IDs | Swift `pickerPairs` S-Log3 / C-Log2 / C-Log3 case lists match Python `SLOG3_*` / `CLOG2_PAIRS` / `CLOG3_PAIRS` raw values. |

## Cycle 23 — Swift picker excludes D-Log M stub

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Swift picker | `IDT.pickerPairs` is locked to `implemented.filter` (not `allCases`). `can_one_click_process` is false for `dji_dlog_m`. |

## Cycle 22 — picker never offers D-Log M

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | Picker lock | `picker_pairs()` never returns `dji_dlog_m` (Venice / S-Log3 / C-Log3 variants included). `test_picker_never_offers_dlog_m`. |

## Cycle 21 — D-Log M Swift stub lock

| ID | Item | What landed |
| --- | --- | --- |
| P2-cameras | D-Log M stub | `FutureIDTs.dLogMIsSupported()` is locked `false`. `test_dlog_m_stub_lock.py` refuses a homemade transfer. Numbers unchanged. |

## Cycle 20 — batch YCbCr returns (local restore only)

| ID | Item | What landed |
| --- | --- | --- |
| P1-types | batch YCbCr | Local `ycbcr_*` / `preview_u8_promoted_float` declare returns. `test_batch_ycbcr_helpers_annotated_when_restored` skips when `batch.py` < 1340. Do not MCP-upload `batch.py`. |

## Cycle 19 — ENGINEERING types + batch floor honesty

| ID | Item | What landed |
| --- | --- | --- |
| docs | Types / batch floor | ENGINEERING states Cycles 14–18 locked public `color/` returns except unrestored `batch.py`. Do not weaken ≥1340. Do not MCP-upload `batch.py`. |

## Cycle 18 — remaining color modules (not batch)

| ID | Item | What landed |
| --- | --- | --- |
| P1-types | Rest of `color/` | `dlog_m_to_linear` is `-> NoReturn` (still raises; D-Log M stays stub). Public `auto_wb` / `exr_write` / `gamuts` / `graph` / `ocio_builtins` / `resolve_export` / `wb` / `stubs` returns are locked. `batch.py` stays a human-push item. |

## P1 — left for next cycle

| ID | Item | Why wait |
| --- | --- | --- |
| P1-ruff-style | Broader Ruff (E/F/I/UP) | Cycle 1 only gates syntax/undefined names so we do not churn the huge copy-lock tests. |
| P1-types | Type hints across `color/` | Cycle 18 locked the rest of public `color/` except `batch.py` (human push) / mypy. |
| P1-split-ui-tests | Split `tests/test_ui_copy.py` | The file is a locked copy contract. Splitting risks false diffs in review. |
| P1-lockfile | `uv.lock` / pip-tools pin | pyproject ranges + CI cache are enough; a lockfile is nicer but not required for pytest. |
| P1-unused-swift | Swift dead-code pass | Needs Xcode; Linux agents cannot compile. |
| P1-hdr-ocio-optional | Optional PyOpenColorIO in CI | Linux 18% tests are reference curves **by design**. Adding OCIO is extra coverage, not a correctness claim. |

## P2 — later

| ID | Item | Notes |
| --- | --- | --- |
| P2-mypy | `mypy --strict` extra | Only after P1 types. Must not change CAT/IDT numbers. |
| P2-pre-commit | pre-commit (Ruff + pytest collect) | Nice for humans; CI already gates. |
| P2-dependabot | GitHub Dependabot for Actions + pip | Separate from color science. |
| P2-swift-tests | Native Swift tests | Today Swift is locked by Python reading source. A XCTest target is Mac-only. |
| P2-ui-rewrite | SwiftUI layout / inspector redesign | Explicitly forbidden unless a later cycle is scoped to UI. |
| P2-cameras | New IDTs / D-Log M | Stay stubbed. Do not implement without papers + 18% tests + paired picker. |
| P2-samples | Manufacturer demo clips | Forbidden. Users drop their own Log. |
| P2-hlg-pq-diy | Homemade HLG/PQ | Forbidden. HDR OT is ACES/BT.2100 Builtin only; macOS preview is ColorSync. |
| P2-split-graph | General node editor | Serial four-slot graph is the product. |

## Explicitly never

- Silent IDT or silent S-Gamut3.Cine / Cinema Gamut.
- Guessing 5600 K / 6504 K when as-shot CCT is missing.
- Calling CI green “达芬奇已验证” or IDTs “supported”.
- Shipping camera manufacturer sample reels.
- Changing OCIO Builtin style names or 18% codes without a failing test that proves a paper mismatch.
