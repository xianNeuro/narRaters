# CLAUDE.md

Guidance for Claude Code (and other contributors) when working in this repository.

## Provenance & attribution

The core pipeline scripts in `scripts/` (`1_audio-transcribe.py` … `6_causal-rater.py`)
and the underlying processing logic were **authored by Xian Li and written by
hand**. They were later adapted, extended, and integrated (web UI, packaging,
tooling) with the help of Claude Code.

> **Attribution rule:** Do **not** state or imply anywhere in the software,
> docs, comments, commit messages, or generated reports that Claude Code or any
> AI wrote the core pipeline scripts or the core algorithms. They are
> human-authored work by Xian Li. AI assistance is limited to adaptation and
> surrounding tooling. Preserve this distinction in any new documentation.

## What this is

`narRaters` is an open-source tool for processing narrative recall data. Raw
audio or text recalls run through a six-step pipeline (transcription →
segmentation → spell/grammar correction → parsing → event matching → causal
rating), with a Flask web UI for interactive review and human editing at each
step. There are no user accounts or passwords; an editor simply enters a
**rater name** used to label exported files.

## Running the project

```bash
pip install -e .              # minimal install (no heavy ML deps by default)
narraters serve               # start the web UI (opens http://localhost:5000)

# macOS alternatives
bash server/START_HERE.command
# or double-click narRater.app
```

Every step is also a CLI subcommand:

```bash
narraters transcribe --kind recall            # Step 1 (needs the [audio] extra)
narraters segment   --method clause           # Step 2: clause | fine | coarse | api
narraters correct   --method rules            # Step 3: rules | gemma-ollama
narraters parse     --method rules            # Step 4: rules | ollama
narraters match     --test-mode               # Step 5: test | api | gemma-ollama | rmatch
narraters rate      --method linguistic       # Step 6: linguistic | api | manual
narraters <step> --help                       # full options for any step
```

The default install is deliberately minimal; heavier methods live behind
optional extras (`[api]`, `[audio]`, `[nlp]`, `[match]`, `[local-llm]`). LLM
methods read keys from a `.env` file in the project root (see
`developer/SETUP_API.md`). Local-model methods run a RAM/disk preflight and
warn before they can wedge the machine.

## Validation / testing

No pytest suite. Validation is done via helper scripts, e.g.:

```bash
python helpers/test_recall_rater_single_subject.py
python helpers/test_story_event_segment.py
```

## Build the macOS app bundle

```bash
bash packaging/macos/build_app_bundle.sh
```

## Architecture

### Web interface (`server/web-interface.py`)

A single large Flask file: routes, the per-request directory-listing cache,
and subprocess calls to the pipeline scripts. Key routes:

- `/pipeline-config` — drag-and-drop pipeline builder; the rater name is
  entered at the top of the Pipeline Flow panel
- `/` — main dashboard (status grid; click a cell to auto-process a step)
- `/subject/<id>`, `/story/<name>` — tabbed inspection / human-editing view

There is no authentication layer; the UI binds to loopback by default.

### Pipeline scripts (`scripts/1_*.py` … `scripts/6_*.py`)

Each script is standalone and multi-method. Adding a backend means adding a
new `--method` branch in the relevant script. LLM prompt templates live in
`scripts/prompt/` and are loaded at runtime (overridable via env vars).
**These scripts are the human-authored core — see the attribution rule above.**

### CLI (`src/narraters/cli.py`)

`argparse` entry point exposing the `narraters` command; each subcommand
translates flags/env vars and delegates to the matching `scripts/N_*.py`.

### Helpers (`helpers/`)

`software_paths.py` — canonical path resolution (use this rather than
hardcoding paths). `gemma_environment.py` / `ollama_gemma_e4b.py` —
Ollama/Gemma readiness. `disk_space.py` / `resource_preflight.py` —
free-disk and heavy-method (RAM) preflight checks.

### Data flow

- **Inputs**: `data/2_story_transcript/{story}.txt`,
  `data/3_story_events/{story}_events.xlsx` (columns `event`, `story_texts`),
  `data/5_recall_texts/{subj_id}.txt`
- **Outputs**: `output/recall_*/` and `output/*_audio-transcribed/`
- **Naming**: automated files use `{subj_id}_{method_slug}.ext`; human-edited
  files use `{subj_id}_{ratername}-edit.ext`

File versioning is a core feature — never overwrite an existing file without
the appropriate suffix; the UI lets users switch versions via a dropdown.

## Key design constraints

- **Minimal corrections**: the spell/grammar step fixes errors only — it never
  rewrites or paraphrases
- **Independent-clause validation**: each segment must contain at least one
  independent clause
- **Preserve verbatim source**: every step keeps the original wording outside
  explicit corrections
- **Human-editable at every step**: outputs are always plain text or Excel,
  never opaque formats
- **Safe by default**: a fresh install pulls no multi-GB ML stacks; local
  models are gated by a resource preflight

## Documentation

`developer/README.md` is the contributor handbook (per-step I/O contracts,
editing workflows, design principles). Read it before changing pipeline logic.
End-user docs: `README.md` and `narRater_Tutorial.pdf`.
