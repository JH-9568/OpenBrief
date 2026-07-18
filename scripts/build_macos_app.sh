#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_PATH="$DIST_DIR/OpenBrief.app"

rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

cat > "$APP_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>OpenBrief</string>
  <key>CFBundleIdentifier</key>
  <string>dev.openbrief.launcher</string>
  <key>CFBundleName</key>
  <string>OpenBrief</string>
  <key>CFBundleDisplayName</key>
  <string>OpenBrief</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.2</string>
  <key>CFBundleVersion</key>
  <string>0.1.2</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
</dict>
</plist>
PLIST

cat > "$APP_PATH/Contents/MacOS/OpenBrief" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail

OPENBRIEF_BIN="${OPENBRIEF_BIN:-}"

if [[ -z "$OPENBRIEF_BIN" ]] && command -v openbrief >/dev/null 2>&1; then
  OPENBRIEF_BIN="$(command -v openbrief)"
fi

if [[ -z "$OPENBRIEF_BIN" && -x "$HOME/.local/bin/openbrief" ]]; then
  OPENBRIEF_BIN="$HOME/.local/bin/openbrief"
fi

if [[ -z "$OPENBRIEF_BIN" && -x "/opt/homebrew/bin/openbrief" ]]; then
  OPENBRIEF_BIN="/opt/homebrew/bin/openbrief"
fi

if [[ -z "$OPENBRIEF_BIN" ]]; then
  osascript -e 'display dialog "OpenBrief CLI is not installed. Install it first with: pipx install \"git+https://github.com/JH-9568/OpenBrief.git\"" buttons {"OK"} default button "OK"'
  exit 127
fi

"$OPENBRIEF_BIN" start --daemon --no-browser >/tmp/openbrief-launcher.log 2>&1 || true

STATUS_OUTPUT="$("$OPENBRIEF_BIN" status 2>/tmp/openbrief-launcher-status.log || true)"
DASHBOARD_URL="$(printf '%s\n' "$STATUS_OUTPUT" | awk '/Dashboard:/ {print $2; exit}')"

if [[ -z "$DASHBOARD_URL" ]]; then
  DASHBOARD_URL="http://127.0.0.1:8000/dashboard"
fi

open "$DASHBOARD_URL"
LAUNCHER

chmod +x "$APP_PATH/Contents/MacOS/OpenBrief"

echo "Built $APP_PATH"
echo "This unsigned app requires OpenBrief to be installed first:"
echo '  pipx install "git+https://github.com/JH-9568/OpenBrief.git"'
