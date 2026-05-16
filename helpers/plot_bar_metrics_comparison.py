#!/usr/bin/env python3
"""
Core plotting functions for bar charts comparing metrics across conditions.

Functions:
- plot_metrics_bar_comparison: Create bar plot with error bars and swarm overlay
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path


def plot_metrics_bar_comparison(
    metrics_data,
    output_file=None,
    title="Metrics Comparison",
    ylabel="Score",
    figsize=(14, 8)
):
    """
    Create bar plot comparing metrics across conditions with error bars and swarm overlay.
    
    Bars are grouped by temperature, colored by measurement type.
    
    Args:
        metrics_data: Dictionary with structure:
            {
                'temperature_0': {
                    'rval': [list of trial values],
                    'raw_acc': [list of trial values],
                    'weighted_acc': [list of trial values]
                },
                'temperature_0.5': {...},
                'temperature_1': {...}
            }
        output_file: Path to save the plot (Path object or string)
        title: Plot title
        ylabel: Y-axis label
        figsize: Figure size tuple
    
    Returns:
        None (saves plot to file)
    """
    # Set random seed for reproducible jitter
    np.random.seed(42)
    
    metric_names = ['rval', 'raw_acc', 'weighted_acc']
    metric_labels = ['Pearson Correlation (rval)', 'Raw Accuracy', 'Weighted Accuracy']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # Blue, Orange, Green
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Set up positions for bars (grouped by temperature or single group)
    # Check if we have temperature-based data or single group
    has_temperatures = any('temperature_' in key for key in metrics_data.keys())
    
    if has_temperatures:
        temp_positions = {0: 0, 0.5: 1, 1: 2}
        metric_positions = {metric_labels[0]: -0.3, metric_labels[1]: 0, metric_labels[2]: 0.3}
        bar_width = 0.25
    else:
        # Single group (e.g., "all_stories")
        temp_positions = {'all_stories': 0}
        metric_positions = {metric_labels[0]: -0.3, metric_labels[1]: 0, metric_labels[2]: 0.3}
        bar_width = 0.25
    
    # Collect all values for y-axis limits
    all_values = []
    
    # Plot bars with error bars
    for temp_key, temp_data in metrics_data.items():
        if has_temperatures:
            temp_val = float(temp_key.split('_')[1])
            temp_pos = temp_positions[temp_val]
        else:
            temp_val = temp_key
            temp_pos = temp_positions.get(temp_val, 0)
        
        for metric_name, metric_label, color in zip(metric_names, metric_labels, colors):
            if metric_name in temp_data:
                trial_values = temp_data[metric_name]
                if len(trial_values) > 0:
                    all_values.extend(trial_values)
                    mean_val = np.mean(trial_values)
                    std_err = np.std(trial_values) / np.sqrt(len(trial_values)) if len(trial_values) > 1 else 0
                    x_pos = temp_pos + metric_positions[metric_label]
                    
                    # Plot bar (only add to legend for first group)
                    if has_temperatures:
                        label_condition = temp_val == 0
                    else:
                        label_condition = True  # Always label for single group
                    ax.bar(x_pos, mean_val, width=bar_width, color=color, alpha=0.7, 
                          label=metric_label if label_condition else '', 
                          edgecolor='black', linewidth=1.5)
                    
                    # Plot error bar
                    ax.errorbar(x_pos, mean_val, yerr=std_err, color='black', 
                               capsize=6, capthick=2, linewidth=2, alpha=0.9, zorder=5)
    
    # Plot swarm overlay (individual trial points)
    for temp_key, temp_data in metrics_data.items():
        if has_temperatures:
            temp_val = float(temp_key.split('_')[1])
            temp_pos = temp_positions[temp_val]
        else:
            temp_val = temp_key
            temp_pos = temp_positions.get(temp_val, 0)
        
        for metric_name, metric_label, color in zip(metric_names, metric_labels, colors):
            if metric_name in temp_data:
                trial_values = temp_data[metric_name]
                if len(trial_values) > 0:
                    x_pos = temp_pos + metric_positions[metric_label]
                    
                    # Add jitter to x position for swarm effect
                    n_trials = len(trial_values)
                    jitter_range = bar_width * 0.5
                    # Use deterministic jitter based on trial index for better visualization
                    jitter = np.linspace(-jitter_range/2, jitter_range/2, n_trials)
                    if n_trials > 1:
                        # Add small random component
                        jitter += np.random.normal(0, jitter_range * 0.1, n_trials)
                    x_jittered = x_pos + jitter
                    
                    # Plot individual points
                    ax.scatter(x_jittered, trial_values, color=color, s=80, alpha=0.7, 
                             edgecolors='black', linewidths=1, zorder=10)
    
    # Set x-axis
    if has_temperatures:
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(['Temperature = 0', 'Temperature = 0.5', 'Temperature = 1'])
        ax.set_xlabel('Temperature', fontsize=12, fontweight='bold')
    else:
        ax.set_xticks([0])
        ax.set_xticklabels(['All Stories'])
        ax.set_xlabel('', fontsize=12, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Add legend (only show once per metric)
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='best', fontsize=11, framealpha=0.9)
    
    # Add grid
    ax.grid(True, alpha=0.3, axis='y', linestyle='--', zorder=0)
    ax.set_axisbelow(True)
    
    # Set y-axis limits
    if all_values:
        y_min = min(all_values)
        y_max = max(all_values)
        y_range = y_max - y_min
        y_padding = y_range * 0.15
        ax.set_ylim(max(0, y_min - y_padding), min(1.1, y_max + y_padding))
    else:
        ax.set_ylim(0, 1)
    
    plt.tight_layout()
    
    # Save figure
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {output_path}")
    
    plt.close()

