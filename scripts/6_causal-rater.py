#!/usr/bin/env python3
"""
Script to rate causal relationships between pairs of story events.

Reads event-segmented story files from data/3_story_events/ and rates the
causal relationship (1-10) for every possible event pair. Only pairs with a
rating greater than 4 are retained in the output.

Methods:
  1. linguistic (default) — Rule-based scoring using causal connectives,
     entity continuity, verb-argument overlap, and consequence markers.
     No API key required. Uses spaCy if available, otherwise regex heuristics.
  2. api — LLM-based rating using configurable model and prompt. Requires
     ANTHROPIC_API_KEY or OPENAI_API_KEY.
  3. manual — Empty scaffold for manual causal rating entry via the web
     interface's N×N event matrix.

Inspired by causal relation extraction approaches (CREST schema, CausalLearn,
and narrative causal reasoning literature):
- Events are treated as discrete narrative units whose causal connections may
  span non-adjacent positions in the story (distal causation).
- Ratings use a 1-10 integer scale; the threshold (default >4) filters for
  meaningfully causal pairs.

Output: output/causal_rated/{story_name}_causal.xlsx
Columns: event_A_number, event_B_number, rating, reasoning
"""

import os
import sys
from pathlib import Path


def _software_package_root() -> Path:
    d = Path(__file__).resolve().parent
    return d.parent if d.name == "scripts" else d


_pr = _software_package_root()
if str(_pr) not in sys.path:
    sys.path.insert(0, str(_pr))


import re
import pandas as pd
import json
import time
from typing import List, Dict, Optional
from itertools import combinations

from helpers.anthropic_ids import ANTHROPIC_SUPPORTED_MODELS, DEFAULT_ANTHROPIC_CAUSAL_MODEL


# ==============================
# SETTINGS
# ==============================

DEFAULT_MODEL = DEFAULT_ANTHROPIC_CAUSAL_MODEL
MAX_TOKENS = 8000
TEMPERATURE = 0
RATING_THRESHOLD = 4

VALID_METHODS = ['linguistic', 'api', 'manual']

SUPPORTED_MODELS = {
    **ANTHROPIC_SUPPORTED_MODELS,
    'gpt-4o': {'provider': 'openai', 'label': 'GPT-4o'},
    'gpt-4o-mini': {'provider': 'openai', 'label': 'GPT-4o Mini'},
}

SYSTEM_PROMPT = """You are an expert annotator of causal relationships in narratives.
You evaluate whether one event directly causes or enables another event.
You distinguish genuine cause-and-effect from thematic similarity, temporal adjacency, and co-occurrence.
You consider both proximal causation (adjacent events) and distal causation (non-adjacent events) with equal rigor."""


# ==============================
# PROMPT LOADING (for API method)
# ==============================

DEFAULT_USER_PROMPT = (
    "Your task is to read a story and return a list of event pairs that had a "
    "strong causal relationship. You will receive a story segmented into events, "
    "each labeled by an event number. Follow the below procedure to complete the task:\n"
    "1) For each event-A, go through the rest of the events, forming event pairs.\n"
    "2) For each event pair, rate on a scale of 1-10 how much content in the two "
    "events is directly causing each other. Use integers only for your rating. "
    "Note that the rating should only reflect a cause-and-effect relationship, not "
    "thematic similarity. Do not prioritize immediate or adjacent event pairs over "
    "non-consecutive ones. Instead, judge every event pair's causal relationship "
    "using the same criteria.\n"
    "3) Return only the event pairs with a causal rating greater than four, with "
    "the returned event pairs added as a new row to a table under the columns "
    "'event_A_number' and 'event_B_number', respectively.\n"
    "4) Provide your rating and reasoning for the rating in another two separate "
    "columns. Return all responses in one table with 4 columns: event_A_number, "
    "event_B_number, rating, reasoning.\n\n"
    "Output format (STRICT):\n"
    "- Output ONLY a valid JSON array.\n"
    "- Each element MUST be an object with EXACTLY these keys:\n"
    '  - "event_A_number" (integer)\n'
    '  - "event_B_number" (integer)\n'
    '  - "rating" (integer, 5-10)\n'
    '  - "reasoning" (string, 1-2 sentences)\n'
    "- Do NOT include any text outside the JSON array.\n"
    "- Do NOT include pairs with rating 4 or below.\n"
)


def get_prompt_dir():
    return Path(__file__).resolve().parent / "prompt"


