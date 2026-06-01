<p align="center">
  <a href="../README.md">README</a> &nbsp;·&nbsp;
  <a href="install.md">Install</a> &nbsp;·&nbsp;
  <strong>Input data</strong> &nbsp;·&nbsp;
  <a href="web-interface.md">Web interface</a> &nbsp;·&nbsp;
  <a href="troubleshooting.md">Troubleshooting</a> &nbsp;·&nbsp;
  <a href="command-line.md">Command-line</a> &nbsp;·&nbsp;
  <a href="../LICENSE">License</a>
</p>

---

## Where to put your data

After [installation](install.md#installation), place files so the paths match what you configured on the **pipeline** page (defaults below are relative to the **project root**). You can **remap** any step’s input/output folders there without moving data.

| You have… | Put it in… | Format / naming |
|---|---|---|
| Story transcript (text) | `data/2_story_transcript/` | `{story}.txt` — plain UTF-8 text, one story per file |
| Story event list (pre-segmented) | `data/3_story_events/` | `{story}_events.xlsx` — columns `event`, `story_texts` |
| Subject recall text | `data/5_recall_texts/` | `{subj_id}.txt` — e.g. `the_siren_sub-01.txt` |
| Story audio (optional, Step 1) | `data/1_story_audio/` | `.wav` / `.mp3` / `.m4a`, named by story |
| Recall audio (optional, Step 1) | `data/4_recall_audio/` | `.wav` / `.mp3` / `.m4a`, named by subject |

Outputs are written under `output/` — one subdirectory per step (`output/recall_corrected/`, `output/recall_parsed/`, `output/recall_rated/`, …). A smaller alternate layout lives in **`demo/data/`** (lighthouse story, three recall `.txt` files).

### Bundled examples (`pieman_edited`, `the_siren`)

The repository ships **realistic sample inputs and outputs** under `data/` and `output/` so you can see accepted naming and file types before adding your own study. Your private files in those folders stay untracked (see `.gitignore`); only the examples below are committed.

**Stories:** **`pieman_edited`** (story audio + transcript + events) and **`the_siren`** (transcript, events, two recall subjects).

| Role | Folder | Example file(s) |
|------|--------|-----------------|
| Story audio (input) | `data/1_story_audio/` | `pieman_edited.wav` |
| Story transcript (input) | `data/2_story_transcript/` | `pieman_edited.txt`, `the_siren.txt` |
| Story events (input) | `data/3_story_events/` | `pieman_edited_events.xlsx`, `the_siren_events.xlsx` |
| Recall audio (input) | `data/4_recall_audio/` | Your own `.wav` / `.mp3` / `.m4a` / `.mp4` (not shipped publicly) |
| Recall text (input) | `data/5_recall_texts/` | `the_siren_sub-01.txt`, `the_siren_sub-02.txt` |
| Story transcription (output) | `output/story_audio-transcribed/` | `pieman_edited.txt` |
| Recall transcription (output) | `output/recall_audio-transcribed/` | `the_siren_sub-01.txt`, `the_siren_sub-02.txt` |
| Spell/grammar correction (output) | `output/recall_corrected/` | `the_siren_sub-01.txt`, `the_siren_sub-02.txt` |
| Parsed recall (output) | `output/recall_parsed/` | `the_siren_sub-01_parsed.xlsx`, `the_siren_sub-02_parsed.xlsx` |
| Recall ↔ events (output) | `output/recall_rated/` | `the_siren_sub-02_rate-recall-test_mode.xlsx` (method slug in filename) |
| Causal ratings (output) | `output/causal_rated/` | `pieman_edited_causal-linguistic.xlsx`, `the_siren_causal-linguistic.xlsx` |

**Quick try:** after install, point a pipeline at the default folders above and run **`sentenceCorrect` → `textParsing` → `textMatching`** on `the_siren_sub-01` / `the_siren_sub-02`, or open the bundled **`output/`** files in Excel to inspect column layouts. Story **`pieman_edited`** is useful for **`audioTranscribe`** (large `.wav`) and **`causalRating`** on `pieman_edited_events.xlsx`.

**File versioning is a core feature.** Automated runs write `{subj_id}_{method}.ext` (or `{story}_…` for story-level steps); your hand-edited versions are saved as `{subj_id}_{ratername}-edit.ext` and never overwrite the originals. The web UI lets you switch between versions via a dropdown, and the `-edit` files are what you export for analysis.
