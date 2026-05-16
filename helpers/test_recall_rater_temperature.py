#!/usr/bin/env python3
"""
Test: Run recall rater with different temperatures (multiple trials per temperature).

This test script runs the recall rating API for a subject with different temperatures,
each with multiple independent trials, and saves the results.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import anthropic
import json
import re

# Import core recall rater functions
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module
recall_rater = import_module('5_recall-rater')

# ==============================
# TEST PARAMETERS
# ==============================

SUBJ_ID = "example_subject"  # Replace with your subject ID
TEMPERATURES = [0, 0.5, 1]
NUM_TRIALS = 5

MODEL_NAME = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2000

STORY_DIR = Path("data/3_story_events")
RECALL_DIR = Path("output/recall_parsed")
OUTPUT_DIR = Path("output/recall_rated_testing")


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


def process_subject_with_temp(subj_id, temperature, trial_num):
    """Process a subject's recall file with a specific temperature."""
    story_file = STORY_DIR / f"{subj_id}_events.xlsx"
    recall_file = RECALL_DIR / f"{subj_id}_parsed.xlsx"
    
    if not recall_file.exists():
        alt_recall_file = RECALL_DIR / f"{subj_id}_rate-recall.xlsx"
        if alt_recall_file.exists():
            recall_file = alt_recall_file
    
    if not story_file.exists() or not recall_file.exists():
        return False
    
    # Read files
    story_df = pd.read_excel(story_file)
    recall_df = pd.read_excel(recall_file)
    
    # Determine recall column
    if 'recall_in_temporal_order' in recall_df.columns:
        recall_col = 'recall_in_temporal_order'
    elif 'recalled_events' in recall_df.columns and len(recall_df.columns) > 1:
        recall_col = recall_df.columns[1]
    else:
        return False
    
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
        return False
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Process
    print(f"    Running trial {trial_num} with temperature={temperature}...")
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
    output_file = OUTPUT_DIR / f"{subj_id}_rate-recall_temp{temperature}_trial{trial_num}.xlsx"
    try:
        output_df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
        print(f"    Saved: {output_file.name}")
        return True
    except Exception as e:
        print(f"  Error saving file: {e}")
        return False


def main():
    """Run the test."""
    print(f"Running recall rater for {SUBJ_ID}...")
    print(f"Temperatures: {TEMPERATURES}")
    print(f"Trials per temperature: {NUM_TRIALS}")
    print(f"Total runs: {len(TEMPERATURES) * NUM_TRIALS}")
    print()
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    
    for temp in TEMPERATURES:
        print(f"Processing temperature = {temp}...")
        for trial in range(1, NUM_TRIALS + 1):
            process_subject_with_temp(SUBJ_ID, temp, trial)
        print()
    
    print("All processing complete!")


if __name__ == "__main__":
    main()

