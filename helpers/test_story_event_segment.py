#!/usr/bin/env python3
"""
Test: Run event segmentation API method for a story.

This script tests the event segmentation API method using the prompt in
scripts/prompt/event_segment.txt for a sample story.
"""

import os
import sys
from pathlib import Path

# Import event segmentation functions (project root for pipeline scripts)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module
event_segment = import_module('2_story-event-segment')

# ==============================
# TEST PARAMETERS
# ==============================

STORY_NAME = "example_story"  # Replace with your story name
INPUT_DIR = Path("data/2_story_transcript")
OUTPUT_DIR = Path("data/3_story_events")
METHOD = "api"  # Use API method


def main():
    """Run the test."""
    print(f"Testing event segmentation API method for {STORY_NAME}...")
    print(f"Method: {METHOD}")
    print()
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-api-key'")
        return
    
    # Check if prompt file exists
    prompt_file = Path(__file__).resolve().parents[1] / "scripts" / "prompt" / "event_segment.txt"
    if prompt_file.exists():
        print(f"✓ Found prompt file: {prompt_file}")
        with open(prompt_file, 'r') as f:
            prompt_content = f.read()
            print(f"  Prompt length: {len(prompt_content)} characters")
    else:
        print(f"Warning: Prompt file not found: {prompt_file}")
        print("  Will use default prompt")
    
    print()
    
    # Find transcript file
    transcript_file = INPUT_DIR / f"{STORY_NAME}.txt"
    
    if not transcript_file.exists():
        print(f"Error: Transcript file not found: {transcript_file}")
        return
    
    print(f"Found transcript file: {transcript_file}")
    print()
    
    # Process the story
    success = event_segment.process_story_transcript(
        transcript_path=transcript_file,
        story_name=STORY_NAME,
        output_dir=OUTPUT_DIR,
        method=METHOD
    )
    
    if success:
        print()
        print("✓ Event segmentation completed successfully!")
        output_file = OUTPUT_DIR / f"{STORY_NAME}_events-{METHOD}.xlsx"
        print(f"  Output file: {output_file}")
    else:
        print()
        print("✗ Event segmentation failed")


if __name__ == "__main__":
    main()

