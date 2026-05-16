#!/usr/bin/env python3
"""
Script to match recall segments to story events using an LLM batch prompt.

Default backend: Anthropic Claude Sonnet 4.5 (``ANTHROPIC_API_KEY``).

Alternative: local Gemma 4 E4B via Ollama — same batch JSON prompt as Claude, no rMatch.
Set ``RECALL_RATING_BACKEND=ollama`` and optionally ``RECALL_RATING_OLLAMA_MODEL=gemma4:e4b``.

Reads story events from data/3_story_events/ and parsed recall workbooks from output/recall_parsed/
(by default). Writes rated recall files to the configured output directory (Excel or CSV).
"""

from __future__ import annotations

import pandas as pd
import os
import sys
from pathlib import Path
from typing import List, Optional
import time
import re
import json

# anthropic is only required for --method api. Defer the import so users who
# only need offline methods (keyword, gemma-ollama, manual) don't need the
# [api] extra installed.
try:
    import anthropic
except ImportError:
    anthropic = None


def _software_package_root() -> Path:
    d = Path(__file__).resolve().parent
    return d.parent if d.name == "scripts" else d


_pr = _software_package_root()
if str(_pr) not in sys.path:
    sys.path.insert(0, str(_pr))


# ==============================
# SETTINGS
# ==============================

MODEL_NAME = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2000
TEMPERATURE = 0

# Models exposed in the UI for method='api'. Keep aligned with steps 2 and 6.
SUPPORTED_MODELS = {
    'claude-opus-4-7': {'provider': 'anthropic', 'label': 'Claude Opus 4.7'},
    'claude-sonnet-4-6': {'provider': 'anthropic', 'label': 'Claude Sonnet 4.6'},
    'claude-haiku-4-5-20251001': {'provider': 'anthropic', 'label': 'Claude Haiku 4.5'},
    'claude-sonnet-4-5-20250929': {'provider': 'anthropic', 'label': 'Claude Sonnet 4.5'},
    'claude-haiku-3-5-20241022': {'provider': 'anthropic', 'label': 'Claude Haiku 3.5'},
}


def _resolve_recall_rating_model() -> str:
    """Resolve the Anthropic model id from RECALL_RATING_MODEL env var (set by launcher), else default."""
    return (os.environ.get("RECALL_RATING_MODEL") or "").strip() or MODEL_NAME

# System prompt
SYSTEM_PROMPT = """You are a careful annotation assistant.
You must not rewrite, paraphrase, or modify any recall text.
"""

# Load user prompt from file
def load_user_prompt(prompt_version="recall_rating"):
    """
    Load the user prompt from the scripts/prompt/ folder.
    
    Args:
        prompt_version: Name of the prompt file (without .txt extension).
                       Defaults to "recall_rating".
                       Can be set via RECALL_RATING_PROMPT environment variable.
    
    Returns:
        Prompt text as string, or default prompt if file not found.
    """
    # Check for environment variable override
    env_prompt = os.getenv('RECALL_RATING_PROMPT')
    if env_prompt:
        prompt_version = env_prompt
    
    prompt_file = Path(__file__).resolve().parent / "prompt" / f"{prompt_version}.txt"
    
    if prompt_file.exists():
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                print(f"Loaded prompt from: {prompt_file}")
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read {prompt_file}: {e}")
    
    # Fallback to default prompt
    print(f"Warning: Prompt file '{prompt_version}.txt' not found. Using default prompt.")
    return """You are given two Excel files: 
story_events.xlsx (each row is a story event; columns: `event`, `story_texts`) and 
story_recall.xlsx (each row is one recall segment). Go through the recall file row by row. 
For each recall segment, identify which story event(s) in `story_events.xlsx` it refers to.
* Write the matching event number(s) into column 1 of the recall row.
* If multiple events are referenced, separate numbers with commas.
* If no event matches, use NONE. Do not modify recall text, row order, or file structure.

Output format (STRICT):
- Output ONLY valid JSON array.
- Each element MUST be an object with EXACTLY these keys:
  - "row_index" (0-based, in the same order and length as recall_rows)
  - "matched_events"
- Do NOT include recall_text, explanations, comments, or extra text in the output.
- You MUST output one object for EVERY recall row. If no event matches, matched_events MUST be "NONE". Missing or skipped row_index is NOT allowed."""

USER_PROMPT = load_user_prompt()


def _safe_filename_slug(s: str, max_len: int = 72) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", s.strip()).strip("_")
    return (slug or "default")[:max_len]


def _recall_rating_use_ollama() -> bool:
    b = (os.environ.get("RECALL_RATING_BACKEND") or "").strip().lower()
    return b in ("ollama", "gemma-ollama", "ollama-gemma", "local-gemma")


def _recall_rating_use_rmatch() -> bool:
    b = (os.environ.get("RECALL_RATING_BACKEND") or "").strip().lower()
    return b in ("rmatch", "rmatch-pypi", "rmatch-hf")


def _rmatch_model_name() -> str:
    return (os.environ.get("RMATCH_MODEL_NAME") or "").strip() or "google/gemma-4-31B-it"


def _recall_ollama_model_tag() -> str:
    return (
        (os.environ.get("RECALL_RATING_OLLAMA_MODEL") or "").strip()
        or (os.environ.get("OLLAMA_GEMMA_TAG") or "").strip()
        or "gemma4:e4b"
    )


