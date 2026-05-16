"""Canonical pipeline step type identifiers (camelCase).

Six conceptual steps; ``audioTranscribe`` uses ``audioScope`` (``story`` | ``recall``)
when both story and recall transcription appear in one pipeline.
"""

from __future__ import annotations

from typing import Any

AUDIO_TRANSCRIBE = "audioTranscribe"
EVENT_SEGMENT = "eventSegment"
SENTENCE_CORRECT = "sentenceCorrect"
TEXT_PARSING = "textParsing"
TEXT_MATCHING = "textMatching"
CAUSAL_RATING = "causalRating"

CANONICAL_STEP_TYPES = frozenset(
    {
        AUDIO_TRANSCRIBE,
        EVENT_SEGMENT,
        SENTENCE_CORRECT,
        TEXT_PARSING,
        TEXT_MATCHING,
        CAUSAL_RATING,
    }
)

# legacy kebab-case type -> (canonical type, audioScope or None)
_LEGACY_STEP_TYPE: dict[str, tuple[str, str | None]] = {
    "story-audio-transcribe": (AUDIO_TRANSCRIBE, "story"),
    "recall-audio-transcribe": (AUDIO_TRANSCRIBE, "recall"),
    "story-event-segment": (EVENT_SEGMENT, None),
    "spell-grammar-correct": (SENTENCE_CORRECT, None),
    "recall-parse": (TEXT_PARSING, None),
    "recall-match-events": (TEXT_MATCHING, None),
    "causal-rate-events": (CAUSAL_RATING, None),
}

STEP_DISPLAY_NAMES: dict[str, str] = {
    AUDIO_TRANSCRIBE: "Audio Transcribe",
    EVENT_SEGMENT: "Event Segment",
    SENTENCE_CORRECT: "Sentence Correct",
    TEXT_PARSING: "Text Parsing",
    TEXT_MATCHING: "Text Matching",
    CAUSAL_RATING: "Causal Rating",
}

AUDIO_SCOPE_LABELS = {"story": "Story", "recall": "Recall"}


def normalize_step_type(step_type: str | None) -> str:
    if not step_type:
        return ""
    entry = _LEGACY_STEP_TYPE.get(step_type)
    if entry:
        return entry[0]
    return step_type


def audio_scope_for_step(step: dict[str, Any] | None) -> str | None:
    if not step:
        return None
    raw_type = step.get("type") or ""
    legacy = _LEGACY_STEP_TYPE.get(raw_type)
    if legacy and legacy[0] == AUDIO_TRANSCRIBE:
        return legacy[1] or step.get("audioScope") or "recall"
    if normalize_step_type(raw_type) == AUDIO_TRANSCRIBE:
        return step.get("audioScope") or "recall"
    return None


def normalize_pipeline_step(step: dict[str, Any]) -> dict[str, Any]:
    raw_type = step.get("type") or ""
    legacy = _LEGACY_STEP_TYPE.get(raw_type)
    if not legacy:
        return step
    new_type, scope = legacy
    out = dict(step)
    out["type"] = new_type
    if scope:
        out["audioScope"] = scope
    return out


def normalize_pipeline_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not config:
        return config
    steps = config.get("steps")
    if not steps:
        return config
    return {**config, "steps": [normalize_pipeline_step(s) for s in steps]}


def step_runtime_key(step: dict[str, Any] | None, step_type: str | None = None) -> str:
    """Map key for routing, I/O streams, and script dispatch (audio includes scope)."""
    if step is not None:
        t = normalize_step_type(step.get("type"))
        if t == AUDIO_TRANSCRIBE:
            scope = audio_scope_for_step(step) or "recall"
            return f"{AUDIO_TRANSCRIBE}:{scope}"
        return t
    t = normalize_step_type(step_type)
    return t


def step_display_label(step: dict[str, Any]) -> str:
    t = normalize_step_type(step.get("type"))
    base = STEP_DISPLAY_NAMES.get(t, t)
    if t == AUDIO_TRANSCRIBE:
        scope = audio_scope_for_step(step) or "recall"
        return f"{base} ({AUDIO_SCOPE_LABELS.get(scope, scope)})"
    return base


def step_matches(
    step: dict[str, Any],
    canonical: str,
    *,
    audio_scope: str | None = None,
) -> bool:
    t = normalize_step_type(step.get("type"))
    if t != canonical:
        return False
    if canonical == AUDIO_TRANSCRIBE and audio_scope is not None:
        return (audio_scope_for_step(step) or "recall") == audio_scope
    return True
