#!/usr/bin/env bash
# Build a standard macOS disk image for distribution (repo root — easy to find on GitHub):
#   narRaters-macos-installer.dmg
#
# Volume layout (Finder-friendly):
#   narRaters_installer.app  — double-click to run pip install -e . once
#   narRaters_source/        — full project tree (run the app from this volume or copy out)
#   Applications             — alias to /Applications (optional: drag the .app here)
#   INSTALL-macOS.txt        — short steps for first-time setup
#
# Run from any directory; resolves project root from this script's location.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DMG="$PROJECT_ROOT/narRaters-macos-installer.dmg"
VOLNAME="narRatersInstaller"

VERSION="$(sed -n 's/^version = "\([^"]*\)".*/\1/p' "$PROJECT_ROOT/pyproject.toml" | head -1)"
if [[ -z "$VERSION" ]]; then
  VERSION="0.0.0"
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/narRaters-dmg-stage.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "Staging DMG contents in $STAGE …"

mkdir -p "$STAGE/narRaters_source"
rsync -a \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='env/' \
  --exclude='ENV/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='narRaters_installer.dmg' \
  --exclude='narRaters-macos-installer.dmg' \
  --exclude='narRaters_installer.app/' \
  --exclude='narRater.app/' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='.DS_Store' \
  "$PROJECT_ROOT/" "$STAGE/narRaters_source/"

bash "$SCRIPT_DIR/build_narRaters_installer_app.sh"
ditto "$PROJECT_ROOT/narRaters_installer.app" "$STAGE/narRaters_installer.app"

# Conventional DMG affordances (same layout many macOS apps use).
ln -sf /Applications "$STAGE/Applications"

cat >"$STAGE/INSTALL-macOS.txt" <<EOF
narRaters — macOS installer disk  (package version ${VERSION})

Python 3.10+ must be installed separately from https://www.python.org/downloads/

Steps:
  1. Copy the folder "narRaters_source" to your Mac (Documents or Desktop is fine).
  2. Copy "narRaters_installer.app" to the same parent folder as "narRaters_source"
     (so the .app sits next to that folder, not inside it).
  3. Double-click narRaters_installer.app once (creates .venv/ and installs deps).
  4. Open narRaters_source/server/START_HERE.command, or run:
       .venv/bin/narraters serve
     (from inside narRaters_source/)

Optional: drag narRaters_installer.app onto the Applications alias if you want
the installer in /Applications — still keep narRaters_source somewhere permanent
beside it (same parent directory as the .app).

This disk image was built from the narRaters repository.
EOF

rm -f "$OUT_DMG"

# Detach any stray mount with same name (best-effort)
if hdiutil info 2>/dev/null | grep -q "$VOLNAME"; then
  hdiutil detach "/Volumes/${VOLNAME}" -force 2>/dev/null || true
fi

echo "Creating compressed disk image → $OUT_DMG"
hdiutil create \
  -volname "$VOLNAME" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$OUT_DMG"

echo "Done: $OUT_DMG"
echo "Ship this file from the repo root (commit for in-repo download, or attach to a GitHub Release)."