def _strip_markdown_json_fenced(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        parts = t.split("```")
        t = parts[1].strip() if len(parts) > 1 else ""
    if t.startswith("json"):
        t = t[4:].strip()
    return t


def _normalize_recall_rating_json_rows(parsed, n_rows: int) -> list:
    """Turn assorted LLM JSON shapes into a list of row dicts with row_index / matched_events."""
    if isinstance(parsed, list) and parsed:
        if all(isinstance(x, dict) for x in parsed):
            return list(parsed)
        # Gemma sometimes outputs only matched_events strings in row order (prompt asks for objects).
        if all(isinstance(x, str) for x in parsed) and len(parsed) == n_rows:
            return [{"row_index": i, "matched_events": x} for i, x in enumerate(parsed)]
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if not isinstance(parsed, dict):
        return []
    for key in ("results", "result", "matches", "ratings", "output", "data", "rows"):
        inner = parsed.get(key)
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    if "row_index" in parsed and "matched_events" in parsed:
        return [parsed]
    pairs: list[tuple[int, dict]] = []
    for k, v in parsed.items():
        if isinstance(v, dict) and str(k).isdigit():
            pairs.append((int(k), v))
    if pairs:
        pairs.sort(key=lambda x: x[0])
        return [v for _, v in pairs]
    return []


def parse_recall_rating_batch_json(output_text: str, n_rows: int) -> List[str]:
    """Parse model JSON array into per-row matched_events strings (same contract as Claude path)."""
    if n_rows <= 0:
        return []
    try:
        t = _strip_markdown_json_fenced(output_text)
        matched_raw = json.loads(t)
        matched = _normalize_recall_rating_json_rows(matched_raw, n_rows)
        if not matched:
            raise ValueError(
                "model output must be a JSON array of objects (or a single object / wrapped object)"
            )
        result_map: dict[int, str] = {}
        for item in matched:
            try:
                row_idx = int(item.get("row_index", -1))
            except (TypeError, ValueError):
                continue
            matched_events = item.get("matched_events", "NONE")
            if matched_events == "NONE" or matched_events == "":
                result_map[row_idx] = ""
            else:
                result_map[row_idx] = str(matched_events).strip()
        return [result_map.get(i, "") for i in range(n_rows)]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"  Error parsing JSON response: {e}")
        print(f"  Response text: {(output_text or '')[:500]}")
        return [""] * n_rows


def _matched_events_list_from_rating_strings(
    results: List[str], story_events: List[dict]
) -> tuple[List[str], int]:
    valid_events = {event["event"] for event in story_events}
    matched_events_list: List[str] = []
    matched_count = 0
    for result in results:
        if result and result.strip() and result.strip().upper() != "NONE":
            numbers = re.findall(r"\d+", result)
            if numbers:
                matched_events = [int(n) for n in numbers if int(n) in valid_events]
                if matched_events:
                    matched_events_list.append(
                        ",".join(str(int(e)) for e in sorted(set(matched_events)))
                    )
                    matched_count += 1
                else:
                    matched_events_list.append("")
            else:
                matched_events_list.append("")
        else:
            matched_events_list.append("")
    return matched_events_list, matched_count


# ==============================
# API CLIENT
# ==============================

def get_anthropic_client(test_mode=False):
    """
    Initialize and return Anthropic client.
    
    Args:
        test_mode: If True, returns None (for test mode without API)
    
    Returns:
        Anthropic client instance or None if test_mode
    """
    if test_mode:
        return None
    
    if anthropic is None:
        raise ImportError(
            "The 'anthropic' package is required for --method api. "
            "Install it with: pip install 'narraters[api]'  (or: pip install anthropic)"
        )
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
        )
    return anthropic.Anthropic(api_key=api_key)


# ==============================
# BATCH PROCESSING (PRIMARY METHOD)
# ==============================

def rate_recall_batch(
    client: anthropic.Anthropic,
    recall_segments: List[str],
    story_events: List[dict],
    model: str = MODEL_NAME
) -> List[str]:
    """
    Rate all recall segments in a single batch API call.
    
    Args:
        client: Anthropic API client
        recall_segments: List of recall segment texts
        story_events: List of dicts with 'event' (int) and 'story_texts' (str) keys
        model: Claude model to use
        
    Returns:
        List of matched events strings (e.g., "1,2" or "" for no match)
    """
    if not recall_segments:
        return []
    
    # Prepare events payload
    events_payload = [{"event": event['event'], "story_texts": event['story_texts']} 
                     for event in story_events]
    
    # Build the user message
    user_content = (
        USER_PROMPT
        + "\n\nStory Events:\n"
        + json.dumps(events_payload, ensure_ascii=False, indent=2)
        + "\n\nRecall Texts:\n"
        + json.dumps(recall_segments, ensure_ascii=False, indent=2)
    )
    
    try:
        # Call Claude API
        response = client.messages.create(
            model=model,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": user_content
            }],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        
        # Extract response text
        output_text = response.content[0].text.strip()
        return parse_recall_rating_batch_json(output_text, len(recall_segments))

    except Exception as e:
        print(f"  Error calling Claude API: {e}")
        # Fallback: return empty matches
        return [""] * len(recall_segments)


def _rmatch_hf_api_key() -> str:
    k = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if k:
        return k
    # Lazy-load software/.env so rmatch can pick up HF_TOKEN from the same place as the standalone helper.
    try:
        from helpers.util_software_env import load_software_dotenv
        load_software_dotenv(Path(__file__).resolve().parent.parent)
    except Exception:
        pass
    k = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if k:
        return k
    try:
        import huggingface_hub
        t = huggingface_hub.get_token()
        if t and str(t).strip():
            return str(t).strip()
    except Exception:
        pass
    return ""


