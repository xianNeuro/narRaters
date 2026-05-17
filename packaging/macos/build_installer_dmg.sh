#!/usr/bin/env bash
# Build narRaters-macos-installer.dmg — portable layout: run or copy narRater.app locally (no drag to Applications).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DMG="$PROJECT_ROOT/narRaters-macos-installer.dmg"
VOLNAME="narRaters"
VERSION="$(sed -n 's/^version = "\([^"]*\)".*/\1/p' "$PROJECT_ROOT/pyproject.toml" | head -1)"
VERSION="${VERSION:-0.0.0}"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/narRaters-dmg-stage.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "Building standalone narRater.app …"
bash "$SCRIPT_DIR/build_standalone_app.sh" "$STAGE/narRater.app"

cp "$SCRIPT_DIR/install_narRater.sh" "$STAGE/install_narRater.sh"
chmod +x "$STAGE/install_narRater.sh"

cat >"$STAGE/Open narRater.command" <<'CMDEOF'
#!/bin/bash
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine "$(dirname "$0")" 2>/dev/null || true
open "$(dirname "$0")/narRater.app"
CMDEOF
chmod +x "$STAGE/Open narRater.command"

cat >"$STAGE/Install narRater.command" <<'CMDEOF'
#!/bin/bash
cd "$(dirname "$0")"
exec bash ./install_narRater.sh
CMDEOF
chmod +x "$STAGE/Install narRater.command"

cat >"$STAGE/INSTALL-macOS.txt" <<EOF
narRaters ${VERSION} — macOS

Python 3.10+ must be installed from https://www.python.org/downloads/

QUICK START (no drag to Applications):
  1. Double-click "Open narRater.command" on this disk image
     (if blocked: Control-click → Open once).
  2. Or double-click "Install narRater.command" to copy narRater.app to:
       ~/narRaters/narRater.app
     then launch it (recommended for everyday use).

You can also double-click narRater.app on this disk image. First launch may need
Control-click → Open once because the download is quarantined.

Terminal (same folder as this file):
  cd /Volumes/narRaters && bash install_narRater.sh
  # optional: bash install_narRater.sh /Applications

Using the app:
  • Terminal opens on launch; first run installs Python packages (several minutes).
  • Open the URL shown in Terminal (http://127.0.0.1:… — use 127.0.0.1, not localhost).
  • Blank page? Turn off AirPlay Receiver (System Settings → General → AirDrop & Handoff).

Data and runtime: ~/Library/Application Support/narRaters/
Update: run Install narRater.command from a new disk image, or replace ~/narRaters/narRater.app
EOF

rm -f "$OUT_DMG"
if hdiutil info 2>/dev/null | grep -q "$VOLNAME"; then
  hdiutil detach "/Volumes/${VOLNAME}" -force 2>/dev/null || true
fi

echo "Creating disk image → $OUT_DMG"
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO "$OUT_DMG"
echo "Done: $OUT_DMG"
