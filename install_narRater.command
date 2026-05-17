#!/bin/bash
# Double-click this file in Finder to install and launch narRaters on macOS.
#
# Where to double-click:
#   - After `git clone` of the repo, OR
#   - After unzipping the GitHub source ZIP (Code → Download ZIP).
#
# First time, macOS may show: "Apple cannot verify ... is free from malware".
#   - Control-click (or right-click) this file → Open → Open. You only need
#     to do this once per download.
#   - On a clean clone with `git`, no warning should appear.

cd "$(dirname "$0")"

# Strip download quarantine on the project folder so future double-clicks work.
xattr -dr com.apple.quarantine "$(pwd)" 2>/dev/null || true

clear
echo "==========================================="
echo "  narRaters installer (macOS)"
echo "==========================================="
echo "Project folder: $(pwd)"
echo ""

bash ./install.sh
status=$?

if [[ $status -ne 0 ]]; then
  echo ""
  echo "Installation did not complete. Read the errors above."
  echo "Common fix: install Python 3.10+ from https://www.python.org/downloads/"
  echo ""
  read -p "Press Enter to close this window ..."
fi
