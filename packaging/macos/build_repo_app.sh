#!/usr/bin/env bash
# Build a minimal narRater.app at the repo root.
#
# This bundle is intentionally tiny: it does NOT contain the project files.
# It is just a clickable wrapper around `install.sh` in the repo root, so a
# user who already has the project folder (via `git clone` or unzip) can
# double-click narRater.app instead of running Terminal commands.
#
# Re-run this whenever you change the launcher script or the icon.
#
# Output:  <repo>/narRater.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP="$REPO_ROOT/narRater.app"
ICON_SRC="$REPO_ROOT/static/app-icon.png"

VERSION="$(sed -n 's/^version = "\([^"]*\)".*/\1/p' "$REPO_ROOT/pyproject.toml" | head -1)"
VERSION="${VERSION:-0.0.0}"

echo "Building $APP (version $VERSION)"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"

# --- Info.plist -------------------------------------------------------------
cat >"$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>narRater</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>org.narraters.launcher</string>
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
  <key>LSBackgroundOnly</key>
  <false/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

# --- Launcher script --------------------------------------------------------
# Resolves the repo root: first by walking up from narRater.app (works after
# git clone). If the app was launched via macOS App Translocation (common for
# ZIP downloads of unsigned bundles), $0 lives in /private/var/folders/.../
# AppTranslocation/... instead of next to install.sh — so we also search the
# user's common project locations as a fallback.
cat >"$APP/Contents/MacOS/narRater" <<'LAUNCHER_EOF'
#!/bin/bash
set -e

is_narraters_root() {
  [[ -d "$1" && -f "$1/install.sh" && -f "$1/pyproject.toml" ]]
}

# 1. Try the .app's actual parent directory (works after `git clone`).
APP_BUNDLE="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_DIR="$(cd "$APP_BUNDLE/.." && pwd)"

REPO_ROOT=""
if is_narraters_root "$PARENT_DIR"; then
  REPO_ROOT="$PARENT_DIR"
fi

# 2. If launched from a translocated copy, $PARENT_DIR is a sandbox path.
#    Search the most common places people unzip / clone projects to.
if [[ -z "$REPO_ROOT" ]]; then
  for candidate in \
      "$HOME/narRaters" \
      "$HOME/narRaters-main" \
      "$HOME/Downloads/narRaters" \
      "$HOME/Downloads/narRaters-main" \
      "$HOME/Desktop/narRaters" \
      "$HOME/Desktop/narRaters-main" \
      "$HOME/Documents/narRaters" \
      "$HOME/Documents/narRaters-main"; do
    if is_narraters_root "$candidate"; then
      REPO_ROOT="$candidate"
      break
    fi
  done
fi

# Also accept versioned release folders (e.g. narRaters-0.3.5 from the tag ZIP).
if [[ -z "$REPO_ROOT" ]]; then
  for base in "$HOME" "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents"; do
    for candidate in "$base"/narRaters-[0-9]*; do
      [[ -d "$candidate" ]] || continue
      if is_narraters_root "$candidate"; then
        REPO_ROOT="$candidate"
        break 2
      fi
    done
  done
fi

# 3. Still not found — show a helpful dialog with copy-paste commands.
if [[ -z "$REPO_ROOT" ]]; then
  /usr/bin/osascript <<'APPLESCRIPT'
display dialog "narRater couldn't find the narRaters project folder.

This usually means one of these is true:

  1. macOS App Translocation: you opened narRater.app from a downloaded
     ZIP/DMG, so macOS is running it from a temporary copy and can't
     see the real project files next to it.

  2. You moved narRater.app away from its project folder.

Easiest fix — open Terminal and paste ONE of these (depending on
where the unzipped folder is):

    cd ~/Downloads/narRaters-0.3.5 && bash install.sh
    cd ~/Downloads/narRaters-main && bash install.sh
    cd ~/Desktop/narRaters-main && bash install.sh
    cd ~/narRaters && bash install.sh

Or remove macOS quarantine on the unzipped folder, then try again:

    xattr -dr com.apple.quarantine ~/Downloads/narRaters-main

The most reliable install path is the Terminal one-liner from the
README — it skips Gatekeeper entirely." buttons {"OK"} default button "OK" with icon stop
APPLESCRIPT
  exit 1
fi

# Strip download quarantine on the project folder so future clicks work.
/usr/bin/xattr -dr com.apple.quarantine "$REPO_ROOT" 2>/dev/null || true

# Open Terminal and run install.sh in the project folder.
/usr/bin/osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "clear && cd " & quoted form of "$REPO_ROOT" & " && bash ./install.sh"
end tell
APPLESCRIPT
LAUNCHER_EOF
chmod +x "$APP/Contents/MacOS/narRater"

# --- Icon -------------------------------------------------------------------
if [[ -f "$ICON_SRC" ]]; then
  ICONSET="$(mktemp -d)/AppIcon.iconset"
  mkdir -p "$ICONSET"
  for size in 16 32 64 128 256 512; do
    /usr/bin/sips -z "$size" "$size" "$ICON_SRC" \
      --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    /usr/bin/sips -z "$double" "$double" "$ICON_SRC" \
      --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  /usr/bin/iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
  rm -rf "$(dirname "$ICONSET")"
fi

# --- Ad-hoc sign so Gatekeeper sees a valid signature (still not notarized) -
# Use /usr/bin/codesign explicitly; some PATH overrides shadow `codesign`.
if [[ -x /usr/bin/codesign ]]; then
  /usr/bin/codesign --force --deep --sign - "$APP" 2>/dev/null || true
fi

# --- Strip quarantine on this freshly built bundle --------------------------
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

echo "Built: $APP"
echo "Bundle size: $(du -sh "$APP" | awk '{print $1}')"