def list_causal_rating_prompts():
    """Return list of available causal rating prompt filenames."""
    prompt_dir = get_prompt_dir()
    if not prompt_dir.exists():
        return []
    return sorted(f.name for f in prompt_dir.glob("causal_rating*.txt"))


def load_causal_rating_prompt(prompt_version="causal_rating"):
    """Load the causal rating prompt from the scripts/prompt/ folder."""
    env_prompt = os.getenv('CAUSAL_RATING_PROMPT')
    if env_prompt:
        prompt_version = env_prompt

    prompt_dir = get_prompt_dir()
    prompt_file = prompt_dir / f"{prompt_version}.txt"

    if prompt_file.exists():
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                prompt_text = f.read().strip()
                print(f"Loaded prompt from: {prompt_file}")
                if "JSON" not in prompt_text and "json" not in prompt_text:
                    prompt_text += (
                        "\n\nOutput format (STRICT):\n"
                        "- Output ONLY a valid JSON array.\n"
                        "- Each element MUST be an object with EXACTLY these keys:\n"
                        '  - "event_A_number" (integer)\n'
                        '  - "event_B_number" (integer)\n'
                        '  - "rating" (integer, 5-10)\n'
                        '  - "reasoning" (string, 1-2 sentences)\n'
                        "- Do NOT include any text outside the JSON array.\n"
                        "- Do NOT include pairs with rating 4 or below.\n"
                    )
                return prompt_text
        except Exception as e:
            print(f"Warning: Could not read {prompt_file}: {e}")

    print(f"Warning: Prompt file '{prompt_version}.txt' not found. Using default prompt.")
    return DEFAULT_USER_PROMPT


# ==============================
# API CLIENT (for API method)
# ==============================

def get_api_client(model=None, api_key_override=None):
    """Initialize and return an API client for the given model."""
    model = model or DEFAULT_MODEL
    info = SUPPORTED_MODELS.get(model, {'provider': 'anthropic'})
    provider = info['provider']

    if provider == 'openai':
        import openai
        api_key = api_key_override or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Please set it with: export OPENAI_API_KEY='your-api-key'"
            )
        return openai.OpenAI(api_key=api_key), provider
    else:
        import anthropic
        api_key = api_key_override or os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
            )
        return anthropic.Anthropic(api_key=api_key), provider


# ==============================
# NLP HELPERS (shared by linguistic method)
# ==============================

_NLP_CACHE = {'nlp': None, 'loaded': False}


def _try_load_spacy():
    """Lazily load spaCy for NER and dependency parsing. Cached per process."""
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
        _NLP_CACHE['nlp'] = nlp
        return nlp
    except ImportError:
        return None


# Causal connective lexicon — drawn from causal relation extraction literature
# (Girju 2003, Khoo et al. 2000, CREST/BECauSE annotations)
CAUSAL_CONNECTIVES = {
    'explicit_forward': [
        r'\bcause[ds]?\b', r'\bcausing\b', r'\bled\s+to\b', r'\blead[s]?\s+to\b',
        r'\bresult(?:s|ed|ing)?\s+in\b', r'\bmade\b', r'\bmake[s]?\b',
        r'\bforce[ds]?\b', r'\bforcing\b', r'\bcompel(?:s|led)?\b',
        r'\btrigger(?:s|ed)?\b', r'\bproduce[ds]?\b', r'\bproducing\b',
        r'\bbring[s]?\s+about\b', r'\bbrought\s+about\b',
        r'\bgive[s]?\s+rise\s+to\b', r'\bgave\s+rise\s+to\b',
        r'\bset\s+off\b', r'\bspark(?:s|ed)?\b',
    ],
    'explicit_backward': [
        r'\bbecause\b', r'\bsince\b', r'\bdue\s+to\b', r'\bowing\s+to\b',
        r'\bthanks\s+to\b', r'\bas\s+a\s+result\s+of\b',
        r'\bon\s+account\s+of\b',
    ],
    'conjunctive': [
        r'\btherefore\b', r'\bthus\b', r'\bhence\b', r'\bconsequently\b',
        r'\baccordingly\b', r'\bas\s+a\s+result\b', r'\bso\b',
    ],
    'enabling': [
        r'\benable[ds]?\b', r'\benabling\b', r'\ballow(?:s|ed)?\b',
        r'\ballowing\b', r'\bpermit(?:s|ted)?\b', r'\blet\b',
        r'\bhelp(?:s|ed)?\b', r'\bhelping\b',
    ],
    'preventive': [
        r'\bprevent(?:s|ed)?\b', r'\bpreventing\b', r'\bblock(?:s|ed)?\b',
        r'\bstop(?:s|ped)?\b', r'\bhinder(?:s|ed)?\b', r'\binhibit(?:s|ed)?\b',
    ],
    'consequence_markers': [
        r'\bin\s+response\b', r'\bas\s+a\s+consequence\b',
        r'\bthis\s+meant\b', r'\bwhich\s+meant\b',
        r'\bleaving\b', r'\bmaking\b',
    ],
}

