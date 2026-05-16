#!/usr/bin/env python3
"""
Script to segment story transcript into discrete events.

Reads story transcript from data/2_story_transcript/ folder, segments it into
discrete events based on semantic boundaries and narrative structure, and outputs
to data/3_story_events/{subj_id}_events.xlsx.

Segmentation methods:
1. clause   - Clause-level segmentation (finest granularity, like recall parsing)
2. fine     - Fine-grained event segmentation (default; each action/state change = new event)
3. coarse   - Coarse-grained event segmentation (scene-level; major shifts only)
4. api      - LLM API call with configurable model and prompt version

Event boundaries are identified based on:
- Scene changes, shifts of topic, location, time, action, emotion
- Natural sentence endings (periods, question marks, exclamation marks)
- Semantic shifts (subject changes, action changes, location changes)
- Narrative transitions (temporal shifts, scene changes)
"""

import os
import sys
from pathlib import Path
import re


def _software_package_root() -> Path:
    """Parent of ``scripts/`` when this file lives under ``scripts/``; else the package root."""
    d = Path(__file__).resolve().parent
    return d.parent if d.name == "scripts" else d


_pr = _software_package_root()
if str(_pr) not in sys.path:
    sys.path.insert(0, str(_pr))


import pandas as pd
import json
import time


# ==============================
# SETTINGS
# ==============================

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4000
TEMPERATURE = 0

SYSTEM_PROMPT = """You are a careful annotation assistant.
You must not rewrite, paraphrase, or modify any story text.
Copy the story word-for-word and segment it into events by starting a new line whenever one event ends and another begins."""

SUPPORTED_MODELS = {
    'claude-opus-4-7': {'provider': 'anthropic', 'label': 'Claude Opus 4.7'},
    'claude-sonnet-4-6': {'provider': 'anthropic', 'label': 'Claude Sonnet 4.6'},
    'claude-haiku-4-5-20251001': {'provider': 'anthropic', 'label': 'Claude Haiku 4.5'},
    'claude-sonnet-4-5-20250929': {'provider': 'anthropic', 'label': 'Claude Sonnet 4.5'},
    'claude-haiku-3-5-20241022': {'provider': 'anthropic', 'label': 'Claude Haiku 3.5'},
    'gpt-4o': {'provider': 'openai', 'label': 'GPT-4o'},
    'gpt-4o-mini': {'provider': 'openai', 'label': 'GPT-4o Mini'},
    'gemma4-e4b-ollama': {
        'provider': 'ollama',
        'label': 'Gemma 4 E4B (Ollama local)',
        'ollama_tag': 'gemma4:e4b',
    },
    'llama5.3-ollama': {
        'provider': 'ollama',
        'label': 'Llama 5.3 (Ollama local; override tag with EVENT_SEGMENT_OLLAMA_MODEL)',
        'ollama_tag': 'llama5.3',
    },
    'llama3.3-ollama': {
        'provider': 'ollama',
        'label': 'Llama 3.3 (Ollama local; override tag with EVENT_SEGMENT_OLLAMA_MODEL)',
        'ollama_tag': 'llama3.3',
    },
}


def _slug_for_events_api_model(model_key: str) -> str:
    """
    Filesystem-safe token for API outputs: {story}_events-api_model-{slug}.xlsx

    For Ollama-backed presets, uses EVENT_SEGMENT_OLLAMA_MODEL when set, otherwise
    the preset's ollama_tag. Otherwise uses the config key or model id string.
    """
    meta = SUPPORTED_MODELS.get(model_key, {})
    if meta.get("provider") == "ollama":
        raw = (
            os.environ.get("EVENT_SEGMENT_OLLAMA_MODEL")
            or (meta.get("ollama_tag") or "")
            or model_key
        )
    else:
        raw = model_key
    s = str(raw).replace(":", "_").replace("/", "_")
    s = re.sub(r"[^\w.\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("._-")
    return s or "unknown_model"


# ==============================
# PROMPT LOADING
# ==============================

DEFAULT_PROMPT = (
    "An event is an ongoing coherent situation. The following story needs to be "
    "copied and segmented into events. Copy the following story word-for-word and "
    "start a new line whenever one event ends and another begins. This is the story:"
)


def get_prompt_dir():
    return Path(__file__).resolve().parent / "prompt"


def list_event_segment_prompts():
    """Return list of available event segmentation prompt filenames."""
    prompt_dir = get_prompt_dir()
    if not prompt_dir.exists():
        return []
    prompts = sorted(
        f.name for f in prompt_dir.glob("event_segment*.txt")
    )
    return prompts


def load_event_segmentation_prompt(prompt_version=None):
    """
    Load an event segmentation prompt from the scripts/prompt/ folder.
    
    Args:
        prompt_version: Filename (e.g. 'event_segment_v2.txt') or None for default.
    
    Returns:
        Prompt text as string.
    """
    prompt_dir = get_prompt_dir()

    if prompt_version:
        prompt_file = prompt_dir / prompt_version
    else:
        prompt_file = prompt_dir / "event_segment.txt"

    if prompt_file.exists():
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read {prompt_file}: {e}")

    return DEFAULT_PROMPT


# ==============================
# API CLIENT
# ==============================

def get_api_client(model=None, api_key_override=None):
    """
    Initialize and return an API client for the given model.

    Args:
        model: Model identifier string (from SUPPORTED_MODELS).
        api_key_override: If provided, use this key instead of env var.

    Returns:
        (client, provider) tuple.
    """
    model = model or DEFAULT_MODEL
    info = SUPPORTED_MODELS.get(model)
    if info is None:
        info = {'provider': 'anthropic'}
    provider = info['provider']

    if provider == 'ollama':
        return None, 'ollama'

    if provider == 'openai':
        import openai
        api_key = api_key_override or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Please set it with: export OPENAI_API_KEY='your-api-key'"
            )
        client = openai.OpenAI(api_key=api_key)
        return client, provider
    else:
        import anthropic
        api_key = api_key_override or os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
            )
        client = anthropic.Anthropic(api_key=api_key)
        return client, provider


# ==============================
# HELPER: Sentence Splitting
# ==============================

