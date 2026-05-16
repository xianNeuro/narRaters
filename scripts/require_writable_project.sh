#!/usr/bin/env bash
# Exit 1 with a macOS dialog if PROJECT_ROOT is not writable (e.g. still on a read-only DMG).
set -euo pipefail

PROJECT_ROOT="${1:-}"
if [[ -z "$PROJECT_ROOT" ]]; then
  exit 2
fi

PROBE="$PROJECT_ROOT/.narRaters_write_probe"
if touch "$PROBE" 2>/dev/null; then
  rm -f "$PROBE"
  exit 0
fi

osascript <<'OSA' 2>/dev/null || true
display dialog "This folder is read-only (often because it is still on the installer disk image).

Copy the entire \"narRaters_source\" folder to Documents or Desktop first, then double-click narRaters_installer.app inside the copied folder." buttons {"OK"} default button "OK" with icon stop
OSA
echo "ERROR: Project folder is not writable: $PROJECT_ROOT" >&2
exit 1
