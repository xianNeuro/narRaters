#!/usr/bin/env python3
"""
Test: Create matrix comparison plots for multiple stories.

This test script loads model and human ratings for multiple stories,
computes metrics, and generates side-by-side comparison plots.
"""

from pathlib import Path
import pandas as pd
from plot_matrix_comparison import (
    create_matrix_from_ratings,
    average_model_matrices,
    plot_matrix_comparison
)
from analysis_recall_metrics import (
    compute_pearson_correlation,
    compute_raw_accuracy,
    compute_weighted_accuracy
)
from utils_recall_data import load_human_rating, load_model_ratings, load_event_file

# ==============================
# TEST PARAMETERS
# ==============================

# Story ID mapping: model story ID -> (human subject prefix, event file prefix)
# Replace with your actual story/subject ID mappings
STORY_MAPPING = {
    # 'story_id': ('subject_prefix', 'event_file_prefix'),
}

# Directories
BASE_DIR = Path(__file__).parent.parent  # project root
MODEL_DIR = BASE_DIR / "output" / "recall_rated_testing"
HUMAN_DIR = BASE_DIR / "output" / "recall_rated"
EVENT_DIR = BASE_DIR / "data" / "3_story_events"
OUTPUT_DIR = BASE_DIR / "output" / "recall_rated_testing" / "visual"


def main():
    """Run the test."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Creating matrix plots for multiple stories...")
    print(f"Model ratings directory: {MODEL_DIR}")
    print(f"Human ratings directory: {HUMAN_DIR}")
    print(f"Event files directory: {EVENT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()
    
    for story_id, (human_prefix, event_prefix) in STORY_MAPPING.items():
        print(f"Processing story {story_id}...")
        
        # Load event file
        event_df = load_event_file(event_prefix, BASE_DIR)
        if event_df is None:
            print(f"  Skipping story {story_id}: could not load event file")
            continue
        
        num_events = len(event_df)
        print(f"  Total events: {num_events}")
        
        # Load model ratings (all trials)
        model_dfs = load_model_ratings(story_id, MODEL_DIR)
        print(f"  Found {len(model_dfs)} model rating files")
        
        if not model_dfs:
            print(f"  Skipping story {story_id}: no model ratings found")
            continue
        
        # Create averaged model matrix
        model_matrix = average_model_matrices(model_dfs, num_events)
        if model_matrix is None:
            print(f"  Skipping story {story_id}: could not create model matrix")
            continue
        
        model_binary_matrix = (model_matrix > 0).astype(int)
        
        # Load human rating
        human_df = load_human_rating(human_prefix, BASE_DIR)
        if human_df is None:
            print(f"  Skipping story {story_id}: could not load human rating")
            continue
        
        human_matrix = create_matrix_from_ratings(human_df, num_events)
        
        # Compute metrics
        if model_matrix is not None and human_matrix is not None:
            # Ensure matrices have same shape
            max_events = max(model_matrix.shape[0], human_matrix.shape[0])
            max_segments = max(model_matrix.shape[1], human_matrix.shape[1])
            
            if model_matrix.shape != (max_events, max_segments):
                from plot_matrix_comparison import resize_matrix
                model_matrix = resize_matrix(model_matrix, (max_events, max_segments))
            if human_matrix.shape != (max_events, max_segments):
                from plot_matrix_comparison import resize_matrix
                human_matrix = resize_matrix(human_matrix, (max_events, max_segments))
            if model_binary_matrix.shape != (max_events, max_segments):
                from plot_matrix_comparison import resize_matrix
                model_binary_matrix = resize_matrix(model_binary_matrix, (max_events, max_segments))
            
            r_val = compute_pearson_correlation(model_matrix, human_matrix)
            raw_acc = compute_raw_accuracy(model_dfs, human_df, num_events)
            weighted_acc = compute_weighted_accuracy(model_dfs, human_df, num_events)
        else:
            r_val = 0.0
            raw_acc = 0.0
            weighted_acc = 0.0
        
        print(f"  rval = {r_val:.3f}, raw-acc = {raw_acc:.3f}, weighted-acc = {weighted_acc:.3f}")
        
        # Plot
        output_file = OUTPUT_DIR / f"story_{story_id}_matrix_comparison.png"
        plot_matrix_comparison(
            human_matrix=human_matrix,
            model_matrix=model_matrix,
            model_binary_matrix=model_binary_matrix,
            title_prefix=f"Story {story_id}",
            r_val=r_val,
            raw_acc=raw_acc,
            weighted_acc=weighted_acc,
            output_file=output_file,
            show_model_overlay=True
        )
        
        print(f"  Completed story {story_id}")
        print()


if __name__ == "__main__":
    main()

