# Narrative Processing Project

Developer handbook for this repository. **New here?** Start with the short [root README](../README.md), then return here for pipeline details.

## Local AI assistant context (private)

Files used only by coding agents (for example **`CLAUDE.md`** at the repository root and the **`.cursor/`** directory) are **gitignored** and are not part of the public GitHub tree. Maintain your own local copies for Cursor / Claude Code / similar workflows. Contributor-facing project facts live in this handbook and the root `README.md` — do not commit agent-specific guidance or internal maintainer notes you intend to stay private.

## Project Overview

This project processes narrative recall data from subjects through a multi-step pipeline that transforms raw recall text into corrected, parsed, and matched formats suitable for analysis. The project maintains strict protocols to preserve the original narrative structure, meaning, and style while fixing errors, organizing content, and matching recall segments to story events.

## Project Structure

```
2_narrative-processor/
├── data/                          # Input data directory
│   ├── summary_*.xlsx            # Source Excel files with recall data (one per condition)
│   ├── 1_story_audio/            # Story audio files (.wav, .mp3, .mp4, .m4a, etc.)
│   ├── 2_story_transcript/       # Story transcript files (if any, to be segmented)
│   ├── 3_story_events/           # Story event files (segmented)
│   │   ├── {story_name}_events.xlsx
│   │   └── ...
│   ├── 4_recall_audio/           # Recall audio files (.wav, .mp3, .mp4, .m4a, etc.)
│   │   ├── {subject_id}_recall.wav
│   │   └── ...
│   └── 5_recall_texts/           # Raw recall text files
├── output/                       # All processing outputs
│   ├── recall_corrected/         # Spell/grammar correction output
│   ├── recall_parsed/            # Parsing output
│   ├── recall_rated/             # Recall rating output
│   ├── causal_rated/             # Causal relationship rating output
│   ├── recall_audio-transcribed/ # Recall audio transcription output
│   └── story_audio-transcribed/  # Story audio transcription output
├── server/                       # Web viewer server
│   ├── web-interface.py         # Flask web server application
│   └── START_HERE.command        # Main launcher (double-click to start)
├── templates/                    # Web viewer HTML templates
│   ├── index.html                # Main dashboard page
│   ├── login.html                # Login / account creation page
│   ├── pipeline-config.html      # Pipeline configuration page
│   └── subject.html              # Individual subject detail page
├── packaging/
│   └── macos/
│       ├── build_app_bundle.sh   # Builds narRater.app (macOS dock icon)
│       └── render_app_icon.py    # Regenerate static/app-icon.png (login + bundle)
├── static/                       # Static assets (JS, app-icon.png for login)
├── helpers/                      # Analysis, plotting, and test scripts (see developer/helpers.md)
├── developer/                    # Markdown docs for developers (this handbook, API setup, etc.)
├── manage/                       # User account records
├── tutorial_screenshots/         # Screenshots for tutorial PDF generation
├── Narrative_Processor_Tutorial.pdf
├── generate_tutorial_pdf.py      # Builds the tutorial PDF from screenshots
├── scripts/                      # Pipeline CLIs, shell helpers, and LLM prompts
│   ├── prompt/                   # LLM prompt templates (see scripts/prompt/README.md)
│   ├── 1_audio-transcribe.py     # Step 1: Audio transcription
│   ├── 2_story-event-segment.py  # Step 2: Story event segmentation
│   ├── 3_spell-grammar-correct.py # Step 3: Spell/grammar correction
│   ├── 4_parse-texts.py          # Step 4: Recall text parsing
│   ├── 5_recall-rater.py         # Step 5: Recall rating / event matching
│   ├── 6_causal-rater.py         # Step 6: Causal relationship rating between event pairs
│   ├── run_event_segment.sh      # Shell helper: run event segmentation with API
│   ├── run_recall_rater.sh       # Shell helper: run recall rater with API
│   └── setup_api_key.sh          # Interactive API key setup script
├── pipeline_config.json          # Active pipeline configuration (created by web UI)
├── requirements.txt              # Python dependencies
├── README.md                     # Short entry point; links here for full docs
└── .env                          # Local secrets (not committed; copy from developer/.env.example)
```

## Data Directory Structure

The project uses a numbered directory structure within `data/` to organize different types of input files:

