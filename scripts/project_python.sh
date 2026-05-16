#!/usr/bin/env bash
# Print the Python interpreter to use for this project (.venv preferred).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

PROJECT_ROOT="${1:-}"
if [[ -z "$PROJECT_ROOT" ]]; then
  echo "Usage: bash scripts/project_python.sh /path/to/narRaters" >&2
  exit 2
fi
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

if [[ -x "$PROJECT_ROOT/.venv/bin/python3" ]]; then
  echo "$PROJECT_ROOT/.venv/bin/python3"
  exit 0
fi

for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 2>/dev/null)" /usr/bin/python3; do
  [[ -z "$p" || ! -x "$p" ]] && continue
  echo "$p"
  exit 0
done

echo "Python 3 not found" >&2
exit 1
