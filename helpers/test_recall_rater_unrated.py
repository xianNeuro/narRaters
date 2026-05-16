#!/usr/bin/env python3
"""
Test: Run recall rating for unrated recall files.

This script:
1. Finds recall files in recall_parsed/ that haven't been rated yet
2. Uses prompt_v1, temperature 0, one trial per story
3. Outputs to recall_rated/ folder
4. Generates matrix comparison visualizations
"""

import os
import sys
from pathlib import Path
import pandas as pd
import anthropic
import json
import re
import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from helpers.anthropic_ids import DEFAULT_ANTHROPIC_RECALL_MATCH_MODEL

# Import core recall rater functions (project root for pipeline scripts)
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

TEMPERATURE = 0
PROMPT_VERSION = "recall_rating_v1"  # Use prompt_v1

MODEL_NAME = DEFAULT_ANTHROPIC_RECALL_MATCH_MODEL
MAX_TOKENS = 2000

STORY_DIR = Path("data/3_story_events")
RECALL_DIR = Path("output/recall_parsed")
OUTPUT_DIR = Path("output/recall_rated")
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


def find_unrated_files():
    """Find recall files that haven't been rated yet."""
    # Get all parsed recall files
    parsed_files = set()
    for pattern in ['*_parsed.xlsx', '*_rate-recall.xlsx']:
        for file in RECALL_DIR.glob(pattern):
            if '_prev' not in str(file):
                subj_id = file.stem.replace('_parsed', '').replace('_rate-recall', '')
                parsed_files.add(subj_id)
    
    # Get all rated files
    rated_files = set()
    for file in OUTPUT_DIR.glob('*_rate-recall.xlsx'):
        subj_id = file.stem.replace('_rate-recall', '')
        rated_files.add(subj_id)
    
    # Find unrated files
    unrated = sorted(parsed_files - rated_files)
    return unrated


def process_subject(subj_id, temperature, prompt_text):
    """Process a subject's recall file."""
    # Try multiple locations for story events
    story_file = STORY_DIR / f"{subj_id}_events.xlsx"
    if not story_file.exists():
        story_file = Path("data/human_ratings") / f"{subj_id}_events.xlsx"
    
    # Try multiple locations for recall file
    recall_file = RECALL_DIR / f"{subj_id}_parsed.xlsx"
    if not recall_file.exists():
        recall_file = RECALL_DIR / f"{subj_id}_rate-recall.xlsx"
    
    if not story_file.exists() or not recall_file.exists():
        return False, None
    
    # Read files
    story_df = pd.read_excel(story_file)
    recall_df = pd.read_excel(recall_file)
    
    # Determine recall column
    if 'recall_in_temporal_order' in recall_df.columns:
        recall_col = 'recall_in_temporal_order'
    elif 'recalled_events' in recall_df.columns and len(recall_df.columns) > 1:
        recall_col = recall_df.columns[1]
    else:
        return False, None
    
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
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return False, None
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Process
    print(f"    Running recall rating with {PROMPT_VERSION}...")
    results = rate_recall_batch_with_prompt(client, recall_segments, story_events, MODEL_NAME, temperature, prompt_text)
    
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
    output_file = OUTPUT_DIR / f"{subj_id}_rate-recall.xlsx"
    try:
        output_df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
        print(f"    Saved: {output_file.name}")
        return True, output_df
    except Exception as e:
        print(f"  Error saving file: {e}")
        return False, None


def main():
    """Run the test."""
    print(f"Finding unrated recall files...")
    print(f"Prompt version: {PROMPT_VERSION}")
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
    
    # Find unrated files
    unrated_files = find_unrated_files()
    
    if not unrated_files:
        print("No unrated files found. All recall files have been rated.")
        return
    
    print(f"Found {len(unrated_files)} unrated files:")
    for subj_id in unrated_files:
        print(f"  - {subj_id}")
    print()
    
    # Process each unrated file
    processed_stories = []
    
    for subj_id in unrated_files:
        print(f"Processing {subj_id}...")
        
        success, model_df = process_subject(subj_id, TEMPERATURE, prompt_text)
        
        if not success or model_df is None:
            print(f"  Skipping {subj_id}: processing failed")
            continue
        
        # Load event file and human rating for visualization
        event_df = load_event_file(subj_id, Path("."))
        human_df = load_human_rating(subj_id, Path("."))
        
        if event_df is None:
            print(f"  Skipping {subj_id}: could not load event file")
            continue
        
        num_events = len(event_df)
        
        # Create visualizations if human rating exists
        if human_df is not None:
            # Create matrices
            model_matrix = create_matrix_from_ratings(model_df, num_events)
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
                raw_acc = compute_raw_accuracy([model_df], human_df, num_events)
                weighted_acc = compute_weighted_accuracy([model_df], human_df, num_events)
                
                print(f"  Metrics: rval={r_val:.3f}, raw_acc={raw_acc:.3f}, weighted_acc={weighted_acc:.3f}")
                
                processed_stories.append(subj_id)
                
                # Create matrix plot
                VISUAL_DIR.mkdir(parents=True, exist_ok=True)
                output_file = VISUAL_DIR / f"{subj_id}_matrix_comparison.png"
                plot_matrix_comparison(
                    human_matrix=human_matrix,
                    model_matrix=model_matrix,
                    model_binary_matrix=model_binary_matrix,
                    title_prefix=f"Story {subj_id}",
                    r_val=r_val,
                    raw_acc=raw_acc,
                    weighted_acc=weighted_acc,
                    output_file=output_file,
                    show_model_overlay=True
                )
        else:
            print(f"  No human rating found for {subj_id} - skipping visualization")
            processed_stories.append(subj_id)
        
        print()
    
    print(f"Processing complete!")
    print(f"  Successfully processed: {len(processed_stories)} stories")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"  Visual directory: {VISUAL_DIR}")


if __name__ == "__main__":
    main()

