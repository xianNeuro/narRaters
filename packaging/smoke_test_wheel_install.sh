#!/usr/bin/env bash
# PyPI-style smoke test: clean venv, build wheel, install with --no-cache-dir, run CLI steps 2–6.
#
# Expects this repo layout (siblings under the same parent directory):
#   narRaters/          ← this script lives in narRaters/packaging/
#   software/data/      ← story + recall inputs (numbered subfolders)
#   test/               ← venv, dist, and work/ outputs are created here
#
# Usage:
#   bash packaging/smoke_test_wheel_install.sh
set -euo pipefail

PKG="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$(cd "$(dirname "$0")/../../software/data" && pwd)"
ROOT="$(cd "$(dirname "$0")/../../test" && pwd)"
VENV="$ROOT/venv"
DIST="$ROOT/dist"
WORK="$ROOT/work"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo "== narRaters wheel smoke test =="
echo "Package: $PKG"
echo "Data:    $DATA"
echo "Scratch: $ROOT (venv + dist + work)"
echo

if [[ ! -d "$PKG/src/narraters" ]]; then
  echo "Expected narRaters package at: $PKG" >&2
  exit 1
fi
if [[ ! -d "$DATA/5_recall_texts" ]]; then
  echo "Expected data tree at: $DATA (create sibling folder software/data)" >&2
  exit 1
fi

mkdir -p "$ROOT"
rm -rf "$VENV" "$DIST" "$WORK"
mkdir -p "$DIST" "$WORK"

echo "== Creating clean venv =="
python3 -m venv "$VENV"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install -U pip wheel build >/dev/null

echo "== Clearing pip cache entries for this package (best-effort) =="
python -m pip cache remove narRaters 2>/dev/null || true
python -m pip cache remove narraters 2>/dev/null || true

echo "== Building wheel from source =="
( cd "$PKG" && python -m build --wheel -o "$DIST" )

WHEEL=( "$DIST"/narraters-*.whl )
if [[ ! -f "${WHEEL[0]}" ]]; then
  echo "No wheel produced in $DIST" >&2
  exit 1
fi

echo "== Installing wheel with --no-cache-dir =="
python -m pip install --no-cache-dir "${WHEEL[0]}"

echo "== CLI sanity =="
narraters --version
narraters segment --help >/dev/null

mkdir -p "$WORK/out_events" "$WORK/out_corrected" "$WORK/out_parsed" "$WORK/out_rated" "$WORK/out_causal"

echo "== Step 2: segment (clause) =="
narraters segment --method clause \
  -i "$DATA/2_story_transcript" \
  -o "$WORK/out_events"

echo "== Step 3: correct (rules), one recall file =="
narraters correct --method rules \
  -i "$DATA/5_recall_texts/the_siren_sub-01.txt" \
  -o "$WORK/out_corrected"

echo "== Step 4: parse (rules) =="
narraters parse --method rules \
  -i "$WORK/out_corrected" \
  -o "$WORK/out_parsed"

echo "== Step 5: match (test backend) =="
narraters match --method test \
  -i "$WORK/out_parsed" \
  -o "$WORK/out_rated" \
  --story-events "$WORK/out_events"

echo "== Step 6: rate (linguistic) =="
narraters rate --method linguistic \
  -i "$WORK/out_events" \
  -o "$WORK/out_causal"

echo
echo "== OK: wheel install + steps 2–6 completed. Artifacts: $WORK =="
ls -la "$WORK/out_events" | head
ls -la "$WORK/out_causal" | head