# Compile all patterns once
_COMPILED_CONNECTIVES = {}
for category, patterns in CAUSAL_CONNECTIVES.items():
    _COMPILED_CONNECTIVES[category] = [
        re.compile(p, re.IGNORECASE) for p in patterns
    ]

# Result-state verbs — verbs that describe outcomes/consequences
_RESULT_VERBS = frozenset({
    'died', 'survived', 'escaped', 'fell', 'broke', 'collapsed', 'disappeared',
    'appeared', 'arrived', 'left', 'returned', 'woke', 'awoke', 'fainted',
    'recovered', 'healed', 'saved', 'rescued', 'freed', 'trapped', 'caught',
    'lost', 'found', 'discovered', 'learned', 'realized', 'understood',
    'changed', 'transformed', 'became', 'turned', 'grew',
    'succeeded', 'failed', 'won', 'defeated', 'destroyed', 'created',
    'born', 'killed', 'injured', 'hurt', 'cured', 'poisoned',
})

# Action verbs that typically initiate causal chains
_ACTION_VERBS = frozenset({
    'gave', 'took', 'sent', 'brought', 'carried', 'threw', 'dropped',
    'pushed', 'pulled', 'hit', 'struck', 'grabbed', 'seized',
    'told', 'said', 'asked', 'ordered', 'commanded', 'warned', 'promised',
    'decided', 'chose', 'agreed', 'refused', 'accepted',
    'opened', 'closed', 'locked', 'unlocked', 'broke', 'built', 'created',
    'drank', 'ate', 'swallowed', 'touched', 'used', 'wore',
    'ran', 'walked', 'went', 'came', 'moved', 'fled', 'followed',
    'fought', 'attacked', 'defended', 'protected',
    'hid', 'revealed', 'showed', 'presented',
})

# Common stop words to exclude from content word overlap
_STOP_WORDS = frozenset({
    'the', 'a', 'an', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to',
    'from', 'by', 'in', 'of', 'with', 'is', 'are', 'was', 'were', 'be',
    'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'shall', 'should', 'may', 'might', 'must', 'can', 'could',
    'not', 'no', 'so', 'if', 'then', 'than', 'that', 'this', 'these',
    'those', 'it', 'its', 'he', 'she', 'they', 'we', 'i', 'you', 'me',
    'him', 'her', 'us', 'them', 'my', 'his', 'your', 'our', 'their',
    'what', 'which', 'who', 'whom', 'when', 'where', 'how', 'why',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'some', 'any',
    'as', 'up', 'out', 'into', 'over', 'after', 'before', 'about',
    'very', 'just', 'also', 'still', 'even', 'back', 'here', 'there',
})


def _extract_content_words(text: str) -> set:
    """Extract content words (4+ chars, excluding stop words)."""
    words = set(re.findall(r'\b[a-z]{4,}\b', text.lower()))
    return words - _STOP_WORDS


