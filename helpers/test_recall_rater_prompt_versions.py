#!/usr/bin/env python3
"""
Test: Run recall rating with a specific prompt version.

This script:
1. Uses a specified prompt version for recall rating
2. Processes a single subject
3. Outputs to recall_rated_test-prompt/ folder
4. Generates matrix comparison visualization
"""

import os
import sys
from pathlib import Path
import pandas as pd
import anthropic
import json
import re
import numpy as np

# Import core recall rater functions
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module
recall_rater = import_module('5_recall-rater')

# Import plotting and analysis functions
from plot_matrix_comparison import (
    create_matrix_from_ratings,
    plot_matrix_comparison,
    resize_matrix
)
from analysis_recall_metrics import (
    compute_pearson_correlation,
    compute_raw_accuracy,
    compute_weighted_accuracy
)
from utils_recall_data import load_human_rating, load_event_file

# ==============================
# TEST PARAMETERS
# ==============================

SUBJ_ID = "example_subject"  # Replace with your subject ID
TEMPERATURE = 0
PROMPT_VERSION = "recall_rating_v4"  # Change this to test different versions

MODEL_NAME = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2000

STORY_DIR = Path("data/3_story_events")
RECALL_DIR = Path("output/recall_parsed")
OUTPUT_DIR = Path("output/recall_rated_test-prompt")
VISUAL_DIR = OUTPUT_DIR / "visual"


def load_prompt(version):
    """Load prompt from scripts/prompt/."""
    prompt_file = Path(__file__).resolve().parents[1] / "scripts" / "prompt" / f"{version}.txt"
    
    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


def rate_recall_batch_with_prompt(client, recall_segments, story_events, model, temperature, prompt_text):
    """Rate all recall segments in a single batch API call with specified prompt."""
    if not recall_segments:
        return []
    
    # Prepare events payload
    events_payload = [{"event": event['event'], "story_texts": event['story_texts']} 
                     for event in story_events]
    
    # Build the user message
    user_content = (
        prompt_text
        + "\n\nStory Events:\n"
        + json.dumps(events_payload, ensure_ascii=False, indent=2)
        + "\n\nRecall Texts:\n"
        + json.dumps(recall_segments, ensure_ascii=False, indent=2)
    )
    
    try:
        response = client.messages.create(
            model=model,
            system=recall_rater.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=MAX_TOKENS,
            temperature=temperature,
        )
        
        output_text = response.content[0].text.strip()
        
        if output_text.startswith("```"):
            output_text = output_text.split("```")[1]
        if output_text.startswith("json"):
            output_text = output_text[4:].strip()
        
        matched = json.loads(output_text)
        result_map = {}
        for item in matched:
            row_idx = item.get("row_index", -1)
            matched_events = item.get("matched_events", "NONE")
            if matched_events == "NONE" or matched_events == "":
                result_map[row_idx] = ""
            else:
                result_map[row_idx] = str(matched_events).strip()
        
        results = []
        for i in range(len(recall_segments)):
            results.append(result_map.get(i, ""))
        
        return results
    except Exception as e:
        print(f"  Error calling API: {e}")
        return [""] * len(recall_segments)


