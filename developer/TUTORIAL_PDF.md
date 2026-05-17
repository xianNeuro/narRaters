# Tutorial PDF (maintainer only)

`developer/` is gitignored on the public checkout — scripts live in your source tree locally.

## Regenerate `narRater_Tutorial.pdf`

```bash
pip install fpdf2 playwright
playwright install chromium

narraters serve --no-browser --host 127.0.0.1   # Terminal A
python developer/capture_tutorial_screenshots.py
python developer/generate_tutorial_pdf.py
```

Output PDF: **`narRater_Tutorial.pdf`** at the repo root (commit alongside releases when screenshots change).

Captured PNG folder: **`tutorial_screenshots/`** (ignored by `.gitignore` until you rebuild the bundle).

Environment overrides (`capture_tutorial_screenshots.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `NARRATERS_URL` | `http://127.0.0.1:5000` | Running server base URL (`localhost` is unreliable on IPv6-heavy macOS setups). |
| `SHOT_STORY` | `the_siren` | Story row screenshots (`05*` / `06*` / causal). |
| `SHOT_STORY_AUDIO_STORY` | `pieman_edited` | Story with bundled `.wav` for `13_story_audio_transcription_tab.png`. |
| `SHOT_SUBJECT` | `the_siren_sub-01` | Recall subject for tab strip shots `07*`‑`12*`. |

## Expected PNG filenames (must stay aligned with `generate_tutorial_pdf.py`)

| Filename | Intended UI |
|-----------|--------------|
| `01_pipeline_rater.png` | `/pipeline-config` — empty palette, inactive Continue |
| `03_pipeline_config.png` | Same page with multi-step Pipeline Flow staged |
| `04_dashboard.png` | `/` — status grid populated from bundled data |
| `05_story_detail.png` | `/story/<SHOT_STORY>` default tab strip |
| `06_story_events.png` | `/story/<SHOT_STORY>/step0` — segmented events inspector |
| `07_subject_detail.png` | `/subject/<SHOT_SUBJECT>` immediately after dashboard click-through |
| `08_subject_recall_audio_tab.png` | Recall inspection — Audio Transcription tab |
| `09_subject_corrected_recall_tab.png` | Recall inspection — Corrected Recall |
| `10_subject_parsed_recall_tab.png` | Recall inspection — Parsed Recall |
| `11_subject_recall_matching_tab.png` | Recall inspection — Recall Matching |
| `12_subject_story_segments_reference_tab.png` | Subject row — contextual Story Segments reference tab (when surfaced) |
| `13_story_audio_transcription_tab.png` | `/story/<SHOT_STORY_AUDIO_STORY>/step0_story_audio` |
| `14_story_causal_rating_tab.png` | `/story/<SHOT_STORY>/step0_causal` — matrix UI |

If any capture fails (missing bundled data / palette rename / Continue disabled because of validation), the PNG will be stale or absent and `generate_tutorial_pdf.py` prints a `[Screenshot not found]` placeholder — fix upstream data/layout, then rerun the capture script.

Ship the regenerated PDF via Git bundles or Releases; screenshots themselves stay out of Git unless you explicitly check them into an internal mirror.