def _split_into_sentences(text):
    """
    Split text into sentences at punctuation boundaries, skipping abbreviations.
    Returns list of (start, end, sentence_text) tuples referencing positions in text.
    """
    sentence_boundaries = []

    for match in re.finditer(r'([.!?])\s+([A-Z])', text):
        pos = match.start()
        before_period = text[max(0, pos - 3):pos]
        if re.search(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|Inc|Ltd|etc|vs|i\.e|e\.g)\s*$', before_period, re.IGNORECASE):
            continue
        if re.search(r'\b[A-Z]\.\s*$', before_period):
            continue
        sentence_boundaries.append(match.start() + 1)

    for match in re.finditer(r'([.!?])(\s*["\']|$)', text):
        pos = match.start()
        group2 = match.group(2)
        if group2 and group2[0] in ('"', "'"):
            boundary = match.end()
        else:
            boundary = pos + 1
        if boundary not in sentence_boundaries:
            sentence_boundaries.append(boundary)

    sentence_boundaries.append(len(text))
    sentence_boundaries = sorted(set(sentence_boundaries))

    sentences = []
    prev = 0
    for boundary in sentence_boundaries:
        s = text[prev:boundary].strip()
        if s and len(s.split()) > 0:
            sentences.append((prev, boundary, s))
        prev = boundary

    return sentences


# ==============================
# HELPER: NLP & Clause Detection
# ==============================

_NLP_CACHE = {'nlp': None, 'loaded': False}


def _try_load_spacy():
    """Lazily load spaCy model (with optional benepar for constituency parsing).

    Returns the loaded nlp pipeline, or None if spaCy is not installed.
    The result is cached so the model is loaded at most once per process.
    """
    if _NLP_CACHE['loaded']:
        return _NLP_CACHE['nlp']
    _NLP_CACHE['loaded'] = True
    try:
        import spacy
        try:
            nlp = spacy.load('en_core_web_sm')
        except OSError:
            try:
                nlp = spacy.load('en_core_web_md')
            except OSError:
                _NLP_CACHE['nlp'] = None
                return None
        try:
            import benepar  # noqa: F401
            if 'benepar' not in nlp.pipe_names:
                nlp.add_pipe('benepar', config={'model': 'benepar_en3'})
        except (ImportError, Exception):
            pass
        _NLP_CACHE['nlp'] = nlp
        return nlp
    except ImportError:
        return None


_IMPERATIVE_RE = re.compile(
    r"^(Come|Go|Run|Stop|Wait|Look|Listen|Tell|Give|Take|Let|"
    r"Don't|Do|Please|Try|Keep|Make|Put|Get|Find|Leave|Stay|"
    r"Meet|Sit|Stand|Walk|Read|Write|Check|Follow|Remember|"
    r"Remain|Bring|Hold|Open|Close|Turn|Move|Help|Ask|Call|"
    r"Set|Think|See|Imagine|Consider|Note|Show|Send|Start|Back)\b",
    re.IGNORECASE,
)

_SUBJECT_RE = re.compile(
    r"\b(I|you|he|she|they|we|it|this|that|these|those|who|what|"
    r"everyone|someone|nobody|anybody|everything|something|nothing|there)\b",
    re.IGNORECASE,
)

_DET_SUBJECT_RE = re.compile(
    r"\b(the|a|an|my|his|her|their|our|its|your)\s+\w+",
    re.IGNORECASE,
)

_PROPER_SUBJECT_RE = re.compile(r"^[A-Z][a-z]{2,}(?:'s)?\s+")

_COMMON_INITIAL_VERBS = frozenset({
    'found', 'made', 'said', 'asked', 'told', 'went', 'came', 'got', 'saw',
    'left', 'thought', 'felt', 'heard', 'took', 'gave', 'put', 'ran',
    'let', 'set', 'began', 'started', 'stopped', 'wanted', 'needed', 'tried',
    'seemed', 'appeared', 'became', 'turned', 'looked', 'walked', 'talked',
    'called', 'brought', 'sat', 'stood', 'opened', 'closed', 'kept',
    'met', 'lived', 'noticed', 'realized', 'decided', 'remembered',
    'screamed', 'blinked', 'whispered', 'laughed', 'groaned', 'shook',
    'pulled', 'typed', 'entered', 'grabbed', 'handed', 'flipped', 'leaned',
    'raised', 'dropped', 'used', 'mapped', 'played', 'watched', 'covered',
    'discovered', 'showed', 'reached', 'touched', 'picked', 'pushed',
    'moved', 'helped', 'followed', 'passed', 'crossed', 'hoped', 'wished',
    'wondered', 'suggested', 'continued', 'added',
})

_FINITE_VERB_RE = re.compile(
    r"\b(is|are|was|were|am|be|been|being|have|has|had|do|does|did|"
    r"will|would|shall|should|can|could|may|might|must|need|dare|"
    r"said|asked|told|went|came|got|saw|knew|thought|felt|heard|"
    r"made|took|gave|found|put|ran|let|set|began|started|stopped|"
    r"wanted|needed|tried|seemed|appeared|became|turned|looked|"
    r"walked|talked|called|brought|sat|stood|opened|closed|kept|"
    r"left|met|lived|noticed|realized|decided|remembered|screamed|"
    r"blinked|whispered|laughed|groaned|shook|pulled|typed|entered|"
    r"grabbed|handed|flipped|leaned|raised|dropped)\b",
    re.IGNORECASE,
)

_PAST_TENSE_RE = re.compile(r"\b\w{2,}ed\b")
_CONTRACTED_VERB_RE = re.compile(r"'(s|re|ve|d|ll)\b")
_NEGATED_VERB_RE = re.compile(
    r"\b(isn't|aren't|wasn't|weren't|don't|doesn't|didn't|"
    r"won't|wouldn't|can't|couldn't|shouldn't|hadn't|haven't)\b",
    re.IGNORECASE,
)