def main():
    """Run the test."""
    print(f"Running recall rating with {PROMPT_VERSION} for {SUBJ_ID}...")
    print(f"Temperature: {TEMPERATURE}")
    print()
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    
    # Load prompt
    try:
        prompt_text = load_prompt(PROMPT_VERSION)
        print(f"Loaded prompt: {PROMPT_VERSION}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    
    # Try multiple locations for story events
    story_file = STORY_DIR / f"{SUBJ_ID}_events.xlsx"
    if not story_file.exists():
        story_file = Path("data/human_ratings") / f"{SUBJ_ID}_events.xlsx"
    
    # Try multiple locations for recall file
    recall_file = RECALL_DIR / f"{SUBJ_ID}_parsed.xlsx"
    if not recall_file.exists():
        recall_file = RECALL_DIR / f"{SUBJ_ID}_rate-recall.xlsx"
    
    if not story_file.exists() or not recall_file.exists():
        print(f"Error: Files not found")
        print(f"  Story file: {story_file} (exists: {story_file.exists()})")
        print(f"  Recall file: {recall_file} (exists: {recall_file.exists()})")
        return
    
    # Read files
    story_df = pd.read_excel(story_file)
    recall_df = pd.read_excel(recall_file)
    
    # Determine recall column
    if 'recall_in_temporal_order' in recall_df.columns:
        recall_col = 'recall_in_temporal_order'
    elif 'recalled_events' in recall_df.columns and len(recall_df.columns) > 1:
        recall_col = recall_df.columns[1]
    else:
        print("Error: Could not determine recall column")
        return
    
    story_events = [
        {'event': int(row['event']), 'story_texts': str(row['story_texts']) if pd.notna(row['story_texts']) else ''}
        for _, row in story_df.iterrows()
        if pd.notna(row['event'])
    ]
    
    recall_segments = [
        str(row[recall_col]) if pd.notna(row[recall_col]) and isinstance(row[recall_col], str) else ''
        for _, row in recall_df.iterrows()
    ]
    
    # Initialize client
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    
    # Process
    print(f"Running recall rating with {PROMPT_VERSION}...")
    results = rate_recall_batch_with_prompt(client, recall_segments, story_events, MODEL_NAME, TEMPERATURE, prompt_text)
    
    # Process results
    matched_events_list = []
    for result in results:
        if result and result.strip() and result.strip().upper() != 'NONE':
            numbers = re.findall(r'\d+', result)
            if numbers:
                valid_events = {event['event'] for event in story_events}
                matched_events = [int(n) for n in numbers if int(n) in valid_events]
                if matched_events:
                    matched_events_list.append(','.join(str(int(e)) for e in sorted(set(matched_events))))
                else:
                    matched_events_list.append('')
            else:
                matched_events_list.append('')
        else:
            matched_events_list.append('')
    
    # Create output
    output_df = recall_df.copy()
    if 'recalled_events' not in output_df.columns:
        output_df.insert(0, 'recalled_events', '')
    output_df['recalled_events'] = matched_events_list
    
    # Clean up
    def clean_matched_event(val):
        if pd.isna(val) or val == '':
            return ''
        if isinstance(val, (int, float)):
            return str(int(val)) if not pd.isna(val) else ''
        val_str = str(val)
        if val_str.lower() in ['nan', 'none', '']:
            return ''
        if ',' in val_str:
            parts = [x.strip() for x in val_str.split(',')]
            try:
                int_parts = [str(int(float(x))) for x in parts if x and x.replace('.', '').replace('-', '').isdigit()]
                return ','.join(int_parts)
            except:
                return val_str
        try:
            if val_str.replace('.', '').replace('-', '').isdigit():
                return str(int(float(val_str)))
        except:
            pass
        return val_str
    
    output_df['recalled_events'] = output_df['recalled_events'].apply(clean_matched_event)
    
    if 'recalled_events' in output_df.columns and recall_col in output_df.columns:
        output_df = output_df[['recalled_events', recall_col]]
    
    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{SUBJ_ID}_rate-recall_{PROMPT_VERSION}.xlsx"
    try:
        output_df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
        print(f"Saved: {output_file.name}")
    except Exception as e:
        print(f"Error saving file: {e}")
        return
    
    # Load event file and human rating for visualization
    event_df = load_event_file(SUBJ_ID, Path("."))
    human_df = load_human_rating(SUBJ_ID, Path("."))
    
    if event_df is None:
        print("Warning: Could not load event file for visualization")
        return
    
    num_events = len(event_df)
    
    # Create visualizations if human rating exists
    if human_df is not None:
        # Create matrices
        model_matrix = create_matrix_from_ratings(output_df, num_events)
        human_matrix = create_matrix_from_ratings(human_df, num_events)
        
        if model_matrix is not None and human_matrix is not None:
            # Ensure same shape
            max_events = max(model_matrix.shape[0], human_matrix.shape[0])
            max_segments = max(model_matrix.shape[1], human_matrix.shape[1])
            
            if model_matrix.shape != (max_events, max_segments):
                model_matrix = resize_matrix(model_matrix, (max_events, max_segments))
            if human_matrix.shape != (max_events, max_segments):
                human_matrix = resize_matrix(human_matrix, (max_events, max_segments))
            
            model_binary_matrix = (model_matrix > 0).astype(int)
            
            # Compute metrics
            r_val = compute_pearson_correlation(model_matrix, human_matrix)
            raw_acc = compute_raw_accuracy([output_df], human_df, num_events)
            weighted_acc = compute_weighted_accuracy([output_df], human_df, num_events)
            
            print(f"\nMetrics:")
            print(f"  rval: {r_val:.3f}")
            print(f"  raw_acc: {raw_acc:.3f}")
            print(f"  weighted_acc: {weighted_acc:.3f}")
            
            # Create matrix plot
            VISUAL_DIR.mkdir(parents=True, exist_ok=True)
            output_plot = VISUAL_DIR / f"{SUBJ_ID}_{PROMPT_VERSION}_matrix_comparison.png"
            plot_matrix_comparison(
                human_matrix=human_matrix,
                model_matrix=model_matrix,
                model_binary_matrix=model_binary_matrix,
                title_prefix=f"Story {SUBJ_ID} ({PROMPT_VERSION})",
                r_val=r_val,
                raw_acc=raw_acc,
                weighted_acc=weighted_acc,
                output_file=output_plot,
                show_model_overlay=True
            )
            print(f"\nVisualization saved: {output_plot}")
    
    print("\nProcessing complete!")


if __name__ == "__main__":
    main()