- **`data/1_story_audio/`**: Story audio files (.wav, .mp3, .mp4, .m4a, .flac, .ogg, .webm, .aac)
- **`data/2_story_transcript/`**: Story transcript files (if any, to be segmented into events)
- **`data/3_story_events/`**: Story event files (segmented story, one file per subject)
  - Naming: `{story_name}_events.xlsx`
  - Contains columns: `event`, `story_texts`, and optionally `old_seg`, `scenes`
- **`data/4_recall_audio/`**: Recall audio files (.wav, .mp3, .mp4, .m4a, .flac, .ogg, .webm, .aac)
  - Naming: `{subj_id}_recall*.mp4` or similar patterns
- **`data/5_recall_texts/`**: Raw recall text files (individual `.txt` files, one per subject)
  - Used as input for Step 3 (spell/grammar correction)

## Processing Pipeline

The narrative processing pipeline consists of several steps. Each step has one or more automated **methods** and always includes a **Manual** option for human editing.

### Step 1: Audio Transcription (`scripts/1_audio-transcribe.py`)
- **Input**: Audio files from `data/4_recall_audio/` or `data/1_story_audio/`
- **Output**: `output/recall_audio-transcribed/{audio_filename}.txt` or `output/story_audio-transcribed/{audio_filename}.txt`
- **Available methods**:
  | Method | Description |
  |--------|-------------|
  | **Automatic (WhisperX / Whisper)** | Preferred engine is WhisperX (batched inference with word-level alignment); falls back to standard Whisper. Default model: `large-v2` (WhisperX) or `medium` (Whisper). Verbatim transcription in English. |
  | **Manual** | Creates an empty transcript file. Open the Audio Transcription tab in the detail view to listen to the audio and type or paste the transcription. |

### Step 2: Story Events Segmentation (`scripts/2_story-event-segment.py`)
- **Input**: Story transcript from `data/2_story_transcript/` (`.txt` files)
- **Output**: `data/3_story_events/{story_name}_events.xlsx` (columns: `event`, `story_texts`)
- **Granularity hierarchy**: Clause (finest) → Fine-grained → Coarse-grained (broadest). Each level is built compositionally on the one below it: every fine-grained event is exactly one or more consecutive clause-level segments, and every coarse-grained event is exactly one or more consecutive fine-grained events. This guarantees that boundaries at a coarser level always coincide with boundaries at the finer level.
- **Fundamental constraint**: Every segment at every level must contain at least one **independent clause** (a clause with a subject and a finite verb that can stand alone). Fragments, interjections, and bare noun phrases are merged with neighbouring segments. Dialogue speech acts (quoted text) are exempt from this rule.
- **Optional NLP enhancement**: If `spacy` is installed (with optional `benepar` for constituency parsing), dependency parsing is used for more accurate clause boundary detection. Otherwise regex heuristics are applied. Install with: `pip install spacy && python -m spacy download en_core_web_sm`
- **Available methods**:
  | Method | Description |
  |--------|-------------|
  | **Clause Level** | Finest granularity — the atomic unit. Splits at independent clause boundaries. No API key. |
  | **Fine-Grained** (default) | Each discrete event (action, state change, dialogue turn). Built by merging consecutive clause-level segments within the same sentence. No API key. |
  | **Coarse-Grained** | Scene-level segmentation. Built by merging consecutive fine-grained events across major narrative boundaries. No API key. |
  | **API (LLM Call)** | Uses a language model (Claude Sonnet 4.5, Haiku 3.5, GPT-4o, GPT-4o Mini, **Gemma 4 E4B via Ollama**, or optional Llama tags via Ollama) with prompt files from `scripts/prompt/event_segment*.txt`. Cloud models require an API key; Ollama presets require a local `ollama serve` and pulled models (e.g. `ollama pull gemma4:e4b`). |
  | **Manual** | Places the full story transcript as a single event. Open the Story Segments tab to manually split events using the Split/Merge buttons. |

#### Segmentation Rules by Method