def _has_independent_clause(text, nlp=None):
    """Check whether *text* contains at least one independent clause.

    An independent clause has a subject and a finite verb and can stand alone
    as a sentence.  Imperatives (verb-first with implied subject) also count.

    When *nlp* is a loaded spaCy model the check uses dependency parsing;
    otherwise a set of regex heuristics is used.
    """
    cleaned = re.sub(
        r'^[\s"\'"\u201c\u201d\u2018\u2019]+|[\s"\'"\u201c\u201d\u2018\u2019]+$',
        '', text,
    )
    words = cleaned.split()
    if not words or len(words) == 1:
        return False

    # --- spaCy path ---
    if nlp is not None:
        try:
            doc = nlp(cleaned)
            for sent in doc.sents:
                has_root = any(
                    t.dep_ == 'ROOT' and t.pos_ in ('VERB', 'AUX') for t in sent
                )
                has_subj = any(
                    t.dep_ in ('nsubj', 'nsubjpass', 'expl', 'csubj') for t in sent
                )
                if has_root and has_subj:
                    return True
                if has_root and sent[0].pos_ == 'VERB' and not has_subj:
                    return True
            return False
        except Exception:
            pass  # fall through to regex

    # --- Regex fallback ---
    if _IMPERATIVE_RE.match(cleaned):
        return True

    subject_source = None
    has_subject = bool(_SUBJECT_RE.search(cleaned))
    if has_subject:
        subject_source = 'pronoun'

    if not has_subject:
        det_match = _DET_SUBJECT_RE.search(cleaned)
        if det_match:
            verb_pos = None
            vm = _FINITE_VERB_RE.search(cleaned)
            if vm:
                verb_pos = vm.start()
            vm2 = _PAST_TENSE_RE.search(cleaned)
            if vm2 and (verb_pos is None or vm2.start() < verb_pos):
                verb_pos = vm2.start()
            if verb_pos is None or det_match.start() < verb_pos:
                has_subject = True
                subject_source = 'determiner'

    if not has_subject:
        if _PROPER_SUBJECT_RE.match(cleaned):
            first_word = words[0].rstrip("'s").lower()
            if first_word not in _COMMON_INITIAL_VERBS:
                has_subject = True
                subject_source = 'proper_noun'

    has_verb = bool(_FINITE_VERB_RE.search(cleaned))
    if not has_verb:
        has_verb = bool(_PAST_TENSE_RE.search(cleaned))
    if not has_verb:
        has_verb = bool(_CONTRACTED_VERB_RE.search(cleaned))
    if not has_verb:
        has_verb = bool(_NEGATED_VERB_RE.search(cleaned))

    return has_subject and has_verb


def _join_segments(a, b):
    """Join two text segments, avoiding space before leading punctuation."""
    b_stripped = b.lstrip()
    if b_stripped and b_stripped[0] in ',:;':
        return a.rstrip() + b_stripped
    return a + ' ' + b


def _merge_non_independent_clauses(events, nlp=None):
    """Merge segments that lack an independent clause into a neighbouring event.

    Rules:
      - Dialogue fragments (start with a quote mark) merge **forward** into the
        next event so the speaker's turn stays together.
      - Non-dialogue fragments merge **backward** into the preceding event.
      - A leading non-IC event with no predecessor merges forward.
    """
    if len(events) <= 1:
        return events

    result = []
    i = 0
    while i < len(events):
        event = events[i]
        if _has_independent_clause(event, nlp):
            result.append(event)
            i += 1
            continue

        stripped = event.strip()
        is_dialogue = (
            stripped.startswith('"') or stripped.startswith("'")
            or stripped.startswith('\u201c') or stripped.startswith('\u2018')
        )

        if is_dialogue and i + 1 < len(events):
            result.append(_join_segments(event, events[i + 1]))
            i += 2
        elif result:
            result[-1] = _join_segments(result[-1], event)
            i += 1
        elif i + 1 < len(events):
            result.append(_join_segments(event, events[i + 1]))
            i += 2
        else:
            result.append(event)
            i += 1

    return result


# ==============================
# METHOD 1: CLAUSE-LEVEL
# ==============================

