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

- Golden grey-block samples still pending (`tests/fixtures/grey_card/` empty slots). Do not invent numbers.
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

## P1 — left for next cycle

| ID | Item | Why wait |
| --- | --- | --- |
| P1-ruff-style | Broader Ruff (E/F/I/UP) | Cycle 1 only gates syntax/undefined names so we do not churn the huge copy-lock tests. |
| P1-types | Type hints across `color/` | Cycle 16 locked all public `curves` returns. Remaining: `batch` / as_shot / mypy. |
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
