# narRaters

**AI-assisted narrative processing with human-screening.**

`narRaters` helps **automate and visualize** a sequence of processing steps for **audio- and text-based narratives** — transcription, segmentation, light text cleanup, parsing, event alignment, and causal scoring. The heavy lifting can be delegated to models or rules, while **human-screening** at every stage lets raters review, correct, and sign off on outputs for quality control.

The same workflow supports **human cognitive studies** (for example, structured recall experiments) and **AI / NLP research** (for example, comparing or auditing model-generated narratives) whenever you need inspectable artifacts and explicit **human-screening** rather than a single opaque end-to-end run.

Raw audio or text recalls are run through a six-step pipeline — transcription → segmentation → spell/grammar correction → parsing → event matching → causal rating — with a Flask web UI for editing and version control at each step.

Once installed, you can drive the entire pipeline from the terminal (one step at a time, with full control over methods, models, and prompts) or open the GUI as described below.

> **No accounts, no passwords.** `narRaters` runs locally as a single-user research tool. Instead of logging in, you type a **rater name** on the configuration page; that name is only used to label the files you export (e.g. `subject_BraveOtter-edit.xlsx`). A dummy name is perfectly fine.

---

## How to open narRaters

**First-time setup without the terminal (macOS):** double-click **`narRaters_installer.app`** if you already built it (`bash packaging/macos/build_narRaters_installer_app.sh`), or double-click **`narRaters_installer.command`** in the project root. Both run a one-time `pip install -e .`. If the icon “does nothing” the first time, **right-click → Open** once (Gatekeeper), then click **Open** — after that, double-click works normally.

**Windows:** double-click **`narRaters_installer.bat`**.

You need **Python 3.10+** installed first ([python.org](https://www.python.org/downloads/) or your platform store). These installers do not bundle Python.

**Distributing a disk image (macOS):** from the project root run `bash packaging/macos/build_installer_dmg.sh`. That writes **`narRaters_installer.dmg`** next to `server/`. Recipients open the DMG, double-click **`narRaters_installer.app`**, then work inside the mounted **`narRaters_source`** folder (or copy that folder anywhere and keep the app next to `server/` as in a normal clone).

**Prerequisite:** the package must be installed once (click-installer above, or `pip install -e .` from the project root — see [Installation](#installation)). After that, use any of the following.

| How | What to do |
|-----|----------------|
| **Terminal (macOS, Linux, Windows)** | In the project folder, run `narraters serve`. Your browser should open to `http://localhost:5000` (use `--no-browser` if you prefer to open the URL yourself). |
| **macOS — shell script** | In Finder, double-click `server/START_HERE.command`. Same server and URL as above (it can install dependencies automatically if needed). |
| **macOS — app icon** | Build the double-clickable launcher with `bash packaging/macos/build_app_bundle.sh`. That creates `narRater.app` next to `server/` and `static/`. Double-click the app to start the server and open the UI. The `.app` bundle is **not** committed to Git (you build it locally); the icon below is the artwork used for that bundle. |

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

`narRaters` requires **Python 3.10 or newer**.

### From source (recommended while in development)

```bash
git clone https://github.com/xianNeuro/narRaters.git
cd narRaters
pip install -e .
```

The `-e` flag installs the package in **editable** mode, so your changes to the source take effect immediately without reinstalling.

If you prefer not to use Terminal for that step, use **`narRaters_installer.command`** (macOS), **`narRaters_installer.app`** (build first; see [How to open narRaters](#how-to-open-narRaters)), or **`narRaters_installer.bat`** (Windows).

`pip install -e .` (or `pip install -r requirements.txt`) installs a **deliberately minimal** set of dependencies — just enough to run the lightweight default method of every pipeline step plus the web UI. It pulls **no** multi-GB machine-learning frameworks, so a fresh install is fast and will not fill up your disk.

| Step | Minimal method installed by default |
|---|---|
| 2 — segment | `clause` (heuristic, no model) |
| 3 — correct | `rules` (spell-checker, no model) |
| 4 — parse | `rules` (regex, no model) |
| 5 — match | `test` / keyword (no model) |
| 6 — rate | `linguistic` (regex; spaCy used only if present) |

### Optional extras (heavier methods — opt in only)

Each extra enables a heavier, non-minimal method. Install only the ones you need:

```bash
pip install -e ".[api]"        # Anthropic + OpenAI clients — Step 5/6 --method api
pip install -e ".[audio]"      # Whisper / WhisperX — Step 1 audio transcription (pulls torch)
pip install -e ".[nlp]"        # spaCy + benepar — higher-accuracy Step 2 fine/coarse
pip install -e ".[grammar]"    # language-tool-python — extra Step 3 grammar rules
pip install -e ".[local-llm]"  # transformers + torch + accelerate — local Gemma (HF)
pip install -e ".[match]"      # rmatch — embedding Step 5 backend (pulls torch + sentence-transformers)
pip install -e ".[all]"        # api + match together
```

> ⚠️ `[audio]`, `[local-llm]`, and `[match]` transitively pull `torch` (several GB). Install them deliberately, not by default. Local-model methods additionally run a **free-disk-space and RAM preflight** before any download or run — see *Heavy-method warning* below.

### Local models via Ollama (no cloud billing)

The `gemma-ollama` methods (Steps 3, 4, 5) talk to a local [Ollama](https://ollama.com) server instead of a cloud API. After installing Ollama:

```bash
ollama pull gemma4:e4b      # ~ a few GB — narRaters checks free disk first
```

`narRaters` checks free disk space **before** advising a pull and warns in the UI if the model would not fit, so an install cannot wedge your machine.

### API keys

LLM-based methods read keys from a `.env` file in the project root. Copy the template and fill in whichever keys you'll use:

```bash
cp developer/.env.example .env
# then edit .env to add ANTHROPIC_API_KEY, OPENAI_API_KEY, HF_TOKEN, etc.
```

See [`developer/SETUP_API.md`](developer/SETUP_API.md) for the full list of supported providers and model names.

### Local installable app (macOS)

After you run `bash packaging/macos/build_app_bundle.sh`, `narRater.app` appears next to `server/`, `static/`, and `templates/`. It is a small portable launcher: the project path and Python interpreter are resolved at launch time, so you can move the whole project folder (Documents, `/Applications`, …) and the bundle keeps working as long as it stays a sibling of `server/`. Double-click the app; it opens Terminal, starts the Flask server, and points your default browser at `http://localhost:5000`.

What happens on the first launch:

- The bundle looks for `python3` in `/opt/homebrew/bin`, `/usr/local/bin`, `$(which python3)`, and `/usr/bin`. The first one that can `import flask` wins. If none qualifies, the bundle pops up a dialog asking you to run `pip install -e .` (or use `narRaters_installer.app` / `narRaters_installer.command`) inside the project folder.
- The bundle resolves the project root from its own location, so there's no rebuild needed if you move the folder.

To build or refresh the bundle (for example, after editing the icon at `static/app-icon.png`):

```bash
bash packaging/macos/build_app_bundle.sh
```

**Installer app and DMG** (optional — for `pip install -e .` without typing Terminal commands, or to ship a disk image):

```bash
bash packaging/macos/build_narRaters_installer_app.sh   # narRaters_installer.app next to server/
bash packaging/macos/build_installer_dmg.sh             # narRaters_installer.dmg (app + narRaters_source/)
```

If you prefer not to use a `.app` bundle, use `narraters serve` or double-click `server/START_HERE.command` — see [How to open narRaters](#how-to-open-narRaters).

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

## License

MIT
