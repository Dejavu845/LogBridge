#!/bin/bash
# Compile and run the UI screenshot baseline on the macOS CI runner.
# A state that cannot render is logged and does not fail this step.
# Compile failure still fails the step so a broken tool is visible.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/ui-screenshots"
mkdir -p "$OUT"
SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
cat > "${OUT}/README.txt" <<EOF
CI 离屏渲染·假数据·非真机

这些 PNG 是 macOS CI runner 上的离屏渲染（SwiftUI ImageRenderer / NSHostingView），使用注入的样例状态，没有真机素材。不能当成真机外观。

commit: ${SHA}
EOF

SDK="$(xcrun --sdk macosx --show-sdk-path)"
ARCH="$(uname -m)"
BIN="${RUNNER_TEMP:-/tmp}/logbridge-ui-snapshot"
SRC_DIR="${ROOT}/macos/LogBridge/LogBridge"

SOURCES=()
while IFS= read -r file; do
  SOURCES+=("$file")
done < <(find "$SRC_DIR" -name '*.swift' ! -name 'LogBridgeApp.swift' ! -name '._*' | sort)
SOURCES+=("${ROOT}/scripts/ui_snapshot.swift")

echo "ui-screenshots: compiling ${#SOURCES[@]} Swift files for ${ARCH}"
if ! xcrun swiftc \
  -parse-as-library \
  -swift-version 5 \
  -sdk "$SDK" \
  -target "${ARCH}-apple-macosx14.0" \
  -framework AppKit \
  -framework SwiftUI \
  -framework Metal \
  -framework MetalKit \
  -framework AVFoundation \
  -framework VideoToolbox \
  -framework QuartzCore \
  -framework CoreMedia \
  -framework CoreVideo \
  -framework CoreGraphics \
  -framework ImageIO \
  -framework UniformTypeIdentifiers \
  -o "$BIN" \
  "${SOURCES[@]}"; then
  echo "ui-screenshots: compile failed; no PNGs produced"
  exit 1
fi

"$BIN" --out "$OUT"
echo "ui-screenshots: tool finished (state failures stay in the log and do not fail the job)"
if [ -f "${OUT}/manifest.txt" ]; then
  echo "----- ui-screenshots/manifest.txt -----"
  cat "${OUT}/manifest.txt"
fi
exit 0
