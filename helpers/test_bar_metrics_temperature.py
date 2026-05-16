#!/usr/bin/env python3
"""
Test: Create bar plot comparing metrics (rval, raw-acc, weighted-acc) across temperatures.

This test script loads model ratings for different temperatures,
computes metrics for each trial, and generates a bar plot with error bars and swarm overlay.
"""

from pathlib import Path
import pandas as pd
from plot_matrix_comparison import create_matrix_from_ratings, average_model_matrices, resize_matrix
from analysis_recall_metrics import (
    compute_pearson_correlation,
    compute_raw_accuracy,
    compute_weighted_accuracy,
    compute_metrics_for_single_trial
)
from utils_recall_data import load_human_rating, load_model_ratings, load_event_file
from plot_bar_metrics_comparison import plot_metrics_bar_comparison

# ==============================
# TEST PARAMETERS
# ==============================

SUBJ_ID = "example_subject"  # Replace with your subject ID
TEMPERATURES = [0, 0.5, 1]

BASE_DIR = Path(__file__).parent.parent  # project root
MODEL_DIR = BASE_DIR / "output" / "recall_rated_testing"
OUTPUT_DIR = BASE_DIR / "output" / "recall_rated_testing" / "visual"




def main():
    """Run the test."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Creating bar plot comparing metrics across temperatures...")
    print(f"Subject: {SUBJ_ID}")
    print(f"Temperatures: {TEMPERATURES}")
    print()
    
    # Load event file
    event_df = load_event_file(SUBJ_ID, BASE_DIR)
    if event_df is None:
        print("Error: Could not load event file")
        return
    
    num_events = len(event_df)
    print(f"Total events: {num_events}")
    
    # Load human rating
    human_df = load_human_rating(SUBJ_ID, BASE_DIR)
    if human_df is None:
        print("Error: Could not load human rating")
        return
    
    # Create human matrix once (used for rval computation)
    human_matrix = create_matrix_from_ratings(human_df, num_events)
    
    # Collect metrics for each temperature and trial
    metrics_data = {}
    
    for temp in TEMPERATURES:
        temp_key = f"temperature_{temp}"
        metrics_data[temp_key] = {
            'rval': [],
            'raw_acc': [],
            'weighted_acc': []
        }
        
        print(f"Processing temperature = {temp}...")
        
        # Load model ratings for this temperature
        model_dfs = load_model_ratings(SUBJ_ID, MODEL_DIR, temperature=temp)
        print(f"  Found {len(model_dfs)} model rating files")
        
        if not model_dfs:
            print(f"  Skipping temperature {temp}: no model ratings found")
            continue
        
        # Compute metrics for each trial
        # Note: rval is computed from averaged matrix (like matrix comparison),
        # while raw_acc and weighted_acc are computed per trial then averaged
        for trial_idx, model_df in enumerate(model_dfs):
            # Compute raw_acc and weighted_acc per trial
            _, raw_acc, weighted_acc = compute_metrics_for_single_trial(model_df, human_df, num_events)
            
            if raw_acc is not None:
                metrics_data[temp_key]['raw_acc'].append(raw_acc)
                metrics_data[temp_key]['weighted_acc'].append(weighted_acc)
                if trial_idx == 0:  # Print first trial values for verification
                    print(f"    Trial 1: raw_acc={raw_acc:.3f}, weighted_acc={weighted_acc:.3f}")
        
        # Compute rval from averaged matrix (matching matrix comparison script)
        model_matrix = average_model_matrices(model_dfs, num_events)
        if model_matrix is not None and human_matrix is not None:
            # Ensure same shape
            max_events = max(model_matrix.shape[0], human_matrix.shape[0])
            max_segments = max(model_matrix.shape[1], human_matrix.shape[1])
            
            if model_matrix.shape != (max_events, max_segments):
                model_matrix = resize_matrix(model_matrix, (max_events, max_segments))
            if human_matrix.shape != (max_events, max_segments):
                human_matrix = resize_matrix(human_matrix, (max_events, max_segments))
            
            r_val = compute_pearson_correlation(model_matrix, human_matrix)
            # Use the same rval for all trials (since it's computed from averaged matrix)
            for _ in range(len(model_dfs)):
                metrics_data[temp_key]['rval'].append(r_val)
        
        # Print summary statistics
        if metrics_data[temp_key]['rval']:
            mean_rval = np.mean(metrics_data[temp_key]['rval'])
            mean_raw = np.mean(metrics_data[temp_key]['raw_acc'])
            mean_weighted = np.mean(metrics_data[temp_key]['weighted_acc'])
            print(f"  Collected {len(metrics_data[temp_key]['rval'])} trials")
            print(f"  Mean: rval={mean_rval:.3f}, raw_acc={mean_raw:.3f}, weighted_acc={mean_weighted:.3f}")
        print()
    
    # Create bar plot
    output_file = OUTPUT_DIR / f"{SUBJ_ID}_metrics_bar_comparison.png"
    plot_metrics_bar_comparison(
        metrics_data=metrics_data,
        output_file=output_file,
        title=f"Metrics Comparison Across Temperatures - {SUBJ_ID}",
        ylabel="Score"
    )
    
    print("Bar plot complete!")


if __name__ == "__main__":
    import numpy as np
    main()