def _rmatch_safe_filename_slug(s: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", s.strip()).strip("-")
    return (slug or "model")[:max_len]


def _rmatch_method_suffix() -> str:
    """Filename suffix for rMatch outputs: -rmatch-pypi-{model-slug}-{quant}."""
    model = _rmatch_model_name()
    quant = (os.environ.get("RMATCH_QUANTIZATION") or "4bit").strip().lower()
    qtag = quant if quant in ("4bit", "8bit") else "noquant"
    return f"-rmatch-pypi-{_rmatch_safe_filename_slug(model)}-{qtag}"


def _rmatch_match_recall_to_events(
    recall_segments: List[str],
    story_events: List[dict],
) -> tuple[List[str], int]:
    """Run the PyPI ``rmatch`` Hugging Face matcher and return (per-row matched_events strings, n_matched)."""
    api_key = _rmatch_hf_api_key()
    if not api_key:
        raise RuntimeError(
            "No Hugging Face token. Set HF_TOKEN in software/.env, export HF_TOKEN, "
            "or run `huggingface-cli login` so rmatch can authenticate."
        )

    story_segments = [str(e.get("story_texts") or "").strip() for e in story_events]
    event_by_pos = [int(e["event"]) for e in story_events]

    model = _rmatch_model_name()
    quant = (os.environ.get("RMATCH_QUANTIZATION") or "4bit").strip().lower()
    window = int((os.environ.get("RMATCH_WINDOW_SIZE") or "5").strip() or "5")
    prompt = (os.environ.get("RMATCH_PROMPT") or "primary_no_story_no_cot").strip()

    kwargs: dict = {
        "model_name": model,
        "window_size": window,
        "prompt": prompt,
        "api_key": api_key,
    }
    if quant in ("4bit", "8bit"):
        kwargs["quantization"] = quant
    mnt = (os.environ.get("RMATCH_MAX_NEW_TOKENS") or "").strip()
    if mnt.isdigit():
        kwargs["max_new_tokens"] = int(mnt)
    bs_raw = (os.environ.get("RMATCH_BATCH_SIZE") or "").strip()
    if bs_raw.isdigit():
        kwargs["batch_size"] = int(bs_raw)
    elif sys.platform == "darwin":
        # Apple MPS: long rMatch prompts hit Metal NDArray size limits; batch=1 is safest.
        kwargs["batch_size"] = 1

    force_cpu_env = (os.environ.get("RMATCH_FORCE_CPU") or "").strip().lower()
    if force_cpu_env in ("1", "true", "yes"):
        import torch
        torch.backends.mps.is_available = lambda: False  # noqa: ARG005 — force CPU
    elif sys.platform == "darwin" and force_cpu_env not in ("0", "false", "no"):
        # macOS default: avoid MPS NDArray>2**32 byte abort on long prompts.
        import torch
        torch.backends.mps.is_available = lambda: False  # noqa: ARG005

    print(f"    rMatch Matcher(matcher_name=huggingface, model={model!r}, quant={quant!r}, window={window}, prompt={prompt!r})")
    from rmatch import Matcher
    matcher = Matcher(matcher_name="huggingface", **kwargs)
    print(
        f"    Matching {len(recall_segments)} recall segments via rMatch "
        f"(may take many minutes on CPU)...",
        flush=True,
    )
    matches = matcher.match(story_segments, recall_segments)
    by_idx = {idx: idxs for idx, idxs in matches}

    matched_events_list: List[str] = []
    matched_count = 0
    for i in range(len(recall_segments)):
        story_indices = by_idx.get(i, []) or []
        ids = sorted({
            event_by_pos[j] for j in story_indices
            if isinstance(j, int) and 0 <= j < len(event_by_pos)
        })
        s = ",".join(str(x) for x in ids)
        matched_events_list.append(s)
        if s:
            matched_count += 1
    return matched_events_list, matched_count


def rate_recall_batch_ollama(
    recall_segments: List[str],
    story_events: List[dict],
    model_tag: str | None = None,
) -> List[str]:
    """
    Same batch prompt/JSON contract as ``rate_recall_batch``, via Ollama (e.g. gemma4:e4b).
    """
    if not recall_segments:
        return []

    from helpers.ollama_gemma_e4b import ollama_chat

    events_payload = [
        {"event": event["event"], "story_texts": event["story_texts"]} for event in story_events
    ]
    user_content = (
        USER_PROMPT
        + "\n\nStory Events:\n"
        + json.dumps(events_payload, ensure_ascii=False, indent=2)
        + "\n\nRecall Texts:\n"
        + json.dumps(recall_segments, ensure_ascii=False, indent=2)
    )

    tag = (model_tag or _recall_ollama_model_tag()).strip() or "gemma4:e4b"
    try:
        num_ctx = int(os.environ.get("RECALL_RATING_OLLAMA_NUM_CTX", "32768"))
    except ValueError:
        num_ctx = 32768
    try:
        num_predict = int(os.environ.get("RECALL_RATING_OLLAMA_MAX_TOKENS", str(MAX_TOKENS)))
    except ValueError:
        num_predict = MAX_TOKENS

    host = (os.environ.get("RECALL_RATING_OLLAMA_HOST") or os.environ.get("OLLAMA_HOST") or "").strip()
    base_url = host or None

    # Constrain the model output to a fixed-length array of {row_index, matched_events}.
    # Plain ``format="json"`` lets the model emit any valid JSON value — gemma4:e4b in
    # particular tends to return a single object covering only row 0. A JSON schema
    # forces one object per recall row.
    n_rows = len(recall_segments)
    response_schema = {
        "type": "array",
        "minItems": n_rows,
        "maxItems": n_rows,
        "items": {
            "type": "object",
            "properties": {
                "row_index": {"type": "integer"},
                "matched_events": {"type": "string"},
            },
            "required": ["row_index", "matched_events"],
        },
    }

    try:
        output_text = ollama_chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            model_tag=tag,
            temperature=TEMPERATURE,
            num_ctx=num_ctx,
            num_predict=num_predict,
            think=False,
            timeout=900,
            base_url=base_url,
            response_format=response_schema,
        )
        return parse_recall_rating_batch_json(output_text, len(recall_segments))
    except Exception as e:
        print(f"  Error calling Ollama for recall batch: {e}")
        return [""] * len(recall_segments)


# ==============================
# INDIVIDUAL SEGMENT PROCESSING (FOR BACKWARD COMPATIBILITY)
# ==============================

def match_recall_to_events_sonnet(
    client: anthropic.Anthropic,
    recall_segment: str,
    story_events: List[dict],
    model: str = MODEL_NAME
) -> List[int]:
    """
    Use Claude Sonnet to match a recall segment to story events.
    
    This function is kept for backward compatibility with the web interface.
    For efficiency, consider using rate_recall_batch() instead.
    
    Args:
        client: Anthropic API client
        recall_segment: Text of the recall segment to match
        story_events: List of dicts with 'event' (int) and 'story_texts' (str) keys
        model: Claude model to use
        
    Returns:
        List of event numbers (integers) that match, empty list if no matches
    """
    if not recall_segment or not isinstance(recall_segment, str) or len(recall_segment.strip()) == 0:
        return []
    
    # Use batch processing with a single segment for consistency
    results = rate_recall_batch(client, [recall_segment], story_events, model)
    
    if not results or not results[0]:
        return []
    
    # Parse the matched_events string (could be "1", "1,2", etc.)
    matched_str = results[0]
    if matched_str.lower() in ['none', '']:
        return []
    
    # Extract numbers
    numbers = re.findall(r'\d+', matched_str)
    if not numbers:
        return []
    
    # Convert to integers and filter to valid event numbers
    event_numbers = [int(n) for n in numbers]
    valid_events = {event['event'] for event in story_events}
    matched_events = [int(e) for e in event_numbers if e in valid_events]
    
    # Remove duplicates and sort
    matched_events = sorted(list(set(matched_events)))
    
    return matched_events


