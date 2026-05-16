#!/usr/bin/env bash
# Build "narRater.app" in the project root (next to server/, static/, etc.).
# Double-click opens Terminal, runs Flask from project/server, then opens the login page.
#
# Portable bundle (since v1.1): the launcher inside the .app resolves both PROJECT_ROOT
# (from the .app's own location) and the Python interpreter (from standard locations) at
# *run time*. The resulting bundle can be copied between Macs without rebuilding — only
# requirement is that the user has Python 3.10+ on PATH and `pip install -e .` (or
# `pip install -r requirements.txt`) ran successfully on that machine.
set -euo pipefail

# Prefer Homebrew / standard locations over niche interpreters early on PATH (e.g. FSL python).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_NAME="narRater.app"
APP_DIR="$PROJECT_ROOT/$APP_NAME"
ICON_SRC="$PROJECT_ROOT/static/app-icon.png"
CROP_PY="$SCRIPT_DIR/crop_squircle_icon.py"

if [[ ! -f "$ICON_SRC" ]]; then
  echo "Missing icon: $ICON_SRC (add static/app-icon.png first)" >&2
  exit 1
fi

# Pillow + numpy are needed only for the icon crop step (which runs locally during build).
# The launcher inside the .app itself no longer embeds a Python path, so this is for the
# build-time icon prep only.
CROP_PY_BIN=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
  [[ -z "$cand" || ! -x "$cand" ]] && continue
  if "$cand" -c "from PIL import Image; import numpy" 2>/dev/null; then
    CROP_PY_BIN="$cand"
    break
  fi
done

# Crop black frame → squircle on transparent square (updates static + bundle).
ICON_TMP="$(mktemp /tmp/np-icon-cropped.XXXXXX.png)"
cleanup() { rm -f "$ICON_TMP"; }
trap cleanup EXIT
if [[ -n "$CROP_PY_BIN" ]] && "$CROP_PY_BIN" "$CROP_PY" "$ICON_SRC" "$ICON_TMP"; then
  cp "$ICON_TMP" "$ICON_SRC"
else
  echo "Note: icon crop skipped (need Pillow + numpy on a system python3). Raw icon kept." >&2
fi

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

cp "$ICON_SRC" "$APP_DIR/Contents/Resources/AppIcon.png"

START_SH="$APP_DIR/Contents/MacOS/start_server.sh"
# Portable launcher — no absolute paths embedded. Layout assumption:
#   $PROJECT_ROOT/narRater.app/Contents/MacOS/start_server.sh
# so PROJECT_ROOT is three levels above this file at run time.
cat > "$START_SH" <<'EOF'
#!/bin/bash
# narRater — server starter (runs inside Terminal).
# Resolves both PROJECT_ROOT and the Python interpreter at run time so this bundle
# can be copied between machines without rebuilding.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." 2>/dev/null && pwd || true)"

cd "$PROJECT_ROOT/server" 2>/dev/null || {
  osascript -e 'display dialog "Cannot find the server/ folder.\n\nKeep \"narRater.app\" next to the project'\''s server/, static/, templates/ folders, or rebuild it with:\n\n  bash packaging/macos/build_app_bundle.sh" buttons {"OK"} default button "OK" with icon stop'
  exit 1
}
export PYTHONUNBUFFERED=1
if [[ ! -f web-interface.py ]]; then
  osascript -e 'display dialog "web-interface.py not found in server/. Check project layout." buttons {"OK"} default button "OK" with icon stop'
  exit 1
fi

# Prefer project .venv (created by narRaters_installer); else any python3 with Flask.
PY=""
if [[ -x "$PROJECT_ROOT/.venv/bin/python3" ]]; then
  PY="$PROJECT_ROOT/.venv/bin/python3"
elif [[ -f "$PROJECT_ROOT/scripts/project_python.sh" ]]; then
  PY="$(bash "$PROJECT_ROOT/scripts/project_python.sh" "$PROJECT_ROOT" 2>/dev/null || true)"
fi
if [[ -n "$PY" ]] && ! "$PY" -c "import flask" 2>/dev/null; then
  PY=""
fi
if [[ -z "$PY" ]]; then
  for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 2>/dev/null)" /usr/bin/python3; do
    [[ -z "$p" || ! -x "$p" ]] && continue
    if "$p" -c "import flask" 2>/dev/null; then
      PY="$p"
      break
    fi
  done
fi
if [[ -z "$PY" ]]; then
  if [[ -f "$PROJECT_ROOT/scripts/setup_project_venv.sh" ]]; then
    echo "First launch: creating .venv and installing dependencies…"
    if ! bash "$PROJECT_ROOT/scripts/setup_project_venv.sh" "$PROJECT_ROOT"; then
      osascript -e 'display dialog "Could not install dependencies.\n\nDouble-click narRaters_installer.command once, or run:\n\n  bash scripts/setup_project_venv.sh ." buttons {"OK"} default button "OK" with icon stop'
      exit 1
    fi
    PY="$PROJECT_ROOT/.venv/bin/python3"
  fi
fi
if [[ -z "$PY" ]] || ! "$PY" -c "import flask" 2>/dev/null; then
  osascript -e 'display dialog "Flask was not found.\n\nDouble-click narRaters_installer.command (or narRaters_installer.app) once to set up, then relaunch narRater.app." buttons {"OK"} default button "OK" with icon stop'
  exit 1
fi

echo "Project: $PROJECT_ROOT"
echo "Python:  $PY"
echo "Starting http://127.0.0.1:5000 (Ctrl+C to stop)"
exec "$PY" web-interface.py
EOF
chmod +x "$START_SH"

LAUNCHER="$APP_DIR/Contents/MacOS/narRater"
cat > "$LAUNCHER" <<'LAUNCHER_EOF'
#!/bin/bash
# GUI entry: open Terminal with start_server.sh (AppleScript quoting-safe).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

START_SH="$(cd "$(dirname "$0")" && pwd)/start_server.sh"

if ! command -v python3 >/dev/null 2>&1 && [[ ! -x /usr/bin/python3 ]]; then
  osascript -e 'display dialog "Python 3 was not found. Install Python 3 or add it to PATH." buttons {"OK"} default button "OK" with icon stop'
  exit 1
fi

osascript <<OSA
tell application "Terminal"
    activate
    do script "bash " & quoted form of "$START_SH"
end tell
OSA

# Wait for Flask (imports can take several seconds)
for _ in $(seq 1 90); do
  if curl -sf --connect-timeout 1 "http://127.0.0.1:5000/pipeline-config" >/dev/null 2>&1 \
     || curl -sf --connect-timeout 1 "http://127.0.0.1:5000/" >/dev/null 2>&1; then
    open "http://127.0.0.1:5000/pipeline-config" 2>/dev/null || true
    exit 0
  fi
  sleep 0.5
done

osascript -e 'display dialog "The browser opened before the server was ready, or the server failed to start.

Check the Terminal window for errors. If this is the first run, double-click narRaters_installer.command once.

Then refresh or visit http://127.0.0.1:5000/pipeline-config" buttons {"OK"} default button "OK" with icon caution'
open "http://127.0.0.1:5000/pipeline-config" 2>/dev/null || true
LAUNCHER_EOF
chmod +x "$LAUNCHER"

PLIST="$APP_DIR/Contents/Info.plist"
cat > "$PLIST" <<EOF
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
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
EOF

echo "Built: $APP_DIR"
echo "Portable bundle — no absolute paths embedded."
echo "Keep the .app as a sibling of server/ and static/. Double-click to launch."
echo "If Safari opens before the server is ready, wait for Terminal to finish starting Python, then refresh."
