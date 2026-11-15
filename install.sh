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

# This branch also needs flask_login (login) and waitress (--production); an
# older .venv from the main app may lack them, so check for those too.
if "$VPY" -c "import flask, flask_login, waitress, narraters" 2>/dev/null; then
  echo "narRaters already installed in .venv"
else
  echo "Installing narRaters into .venv (one-time, ~1-2 minutes) ..."
  "$VPY" -m pip install -e "$PROJECT_ROOT[deploy]"
fi

echo ""
echo "================================================================"
echo "Setup complete. Starting narRaters ..."
echo "================================================================"
echo ""

# ---------------------------------------------------------------------------
# segcausal branch: open the RATER TASK, not the pipeline app.
# (On main, this script opens /pipeline-config. This branch exists only for the
# hosted story-segmentation + causal-rating task, so the launchers start
# `narraters serve --task segment-causal`.)
#   stories   $PROJECT_ROOT/task_segcausal/unrated/<story>/  (<story>.txt + <story>_events*.xlsx)
#   results   $PROJECT_ROOT/task_segcausal/rated/<rater>/
#   state     ~/.narraters-segcausal  (never ~/.narraters, which the main app uses)
#   port      first free from 5001    (5000 is the main app's default)
# ---------------------------------------------------------------------------
TASK_DIR="$PROJECT_ROOT/task_segcausal"
mkdir -p "$TASK_DIR/unrated" "$TASK_DIR/rated"
if [[ -z "$(find "$TASK_DIR/unrated" -mindepth 2 -name '*_events*.xlsx' -print -quit)" ]]; then
  # No stories yet: add the bundled example so the task list is not empty.
  if [[ -f "$PROJECT_ROOT/data/2_story_transcript/the_siren.txt" && -f "$PROJECT_ROOT/data/3_story_events/the_siren_events.xlsx" ]]; then
    mkdir -p "$TASK_DIR/unrated/the_siren"
    cp "$PROJECT_ROOT/data/2_story_transcript/the_siren.txt" "$TASK_DIR/unrated/the_siren/"
    cp "$PROJECT_ROOT/data/3_story_events/the_siren_events.xlsx" "$TASK_DIR/unrated/the_siren/"
    echo "Added the example story 'the_siren' to $TASK_DIR/unrated/ (put your own stories there)."
  fi
fi

PORT=5001
while lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; do
  PORT=$((PORT + 1))
  if [[ $PORT -gt 5020 ]]; then
    echo "WARNING: Could not find a free port between 5001 and 5020. Stop other servers and retry." >&2
    exit 1
  fi
done

URL="http://127.0.0.1:${PORT}/tasks"
echo "Rater task (story segmentation + causal rating):  $URL"
echo "Stories: $TASK_DIR/unrated/    Results: $TASK_DIR/rated/"
echo "No login in this local mode (rater = local_rater). For hosting with login see HOSTING_SEGCAUSAL.md."
echo "(Press Ctrl+C in this Terminal window to stop the server.)"
echo ""

[[ -n "${NO_OPEN:-}" ]] || (
  sleep 3
  if command -v open >/dev/null 2>&1; then
    open "$URL" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" 2>/dev/null || true
  fi
) &

export NARRATERS_TASK_DIR="$TASK_DIR"
exec "$VENV/bin/narraters" serve --task segment-causal --no-browser --port "$PORT"
