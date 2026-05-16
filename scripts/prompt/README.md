# Prompt Files

This folder lives under **`scripts/prompt/`** next to the pipeline CLI scripts. It contains plain-text templates used by the LLM-based pipeline methods.

## Current Prompts

- **`event_segment.txt`** — Used by `scripts/2_story-event-segment.py` (API method). Instructs the model to copy a story word-for-word and segment it into events.
- **`recall_rating.txt`** — Used by `scripts/5_recall-rater.py` (API method). Instructs the model to match recall segments to story events and output a JSON array.

## Using Custom Prompt Versions

You can create additional prompt versions and select them at runtime.

**Recall rating prompts** — name them `recall_rating_v2.txt`, `recall_rating_v3.txt`, etc.:
```bash
export RECALL_RATING_PROMPT="recall_rating_v2"
python scripts/5_recall-rater.py
```
The default file is `recall_rating.txt` (loaded as `recall_rating_v1`). If the file is not found, a hardcoded fallback prompt is used.

**Event segmentation prompts** — name them `event_segment_v2.txt`, etc.:
```bash
python scripts/2_story-event-segment.py --method api --prompt-version event_segment_v2.txt
python scripts/2_story-event-segment.py --list-prompts
```
The default file is `event_segment.txt`.

## Adding a New Prompt

1. Create a new file in this folder (e.g. `recall_rating_v2.txt`)
2. Write your prompt text
3. Select it via environment variable or command-line argument as shown above
