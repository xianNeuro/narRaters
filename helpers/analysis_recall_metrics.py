#!/usr/bin/env python3
"""
Core analysis functions for computing recall rating metrics.

Functions:
- compute_pearson_correlation: Pearson correlation between model and human matrices
- compute_raw_accuracy: Raw accuracy (model matched events / human total events)
- compute_weighted_accuracy: Weighted accuracy (weighted-hit / total-match)
"""

import pandas as pd
import numpy as np
from scipy.stats import pearsonr
import re


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


def compute_pearson_correlation(model_matrix, human_matrix):
    """
    Compute Pearson correlation between model and human matrices.
    
    Args:
        model_matrix: Model rating matrix (numpy array)
        human_matrix: Human rating matrix (numpy array)
    
    Returns:
        Pearson correlation coefficient (float)
    """
    model_flat = model_matrix.flatten()
    human_flat = human_matrix.flatten()
    
    if len(model_flat) == 0 or np.std(model_flat) == 0 or np.std(human_flat) == 0:
        return 0.0
    
    r_val, _ = pearsonr(model_flat, human_flat)
    return r_val if not np.isnan(r_val) else 0.0


def compute_raw_accuracy(model_dfs, human_df, num_events):
    """
    Compute raw accuracy across all model trials.
    
    For each recall segment:
    - raw-acc = (number of model events matched with human) / (total number of events returned by human)
    
    Average across all recall segments for each trial, then average across all trials.
    
    Args:
        model_dfs: List of DataFrames, each containing model ratings for one trial
        human_df: DataFrame containing human ratings
        num_events: Total number of events in the story
    
    Returns:
        Average raw accuracy (float)
    """
    if not model_dfs or human_df is None:
        return 0.0
    
    trial_accuracies = []
    
    for model_df in model_dfs:
        segment_accuracies = []
        
        # Ensure both dataframes have same number of segments
        min_segments = min(len(model_df), len(human_df))
        
        for seg_idx in range(min_segments):
            # Get model events for this segment
            model_events_str = model_df.iloc[seg_idx]['recalled_events']
            model_events = set(parse_event_string(model_events_str))
            
            # Get human events for this segment
            human_events_str = human_df.iloc[seg_idx]['recalled_events']
            human_events = set(parse_event_string(human_events_str))
            
            # Skip if human has no events (can't compute accuracy)
            if len(human_events) == 0:
                continue
            
            # Compute intersection: model events matched with human
            intersection = model_events & human_events
            
            # Compute raw accuracy: intersection / human total events
            raw_acc = len(intersection) / len(human_events) if len(human_events) > 0 else 0.0
            segment_accuracies.append(raw_acc)
        
        # Average across all segments for this trial
        if segment_accuracies:
            trial_acc = np.mean(segment_accuracies)
            trial_accuracies.append(trial_acc)
    
    # Average across all trials
    if trial_accuracies:
        return np.mean(trial_accuracies)
    else:
        return 0.0