def segment_story_clause_level(story_text):
    """
    Clause-level segmentation — the finest granularity.

    An independent clause has a subject and a predicate and can stand alone
    as a sentence.  Each segment represents one independent clause or one
    speech act.  Dialogue turns from different speakers are always separate.

    Rules (split at):
      1. Sentence boundaries (. ! ? followed by uppercase)
      2. Semicolons (always separate independent clauses)
      3. Non-restrictive relative clauses (, who/which/whom)
      4. Speech attribution + direct speech boundaries
      5. Commas between independent clauses (subject + verb on both sides)
      6. Coordinating conjunctions (and/but/so/yet) between independent clauses

    Post-processing:
      - Proof-check pass merges unjustified fragments
      - Independent-clause check merges any remaining non-IC segments

    If spaCy is installed, dependency parsing is used to validate clause
    boundaries.  Otherwise regex heuristics are applied.
    """
    if not story_text or not isinstance(story_text, str) or len(story_text.strip()) == 0:
        return []

    original_text = story_text.strip()
    sentences = _split_into_sentences(original_text)

    if not sentences:
        return [original_text]

    SPEECH_VERBS = (
        r'(?:said|says|say|asked|asks|ask|replied|replies|reply'
        r'|told|tells|tell|answered|answers|answer'
        r'|yelled|whispered|called|cried|shouted|exclaimed'
        r'|demanded|continued|added|interrupted|responded'
        r'|screamed|muttered|mumbled)'
    )

    PRONOUN_SUBJECTS = r'(?:I|you|he|she|they|we|it)'
    NOUN_SUBJECTS = (
        r'(?:the\s+[\w-]+|a\s+[\w-]+|an\s+[\w-]+|this\s+\w+'
        r'|that\s+\w+|my\s+\w+|his\s+\w+|her\s+\w+'
        r'|their\s+\w+|our\s+\w+)'
    )
    CI_SUBJECTS = rf'(?:{PRONOUN_SUBJECTS}|{NOUN_SUBJECTS})'
    PROPER_NOUN_SUBJECTS = r'(?:[A-Z][a-z]{2,})'
    ALL_SUBJECTS = rf'(?:{PRONOUN_SUBJECTS}|{NOUN_SUBJECTS}|{PROPER_NOUN_SUBJECTS})'

    _sv_re = re.compile(rf'\b{SPEECH_VERBS}\s*,\s', re.IGNORECASE)
    _attr_re = re.compile(
        rf'\s+(and\s+(?:{ALL_SUBJECTS}\s+)?|{ALL_SUBJECTS}\s+)$', re.IGNORECASE
    )
    _subj_after_re_ci = re.compile(rf'^{CI_SUBJECTS}\s+\w+', re.IGNORECASE)
    _subj_after_re_cs = re.compile(rf'^{PROPER_NOUN_SUBJECTS}\s+\w+')
    _subj_cap_re_ci = re.compile(rf'^({CI_SUBJECTS})\s+\w+', re.IGNORECASE)
    _subj_cap_re_cs = re.compile(rf'^({PROPER_NOUN_SUBJECTS})\s+\w+')
    _pron_re = re.compile(rf'\b{PRONOUN_SUBJECTS}\b', re.IGNORECASE)

    parsed_units = []
    for raw_start, end_pos, sentence in sentences:
        if not sentence or len(sentence.split()) == 0:
            continue

        # _split_into_sentences strips whitespace from the sentence text but
        # keeps the original positions.  Compute the offset so that positions
        # within the stripped sentence map back to the correct original-text
        # positions.
        raw_text = original_text[raw_start:end_pos]
        start_pos = raw_start + (len(raw_text) - len(raw_text.lstrip()))

        boundary_positions = set([0])

        # Pre-compute speech-verb data once per sentence for dialogue awareness
        _sv_matches = list(_sv_re.finditer(sentence))
        _sv_comma_pos = set()
        for m in _sv_matches:
            _sv_comma_pos.add(m.start() + m.group().index(','))
        _dialogue_zones = []
        for idx, m in enumerate(_sv_matches):
            zone_start = m.end()
            zone_end = (_sv_matches[idx + 1].start()
                        if idx + 1 < len(_sv_matches) else len(sentence))
            _dialogue_zones.append((zone_start, zone_end))

        def _in_dialogue(pos):
            return any(zs <= pos < ze for zs, ze in _dialogue_zones)

        # RULE 1: Semicolons always separate independent clauses
        for match in re.finditer(r';\s*', sentence):
            before = sentence[:match.start()]
            after = sentence[match.end():]
            if len(before.split()) >= 2 and len(after.split()) >= 2:
                boundary_positions.add(match.end())

        # RULE 2: Non-restrictive relative clauses (, who/which/whom)
        for match in re.finditer(r',\s+(who|which|whom)\s+', sentence, re.IGNORECASE):
            before = sentence[:match.start()]
            if len(before.split()) >= 4:
                boundary_positions.add(match.start() + 1)

        # RULE 3: Speech attribution + direct speech
        for match in _sv_matches:
            verb_start = match.start()
            before = sentence[:verb_start]

            if len(before.split()) < 4:
                continue

            attr_match = _attr_re.search(before)

            if attr_match:
                split_pos = attr_match.start() + 1
                narration = sentence[:split_pos]
                if len(narration.split()) >= 3:
                    boundary_positions.add(split_pos)
                else:
                    boundary_positions.add(verb_start)
            else:
                boundary_positions.add(verb_start)

        # RULE 4: Comma between two independent clauses
        for match in re.finditer(r',\s+', sentence):
            pos_after = match.start() + len(match.group())
            before = sentence[:match.start()]
            after = sentence[pos_after:]

            if re.match(r'^(who|which|whom)\s+', after, re.IGNORECASE):
                continue
            if re.match(r'^\s*(When|While|Although|Because|If|Since|Before|After|As)\s+', before[:25], re.IGNORECASE):
                continue
            if re.match(r'^\s*(At|On|In|By)\s+', before[:15], re.IGNORECASE) and len(before.split()) <= 6:
                continue
            if re.match(r'^(and|or|but|nor|so|yet)\s+', after, re.IGNORECASE):
                continue
            if re.match(r'^(followed|resulting|causing|making|leaving|hoping|especially|particularly)\s+', after, re.IGNORECASE):
                continue

            # Skip if this comma is a speech-verb comma or inside dialogue
            if match.start() in _sv_comma_pos:
                continue
            if _in_dialogue(match.start()):
                continue

            if len(before.split()) >= 6 and (_subj_after_re_ci.match(after) or _subj_after_re_cs.match(after)):
                boundary_positions.add(pos_after)

        # RULE 5: Coordinating conjunctions between independent clauses
        for match in re.finditer(r',?\s+(and|but|so|yet)\s+', sentence):
            conj = match.group(1).lower()
            before = sentence[:match.start()]
            after = sentence[match.start() + len(match.group()):]

            subj_match = _subj_cap_re_ci.match(after) or _subj_cap_re_cs.match(after)
            if not subj_match:
                continue

            if len(before.split()) < 6:
                continue

            # Skip if inside dialogue content
            if _in_dialogue(match.start()):
                continue

            if conj == 'and':
                new_subj = subj_match.group(1).lower()
                new_subj_last = new_subj.split()[-1] if ' ' in new_subj else new_subj
                prev_subjects = _pron_re.findall(before)
                if prev_subjects:
                    old_subject = prev_subjects[-1].lower()
                    if old_subject == new_subj_last:
                        continue

            boundary_positions.add(match.start())

        clause_boundaries = sorted(boundary_positions)
        clause_boundaries.append(len(sentence))

        for i in range(len(clause_boundaries) - 1):
            seg_start = clause_boundaries[i]
            seg_end = clause_boundaries[i + 1]
            segment = original_text[start_pos + seg_start:start_pos + seg_end]
            if segment and len(segment.split()) >= 1:
                parsed_units.append(segment)

    final = [p for p in parsed_units if p and len(p.split()) > 0]
    if not final:
        final = [original_text] if original_text.strip() else []

    final = _proof_check_segments(final)

    nlp = _try_load_spacy()
    final = _merge_non_independent_clauses(final, nlp)
    return final


def _proof_check_segments(segments):
    """Merge unjustified clause fragments back together.

    Protection: never merge across quotation-mark boundaries (dialogue turns).
    """
    if len(segments) <= 1:
        return segments

    result = []
    i = 0
    while i < len(segments):
        curr = segments[i]
        prev = result[-1] if result else None
        nxt = segments[i + 1] if i + 1 < len(segments) else None

        merge_with_prev = False
        merge_with_next = False
        curr_words = len(curr.split())
        curr_stripped = curr.strip()

        if curr_words <= 4 and re.match(r'^(At|On|In|By)\s+\d', curr, re.IGNORECASE) and nxt:
            merge_with_next = True
        if (curr_words <= 8
                and re.match(r'^(When|While|Although|Because|If)\s+', curr, re.IGNORECASE)
                and not re.search(r'[.!?]\s*$', curr_stripped) and nxt):
            merge_with_next = True
        if prev and re.match(r'^\s*and\s+', curr) and prev.rstrip().endswith(',') and curr_words <= 5:
            merge_with_prev = True
        if prev and re.search(r'\s(the|a|an)\s*$', prev.rstrip()) and curr:
            merge_with_prev = True

        # Protection: don't merge dialogue turns
        if merge_with_next and nxt and re.match(r'^\s*["\u201c\u201d\u2018\u2019]', nxt.strip()):
            merge_with_next = False
        if merge_with_prev and re.match(r'^\s*["\u201c\u201d\u2018\u2019]', curr_stripped):
            merge_with_prev = False

        if merge_with_next and nxt:
            joined = curr.rstrip().rstrip(',') + ' ' + nxt.lstrip()
            result.append(joined)
            i += 2
            continue
        elif merge_with_prev and prev:
            result[-1] = (prev.rstrip().rstrip(',') + ' ' + curr.lstrip()).strip()
            i += 1
            continue

        result.append(curr)
        i += 1

    return result


# ==============================
# METHOD 2: FINE-GRAINED EVENTS
# ==============================