def match_recall_to_events_test_mode(
    recall_segment: str,
    story_events: List[dict]
) -> List[int]:
    """
    Test mode: High-quality semantic matching (simulates API response).
    Uses strict, precise matching to avoid false positives.
    
    This function is kept for backward compatibility with the web interface.
    
    Args:
        recall_segment: Text of the recall segment to match
        story_events: List of dicts with 'event' (int) and 'story_texts' (str) keys
        
    Returns:
        List of event numbers (integers) that match - typically 0-2 events for precision
    """
    if not recall_segment or not isinstance(recall_segment, str) or len(recall_segment.strip()) == 0:
        return []
    
    # Skip very short or vague segments
    recall_clean = recall_segment.strip()
    if len(recall_clean) < 10:
        # Very short segments are often too vague - be very strict
        pass
    
    # Normalize text (handle first/second person)
    recall_normalized = recall_segment.lower().strip()
    recall_normalized = re.sub(r'\bi\b', 'you', recall_normalized)
    recall_normalized = re.sub(r'\bmy\b', 'your', recall_normalized)
    recall_normalized = re.sub(r'\bme\b', 'you', recall_normalized)
    recall_normalized = re.sub(r'\bmyself\b', 'yourself', recall_normalized)
    
    # Extract meaningful words (longer words are more significant)
    recall_words = set(re.findall(r'\b\w{4,}\b', recall_normalized))  # Only words 4+ chars
    
    # Remove common stop words
    stop_words = {
        'the', 'and', 'but', 'for', 'are', 'was', 'were', 'been', 'have', 'has', 'had',
        'this', 'that', 'with', 'from', 'then', 'when', 'where', 'what', 'which', 'who',
        'can', 'could', 'would', 'should', 'may', 'might', 'must', 'will', 'shall',
        'about', 'into', 'onto', 'upon', 'over', 'under', 'through', 'during', 'while',
        'there', 'here', 'some', 'many', 'more', 'most', 'very', 'much', 'also', 'just'
    }
    recall_words = recall_words - stop_words
    
    # Extract key phrases (2-word sequences with meaningful words)
    recall_phrases = set()
    words_list = recall_normalized.split()
    for i in range(len(words_list) - 1):
        w1, w2 = words_list[i], words_list[i+1]
        if len(w1) > 3 and len(w2) > 3 and w1 not in stop_words and w2 not in stop_words:
            phrase = f"{w1} {w2}"
            recall_phrases.add(phrase)
    
    # Key semantic concepts with specific matching
    key_concepts = {
        'dream': ['dream', 'dreaming', 'dreams', 'awaken', 'awake', 'waking', 'wake'],
        'bird': ['bird', 'birds', 'chirp', 'chirps', 'chirping', 'peeps'],
        'chest': ['chest'],
        'bed': ['bed'],
        'journey': ['journey', 'journeys', 'travel', 'walking', 'foot'],
        'crossroad': ['crossroad', 'crossroads'],
        'kingdom': ['kingdom', 'kingdoms'],
        'heir': ['heir'],
        'duchess': ['duchess'],
        'village': ['village'],
        'old_man': ['old', 'man'],
        'dr_peeps': ['peeps', 'dr']
    }
    
    event_scores = []
    
    for event in story_events:
        story_text = str(event['story_texts']).lower().strip()
        story_words = set(re.findall(r'\b\w{4,}\b', story_text))
        story_words = story_words - stop_words
        
        score = 0.0
        match_reasons = []  # Track why this matches
        
        # 1. Exact phrase matching (40% weight) - most important for precision
        story_phrases = set()
        story_words_list = story_text.split()
        for i in range(len(story_words_list) - 1):
            w1, w2 = story_words_list[i], story_words_list[i+1]
            if len(w1) > 3 and len(w2) > 3 and w1 not in stop_words and w2 not in stop_words:
                phrase = f"{w1} {w2}"
                story_phrases.add(phrase)
        
        if recall_phrases and story_phrases:
            phrase_overlap = recall_phrases & story_phrases
            if phrase_overlap:
                phrase_score = len(phrase_overlap) / max(len(recall_phrases), 1)
                score += phrase_score * 0.4
                match_reasons.append(f"phrase_match:{len(phrase_overlap)}")
        
        # 1b. Partial phrase matching (10% weight) - if words appear near each other
        if recall_phrases:
            partial_matches = 0
            for r_phrase in recall_phrases:
                r_words = r_phrase.split()
                # Check if both words appear in story (even if not together)
                if len(r_words) == 2 and r_words[0] in story_text and r_words[1] in story_text:
                    # Check if they appear close together (within 5 words)
                    story_words_list = story_text.split()
                    try:
                        idx1 = story_words_list.index(r_words[0])
                        idx2 = story_words_list.index(r_words[1])
                        if abs(idx1 - idx2) <= 5:
                            partial_matches += 1
                    except ValueError:
                        pass
            if partial_matches > 0:
                partial_score = min(partial_matches / len(recall_phrases), 1.0) * 0.1
                score += partial_score
        
        # 2. Key concept matching (35% weight) - specific concepts (increased importance)
        concept_matches = 0
        matched_concepts = []
        for concept_name, keywords in key_concepts.items():
            recall_has = any(kw in recall_normalized for kw in keywords)
            story_has = any(kw in story_text for kw in keywords)
            if recall_has and story_has:
                concept_matches += 1
                matched_concepts.append(concept_name)
                match_reasons.append(concept_name)
        
        if concept_matches > 0:
            # Boost score more for concept matches
            concept_score = min(concept_matches / 1.5, 1.0)  # More generous
            score += concept_score * 0.35
        
        # 3. Significant word overlap (15% weight) - more permissive
        if recall_words and story_words:
            overlap = recall_words & story_words
            if len(overlap) >= 1:  # Lower threshold - at least 1 word
                word_score = len(overlap) / max(len(recall_words), 1)
                # Boost if multiple words match
                if len(overlap) >= 2:
                    word_score *= 1.2  # 20% boost for multiple matches
                score += word_score * 0.15
                match_reasons.append(f"words:{len(overlap)}")
        
        # Quality filters - reject if too vague
        # Reject if recall is very short and score is very low
        if len(recall_clean) < 10 and score < 0.25:
            continue
        
        # Require minimum score threshold (more permissive to catch more matches)
        if score >= 0.18:  # Lower threshold
            event_scores.append((event['event'], score, match_reasons))
    
    # Sort by score (highest first)
    event_scores.sort(key=lambda x: -x[1])
    
    # Return matches with quality filtering - more balanced approach
    matching_events = []
    top_score = event_scores[0][1] if event_scores else 0
    
    for event_num, score, reasons in event_scores:
        # High confidence: always include (score >= 0.35)
        if score >= 0.35:
            matching_events.append(event_num)
        # Medium-high confidence: include if within 0.12 of top score
        elif score >= 0.25 and (top_score - score) <= 0.12 and len(matching_events) < 3:
            matching_events.append(event_num)
        # Medium confidence: include if it's the top match or close to top
        elif score >= 0.22 and (top_score - score) <= 0.15 and len(matching_events) < 2:
            matching_events.append(event_num)
        # Lower confidence: include if no other matches or score is reasonable
        elif score >= 0.18 and (len(matching_events) == 0 or (top_score - score) <= 0.2):
            if len(matching_events) < 2:  # Max 2 for lower confidence
                matching_events.append(event_num)
        else:
            break  # Stop once we hit significantly lower scores
    
    # Limit to max 3 matches for quality
    if len(matching_events) > 3:
        matching_events = matching_events[:3]
    
    return sorted(matching_events)


