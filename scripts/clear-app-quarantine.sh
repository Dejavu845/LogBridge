#!/usr/bin/env bash
# 本机试用：清掉拷过来的 .app 上的隔离属性（quarantine）。
#
# 不是公证（notarization），不是签名，不是上架，无密钥。
# 只在你自己拷来的试用 LogBridge.app 上跑。不要拿去提交 Apple。
#
# 用法（本机终端）：
#   ./scripts/clear-app-quarantine.sh /path/to/LogBridge.app
#
# 做了什么：xattr -dr com.apple.quarantine <app>
# 没做什么：不跑 notarytool、不改证书、不打包、不声称已公证。
# 整段代理，不是全精度成片。CI 绿不等于达芬奇已验证。

set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  ./scripts/clear-app-quarantine.sh /path/to/LogBridge.app

只清隔离（com.apple.quarantine）。不是公证，不是签名，无密钥。
只在 macOS 上对自己拷来的试用 .app 跑。
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "这是 macOS 本机脚本。Linux / CI 清不了隔离，也不需要。" >&2
  exit 1
fi

if [[ ! -e "$1" ]]; then
  echo "找不到这个路径：$1" >&2
  exit 1
fi

# Resolve to an absolute path without requiring the caller to cd.
APP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"

if [[ "$APP" != *.app ]]; then
  echo "路径要指向一个 .app 包，例如 LogBridge.app" >&2
  exit 1
fi

if [[ ! -d "$APP" ]]; then
  echo "这不是一个 .app 包：$APP" >&2
  exit 1
fi

echo "将清隔离（不是公证）：$APP"
if command -v xattr >/dev/null 2>&1; then
  if xattr -l "$APP" 2>/dev/null | grep -qi quarantine; then
    xattr -l "$APP" 2>/dev/null | grep -i quarantine || true
  else
    echo "包根上看不到 com.apple.quarantine（里面可能还有，仍会递归清）。"
  fi
  xattr -dr com.apple.quarantine "$APP"
else
  echo "这台机器没有 xattr。" >&2
  exit 1
fi

echo "已清 com.apple.quarantine。再双击打开。仍拦就按住 Control 点 → 打开。"
echo "整段代理，不是全精度成片。不要去做公证。"