def segment_story_fine_grained(story_text):
    """
    Fine-grained event segmentation built on clause-level segments.

    Each fine-grained event is one or more consecutive clause-level segments.
    Each discrete action, state change, dialogue line, or shift in
    topic/location/time/emotion constitutes a new event.

    Merge rules (clause segments → fine-grained events):
      - Clauses within the same sentence are merged into a single event.
      - Sentence boundaries always start a new event.
      - Temporal transitions (and then/eventually/later/suddenly/next/finally)
        within a long clause group (≥ 5 words so far) keep the clause split.
      - Contrast transitions (but) within a long clause group (≥ 8 words so
        far) keep the clause split.
      - Very short adjacent events (both ≤ 3 words) are merged together.
    """
    if not story_text or not isinstance(story_text, str) or len(story_text.strip()) == 0:
        return []

    clause_segments = segment_story_clause_level(story_text)
    if not clause_segments or len(clause_segments) <= 1:
        return clause_segments

    _sent_end_re = re.compile(r'[.!?]["\u201d\u2019\']*\s*$')
    _temporal_re = re.compile(
        r'^\s*,?\s*(?:and\s+)?(?:then|eventually|later|suddenly|next|finally)\s+',
        re.IGNORECASE,
    )
    _contrast_re = re.compile(r'^\s*,?\s*but\s+', re.IGNORECASE)

    def _flush_group(group):
        merged = group[0]
        for seg in group[1:]:
            merged = _join_segments(merged, seg)
        return merged

    events = []
    current_group = [clause_segments[0]]
    current_words = len(clause_segments[0].split())

    for i in range(1, len(clause_segments)):
        prev = clause_segments[i - 1]
        curr = clause_segments[i]

        is_sentence_boundary = bool(_sent_end_re.search(prev))
        has_temporal = bool(_temporal_re.match(curr))
        has_contrast = bool(_contrast_re.match(curr))

        start_new = False
        if is_sentence_boundary:
            start_new = True
        elif has_temporal and current_words >= 5:
            start_new = True
        elif has_contrast and current_words >= 8:
            start_new = True

        if start_new:
            events.append(_flush_group(current_group))
            current_group = [curr]
            current_words = len(curr.split())
        else:
            current_group.append(curr)
            current_words += len(curr.split())

    if current_group:
        events.append(_flush_group(current_group))

    final = []
    for event in events:
        if final and len(final[-1].split()) <= 3 and len(event.split()) <= 3:
            final[-1] = _join_segments(final[-1], event)
        else:
            final.append(event)

    final = [e for e in final if e and len(e.split()) > 0]
    return final if final else [story_text.strip()]


# ==============================
# HELPER: Semantic Features for Coarse Segmentation
# ==============================

_COARSE_STOP_WORDS = frozenset({
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'shall', 'should', 'may', 'might', 'can', 'could', 'must', 'it', 'its',
    'he', 'she', 'they', 'we', 'you', 'me', 'him', 'her', 'us', 'them',
    'my', 'his', 'her', 'their', 'our', 'your', 'this', 'that', 'these',
    'those', 'which', 'who', 'whom', 'what', 'where', 'when', 'why', 'how',
    'not', 'no', 'nor', 'so', 'if', 'then', 'than', 'too', 'very', 'just',
    'about', 'up', 'out', 'off', 'over', 'back', 'into', 'down', 'all',
    'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
    'only', 'own', 'same', 'as', 'said', 'also', 'still', 'even', 'again',
    'one', 'two', 'three', 'been', 'being', 'much', 'many', 'like', 'way',
})

_COARSE_NON_AGENT_WORDS = frozenset({
    'the', 'this', 'that', 'these', 'those', 'there', 'then', 'they',
    'later', 'eventually', 'meanwhile', 'finally', 'suddenly', 'inside',
    'outside', 'after', 'before', 'once', 'when', 'while', 'back',
    'hours', 'days', 'weeks', 'months', 'years', 'not', 'but', 'and',
    'however', 'although', 'because', 'since', 'until', 'upon', 'during',
    'sometimes', 'always', 'never', 'perhaps', 'maybe', 'certainly',
    'today', 'tomorrow', 'yesterday', 'morning', 'evening', 'night',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
    'sunday', 'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
})

_LOCATION_PREP_RE = re.compile(
    r'\b(?:at|in|inside|outside|near|behind|beside|above|across|'
    r'toward|towards|through)\s+'
    r'(?:the|a|an|his|her|their|its|my|our)\s+'
    r'(\w+(?:\s+\w+)?)',
    re.IGNORECASE
)

_NAMED_LOCATION_RE = re.compile(
    r"\b(?:at|in|to|near|from|inside|outside)\s+"
    r"([A-Z][a-z]+(?:'s)?(?:\s+[A-Z][a-z]+)*)",
)

_TIME_PASSAGE_RE_COARSE = re.compile(
    r'(?:^|\b)(?:'
    r'the\s+next\s+(?:day|morning|evening|night|week|month|year)|'
    r'that\s+(?:night|evening|morning|afternoon)|'
    r'the\s+following\s+(?:day|morning|evening|week)|'
    r'after\s+a\s+(?:while|moment|pause|few|long)|'
    r'hours?\s+later|days?\s+later|weeks?\s+later|months?\s+later|years?\s+later|'
    r'soon\s+after|some\s+time\s+(?:later|after)|'
    r'by\s+(?:the\s+time|then|now|morning|evening|nightfall|dawn|dusk)|'
    r'when\s+(?:morning|night|dawn|dusk)\s+(?:came|arrived|broke)|'
    r'before\s+long|not\s+long\s+after|a\s+(?:few|couple)\s+of\s+(?:hours|days|weeks)'
    r')\b',
    re.IGNORECASE
)

_COARSE_PROPER_NOUN_RE = re.compile(r'\b([A-Z][a-z]{2,})\b')
_COARSE_DIALOGUE_RE = re.compile(r'["\u201c\u201d\u2018\u2019]')

_STRONG_TRANSITIONS_COARSE = re.compile(
    r'^(?:Later|Eventually|Meanwhile|Finally|The\s+next\s+day|'
    r'The\s+following|After\s+a\s+while|Hours\s+later|Days\s+later|'
    r'Suddenly|In\s+the\s+end|At\s+last|When\s+they\s+arrived|'
    r'Back\s+at|Once\s+inside|Outside|Inside|At\s+the|'
    r'Sometime\s+later|Not\s+long\s+after|Before\s+long|'
    r'The\s+next\s+(?:morning|evening|night|week)|'
    r'That\s+(?:night|morning|evening|afternoon)|'
    r'When\s+morning\s+came|As\s+night\s+fell|By\s+the\s+time|'
    r'After\s+(?:that|this|the)|Upon\s+(?:arriving|reaching|entering)|'
    r'As\s+they\s+(?:left|arrived|entered|walked|drove|reached)|'
    r'Once\s+they\s+(?:arrived|reached|were)|'
    r'In\s+the\s+(?:morning|evening|afternoon|meantime)|'
    r'On\s+the\s+(?:way|road|drive|walk)|'
    r'By\s+(?:morning|evening|nightfall|dawn|dusk)|'
    r'Weeks?\s+later|Months?\s+later|Years?\s+later)\s+',
    re.IGNORECASE
)