# ==============================
# SUBJECT PROCESSING
# ==============================

_EDITORIAL_STORY_SUFFIXES = ("_edited", "_edit", "_revised", "_clean", "_final")


def parse_recall_parsed_path(recall_file: Path) -> tuple[str, str]:
    """
    From a recall-parse workbook path, return (story_item_id, rated_edit_tail).

    Tolerates method-suffix chains from earlier pipeline steps. Recognises:
      - ``{item}_parsed.xlsx`` (canonical)
      - ``{item}_parsed-<parse-method>.xlsx``
      - ``{item}_spell-<spell-method>_parsed[-<parse-method>].xlsx``
      - any of the above with a trailing ``_<username>-edit`` before ``.xlsx``

    rated_edit_tail is '' or '_username-edit' appended after the method suffix in
    rated outputs (matches web-interface find_best_edit_file patterns).
    """
    stem = recall_file.stem

    # Strip user-edit tail if present (only the suffix, not embedded "edit" tokens)
    edit_m = re.search(r"_(?P<user>\w+-edit)$", stem)
    if edit_m:
        tail = f"_{edit_m.group('user')}"
        stem = stem[: edit_m.start()]
    else:
        tail = ""

    # Prefer matching a "{item}_spell-...parsed..." chain so we recover the
    # original item_id without the inherited spell-correction tag.
    m = re.match(r"^(?P<item>.+?)_spell-.*_parsed(?:[-_].*)?$", stem)
    if m:
        return m.group("item"), tail
    m = re.match(r"^(?P<item>.+?)_parsed(?:[-_].*)?$", stem)
    if m:
        return m.group("item"), tail
    # Last-ditch fallback for unusual names
    return stem.replace("_parsed", ""), tail


def expand_story_event_file_bases(item_id: str) -> list[str]:
    """Basenames for ``{{base}}_events*.xlsx``, aligned with server/web-interface.expand_story_event_file_bases."""
    if not item_id:
        return []
    seen: set[str] = set()
    out: list[str] = []

    def add(b: Optional[str]) -> None:
        if b and b not in seen:
            seen.add(b)
            out.append(b)

    add(item_id)
    m = re.match(r"^(.+?)_sub-?\d+$", item_id)
    if m:
        add(m.group(1))
    for b in list(out):
        if not b or "_sub-" in b:
            continue
        for suf in _EDITORIAL_STORY_SUFFIXES:
            if b.endswith(suf) and len(b) > len(suf):
                add(b[: -len(suf)])
    return out


def _pick_story_events_for_base(events_dir: Path, base_id: str) -> Optional[Path]:
    """Resolve ``{base}_events.xlsx``; prefer exact canonical name over newer *-fine / *-coarse files."""
    base = f"{base_id}_events"
    p0 = events_dir / f"{base}.xlsx"
    if p0.exists():
        return p0
    paths: list[Path] = []
    paths.extend(events_dir.glob(f"{base}-*.xlsx"))
    for suffix in ("_rule-based.xlsx", "_api.xlsx"):
        q = events_dir / f"{base}{suffix}"
        if q.exists():
            paths.append(q)
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def iter_story_events_search_dirs(story_dir_arg: str) -> list[Path]:
    """Directories to search for story-event .xlsx (subset of web-interface.iter_story_events_search_dirs)."""
    roots: list[Path] = []
    seen: set = set()

    def add(d: Path) -> None:
        try:
            k = d.resolve()
        except OSError:
            k = d
        if k not in seen:
            seen.add(k)
            roots.append(d)

    env_override = (os.environ.get("NARRATIVE_STORY_EVENTS_DIR") or "").strip()
    if env_override:
        add(Path(env_override).expanduser())

    sd = Path(story_dir_arg)
    if not sd.is_absolute():
        sd = _software_package_root() / sd
    add(sd)

    pkg_root = _software_package_root()
    add(pkg_root / "data" / "3_story_events")
    add(pkg_root.parent / "data" / "3_story_events")
    return roots


def resolve_story_events_xlsx(subj_id: str, story_dir_arg: str = "data/3_story_events") -> Optional[Path]:
    """Resolve path to story events Excel for a subject (story-stem filenames, multiple dirs).

    Honors ``BATCH_STORY_EVENTS_VARIANT`` (env var): when set, matches
    ``{base}_events{variant}.xlsx`` exactly, with no granularity fallback.
    """
    bases = expand_story_event_file_bases(subj_id)
    explicit_variant = os.environ.get("BATCH_STORY_EVENTS_VARIANT")
    for events_dir in iter_story_events_search_dirs(story_dir_arg):
        if not events_dir.is_dir():
            continue
        for base in bases:
            if explicit_variant is not None:
                cand = events_dir / f"{base}_events{explicit_variant}.xlsx"
                if cand.is_file():
                    print(
                        f"  Using story events file: {cand.name} "
                        f"(directory={events_dir}, base={base!r}, variant={explicit_variant!r})"
                    )
                    return cand
                continue
            picked = _pick_story_events_for_base(events_dir, base)
            if picked:
                print(f"  Using story events file: {picked.name} (directory={events_dir}, base={base!r})")
                return picked
    print(f"  Warning: No story events file found for subject {subj_id!r}")
    print(f"    Searched bases: {bases}")
    print(f"    Story dir argument: {story_dir_arg!r}")
    if explicit_variant is not None:
        print(f"    Required variant: {explicit_variant!r} (BATCH_STORY_EVENTS_VARIANT)")
    return None


