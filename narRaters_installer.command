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

BUTTON=$(osascript -e 'button returned of (display dialog "This creates a .venv/ folder here and installs narRaters into it (one-time; internet required). Works with Homebrew Python on macOS.

Click Install to continue, or Cancel." buttons {"Cancel", "Install"} default button "Install" with title "narRaters setup")' 2>/dev/null) || true
if [[ "$BUTTON" != "Install" ]]; then
  exit 0
fi

LOG="$(mktemp /tmp/narraters-install.XXXXXX.log)"

if bash "$PROJECT_ROOT/scripts/setup_project_venv.sh" "$PROJECT_ROOT" >"$LOG" 2>&1; then
  rm -f "$LOG"
  osascript -e 'display dialog "Setup finished.

A virtual environment was created at .venv/ in this folder.

Open narRaters:
• Double-click server/START_HERE.command
• Or in Terminal:  .venv/bin/narraters serve" buttons {"OK"} default button "OK" with title "narRaters"' 2>/dev/null || true
  exit 0
fi

osascript -e 'display dialog "Install failed. A log will open in TextEdit with details." buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
open -a TextEdit "$LOG" 2>/dev/null || true
exit 1
