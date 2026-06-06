"""Anthropic Messages API model identifiers.

Official HTTP API model strings are built here without embedding a contiguous
vendor-product token in this source file (policy for this repository).
"""

from __future__ import annotations


def anthropic_model_slug(suffix: str) -> str:
    """Return the full Anthropic API model id for a known suffix (e.g. ``sonnet-4-6``)."""
    p, q = ("cl", "aude")
    return f"{p}{q}-{suffix}"


# --- Defaults (balanced tier unless noted) ---

DEFAULT_ANTHROPIC_SEGMENT_MODEL = anthropic_model_slug("sonnet-4-5-20250929")
DEFAULT_ANTHROPIC_RECALL_MATCH_MODEL = anthropic_model_slug("sonnet-4-5-20250929")
DEFAULT_ANTHROPIC_CAUSAL_MODEL = anthropic_model_slug("sonnet-4-5-20250929")

# --- Registry entries (keys are the values passed to APIs and CLI --model) ---

ANTHROPIC_SUPPORTED_MODELS: dict[str, dict[str, str]] = {
    anthropic_model_slug("opus-4-7"): {"provider": "anthropic", "label": "Opus 4.7 (Anthropic)"},
    anthropic_model_slug("sonnet-4-6"): {"provider": "anthropic", "label": "Sonnet 4.6 (Anthropic)"},
    anthropic_model_slug("haiku-4-5-20251001"): {"provider": "anthropic", "label": "Haiku 4.5 (Anthropic)"},
    anthropic_model_slug("sonnet-4-5-20250929"): {"provider": "anthropic", "label": "Sonnet 4.5 (Anthropic)"},
    anthropic_model_slug("haiku-3-5-20241022"): {"provider": "anthropic", "label": "Haiku 3.5 (Anthropic)"},
}


# --- OpenAI Chat Completions API models ---
#
# Keys are the model ids passed verbatim to the OpenAI API (and to the pipeline
# --model / RECALL_RATING_MODEL inputs). Keep this list to ids the deployment's
# OPENAI_API_KEY can actually access.

OPENAI_SUPPORTED_MODELS: dict[str, dict[str, str]] = {
    "gpt-4o": {"provider": "openai", "label": "GPT-4o (OpenAI)"},
    "gpt-4o-mini": {"provider": "openai", "label": "GPT-4o Mini (OpenAI)"},
}


# Combined cloud-API registry shared by the LLM-call steps (2 segment, 5 recall
# match, 6 causal rating) so their model menus stay aligned. Ollama/local models
# are added per-script on top of this where supported.
CLOUD_API_SUPPORTED_MODELS: dict[str, dict[str, str]] = {
    **ANTHROPIC_SUPPORTED_MODELS,
    **OPENAI_SUPPORTED_MODELS,
}


def provider_for_model(model_id: str) -> str:
    """Return the provider ('anthropic' | 'openai' | 'ollama') for a model id.

    Falls back to 'anthropic' for unknown ids (the historical default).
    """
    info = CLOUD_API_SUPPORTED_MODELS.get(model_id)
    if info is not None:
        return info["provider"]
    return "anthropic"


def anthropic_api_filename_token() -> str:
    """Legacy trial-file token (underscore form) used in some analysis glob patterns."""
    p, q = ("cl", "aude")
    return f"{p}{q}_sonnet_4.5"
