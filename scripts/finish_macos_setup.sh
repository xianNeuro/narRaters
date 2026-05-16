#!/usr/bin/env bash
# One-time macOS setup: .venv + narRater.app launcher (same double-click entry as manual build).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

PROJECT_ROOT="${1:-}"
LAUNCH="${2:-}"

if [[ -z "$PROJECT_ROOT" ]]; then
  echo "Usage: bash scripts/finish_macos_setup.sh /path/to/narRaters [launch]" >&2
  exit 2
fi
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

bash "$PROJECT_ROOT/scripts/require_writable_project.sh" "$PROJECT_ROOT"

bash "$PROJECT_ROOT/scripts/setup_project_venv.sh" "$PROJECT_ROOT"

BUILD="$PROJECT_ROOT/packaging/macos/build_app_bundle.sh"
if [[ ! -f "$BUILD" ]]; then
  echo "Missing $BUILD" >&2
  exit 1
fi
bash "$BUILD"

APP="$PROJECT_ROOT/narRater.app"
if [[ ! -d "$APP" ]]; then
  echo "narRater.app was not created at $APP" >&2
  exit 1
fi

echo ""
echo "narRater.app is ready: $APP"
echo "Double-click narRater.app anytime to start the web UI."

if [[ "$LAUNCH" == "launch" ]]; then
  open "$APP"
fi
