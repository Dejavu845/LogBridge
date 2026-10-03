#!/bin/bash
# Compile and run the UI screenshot capture on the macOS CI runner.
# NSHostingView + cacheDisplay first. If those PNGs are still the prohibited
# placeholder or a blank field, launch the real app with XCUITest.
# The checker fails this step when the shots are still unusable.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_ROOT="${SNAPSHOT_SRC_ROOT:-$ROOT}"
OUT="${SNAPSHOT_OUT:-${ROOT}/ui-screenshots}"
TOOL="${SNAPSHOT_TOOL:-${ROOT}/scripts/ui_snapshot.swift}"
XCTEST="${SNAPSHOT_XCTEST:-1}"
export SNAPSHOT_REQUIRE_TOOLBAR="${SNAPSHOT_REQUIRE_TOOLBAR:-1}"
PROJECT_DIR="${SNAPSHOT_PROJECT_DIR:-${SRC_ROOT}/macos/LogBridge}"
SHA="${SNAPSHOT_SHA:-$(git -C "$SRC_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)}"
CHECK="${ROOT}/scripts/check_ui_screenshots.py"

mkdir -p "$OUT"
cat > "${OUT}/README.txt" <<EOF
CI 离屏渲染·假数据·非真机

这些 PNG 是 macOS CI runner 上的整窗捕获（标题栏和工具栏，不只是内容区）。NSHostingController 装上工具栏，跑几轮 runloop（约 0.5s）后 cacheDisplay 窗框，或对 windowNumber 做 CGWindowListCreateImage。高度必须大于内容高度。若仍是占位色、空白或没有工具栏，则改由 XCUITest 启动真应用，注入样例状态，用窗口 screenshot。没有真机素材。不能当成真机外观。

commit: ${SHA}
EOF

SDK="$(xcrun --sdk macosx --show-sdk-path)"
ARCH="$(uname -m)"
BIN="${RUNNER_TEMP:-/tmp}/logbridge-ui-snapshot"
SRC_DIR="${SRC_ROOT}/macos/LogBridge/LogBridge"

SOURCES=()
while IFS= read -r file; do
  SOURCES+=("$file")
done < <(find "$SRC_DIR" -name '*.swift' ! -name 'LogBridgeApp.swift' ! -name '._*' | sort)
SOURCES+=("$TOOL")

echo "ui-screenshots: compiling ${#SOURCES[@]} Swift files for ${ARCH}"
echo "ui-screenshots: sources ${SRC_DIR}"
echo "ui-screenshots: tool ${TOOL}"
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

"$BIN" --out "$OUT" || echo "ui-screenshots: hosting capture returned errors (checker decides)"
if [ -f "${OUT}/manifest.txt" ]; then
  echo "----- ui-screenshots/manifest.txt -----"
  cat "${OUT}/manifest.txt"
fi

if python3 "$CHECK" "$OUT"; then
  echo "ui-screenshots: hosting capture accepted"
  exit 0
fi

echo "ui-screenshots: NSHostingView cacheDisplay still placeholder or blank"
if [ "$XCTEST" != "1" ]; then
  exit 1
fi

rm -f "$OUT"/*.png
printf '%s\n' "$OUT" > /tmp/logbridge-ui-screenshot-out.txt
if [ "${SNAPSHOT_REQUIRE_TOOLBAR}" = "0" ]; then
  printf '0\n' > /tmp/logbridge-ui-shot-require-toolbar.txt
else
  rm -f /tmp/logbridge-ui-shot-require-toolbar.txt
fi
export UI_SCREENSHOT_OUT="$OUT"
echo "ui-screenshots: XCUITest fallback"
if ! xcodebuild \
  -project "${PROJECT_DIR}/LogBridge.xcodeproj" \
  -scheme LogBridge \
  -destination 'platform=macOS' \
  -configuration Debug \
  CODE_SIGNING_ALLOWED=YES \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY=- \
  ENABLE_HARDENED_RUNTIME=NO \
  test \
  -only-testing:LogBridgeUITests; then
  echo "ui-screenshots: XCUITest failed"
  python3 "$CHECK" "$OUT" || exit 1
  exit 1
fi
python3 "$CHECK" "$OUT"
exit $?
