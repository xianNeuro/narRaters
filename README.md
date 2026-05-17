<h1 align="center">narRaters</h1>

<p align="center">
  AI-assisted narrative processing with human-screening.
</p>

**narRaters** supports **human cognitive studies** and **LLM research** on **long, naturalistic language**—**narratives** as audio or text. It is built around **six widely used processing steps** for complex stimuli: **`audioTranscribe`**, **`eventSegment`**, **`sentenceCorrect`**, **`textParsing`**, **`textMatching`**, and **`causalRating`**.

You are not locked into one workflow: **pick only the steps your study needs**, **combine them in the order you want**, and choose among **multiple methods per step** (rules, local models, cloud APIs, and more).

The app automates and visualizes those steps; human-screening is facilitated through interface at every step, allowing human raters to review, edit, and sign off on outputs. The same platform supports human vs. LLM comparisons when you want to benchmark summarization, alignment, or causality reasoning on shared materials and prompts.

<p align="center">
  <img src="static/app-icon.png" alt="narRater app icon" width="128" height="128">
  <br>
  <em>macOS: build <code>narRater.app</code> with <code>packaging/macos/build_app_bundle.sh</code> (uses this icon).</em>
</p>

---

## Table of contents

- [Quick start](#quick-start)
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

## Quick start

You need **[Python 3.10+](https://www.python.org/downloads/)** installed (Windows: check **“Add python.exe to PATH”** during the installer).

### macOS / Linux — open Terminal and paste:

```bash
cd ~ && git clone https://github.com/xianNeuro/narRaters.git && cd narRaters && bash install.sh
```

That's it — clones the project to `~/narRaters/`, sets up a `.venv/`, installs everything, and opens the web UI in your browser.

### Windows — open Command Prompt and paste:

```bat
cd %USERPROFILE% && git clone https://github.com/xianNeuro/narRaters.git && cd narRaters && narRaters_installer.bat
```

(No git? Download the [project ZIP](https://github.com/xianNeuro/narRaters/archive/refs/heads/main.zip), unzip, then double-click `narRaters_installer.bat`.)

### After install

The browser opens **`http://127.0.0.1:5000/pipeline-config`**. Enter a **rater name**, drag the steps you need, **Continue**, and run from the **dashboard**. Your data goes in **`data/`** inside the project folder — see [Where to put your data](#where-to-put-your-data). Bundled examples (`pieman_edited`, `the_siren`) are already there so you can try the pipeline before adding your own files.

### To restart later

```bash
cd ~/narRaters && bash install.sh    # Mac / Linux
```

```bat
cd %USERPROFILE%\narRaters && narRaters_installer.bat
```

> **Why Terminal?** macOS Gatekeeper blocks unsigned `.app` and `.command` files downloaded from the internet — sometimes with a “malicious software” popup that won’t let you click *Open* at all. Running `bash install.sh` from Terminal completely bypasses that. The same install steps work; you just kick them off from a shell.

---

## Getting started

1. **[Install](#installation)** — clone the repo and run `bash install.sh` (Mac/Linux) or `narRaters_installer.bat` (Windows). Bundled examples live in `data/`.
2. **[Add inputs](#where-to-put-your-data)** under `data/` — the repo includes **bundled examples** (`pieman_edited`, `the_siren`) you can inspect or run as-is; see that section for paths. Smaller **`demo/data/`** samples are also available.
3. **[Start the web UI](#using-the-web-interface)** — the installer starts it for you. To restart later: re-run `bash install.sh` (Mac/Linux) / `narRaters_installer.bat` (Windows). PyPI users: `narraters serve` from any folder.
4. **Configure your workflow** — on the first screen, enter a **rater name** (any label you like), **drag in only the steps you need**, set each step’s paths and (when you run) its **method**, then **Continue**. You need a name and **at least one step** before **Continue** enables.
5. **Run and review** — use the **dashboard** grid to run steps per cell; **open a subject or story** to see tabs for each step, switch **versions** in the dropdown (automated vs `*-edit`), **edit**, **save**, and export **`-edit`** files for analysis.

---

## Pipeline overview

**Six steps, your configuration.** narRaters does **not** require all six steps or a fixed order. On the configuration page you **select and chain** only what your study needs; when you run a step you choose its **method** (and model or prompt, if applicable). The table below lists each step’s **ID** (used in the web UI and `pipeline_config.json`), role, CLI command, and default folders. In typical recall work, **`audioTranscribe`** / **`eventSegment`** target the **story**, **`sentenceCorrect`**–**`textMatching`** each **subject recall**, and **`causalRating`** the **story event list**—but text-only projects may skip **`audioTranscribe`**, and you might run only **`eventSegment`** and **`causalRating`**, or **`sentenceCorrect` → `textParsing` → `textMatching`**, and so on. Every included step is available from the **GUI** or **`narraters` CLI**, has a **lightweight default method**, and supports **hand-editing** afterward.

| # | Step ID | What it does | Terminal command | Default in / out |
|---|---------|--------------|------------------|------------------|
| 1 | **`audioTranscribe`** | Audio recordings → text (Whisper/WhisperX); story vs recall via `audioScope` or `--kind` | `narraters transcribe` | `data/4_recall_audio/` (or `data/1_story_audio/` with `--kind story`) → `output/*_audio-transcribed/` |
| 2 | **`eventSegment`** | Story transcript → numbered events | `narraters segment` | `data/2_story_transcript/` → `data/3_story_events/` |
| 3 | **`sentenceCorrect`** | Fix spelling/grammar in recall text (no rewriting) | `narraters correct` | `data/5_recall_texts/` → `output/recall_corrected/` |
| 4 | **`textParsing`** | Corrected recall → clause-level segments | `narraters parse` | `output/recall_corrected/` → `output/recall_parsed/` |
| 5 | **`textMatching`** | Recall segments ↔ story events | `narraters match` | `output/recall_parsed/` + `data/3_story_events/` → `output/recall_rated/` |
| 6 | **`causalRating`** | Causal strength of every story-event pair | `narraters rate` | `data/3_story_events/` → `output/causal_rated/` |

For each step, the GUI runs the same backends as the CLI. **Available methods, flags, and examples** are under **[Command-line pipeline](#command-line-pipeline)** below.

---

## Installation

> **Prerequisite:** [Python 3.10 or newer](https://www.python.org/downloads/). On Windows, tick **“Add python.exe to PATH”** in the installer.  
> **You’re done when** your browser shows the **pipeline setup** page (`…/pipeline-config`).

### Recommended — Terminal one-liner (works on every macOS, Linux, Windows)

This is the most reliable path. It clones the project, creates a virtual environment, installs everything, and starts the web UI — no double-clicks, no Gatekeeper popups.

**macOS / Linux** — open **Terminal** and paste:

```bash
cd ~ && git clone https://github.com/xianNeuro/narRaters.git && cd narRaters && bash install.sh
```

**Windows** — open **Command Prompt** and paste:

```bat
cd %USERPROFILE% && git clone https://github.com/xianNeuro/narRaters.git && cd narRaters && narRaters_installer.bat
```

Result on every platform: a `narRaters/` folder in your home directory, a `.venv/` inside it, and the web UI running at **`http://127.0.0.1:5000/pipeline-config`**.

**Restart later:**

```bash
cd ~/narRaters && bash install.sh                   # macOS / Linux
```

```bat
cd %USERPROFILE%\narRaters && narRaters_installer.bat
```

The installer is **idempotent** — re-running just re-launches the app (skips already-installed deps).

| Problem | Fix |
|---------|-----|
| `git: command not found` | Install Xcode Command Line Tools (`xcode-select --install`) on macOS, or [Git for Windows](https://git-scm.com/download/win). |
| `Python 3.10+ required` | Install from [python.org/downloads](https://www.python.org/downloads/), close and reopen Terminal, run again. |
| Blank page on `localhost:5000` | Visit **`http://127.0.0.1:5000/pipeline-config`** instead. macOS sometimes resolves `localhost` over IPv6 while Flask binds IPv4. |
| Port already in use (often **AirPlay Receiver** on macOS) | The installer auto-tries `5001`–`5010`. Use the URL printed in Terminal. To free port 5000: System Settings → General → AirDrop & Handoff → turn off **AirPlay Receiver**. |
| Need the bundled `data/` examples | Already in `data/` after `git clone` (`pieman_edited`, `the_siren`). |

---

### No git? — download a ZIP, install from Terminal

```bash
curl -L https://github.com/xianNeuro/narRaters/archive/refs/heads/main.zip -o ~/narRaters.zip
cd ~ && unzip narRaters.zip && mv narRaters-main narRaters && cd narRaters
xattr -dr com.apple.quarantine .          # macOS only — clears download quarantine
bash install.sh
```

Windows: download the ZIP from [github.com/xianNeuro/narRaters → Code → Download ZIP](https://github.com/xianNeuro/narRaters/archive/refs/heads/main.zip), unzip, open Command Prompt in the folder, run `narRaters_installer.bat`.

---

### Double-click installers (only if Terminal isn't an option)

> ⚠️ **macOS users — read this first.** macOS Gatekeeper blocks unsigned, un-notarized installers downloaded from the internet. The “*macOS cannot verify the developer / malicious software*” popup may not even let you click *Open*. We are not paying $99/year for an Apple Developer ID, so the items below **only work reliably after `git clone`** (which doesn't add quarantine attributes), or after running the `xattr -dr com.apple.quarantine .` command above on a downloaded ZIP. **The Terminal one-liner is strictly more reliable** — use it if at all possible.

In a project folder where Gatekeeper is satisfied:

| Platform | Double-click | What it does |
|----------|--------------|--------------|
| **macOS** | **`narRater.app`** | Calls `install.sh` and opens the web UI; shows the proper Dock icon |
| **macOS** | **`install_narRater.command`** | Same flow, plain Terminal window |
| **Windows** | **`narRaters_installer.bat`** | Creates `.venv\`, installs narRaters, opens browser |

If macOS blocks any of the macOS items above:

1. **Try the Terminal one-liner instead** (top of this section).
2. Or, if you really want the click flow, drop quarantine on the project folder once: `xattr -dr com.apple.quarantine ~/narRaters` and double-click again.

---

### Alternate — install from PyPI

For users who already have a working Python environment and don't need the bundled example data.

> ⚠️ **Always use `python3 -m pip`, not bare `pip`.**  On macOS, `pip` often points at an old Python (e.g. system 3.9), which makes PyPI report **`No matching distribution found for narraters`** even though the package exists. `python3 -m pip` runs pip through the same Python you'd use to run the app.

**Step 1 — Check Python (must be ≥ 3.10):**

```bash
python3 --version    # must show 3.10, 3.11, 3.12, or 3.13
```

If 3.9 or older, install Python from [python.org/downloads](https://www.python.org/downloads/), then **restart Terminal** before continuing.

**Step 2 — Install into a venv:**

```bash
python3 -m venv ~/narRaters-venv
source ~/narRaters-venv/bin/activate     # Windows: ~\narRaters-venv\Scripts\activate
python3 -m pip install --upgrade pip
python3 -m pip install narraters
narraters serve
```

The browser auto-opens **`http://127.0.0.1:5000/pipeline-config`**. If you see a blank page on `localhost:5000`, manually visit **`http://127.0.0.1:5000/pipeline-config`** instead — `localhost` resolves to IPv6 (`::1`) on some macOS setups while Flask binds to IPv4 (`127.0.0.1`). Fixed in **0.1.1+** (auto-rewrites to `127.0.0.1`).

**Exact package name:** `narraters` (all lowercase) — [`pypi.org/project/narraters`](https://pypi.org/project/narraters/).  Pin a version: `python3 -m pip install narraters==0.1.1`.

**Next time:** `source ~/narRaters-venv/bin/activate && narraters serve`.

| Problem | Fix |
|---------|-----|
| **`No matching distribution found for narraters`** when running `pip install narraters` | Use `python3 -m pip install narraters` instead. Bare `pip` likely points at Python < 3.10. (Verify with `python3 --version`.) |
| Same error even with `python3 -m pip` | `python3 --version` must be ≥ 3.10. Install [Python 3.10+](https://www.python.org/downloads/), open a **new** Terminal, recreate the venv, retry. |
| `narraters: command not found` | Activate the venv: `source ~/narRaters-venv/bin/activate`. |
| Browser opens **`localhost:5000`** but page is blank | Visit **`http://127.0.0.1:5000/pipeline-config`** instead, or upgrade: `python3 -m pip install --upgrade narraters`. |
| Port 5000 in use (macOS AirPlay Receiver) | `narraters serve --port 5001`, or System Settings → General → AirDrop & Handoff → turn off AirPlay Receiver. |
| `Could not find a version` / offline | `python3 -m pip install narraters -i https://pypi.org/simple` |
| You need bundled `data/` examples | Use the **clone or download** path above — PyPI installs the app only. |

PyPI installs the app **only**. To get the `data/` folder structure with bundled examples, also clone the repo or use the recommended path above.

---

### After install (every path)

1. Browser opens **`http://127.0.0.1:5000/pipeline-config`** (port may differ — read the URL printed in the Terminal window).
2. Type a **rater name** (any label).
3. **Drag** steps into the pipeline → **Continue** → run from the **dashboard**.

**Default methods** all work offline with no huge downloads:

| Step | Default |
|------|---------|
| segment | `clause` |
| correct | `rules` |
| parse | `rules` |
| match | `test` |
| rate | `linguistic` |

---

### Optional extras (Whisper, APIs, big models)

Add only what you need — **after** the base install. From inside a clone, with the venv activated:

```bash
python3 -m pip install -e ".[audio]"     # transcription (Whisper)
python3 -m pip install -e ".[api]"       # cloud LLM steps (Anthropic / OpenAI)
python3 -m pip install -e ".[nlp]"       # finer segmentation (spaCy)
python3 -m pip install -e ".[grammar]"   # grammar checker
python3 -m pip install -e ".[local-llm]" # local Gemma (large)
python3 -m pip install -e ".[match]"     # rmatch
python3 -m pip install -e ".[all]"       # api + match
```

If you installed from PyPI: `python3 -m pip install "narraters[audio]"`, etc.

Heavy downloads show a **RAM/disk warning** first — see [Heavy local models](#heavy-local-models).

**Ollama (local Gemma):** install [Ollama](https://ollama.com), then `ollama pull gemma4:e4b`.

**API keys (cloud):** copy `.env.example` to `.env` and fill in the keys — see [`SETUP_API.md`](SETUP_API.md).

---

### Developers

The `install.sh` script already does an editable install. To work on the codebase:

```bash
git clone https://github.com/xianNeuro/narRaters.git
cd narRaters
bash install.sh         # creates .venv, installs editable, starts server
# or, manual:
python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install -e .
```

Build a local **`narRater.app`** for icon/Dock testing: `bash packaging/macos/build_app_bundle.sh`.

---

### Advanced — macOS DMG (unsigned, often blocked by Gatekeeper)

The `narRaters-macos-installer.dmg` produced by `bash packaging/macos/build_installer_dmg.sh` exists for distribution channels that need a single-file artifact. **It is unsigned and un-notarized**, so most users will hit the same Gatekeeper block as `.command` and `.app` files. The Terminal one-liner is recommended instead.

If you really want to use the DMG:

```bash
xattr -dr com.apple.quarantine ~/Downloads/narRaters-macos-installer.dmg
open ~/Downloads/narRaters-macos-installer.dmg
xattr -dr com.apple.quarantine /Volumes/narRaters
```

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

Outputs are written under `output/` — one subdirectory per step (`output/recall_corrected/`, `output/recall_parsed/`, `output/recall_rated/`, …). A smaller alternate layout lives in **`demo/data/`** (lighthouse story, three recall `.txt` files).

### Bundled examples (`pieman_edited`, `the_siren`)

The repository ships **realistic sample inputs and outputs** under `data/` and `output/` so you can see accepted naming and file types before adding your own study. Your private files in those folders stay untracked (see `.gitignore`); only the examples below are committed.

**Stories:** **`pieman_edited`** (story audio + transcript + events) and **`the_siren`** (transcript, events, two recall subjects).

| Role | Folder | Example file(s) |
|------|--------|-----------------|
| Story audio (input) | `data/1_story_audio/` | `pieman_edited.wav` |
| Story transcript (input) | `data/2_story_transcript/` | `pieman_edited.txt`, `the_siren.txt` |
| Story events (input) | `data/3_story_events/` | `pieman_edited_events.xlsx`, `the_siren_events.xlsx` |
| Recall audio (input) | `data/4_recall_audio/` | `the_siren_sub-01.mp4`, `the_siren_sub-02.mp4` |
| Recall text (input) | `data/5_recall_texts/` | `the_siren_sub-01.txt`, `the_siren_sub-02.txt` |
| Story transcription (output) | `output/story_audio-transcribed/` | `pieman_edited.txt` |
| Recall transcription (output) | `output/recall_audio-transcribed/` | `the_siren_sub-01.txt`, `the_siren_sub-02.txt` |
| Spell/grammar correction (output) | `output/recall_corrected/` | `the_siren_sub-01.txt`, `the_siren_sub-02.txt` |
| Parsed recall (output) | `output/recall_parsed/` | `the_siren_sub-01_parsed.xlsx`, `the_siren_sub-02_parsed.xlsx` |
| Recall ↔ events (output) | `output/recall_rated/` | `the_siren_sub-02_rate-recall-test_mode.xlsx` (method slug in filename) |
| Causal ratings (output) | `output/causal_rated/` | `pieman_edited_causal-linguistic.xlsx`, `the_siren_causal-linguistic.xlsx` |

**Quick try:** after install, point a pipeline at the default folders above and run **`sentenceCorrect` → `textParsing` → `textMatching`** on `the_siren_sub-01` / `the_siren_sub-02`, or open the bundled **`output/`** files in Excel to inspect column layouts. Story **`pieman_edited`** is useful for **`audioTranscribe`** (large `.wav`) and **`causalRating`** on `pieman_edited_events.xlsx`.

**File versioning is a core feature.** Automated runs write `{subj_id}_{method}.ext` (or `{story}_…` for story-level steps); your hand-edited versions are saved as `{subj_id}_{ratername}-edit.ext` and never overwrite the originals. The web UI lets you switch between versions via a dropdown, and the `-edit` files are what you export for analysis.

---

## Using the web interface

The app is a **local Flask site** (default **`http://127.0.0.1:5000`**). Start it from the project directory in any of these ways:

| How | What to do |
|-----|-------------|
| **Terminal** (macOS, Linux, Windows) | `narraters serve` — usually opens your browser automatically. |
| **macOS — script** | Double-click **`server/START_HERE.command`** (can install missing deps on first run). |
| **macOS — app bundle** | Build once: `bash packaging/macos/build_app_bundle.sh`, then double-click **`narRater.app`**. Not committed to Git; see the icon at the top of this README. |

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

Each of the six steps is a separate **`narraters`** subcommand with its own **`--method`** (and related options). Use the CLI for **scripts**, **clusters**, or **reproducible** runs—**with or without** the web UI, and **with any subset** of steps your study uses. General shape:

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

Requires `pip install "narraters[audio]"` (or `pip install -e ".[audio]"` from a clone). Text-only projects can skip Step 1 entirely.

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
| `--method` | `test`, `api`, `gemma-ollama`, `rmatch` | `test` is keyword-based, free, and always available; `rmatch` needs `pip install "narraters[match]"` |
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

**`audioTranscribe` (step 1)**  
No paper cited here; validation is Whisper/WhisperX accuracy on your audio and manual spot checks. See [Installation](#installation) (`[audio]` extra) and the helper scripts above.

**`eventSegment` (step 2)**  
Michelmann, Kumar, **Norman**, & Toneva, *Large language models can segment narrative events similarly to humans*: GPT-3 zero-shot boundaries correlate with human segmentations and approximate crowd consensus on continuous text—useful precedent for LLM-based story segmentation in narRaters. [arXiv:2301.10297](https://arxiv.org/abs/2301.10297), [Behavior Research Methods (2025)](https://doi.org/10.3758/s13428-024-02569-z), [companion code](https://github.com/s-michelmann/GPT_event_segmentation).

**`sentenceCorrect` (step 3)**  
No external benchmark listed; the package enforces minimal, non-paraphrasing edits. Exercise the recall-correction helpers if you change rules or prompts.

**`textParsing` (step 4)**  
No paper cited here; clause-level structure is checked against the same independent-clause logic as **`eventSegment`** (see above and the web UI tooltips).

**`textMatching` (step 5)**  
- **Norman lab / Computational Memory (Princeton)** — Toneva et al., *Memory for long narratives* (presentation materials, 2021; includes **K. A. Norman**): long-form novel recall scored by aligning recalled events to chapter events with GPT-2 representations, toward scalable scoring without fully manual coding. [PDF (Princeton Computational Memory Lab)](https://compmem.princeton.edu/wp/wp-content/uploads/2022/05/memory-for-long-narratives.pdf).  
- **rMatch** — Kressin Palacios & Arekar: embedding-based recall-to-event matching with human-data validation. [GabrielKP/rMatch](https://github.com/GabrielKP/rMatch).

**`causalRating` (step 6)**  
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
├── data/                         # inputs (bundled pieman_edited + the_siren examples; your files stay local)
├── output/                       # pipeline outputs (sample outputs for the same examples)
├── demo/                         # smaller demo dataset (lighthouse)
├── packaging/macos/              # build script for the `.app` bundle
├── SETUP_API.md                  # user-facing API key and provider setup
└── .env.example                  # template for local API keys (copy to `.env`)
```

---

## Further reading

**`narRater_Tutorial.pdf`** (repo root) is an illustrated, click-by-click tour of the web UI—good next step after [Getting started](#getting-started).

- **[`SETUP_API.md`](SETUP_API.md)** — API keys for Anthropic, OpenAI, and Hugging Face; which pipeline steps need which keys.
- **[`scripts/prompt/README.md`](scripts/prompt/README.md)** — prompt template conventions for LLM-backed methods.

Maintainer-only design notes, tutorial PDF build scripts, and internal handbooks are **not** published in this repository; keep those materials private to your team.

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