_MODERATE_TRANSITIONS_COARSE = re.compile(
    r'^(?:Then|And\s+then|So|After|Before|While|During|'
    r'When|As\s+soon\s+as|Once|Now|Next)\s+',
    re.IGNORECASE
)


def _extract_coarse_features(text):
    """Extract semantic features from a text segment for coarse-grained boundary detection."""
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    content_words = frozenset(w for w in words if w not in _COARSE_STOP_WORDS)

    locs = set()
    for m in _LOCATION_PREP_RE.finditer(text):
        loc = m.group(1).lower().strip()
        if loc and len(loc) > 2:
            locs.add(loc)
    for m in _NAMED_LOCATION_RE.finditer(text):
        locs.add(m.group(1).lower())

    agents = set()
    for m in _COARSE_PROPER_NOUN_RE.finditer(text):
        name = m.group(1)
        if name.lower() not in _COARSE_NON_AGENT_WORDS:
            agents.add(name.lower())

    return {
        'content_words': content_words,
        'locations': frozenset(locs),
        'agents': frozenset(agents),
        'has_time_passage': bool(_TIME_PASSAGE_RE_COARSE.search(text)),
        'has_dialogue': bool(_COARSE_DIALOGUE_RE.search(text)),
    }


def _coarse_transition_score(group_features, next_features, next_text):
    """Score the semantic transition between a group and the next event.
    Higher score = more significant narrative boundary."""
    score = 0.0

    if _STRONG_TRANSITIONS_COARSE.match(next_text.lstrip()):
        score += 3.0
    elif _MODERATE_TRANSITIONS_COARSE.match(next_text.lstrip()):
        score += 1.0

    if next_features['locations'] and group_features['locations']:
        if not (next_features['locations'] & group_features['locations']):
            score += 3.0
    elif next_features['locations'] and not group_features['locations']:
        score += 1.5

    if next_features['agents'] and group_features['agents']:
        if not (next_features['agents'] & group_features['agents']):
            score += 2.0
        elif len(next_features['agents'] - group_features['agents']) > 0:
            score += 0.5

    if next_features['has_time_passage']:
        score += 2.0

    if group_features['content_words'] and next_features['content_words']:
        intersection = len(group_features['content_words'] & next_features['content_words'])
        union = len(group_features['content_words'] | next_features['content_words'])
        if union > 0:
            jaccard = intersection / union
            if jaccard < 0.05:
                score += 2.0
            elif jaccard < 0.12:
                score += 1.0

    if next_features['has_dialogue'] != group_features['has_dialogue']:
        score += 0.5

    return score


# ==============================
# METHOD 3: COARSE-GRAINED EVENTS
# ==============================

def segment_story_coarse_grained(story_text):
    """
    Coarse-grained event segmentation built on fine-grained events.

    Determines event boundaries based on significant semantic transitions
    across multiple narrative dimensions: scene/location changes, character
    shifts, temporal jumps, topic/goal changes, and discourse markers.

    Each coarse-grained event represents a coherent narrative scene or
    episode sharing consistent characters, location, time frame, and topic.
    Boundaries are placed where multiple semantic dimensions change
    simultaneously, indicating a genuine scene or episode transition.

    Transition scoring (fine-grained events → coarse-grained events):
      - Strong discourse transitions (Later, Meanwhile, ...): +3
      - Moderate discourse transitions (Then, After, ...): +1
      - Location/scene change: +3 (full change) or +1.5 (new location)
      - Agent/character change: +2 (full change) or +0.5 (new characters)
      - Temporal jump (time passage phrases): +2
      - Topic shift (low content-word overlap): +1 to +2
      - Dialogue/narration mode switch: +0.5
      Split when score ≥ 3 and group has ≥ 12 words.
      Strong split (score ≥ 6) overrides the minimum to just 5 words.
      Hard cap at 120 words.
    """
    if not story_text or not isinstance(story_text, str) or len(story_text.strip()) == 0:
        return []

    fine_events = segment_story_fine_grained(story_text)
    if not fine_events or len(fine_events) <= 1:
        return fine_events

    SPLIT_THRESHOLD = 3.0
    STRONG_SPLIT_THRESHOLD = 6.0
    MIN_GROUP_WORDS = 12
    MIN_GROUP_WORDS_STRONG = 5
    MAX_GROUP_WORDS = 120

    event_features = [_extract_coarse_features(ev) for ev in fine_events]

    def _merge_group_features(indices):
        agents = set()
        locations = set()
        content_words = set()
        has_dialogue = False
        for idx in indices:
            f = event_features[idx]
            agents |= f['agents']
            locations |= f['locations']
            content_words |= f['content_words']
            has_dialogue = has_dialogue or f['has_dialogue']
        return {
            'agents': frozenset(agents),
            'locations': frozenset(locations),
            'content_words': frozenset(content_words),
            'has_dialogue': has_dialogue,
        }

    groups = []
    current_indices = [0]
    current_words = len(fine_events[0].split())

    for i in range(1, len(fine_events)):
        group_features = _merge_group_features(current_indices)
        next_f = event_features[i]
        score = _coarse_transition_score(group_features, next_f, fine_events[i])

        start_new = False
        if score >= STRONG_SPLIT_THRESHOLD and current_words >= MIN_GROUP_WORDS_STRONG:
            start_new = True
        elif score >= SPLIT_THRESHOLD and current_words >= MIN_GROUP_WORDS:
            start_new = True
        elif current_words > MAX_GROUP_WORDS:
            start_new = True

        if start_new:
            groups.append(current_indices)
            current_indices = [i]
            current_words = len(fine_events[i].split())
        else:
            current_indices.append(i)
            current_words += len(fine_events[i].split())

    if current_indices:
        groups.append(current_indices)

    events = []
    for group in groups:
        merged = fine_events[group[0]]
        for idx in group[1:]:
            merged = _join_segments(merged, fine_events[idx])
        events.append(merged)

    final = [e for e in events if e and len(e.split()) > 0]
    return final if final else [story_text.strip()]


# ==============================
# METHOD 4: API-BASED
# ==============================


