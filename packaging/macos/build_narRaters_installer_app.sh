#!/usr/bin/env bash
# Build narRaters_installer.app in the project root (next to server/).
# Double-click runs Terminal and pip install -e . for the parent folder, or narRaters_source/
# when the app is laid out next to that folder (e.g. inside the DMG).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_DIR="$PROJECT_ROOT/narRaters_installer.app"
ICON_SRC="$PROJECT_ROOT/static/app-icon.png"

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APP_DIR/Contents/Resources/AppIcon.png"
fi

RUN_SH="$APP_DIR/Contents/MacOS/run_install.sh"
cat > "$RUN_SH" <<'EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

MACOS_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTENTS="$(cd "$MACOS_DIR/.." && pwd)"
APP_BUNDLE="$(cd "$CONTENTS/.." && pwd)"
PARENT="$(cd "$APP_BUNDLE/.." && pwd)"

if [[ -f "$PARENT/server/web-interface.py" ]]; then
  PROJECT_ROOT="$PARENT"
elif [[ -f "$PARENT/narRaters_source/server/web-interface.py" ]]; then
  PROJECT_ROOT="$PARENT/narRaters_source"
else
  osascript -e 'display dialog "Could not find narRaters files.

Keep narRaters_installer.app in the project folder next to server/, or open the DMG and run this app from there (with narRaters_source/ alongside it)." buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  osascript -e 'display dialog "Python 3 was not found. Install from https://www.python.org/downloads/ or Homebrew, then try again." buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
  exit 1
fi

echo "Project root: $PROJECT_ROOT"
echo "Running: python3 -m pip install -e \"$PROJECT_ROOT\""
echo ""

if python3 -m pip install -e "$PROJECT_ROOT"; then
  osascript -e 'display dialog "Setup finished.

Next: double-click server/START_HERE.command, or build narRater.app (README), or run: narraters serve" buttons {"OK"} default button "OK" with title "narRaters"' 2>/dev/null || true
else
  osascript -e 'display dialog "pip install failed. See the Terminal window above for errors." buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
  exit 1
fi

echo ""
read -r -p "Press Enter to close this window…" _
EOF
chmod +x "$RUN_SH"

LAUNCHER="$APP_DIR/Contents/MacOS/narRaters_installer"
cat > "$LAUNCHER" <<'LAUNCHER_EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

MACOS_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_SH="$MACOS_DIR/run_install.sh"

osascript <<OSA
tell application "Terminal"
    activate
    do script "bash " & quoted form of "$RUN_SH"
end tell
OSA
LAUNCHER_EOF
chmod +x "$LAUNCHER"

PLIST="$APP_DIR/Contents/Info.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>narRaters_installer</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>org.narraters.installer</string>
  <key>CFBundleName</key>
  <string>narRaters_installer</string>
  <key>CFBundleDisplayName</key>
  <string>narRaters installer</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
EOF

echo "Built: $APP_DIR"
echo "Double-click narRaters_installer.app (first time: right-click → Open if Gatekeeper blocks)."
