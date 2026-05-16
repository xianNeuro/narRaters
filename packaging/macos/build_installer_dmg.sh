#!/usr/bin/env bash
# Build narRaters_installer.dmg containing narRaters_installer.app + narRaters_source/ (full tree).
# Run from any directory; resolves project root from this script's location.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
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
  --exclude='narRaters_installer.app/' \
  --exclude='narRater.app/' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='.DS_Store' \
  "$PROJECT_ROOT/" "$STAGE/narRaters_source/"

bash "$SCRIPT_DIR/build_narRaters_installer_app.sh"
ditto "$PROJECT_ROOT/narRaters_installer.app" "$STAGE/narRaters_installer.app"

OUT_DMG="$PROJECT_ROOT/narRaters_installer.dmg"
rm -f "$OUT_DMG"

# Detach any stray mount with same name (best-effort)
if hdiutil info 2>/dev/null | grep -q "narRaters_installer"; then
  hdiutil detach "/Volumes/narRaters_installer" -force 2>/dev/null || true
fi

echo "Creating compressed disk image …"
hdiutil create \
  -volname "narRaters_installer" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$OUT_DMG"

echo "Done: $OUT_DMG"
echo "Distribute the DMG; recipients open it, double-click narRaters_installer.app, then use START_HERE or narraters serve inside narRaters_source/."
