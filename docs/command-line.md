<p align="center">
  <a href="../README.md">README</a> &nbsp;·&nbsp;
  <a href="install.md">Install</a> &nbsp;·&nbsp;
  <a href="input-data.md">Input data</a> &nbsp;·&nbsp;
  <a href="web-interface.md">Web interface</a> &nbsp;·&nbsp;
  <a href="troubleshooting.md">Troubleshooting</a> &nbsp;·&nbsp;
  <strong>Command-line</strong> &nbsp;·&nbsp;
  <a href="../LICENSE">License</a>
</p>

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
