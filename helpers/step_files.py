"""Flexible recognition of pipeline input/output files across naming conventions.

A single place that answers "does this file belong to (item, step)?" so the
dashboard status grid, the per-step loaders, and the completed-methods endpoint
all agree — regardless of which naming convention or tabular format produced it.

Recognised, for each step, in any of ``.xlsx/.xls/.csv/.tsv`` (and ``.txt`` for the
text steps):

  - **Canonical subject-first**: ``{item}_parsed``, ``{item}_rate-recall``,
    ``{story}_events``, ``{story}_causal``, ``{item}`` / ``{item}_corrected`` …
    optionally with a ``-{method}`` tag and/or a trailing ``_{rater}-edit``.
  - **Legacy verbose**: the same step token appearing anywhere in a longer stem
    that still contains the item id, e.g.
    ``the_siren_events_the_siren_sub-02_rate-recall_manual_GentleTiger-edit.xlsx``.
  - **Alternative ``story-`` form**: ``story-{story}-segmented`` (events) and
    ``story-{story}_sub-{id}-recall-matched`` (rated), where the story is the part
    before ``_sub-`` and the participant is ``sub-{id}``.

Cross-step disambiguation: each step lists *foreign* tokens that, if present,
mean the file belongs to a different step (so a rated/causal file is never
mistaken for a story-events file).
"""
from __future__ import annotations

import re
from pathlib import Path

# Extensions we treat as tabular (parsed/rated/events/causal) and text.
TABULAR_EXTS = (".xlsx", ".xls", ".csv", ".tsv")
TEXT_EXTS = (".txt", ".md")
ALL_STEP_EXTS = TABULAR_EXTS + TEXT_EXTS

# (positive step tokens, foreign tokens that disqualify) — matched on lower-cased stem.
_STEP_DEFS = {
    "eventSegment": (("_events", "-segmented", "-segment"),
                     ("rate-recall", "recall-matched", "_parsed", "-parsed", "textparsing", "causal", "recall-corrected")),
    # NB: legacy verbose parsed/rated/causal names embed a ``{story}_events`` prefix
    # as provenance, so ``_events`` must NOT be a foreign token for those steps — the
    # step is keyed off its own token (``_parsed``/``-parsed``/``textparsing``) plus the
    # absence of other steps'. (Canonical parsed uses ``_parsed``; the alternative
    # ``story-...-parsed.csv`` convention uses ``-parsed``; legacy uses ``textParsingd``.)
    "textParsing": (("_parsed", "-parsed", "textparsing"),
                    ("rate-recall", "recall-matched", "causal")),
    "textMatching": (("rate-recall", "recall-matched"),
                     ("causal", "_parsed", "-parsed", "-segment")),
    "causalRating": (("causal", "rate-causal"),
                     ("rate-recall", "recall-matched", "_parsed", "-parsed")),
    # Corrected text has no mandatory token (canonical is just ``{item}.txt``); see
    # special handling in ``file_belongs_to_step``.
    "sentenceCorrect": (("_corrected", "recall-corrected", "_spell-"),
                        ("_parsed", "rate-recall", "recall-matched", "causal", "_events")),
}

_STORY_LEVEL = {"eventSegment", "causalRating"}


def _story_and_sub(item_id: str):
    """Return (story_name, sub_token) for an item id like ``the_siren_sub-02``.

    sub_token is the ``sub-..`` participant fragment, or None.
    """
    m = re.match(r"^(.*)_(sub[-_]?\w+)$", item_id)
    if m:
        return m.group(1), m.group(2)
    return item_id, None


def _stem_has_item(stem_l: str, item_id: str, story_name: str | None, is_story: bool) -> bool:
    item_l = (item_id or "").lower()
    if item_l and item_l in stem_l:
        return True
    story, sub = _story_and_sub(item_id or "")
    story_l = (story_name or story or "").lower()
    if is_story or story_name is not None or sub is not None:
        if story_l and story_l in stem_l:
            # For a participant, also require the sub fragment so we don't match a
            # sibling subject of the same story. Story-level steps match on story alone.
            if is_story or sub is None or sub.lower() in stem_l:
                return True
    return False


def file_belongs_to_step(filename, step_type: str, item_id: str,
                         story_name: str | None = None, is_story: bool = False) -> bool:
    """True if ``filename`` is an input/output for (item_id, step_type)."""
    name = Path(filename).name
    stem = Path(name).stem
    ext = Path(name).suffix.lower()
    if step_type in ("audioTranscribe:story", "audioTranscribe:recall"):
        # transcripts are plain text named after the item / audio file
        return ext in TEXT_EXTS and _stem_has_item(stem.lower(), item_id, story_name, is_story)
    defs = _STEP_DEFS.get(step_type)
    if not defs:
        return False
    positives, foreign = defs
    stem_l = stem.lower()
    allowed = TABULAR_EXTS if step_type != "sentenceCorrect" else TEXT_EXTS
    if ext not in allowed:
        return False
    # Story-level steps (events, causal) are named after the story, so match on the
    # story even when called with a subject id.
    story_level = step_type in _STORY_LEVEL
    if not _stem_has_item(stem_l, item_id, story_name, is_story or story_level):
        return False
    if any(f in stem_l for f in foreign):
        return False
    if any(tok in stem_l for tok in positives):
        return True
    # sentenceCorrect canonical has no token: ``{item}.txt`` or ``{item}_{rater}-edit.txt``
    if step_type == "sentenceCorrect":
        item_l = (item_id or "").lower()
        base = re.sub(r"_\w+-edit$", "", stem_l)
        return base == item_l or stem_l == item_l
    return False


def find_step_files(directory, step_type: str, item_id: str,
                    story_name: str | None = None, is_story: bool = False) -> list:
    """All files under ``directory`` that belong to (item_id, step_type), newest first."""
    d = Path(directory)
    if not d.is_dir():
        return []
    out = []
    for f in d.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in ALL_STEP_EXTS:
            continue
        if file_belongs_to_step(f.name, step_type, item_id, story_name, is_story):
            out.append(f)
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


def has_step_output(directory, step_type: str, item_id: str,
                    story_name: str | None = None, is_story: bool = False) -> bool:
    return bool(find_step_files(directory, step_type, item_id, story_name, is_story))
