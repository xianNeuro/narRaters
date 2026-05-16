#!/usr/bin/env python3
"""
Utility functions for loading recall rating data files.

Functions:
- load_human_rating: Load human rating file from multiple possible locations
- load_model_ratings: Load model rating files (single or multiple trials)
- load_event_file: Load story event file
"""

import pandas as pd
from pathlib import Path


def load_human_rating(subj_id, base_dir=None):
    """
    Load human rating file from multiple possible locations.
    
    Args:
        subj_id: Subject ID (e.g., 'subN_XXXX')
        base_dir: Base directory (defaults to current directory)
    
    Returns:
        DataFrame with human ratings, or None if not found
    """
    if base_dir is None:
        base_dir = Path(".")
    else:
        base_dir = Path(base_dir)
    
    possible_files = [
        base_dir / "data" / "human_ratings" / f"{subj_id}_rate-recall.xlsx",  # Check human_ratings first
        base_dir / "output" / "recall_rated" / f"{subj_id}_rate-recall.xlsx",
    ]
    
    for file in possible_files:
        if file.exists():
            try:
                return pd.read_excel(file)
            except Exception as e:
                continue
    
    return None


def load_model_ratings(subj_id, model_dir, pattern=None, temperature=None):
    """
    Load model rating files.
    
    Args:
        subj_id: Subject ID or story ID
        model_dir: Directory containing model rating files
        pattern: Optional glob pattern (if None, tries common patterns)
        temperature: Optional temperature value (for temp-specific patterns)
    
    Returns:
        List of DataFrames, one per model rating file
    """
    model_dir = Path(model_dir)
    
    if pattern is None:
        # Try multiple patterns
        if temperature is not None:
            pattern = f"{subj_id}_rate-recall_temp{temperature}_trial*.xlsx"
            files = sorted(model_dir.glob(pattern))
        else:
            # Try story pattern
            pattern1 = f"story_{subj_id}_claude_sonnet_4.5_run_*.xlsx"
            pattern2 = f"sub*_{subj_id}_rate-recall_temp*_trial*.xlsx"
            files = sorted(list(model_dir.glob(pattern1)) + list(model_dir.glob(pattern2)))
    else:
        files = sorted(model_dir.glob(pattern))
    
    dataframes = []
    for file in files:
        try:
            df = pd.read_excel(file)
            if 'recalled_events' in df.columns:
                dataframes.append(df)
        except Exception as e:
            continue
    
    return dataframes


def load_event_file(subj_id, base_dir=None):
    """
    Load event file from multiple possible locations.
    
    Args:
        subj_id: Subject ID (e.g., 'subN_XXXX')
        base_dir: Base directory (defaults to current directory)
    
    Returns:
        DataFrame with event data, or None if not found
    """
    if base_dir is None:
        base_dir = Path(".")
    else:
        base_dir = Path(base_dir)
    
    possible_files = [
        base_dir / "data" / "human_ratings" / f"{subj_id}_events.xlsx",  # Check human_ratings first
        base_dir / "data" / "3_story_events" / f"{subj_id}_events.xlsx",
        base_dir / "data" / "3_story_events" / "_prev" / f"{subj_id}_events.xlsx",
    ]
    
    for file in possible_files:
        if file.exists():
            try:
                df = pd.read_excel(file)
                if 'event' in df.columns:
                    return df
            except Exception as e:
                continue
    
    return None