**Clause Level** (finest granularity — the atomic unit):
1. **SPLIT** at sentence boundaries (`.` `!` `?` followed by uppercase letter), skipping abbreviations (Dr., Mr., p.m., etc.)
2. **SPLIT** at semicolons (always separate independent clauses)
3. **SPLIT** at non-restrictive relative clauses: `, who/which/whom`
4. **SPLIT** at speech attribution + direct speech boundaries (`said`, `asked`, etc.)
5. **SPLIT** at commas between independent clauses (subject + verb on both sides, ≥ 6 words before)
6. **SPLIT** at coordinating conjunctions (`and`/`but`/`so`/`yet`) between independent clauses with different subjects
7. **NEVER SPLIT**: subordinate + main clause, time/place + action, participial continuations, same subject with "and"
8. **POST-PROCESS**: proof-check pass merges unjustified fragments (bare time phrases, dangling subordinates, trailing conjunctions); independent-clause validation pass merges any remaining non-IC segments

**Fine-Grained** (event level — each event = 1+ consecutive clause segments):

Built on clause-level output. Consecutive clause segments are merged into one event unless a split condition is met:
1. **SPLIT** at sentence boundaries — clauses from different sentences are always separate events
2. **KEEP SPLIT** at temporal transitions (`and then`/`eventually`/`later`/`suddenly`/`next`/`finally`) when the current group has ≥ 5 words
3. **KEEP SPLIT** at contrast transitions (`but`) when the current group has ≥ 8 words
4. **MERGE** consecutive very short events (both ≤ 3 words) into a single event

**Coarse-Grained** (scene level — each event = 1+ consecutive fine-grained events):

Built on fine-grained output. Consecutive fine-grained events are merged into one scene block unless a split condition is met:
1. **SPLIT** at strong narrative transitions (`Later`, `Eventually`, `Meanwhile`, `Finally`, `The next day`, `Suddenly`, `In the end`, `Back at`, etc.) when the current block has ≥ 15 words
2. **SPLIT** when a block exceeds ~100 words (forced cap)
3. All other fine-grained events accumulate into the current scene block

### Step 3: Spell and Grammar Correction (`scripts/3_spell-grammar-correct.py`)
- **Input**: Raw recall text from `data/5_recall_texts/` (individual `.txt` files) or `data/summary_*.xlsx`
- **Output**: `output/recall_corrected/{subj_id}.txt` for rule-based correction; Gemma methods also write `{subj_id}_spell-gemma-hf_{model-slug}.txt` or `{subj_id}_spell-ollama_{tag-slug}.txt` so different runs can coexist (prompt: `scripts/prompt/spell_gram.txt`).
- **Available methods**:
  | Method | Description |
  |--------|-------------|
  | **Automatic (Rule-Based)** (default) | Multi-pass pipeline: abbreviation protection, contraction repair, grammar fixes (i→I), capitalization, common misspellings, punctuation cleanup, pyspellchecker (with whitelist, proper nouns, acronyms), and optional LanguageTool. |
  | **Gemma 4 (Hugging Face, local)** | Local `google/gemma-4-E4B-it` (override via `--gemma-model` / `SPELL_GRAM_GEMMA_MODEL`) using `scripts/prompt/spell_gram.txt`. Requires PyTorch + transformers (GPU recommended). |
  | **Gemma 4 (Ollama, local)** | Same prompt via Ollama HTTP API; default tag `gemma4:e4b` (`SPELL_GRAM_OLLAMA_MODEL`, `OLLAMA_HOST`). |
  | **Manual** | Copies the raw input text to the output folder. Open the Corrected Recall tab to manually correct the text side-by-side with the original. |
- **Detailed automatic processing rules**:
  - Abbreviation protection (p.m., a.m., e.g., i.e., etc.) via placeholders
  - Contraction repair (could't → couldn't, etc.)
  - Grammar fixes ("i" → "I", "i a," → "I am,")
  - Capitalization after sentence-ending punctuation (not after abbreviation periods)
  - Common misspellings (seperate → separate, recieve → receive, etc.)
  - Punctuation cleanup (spaces, duplicates, misplaced periods)
  - Spell-check with whitelist, Roman numerals, acronyms, proper nouns; blocks plural→singular and adjective→verb changes
  - LanguageTool (optional): additional grammar fixes, skips style/typography/semantics