def _extract_entities_regex(text: str) -> set:
    """Extract likely entity names using regex (capitalized multi-word or single proper nouns)."""
    entities = set()
    for m in re.finditer(r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b', text):
        entities.add(m.group(1).lower())
    return entities


def _extract_entities_spacy(doc) -> set:
    """Extract named entities from a spaCy doc."""
    entities = set()
    for ent in doc.ents:
        entities.add(ent.text.lower())
    for token in doc:
        if token.pos_ == 'PROPN' and len(token.text) > 2:
            entities.add(token.text.lower())
    return entities


def _extract_verbs_regex(text: str) -> set:
    """Extract verb-like words using regex."""
    words = re.findall(r'\b[a-z]+(?:ed|ing|s)?\b', text.lower())
    verbs = set()
    for w in words:
        base = re.sub(r'(ed|ing|s)$', '', w)
        if w in _ACTION_VERBS or w in _RESULT_VERBS:
            verbs.add(w)
        elif base in _ACTION_VERBS or base in _RESULT_VERBS:
            verbs.add(w)
    return verbs


def _extract_verbs_spacy(doc) -> set:
    """Extract verbs from a spaCy doc."""
    return {token.lemma_.lower() for token in doc if token.pos_ == 'VERB'}


def _count_connective_matches(text: str) -> Dict[str, int]:
    """Count causal connective matches by category in the text."""
    counts = {}
    for category, compiled_patterns in _COMPILED_CONNECTIVES.items():
        count = 0
        for pattern in compiled_patterns:
            count += len(pattern.findall(text))
        if count > 0:
            counts[category] = count
    return counts


# ==============================
# METHOD 1: LINGUISTIC (default)
# ==============================

def rate_causal_pairs_linguistic(story_events: List[Dict]) -> List[Dict]:
    """
    Rate causal relationships using linguistic features.

    Scoring dimensions (each contributes to a 1-10 scale):
      1. Causal connectives: Explicit markers in either event referencing the other
      2. Entity continuity: Shared characters/entities across events
      3. Action-consequence pattern: Action verb in A, result verb in B
      4. Content word overlap: Shared meaningful vocabulary (low weight to avoid
         thematic-similarity bias)
      5. Causal argument structure: spaCy dependency patterns (if available)

    Proximal and distal pairs are scored with identical criteria — no adjacency bonus.
    """
    if not story_events or len(story_events) < 2:
        return []

    nlp = _try_load_spacy()
    if nlp:
        print("    Using spaCy NLP for enhanced causal analysis")
    else:
        print("    Using regex heuristics (install spaCy for better accuracy)")

    # Pre-process all events
    event_data = {}
    for event in story_events:
        eid = event['event']
        text = event['story_texts']

        if nlp:
            doc = nlp(text)
            entities = _extract_entities_spacy(doc)
            verbs = _extract_verbs_spacy(doc)
            # Also get subject-verb-object triples
            svos = []
            for token in doc:
                if token.dep_ == 'ROOT' and token.pos_ == 'VERB':
                    subjs = [c.text.lower() for c in token.children if c.dep_ in ('nsubj', 'nsubjpass')]
                    objs = [c.text.lower() for c in token.children if c.dep_ in ('dobj', 'pobj', 'attr')]
                    svos.append({'verb': token.lemma_.lower(), 'subjects': subjs, 'objects': objs})
        else:
            entities = _extract_entities_regex(text)
            verbs = _extract_verbs_regex(text)
            svos = []

        content_words = _extract_content_words(text)
        connective_counts = _count_connective_matches(text)

        # Identify action vs result verbs present
        action_verbs = verbs & _ACTION_VERBS if not nlp else {v for v in verbs if v in _ACTION_VERBS or v + 'ed' in _ACTION_VERBS or v + 'd' in _ACTION_VERBS}
        result_verbs = verbs & _RESULT_VERBS if not nlp else {v for v in verbs if v in _RESULT_VERBS or v + 'ed' in _RESULT_VERBS or v + 'd' in _RESULT_VERBS}

        event_data[eid] = {
            'text': text,
            'entities': entities,
            'verbs': verbs,
            'action_verbs': action_verbs,
            'result_verbs': result_verbs,
            'content_words': content_words,
            'connectives': connective_counts,
            'svos': svos,
        }

    # Score all pairs
    all_pairs = []
    event_ids = [e['event'] for e in story_events]

    for i, eid_a in enumerate(event_ids):
        for eid_b in event_ids[i + 1:]:
            data_a = event_data[eid_a]
            data_b = event_data[eid_b]

            score = 0.0
            reasons = []

            # --- 1. Causal connectives (0-3 points) ---
            # Check if either event contains explicit causal language
            conn_a = data_a['connectives']
            conn_b = data_b['connectives']

            # Forward causation markers in A suggest A causes something
            if 'explicit_forward' in conn_a or 'explicit_forward' in conn_b:
                score += 2.0
                reasons.append("explicit causal marker")
            if 'explicit_backward' in conn_b:
                score += 1.5
                reasons.append("backward causal reference")
            if 'conjunctive' in conn_b:
                score += 1.0
                reasons.append("conjunctive consequence marker")
            if 'enabling' in conn_a or 'enabling' in conn_b:
                score += 1.5
                reasons.append("enabling relationship")
            if 'preventive' in conn_a or 'preventive' in conn_b:
                score += 1.5
                reasons.append("preventive causal relationship")
            if 'consequence_markers' in conn_b:
                score += 1.0
                reasons.append("consequence marker")

            connective_score = min(score, 3.0)
            score = connective_score

            # --- 2. Entity continuity (0-2.5 points) ---
            shared_entities = data_a['entities'] & data_b['entities']
            if shared_entities:
                entity_score = min(len(shared_entities) * 1.0, 2.5)
                score += entity_score
                reasons.append(f"shared entities: {', '.join(sorted(shared_entities)[:3])}")

            # --- 3. Action-consequence pattern (0-2.5 points) ---
            # A has action verbs and B has result/state-change verbs
            if data_a['action_verbs'] and data_b['result_verbs']:
                score += 2.0
                reasons.append("action-consequence verb pattern")
            elif data_a['result_verbs'] and data_b['action_verbs']:
                # Reverse: B acts in response to A's outcome
                score += 1.5
                reasons.append("outcome-response verb pattern")
            elif data_a['action_verbs'] and data_b['action_verbs']:
                # Both are actions — weaker signal but possible chain
                if shared_entities:
                    score += 1.0
                    reasons.append("action chain with shared entity")

            # SVO-based argument overlap (spaCy only)
            if data_a['svos'] and data_b['svos']:
                for svo_a in data_a['svos']:
                    for svo_b in data_b['svos']:
                        # Object of A appears as subject of B (causal chain)
                        obj_to_subj = set(svo_a['objects']) & set(svo_b['subjects'])
                        if obj_to_subj:
                            score += 1.5
                            reasons.append(f"object-to-subject chain: {', '.join(obj_to_subj)}")
                            break
                    else:
                        continue
                    break

            # --- 4. Content word overlap (0-1.5 points, low weight) ---
            # Overlap signals relatedness but NOT causation on its own
            shared_content = data_a['content_words'] & data_b['content_words']
            if shared_content:
                n_shared = len(shared_content)
                max_possible = min(len(data_a['content_words']), len(data_b['content_words']))
                if max_possible > 0:
                    overlap_ratio = n_shared / max_possible
                    content_score = min(overlap_ratio * 2.0, 1.5)
                    if content_score >= 0.3:
                        score += content_score
                        reasons.append(f"{n_shared} shared content words")

            # --- 5. Pronoun/anaphora continuity bonus (0-0.5 points) ---
            text_b_lower = data_b['text'].lower()
            if re.match(r'^\s*(he|she|they|it|this|that)\s+', text_b_lower):
                if shared_entities:
                    score += 0.5
                    reasons.append("anaphoric reference to shared entity")

            # Convert to 1-10 scale (max raw score ~10)
            rating = max(1, min(10, round(score)))

            if rating > RATING_THRESHOLD:
                reasoning = "; ".join(reasons) if reasons else "weak causal signal"
                all_pairs.append({
                    'event_A_number': eid_a,
                    'event_B_number': eid_b,
                    'rating': rating,
                    'reasoning': reasoning,
                })

    # Sort by rating (descending), then by event_A, event_B
    all_pairs.sort(key=lambda p: (-p['rating'], p['event_A_number'], p['event_B_number']))

    return all_pairs


# ==============================
# METHOD 2: API-BASED
# ==============================

def _build_events_text(story_events: List[Dict]) -> str:
    """Format story events into numbered text for the LLM prompt."""
    lines = []
    for event in story_events:
        lines.append(f"Event {event['event']}: {event['story_texts']}")
    return "\n".join(lines)


def _parse_causal_response(response_text: str, valid_event_numbers: set) -> List[Dict]:
    """Parse the LLM JSON response into a list of causal pair dicts."""
    text = response_text.strip()

    if text.startswith("```"):
        text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:].strip()

    pairs = json.loads(text)

    validated = []
    for pair in pairs:
        event_a = pair.get("event_A_number") or pair.get("event_A") or pair.get("event_a_number") or pair.get("event_a")
        event_b = pair.get("event_B_number") or pair.get("event_B") or pair.get("event_b_number") or pair.get("event_b")
        rating = pair.get("rating") or pair.get("rate")
        reasoning = pair.get("reasoning") or pair.get("reason") or ""

        if event_a is None or event_b is None or rating is None:
            continue

        event_a = int(event_a)
        event_b = int(event_b)
        rating = int(rating)

        if event_a not in valid_event_numbers or event_b not in valid_event_numbers:
            continue
        if rating <= RATING_THRESHOLD:
            continue

        validated.append({
            "event_A_number": event_a,
            "event_B_number": event_b,
            "rating": rating,
            "reasoning": str(reasoning).strip().strip('"'),
        })

    return validated


