#!/usr/bin/env python3
"""
Test: Run recall rating for all stories in recall_parsed/ folder.

This script:
1. Processes all recall files in recall_parsed/ folder
2. Uses temperature 0, 1 trial per story
3. Outputs to recall_rated/ folder
4. Generates matrix plots for each story
5. Generates a bar plot showing metrics averaged across all stories
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

# Import core recall rater functions
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module
recall_rater = import_module('5_recall-rater')

# Import plotting and analysis functions
from plot_matrix_comparison import (
    create_matrix_from_ratings,
    average_model_matrices,
    plot_matrix_comparison,
    resize_matrix
)
from analysis_recall_metrics import (
    compute_pearson_correlation,
    compute_raw_accuracy,
    compute_weighted_accuracy,
    compute_metrics_for_single_trial
)
from utils_recall_data import load_human_rating, load_event_file
from plot_bar_metrics_comparison import plot_metrics_bar_comparison

# ==============================
# TEST PARAMETERS
# ==============================

TEMPERATURE = 0
NUM_TRIALS = 1  # Only 1 trial per story

MODEL_NAME = DEFAULT_ANTHROPIC_RECALL_MATCH_MODEL
MAX_TOKENS = 2000

STORY_DIR = Path("data/3_story_events")
RECALL_DIR = Path("output/recall_parsed")
OUTPUT_DIR = Path("output/recall_rated")
VISUAL_DIR = OUTPUT_DIR / "visual"


def rate_recall_batch_with_temp(client, recall_segments, story_events, model, temperature):
    """Rate all recall segments in a single batch API call with specified temperature."""
    if not recall_segments:
        return []
    
    # Prepare events payload
    events_payload = [{"event": event['event'], "story_texts": event['story_texts']} 
                     for event in story_events]
    
    # Build the user message
    user_content = (
        recall_rater.USER_PROMPT
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


def process_subject(subj_id, temperature, trial_num):
    """Process a subject's recall file with a specific temperature."""
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
    print(f"    Running recall rating with temperature={temperature}...")
    results = rate_recall_batch_with_temp(client, recall_segments, story_events, MODEL_NAME, temperature)
    
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
    print(f"Running recall rating for all stories...")
    print(f"Temperature: {TEMPERATURE}")
    print(f"Trials per story: {NUM_TRIALS}")
    print()
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    
    # Find all parsed recall files (try both _parsed.xlsx and _rate-recall.xlsx patterns)
    recall_files_parsed = sorted(RECALL_DIR.glob('*_parsed.xlsx'))
    recall_files_rated = sorted(RECALL_DIR.glob('*_rate-recall.xlsx'))
    
    # Combine and deduplicate (prefer _parsed.xlsx if both exist)
    all_files = {}
    for f in recall_files_rated:
        subj_id = f.stem.replace('_rate-recall', '')
        all_files[subj_id] = f
    for f in recall_files_parsed:
        subj_id = f.stem.replace('_parsed', '')
        all_files[subj_id] = f  # This will overwrite if _parsed exists, which is what we want
    
    recall_files = sorted(all_files.values())
    
    if not recall_files:
        print(f"No parsed recall files found in {RECALL_DIR}")
        return
    
    print(f"Found {len(recall_files)} recall files to process")
    print()
    
    # Process each story
    processed_stories = []
    all_metrics = {
        'rval': [],
        'raw_acc': [],
        'weighted_acc': []
    }
    
    for recall_file in recall_files:
        # Extract subject ID from filename
        subj_id = recall_file.stem.replace('_parsed', '').replace('_rate-recall', '')
        print(f"Processing {subj_id}...")
        
        success, model_df = process_subject(subj_id, TEMPERATURE, 1)
        
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
                
                # Store metrics
                all_metrics['rval'].append(r_val)
                all_metrics['raw_acc'].append(raw_acc)
                all_metrics['weighted_acc'].append(weighted_acc)
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
        
        print()
    
    # Create bar plot showing metrics averaged across all stories
    if processed_stories:
        print(f"Creating bar plot for {len(processed_stories)} stories...")
        
        # Prepare data structure for bar plot (single group with averaged metrics)
        metrics_data = {
            'all_stories': {
                'rval': all_metrics['rval'],
                'raw_acc': all_metrics['raw_acc'],
                'weighted_acc': all_metrics['weighted_acc']
            }
        }
        
        # Calculate means
        mean_rval = np.mean(all_metrics['rval'])
        mean_raw = np.mean(all_metrics['raw_acc'])
        mean_weighted = np.mean(all_metrics['weighted_acc'])
        
        print(f"Average across all stories:")
        print(f"  rval: {mean_rval:.3f} ± {np.std(all_metrics['rval']):.3f}")
        print(f"  raw_acc: {mean_raw:.3f} ± {np.std(all_metrics['raw_acc']):.3f}")
        print(f"  weighted_acc: {mean_weighted:.3f} ± {np.std(all_metrics['weighted_acc']):.3f}")
        
        # Create bar plot
        output_file = VISUAL_DIR / "all_stories_metrics_bar_comparison.png"
        plot_metrics_bar_comparison(
            metrics_data=metrics_data,
            output_file=output_file,
            title=f"Metrics Averaged Across All Stories (n={len(processed_stories)})",
            ylabel="Score"
        )
        
        print(f"Bar plot saved: {output_file}")
    
    print()
    print(f"Processing complete!")
    print(f"  Successfully processed: {len(processed_stories)} stories")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"  Visual directory: {VISUAL_DIR}")


if __name__ == "__main__":
    main()

