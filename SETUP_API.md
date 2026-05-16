# API key setup (user guide)

narRaters can call **Anthropic**, **OpenAI**, and **Hugging Face** for optional LLM-heavy methods, or use **local Ollama** with no cloud key.

## Quick setup

```bash
# Anthropic (Messages API — model ids are chosen in the web UI or via --model)
export ANTHROPIC_API_KEY='your-api-key-here'

# OpenAI
export OPENAI_API_KEY='your-api-key-here'
```

Get keys from:

- Anthropic — https://console.anthropic.com/
- OpenAI — https://platform.openai.com/api-keys

Optional interactive helper:

```bash
bash scripts/setup_api_key.sh
```

## Hugging Face

Some local-model paths use Hugging Face. Set `HF_TOKEN` in `.env` (copy from `.env.example`):

```bash
cp .env.example .env
# edit .env
```

## Which steps need which key?

| Capability | Anthropic | OpenAI | HF token | Ollama only |
|------------|:---------:|:------:|:--------:|:-----------:|
| Story segmentation — API cloud models | optional | optional | — | optional presets |
| Recall match — API batch | optional | — | — | optional Gemma path |
| Causal rating — API | optional | optional | — | — |
| Local Gemma / Llama via Ollama | — | — | — | yes (no cloud key) |
| rMatch (Step 5) | — | — | optional | — |

Rule-based defaults (`clause`, `test`, `linguistic`, etc.) need **no** API keys.

## Model IDs

Exact `--model` strings for Anthropic tiers are listed by:

```bash
narraters segment --list-models
```

Use the same model keys in the web UI dropdowns for API-backed steps.

## More detail

- Prompt files: `scripts/prompt/README.md`
- End-user overview: `README.md`