def compute_metrics_for_single_trial(model_df, human_df, num_events):
    """
    Compute all metrics (rval, raw_acc, weighted_acc) for a single trial.
    
    This function computes metrics for one model trial against human ratings,
    using the same logic as the multi-trial functions but for a single trial.
    
    Args:
        model_df: DataFrame containing model ratings for one trial
        human_df: DataFrame containing human ratings
        num_events: Total number of events in the story
    
    Returns:
        Tuple of (r_val, raw_acc, weighted_acc) or (None, None, None) if error
    """
    if model_df is None or human_df is None:
        return None, None, None
    
    # Import here to avoid circular imports
    from plot_matrix_comparison import create_matrix_from_ratings, resize_matrix
    
    # Create matrices
    model_matrix = create_matrix_from_ratings(model_df, num_events)
    human_matrix = create_matrix_from_ratings(human_df, num_events)
    
    if model_matrix is None or human_matrix is None:
        return None, None, None
    
    # Ensure same shape
    max_events = max(model_matrix.shape[0], human_matrix.shape[0])
    max_segments = max(model_matrix.shape[1], human_matrix.shape[1])
    
    if model_matrix.shape != (max_events, max_segments):
        model_matrix = resize_matrix(model_matrix, (max_events, max_segments))
    if human_matrix.shape != (max_events, max_segments):
        human_matrix = resize_matrix(human_matrix, (max_events, max_segments))
    
    # Compute rval: Pearson correlation between matrices
    r_val = compute_pearson_correlation(model_matrix, human_matrix)
    
    # Compute raw accuracy for this trial
    min_segments = min(len(model_df), len(human_df))
    segment_accuracies = []
    
    for seg_idx in range(min_segments):
        # Get model events for this segment
        model_events_str = model_df.iloc[seg_idx]['recalled_events']
        model_events = set(parse_event_string(model_events_str))
        
        # Get human events for this segment
        human_events_str = human_df.iloc[seg_idx]['recalled_events']
        human_events = set(parse_event_string(human_events_str))
        
        # Skip if human has no events (can't compute accuracy)
        if len(human_events) == 0:
            continue
        
        # Compute intersection: model events matched with human
        intersection = model_events & human_events
        
        # Compute raw accuracy: intersection / human total events
        raw_acc = len(intersection) / len(human_events) if len(human_events) > 0 else 0.0
        segment_accuracies.append(raw_acc)
    
    # Average across all segments for this trial
    raw_acc = np.mean(segment_accuracies) if segment_accuracies else 0.0
    
    # Compute weighted accuracy for this trial
    weighted_segment_accuracies = []
    
    for seg_idx in range(min_segments):
        # Get model events for this segment
        model_events_str = model_df.iloc[seg_idx]['recalled_events']
        model_events = set(parse_event_string(model_events_str))
        
        # Get human events for this segment
        human_events_str = human_df.iloc[seg_idx]['recalled_events']
        human_events = set(parse_event_string(human_events_str))
        
        # Skip if human has no events (can't compute accuracy)
        if len(human_events) == 0:
            continue
        
        # Skip if model has no events (weighted-hit would be 0)
        if len(model_events) == 0:
            weighted_segment_accuracies.append(0.0)
            continue
        
        # Compute weighted-hit: intersection / model total
        intersection = model_events & human_events
        weighted_hit = len(intersection) / len(model_events) if len(model_events) > 0 else 0.0
        
        # Compute total-match: human total events
        total_match = len(human_events)
        
        # Compute weighted accuracy for this segment
        if total_match > 0:
            weighted_acc = weighted_hit / total_match
            weighted_segment_accuracies.append(weighted_acc)
    
    # Average across all segments for this trial
    weighted_acc = np.mean(weighted_segment_accuracies) if weighted_segment_accuracies else 0.0
    
    return r_val, raw_acc, weighted_acc


def compute_weighted_accuracy(model_dfs, human_df, num_events):
    """
    Compute weighted accuracy across all model trials.
    
    For each recall segment:
    - weighted-hit = (model events matched with human events) / (model total events)
    - total-match = human returned events
    - weighted-acc = weighted-hit / total-match
    
    Average across all recall segments for each trial, then average across all trials.
    
    Args:
        model_dfs: List of DataFrames, each containing model ratings for one trial
        human_df: DataFrame containing human ratings
        num_events: Total number of events in the story
    
    Returns:
        Average weighted accuracy (float)
    """
    if not model_dfs or human_df is None:
        return 0.0
    
    trial_accuracies = []
    
    for model_df in model_dfs:
        segment_accuracies = []
        
        # Ensure both dataframes have same number of segments
        min_segments = min(len(model_df), len(human_df))
        
        for seg_idx in range(min_segments):
            # Get model events for this segment
            model_events_str = model_df.iloc[seg_idx]['recalled_events']
            model_events = set(parse_event_string(model_events_str))
            
            # Get human events for this segment
            human_events_str = human_df.iloc[seg_idx]['recalled_events']
            human_events = set(parse_event_string(human_events_str))
            
            # Skip if human has no events (can't compute accuracy)
            if len(human_events) == 0:
                continue
            
            # Skip if model has no events (weighted-hit would be 0)
            if len(model_events) == 0:
                segment_accuracies.append(0.0)
                continue
            
            # Compute weighted-hit: intersection / model total
            intersection = model_events & human_events
            weighted_hit = len(intersection) / len(model_events) if len(model_events) > 0 else 0.0
            
            # Compute total-match: human total events
            total_match = len(human_events)
            
            # Compute weighted accuracy for this segment
            if total_match > 0:
                weighted_acc = weighted_hit / total_match
                segment_accuracies.append(weighted_acc)
        
        # Average across all segments for this trial
        if segment_accuracies:
            trial_acc = np.mean(segment_accuracies)
            trial_accuracies.append(trial_acc)
    
    # Average across all trials
    if trial_accuracies:
        return np.mean(trial_accuracies)
    else:
        return 0.0

