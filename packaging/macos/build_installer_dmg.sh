#!/usr/bin/env bash
# Build narRaters-macos-installer.dmg — standard layout: drag narRater.app to Applications.
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

ln -sf /Applications "$STAGE/Applications"

cat >"$STAGE/INSTALL-macOS.txt" <<EOF
narRaters ${VERSION} — macOS install

Python 3.10+ must be installed from https://www.python.org/downloads/

Install:
  1. Drag narRater.app onto the Applications folder (or your Applications alias).
  2. Open narRater from Applications (first time: right-click → Open if Gatekeeper asks).
  3. On first launch, Terminal opens while dependencies install; your browser opens when ready.

Your data and settings are stored under:
  ~/Library/Application Support/narRaters/

To update: replace narRater.app in Applications with a newer copy from a fresh disk image.
EOF

rm -f "$OUT_DMG"
if hdiutil info 2>/dev/null | grep -q "$VOLNAME"; then
  hdiutil detach "/Volumes/${VOLNAME}" -force 2>/dev/null || true
fi

echo "Creating disk image → $OUT_DMG"
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO "$OUT_DMG"
echo "Done: $OUT_DMG"
