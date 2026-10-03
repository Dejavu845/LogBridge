#!/bin/bash
# Re-render commit 28066d5 with the current capture method.
# The worktree is disposable. Nothing is committed onto 28066d5.

set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WT="${RUNNER_TEMP:-/tmp}/logbridge-ui-baseline-28066d5"
rm -rf "$WT"
git -C "$ROOT" worktree add --detach "$WT" 28066d5
cleanup() {
  git -C "$ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"
}
trap cleanup EXIT

python3 "${ROOT}/scripts/wire_baseline_shot_launch.py" "$WT" "$ROOT"

export SNAPSHOT_SRC_ROOT="$WT"
export SNAPSHOT_TOOL="${ROOT}/scripts/ui_snapshot.swift"
export SNAPSHOT_OUT="${ROOT}/ui-screenshots-baseline"
export SNAPSHOT_SHA="28066d5"
export SNAPSHOT_XCTEST=1
export SNAPSHOT_REQUIRE_TOOLBAR=0
export SNAPSHOT_PROJECT_DIR="${WT}/macos/LogBridge"
bash "${ROOT}/scripts/ui_snapshot.sh"
