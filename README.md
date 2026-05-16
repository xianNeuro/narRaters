# narRaters

**AI-assisted narrative processing with human-screening.**

**narRaters** is for **human cognitive studies** and **LLM-oriented research** whenever the data are **long passages of natural language**—in other words, **narratives** (listened to or read as text). It **automates and visualizes** a single, repeatable pipeline for **audio- and text-based narratives**: **transcription**, **segmentation**, **light text cleanup**, **parsing**, **event alignment** (mapping recall to story events), and **causal scoring**. You can assign the heavy lifting to **rules or models**; **human-screening** at every step means raters can **review, edit, and sign off** on outputs before they enter analysis. The web UI and versioned files also make it practical to run **human vs. LLM** comparisons on the same inputs and prompts.

There are no accounts or passwords. You run a small web server on your machine; a **rater name** on the setup page only labels exported hand-edited files (for example `subject_YourName-edit.xlsx`).

### Typical uses

- **Structured recall and memory experiments** — encode a narrative, collect recalls (audio or text), then clean, segment, align with story events, and score causal relations with auditable intermediate files.
- **LLM evaluation and NLP workflows** — benchmark models against rules or human edits on the same pipeline, with explicit **human-screening** rather than a single opaque pass over the text.
- **Teaching or pilots** — defaults stay small; add `[audio]`, `[api]`, `[match]`, and similar extras **only when you need them** ([Installation](#installation)).

---

## Table of contents

- [Getting started](#getting-started)
- [Pipeline overview](#pipeline-overview)
- [Installation](#installation)
- [Where to put your data](#where-to-put-your-data)
- [Using the web interface](#using-the-web-interface)
- [Command-line pipeline](#command-line-pipeline)
- [Prompt templates](#prompt-templates)
- [Validation / testing](#validation--testing)
- [Performance notes](#performance-notes)
- [Library / Python use](#library--python-use)
- [Project layout](#project-layout)
- [Further reading](#further-reading)
- [Author](#author)
- [Acknowledgements](#acknowledgements)
- [License](#license)

---

## Getting started

1. **[Install](#installation)** once (`pip install -e .` from the project root, or the macOS / Windows installers in the repo).
2. **[Add inputs](#where-to-put-your-data)** under `data/` (or try **`demo/data/`** to learn the layout without your own files).
3. **[Start the web UI](#using-the-web-interface)** — from the project folder run `narraters serve`, or on macOS double-click `server/START_HERE.command`. Your browser should open **`http://localhost:5000`**.
4. **Configure the pipeline** — on the first screen, enter a **rater name** (any label you like), **drag** the steps you need into the flow, adjust paths if needed, then **Continue**. You need a name and at least one step before **Continue** enables.
5. **Run and review** — use the **dashboard** grid to run steps per cell; **open a subject or story** to see tabs for each step, switch **versions** in the dropdown (automated vs `*-edit`), **edit**, **save**, and export **`-edit`** files for analysis.

**First-session tip:** build a short chain (for example **Correct → Parse → Match** if you already have recall `.txt` files), run **one subject**, open its detail view, and tab through outputs before batching the whole dataset. The same steps are available from the **[command line](#command-line-pipeline)** for scripts and HPC.

---

## Pipeline overview

The table below is the **route map**: steps **1-2** are **story**-side; **3-5** run per **subject recall**; **6** scores the **story event list**. Text-only projects can **skip step 1**. Every step runs from the **GUI** or **`narraters` CLI**, ships with a **minimal default method**, and can be **hand-edited** afterward.

| # | Step | What it does | Terminal command | Default in / out |
|---|------|--------------|------------------|------------------|
| 1 | **Transcribe** | Audio recordings → text (Whisper/WhisperX) | `narraters transcribe` | `data/4_recall_audio/` (or `data/1_story_audio/` with `--kind story`) → `output/*_audio-transcribed/` |
| 2 | **Segment** | Story transcript → numbered events | `narraters segment` | `data/2_story_transcript/` → `data/3_story_events/` |
| 3 | **Correct** | Fix spelling/grammar in recall text (no rewriting) | `narraters correct` | `data/5_recall_texts/` → `output/recall_corrected/` |
| 4 | **Parse** | Corrected recall → clause-level segments | `narraters parse` | `output/recall_corrected/` → `output/recall_parsed/` |
| 5 | **Match** | Recall segments ↔ story events | `narraters match` | `output/recall_parsed/` + `data/3_story_events/` → `output/recall_rated/` |
| 6 | **Rate** | Causal strength of every story-event pair | `narraters rate` | `data/3_story_events/` → `output/causal_rated/` |

For each step, the GUI runs the same backends as the CLI. **Flags, methods, and examples** are documented under **[Command-line pipeline](#command-line-pipeline)** below.

---

## Installation

This section goes beyond the minimal path in **[Getting started](#getting-started)**—use it when you add **optional methods** (Whisper, APIs, local LLMs), set **API keys**, or build **macOS installers / `.app` bundles**.

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

> ⚠️ Heavy methods run a **disk/RAM preflight** before downloads — see [Heavy local models](#heavy-local-models) under [Using the web interface](#using-the-web-interface).

### Ollama (local Gemma, no cloud billing)

Install [Ollama](https://ollama.com), then e.g. `ollama pull gemma4:e4b` for the `gemma-ollama` methods (Steps 3–5). The app checks free disk before suggesting large pulls.

### API keys

```bash
cp .env.example .env   # then edit for ANTHROPIC_API_KEY, OPENAI_API_KEY, HF_TOKEN, …
```

Full provider list: [`SETUP_API.md`](SETUP_API.md).

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

After [installation](#installation), place files so the paths match what you configured on the **pipeline** page (defaults below are relative to the **project root**). You can **remap** any step’s input/output folders there without moving data.

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

## Using the web interface

The app is a **local Flask site** (default **`http://127.0.0.1:5000`**). Start it from the project directory in any of these ways:

| How | What to do |
|-----|-------------|
| **Terminal** (macOS, Linux, Windows) | `narraters serve` — usually opens your browser automatically. |
| **macOS — script** | Double-click **`server/START_HERE.command`** (can install missing deps on first run). |
| **macOS — app bundle** | Build once: `bash packaging/macos/build_app_bundle.sh`, then double-click **`narRater.app`**. Not committed to Git; the icon below is used when you build locally. |

<p align="center">
  <img src="static/app-icon.png" alt="narRater macOS app icon" width="128" height="128">
  <br>
  <em><code>narRater.app</code> uses this icon after <code>packaging/macos/build_app_bundle.sh</code>.</em>
</p>

On first visit you see **pipeline configuration** unless a pipeline was already saved, in which case you land on the **dashboard**.

### `narraters serve` options

| Flag | Default | Purpose |
|---|---|---|
| `--port` | `5000` | Another port if `5000` is busy |
| `--host` | `127.0.0.1` | Bind address; use `0.0.0.0` only on a **trusted** network (the UI runs subprocesses on your machine) |
| `--no-browser` | off | Do not open a browser tab (SSH, headless) |
| `--debug` | off | Flask debug / auto-reload while hacking on the server |

```bash
narraters serve --port 8080 --no-browser
```

### Navigating the three main screens

Use this table as a mental map; URLs are for bookmarking or support.

| Screen | Route | What you do there |
|--------|--------|-------------------|
| **Pipeline setup** | `/pipeline-config` | Drag steps from **Available Steps** into **Pipeline Flow**, set per-step **folders**, enter a **rater name** (or 🎲). **Continue** unlocks only when there is a **name** and **at least one step**; it saves config and opens the dashboard. |
| **Dashboard** | `/` | Grid: **rows** = subjects or stories, **columns** = steps. **Click a cell** to run that step for that row (pick **method / model / prompt / variant** if the step offers them). **Batch** actions run one step across all rows. **Change rater** returns to setup. |
| **Detail view** | `/subject/…` or `/story/…` | **Tabs** per pipeline step for **one** row. Read outputs, use the **version** dropdown to compare the latest automated file vs your **`{id}_{ratername}-edit`** saves, **edit**, **save**. Use **`-edit`** files for downstream analysis. |

**Flow:** setup → dashboard (bulk status + runs) → open a row when you need to **inspect, hand-correct, or compare versions**. You can return to setup anytime to add steps or change paths.

### Heavy local models

Before a step that would load **Whisper**, **Gemma via Ollama**, **rMatch** embeddings, or **local Transformers**, the app runs a **RAM / disk / model** preflight. If the run is likely unsafe for your machine, a **popup** explains why and can **switch you to a lighter method** (for example `rules`, `test`, `clause`). The check does **not** download or start a model just to decide, so it should not wedge the system. Capable machines with models already installed often see no popup.

---

## Command-line pipeline

Everything the dashboard runs is available as a **`narraters`** subcommand—use this for **scripts**, **clusters**, or **reproducible** one-off commands. General shape:

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
narraters segment --method api --model <anthropic-model-id> --prompt-version event_segment
narraters segment --method fine --input data/2_story_transcript/my_story.txt
```
Run `narraters segment --list-models` for the exact `--model` strings (Anthropic, OpenAI, and Ollama-backed presets).

| Option | Choices | Notes |
|---|---|---|
| `--method` | `clause`, `fine`, `coarse`, `api` | `clause` needs no model; `fine`/`coarse` use spaCy if installed; `api` calls an LLM |
| `--model` | see `narraters segment --list-models` | Only used with `--method api` (Anthropic, OpenAI, or Ollama preset keys) |
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
narraters rate --method api --model <anthropic-or-openai-model-id> --prompt-version causal_rating
narraters rate --method manual                    # write an empty matrix for hand rating
```
Use `narraters rate --help` and the Step 6 model dropdown in the web UI for supported `--model` values when using `--method api`.

| Option | Choices | Notes |
|---|---|---|
| `--method` | `linguistic`, `api`, `manual` | `linguistic` is rule-based (no model); `manual` scaffolds an N×N matrix to fill in by hand |
| `--model` | see web UI / provider docs | Only used with `--method api` |
| `--prompt-version` | see `scripts/prompt/causal_rating*.txt` | Prompt template name |
| `-i, --input` | path | Input file/directory |
| `-o, --output` | path | Output directory |

---

## Prompt templates

LLM-backed methods load text from **`scripts/prompt/`** (you can add versions or override paths; see [`scripts/prompt/README.md`](scripts/prompt/README.md)). Bundled templates:

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

---

## Validation / testing

There is no bundled **pytest** suite. Use the **helper scripts** under `helpers/` for smoke checks and regression-style runs, for example:

```bash
python helpers/test_recall_rater_single_subject.py
python helpers/test_story_event_segment.py
python helpers/test_recall_rater_all_stories.py
python helpers/test_bar_metrics_all_rated.py
```

### Research background (by pipeline step)

The steps below follow the **same numbering as the pipeline overview**. Citations motivate or validate **automated** approaches similar to optional narRaters methods; your study still needs design-appropriate evaluation.

**Step 1 — Transcribe**  
No paper cited here; validation is Whisper/WhisperX accuracy on your audio and manual spot checks. See [Installation](#installation) (`[audio]` extra) and the helper scripts above.

**Step 2 — Segment (story transcript to events)**  
Michelmann, Kumar, **Norman**, & Toneva, *Large language models can segment narrative events similarly to humans*: GPT-3 zero-shot boundaries correlate with human segmentations and approximate crowd consensus on continuous text—useful precedent for LLM-based story segmentation in narRaters. [arXiv:2301.10297](https://arxiv.org/abs/2301.10297), [Behavior Research Methods (2025)](https://doi.org/10.3758/s13428-024-02569-z), [companion code](https://github.com/s-michelmann/GPT_event_segmentation).

**Step 3 — Correct**  
No external benchmark listed; the package enforces minimal, non-paraphrasing edits. Exercise the recall-correction helpers if you change rules or prompts.

**Step 4 — Parse**  
No paper cited here; clause-level structure is checked against the same independent-clause logic as segmentation (see Step 2 above and the web UI tooltips).

**Step 5 — Match (recall segments to story events)**  
- **Norman lab / Computational Memory (Princeton)** — Toneva et al., *Memory for long narratives* (presentation materials, 2021; includes **K. A. Norman**): long-form novel recall scored by aligning recalled events to chapter events with GPT-2 representations, toward scalable scoring without fully manual coding. [PDF (Princeton Computational Memory Lab)](https://compmem.princeton.edu/wp/wp-content/uploads/2022/05/memory-for-long-narratives.pdf).  
- **rMatch** — Kressin Palacios & Arekar: embedding-based recall-to-event matching with human-data validation. [GabrielKP/rMatch](https://github.com/GabrielKP/rMatch).

**Step 6 — Rate (pairwise causal strength between story events)**  
Li et al., *Agency personalizes episodic memories* (PsyArXiv, 2024): behavioral work with **choose-your-own-adventure** narratives and controlled choice, examining how agency shapes memory for branching, choice-contingent event sequences—aligned with rich **event-wise** materials for which pairwise **causal** ratings are meaningful. [DOI:10.31234/osf.io/7evwj](https://doi.org/10.31234/osf.io/7evwj).

---

## Performance notes

The dashboard **caches each output directory's listing once per page request** and reuses it for every cell in the status grid, instead of scanning the disk again for each subject and step separately. On large studies that difference is very noticeable.

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
narRaters/
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
├── SETUP_API.md                  # user-facing API key and provider setup
└── .env.example                  # template for local API keys (copy to `.env`)
```

---

## Further reading

**`narRater_Tutorial.pdf`** (repo root) is an illustrated, click-by-click tour of the web UI—good next step after [Getting started](#getting-started).

- **[`SETUP_API.md`](SETUP_API.md)** — API keys for Anthropic, OpenAI, and Hugging Face; which pipeline steps need which keys.
- **[`scripts/prompt/README.md`](scripts/prompt/README.md)** — prompt template conventions for LLM-backed methods.
- **`narRater_Tutorial.pdf`** — illustrated end-to-end walkthrough. To rebuild it: refresh the screenshots with the running app (`python tutorial_screenshots/capture_screenshots.py`, see that file's header for the shot list), then `python generate_tutorial_pdf.py` after `pip install -e ".[pdf]"`.

Maintainer-only design notes and internal handbooks are **not** published in this repository; keep those materials private to your team.

---

## Author

**Xian Li** — [xianl.cogneuro@gmail.com](mailto:xianl.cogneuro@gmail.com)

---

## Acknowledgements

- **Janice Chen** for brainstorming the causal-rating step interface and for help testing and improving package functionality.
- **Gabi Kressin Palacios** and **Dhruva Arekar** for an additional method for the recall-matching step (matching human recall text to story events). See [GabrielKP/rMatch](https://github.com/GabrielKP/rMatch) for human-data–validated AI-assisted recall rating.
- **Xiyu Li (Rita)** for contributions to the `recall_rating` prompt development and for validating model performance on human recall data (commercial LLM APIs were close to human raters).

---

## License

**In short:** free for **research, education, and other non-commercial** use; **commercial or for-profit** use needs **prior written permission** from the copyright holder (contact below).

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
