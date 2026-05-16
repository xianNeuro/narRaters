#!/usr/bin/env python3
"""
Test: Create bar plot comparing metrics across all rated stories.

This script loads all recall rating files from recall_rated/ folder,
computes metrics for each story, and generates a bar plot showing
metrics averaged across all stories.
"""

from pathlib import Path
import pandas as pd
import numpy as np
from plot_matrix_comparison import create_matrix_from_ratings, resize_matrix
from analysis_recall_metrics import (
    compute_pearson_correlation,
    compute_raw_accuracy,
    compute_weighted_accuracy
)
from utils_recall_data import load_human_rating, load_event_file
from plot_bar_metrics_comparison import plot_metrics_bar_comparison

# ==============================
# TEST PARAMETERS
# ==============================

BASE_DIR = Path(__file__).parent.parent  # project root
RATED_DIR = BASE_DIR / "output" / "recall_rated"
VISUAL_DIR = RATED_DIR / "visual"


def main():
    """Run the test."""
    print("Creating bar plot for all rated stories...")
    print(f"Loading files from: {RATED_DIR}")
    print()
    
    # Find all rate-recall files
    rated_files = sorted(RATED_DIR.glob('*_rate-recall.xlsx'))
    
    if not rated_files:
        print("No rated files found")
        return
    
    print(f"Found {len(rated_files)} rated files")
    print()
    
    # Collect metrics for all stories
    all_metrics = {
        'rval': [],
        'raw_acc': [],
        'weighted_acc': []
    }
    processed_stories = []
    
    for file in rated_files:
        subj_id = file.stem.replace('_rate-recall', '')
        print(f'Processing {subj_id}...', end=' ')
        
        # Load files
        try:
            model_df = pd.read_excel(file)
            event_df = load_event_file(subj_id, BASE_DIR)
            human_df = load_human_rating(subj_id, BASE_DIR)
        except Exception as e:
            print(f'Error loading files: {e}')
            continue
        
        if event_df is None or human_df is None:
            print('Skipping (missing event or human data)')
            continue
        
        num_events = len(event_df)
        
        # Create matrices
        model_matrix = create_matrix_from_ratings(model_df, num_events)
        human_matrix = create_matrix_from_ratings(human_df, num_events)
        
        if model_matrix is None or human_matrix is None:
            print('Skipping (could not create matrices)')
            continue
        
        # Ensure same shape
        max_events = max(model_matrix.shape[0], human_matrix.shape[0])
        max_segments = max(model_matrix.shape[1], human_matrix.shape[1])
        
        if model_matrix.shape != (max_events, max_segments):
            model_matrix = resize_matrix(model_matrix, (max_events, max_segments))
        if human_matrix.shape != (max_events, max_segments):
            human_matrix = resize_matrix(human_matrix, (max_events, max_segments))
        
        # Compute metrics
        r_val = compute_pearson_correlation(model_matrix, human_matrix)
        raw_acc = compute_raw_accuracy([model_df], human_df, num_events)
        weighted_acc = compute_weighted_accuracy([model_df], human_df, num_events)
        
        all_metrics['rval'].append(r_val)
        all_metrics['raw_acc'].append(raw_acc)
        all_metrics['weighted_acc'].append(weighted_acc)
        processed_stories.append(subj_id)
        print(f'✓ rval={r_val:.3f}, raw_acc={raw_acc:.3f}, weighted_acc={weighted_acc:.3f}')
    
    print()
    print(f"Collected metrics for {len(processed_stories)} stories")
    
    if not processed_stories:
        print("No stories with complete data found")
        return
    
    # Create bar plot with individual story values
    metrics_data = {
        'all_stories': {
            'rval': all_metrics['rval'],
            'raw_acc': all_metrics['raw_acc'],
            'weighted_acc': all_metrics['weighted_acc']
        }
    }
    
    mean_rval = np.mean(all_metrics['rval'])
    mean_raw = np.mean(all_metrics['raw_acc'])
    mean_weighted = np.mean(all_metrics['weighted_acc'])
    
    std_rval = np.std(all_metrics['rval'])
    std_raw = np.std(all_metrics['raw_acc'])
    std_weighted = np.std(all_metrics['weighted_acc'])
    
    print(f'\nAverage across all {len(processed_stories)} stories:')
    print(f'  rval: {mean_rval:.3f} ± {std_rval:.3f}')
    print(f'  raw_acc: {mean_raw:.3f} ± {std_raw:.3f}')
    print(f'  weighted_acc: {mean_weighted:.3f} ± {std_weighted:.3f}')
    
    # Create bar plot
    output_file = VISUAL_DIR / "all_stories_metrics_bar_comparison.png"
    plot_metrics_bar_comparison(
        metrics_data=metrics_data,
        output_file=output_file,
        title=f'Metrics Averaged Across All Rated Stories (n={len(processed_stories)})',
        ylabel='Score'
    )
    print(f'\nBar plot saved: {output_file}')


if __name__ == "__main__":
    main()

