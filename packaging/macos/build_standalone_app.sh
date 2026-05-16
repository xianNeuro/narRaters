#!/usr/bin/env bash
# Build narRater.app with the full project bundled for drag-to-Applications install.
# Runtime copies to ~/Library/Application Support/narRaters/ on first launch (writable).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_APP="${1:-$PROJECT_ROOT/narRater.app}"
VERSION="$(sed -n 's/^version = "\([^"]*\)".*/\1/p' "$PROJECT_ROOT/pyproject.toml" | head -1)"
VERSION="${VERSION:-0.0.0}"
ICON_SRC="$PROJECT_ROOT/static/app-icon.png"
BUNDLE_ROOT_NAME="narRaters"

rm -rf "$OUT_APP"
mkdir -p "$OUT_APP/Contents/MacOS"
mkdir -p "$OUT_APP/Contents/Resources"

if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$OUT_APP/Contents/Resources/AppIcon.png"
fi

BUNDLE="$OUT_APP/Contents/Resources/$BUNDLE_ROOT_NAME"
mkdir -p "$BUNDLE"
rsync -a \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='narRater.app/' \
  --exclude='narRaters_installer.app/' \
  --exclude='narRaters-macos-installer.dmg' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='.DS_Store' \
  --exclude='data/1_story_audio/pieman_edited.wav' \
  --exclude='data/4_recall_audio/*.mp4' \
  --exclude='narRater_Tutorial.pdf' \
  "$PROJECT_ROOT/" "$BUNDLE/"

echo "$VERSION" >"$BUNDLE/.bundle_version"

START_SH="$OUT_APP/Contents/MacOS/start_server.sh"
cat >"$START_SH" <<'EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

MACOS_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$MACOS_DIR/../.." && pwd)"
BUNDLE_ROOT="$APP_ROOT/Contents/Resources/narRaters"
APP_SUPPORT="$HOME/Library/Application Support/narRaters"
RUNTIME_ROOT="$APP_SUPPORT/runtime"
VENV="$APP_SUPPORT/.venv"
STAMP="$APP_SUPPORT/.bundle_version"
VERSION="$(cat "$BUNDLE_ROOT/.bundle_version" 2>/dev/null || echo 0)"

mkdir -p "$APP_SUPPORT" "$RUNTIME_ROOT/data" "$RUNTIME_ROOT/output"

sync_runtime() {
  rsync -a \
    --exclude='.venv/' \
    --exclude='data/' \
    --exclude='output/' \
    --exclude='pipeline_config.json' \
    "$BUNDLE_ROOT/" "$RUNTIME_ROOT/"
  echo "$VERSION" >"$STAMP"
}

if [[ ! -f "$RUNTIME_ROOT/server/web-interface.py" ]] || [[ "$(cat "$STAMP" 2>/dev/null)" != "$VERSION" ]]; then
  echo "Preparing narRaters (first launch or update)…"
  sync_runtime
  if [[ ! -f "$RUNTIME_ROOT/data/2_story_transcript/the_siren.txt" ]]; then
    rsync -a "$BUNDLE_ROOT/data/" "$RUNTIME_ROOT/data/" 2>/dev/null || true
    rsync -a "$BUNDLE_ROOT/output/" "$RUNTIME_ROOT/output/" 2>/dev/null || true
  fi
fi

PY="$VENV/bin/python3"
if [[ ! -x "$PY" ]] || ! "$PY" -c "import flask" 2>/dev/null; then
  if ! command -v python3 &>/dev/null; then
    osascript -e 'display dialog "Python 3 is required. Install from https://www.python.org/downloads/ then open narRater again." buttons {"OK"} default button "OK" with icon stop'
    exit 1
  fi
  echo "Installing dependencies (one-time)…"
  python3 -m venv "$VENV"
  PY="$VENV/bin/python3"
  "$PY" -m pip install -U pip wheel
  "$PY" -m pip install -e "$RUNTIME_ROOT"
fi

export NARRATERS_PROJECT_ROOT="$RUNTIME_ROOT"
cd "$RUNTIME_ROOT/server"
export PYTHONUNBUFFERED=1
echo "narRaters — $RUNTIME_ROOT"
echo "http://127.0.0.1:5000 (Ctrl+C to stop)"
exec "$PY" web-interface.py
EOF
chmod +x "$START_SH"

LAUNCHER="$OUT_APP/Contents/MacOS/narRater"
cat >"$LAUNCHER" <<'LAUNCHER_EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"
START_SH="$(cd "$(dirname "$0")" && pwd)/start_server.sh"

osascript <<OSA
tell application "Terminal"
  activate
  do script "bash " & quoted form of "$START_SH"
end tell
OSA

for _ in $(seq 1 90); do
  if curl -sf --connect-timeout 1 "http://127.0.0.1:5000/pipeline-config" >/dev/null 2>&1 \
     || curl -sf --connect-timeout 1 "http://127.0.0.1:5000/" >/dev/null 2>&1; then
    open "http://127.0.0.1:5000/pipeline-config" 2>/dev/null || true
    exit 0
  fi
  sleep 0.5
done
open "http://127.0.0.1:5000/pipeline-config" 2>/dev/null || true
LAUNCHER_EOF
chmod +x "$LAUNCHER"

cat >"$OUT_APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>narRater</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>org.narraters.desktop</string>
  <key>CFBundleName</key>
  <string>narRater</string>
  <key>CFBundleDisplayName</key>
  <string>narRater</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${VERSION}</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
EOF

echo "Built standalone app: $OUT_APP (version $VERSION)"
