#!/usr/bin/env python3
"""
Core plotting functions for recall rating matrix comparisons.

Functions:
- plot_matrix_comparison: Create side-by-side matrix plots (human vs model)
- create_matrix_from_ratings: Convert recall ratings DataFrame to binary matrix
- average_model_matrices: Average multiple model rating matrices
- resize_matrix: Resize matrix to target shape
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import re
from collections import Counter


def parse_event_string(event_str):
    """Parse event string (e.g., '1,2' or '1' or '') into list of integers."""
    if pd.isna(event_str) or event_str == '' or str(event_str).strip() == '':
        return []
    
    event_str = str(event_str).strip()
    if event_str.upper() == 'NONE':
        return []
    
    # Extract all numbers
    numbers = re.findall(r'\d+', event_str)
    return [int(n) for n in numbers]


def create_matrix_from_ratings(recall_df, num_events):
    """
    Create a binary matrix from recall ratings DataFrame.
    
    Args:
        recall_df: DataFrame with 'recalled_events' column
        num_events: Total number of events in the story
    
    Returns:
        numpy array of shape (num_events, num_recall_segments) with 0/1 values
        Rows = events, Columns = recall segments
    """
    if recall_df is None or len(recall_df) == 0:
        return None
    
    if 'recalled_events' not in recall_df.columns:
        return None
    
    # Reset index to ensure sequential column indices
    recall_df = recall_df.reset_index(drop=True)
    
    num_segments = len(recall_df)
    matrix = np.zeros((num_events, num_segments), dtype=int)
    
    for seg_idx, row in recall_df.iterrows():
        try:
            event_str = row['recalled_events']
            # Handle NaN, None, or other non-string types
            if pd.isna(event_str):
                event_str = ''
            else:
                event_str = str(event_str)
            
            matched_events = parse_event_string(event_str)
            
            for event_num in matched_events:
                if 1 <= event_num <= num_events:
                    matrix[event_num - 1, seg_idx] = 1
        except Exception as e:
            # Log error but continue processing other segments
            print(f"Warning: Error processing segment {seg_idx}: {e}")
            continue
    
    return matrix


def average_model_matrices(model_dfs, num_events):
    """
    Average multiple model rating matrices.
    
    Args:
        model_dfs: List of DataFrames, each containing model ratings for one trial
        num_events: Total number of events in the story
    
    Returns:
        numpy array of shape (num_events, num_segments) with float values
        representing proportion of trials that matched (0.0 to 1.0)
    """
    if not model_dfs:
        return None
    
    matrices = []
    for df in model_dfs:
        matrix = create_matrix_from_ratings(df, num_events)
        if matrix is not None:
            matrices.append(matrix)
    
    if not matrices:
        return None
    
    # Check all matrices have same shape
    shapes = [m.shape for m in matrices]
    if len(set(shapes)) > 1:
        # Use the most common shape
        common_shape = Counter(shapes).most_common(1)[0][0]
        # Resize all matrices to common shape
        matrices = [resize_matrix(m, common_shape) for m in matrices]
    
    # Average the matrices - keep as float (proportion of trials)
    avg_matrix = np.mean(matrices, axis=0).astype(float)
    
    return avg_matrix


def resize_matrix(matrix, target_shape):
    """
    Resize matrix to target shape by padding or cropping.
    
    Args:
        matrix: Input matrix (numpy array)
        target_shape: Target shape tuple (rows, cols)
    
    Returns:
        Resized matrix (numpy array)
    """
    current_shape = matrix.shape
    target_rows, target_cols = target_shape
    
    # Create new matrix with target shape (preserve dtype)
    new_matrix = np.zeros(target_shape, dtype=matrix.dtype)
    
    # Copy overlapping region
    rows_to_copy = min(current_shape[0], target_rows)
    cols_to_copy = min(current_shape[1], target_cols)
    
    new_matrix[:rows_to_copy, :cols_to_copy] = matrix[:rows_to_copy, :cols_to_copy]
    
    return new_matrix


def plot_matrix_comparison(
    human_matrix,
    model_matrix,
    model_binary_matrix,
    title_prefix,
    r_val=0.0,
    raw_acc=0.0,
    weighted_acc=0.0,
    output_file=None,
    show_model_overlay=True
):
    """
    Plot human and model matrices side by side.
    
    Args:
        human_matrix: Human rating matrix (binary, numpy array)
        model_matrix: Averaged model rating matrix (float, numpy array)
        model_binary_matrix: Binary version of model matrix for overlay (numpy array)
        title_prefix: Prefix for plot titles (e.g., "Story A" or "Temperature = 0")
        r_val: Pearson correlation coefficient
        raw_acc: Raw accuracy score
        weighted_acc: Weighted accuracy score
        output_file: Path to save the plot (Path object or string)
        show_model_overlay: If True, show red dotted outline on human matrix where model found matches
    
    Returns:
        None (saves plot to file)
    """
    if human_matrix is None and model_matrix is None:
        print("Warning: No data to plot")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 10))
    
    # Determine common shape
    if human_matrix is not None and model_matrix is not None:
        max_events = max(human_matrix.shape[0], model_matrix.shape[0])
        max_segments = max(human_matrix.shape[1], model_matrix.shape[1])
        
        if human_matrix.shape != (max_events, max_segments):
            human_matrix = resize_matrix(human_matrix, (max_events, max_segments))
        if model_matrix.shape != (max_events, max_segments):
            model_matrix = resize_matrix(model_matrix, (max_events, max_segments))
        if model_binary_matrix is not None and model_binary_matrix.shape != (max_events, max_segments):
            model_binary_matrix = resize_matrix(model_binary_matrix, (max_events, max_segments))
    elif human_matrix is not None:
        max_events, max_segments = human_matrix.shape
        model_matrix = np.zeros((max_events, max_segments), dtype=float)
        model_binary_matrix = np.zeros((max_events, max_segments), dtype=int)
    elif model_matrix is not None:
        max_events, max_segments = model_matrix.shape
        human_matrix = np.zeros((max_events, max_segments), dtype=int)
        model_binary_matrix = (model_matrix > 0).astype(int)
    
    # Ensure model_binary_matrix exists
    if model_binary_matrix is None:
        model_binary_matrix = (model_matrix > 0).astype(int)
    
    # Plot human matrix (left)
    ax1 = axes[0]
    im1 = ax1.imshow(human_matrix, aspect='auto', cmap='viridis', vmin=0, vmax=1, interpolation='nearest')
    
    # Overlay red dotted outline on cells where model found matches (if requested)
    if show_model_overlay:
        for event_idx in range(max_events):
            for seg_idx in range(max_segments):
                if model_binary_matrix[event_idx, seg_idx] > 0:
                    rect = mpatches.Rectangle(
                        (seg_idx - 0.5, event_idx - 0.5), 1, 1,
                        linewidth=1.5, edgecolor='red', facecolor='none',
                        linestyle='--', alpha=0.8
                    )
                    ax1.add_patch(rect)
    
    ax1.set_title(f'Human - {title_prefix}\nrval = {r_val:.3f}, raw-acc = {raw_acc:.3f}, weighted-acc = {weighted_acc:.3f}', 
                  fontsize=14, fontweight='bold')
    ax1.set_xlabel('Recall Segment', fontsize=12)
    ax1.set_ylabel('Story Event', fontsize=12)
    
    # Set ticks
    if max_events <= 50:
        ax1.set_yticks(range(max_events))
        ax1.set_yticklabels(range(1, max_events + 1))
    else:
        step = max(1, max_events // 20)
        ax1.set_yticks(range(0, max_events, step))
        ax1.set_yticklabels(range(1, max_events + 1, step))
    
    if max_segments <= 50:
        ax1.set_xticks(range(max_segments))
        ax1.set_xticklabels(range(1, max_segments + 1), rotation=45, ha='right')
    else:
        step = max(1, max_segments // 20)
        ax1.set_xticks(range(0, max_segments, step))
        ax1.set_xticklabels(range(1, max_segments + 1, step), rotation=45, ha='right')
    
    plt.colorbar(im1, ax=ax1, label='Match (1=Yes, 0=No)')
    
    # Plot model matrix (right)
    ax2 = axes[1]
    im2 = ax2.imshow(model_matrix, aspect='auto', cmap='viridis', vmin=0, vmax=1, interpolation='nearest')
    ax2.set_title(f'Model (Averaged) - {title_prefix}\nrval = {r_val:.3f}, raw-acc = {raw_acc:.3f}, weighted-acc = {weighted_acc:.3f}', 
                  fontsize=14, fontweight='bold')
    ax2.set_xlabel('Recall Segment', fontsize=12)
    ax2.set_ylabel('Story Event', fontsize=12)
    
    # Set ticks
    if max_events <= 50:
        ax2.set_yticks(range(max_events))
        ax2.set_yticklabels(range(1, max_events + 1))
    else:
        step = max(1, max_events // 20)
        ax2.set_yticks(range(0, max_events, step))
        ax2.set_yticklabels(range(1, max_events + 1, step))
    
    if max_segments <= 50:
        ax2.set_xticks(range(max_segments))
        ax2.set_xticklabels(range(1, max_segments + 1), rotation=45, ha='right')
    else:
        step = max(1, max_segments // 20)
        ax2.set_xticks(range(0, max_segments, step))
        ax2.set_xticklabels(range(1, max_segments + 1, step), rotation=45, ha='right')
    
    plt.colorbar(im2, ax=ax2, label='Proportion of Trials')
    
    plt.tight_layout()
    
    # Save figure
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    
    plt.close()

