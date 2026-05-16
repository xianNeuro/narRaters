# narRaters

**AI-assisted narrative processing with human-screening.**

`narRaters` helps **automate and visualize** a sequence of processing steps for **audio- and text-based narratives** — transcription, segmentation, light text cleanup, parsing, event alignment, and causal scoring. The heavy lifting can be delegated to models or rules, while **human-screening** at every stage lets raters review, correct, and sign off on outputs for quality control.

The same workflow supports **human cognitive studies** (for example, structured recall experiments) and **AI / NLP research** (for example, comparing or auditing model-generated narratives) whenever you need inspectable artifacts and explicit **human-screening** rather than a single opaque end-to-end run.

Raw audio or text recalls are run through a six-step pipeline — transcription → segmentation → spell/grammar correction → parsing → event matching → causal rating — with a Flask web UI for editing and version control at each step.

Once installed, you can drive the entire pipeline from the terminal (one step at a time, with full control over methods, models, and prompts) or open the GUI as described below.

---

## How to open narRaters

Complete **[Installation](#installation)** once (usually a double-click installer). Then start the web UI:

| How | What to do |
|-----|----------------|
| **Terminal (macOS, Linux, Windows)** | In the project folder, run `narraters serve`. Your browser should open to `http://localhost:5000` (use `--no-browser` if you prefer to open the URL yourself). |
| **macOS — shell script** | In Finder, double-click `server/START_HERE.command`. Same server and URL as above (it can install dependencies automatically if needed). |
| **macOS — app icon** | Build `narRater.app` with `bash packaging/macos/build_app_bundle.sh`, then double-click the app. The bundle is not committed to Git; the icon below is the artwork used when you build it. |

<p align="center">
  <img src="static/app-icon.png" alt="narRater macOS app icon" width="128" height="128">
  <br>
  <em>narRater.app uses this icon (after you run <code>packaging/macos/build_app_bundle.sh</code>).</em>
</p>

From the web UI you configure the pipeline, run steps from the dashboard, and open per-subject or per-story tabs to inspect or hand-edit outputs. Command-line equivalents for every step are listed under [Command-line pipeline](#command-line-pipeline).

---

## Pipeline overview

The app covers a six-step pipeline. Every step runs from the GUI **or** the `narraters` terminal command, has a lightweight default method, and can be human-edited afterwards.

| # | Step | What it does | Terminal command | Default in / out |
|---|------|--------------|------------------|------------------|
| 1 | **Transcribe** | Audio recordings → text (Whisper/WhisperX) | `narraters transcribe` | `data/4_recall_audio/` (or `data/1_story_audio/` with `--kind story`) → `output/*_audio-transcribed/` |
| 2 | **Segment** | Story transcript → numbered events | `narraters segment` | `data/2_story_transcript/` → `data/3_story_events/` |
| 3 | **Correct** | Fix spelling/grammar in recall text (no rewriting) | `narraters correct` | `data/5_recall_texts/` → `output/recall_corrected/` |
| 4 | **Parse** | Corrected recall → clause-level segments | `narraters parse` | `output/recall_corrected/` → `output/recall_parsed/` |
| 5 | **Match** | Recall segments ↔ story events | `narraters match` | `output/recall_parsed/` + `data/3_story_events/` → `output/recall_rated/` |
| 6 | **Rate** | Causal strength of every story-event pair | `narraters rate` | `data/3_story_events/` → `output/causal_rated/` |

Steps 1 and 2 operate on the *story*; steps 3–5 on each *subject's recall*; step 6 on the *story event list*. A text-only project can skip Step 1 entirely. Per-step options are detailed under **Command-line pipeline** below.

---

## Installation

**Prerequisite:** [Python 3.10+](https://www.python.org/downloads/) on your PATH (or the Microsoft Store / Homebrew equivalent). The installers below do **not** bundle Python.

### Quick install (double-click)

| Platform | File (repo root) | What it does |
|----------|------------------|----------------|
| **macOS** | `narRaters_installer.command` | Runs a one-time `pip install -e .` for this folder. If nothing happens the first time, **Right-click → Open**, then **Open** (Gatekeeper). |
| **Windows** | `narRaters_installer.bat` | Same, using `py -3` or `python` (install Python with “Add to PATH” enabled). |

**macOS disk image (standard layout):** **`narRaters-macos-installer.dmg`** at the **repository root** (top level of the clone, next to `README.md`) — Finder volume contains **`narRaters_installer.app`**, **`narRaters_source/`** (full tree), an **`Applications`** shortcut, and **`INSTALL-macOS.txt`**. Download from the repo ([raw on `main`](https://github.com/xianNeuro/narRaters/raw/main/narRaters-macos-installer.dmg) once the file is committed), from [**GitHub Releases**](https://github.com/xianNeuro/narRaters/releases), or build locally: **`bash packaging/macos/build_installer_dmg.sh`**. Follow **`INSTALL-macOS.txt`** on the disk.

That completes a normal install. The default dependency set is **minimal** (no multi-GB ML stacks). Default methods per step:

| Step | Default method |
|------|----------------|
| 2 — segment | `clause` (heuristic) |
| 3 — correct | `rules` (spell-checker) |
| 4 — parse | `rules` (regex) |
| 5 — match | `test` (keyword) |
| 6 — rate | `linguistic` (regex; spaCy if installed) |

### Developers: clone + editable install

```bash
git clone https://github.com/xianNeuro/narRaters.git
cd narRaters
pip install -e .
```

Use `-e` so edits to the source apply without reinstalling.

### Optional extras (heavier methods)

Install only what you need (`[audio]`, `[local-llm]`, and `[match]` pull **torch**, multi-GB):

```bash
pip install -e ".[api]"        # Step 5/6 --method api
pip install -e ".[audio]"     # Step 1 — Whisper / WhisperX
pip install -e ".[nlp]"       # Step 2 — spaCy + benepar
pip install -e ".[grammar]"   # Step 3 — language-tool-python
pip install -e ".[local-llm]" # local Gemma (HF)
pip install -e ".[match]"     # Step 5 — rmatch
pip install -e ".[all]"       # api + match
```

> ⚠️ Heavy methods run a **disk/RAM preflight** before downloads — see *Heavy-method warning* under [Launching the GUI](#launching-the-gui).

### Ollama (local Gemma, no cloud billing)

Install [Ollama](https://ollama.com), then e.g. `ollama pull gemma4:e4b` for the `gemma-ollama` methods (Steps 3–5). The app checks free disk before suggesting large pulls.

### API keys

```bash
cp developer/.env.example .env   # then edit for ANTHROPIC_API_KEY, OPENAI_API_KEY, HF_TOKEN, …
```

Full provider list: [`developer/SETUP_API.md`](developer/SETUP_API.md).

### Optional: macOS `narRater.app` (GUI launcher)

`bash packaging/macos/build_app_bundle.sh` builds **`narRater.app`** next to `server/`. Double-click to start the Flask server and open the browser. The bundle picks a `python3` that can `import flask`; if none qualifies, it prompts you to run the click-installer or `pip install -e .` first. Rebuild after changing `static/app-icon.png`.

### Maintainers: rebuild installer `.app` / DMG

```bash
bash packaging/macos/build_narRaters_installer_app.sh   # narRaters_installer.app at repo root (gitignored)
bash packaging/macos/build_installer_dmg.sh             # narRaters-macos-installer.dmg at repo root
```

CI: `.github/workflows/build-installer-dmg.yml` (artifact on manual runs; attaches the DMG to GitHub Releases). Commit **`narRaters-macos-installer.dmg`** at the repo root when you want a direct in-tree download link.

---

## Where to put your data

Drop input files into these directories before launching (paths are relative to the project root, and every step's input/output directory can also be remapped on the configuration page):

| You have… | Put it in… | Format / naming |
|---|---|---|
| Story transcript (text) | `data/2_story_transcript/` | `{story}.txt` — plain UTF-8 text, one story per file |
| Story event list (pre-segmented) | `data/3_story_events/` | `{story}_events.xlsx` — columns `event`, `story_texts` |
| Subject recall text | `data/5_recall_texts/` | `{subj_id}.txt` — e.g. `the_siren_sub-01.txt` |
| Story audio (optional, Step 1) | `data/1_story_audio/` | `.wav` / `.mp3` / `.m4a`, named by story |
| Recall audio (optional, Step 1) | `data/4_recall_audio/` | `.wav` / `.mp3` / `.m4a`, named by subject |

Outputs are written under `output/` — one subdirectory per step (`output/recall_corrected/`, `output/recall_parsed/`, `output/recall_rated/`, …). A working demo dataset lives in `demo/data/`.

**File versioning is a core feature.** Automated runs write `{subj_id}_{method}.ext`; your hand-edited versions are saved as `{subj_id}_{ratername}-edit.ext` and never overwrite the originals. The web UI lets you switch between versions via a dropdown, and the `-edit` files are what you export for analysis.

---

## Launching the GUI

Same entry point as in [How to open narRaters](#how-to-open-narRaters); from a terminal in the project root:

```bash
narraters serve
```

The command starts the Flask web server, auto-opens your default browser to `http://localhost:5000`, and lands on the **pipeline configuration page** (or the dashboard, if a pipeline is already configured).

Common options:

| Flag | Default | Purpose |
|---|---|---|
| `--port` | `5000` | Bind to a different port (e.g. if `5000` is already in use) |
| `--host` | `127.0.0.1` | Bind to a specific interface. Use `0.0.0.0` to allow access from other machines on your network (only on a trusted network — the UI runs subprocesses on your behalf) |
| `--no-browser` | off | Don't auto-open the browser — useful when running headless or over SSH |
| `--debug` | off | Enable Flask debug mode (auto-reload on code changes) |

```bash
narraters serve --port 8080 --no-browser
```

### Using the web UI — the three pages

1. **Pipeline configuration** (`/pipeline-config`) — the first screen. Drag steps from the **Available Steps** palette into the **Pipeline Flow** canvas in the middle to build your pipeline; configure each step's input/output paths. At the top of the Pipeline Flow panel, enter a **Rater name** (or click the 🎲 dice for a random one) — this labels any files you export. The **Continue** button stays greyed out until you have both a rater name *and* at least one step; clicking it saves the pipeline and opens the dashboard.

2. **Dashboard** (`/`) — one panel per pipeline chain, a row per subject/story, a column per step. Each cell shows that step's status; click a cell to **auto-process** that step for that item. Steps with multiple methods open a small dialog where you choose the **method**, **model**, **prompt version**, and **input variant** before running. Batch buttons run a step across all items. "Change Rater" (top-right) returns you to the configuration page.

3. **Subject / story detail** (`/subject/<id>`, `/story/<name>`) — a tabbed view of every step's output for one item. Inspect the text/table, switch between automated and `-edit` versions via the dropdown, **edit by hand**, and **save** — your edits become a `{id}_{ratername}-edit` file ready for export.

### Heavy-method warning

Before launching a step that loads a heavy local model (Gemma-4 via Ollama, the rMatch embedding matcher, local Transformers, or Whisper), the app runs a resource preflight (RAM + free disk + model availability). If the method is likely too heavy for your device, a **popup** appears explaining why and offering a one-click switch to a lighter method (e.g. `rules`, keyword `test`, `clause`). It never downloads or starts a model to make this decision, so the check itself can't crash your machine. On a capable machine with the model installed, no popup appears.

---

## Command-line pipeline

Every step is also exposed as a subcommand for scripted / batch use. The general shape is:

```
narraters <step> [--method METHOD] [--model MODEL] [-i INPUT] [-o OUTPUT] [--prompt-version VERSION] ...
```

Discover what's available at any time:

```bash
narraters --help                 # list all subcommands
narraters <step> --help          # step-specific options
narraters segment --list-prompts # list available prompt versions for a step
narraters segment --list-models  # list supported model identifiers
```

The method choices below are exactly those accepted by the CLI (`src/narraters/cli.py`).

### Step 1 — `transcribe` (audio → text)

```bash
narraters transcribe --model large-v3 --timestamps          # recall audio (default)
narraters transcribe --kind story --model small              # story audio instead
narraters transcribe -i path/to/audio -o path/to/out         # custom directories
narraters transcribe --filter sub-01                         # one item only
```

| Option | Choices | Notes |
|---|---|---|
| `--model` | `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3` | Whisper model name |
| `--timestamps` | flag | Also write Excel files with word-level timestamps |
| `--kind` | `recall` (default), `story` | Picks the conventional directories: `recall` = `data/4_recall_audio/` → `output/recall_audio-transcribed/`; `story` = `data/1_story_audio/` → `output/story_audio-transcribed/` |
| `-i, --input` | path | Input audio directory (overrides the `--kind` default) |
| `-o, --output` | path | Output directory (overrides the `--kind` default) |
| `--filter` | substring | Only transcribe files whose name matches this item id |

Requires `pip install -e ".[audio]"`. (Text-only projects can skip Step 1 entirely.)

### Step 2 — `segment` (story → events)

```bash
narraters segment --method clause
narraters segment --method api --model claude-sonnet-4-6 --prompt-version event_segment
narraters segment --method fine --input data/2_story_transcript/my_story.txt
```

| Option | Choices | Notes |
|---|---|---|
| `--method` | `clause`, `fine`, `coarse`, `api` | `clause` needs no model; `fine`/`coarse` use spaCy if installed; `api` calls an LLM |
| `--model` | e.g. `claude-sonnet-4-6`, `gpt-4o`, `gemma4-e4b-ollama` | Only used with `--method api` |
| `--prompt-version` | see `--list-prompts` | Selects a template from `scripts/prompt/event_segment*.txt` |
| `-i, --input` | path | Single transcript file or a directory (else processes all) |
| `-o, --output` | path | Output directory (default: `data/3_story_events/`) |

### Step 3 — `correct` (spell / grammar fixes)

```bash
narraters correct --method rules
narraters correct --method gemma-ollama --ollama-model gemma4:e4b
```

| Option | Choices | Notes |
|---|---|---|
| `--method` | `rules`, `gemma-ollama` | `rules` runs entirely locally with no model; `gemma-ollama` needs a local Ollama server |
| `--ollama-model` | e.g. `gemma4:e4b` | Local Ollama model tag (with `gemma-ollama`) |
| `--prompt-file` | path | Override the instructions file (default: `scripts/prompt/spell_gram.txt`) |
| `-i, --input` | path | Single recall text file |
| `-o, --output` | path | Output directory |

Minimal corrections only — Step 3 fixes spelling/grammar errors and never rewrites or paraphrases.

### Step 4 — `parse` (recall text → clause-level segments)

```bash
narraters parse --method rules
narraters parse --method ollama --model gemma4:e4b --prompt-version recall_parse_clause
narraters parse --filter-pattern sub-02            # process one subject only
```

| Option | Choices | Notes |
|---|---|---|
| `--method` | `rules`, `ollama` | `rules` is the default (regex, no model); `ollama` uses local Gemma |
| `--model` | e.g. `gemma4:e4b` | Ollama model tag (with `--method ollama`) |
| `--prompt-version` | see `scripts/prompt/recall_parse_*.txt` | Prompt template name |
| `-i, --input` | path | Input directory (default: `output/recall_corrected/`) |
| `-o, --output` | path | Output directory (default: `output/recall_parsed/`) |
| `--filter-pattern` | substring | Optional filter to process a single subject |

### Step 5 — `match` (recall segments ↔ story events)

```bash
narraters match --test-mode                       # simulated keyword matching, no model/API
narraters match --method api --story-events data/3_story_events
narraters match --method gemma-ollama
narraters match --method rmatch                   # embedding matcher (requires [match])
```

| Option | Choices | Notes |
|---|---|---|
| `--method` | `test`, `api`, `gemma-ollama`, `rmatch` | `test` is keyword-based, free, and always available; `rmatch` needs `pip install -e ".[match]"` |
| `--story-events` | path | Directory of `{story}_events.xlsx` (default: `data/3_story_events`) |
| `-i, --input` | path | Recall-parsed input directory (default: `output/recall_parsed/`) |
| `-o, --output` | path | Output directory (default: `output/recall_rated/`) |
| `--test-mode` | flag | Equivalent to `--method test` — simulated matching, no API calls |

### Step 6 — `rate` (causal relationships between event pairs)

```bash
narraters rate --method linguistic
narraters rate --method api --model claude-sonnet-4-6 --prompt-version causal_rating
narraters rate --method manual                    # write an empty matrix for hand rating
```

| Option | Choices | Notes |
|---|---|---|
| `--method` | `linguistic`, `api`, `manual` | `linguistic` is rule-based (no model); `manual` scaffolds an N×N matrix to fill in by hand |
| `--model` | e.g. `claude-sonnet-4-6`, `gpt-4o` | Only used with `--method api` |
| `--prompt-version` | see `scripts/prompt/causal_rating*.txt` | Prompt template name |
| `-i, --input` | path | Input file/directory |
| `-o, --output` | path | Output directory |

---

## Prompt templates

LLM-based methods load prompts from `scripts/prompt/`. The current templates are:

| File | Step | Used by |
|---|---|---|
| `event_segment.txt` | 2 — segment | `--method api` |
| `spell_gram.txt` | 3 — correct | `--method gemma-ollama` |
| `recall_parse_clause.txt` | 4 — parse | `--method ollama` |
| `recall_rating.txt` | 5 — match | `--method api`, `--method gemma-ollama` |
| `causal_rating.txt` | 6 — rate | `--method api` |

You can:

- **Browse available versions** with `narraters <step> --list-prompts`
- **Select a version** with `--prompt-version <name>`
- **Override the file directly** for Step 3 with `--prompt-file path/to/prompt.txt`
- **Add your own** by dropping a new `.txt` into `scripts/prompt/` — it's picked up automatically

See [`scripts/prompt/README.md`](scripts/prompt/README.md) for the conventions each template follows.

---

## Validation / testing

There is no pytest suite; validation is done via helper scripts:

```bash
python helpers/test_recall_rater_single_subject.py
python helpers/test_story_event_segment.py
python helpers/test_recall_rater_all_stories.py
python helpers/test_bar_metrics_all_rated.py
```

---

## Performance notes

The dashboard caches each output directory's listing per request, so building the status grid no longer re-scans the filesystem once per (item × step). On datasets with many subjects/steps this turns thousands of redundant directory scans into one scan per directory, making the dashboard load fast.

---

## Library / Python use

```python
from narraters import __version__, project_root
print(__version__, project_root())
```

Direct per-step imports are planned for a future release; for now, programmatic use should call the CLI via `subprocess` or import the modules under `scripts/`.

---

## Project layout

```
narrative-processor/
├── pyproject.toml                # package metadata, deps, console scripts
├── requirements.txt              # minimal runtime deps (extras commented)
├── src/narraters/                # the installed package
│   ├── cli.py                    # argparse entry point (`narraters` command)
│   └── paths.py                  # repo-root resolution
├── scripts/                      # pipeline scripts (delegated to by the CLI)
│   ├── 1_audio-transcribe.py … 6_causal-rater.py
│   └── prompt/                   # LLM prompt templates
├── server/web-interface.py       # Flask web UI (routes, subprocess orchestration)
├── templates/, static/           # HTML / CSS / JS for the web UI
├── helpers/                      # paths, Ollama/disk/RAM preflight, plotting, tests
│   ├── disk_space.py             # free-disk preflight for local models
│   └── resource_preflight.py     # heavy-method (RAM/disk) assessment
├── data/                         # inputs (audio, transcripts, story events, recalls)
├── output/                       # pipeline outputs (one subdir per step)
├── demo/                         # runnable demo dataset
├── packaging/macos/              # build script for the `.app` bundle
└── developer/                    # full handbook and design docs
```

---

## Further reading

- **[`developer/README.md`](developer/README.md)** — handbook covering each pipeline step, I/O contracts, editing workflows, and design principles. Read this before changing pipeline logic.
- **[`developer/SETUP_API.md`](developer/SETUP_API.md)** — API key setup for Anthropic, OpenAI, HuggingFace
- **[`developer/server.md`](developer/server.md)** — web server internals
- **[`developer/helpers.md`](developer/helpers.md)** — helper / test scripts reference
- **[`scripts/prompt/README.md`](scripts/prompt/README.md)** — prompt template conventions
- **`narRater_Tutorial.pdf`** — illustrated end-to-end walkthrough. To rebuild it: refresh the screenshots with the running app (`python tutorial_screenshots/capture_screenshots.py`, see that file's header for the shot list), then `python generate_tutorial_pdf.py` after `pip install -e ".[pdf]"`.

---

## Author

**Xian Li** — [xianl.cogneuro@gmail.com](mailto:xianl.cogneuro@gmail.com)

---

## Acknowledgements

- **Janice Chen** for brainstorming the causal-rating step interface and for help testing and improving package functionality.
- **Gabi Kressin Palacios** and **Dhruva Arekar** for an additional method for the recall-matching step (matching human recall text to story events). See [GabrielKP/rMatch](https://github.com/GabrielKP/rMatch) for human-data–validated AI-assisted recall rating.
- **Xiyu Li (Rita)** for contributions to the `recall_rating` prompt development and for validating model performance on human recall data (Claude Sonnet 4.5 and Opus 4.6 were close to human raters).

---

## License

The Software is licensed under the **NarRaters Research and Non-Commercial
License** (see [`LICENSE`](LICENSE)): free use for research, education, and
other non-commercial purposes; **commercial or for-profit use requires prior
written permission** from the copyright holder. Contact
[xianl.cogneuro@gmail.com](mailto:xianl.cogneuro@gmail.com) for commercial
licensing.

This model is in the same family as widely used **non-commercial / academic
first** terms (for example the [PolyForm Noncommercial](https://polyformproject.org/licenses/noncommercial/1.0.0/)
pattern for permitted non-commercial purposes, and **dual-license** or
**commercial-license-required** approaches similar in spirit to the
[Prosperity Public License](https://prosperitylicense.com/) model, where
commercial rights are negotiated separately with the author).