def process_subject(
    subj_id: str,
    story_dir: str = 'data/3_story_events',
    recall_dir: str = 'output/recall_parsed',
    output_dir: str = 'output/recall_rated',
    output_format: str = 'excel',
    model: str = MODEL_NAME,
    delay: float = 1.0,
    test_mode: bool = False,
    use_batch: bool = True,
    recall_source: Optional[Path] = None,
):
    """
    Process a single subject's recall file and match it to story events using Claude Sonnet 4.5.
    
    Args:
        subj_id: Subject ID (e.g., 'subN_XXXX')
        story_dir: Directory containing story event files
        recall_dir: Directory containing parsed recall files
        output_dir: Directory to save rated recall files
        output_format: Output format ('excel' or 'csv')
        model: Claude model to use
        delay: Delay between API calls (seconds) to avoid rate limits (not used in batch mode)
        test_mode: If True, use test mode matching instead of API
        use_batch: If True, use batch processing (more efficient)
        recall_source: Optional explicit parsed-recall workbook (e.g. *_parsed_*-edit.xlsx)

    Returns:
        True if successful, False otherwise
    """
    recall_path = Path(recall_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(exist_ok=True)

    if recall_source is not None:
        recall_file = Path(recall_source)
        if not recall_file.is_absolute():
            recall_file = recall_path / recall_file.name
    else:
        explicit_variant = os.environ.get("BATCH_INPUT_VARIANT")
        if explicit_variant is not None:
            recall_file = recall_path / f"{subj_id}{explicit_variant}.xlsx"
        else:
            recall_file = recall_path / f"{subj_id}_parsed.xlsx"
            if not recall_file.exists():
                env_rf = (os.environ.get("BATCH_RECALL_FILE") or "").strip()
                if env_rf:
                    cand = Path(env_rf)
                    if not cand.is_absolute():
                        cand = recall_path / cand.name
                    if cand.is_file():
                        recall_file = cand
            if not recall_file.exists():
                edits = sorted(
                    (
                        p
                        for p in recall_path.glob(f"{subj_id}_parsed_*-edit.xlsx")
                        if re.search(r"_\w+-edit\.xlsx$", p.name, re.IGNORECASE)
                    ),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if edits:
                    recall_file = edits[0]

    if not recall_file.is_file():
        print(f"  Warning: Recall parsed file not found: {recall_file}")
        return False

    story_id, rated_edit_tail = parse_recall_parsed_path(recall_file)
    if story_id != subj_id:
        print(
            f"  Note: Parsed filename implies item_id={story_id!r} (caller passed {subj_id!r}); "
            "using filename for story events and rated output basename."
        )

    story_file = resolve_story_events_xlsx(story_id, story_dir)
    if not story_file:
        return False
    
    # Read story events file
    try:
        story_df = pd.read_excel(story_file)
        if "event" not in story_df.columns:
            print("  Error: Story events file missing required column (event)")
            return False
        text_col = (
            "story_texts"
            if "story_texts" in story_df.columns
            else ("story_text" if "story_text" in story_df.columns else None)
        )
        if not text_col:
            print("  Error: Story events file missing story text column (story_texts or story_text)")
            return False

        # Convert to list of dicts for easier handling
        story_events = [
            {
                "event": int(row["event"]),
                "story_texts": str(row[text_col]) if pd.notna(row[text_col]) else "",
            }
            for _, row in story_df.iterrows()
            if pd.notna(row["event"])
        ]
        
    except Exception as e:
        print(f"  Error reading story events file: {e}")
        return False
    
    # Read recall parsed file
    try:
        recall_df = pd.read_excel(recall_file)
        if 'recall_in_temporal_order' not in recall_df.columns:
            print(f"  Error: Recall file missing required column (recall_in_temporal_order)")
            return False
    except Exception as e:
        print(f"  Error reading recall file: {e}")
        return False
    
    # Ensure recalled_events column exists
    if 'recalled_events' not in recall_df.columns:
        recall_df.insert(0, 'recalled_events', '')

    total_segments = len(recall_df)
    matched_count = 0
    matched_events_list: List[str] = []

    print(f"  Processing {total_segments} recall segments...")

    recall_segments: List[str] = []
    for _, row in recall_df.iterrows():
        recall_segment = row["recall_in_temporal_order"]
        if (
            pd.isna(recall_segment)
            or not isinstance(recall_segment, str)
            or len(str(recall_segment).strip()) == 0
        ):
            recall_segments.append("")
        else:
            recall_segments.append(str(recall_segment))

    use_ollama_recall = _recall_rating_use_ollama()
    use_rmatch_recall = _recall_rating_use_rmatch()

    if use_ollama_recall:
        try:
            from helpers.ollama_gemma_e4b import check_ollama_e4b_environment
        except ImportError as e:
            print(f"  Error: Could not import Ollama helper: {e}")
            return False
        tag = _recall_ollama_model_tag()
        report = check_ollama_e4b_environment(model_tag=tag)
        if not report.get("ok"):
            for err in report.get("errors") or []:
                print(f"  Error: {err}")
            return False
        for w in report.get("warnings") or []:
            print(f"  Warning: {w}")
        d = report.get("details") or {}
        print(f"  Ollama OK (base={d.get('base', '?')}, model_tag={d.get('model_tag', '?')})")
        print(f"    Ollama batch (same JSON prompt as Claude) model={tag!r}...")
        results = rate_recall_batch_ollama(recall_segments, story_events, model_tag=tag)
        matched_events_list, matched_count = _matched_events_list_from_rating_strings(
            results, story_events
        )
    elif use_rmatch_recall:
        try:
            matched_events_list, matched_count = _rmatch_match_recall_to_events(
                recall_segments, story_events
            )
        except Exception as e:
            print(f"  Error running rMatch matcher: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # Initialize Anthropic client (or use test mode)
        client = None
        if not test_mode:
            try:
                client = get_anthropic_client()
            except Exception as e:
                print(f"  Error: Failed to initialize LLM API client: {e}")
                return False
        else:
            print(f"  Running in TEST MODE (simulated matching)")

        if test_mode:
            # Test mode: process one by one
            for idx, row in recall_df.iterrows():
                recall_segment = row["recall_in_temporal_order"]

                # Skip if empty
                if (
                    pd.isna(recall_segment)
                    or not isinstance(recall_segment, str)
                    or len(str(recall_segment).strip()) == 0
                ):
                    matched_events_list.append("")
                    continue

                # Use test mode matching
                matching_events = match_recall_to_events_test_mode(
                    recall_segment=str(recall_segment),
                    story_events=story_events,
                )

                # Store match result
                if matching_events:
                    matched_events_list.append(
                        ",".join(str(int(e)) for e in matching_events)
                    )
                    matched_count += 1
                else:
                    matched_events_list.append("")

                # Progress indicator
                if (idx + 1) % 5 == 0:
                    print(f"    Processed {idx + 1}/{total_segments} segments...")

        elif use_batch:
            # Batch mode: process all segments at once
            print(f"    Using batch processing with {model}...")
            results = rate_recall_batch(client, recall_segments, story_events, model)
            matched_events_list, matched_count = _matched_events_list_from_rating_strings(
                results, story_events
            )

        else:
            # Individual mode: process one by one (for backward compatibility)
            for idx, row in recall_df.iterrows():
                recall_segment = row["recall_in_temporal_order"]

                # Skip if empty
                if (
                    pd.isna(recall_segment)
                    or not isinstance(recall_segment, str)
                    or len(str(recall_segment).strip()) == 0
                ):
                    matched_events_list.append("")
                    continue

                # Use API to find matching events
                matching_events = match_recall_to_events_sonnet(
                    client=client,
                    recall_segment=str(recall_segment),
                    story_events=story_events,
                    model=model,
                )

                # Store match result
                if matching_events:
                    matched_events_list.append(
                        ",".join(str(int(e)) for e in matching_events)
                    )
                    matched_count += 1
                else:
                    matched_events_list.append("")

                # Progress indicator
                if (idx + 1) % 5 == 0:
                    print(f"    Processed {idx + 1}/{total_segments} segments...")

                # Delay to avoid rate limits
                if delay > 0:
                    time.sleep(delay)
    
    # Assign all matches at once
    recall_df['recalled_events'] = matched_events_list

    # Clean up recalled_events column - ensure all are integers (no floats)
    def clean_matched_event(val):
        if pd.isna(val) or val == '':
            return ''
        if isinstance(val, (int, float)):
            if pd.isna(val):
                return ''
            # Always convert to int (no floats)
            return str(int(val))
        val_str = str(val)
        if val_str.lower() in ['nan', 'none', '']:
            return ''
        # If it's a comma-separated list, ensure each is an integer
        if ',' in val_str:
            parts = [x.strip() for x in val_str.split(',')]
            try:
                # Convert each part to int to remove decimals, then back to string
                int_parts = [str(int(float(x))) for x in parts if x and x.replace('.', '').replace('-', '').isdigit()]
                return ','.join(int_parts)
            except:
                return val_str
        # Single value - try to convert to int
        try:
            if val_str.replace('.', '').replace('-', '').isdigit():
                return str(int(float(val_str)))
        except:
            pass
        return val_str
    
    recall_df['recalled_events'] = recall_df['recalled_events'].apply(clean_matched_event)
    
    # Ensure correct column order: recalled_events first, then recall_in_temporal_order
    if 'recalled_events' in recall_df.columns and 'recall_in_temporal_order' in recall_df.columns:
        recall_df = recall_df[['recalled_events', 'recall_in_temporal_order']]
    
    # Save to output file
    if use_ollama_recall:
        method_suffix = "-ollama_" + _safe_filename_slug(_recall_ollama_model_tag())
    elif use_rmatch_recall:
        method_suffix = _rmatch_method_suffix()
    elif test_mode:
        method_suffix = "-test_mode"
    else:
        method_suffix = f"-api_{model}"
    try:
        if output_format.lower() == 'excel':
            output_file = output_path / f"{story_id}_rate-recall{method_suffix}{rated_edit_tail}.xlsx"
            
            # Check if file exists and is locked
            if output_file.exists():
                try:
                    # Try to read it first to check if it's locked
                    test_df = pd.read_excel(output_file, engine='openpyxl')
                except Exception as read_error:
                    error_msg = str(read_error).lower()
                    if 'locked' in error_msg or 'disturbed' in error_msg or 'body' in error_msg:
                        print(f"  Warning: Excel file is locked. Saving as CSV instead...")
                        # Fall back to CSV
                        output_file = output_path / f"{story_id}_rate-recall{method_suffix}{rated_edit_tail}.csv"
                        recall_df.to_csv(output_file, index=False, encoding='utf-8', na_rep='')
                        print(f"  Processed {total_segments} recall segments")
                        print(f"  Matched {matched_count} segments to story events")
                        print(f"  Saved to: {output_file} (CSV format - Excel file was locked)")
                        return True
            
            # Try to save as Excel
            try:
                recall_df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
            except Exception as excel_error:
                error_msg = str(excel_error).lower()
                if 'locked' in error_msg or 'disturbed' in error_msg or 'body' in error_msg:
                    print(f"  Warning: Could not save as Excel (file may be open). Saving as CSV instead...")
                    # Fall back to CSV
                    output_file = output_path / f"{story_id}_rate-recall{method_suffix}{rated_edit_tail}.csv"
                    recall_df.to_csv(output_file, index=False, encoding='utf-8', na_rep='')
                    print(f"  Processed {total_segments} recall segments")
                    print(f"  Matched {matched_count} segments to story events")
                    print(f"  Saved to: {output_file} (CSV format - Excel file was locked)")
                    return True
                else:
                    raise  # Re-raise if it's a different error
        else:  # CSV
            output_file = output_path / f"{story_id}_rate-recall{method_suffix}{rated_edit_tail}.csv"
            recall_df.to_csv(output_file, index=False, encoding='utf-8', na_rep='')
        
        print(f"  Processed {total_segments} recall segments")
        print(f"  Matched {matched_count} segments to story events")
        print(f"  Saved to: {output_file}")
        
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if 'locked' in error_msg or 'disturbed' in error_msg or 'body' in error_msg:
            print(f"  Error: File is locked or in use. Please close any Excel files and try again.")
            print(f"  Tip: Close {output_file} if it's open in Excel or another program")
        else:
            print(f"  Error saving recall file: {e}")
        return False


def process_all_subjects(
    story_dir: str = 'data/3_story_events',
    recall_dir: str = 'output/recall_parsed',
    output_dir: str = 'output/recall_rated',
    output_format: str = 'excel',
    model: str = MODEL_NAME,
    delay: float = 1.0,
    test_mode: bool = False,
    use_batch: bool = True
):
    """
    Process all subjects' recall files and match them to story events using Claude Sonnet 4.5.
    
    Args:
        story_dir: Directory containing story event files
        recall_dir: Directory containing parsed recall files
        output_dir: Directory to save rated recall files
        output_format: Output format ('excel' or 'csv')
        model: Claude model to use
        delay: Delay between API calls (seconds) to avoid rate limits (not used in batch mode)
        test_mode: If True, use test mode matching instead of API
        use_batch: If True, use batch processing (more efficient)
    """
    recall_path = Path(recall_dir)
    batch_item_id = os.environ.get('BATCH_ITEM_ID', None)

    if not recall_path.exists():
        msg = f"Error: Recall directory not found: {recall_dir}"
        print(msg)
        if batch_item_id:
            raise RuntimeError(msg)
        return

    # Find all parsed recall files: canonical ({item}_parsed.xlsx), method-suffixed
    # ({item}[_spell-...]_parsed[-method].xlsx), and user-edit variants thereof.
    parsed_name_re = re.compile(r"_parsed(?:[-_].*)?\.xlsx$", re.IGNORECASE)
    recall_files_set: set[Path] = {
        p for p in recall_path.glob("*.xlsx") if parsed_name_re.search(p.name)
    }
    recall_files = sorted(recall_files_set, key=lambda p: p.name)

    # Filter by BATCH_ITEM_ID if set (for single subject processing)
    if batch_item_id:
        filtered_files = []
        for recall_file in recall_files:
            item_id, _ed = parse_recall_parsed_path(recall_file)
            if item_id == batch_item_id:
                filtered_files.append(recall_file)
        recall_files = filtered_files
        if recall_files:
            print(f"Filtering by BATCH_ITEM_ID: {batch_item_id}")
        else:
            print(f"No recall files found matching BATCH_ITEM_ID: {batch_item_id}")

    # Filter by BATCH_INPUT_VARIANT if set: keep only files whose tail after item_id matches exactly.
    explicit_variant = os.environ.get("BATCH_INPUT_VARIANT")
    if explicit_variant is not None and recall_files:
        before = len(recall_files)
        kept = []
        for recall_file in recall_files:
            item_id, _ed = parse_recall_parsed_path(recall_file)
            if recall_file.stem == f"{item_id}{explicit_variant}":
                kept.append(recall_file)
        recall_files = kept
        print(
            f"Filtering by BATCH_INPUT_VARIANT={explicit_variant!r}: "
            f"{before} -> {len(recall_files)} file(s)"
        )

    if not recall_files:
        tail = f" matching BATCH_ITEM_ID={batch_item_id}" if batch_item_id else ""
        msg = (
            f"No parsed recall files found in {recall_dir}{tail}. "
            "Expected `<subject_id>_parsed.xlsx` or `<subject_id>_parsed_<user>-edit.xlsx`."
        )
        print(msg)
        if batch_item_id:
            raise RuntimeError(
                f"No parsed recall file for subject {batch_item_id!r} in {recall_dir}. "
                f"Add or run recall-parse so {batch_item_id}_parsed.xlsx (or an edit variant) exists."
            )
        return
    
    print(f"Found {len(recall_files)} recall files to process")
    print(f"Output format: {output_format}")
    print(f"Output directory: {output_dir}")
    if _recall_rating_use_ollama():
        print(
            "Mode: Ollama batch (RECALL_RATING_BACKEND, same JSON prompt as Claude API; "
            f"model={_recall_ollama_model_tag()!r})"
        )
    elif _recall_rating_use_rmatch():
        print(
            f"Mode: rMatch (PyPI Hugging Face matcher; model={_rmatch_model_name()!r}, "
            f"quant={(os.environ.get('RMATCH_QUANTIZATION') or '4bit').strip().lower()!r})"
        )
    elif test_mode:
        print(f"Mode: TEST MODE (simulated matching, no API calls)")
    else:
        print(f"Using model: {model}")
        if use_batch:
            print(f"Mode: BATCH PROCESSING (all segments processed in one API call per subject)")
        else:
            print(f"Mode: INDIVIDUAL PROCESSING (one API call per segment)")
            print(f"API call delay: {delay} seconds")
    print()
    
    processed_count = 0
    failed_count = 0
    
    for recall_file in recall_files:
        item_id, _ed = parse_recall_parsed_path(recall_file)

        print(f"Processing {recall_file.name} (item_id={item_id})...")

        success = process_subject(
            subj_id=item_id,
            story_dir=story_dir,
            recall_dir=recall_dir,
            output_dir=output_dir,
            output_format=output_format,
            model=model,
            delay=delay,
            test_mode=test_mode,
            use_batch=use_batch,
            recall_source=recall_file,
        )
        
        if success:
            processed_count += 1
        else:
            failed_count += 1
        
        print()
    
    print(f"Processing complete!")
    print(f"  Successfully processed: {processed_count} files")
    print(f"  Failed: {failed_count} files")

    if failed_count > 0:
        raise RuntimeError(f"{failed_count} file(s) failed to process")


if __name__ == "__main__":
    # Check if test mode is requested
    test_mode = os.getenv('TEST_MODE', '').lower() in ('1', 'true', 'yes')
    use_ollama_main = _recall_rating_use_ollama()
    use_rmatch_main = _recall_rating_use_rmatch()

    # If no API key and not explicitly in test mode, try test mode (Claude API only).
    if not use_ollama_main and not use_rmatch_main and not test_mode and not os.getenv('ANTHROPIC_API_KEY'):
        print("="*70)
        print("NOTE: ANTHROPIC_API_KEY not set")
        print("Running in TEST MODE (simulated matching)")
        print("For real API matching, set: export ANTHROPIC_API_KEY='your-key'")
        print("="*70)
        print()
        test_mode = True
    
    # Paths: honor env set by Flask batch/execute (pipeline input/output)
    story_dir = (os.environ.get("BATCH_STORY_EVENTS_DIR") or "").strip() or "data/3_story_events"
    recall_dir = (os.environ.get("BATCH_INPUT_DIR") or "").strip() or "output/recall_parsed"
    output_dir = (os.environ.get("BATCH_OUTPUT_DIR") or "").strip() or "output/recall_rated"

    # Process all subjects
    # Default to Excel format, batch processing; Anthropic model resolved from env (set by launcher).
    resolved_model = _resolve_recall_rating_model()
    if resolved_model != MODEL_NAME:
        print(f"Using Anthropic model (from RECALL_RATING_MODEL): {resolved_model}")
    try:
        process_all_subjects(
            story_dir=story_dir,
            recall_dir=recall_dir,
            output_dir=output_dir,
            output_format='excel',
            model=resolved_model,
            delay=1.0,  # Not used in batch mode
            test_mode=test_mode,
            use_batch=True  # Use batch processing for efficiency
        )
    except Exception as e:
        print(f"Error processing files: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
