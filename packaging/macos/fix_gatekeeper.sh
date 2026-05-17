#!/usr/bin/env bash
# Fix double-click blocked for narRater.app (no reinstall).
set -euo pipefail

DEST_APP="${1:-}"
if [[ -z "$DEST_APP" ]]; then
  for candidate in \
    "$HOME/narRaters/narRater.app" \
    "/Applications/narRater.app"; do
    if [[ -d "$candidate" ]]; then
      DEST_APP="$candidate"
      break
    fi
  done
fi

if [[ ! -d "$DEST_APP" ]]; then
  echo "ERROR: narRater.app not found. Pass a path, e.g.:" >&2
  echo "  bash fix_gatekeeper.sh \"\$HOME/narRaters/narRater.app\"" >&2
  exit 1
fi

echo "Removing quarantine from $DEST_APP …"
xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$DEST_APP" 2>/dev/null || true
fi

echo "Done. Try double-clicking narRater again."
echo "If still blocked: System Settings → Privacy & Security → Open Anyway."
