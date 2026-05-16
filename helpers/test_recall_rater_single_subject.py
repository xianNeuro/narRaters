#!/usr/bin/env python3
"""Test script to run recall rating on a single subject"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module
recall_rater = import_module('5_recall-rater')

# Test with a single subject
SUBJ_ID = "example_subject"  # Replace with your subject ID
print(f"Testing with {SUBJ_ID} only...\n")
recall_rater.process_subject(
    subj_id=SUBJ_ID,
    story_dir='data/3_story_events',
    recall_dir='output/recall_parsed',
    output_dir='output/recall_rated',
    output_format='excel',
    model="claude-sonnet-4-20250514",
    delay=1.0
)
