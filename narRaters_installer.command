#!/bin/bash
# Double-click in Finder: installs narRaters (pip install -e .) for this folder.
# If nothing happens: right-click → Open (Gatekeeper), or use narRaters_installer.app from:
#   bash packaging/macos/build_narRaters_installer_app.sh

cd "$(dirname "$0")" || exit 1
PROJECT_ROOT="$(pwd)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

if ! command -v python3 &>/dev/null; then
  osascript -e 'display dialog "Python 3 was not found. Install from https://www.python.org/downloads/ or Homebrew, then try again." buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
  exit 1
fi

BUTTON=$(osascript -e 'button returned of (display dialog "This installs narRaters and its Python dependencies for your user account (one-time; internet required).

Click Install to continue, or Cancel." buttons {"Cancel", "Install"} default button "Install" with title "narRaters setup")' 2>/dev/null) || true
if [[ "$BUTTON" != "Install" ]]; then
  exit 0
fi

LOG="$(mktemp /tmp/narraters-install.XXXXXX.log)"

if python3 -m pip install -e "$PROJECT_ROOT" >"$LOG" 2>&1; then
  rm -f "$LOG"
  osascript -e 'display dialog "Setup finished.

Open narRaters:
• Double-click narRaters_installer.app (build with packaging/macos/build_narRaters_installer_app.sh), or
• Double-click server/START_HERE.command
• Or: narraters serve in Terminal" buttons {"OK"} default button "OK" with title "narRaters"' 2>/dev/null || true
  exit 0
fi

osascript -e 'display dialog "Install failed. A log will open in TextEdit with details." buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
open -a TextEdit "$LOG" 2>/dev/null || true
exit 1
