# Helpers — Analysis, Plotting, and Test Scripts

Documentation for the **`helpers/`** directory (this file was moved here from `helpers/README.md`).

This folder contains helper modules and test scripts that are **not** part of the main app pipeline. The web app runs the numbered pipeline scripts (`scripts/1_audio-transcribe.py` through `scripts/6_causal-rater.py`) via `SCRIPTS_DIR` in `server/web-interface.py`.

## Modules (used by test scripts)

| Module | Purpose |
|--------|---------|
| `plot_matrix_comparison.py` | Create recall-segment vs story-event matrix plots; used by web app for matrix visualization |
| `plot_bar_metrics_comparison.py` | Bar charts comparing metrics (rval, raw-acc, weighted-acc) across conditions |
| `analysis_recall_metrics.py` | Compute Pearson correlation, raw accuracy, weighted accuracy between model and human ratings |
| `utils_recall_data.py` | Load human ratings, model ratings, and story event files |

## Test Scripts

| Script | Purpose |
|--------|---------|
| `test_recall_rater_single_subject.py` | Run recall rater on a single subject |
| `test_recall_rater_unrated.py` | Run recall rater on unrated recall files; generates matrix visualizations |
| `test_recall_rater_prompt_versions.py` | Test recall rater with different prompt versions (v1–v4) |
| `test_recall_rater_all_stories.py` | Run recall rater across all stories; matrix + bar plot output |
| `test_recall_rater_temperature.py` | Test recall rater at different temperatures |
| `test_story_event_segment.py` | Test story event segmentation API on a sample story |
| `test_bar_metrics_all_rated.py` | Bar plot comparing metrics across all rated stories |
| `test_bar_metrics_temperature.py` | Bar plot comparing metrics across temperatures |
| `test_matrix_comparison_multi_story.py` | Matrix comparison plots for multiple stories |
| `test_matrix_comparison_temperature.py` | Matrix comparison plots across temperatures |

## Usage

Run from project root:

```bash
python helpers/test_recall_rater_single_subject.py
python helpers/test_story_event_segment.py
python helpers/test_bar_metrics_all_rated.py
# etc.
```

## Importing Helper Modules

To use helper modules in your own script outside this folder:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'helpers'))
from plot_matrix_comparison import plot_matrix_comparison, create_matrix_from_ratings
from analysis_recall_metrics import compute_pearson_correlation
from utils_recall_data import load_human_rating
```
