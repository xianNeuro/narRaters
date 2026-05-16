# Demo Data

Documentation for the **`demo/`** sample dataset at the repository root (this file lives under **`developer/`**).

This folder contains demo/dummy data to illustrate the expected input format for each pipeline step. Use this data to test the pipeline without needing real experimental data.

## Directory Structure

```
demo/
├── data/
│   ├── 2_story_transcript/     ← Step 1 input: Story Event Segment
│   │   └── the_lighthouse.txt
│   └── 5_recall_texts/         ← Step 2 input: Spell & Grammar Correction
│       ├── the_lighthouse_sub-100000001.txt
│       ├── the_lighthouse_sub-100000002.txt
│       └── the_lighthouse_sub-100000003.txt
└── output/                     ← All processing outputs go here
```

## Input Formats by Step

### Step 1: Story Event Segment
- **Input folder:** `data/2_story_transcript/`
- **File format:** Plain `.txt` file containing the full story transcript
- **Naming:** `{story_name}.txt` (e.g., `the_lighthouse.txt`)
- **Content:** The complete story text, paragraph by paragraph

### Step 2: Spell & Grammar Correction
- **Input folder:** `data/5_recall_texts/`
- **File format:** Plain `.txt` file containing a subject's recall of the story
- **Naming:** `{story_name}_sub-{subject_id}.txt` (e.g., `the_lighthouse_sub-100000001.txt`)
- **Content:** Raw transcription of a participant's recall, including filler words, false starts, repetitions, etc.

### Step 3: Recall Parse to Segments
- **Input:** Output from Step 2 (`output/recall_corrected/`)
- **File format:** `.txt` file with filename on line 1 and corrected text on subsequent lines
- **Naming:** `{story_name}_sub-{subject_id}.txt`

### Step 4: Recall Match to Story Events
- **Input:** Output from Steps 1 and 3
  - Story events: `data/3_story_events/{story_name}_events-{method}.xlsx` (Excel with `event` and `story_texts` columns)
  - Parsed recalls: `output/recall_parsed/{story_name}_sub-{subject_id}_parsed.xlsx` (Excel with `unit` and `recall_texts` columns)

## How to Use

1. In the web interface, go to **Pipeline Config** and set the input paths to point to this demo folder:
   - Story Event Segment input: `demo/data/2_story_transcript`
   - Spell & Grammar Correction input: `demo/data/5_recall_texts`
   - Set output paths to `demo/output/...` as needed
2. Or run scripts directly:
   ```bash
   python scripts/2_story-event-segment.py --input demo/data/2_story_transcript/the_lighthouse.txt --method fine
   python scripts/3_spell-grammar-correct.py  # with BATCH_INPUT_DIR=demo/data/5_recall_texts
   ```