def rate_causal_pairs_api(
    story_events: List[Dict],
    model: str = DEFAULT_MODEL,
    prompt_version: str = "causal_rating",
    api_key_override: str = None,
    max_events_per_chunk: int = 60,
) -> List[Dict]:
    """
    Rate causal relationships between all event pairs using an LLM.

    For stories with many events, the event list is sent in chunks to stay
    within token limits, and results are merged.
    """
    if not story_events:
        return []

    client, provider = get_api_client(model, api_key_override)
    prompt = load_causal_rating_prompt(prompt_version)
    valid_event_numbers = {e['event'] for e in story_events}

    n_events = len(story_events)
    all_pairs = []

    if n_events <= max_events_per_chunk:
        chunks = [story_events]
    else:
        chunks = []
        for i in range(0, n_events, max_events_per_chunk):
            chunks.append(story_events[i:i + max_events_per_chunk])

    for chunk_idx, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    Processing chunk {chunk_idx + 1}/{len(chunks)} "
                  f"(events {chunk[0]['event']}-{chunk[-1]['event']})...")

        events_text = _build_events_text(chunk if len(chunks) == 1 else story_events)
        user_content = f"{prompt}\n\nStory Events:\n{events_text}"

        try:
            if provider == 'openai':
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                )
                output_text = response.choices[0].message.content.strip()
            else:
                response = client.messages.create(
                    model=model,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content}],
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                )
                output_text = response.content[0].text.strip()

            pairs = _parse_causal_response(output_text, valid_event_numbers)
            all_pairs.extend(pairs)

            if len(chunks) > 1:
                time.sleep(1.0)

        except json.JSONDecodeError as e:
            print(f"    Error parsing JSON response: {e}")
            print(f"    Response preview: {output_text[:500]}")
        except Exception as e:
            print(f"    Error calling LLM API ({provider}, model={model}): {e}")
            raise

    # Deduplicate
    seen = set()
    unique_pairs = []
    for pair in all_pairs:
        key = (pair['event_A_number'], pair['event_B_number'])
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)

    unique_pairs.sort(key=lambda p: (p['event_A_number'], p['event_B_number']))
    return unique_pairs


