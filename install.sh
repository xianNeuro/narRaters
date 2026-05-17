#!/usr/bin/env bash
# narRaters installer — Mac / Linux.
#
# Run from the project root (after `git clone` or unzipping the source):
#   bash install.sh
#
# What it does:
#   - Confirms Python 3.10+ is available
#   - Creates .venv/ in the project root
#   - Installs narRaters (editable) and required deps
#   - Starts the web UI and opens your browser
#
# Re-run any time. Rerunning is safe and fast (skips already-installed deps).

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
  echo "ERROR: pyproject.toml not found in $PROJECT_ROOT" >&2
  echo "Run this script from the narRaters project folder." >&2
  exit 1
fi

VENV="$PROJECT_ROOT/.venv"

# Find a Python ≥ 3.10. Prefer python3.13 → 3.10, then python3, then python.
pick_python() {
  local candidate
  for candidate in \
      python3.13 python3.12 python3.11 python3.10 \
      /opt/homebrew/bin/python3 /usr/local/bin/python3 \
      python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

if ! PY="$(pick_python)"; then
  cat >&2 <<'EOF'

================================================================
ERROR: Python 3.10 or newer is required.
================================================================

Install from https://www.python.org/downloads/ (download the
universal installer for macOS), then re-run this script.

If you already installed Python from python.org, restart Terminal
and run install.sh again — the new "python3" needs a fresh shell
to be found on PATH.

EOF
  exit 1
fi

echo "Using Python: $PY ($("$PY" --version 2>&1))"

if [[ ! -x "$VENV/bin/python3" ]]; then
  echo "Creating .venv in $PROJECT_ROOT"
  "$PY" -m venv "$VENV"
fi

VPY="$VENV/bin/python3"
echo "Upgrading pip + wheel ..."
"$VPY" -m pip install --upgrade pip wheel >/dev/null

if "$VPY" -c "import flask, narraters" 2>/dev/null; then
  echo "narRaters already installed in .venv"
else
  echo "Installing narRaters into .venv (one-time, ~1-2 minutes) ..."
  "$VPY" -m pip install -e "$PROJECT_ROOT"
fi

echo ""
echo "================================================================"
echo "Setup complete. Starting narRaters ..."
echo "================================================================"
echo ""

PORT=5000
while lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; do
  PORT=$((PORT + 1))
  if [[ $PORT -gt 5010 ]]; then
    echo "WARNING: Could not find a free port between 5000 and 5010. Stop other servers and retry." >&2
    exit 1
  fi
done

URL="http://127.0.0.1:${PORT}/pipeline-config"
echo "Web UI:  $URL"
echo "(Press Ctrl+C in this Terminal window to stop the server.)"
echo ""

(
  sleep 2
  if command -v open >/dev/null 2>&1; then
    open "$URL" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" 2>/dev/null || true
  fi
) &

cd "$PROJECT_ROOT/server"
export NARRATERS_PORT="$PORT"
exec "$VPY" web-interface.py
