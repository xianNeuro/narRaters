#!/usr/bin/env bash
# Copy narRater.app to a local folder (default ~/narRaters) and clear Gatekeeper quarantine.
# Run from the mounted DMG, e.g.:
#   cd /Volumes/narRaters && bash install_narRater.sh
#
# Optional:
#   bash install_narRater.sh /Applications          # install to /Applications/narRater.app
#   bash install_narRater.sh "$HOME/Desktop/narRaters"
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_APP="$SCRIPT_DIR/narRater.app"

resolve_dest() {
  local arg="${1:-}"
  case "$arg" in
    ""|--local)
      echo "$HOME/narRaters/narRater.app"
      ;;
    /Applications|/Applications/narRater.app)
      echo "/Applications/narRater.app"
      ;;
    *)
      if [[ "$arg" == *.app ]]; then
        echo "$arg"
      else
        echo "${arg%/}/narRater.app"
      fi
      ;;
  esac
}

DEST_APP="$(resolve_dest "${1:-}")"
DEST_DIR="$(dirname "$DEST_APP")"

if [[ ! -d "$SRC_APP" ]]; then
  echo "ERROR: narRater.app not found next to this script ($SCRIPT_DIR)" >&2
  exit 1
fi

echo "Clearing download quarantine on the disk image (if present)…"
xattr -dr com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true

mkdir -p "$DEST_DIR"
echo "Installing to $DEST_APP …"
if [[ -d "$DEST_APP" ]]; then
  rm -rf "$DEST_APP"
fi
ditto "$SRC_APP" "$DEST_APP"

echo "Clearing quarantine on the installed app…"
xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$DEST_APP" 2>/dev/null || true
fi

echo "Launching narRater…"
open "$DEST_APP"

echo ""
echo "Done. narRater is installed at:"
echo "  $DEST_APP"
echo ""
echo "If macOS still blocks the app:"
echo "  System Settings → Privacy & Security → Open Anyway (after one double-click attempt)"
echo "  or run:  xattr -dr com.apple.quarantine \"$DEST_APP\""