# ==============================
# FILE PROCESSING
# ==============================

def _read_story_events(events_path: Path) -> Optional[List[Dict]]:
    """Read story events from Excel/CSV/TSV. Returns list of dicts or None on error."""
    try:
        from helpers.flexible_io import read_story_events_file, story_events_to_records

        story_df = read_story_events_file(events_path)
        return story_events_to_records(story_df)
    except Exception as e:
        print(f"  Error reading events file: {e}")
        return None


def _save_causal_output(df: pd.DataFrame, output_file: Path) -> bool:
    """Save causal rating DataFrame to Excel (with CSV fallback)."""
    try:
        df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
        print(f"  Saved to: {output_file}")
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if 'locked' in error_msg or 'disturbed' in error_msg:
            print(f"  Warning: Excel file is locked. Saving as CSV instead...")
            csv_file = output_file.with_suffix('.csv')
            df.to_csv(csv_file, index=False, encoding='utf-8', na_rep='')
            print(f"  Saved to: {csv_file} (CSV format - Excel file was locked)")
            return True
        print(f"  Error saving output file: {e}")
        return False


def process_story_file(
    story_events_file: str,
    output_dir: str = 'output/causal_rated',
    method: str = 'linguistic',
    model: str = DEFAULT_MODEL,
    prompt_version: str = "causal_rating",
    api_key_override: str = None,
) -> bool:
    """
    Process a single story events file and produce causal ratings.

    Args:
        story_events_file: Path to story events Excel file.
        output_dir: Directory for output files.
        method: 'linguistic' (default), 'api', or 'manual'.
        model: LLM model identifier (for api method).
        prompt_version: Prompt file name without .txt (for api method).
        api_key_override: Override API key (for api method).

    Returns:
        True if successful, False otherwise.
    """
    events_path = Path(story_events_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    story_events = _read_story_events(events_path)
    if not story_events:
        print("  Warning: No events found in file")
        return False

    n_events = len(story_events)
    n_possible_pairs = n_events * (n_events - 1) // 2
    print(f"  Found {n_events} events ({n_possible_pairs} possible pairs)")
    print(f"  Method: {method}")

    if method == 'manual':
        # Manual method: create empty scaffold file for UI-based entry
        df = pd.DataFrame(columns=['event_A_number', 'event_B_number', 'rating', 'reasoning'])
        print(f"  Manual method: created empty causal rating scaffold")
        causal_pairs = []
    elif method == 'api':
        print(f"  Model: {model}")
        try:
            causal_pairs = rate_causal_pairs_api(
                story_events, model=model,
                prompt_version=prompt_version,
                api_key_override=api_key_override,
            )
        except Exception as e:
            print(f"  Error during API causal rating: {e}")
            return False
    else:
        causal_pairs = rate_causal_pairs_linguistic(story_events)

    if method != 'manual':
        print(f"  Found {len(causal_pairs)} causal pairs (rating > {RATING_THRESHOLD})")

    if causal_pairs:
        df = pd.DataFrame(causal_pairs)
        df = df[['event_A_number', 'event_B_number', 'rating', 'reasoning']]
    elif method != 'manual':
        df = pd.DataFrame(columns=['event_A_number', 'event_B_number', 'rating', 'reasoning'])

    stem = events_path.stem
    story_name = re.sub(r'_events(-.*)?$', '', stem)
    if method == 'api':
        method_suffix = f"api_{model}"
    elif method == 'manual':
        method_suffix = "manual"
    else:
        method_suffix = "linguistic"
    output_file = output_path / f"{story_name}_causal-{method_suffix}.xlsx"

    if method == 'api' and output_file.exists():
        trial_num = 2
        while True:
            trial_file = output_path / f"{story_name}_causal-{method_suffix}_trial{trial_num}.xlsx"
            if not trial_file.exists():
                output_file = trial_file
                break
            trial_num += 1

    return _save_causal_output(df, output_file)


def process_all_stories(
    input_dir: str = None,
    output_dir: str = None,
    method: str = 'linguistic',
    model: str = DEFAULT_MODEL,
    prompt_version: str = "causal_rating",
    api_key_override: str = None,
):
    """
    Process all story events files and produce causal ratings.

    Respects BATCH_INPUT_DIR, BATCH_OUTPUT_DIR, and BATCH_ITEM_ID environment
    variables for integration with the web interface.
    """
    input_dir = os.environ.get('BATCH_INPUT_DIR', input_dir or 'data/3_story_events')
    output_dir = os.environ.get('BATCH_OUTPUT_DIR', output_dir or 'output/causal_rated')

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return

    from helpers.flexible_io import STORY_EVENTS_EXTENSIONS

    events_files: list[Path] = []
    for ext in STORY_EVENTS_EXTENSIONS:
        events_files.extend(input_path.glob(f"*_events*{ext}"))
    events_files = sorted({f for f in events_files if '-edit' not in f.name}, key=lambda p: p.name)

    batch_item_id = os.environ.get('BATCH_ITEM_ID', None)
    if batch_item_id:
        filtered = [
            ef for ef in events_files
            if re.sub(r'_events(-.*)?$', '', ef.stem) == batch_item_id
        ]
        if not filtered:
            filtered = [
                ef for ef in events_files
                if re.sub(r'_events(-.*)?$', '', ef.stem) == batch_item_id
                or batch_item_id in ef.stem
            ]
        events_files = filtered
        if events_files:
            print(f"Filtering by BATCH_ITEM_ID: {batch_item_id}")
        else:
            print(f"No events files found matching BATCH_ITEM_ID: {batch_item_id}")

    explicit_events_variant = os.environ.get('BATCH_STORY_EVENTS_VARIANT')
    if explicit_events_variant is not None:
        before = len(events_files)
        events_files = [
            ef for ef in events_files
            if ef.stem.endswith(f"_events{explicit_events_variant}")
        ]
        print(
            f"Filtering by BATCH_STORY_EVENTS_VARIANT={explicit_events_variant!r}: "
            f"{before} -> {len(events_files)} file(s)"
        )

    if not events_files:
        print(f"No story events files found in {input_dir}"
              + (f" matching {batch_item_id}" if batch_item_id else ""))
        return

    if method == 'api':
        model = os.environ.get('CAUSAL_RATING_MODEL', model)
        prompt_version = os.environ.get('CAUSAL_RATING_PROMPT', prompt_version) or prompt_version
        api_key_override = api_key_override or os.environ.get('CAUSAL_RATING_API_KEY', None)

    print(f"Found {len(events_files)} story events file(s) to process")
    print(f"Method: {method}")
    if method == 'api':
        print(f"Model: {model}")
    print(f"Output directory: {output_path.absolute()}")
    print()

    processed_count = 0
    failed_count = 0

    for events_file in events_files:
        stem = events_file.stem
        story_name = re.sub(r'_events(-.*)?$', '', stem)
        print(f"Processing {events_file.name} (story: {story_name})...")

        success = process_story_file(
            story_events_file=str(events_file),
            output_dir=str(output_dir),
            method=method,
            model=model,
            prompt_version=prompt_version,
            api_key_override=api_key_override,
        )

        if success:
            processed_count += 1
        else:
            failed_count += 1
        print()

    print("Processing complete!")
    print(f"  Successfully processed: {processed_count} file(s)")
    print(f"  Failed: {failed_count} file(s)")

    if failed_count > 0:
        raise RuntimeError(f"{failed_count} file(s) failed to process")


# ==============================
# CLI
# ==============================

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='Rate causal relationships between story event pairs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Methods:
  linguistic  Rule-based causal scoring (default, no API key required)
  api         LLM-based causal rating (requires API key)
  manual      Empty scaffold for manual entry via the web interface

Examples:
  python scripts/6_causal-rater.py
  python scripts/6_causal-rater.py --method linguistic
  python scripts/6_causal-rater.py --method api --model gpt-4o
  python scripts/6_causal-rater.py --method manual
  python scripts/6_causal-rater.py --input data/3_story_events/my_story_events.xlsx
  python scripts/6_causal-rater.py --list-prompts
  python scripts/6_causal-rater.py --list-models
        """
    )

    parser.add_argument('--method', choices=VALID_METHODS, default='linguistic',
                        help='Rating method (default: linguistic)')
    parser.add_argument('--model', type=str, default=None,
                        help=f'LLM model for API method (default: {DEFAULT_MODEL})')
    parser.add_argument('--prompt-version', type=str, default=None,
                        help='Prompt filename from scripts/prompt/ (without .txt)')
    parser.add_argument('--input', type=str,
                        help='Input story events file (single file mode)')
    parser.add_argument('--output', type=str,
                        help='Output directory for causal rating files')
    parser.add_argument('--list-prompts', action='store_true',
                        help='List available causal rating prompts')
    parser.add_argument('--list-models', action='store_true',
                        help='List supported models')

    args = parser.parse_args()

    if args.list_prompts:
        prompts = list_causal_rating_prompts()
        print("Available causal rating prompts:")
        for p in prompts:
            print(f"  {p}")
        if not prompts:
            print("  (none found — place causal_rating*.txt files in scripts/prompt/)")
        sys.exit(0)

    if args.list_models:
        print("Supported models:")
        for mid, info in SUPPORTED_MODELS.items():
            print(f"  {mid}  ({info['provider']}, {info['label']})")
        sys.exit(0)

    method = args.method
    model = args.model or os.environ.get('CAUSAL_RATING_MODEL', DEFAULT_MODEL)

    if method == 'api':
        info = SUPPORTED_MODELS.get(model, {'provider': 'anthropic'})
        provider = info['provider']
        key_env = 'OPENAI_API_KEY' if provider == 'openai' else 'ANTHROPIC_API_KEY'
        if not os.getenv(key_env):
            print("=" * 70)
            print(f"ERROR: {key_env} not set")
            print(f"API causal rating requires an LLM API key.")
            print(f"Set it with: export {key_env}='your-key'")
            print(f"Or use --method linguistic for rule-based rating (no API key needed)")
            print("=" * 70)
            sys.exit(1)

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}")
            sys.exit(1)

        output_dir = args.output or 'output/causal_rated'
        print(f"Processing {input_path.name}...")
        success = process_story_file(
            story_events_file=str(input_path),
            output_dir=output_dir,
            method=method,
            model=model,
            prompt_version=args.prompt_version or "causal_rating",
        )
        if not success:
            sys.exit(1)
    else:
        try:
            input_dir = os.environ.get('BATCH_INPUT_DIR', None)
            output_dir = os.environ.get('BATCH_OUTPUT_DIR', args.output)
            process_all_stories(
                input_dir=input_dir,
                output_dir=output_dir,
                method=method,
                model=model,
                prompt_version=args.prompt_version or "causal_rating",
            )
        except Exception as e:
            print(f"Error processing stories: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