### Step 4: Recall Text Parsing (`scripts/4_parse-texts.py`)
- **Input**: Corrected recall text from `output/recall_corrected/` (see Step 3 naming; the interface prefers `{subj_id}.txt` when present, otherwise the newest `{subj_id}_spell-*.txt`).
- **Output**: `output/recall_parsed/{subj_id}_parsed.xlsx` for clause rules (columns: `recalled_events`, `recall_in_temporal_order`); Ollama Gemma uses `{subj_id}_parsed-ollama_{tag-slug}.xlsx` with `scripts/prompt/recall_parse_clause.txt`.
- **Fundamental constraint**: Same as story segmentation — every parsed segment must contain at least one independent clause. Uses the same independent-clause validation from `scripts/2_story-event-segment.py`.
- **Available methods**:
  | Method | Description |
  |--------|-------------|
  | **Automatic (Clause-Based)** (default) | Clause-level parsing using the same rules as clause-level story segmentation (see above). Includes proof-check pass and independent-clause validation. |
  | **Gemma 4 (Ollama, local)** | Segmentation via local Ollama (`RECALL_PARSE_METHOD=ollama`, default model tag `gemma4:e4b`, `RECALL_PARSE_OLLAMA_MODEL`, `scripts/prompt/recall_parse_clause.txt`). |
  | **Manual** | Places the full corrected text as a single segment. Open the Parsed Recall tab to manually split segments using the Split/Merge buttons. |
- **Splitting rules** (automatic mode):
  1. Sentence boundaries (`.`, `!`, `?` followed by capital letter, ignoring abbreviation periods)
  2. Closing-quote sentence boundaries (`.` `!` `?` + `"` correctly keeps quote with its sentence)
  3. Semicolons (always split)
  4. Non-restrictive relative clauses (`, who/which/whom` with own verb)
  5. Commas between independent clauses (≥ 6 words before, new subject+verb after)
  6. Coordinating conjunctions (`and`/`but`/`so`/`yet`) between independent clauses with different subjects
- **Never splits**: subordinate+main clause, time/place+action, participial continuations, same subject with "and"
- **Post-processing**: proof-check merges unjustified fragments; IC validation merges remaining non-IC segments

### Step 5: Recall Rating — Match to Story Events (`scripts/5_recall-rater.py`)
- **Input**: Parsed recall segments from `output/recall_parsed/` and story events from `data/3_story_events/`
- **Output**: `output/recall_rated/{subj_id}_rate-recall.xlsx` or method-specific names such as `{subj_id}_rate-recall-api_{model}.xlsx` or `{subj_id}_rate-recall-ollama_{tag}.xlsx` (columns: `recalled_events`, `recall_in_temporal_order`)
- **Available methods**:
  | Method | Description |
  |--------|-------------|
  | **Test Mode** (default) | Keyword/phrase matching without API. Uses phrase overlap, concept matching, and word overlap with score thresholds. Returns up to 3 matched events per segment. |
  | **API (Claude Sonnet)** | Uses Claude Sonnet 4.5 via Anthropic API. Batch-processes all segments in one API call, outputs JSON mapping each recall row to event number(s). Requires ANTHROPIC_API_KEY. |
  | **Gemma 4 (Ollama, local)** | Same batch JSON contract and `scripts/prompt/recall_rating.txt` as the Claude path, executed via Ollama (`RECALL_RATING_BACKEND=ollama`, default `RECALL_RATING_OLLAMA_MODEL=gemma4:e4b`). |
  | **Manual** | Copies parsed segments with empty event-match fields. Open the Recall Matching tab to manually assign story event numbers to each recall segment. |

### Step 6: Causal Relationship Rating (`scripts/6_causal-rater.py`)
- **Input**: Event-segmented story files from `data/3_story_events/` (`.xlsx` files with `event`, `story_texts` columns)
- **Output**: `output/causal_rated/{story_name}_causal-{method}.xlsx` (columns: `event_A_number`, `event_B_number`, `rating`, `reasoning`)
- **Available methods**:
  | Method | Description |
  |--------|-------------|
  | **Linguistic** (default) | Rule-based causal scoring using causal connectives (from CREST/BECauSE causal relation literature), entity continuity, action-consequence verb patterns, and content overlap. Uses spaCy for enhanced NLP if installed, otherwise regex heuristics. No API key required. |
  | **API (LLM Call)** | Uses a language model (Claude Sonnet 4.5, Haiku 3.5, GPT-4o, GPT-4o Mini) with prompt from `scripts/prompt/causal_rating*.txt`. Requires API key. |

