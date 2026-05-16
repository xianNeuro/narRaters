#!/usr/bin/env bash
# Create/update .venv in the project root and pip install -e .
# Avoids PEP 668 "externally managed environment" errors on Homebrew macOS Python.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

PROJECT_ROOT="${1:-}"
if [[ -z "$PROJECT_ROOT" ]]; then
  echo "Usage: bash scripts/setup_project_venv.sh /path/to/narRaters" >&2
  exit 2
fi
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
  echo "Not a narRaters project (missing pyproject.toml): $PROJECT_ROOT" >&2
  exit 2
fi

if ! command -v python3 &>/dev/null; then
  echo "Python 3 not found on PATH." >&2
  exit 1
fi

VENV="$PROJECT_ROOT/.venv"
if [[ ! -x "$VENV/bin/python3" ]]; then
  echo "Creating virtual environment: $VENV"
  python3 -m venv "$VENV"
fi

PY="$VENV/bin/python3"
echo "Using: $PY ($("$PY" --version 2>&1))"
"$PY" -m pip install -U pip wheel
"$PY" -m pip install -e "$PROJECT_ROOT"
echo ""
echo "Install complete. Activate with:  source .venv/bin/activate"
echo "Or run directly:  .venv/bin/narraters serve"
