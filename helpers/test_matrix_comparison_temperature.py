#!/usr/bin/env python3
"""
Test: Create matrix comparison plots for different temperatures.

This test script loads model ratings for different temperatures,
averages across trials, and generates side-by-side comparison plots with human.
"""

from pathlib import Path
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

SUBJ_ID = "example_subject"  # Replace with your subject ID
TEMPERATURES = [0, 0.5, 1]

BASE_DIR = Path(__file__).parent.parent  # project root
MODEL_DIR = BASE_DIR / "output" / "recall_rated_testing"
OUTPUT_DIR = BASE_DIR / "output" / "recall_rated_testing" / "visual"


def main():
    """Run the test."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Creating matrix plots for different temperatures...")
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
    print()
    
    # Load human rating
    human_df = load_human_rating(SUBJ_ID, BASE_DIR)
    if human_df is None:
        print("Warning: Could not load human rating - will show model only")
        human_matrix = None
    else:
        human_matrix = create_matrix_from_ratings(human_df, num_events)
    
    # Process each temperature
    for temp in TEMPERATURES:
        print(f"Processing temperature = {temp}...")
        
        # Load model ratings for this temperature
        model_dfs = load_model_ratings(SUBJ_ID, MODEL_DIR, temperature=temp)
        print(f"  Found {len(model_dfs)} model rating files")
        
        if not model_dfs:
            print(f"  Skipping temperature {temp}: no model ratings found")
            continue
        
        # Create averaged model matrix
        model_matrix = average_model_matrices(model_dfs, num_events)
        if model_matrix is None:
            print(f"  Skipping temperature {temp}: could not create matrix")
            continue
        
        model_binary_matrix = (model_matrix > 0).astype(int)
        
        # Compute metrics
        if human_matrix is not None:
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
        output_file = OUTPUT_DIR / f"{SUBJ_ID}_temp{temp}_matrix_comparison.png"
        plot_matrix_comparison(
            human_matrix=human_matrix,
            model_matrix=model_matrix,
            model_binary_matrix=model_binary_matrix,
            title_prefix=f"Temperature = {temp}",
            r_val=r_val,
            raw_acc=raw_acc,
            weighted_acc=weighted_acc,
            output_file=output_file,
            show_model_overlay=True
        )
        
        print(f"  Completed temperature {temp}")
        print()
    
    print("All visualizations complete!")


if __name__ == "__main__":
    main()