def segment_story_api(story_text, model=None, prompt_version=None, api_key_override=None):
    """
    Segment a story using an LLM API call.

    Args:
        story_text: Full story text.
        model: Model identifier (key in SUPPORTED_MODELS). Defaults to DEFAULT_MODEL.
        prompt_version: Prompt filename from scripts/prompt/, or None for default.
        api_key_override: Override API key (from web UI).
    
    Returns:
        List of event strings.
    """
    if not story_text or not isinstance(story_text, str) or len(story_text.strip()) == 0:
        return []

    model = model or DEFAULT_MODEL
    client, provider = get_api_client(model, api_key_override)

    prompt_template = load_event_segmentation_prompt(prompt_version)
    user_message = f"{prompt_template}\n\n{story_text}"

    try:
        if provider == 'ollama':
            from helpers.ollama_gemma_e4b import ollama_chat

            meta = SUPPORTED_MODELS.get(model) or {}
            otag = (
                os.environ.get("EVENT_SEGMENT_OLLAMA_MODEL")
                or meta.get("ollama_tag")
                or "gemma4:e4b"
            ).strip()
            try:
                num_ctx = int(os.environ.get('EVENT_SEGMENT_OLLAMA_NUM_CTX', '32768'))
            except ValueError:
                num_ctx = 32768
            output_text = ollama_chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                model_tag=otag,
                temperature=TEMPERATURE,
                num_ctx=num_ctx,
                num_predict=MAX_TOKENS,
                think=False,
            ).strip()
        elif provider == 'openai':
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            output_text = response.choices[0].message.content.strip()
        else:
            response = client.messages.create(
                model=model,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            output_text = response.content[0].text.strip()

        if output_text.startswith("```"):
            output_text = output_text.split("```")[1]
        if output_text.startswith("text") or output_text.startswith("plaintext"):
            output_text = output_text[4:].strip() if output_text.startswith("text") else output_text[9:].strip()

        events = [line.strip() for line in output_text.split('\n') if line.strip()]

        if not events:
            print("  Warning: API returned no events, using original text as single event")
            return [story_text.strip()]

        return events

    except Exception as e:
        raise RuntimeError(
            f"LLM call failed ({provider}, model={model}): {e}"
        ) from e


# ==============================
# PROCESSING PIPELINE
# ==============================

VALID_METHODS = ['clause', 'fine', 'coarse', 'api']


def process_story_transcript(transcript_path, story_name, output_dir='data/3_story_events',
                             method='fine', model=None, prompt_version=None, api_key_override=None):
    """
    Process a single story transcript file and create event segmentation.
    
    Args:
        transcript_path: Path to the story transcript file (.txt)
        story_name: Story name (e.g., 'my_story')
        output_dir: Directory to save event files
        method: 'clause', 'fine' (default), 'coarse', or 'api'
        model: Model identifier for API method
        prompt_version: Prompt filename for API method
        api_key_override: Override API key for API method
        
    Returns:
        True if successful, False otherwise
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            story_text = f.read().strip()
    except Exception as e:
        print(f"  Error reading transcript file: {e}")
        return False

    if not story_text:
        print("  Warning: Transcript file is empty")
        return False

    print(f"  Processing story transcript ({len(story_text)} chars, {len(story_text.split())} words)...")
    print(f"  Using method: {method}")

    if method == 'api':
        model = model or os.environ.get('EVENT_SEGMENT_MODEL', DEFAULT_MODEL)
        prompt_version = prompt_version or os.environ.get('EVENT_SEGMENT_PROMPT_VERSION', None)
        api_key_override = api_key_override or os.environ.get('EVENT_SEGMENT_API_KEY', None)
        print(f"  Model: {model}")
        if prompt_version:
            print(f"  Prompt version: {prompt_version}")

        try:
            events = segment_story_api(story_text, model=model,
                                       prompt_version=prompt_version,
                                       api_key_override=api_key_override)
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error: LLM API call failed: {e}")
            return False
    elif method == 'clause':
        events = segment_story_clause_level(story_text)
    elif method == 'coarse':
        events = segment_story_coarse_grained(story_text)
    else:
        events = segment_story_fine_grained(story_text)

    if not events:
        print("  Warning: No events extracted from transcript")
        return False

    print(f"  Segmented into {len(events)} events")

    df = pd.DataFrame({
        'event': range(1, len(events) + 1),
        'story_texts': events
    })

    method_suffix = method.replace('-', '_')
    if method == 'api':
        model_used = model or DEFAULT_MODEL
        method_suffix = f"api_model-{_slug_for_events_api_model(model_used)}"
    output_file = output_path / f"{story_name}_events-{method_suffix}.xlsx"

    if method == 'api' and output_file.exists():
        trial_num = 2
        while True:
            trial_file = output_path / f"{story_name}_events-{method_suffix}_trial{trial_num}.xlsx"
            if not trial_file.exists():
                output_file = trial_file
                break
            trial_num += 1

    try:
        df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
        print(f"  Saved to {output_file}")
        return True
    except Exception as e:
        print(f"  Error saving event file: {e}")
        return False


def process_all_story_transcripts(input_dir=None, output_dir=None, method='fine',
                                  model=None, prompt_version=None, api_key_override=None):
    """
    Process all story transcript files and create event segmentations.
    """
    input_dir = os.environ.get('BATCH_INPUT_DIR', input_dir or 'data/2_story_transcript')
    output_dir = os.environ.get('BATCH_OUTPUT_DIR', output_dir or 'data/3_story_events')

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        msg = f"Input directory not found: {input_dir}"
        print(f"Error: {msg}")
        print(f"  Please place story transcript files (.txt) in {input_dir}")
        raise RuntimeError(msg)

    transcript_files = sorted(input_path.glob('*.txt'))

    batch_item_id = os.environ.get('BATCH_ITEM_ID', None)
    if batch_item_id:
        filtered_files = []
        for tf in transcript_files:
            fn = tf.stem
            sn = fn.replace('_story', '').replace('_transcript', '')
            if batch_item_id in fn or sn == batch_item_id or fn.startswith(batch_item_id):
                filtered_files.append(tf)
        transcript_files = filtered_files
        if transcript_files:
            print(f"Filtering by BATCH_ITEM_ID: {batch_item_id}")
        else:
            print(f"No transcript files found matching BATCH_ITEM_ID: {batch_item_id}")

    explicit_variant = os.environ.get('BATCH_INPUT_VARIANT')
    if explicit_variant is not None and batch_item_id:
        before = len(transcript_files)
        target_stem = f"{batch_item_id}{explicit_variant}"
        transcript_files = [tf for tf in transcript_files if tf.stem == target_stem]
        print(
            f"Filtering by BATCH_INPUT_VARIANT={explicit_variant!r}: "
            f"{before} -> {len(transcript_files)} file(s)"
        )

    if not transcript_files:
        msg = (
            f"No .txt files found in {input_dir}"
            + (f" matching BATCH_ITEM_ID={batch_item_id}" if batch_item_id else "")
        )
        print(msg)
        print(f"  Please place story transcript files (.txt) in {input_dir}")
        raise RuntimeError(msg)

    print(f"Found {len(transcript_files)} story transcript file(s) to process")
    print(f"Output directory: {output_path.absolute()}\n")

    processed_count = 0
    failed_count = 0

    for transcript_file in transcript_files:
        filename = transcript_file.stem
        story_name = filename.replace('_story', '').replace('_transcript', '')

        print(f"Processing {transcript_file.name} (story: {story_name})...")

        success = process_story_transcript(
            transcript_file, story_name, output_dir,
            method=method, model=model, prompt_version=prompt_version,
            api_key_override=api_key_override
        )

        if success:
            processed_count += 1
        else:
            failed_count += 1

        print()

    print("Processing complete!")
    print(f"  Successfully processed: {processed_count} file(s)")
    print(f"  Failed: {failed_count} file(s)")
    print(f"  Output directory: {output_path.absolute()}")

    if failed_count > 0:
        raise RuntimeError(f"{failed_count} file(s) failed to process")


def reconstruct_story_from_events(events_file, output_transcript_path=None):
    """
    Helper function: Reconstruct full story text from existing events file.
    Useful when transcript is missing but events file exists.
    """
    try:
        df = pd.read_excel(events_file)
        if 'story_texts' not in df.columns:
            print("Error: Events file missing 'story_texts' column")
            return None

        full_story = ' '.join(df['story_texts'].astype(str).tolist())

        if output_transcript_path:
            with open(output_transcript_path, 'w', encoding='utf-8') as f:
                f.write(full_story)
            print(f"Reconstructed transcript saved to {output_transcript_path}")

        return full_story
    except Exception as e:
        print(f"Error reconstructing story: {e}")
        return None


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='Segment story transcripts into discrete events',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Methods:
  clause   Clause-level (finest granularity, like recall parsing)
  fine     Fine-grained event level (default — each action/state change)
  coarse   Coarse-grained event level (scene-level, major shifts only)
  api      LLM API call (configurable model & prompt)

Examples:
  python scripts/2_story-event-segment.py --method fine
  python scripts/2_story-event-segment.py --method api --model gemma4-e4b-ollama --input data/2_story_transcript/the_siren.txt
  python scripts/2_story-event-segment.py --method api --model llama5.3-ollama --input data/2_story_transcript/the_siren.txt
  # Preset default for llama3.3-ollama is Ollama tag llama3.3 (~43GB 70B). On limited RAM, pull a smaller quant and set:
  #   EVENT_SEGMENT_OLLAMA_MODEL=llama3.3:70b-instruct-q3_K_M python ... --model llama3.3-ollama ...
  # If tag llama5.3 is not in your Ollama library yet, override the image, e.g.:
  #   EVENT_SEGMENT_OLLAMA_MODEL=llama3.3 python scripts/2_story-event-segment.py --method api --model llama5.3-ollama ...
  python scripts/2_story-event-segment.py --input data/2_story_transcript/my_story.txt --method coarse
  python scripts/2_story-event-segment.py --reconstruct data/3_story_events/my_story_events.xlsx
  python scripts/2_story-event-segment.py --list-prompts
  python scripts/2_story-event-segment.py --list-models
        """
    )

    parser.add_argument('--method', choices=VALID_METHODS, default='fine',
                        help='Segmentation method (default: fine)')
    parser.add_argument('--model', type=str, default=None,
                        help=f'Model for API method (default: {DEFAULT_MODEL})')
    parser.add_argument('--prompt-version', type=str, default=None,
                        help='Prompt filename from scripts/prompt/ (e.g. event_segment_v2.txt)')
    parser.add_argument('--input', type=str, help='Input transcript file path (single file)')
    parser.add_argument('--output', type=str, help='Output directory for event files')
    parser.add_argument('--reconstruct', type=str, metavar='EVENTS_FILE',
                        help='Reconstruct story from events file')
    parser.add_argument('--output-transcript', type=str, metavar='OUTPUT_FILE',
                        help='Output file for reconstructed transcript (use with --reconstruct)')
    parser.add_argument('--list-prompts', action='store_true',
                        help='List available event segmentation prompts')
    parser.add_argument('--list-models', action='store_true',
                        help='List supported models')

    args = parser.parse_args()

    if args.list_prompts:
        prompts = list_event_segment_prompts()
        print("Available event segmentation prompts:")
        for p in prompts:
            print(f"  {p}")
        if not prompts:
            print("  (none found — place event_segment*.txt files in scripts/prompt/)")
        sys.exit(0)

    if args.list_models:
        print("Supported models:")
        for mid, info in SUPPORTED_MODELS.items():
            print(f"  {mid}  ({info['provider']}, {info['label']})")
        sys.exit(0)

    if args.method == 'api':
        model = args.model or DEFAULT_MODEL
        info = SUPPORTED_MODELS.get(model, {'provider': 'anthropic'})
        provider = info['provider']
        if provider == 'openai':
            key_env = 'OPENAI_API_KEY'
        elif provider == 'anthropic':
            key_env = 'ANTHROPIC_API_KEY'
        else:
            key_env = None
        if key_env and not os.getenv(key_env):
            print("=" * 70)
            print(f"NOTE: API method requested but {key_env} not set")
            print(f"The script will fall back to fine-grained if API key is unavailable")
            print(f"Set it with: export {key_env}='your-key'")
            print("=" * 70)
            print()

    if args.reconstruct:
        reconstruct_story_from_events(args.reconstruct, args.output_transcript)
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}")
            sys.exit(1)

        story_name = os.environ.get('BATCH_ITEM_ID', None)
        if not story_name:
            story_name = input_path.stem.replace('_story', '').replace('_transcript', '')
        output_dir = args.output or 'data/3_story_events'

        print(f"Processing {input_path.name} (story: {story_name})...")
        success = process_story_transcript(
            input_path, story_name, output_dir,
            method=args.method, model=args.model, prompt_version=args.prompt_version
        )

        if not success:
            sys.exit(1)
    else:
        try:
            input_dir = os.environ.get('BATCH_INPUT_DIR', None)
            output_dir = os.environ.get('BATCH_OUTPUT_DIR', args.output)
            process_all_story_transcripts(
                input_dir=input_dir, output_dir=output_dir,
                method=args.method, model=args.model, prompt_version=args.prompt_version
            )
        except Exception as e:
            print(f"Error processing story transcripts: {e}")
            import traceback
            traceback.print_exc()
            exit(1)

