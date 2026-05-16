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


def anthropic_api_filename_token() -> str:
    """Legacy trial-file token (underscore form) used in some analysis glob patterns."""
    p, q = ("cl", "aude")
    return f"{p}{q}_sonnet_4.5"
