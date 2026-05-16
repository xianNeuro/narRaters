#!/usr/bin/env bash
# Build narRater.app at the project root (same bundle used in the macOS DMG).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
exec bash "$SCRIPT_DIR/build_standalone_app.sh" "$PROJECT_ROOT/narRater.app"
