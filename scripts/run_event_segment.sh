#!/bin/bash
# Helper script to run story event segmentation with the API method.
# Checks for at least one API key (Anthropic or OpenAI) before running.

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPTS_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: No API key found"
    echo ""
    echo "Set at least one of the following:"
    echo "  export ANTHROPIC_API_KEY='your-api-key-here'   (for Anthropic models)"
    echo "  export OPENAI_API_KEY='your-api-key-here'      (for GPT models)"
    echo ""
    echo "See SETUP_API.md in the repository root for details."
    exit 1
fi

echo "Running event segmentation with API method..."
[ -n "$ANTHROPIC_API_KEY" ] && echo "  Anthropic key: set (length: ${#ANTHROPIC_API_KEY})"
[ -n "$OPENAI_API_KEY" ] && echo "  OpenAI key:    set (length: ${#OPENAI_API_KEY})"
echo ""

if [ -z "$1" ]; then
    echo "Usage: $0 <input_file> [output_dir] [--model MODEL]"
    echo "Example: $0 data/2_story_transcript/my_story.txt data/3_story_events_test"
    echo "Example: $0 data/2_story_transcript/my_story.txt data/3_story_events_test --model gpt-4o"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_DIR="${2:-data/3_story_events_test}"
shift 2 2>/dev/null

python3 "$SCRIPTS_DIR/2_story-event-segment.py" --input "$INPUT_FILE" --output "$OUTPUT_DIR" --method api "$@"
