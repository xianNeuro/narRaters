# API Key Setup

This document lives in **`developer/`**; paths below are relative to the **`software/`** project root unless noted.

narRater optionally uses LLM APIs or **local Ollama** for several steps:

- **Story Event Segmentation** (`scripts/2_story-event-segment.py`): Claude, GPT-4o/Mini, **Gemma 4 E4B / Llama via Ollama** (no cloud key)
- **Spell & Grammar** (`scripts/3_spell-grammar-correct.py`): **Gemma 4** via Hugging Face or **Ollama**
- **Recall Parse** (`scripts/4_parse-texts.py`): **Gemma 4 via Ollama** (`RECALL_PARSE_METHOD=ollama`)
- **Recall Rating** (`scripts/5_recall-rater.py`): Claude API or **same batch prompt via Ollama** (`RECALL_RATING_BACKEND=ollama`)

Rule-based and manual paths require no key.

## Local Gemma 4 (Ollama)

Install [Ollama](https://ollama.com/), then pull a Gemma 4 E4B-compatible tag (default in this project: `gemma4:e4b`). Ensure `ollama serve` is running (the desktop app starts it). Override host with `OLLAMA_HOST` if needed. Optional env vars: `SPELL_GRAM_OLLAMA_MODEL`, `RECALL_PARSE_OLLAMA_MODEL`, `RECALL_RATING_OLLAMA_MODEL`, `EVENT_SEGMENT_OLLAMA_MODEL`.

## Quick Setup

Set the environment variable for the provider you plan to use:

```bash
# Anthropic (Claude models)
export ANTHROPIC_API_KEY='your-api-key-here'

# OpenAI (GPT models)
export OPENAI_API_KEY='your-api-key-here'
```

Verify:
```bash
echo $ANTHROPIC_API_KEY | head -c 20
echo $OPENAI_API_KEY | head -c 20
```

## Persistent Setup (Optional)

Add to your shell profile so the key is available in every terminal session.

**For zsh** (default on macOS):
```bash
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
echo 'export OPENAI_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

**For bash**:
```bash
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.bash_profile
echo 'export OPENAI_API_KEY="your-api-key-here"' >> ~/.bash_profile
source ~/.bash_profile
```

Or use the interactive helper script:
```bash
./scripts/setup_api_key.sh
```

## Get Your API Keys

**Anthropic (Claude)**:
1. Visit https://console.anthropic.com/
2. Sign in or create an account
3. Navigate to API Keys section
4. Create a new key and copy it

**OpenAI (GPT)**:
1. Visit https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key

## Which Key Do I Need?

| Pipeline Step | Anthropic Key | OpenAI Key |
|---------------|:---:|:---:|
| Story Event Segmentation — Claude models | Required | — |
| Story Event Segmentation — GPT models | — | Required |
| Recall Rating — API method (Claude Sonnet) | Required | — |
| Story Event Segmentation — Ollama (Gemma/Llama presets) | Not needed | Not needed |
| Spell / Recall Parse / Recall Rating — Ollama Gemma | Not needed | Not needed |
| All other non-API methods (rule-based, test, manual) | Not needed | Not needed |

## Testing

```bash
# Test event segmentation with API
python scripts/2_story-event-segment.py --input data/2_story_transcript/my_story.txt --output data/3_story_events_test --method api

# Test recall rater with API
python scripts/5_recall-rater.py
```

If no API key is set, the software falls back to non-API methods automatically.
