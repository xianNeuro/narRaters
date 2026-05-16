#!/bin/bash
# Helper script to run the recall rater with API key

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPTS_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY environment variable not set"
    echo ""
    echo "Please set your API key first:"
    echo "  export ANTHROPIC_API_KEY='your-api-key-here'"
    echo ""
    echo "Get your API key from: https://console.anthropic.com/"
    exit 1
fi

echo "Running recall rater on all 3 subjects..."
echo "API key is set (length: ${#ANTHROPIC_API_KEY})"
echo ""

python3 "$SCRIPTS_DIR/5_recall-rater.py"
