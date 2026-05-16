#!/usr/bin/env bash
# Show post-install dialog; optional immediate launch of narRater.app.
set -euo pipefail

PROJECT_ROOT="${1:-}"
APP="${PROJECT_ROOT}/narRater.app"

if [[ ! -d "$APP" ]]; then
  osascript -e 'display dialog "Setup finished, but narRater.app was not found. Run: bash packaging/macos/build_app_bundle.sh" buttons {"OK"} default button "OK" with icon caution' 2>/dev/null || true
  exit 0
fi

BUTTON=$(osascript -e 'button returned of (display dialog "Setup finished.

A virtual environment (.venv/) and narRater.app were created in your project folder.

To open narRaters later, double-click narRater.app (same as after a manual install)." buttons {"Later", "Open narRater"} default button "Open narRater" with title "narRaters")' 2>/dev/null) || BUTTON="Later"

if [[ "$BUTTON" == "Open narRater" ]]; then
  open "$APP"
fi
