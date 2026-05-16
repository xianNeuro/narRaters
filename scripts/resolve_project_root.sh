#!/usr/bin/env bash
# Print narRaters project root when given the path to narRaters_installer.app (or its MacOS dir).
set -euo pipefail

START="${1:-}"
if [[ -z "$START" ]]; then
  echo "Usage: bash scripts/resolve_project_root.sh /path/to/narRaters_installer.app" >&2
  exit 2
fi

if [[ -d "$START/Contents/MacOS" ]]; then
  MACOS_DIR="$(cd "$START/Contents/MacOS" && pwd)"
else
  MACOS_DIR="$(cd "$START" && pwd)"
fi
CONTENTS="$(cd "$MACOS_DIR/.." && pwd)"
APP_BUNDLE="$(cd "$CONTENTS/.." && pwd)"
PARENT="$(cd "$APP_BUNDLE/.." && pwd)"

if [[ -f "$PARENT/pyproject.toml" && -f "$PARENT/server/web-interface.py" ]]; then
  echo "$PARENT"
  exit 0
fi
if [[ -f "$PARENT/narRaters_source/pyproject.toml" && -f "$PARENT/narRaters_source/server/web-interface.py" ]]; then
  echo "$PARENT/narRaters_source"
  exit 0
fi

echo "Could not resolve narRaters project root from: $START" >&2
exit 1