- **Approach**: Inspired by causal relation extraction research (CREST schema, CausalLearn, BECauSE corpus). Both proximal (adjacent) and distal (non-adjacent) event pairs are judged with identical criteria — no adjacency bonus.
- **Linguistic scoring dimensions**: (1) Explicit causal connectives (because, caused, led to, etc.), (2) Entity continuity across events, (3) Action-consequence verb patterns, (4) Content word overlap (low weight), (5) SVO argument chain detection (spaCy only)
- **Rating scale**: 1-10 integer. Only pairs with rating >4 are included in output.
- **Output columns**:
  - `event_A_number`: First event in the causal pair
  - `event_B_number`: Second event in the causal pair
  - `rating`: Causal strength rating (5-10)
  - `reasoning`: Explanation of the causal signals detected

## Input Data Format

### Source Excel Files
**Location**: `data/summary_*.xlsx` (one file per condition)

**Sheet**: `all` (or `Sheet1` if `all` doesn't exist)

**Required Columns**:
- `sub`: Subject identifier (numeric, e.g., 2, 3, 4)
- `ID`: Subject ID number (numeric, e.g., 1001, 1002, 1003)
- `recall`: Narrative recall text (string)

### Story Events Files
**Location**: `data/3_story_events/{subj_id}_events.xlsx`

**Required Columns**:
- `event`: Event number (integer)
- `story_texts`: Story text for this event (string)

**Optional Columns**:
- `old_seg`: Previous segmentation
- `scenes`: Scene information

## Output Data Formats

### Step 1 Output: `output/recall_corrected/`
**File Format**: Plain text files (`.txt`)

**Naming Convention**: `{subj_id}.txt` (rule-based), `{subj_id}_spell-gemma-hf_*.txt` / `{subj_id}_spell-ollama_*.txt` (local Gemma), or `{subj_id}_{username}-edit.txt` (user edit)
- Example: `{subject_id}.txt`, `{subject_id}_{username}-edit.txt`

**File Structure**:
```
{filename}.txt
{corrected_text_content}
```

### Step 2 Output: `output/recall_parsed/`
**File Format**: Excel files (`.xlsx`)

**Naming Convention**: `{subj_id}_parsed.xlsx` (clause rules), `{subj_id}_parsed-ollama_*.xlsx` (Ollama Gemma), or `{subj_id}_parsed_{username}-edit.xlsx` (user edit)

**Columns** (in order):
- `recalled_events`: Matched story event number(s) (initially empty, filled in Step 5)
- `recall_in_temporal_order`: Parsed recall segment text

### Step 3 Output: `output/recall_rated/`
**File Format**: Excel files (`.xlsx`)

**Naming Convention**: `{subj_id}_rate-recall.xlsx` (automated) or `{subj_id}_rate-recall_{username}-edit.xlsx` (user edit)

**Columns** (in order):
- `recalled_events`: Matched story event number(s) (comma-separated if multiple)
- `recall_in_temporal_order`: Recall segment text

### Audio Transcription Output: `output/recall_audio-transcribed/`
**File Format**: Plain text files (`.txt`)

**Naming Convention**: `{audio_filename}.txt` (automated) or `{audio_filename}_{username}-edit.txt` (user edit)

## Running the Pipeline

### Web Viewer (Recommended)

1. **Start the server:**
   - **macOS app icon:** The repository already ships a portable `narRater.app` next to `server/`, `static/`, `templates/`; double-click it to open Terminal, start the server, and open the login page. The bundle resolves both the project root and the Python interpreter at launch time, so it works on any Mac without a rebuild — just keep `narRater.app` as a sibling of `server/`. Re-run `bash packaging/macos/build_app_bundle.sh` only if you've changed the launcher source or want to refresh the icon. The login page and bundle use `static/app-icon.png`; to regenerate the default narrative-themed squircle icon (open book + story thread, purple gradient), run `python3 packaging/macos/render_app_icon.py`.
   - **Alternative:** Double-click `server/START_HERE.command` (macOS)
   - Browser opens automatically to pipeline configuration page when using START_HERE; the `.app` opens the login URL first.

2. **Configure pipeline:**
   - Drag steps from palette to build your pipeline
   - Configure input/output paths for each step
   - Click "Confirm Pipeline"

3. **Process data:**
   - View individual subjects and edit data
   - Use "Batch Process" button to run scripts on all files
   - Each step can be processed individually or in sequence

### Command Line

You can also run scripts directly from the command line (from the `software/` project root so `data/`, `scripts/prompt/`, and `output/` paths resolve as documented):

1. **Audio Transcription**:
   ```bash
   python scripts/1_audio-transcribe.py
   ```

2. **Story Event Segmentation** (if story transcript available):
   ```bash
   python scripts/2_story-event-segment.py
   ```
   Or reconstruct story from existing events:
   ```bash
   python scripts/2_story-event-segment.py --reconstruct data/3_story_events/{story_name}_events.xlsx output.txt
   ```

3. **Spell and Grammar Correction**:
   ```bash
   python scripts/3_spell-grammar-correct.py
   ```

4. **Parse Texts**:
   ```bash
   python scripts/4_parse-texts.py
   ```

5. **Rate Recall**:
   ```bash
   python scripts/5_recall-rater.py
   ```

6. **Causal Rating**:
   ```bash
   python scripts/6_causal-rater.py
   python scripts/6_causal-rater.py --method linguistic
   python scripts/6_causal-rater.py --method api --model gpt-4o
   python scripts/6_causal-rater.py --input data/3_story_events/my_story_events.xlsx
   ```

All outputs are saved to the `output/` directory.

### Test and Analysis Scripts

Test and analysis scripts live in `helpers/`. Run from project root:
```bash
python helpers/test_recall_rater_single_subject.py
python helpers/test_story_event_segment.py
```
See `developer/helpers.md` for the full list.

## Human Editing (Manual Rating & Correction)

The web interface supports full manual editing of both raw input files and automated output files at every step. There are two workflows:

### Workflow A: Edit automated output
1. Run any step using one of its automated methods (e.g., Fine-Grained for story segmentation, Rule-Based for spell-check).
2. Click the output status icon (magnifying glass) in the dashboard to open the detail view.
3. The detail view shows the input on the left and the output on the right. Edit the output directly.
4. Click **Export Edited File** to save. The file is saved as `{name}_{username}-edit.{ext}` (where `{username}` is your logged-in account name) in the same output folder.

### Workflow B: Start from raw source (Manual method)
1. Click the step's progress bar in the dashboard to select a method.
2. Choose **Manual**. This copies the step's input file into the output area as a starting point:
   - **Spell & Grammar**: raw text copied as-is for manual correction
   - **Recall Parse**: full corrected text placed as one segment — use Split/Merge to segment manually
   - **Story Segmentation**: full transcript placed as one event — use Split/Merge to segment manually
   - **Recall Matching**: parsed segments copied with empty event fields — assign event numbers manually
   - **Audio Transcription**: empty file created — type or paste the transcription while listening
3. Open the detail view and edit as needed, then export.

### Editing controls per tab
| Tab | Left panel | Right panel (editable) | Actions |
|-----|-----------|----------------------|---------|
| **Audio Transcription** | Audio player + read-only transcript | Editable transcript text | Export |
| **Story Segments** | Full story transcript | Event segments with text editors | Split, Merge, Export |
| **Corrected Recall** | Raw recall text | Corrected text editor | Export |
| **Parsed Recall** | Story events reference | Parsed segments with text editors | Split, Merge, Export |
| **Recall Matching** | Story events reference | Recall segments with event-match editors | Export |

### File version selector
The detail view header includes a **File Version** dropdown. When both automated output and user-edited versions exist, you can switch between them. The dropdown shows each editor's username (e.g., "editor1 (edit)") alongside "Original".

## Key Principles

1. **Preserve Original Text**: All corrections and parsing preserve the original text verbatim — no rewriting, summarizing, or paraphrasing
2. **Minimal Corrections**: Only fix spelling and grammar errors, do not change sentence structure
3. **Natural Segmentation**: Parse at natural sentence boundaries, splitting only when a sentence contains multiple events
4. **Human-Editable**: All outputs can be manually edited through the web viewer, with edits saved as `_{username}-edit` files

## User Accounts

- Each user creates an account with a unique username (letters, numbers, underscores) and password on the login page.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes (200 000 iterations, per-user 16-byte salt).
- Account data lives **outside the installed package** so it isn't shared between users of a pip-installed copy or wiped on upgrade: `~/.narraters/users.json` and `~/.narraters/manage/user_records.json` (override the parent directory with the `NARRATERS_DATA_DIR` env var). Both files are created with owner-only (`0600`) permissions. On first run after upgrading, any legacy `server/users.json` / `manage/user_records.json` in the project root is migrated automatically.
- User activity (logins, edits) is tracked in `~/.narraters/manage/user_records.json`.
- Edited files include the editor's username in the filename (e.g., `{subject_id}_{username}-edit.txt`), so different users' edits are kept separate.

## Dependencies

See `requirements.txt` for full list. Key dependencies:
- `pandas`, `openpyxl`: Excel file handling
- `flask`: Web viewer
- `pyspellchecker`: Spell checking in Step 3
- `numpy`, `matplotlib`, `scipy`: Analysis and plotting (helpers, web app matrix viz)
- `anthropic`, `openai`: LLM API clients (optional, for API-based methods)
- `whisper` / `whisperx`: Audio transcription (optional, for Step 1)
- `spacy`, `benepar`: NLP-enhanced clause detection (optional, improves segmentation accuracy)
- `fpdf2`: Tutorial PDF generation (optional, only needed to regenerate the tutorial)

To install optional NLP dependencies:
```bash
pip install spacy benepar
python -m spacy download en_core_web_sm
```

## Notes

- Story events are stored in `data/3_story_events/` with naming pattern `{story_name}_events.xlsx`
- Recall audio files are in `data/4_recall_audio/`
- Story audio files are in `data/1_story_audio/`
- Story transcripts (if any) are in `data/2_story_transcript/`
- All manual edits through the web viewer are saved with `_{username}-edit` suffix
- The web viewer supports keyboard shortcuts (Ctrl+S/Cmd+S) to save current tab
- User management records are stored in `~/.narraters/manage/user_records.json` (out of the installed package; see "User Accounts" above).

## Root-Level File Reference

| File | Purpose | Status |
|------|---------|--------|
| `developer/README.md` | Comprehensive project documentation: overview, pipeline steps, I/O formats, usage, and editing workflows. | Complete |
| `developer/SETUP_API.md` | API key setup instructions for both Anthropic (Claude) and OpenAI (GPT) providers, with quick/persistent setup and provider table. | Complete |
| `requirements.txt` | Python dependencies — core, optional API, optional audio, optional NLP, optional PDF generation. | Complete |
| `pipeline_config.json` | Active pipeline configuration created/managed by the web UI; stores step order, input/output paths. | Runtime file — do not edit manually |
| `.gitignore` | Git ignore rules for caches, environments, IDE files, OS files, and user data. | Complete |
| `scripts/1_audio-transcribe.py` | Pipeline Step 1: transcribe audio files using WhisperX/Whisper. | Core script |
| `scripts/2_story-event-segment.py` | Pipeline Step 2: segment story transcripts into events (clause/fine/coarse/API/manual). | Core script |
| `scripts/3_spell-grammar-correct.py` | Pipeline Step 3: multi-pass spell and grammar correction with pyspellchecker and optional LanguageTool. | Core script |
| `scripts/4_parse-texts.py` | Pipeline Step 4: parse corrected recall text into clause-level segments. | Core script |
| `scripts/5_recall-rater.py` | Pipeline Step 5: match recall segments to story events (keyword/API/manual). | Core script |
| `scripts/6_causal-rater.py` | Pipeline Step 6: rate causal relationships between story event pairs (API). | Core script |
| `generate_tutorial_pdf.py` | Builds `Narrative_Processor_Tutorial.pdf` from `tutorial_screenshots/` using fpdf2. | Utility script |
| `Narrative_Processor_Tutorial.pdf` | Pre-generated user tutorial with annotated screenshots of the web interface. | Reference document |
| `scripts/run_event_segment.sh` | Shell helper: checks for API key, then runs `scripts/2_story-event-segment.py --method api`. | Convenience script |
| `scripts/run_recall_rater.sh` | Shell helper: checks for Anthropic key, then runs `scripts/5_recall-rater.py`. | Convenience script |
| `scripts/setup_api_key.sh` | Interactive script to set Anthropic and/or OpenAI API keys in `~/.zshrc`. | Convenience script |

