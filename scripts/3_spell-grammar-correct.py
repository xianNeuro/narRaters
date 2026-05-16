#!/usr/bin/env python3
"""
Script to perform spelling and grammar correction on narrative recall data.

By default reads individual recall text files from data/5_recall_texts/ (one .txt
per subject), performs conservative spell/grammar correction, and outputs
corrected text files (rule-based: ``{id}.txt``; Ollama Gemma:
``{id}_spell-ollama_*.txt``). Can also read from a summary Excel file (e.g. summary_*.xlsx)
if the input path is an Excel file or a directory containing only .xlsx.

Local Gemma-4 (no cloud API billing):
  * ``--method gemma-ollama`` — Ollama tag ``gemma4:e4b`` by default (override ``--ollama-model`` /
    ``SPELL_GRAM_OLLAMA_MODEL``). Requires Ollama running; set ``OLLAMA_HOST`` if not localhost:11434.

Environment (optional): SPELL_GRAM_METHOD, SPELL_GRAM_PROMPT_FILE, SPELL_GRAM_OLLAMA_MODEL.
"""

import argparse
import pandas as pd
import os
import sys
from pathlib import Path
import re


def _software_package_root() -> Path:
    d = Path(__file__).resolve().parent
    return d.parent if d.name == "scripts" else d


_pr = _software_package_root()
if str(_pr) not in sys.path:
    sys.path.insert(0, str(_pr))


from spellchecker import SpellChecker


def _filename_slug(s: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (s or "").strip()).strip("_")
    return (slug or "default")[:max_len]


def spell_corrected_output_names(
    subject_id: str,
    method: str,
    *,
    ollama_model=None,
):
    """
    Return (output_stem, header_line) for the corrected recall .txt file.

    Rule-based output stays ``{subject_id}.txt`` (first line ``{subject_id}.txt``).
    Ollama Gemma writes ``{subject_id}_spell-ollama_{slug}.txt`` so multiple methods can coexist.
    """
    m = (method or "rules").strip().lower()
    if m == "gemma-ollama":
        tag = (ollama_model or os.environ.get("SPELL_GRAM_OLLAMA_MODEL") or "gemma4:e4b").strip()
        stem = f"{subject_id}_spell-ollama_{_filename_slug(tag)}"
        return stem, f"{stem}.txt"
    return subject_id, f"{subject_id}.txt"


# ==============================
# FILLER WORD REMOVAL
# ==============================

FILLER_WORDS_RE = re.compile(
    r'(?<!\d\s)(?<!\d)\b(?:uh-huh|mm-hmm|um|umm|ummm|uh|uhh|uhm|ah|ahh|er|erm|err|hmm|hm|hmmm|mm|mmm|mhm)\b',
    re.IGNORECASE
)


def _remove_filler_words(text):
    """Remove oral filler words (um, uh, ah, etc.) and clean up surrounding punctuation."""
    if not text:
        return text

    prev = None
    result = text

    while result != prev:
        prev = result

        # Filler at start of text: "um, text" or "um text"
        result = re.sub(
            r'^\s*' + FILLER_WORDS_RE.pattern + r'\s*,?\s*',
            '', result, flags=re.IGNORECASE
        )

        # Filler after pronoun or conjunction with surrounding commas:
        # "I, um, don't" → "I don't";  "and, um, she" → "and she"
        result = re.sub(
            r'(\b(?:I|he|she|it|we|they|you|and|but|or|so|because|then|that)\b)\s*,\s*'
            + FILLER_WORDS_RE.pattern + r'\s*,?\s*',
            r'\1 ', result, flags=re.IGNORECASE
        )

        # Filler between commas: "text, um, text" → "text, text"
        result = re.sub(
            r',\s*' + FILLER_WORDS_RE.pattern + r'\s*,',
            ',', result, flags=re.IGNORECASE
        )

        # Filler after comma (no comma after): "text, um text" → "text, text"
        result = re.sub(
            r',\s*' + FILLER_WORDS_RE.pattern + r'\s+',
            ', ', result, flags=re.IGNORECASE
        )

        # Filler before comma: "text um, text" → "text, text"
        result = re.sub(
            r'\s+' + FILLER_WORDS_RE.pattern + r'\s*,',
            ',', result, flags=re.IGNORECASE
        )

        # Standalone filler between words: "text um text" → "text text"
        result = re.sub(
            r'\s+' + FILLER_WORDS_RE.pattern + r'\s+',
            ' ', result, flags=re.IGNORECASE
        )

        # Filler at end of text
        result = re.sub(
            r'\s*,?\s*' + FILLER_WORDS_RE.pattern + r'\s*$',
            '', result, flags=re.IGNORECASE
        )

        # Clean up artifacts
        result = re.sub(r',\s*,', ',', result)
        result = re.sub(r'\s+', ' ', result)
        result = result.strip()

    return result


# ==============================
# RUN-ON SENTENCE CORRECTION
# ==============================

_COMMON_PAST_VERBS = (
    r'(?:brought|went|came|saw|heard|told|took|made|got|had|was|were|said|asked'
    r'|decided|noticed|realized|found|left|arrived|started|began|tried|wanted'
    r'|needed|knew|thought|felt|walked|ran|looked|turned|called|grabbed|held'
    r'|gave|put|sat|stood|watched|waited|stayed|became|opened|closed|pulled'
    r'|pushed|picked|threw|caught|hit|broke|cut|ate|drank|slept|woke|wore'
    r'|drove|flew|read|wrote|played|fought|died|lived|loved|hated|feared'
    r'|hoped|wished|believed|remembered|forgot|learned|showed|used|kept'
    r'|let|helped|stopped|moved|followed)'
)


def _fix_run_on_sentences(text):
    """Fix run-on sentences by inserting sentence breaks at natural boundaries.

    Targets oral transcript patterns where clauses are connected with 'and'
    and commas without sentence-ending punctuation.
    """
    if not text or len(text.split()) < 25:
        return text

    # Only process if there are long stretches without sentence breaks
    segments = re.split(r'[.!?]\s+', text)
    max_segment_words = max((len(s.split()) for s in segments if s.strip()), default=0)
    if max_segment_words < 25:
        return text

    # Collect candidate break points
    candidates = []

    # Strong temporal: ", and after [subject/word]"
    for m in re.finditer(r',\s+and\s+(after\s+)', text, re.IGNORECASE):
        candidates.append({
            'cut': m.start(), 'new': m.start(1),
            'prefix': 'And ', 'min_words': 10, 'priority': 1
        })

    # Strong temporal: ", and the next [time/day/...]"
    for m in re.finditer(r',\s+and\s+(the\s+next\s+)', text, re.IGNORECASE):
        candidates.append({
            'cut': m.start(), 'new': m.start(1),
            'prefix': 'And ', 'min_words': 8, 'priority': 1
        })

    # Temporal: ", and [later/eventually/finally/suddenly]"
    for m in re.finditer(r',\s+and\s+((?:later|eventually|finally|suddenly)\b)', text, re.IGNORECASE):
        candidates.append({
            'cut': m.start(), 'new': m.start(1),
            'prefix': 'And ', 'min_words': 12, 'priority': 2
        })

    # Topic resumption: "anyways" or "anyway"
    for m in re.finditer(r'(,?\s+)(anyways?\b)', text, re.IGNORECASE):
        candidates.append({
            'cut': m.start(), 'new': m.start(2),
            'prefix': '', 'min_words': 8, 'priority': 1
        })

    # Subject change: proper noun + past tense verb (case-sensitive for proper nouns)
    for m in re.finditer(
        r',\s+(?:and\s+)?([A-Z][a-z]{2,}\s+' + _COMMON_PAST_VERBS + r')',
        text
    ):
        candidates.append({
            'cut': m.start(), 'new': m.start(1),
            'prefix': '', 'min_words': 18, 'priority': 3
        })

    # Fallback for very long sentences: ", and [pronoun] [verb]"
    for m in re.finditer(r',\s+and\s+((?:he|she|they|we|I|you)\s+\w+)', text, re.IGNORECASE):
        candidates.append({
            'cut': m.start(), 'new': m.start(1),
            'prefix': 'And ', 'min_words': 35, 'priority': 4
        })

    if not candidates:
        return text

    # Sort by position, then priority
    candidates.sort(key=lambda x: (x['cut'], x['priority']))

    # Remove overlapping candidates (keep higher priority at same position)
    filtered = []
    for cand in candidates:
        if filtered and cand['cut'] <= filtered[-1].get('new', 0):
            if cand['priority'] < filtered[-1]['priority']:
                filtered[-1] = cand
            continue
        filtered.append(cand)

    # Apply breaks left to right based on word count since last break
    applied = []
    current_start = 0

    for cand in filtered:
        if cand['cut'] < current_start:
            continue
        words = len(text[current_start:cand['cut']].split())
        if words >= cand['min_words']:
            applied.append(cand)
            current_start = cand['new']

    if not applied:
        return text

    # Build output
    parts = []
    last_pos = 0
    for brk in applied:
        segment = text[last_pos:brk['cut']].rstrip().rstrip(',')
        parts.append(segment)
        last_pos = brk['new']

    remaining = text[last_pos:].strip()
    parts.append(remaining)

    # Join with sentence breaks, applying prefix and capitalization
    result = parts[0]
    for i, part in enumerate(parts[1:]):
        brk = applied[i]
        if not part:
            continue
        if brk['prefix']:
            result += '. ' + brk['prefix'] + part
        else:
            result += '. ' + part[0].upper() + part[1:]

    return result


def _resolve_prompt_path(prompt_file):
    """Resolve spell/grammar prompt path relative to CWD or this script's ``scripts/prompt/`` tree."""
    p = Path(prompt_file)
    if p.is_file():
        return p
    alt = Path(__file__).resolve().parent / p
    if alt.is_file():
        return alt
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


def _maybe_strip_subject_header(text):
    """If the first line looks like a filename (e.g. sub-01_1234.txt), drop it."""
    lines = text.split("\n", 1)
    if len(lines) < 2:
        return text
    first = lines[0].strip()
    if re.match(r"^[\w\-]+\.txt$", first, re.IGNORECASE):
        return lines[1].lstrip("\n")
    return text


def correct_text_gemma_ollama(
    text,
    *,
    prompt_file,
    ollama_model,
    remove_fillers=True,
):
    """
    Spell/grammar cleanup using Gemma 4 E4B served by Ollama (local HTTP).
    """
    if pd.isna(text) or not isinstance(text, str) or len(text.strip()) == 0:
        return text

    body = _maybe_strip_subject_header(text.strip())
    if remove_fillers:
        body = _remove_filler_words(body)

    instruction = _resolve_prompt_path(prompt_file).read_text(encoding="utf-8").strip()
    user_content = f"{instruction}\n\n---\n\n{body}"
    messages = [{"role": "user", "content": user_content}]

    from helpers.ollama_gemma_e4b import ollama_chat

    tag = (ollama_model or os.environ.get("SPELL_GRAM_OLLAMA_MODEL") or "gemma4:e4b").strip()
    gen = ollama_chat(
        messages,
        model_tag=tag,
        temperature=0.0,
        num_ctx=32768,
        num_predict=8192,
        think=False,
    )
    gen = gen.strip()
    for prefix in ("model:", "assistant:", "<start_of_turn>model"):
        if gen.lower().startswith(prefix.lower()):
            gen = gen[len(prefix) :].lstrip()
    return gen.strip()


def correct_text(
    text,
    remove_fillers=True,
    method="rules",
    prompt_file=None,
    ollama_model=None,
):
    """
    Perform conservative spelling and grammar correction on text.
    Only fixes obvious spelling mistakes and clear grammatical errors.
    Does NOT rewrite, summarize, or change style/tone.

    With method='gemma-ollama', uses Ollama (see correct_text_gemma_ollama).

    Args:
        text: Input text string
        remove_fillers: If True (default), remove oral filler words (um, uh, ah, etc.)
        method: 'rules' (default) or 'gemma-ollama' (Ollama E4B)
        prompt_file: Path to instructions for gemma-ollama (default: scripts/prompt/spell_gram.txt)
        ollama_model: Ollama model tag for method 'gemma-ollama' (default: gemma4:e4b)

    Returns:
        Corrected text string
    """
    if pd.isna(text) or not isinstance(text, str) or len(text.strip()) == 0:
        return text

    if method == "gemma-ollama":
        pf = prompt_file or "prompt/spell_gram.txt"
        om = ollama_model or os.environ.get("SPELL_GRAM_OLLAMA_MODEL") or "gemma4:e4b"
        return correct_text_gemma_ollama(
            text,
            prompt_file=pf,
            ollama_model=om,
            remove_fillers=remove_fillers,
        )

    corrected_text = text

    # Step 0a: Remove filler words (if enabled)
    if remove_fillers:
        corrected_text = _remove_filler_words(corrected_text)

    # Step 0b: Fix run-on sentences
    corrected_text = _fix_run_on_sentences(corrected_text)
    
    # Protect abbreviations from corruption - periods in these are NOT sentence endings
    _ph = {'pm': '\uE000PM\uE001', 'am': '\uE000AM\uE001', 'eg': '\uE001EG\uE001',
           'ie': '\uE001IE\uE001', 'ps': '\uE001PS\uE001', 'etc': '\uE001ETC\uE001'}
    corrected_text = re.sub(r'\b(\d{1,2})\s*p\.\s*m\.', r'\1 ' + _ph['pm'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\b(\d{1,2})\s*a\.\s*m\.', r'\1 ' + _ph['am'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\b(\d{1,2})\s*p\.m\.', r'\1 ' + _ph['pm'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\b(\d{1,2})\s*a\.m\.', r'\1 ' + _ph['am'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\be\.g\.', _ph['eg'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bi\.e\.', _ph['ie'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bp\.s\.', _ph['ps'], corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\betc\.', _ph['etc'], corrected_text, flags=re.IGNORECASE)
    
    # Step 1: Fix common contraction errors first
    corrected_text = re.sub(r'\bcould\'t\b', "couldn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bwould\'t\b', "wouldn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bshould\'t\b', "shouldn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bcan\'t\b', "can't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bwon\'t\b', "won't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bisn\'t\b', "isn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\baren\'t\b', "aren't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bwasn\'t\b', "wasn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bweren\'t\b', "weren't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bdon\'t\b', "don't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bdidn\'t\b', "didn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bdoesn\'t\b', "doesn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bhaven\'t\b', "haven't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bhasn\'t\b', "hasn't", corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bhadn\'t\b', "hadn't", corrected_text, flags=re.IGNORECASE)
    
    # Step 2: Fix obvious grammar errors - fix "which i a," first before general "i" -> "I"
    # Fix "which i a," -> "which I am trying" (remove the comma, add "trying")
    # The original "which i a, trying" should become "which I am trying" (no comma)
    corrected_text = re.sub(r'\bwhich i a\s*,\s*trying', 'which I am trying', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bwhich i a\s*,', 'which I am', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bwhich i a\s+', 'which I am ', corrected_text, flags=re.IGNORECASE)
    # Fix other "i a," patterns
    corrected_text = re.sub(r'\bi\s+a\s*,', 'I am,', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bi\s+a\s+', 'I am ', corrected_text, flags=re.IGNORECASE)
    
    # Step 3: Fix standalone lowercase "i" pronoun to "I"
    corrected_text = re.sub(r'\bi\b', 'I', corrected_text)
    
    # Step 4: Capitalize first letter of sentences (but NOT after abbreviations like p.m., a.m.)
    if corrected_text and corrected_text[0].islower() and corrected_text[0].isalpha():
        corrected_text = corrected_text[0].upper() + corrected_text[1:]
    # Only capitalize after ACTUAL sentence endings - NOT after abbreviation periods (p.s., i.e., e.g., etc.)
    def cap_after_sentence(m):
        punct, space, letter = m.group(1), m.group(2), m.group(3)
        start = max(0, m.start() - 60)
        before = corrected_text[start:m.start()]
        if re.search(r'(?:p\.m\.?|a\.m\.?|e\.g\.?|i\.e\.?|p\.s\.?|etc\.?|dr\.|mr\.|mrs\.|ms\.|no\.|vol\.|fig\.|ph\.d|vs\.?)[\.\s]*$', before, re.IGNORECASE):
            return m.group(0)
        if any(placeholder in before for placeholder in _ph.values()):
            return m.group(0)
        return punct + space + letter.upper()
    corrected_text = re.sub(r'([.!?])(\s+)([a-z])', cap_after_sentence, corrected_text)
    
    # Step 5: Fix common context errors and word combinations
    corrected_text = re.sub(r'\bto his moth\b', 'to his mouth', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bto her moth\b', 'to her mouth', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bto my moth\b', 'to my mouth', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bto your moth\b', 'to your mouth', corrected_text, flags=re.IGNORECASE)
    # Removed: walk up→wake up, cross road→crossroad — these clobber legitimate English.

    # Fix "which i a," -> "which I am," (fix the incomplete phrase - do this BEFORE fixing "i" to "I")
    # This needs to happen early, before the general "i" -> "I" replacement
    
    # Fix common spelling errors
    corrected_text = re.sub(r'\bseperate\b', 'separate', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\brecieve\b', 'receive', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\boccured\b', 'occurred', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\boccurence\b', 'occurrence', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bdefinately\b', 'definitely', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bneccessary\b', 'necessary', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\baccross\b', 'across', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bexistance\b', 'existence', corrected_text, flags=re.IGNORECASE)
    
    # Fix misplaced periods in words (e.g., "hous.e" -> "house") but NOT abbreviations (p.m., a.m.)
    corrected_text = re.sub(r'(\w{2,})\.(\w+)(\s|\.|,|!|\?|$)', r'\1\2\3', corrected_text)
    # Fix missing spaces between words (e.g., "hisbed" -> "his bed")
    corrected_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', corrected_text)  # Add space between lowercase and uppercase
    
    # Fix punctuation: ensure proper spacing after periods, commas, etc. (only if missing)
    # But do NOT add space inside abbreviations like p.m., a.m., e.g., i.e.
    def add_space_after_punct(m):
        if m.group(1) == '.' and m.start() > 0:
            before_period = corrected_text[m.start() - 1]
            if before_period == '.':
                return m.group(0)
            if m.start() + 2 <= len(corrected_text):
                after_period = corrected_text[m.start() + 1]
                if before_period.isalpha() and after_period.isalpha():
                    return m.group(0)
        return m.group(1) + ' ' + m.group(2)
    corrected_text = re.sub(r'([.!?])([A-Za-z])', add_space_after_punct, corrected_text)
    corrected_text = re.sub(r'([,;:])([A-Za-z])', r'\1 \2', corrected_text)  # Add space after punctuation if missing
    corrected_text = re.sub(r'\s+([,.!?;:])', r'\1', corrected_text)  # Remove space before punctuation
    corrected_text = re.sub(r'\s+', ' ', corrected_text)  # Normalize multiple spaces to single space
    
    # Fix double punctuation
    corrected_text = re.sub(r'([.!?])\1+', r'\1', corrected_text)
    corrected_text = re.sub(r'([,;:])\1+', r'\1', corrected_text)
    
    # Fix missing capitalization after sentence endings (abbreviation-aware)
    corrected_text = re.sub(r'([.!?])(\s+)([a-z])', cap_after_sentence, corrected_text)
    
    # Step 6: Comprehensive spelling check using pyspellchecker
    spell = SpellChecker()
    
    # Words to never correct (valid words that spell-checkers get wrong)
    WORD_WHITELIST = {
        'taser', 'tasers', 'usb', 'storylines', 'immersive', 'roleplaying', 'role-playing',
        'live-action', 'waterproof', 'fireproof', 'memos', 'stimuli', 'fictional',
        'larp', 'larper', 'larping', 'scifi', 'sci-fi',
        'texted', 'texting', 'texts',  # verb "to text" (message someone) - wrongly "corrected" to tested
    }
    
    proper_nouns = ['Durchard', 'Duchard', 'Orchard', 'Heart', 'Hearts', 'Heartland', 'Heartlands', 
                    'Peeps', 'Mary', 'Ann', 'Phenersis', 'Phrenesis', 'Nona', 'Nora', 'Irascile',
                    'Taser', 'Tasers', 'Nico', 'Grantham']
    
    # Hyphenated compounds and abbreviations to never "correct" (spell-checker splits on hyphen
    # and wrongly corrects e.g. "sci" in "sci-fi" to "ski"). Include common terms.
    HYPHENATED_WHITELIST = {
        'sci-fi', 'high-tech', 'low-tech', 'state-of-the-art', 'run-of-the-mill',
        'co-worker', 'co-workers', 'self-esteem', 'self-aware', 'self-conscious',
        'e-mail', 'email', 'on-line', 'online', 'off-line', 'offline',
        'well-known', 'well-being', 'long-term', 'short-term', 'multi-year',
        'non-fiction', 'sci-fi', 'sci‑fi',
        't-shirt', 'x-ray', 'x-rays', 'u-turn', 'a-level', 'b-grade',
        'pre-war', 'post-war', 'mid-week', 'semi-automatic',
        'first-hand', 'second-hand', 'third-party',
        'live-action', 'role-playing',
    }
    
    def is_part_of_whitelisted_hyphenated(text, start, end, word):
        """Check if this word is part of a hyphenated compound that we should preserve."""
        # Look for hyphenated compound containing this word (before or after hyphen)
        if start > 0 and start < len(text) and text[start - 1] == '-':
            # Word is after hyphen, e.g. "fi" in "sci-fi"
            pre_start = start - 2
            while pre_start >= 0 and text[pre_start].isalnum():
                pre_start -= 1
            pre_start += 1
            before_hyphen = text[pre_start:start - 1]
            compound = f"{before_hyphen}-{word}".lower()
            if compound in HYPHENATED_WHITELIST:
                return True
        if end < len(text) and text[end] == '-':
            # Word is before hyphen, e.g. "sci" in "sci-fi"
            post_end = end + 1
            while post_end < len(text) and text[post_end].isalnum():
                post_end += 1
            after_hyphen = text[end + 1:post_end]
            compound = f"{word}-{after_hyphen}".lower()
            if compound in HYPHENATED_WHITELIST:
                return True
        return False
    
    # Find all words including contractions (words with apostrophes)
    word_positions = []
    for match in re.finditer(r'\b[\w\']+\b', corrected_text):
        word_positions.append((match.start(), match.end(), match.group()))
    
    # Roman numerals (I, II, III, IV, V, etc.) - never "correct" these
    ROMAN_RE = re.compile(r'^M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$', re.IGNORECASE)
    def is_roman_numeral(s):
        if not s or not all(c in 'IVXLCDM' for c in s.upper()):
            return False
        return bool(ROMAN_RE.match(s.upper()))
    
    for start, end, word in reversed(word_positions):
        if word.lower() in spell or word.isdigit() or word == 'I':
            continue
        
        if word.lower() in WORD_WHITELIST:
            continue
        
        if is_roman_numeral(word):
            continue
        
        if len(word) >= 2 and word.isupper():
            continue
        
        # Skip words that are part of whitelisted hyphenated compounds
        if is_part_of_whitelisted_hyphenated(corrected_text, start, end, word):
            continue
        
        # Skip very short words (but check common contractions)
        if len(word) <= 2 and word.lower() not in ["i'm", "i'd", "i've", "i'll", "it's", "we're", "you're", "he's", "she's", "they're"]:
            continue
        
        # Skip proper nouns
        if word in proper_nouns or word in [pn.lower() for pn in proper_nouns]:
            continue
        
        # Skip capitalized words that look like proper nouns (first letter capitalized, not common words)
        if word[0].isupper() and len(word) > 3 and word.lower() not in spell:
            continue
        
        # Get the most likely correction
        correction = spell.correction(word)
        
        # Apply correction if valid
        if (correction and 
            correction.lower() != word.lower() and 
            correction.lower() in spell and
            abs(len(correction) - len(word)) <= 4):
            # Don't change plural to singular (storylines->storyline is often wrong)
            if word.endswith('s') and correction.lower() == word[:-1].lower():
                continue
            # Don't change adjective to verb (immersive->immerse changes part of speech)
            if word.endswith('ive') and not correction.endswith('ive') and len(correction) < len(word) - 2:
                continue
            # Preserve capitalization
            if word[0].isupper():
                correction = correction.capitalize()
            # Apply the correction
            corrected_text = corrected_text[:start] + correction + corrected_text[end:]
    
    # Step 7: Try LanguageTool for additional grammar fixes (if available)
    try:
        import language_tool_python
        tool = language_tool_python.LanguageTool('en-US')
        matches = tool.check(corrected_text)
        
        # Apply corrections in reverse order
        sorted_matches = sorted(matches, key=lambda x: x.offset, reverse=True)
        
        for match in sorted_matches:
            category = match.category
            rule_id = match.ruleId
            
            skip_categories = [
                'STYLE', 'TYPOGRAPHY', 'REDUNDANCY', 
                'COLLOQUIALISMS', 'COMPOUNDING', 'SEMANTICS'
            ]
            
            skip_rules = [
                'EN_QUOTES', 'WHITESPACE_RULE', 'COMMA_PARENTHESIS_WHITESPACE',
                'DOUBLE_PUNCTUATION', 'PLURAL_VERB', 'SINGULAR_PLURAL',
                'MORFOLOGIK_RULE', 'UPPERCASE_SENTENCE_START'
            ]
            
            if category in skip_categories or any(rule_id.startswith(rule) for rule in skip_rules):
                continue
            
            if len(match.replacements) >= 1:
                replacement = match.replacements[0]
                original_segment = corrected_text[match.offset:match.offset + match.errorLength]
                
                orig_lower = original_segment.lower().strip()
                repl_lower = replacement.lower().strip()
                
                if orig_lower in WORD_WHITELIST or orig_lower.upper() == orig_lower:
                    continue
                if is_roman_numeral(orig_lower):
                    continue
                if orig_lower.endswith('s') and repl_lower == orig_lower[:-1]:
                    continue
                if orig_lower.endswith('ive') and not repl_lower.endswith('ive') and len(repl_lower) < len(orig_lower) - 2:
                    continue
                if len(original_segment) >= 2 and original_segment.isupper():
                    continue
                
                if abs(len(replacement) - len(original_segment)) <= 10 and len(original_segment) > 0:
                    if len(replacement) <= len(original_segment) + 5:
                        start_idx = match.offset
                        end_idx = start_idx + match.errorLength
                        corrected_text = corrected_text[:start_idx] + replacement + corrected_text[end_idx:]
        
        tool.close()
    except Exception as e:
        # LanguageTool not available, continue with rule-based corrections
        pass
    
    # Step 8: Fix common title abbreviations
    corrected_text = re.sub(r'\bdr\s+peeps\b', 'Dr. Peeps', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bdr\s+([A-Z])', r'Dr. \1', corrected_text)
    
    # Step 9: Final cleanup - ensure proper spacing and punctuation
    # Fix "word. letter." patterns (e.g., "house. e." -> "house.")
    corrected_text = re.sub(r'(\w+)\.\s*([a-z])\s*\.', r'\1.', corrected_text)
    corrected_text = re.sub(r'\.\s+([a-z])\s*\.', r'.', corrected_text)
    
    # Restore protected abbreviations
    corrected_text = corrected_text.replace(_ph['pm'], 'p.m.')
    corrected_text = corrected_text.replace(_ph['am'], 'a.m.')
    corrected_text = corrected_text.replace(_ph['eg'], 'e.g.')
    corrected_text = corrected_text.replace(_ph['ie'], 'i.e.')
    corrected_text = corrected_text.replace(_ph['ps'], 'p.s.')
    corrected_text = corrected_text.replace(_ph['etc'], 'etc.')
    corrected_text = re.sub(r'\b(\d{1,2})\s+pm\b', r'\1 p.m.', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\b(\d{1,2})\s+am\b', r'\1 a.m.', corrected_text, flags=re.IGNORECASE)
    
    # Fix specific common errors
    corrected_text = re.sub(r'\bback to e\.', 'back to me.', corrected_text, flags=re.IGNORECASE)
    # Removed: hissed→his bed — overfit to one stimulus, corrupts the verb "hissed".
    corrected_text = re.sub(r'\bhisbed\b', 'his bed', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bwows\s+bringing', 'wow. Bringing', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bI remember There\b', 'I remember there', corrected_text)
    corrected_text = re.sub(r'\bI remained quite\.', 'I remained quiet.', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bI though\b', 'I thought', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'\bHe offered be\b', 'He offered me', corrected_text, flags=re.IGNORECASE)
    
    # Fix missing capitalization after sentence endings (again, in case it was missed)
    corrected_text = re.sub(r'([.!?])(\s+)([a-z])', cap_after_sentence, corrected_text)
    
    # Normalize multiple spaces to single space
    corrected_text = re.sub(r'\s+', ' ', corrected_text)
    # Ensure space after sentence-ending punctuation if missing (but NOT inside
    # abbreviations like e.g., i.e., p.s., and NOT inside ellipses "...")
    def add_space_if_not_abbrev(m):
        punct, letter = m.group(1), m.group(2)
        if punct != '.':
            return punct + ' ' + letter
        if m.start() > 0:
            before = corrected_text[m.start() - 1]
            # Don't add space inside ellipses (consecutive periods)
            if before == '.':
                return m.group(0)
            if m.end() < len(corrected_text):
                after_next = corrected_text[m.end()] if m.end() < len(corrected_text) else ''
                if before.isalpha() and after_next in ('.', ','):
                    return m.group(0)
        return punct + ' ' + letter
    corrected_text = re.sub(r'([.!?])([A-Za-z])', add_space_if_not_abbrev, corrected_text)
    # Remove space before punctuation
    corrected_text = re.sub(r'\s+([,.!?;:])', r'\1', corrected_text)
    
    # Step 10: Trailing punctuation cleanup
    corrected_text = corrected_text.rstrip()
    while corrected_text and corrected_text[-1] in ',;:':
        corrected_text = corrected_text[:-1].rstrip()
    if corrected_text and corrected_text[-1] not in '.!?"\'':
        corrected_text += '.'
    
    # Trim whitespace
    corrected_text = corrected_text.strip()
    
    return corrected_text


def process_recall_data(
    excel_path,
    sheet_name='all',
    output_dir='output/recall_corrected',
    remove_fillers=True,
    method='rules',
    prompt_file=None,
    ollama_model=None,
):
    """
    Read Excel file, process recall data, and output corrected text files.
    
    Args:
        excel_path: Path to the Excel file
        sheet_name: Name of the sheet to read (default: 'all')
        output_dir: Directory to save corrected text files
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Read Excel file
    print(f"Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    # Check if required columns exist
    required_cols = ['sub', 'ID', 'recall']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    print(f"Found {len(df)} rows in the Excel file")
    
    # Check for BATCH_ITEM_ID filter (for single subject processing)
    batch_item_id = os.environ.get('BATCH_ITEM_ID', None)
    if batch_item_id:
        print(f"Filtering by BATCH_ITEM_ID: {batch_item_id}")
    
    # Process all subjects
    print(f"Processing all {len(df)} subjects...")
    
    # Process each row
    processed_count = 0
    skipped_count = 0
    
    for idx, row in df.iterrows():
        # Get subject ID (combination of sub and ID columns)
        sub = row['sub']
        sub_id = row['ID']
        
        # Skip if either sub or ID is missing
        if pd.isna(sub) or pd.isna(sub_id):
            print(f"Skipping row {idx}: Missing sub or ID")
            skipped_count += 1
            continue
        
        # Convert to string and format
        sub_str = str(int(sub)) if isinstance(sub, (int, float)) else str(sub).strip()
        sub_id_str = str(int(sub_id)) if isinstance(sub_id, (int, float)) else str(sub_id).strip()
        
        # Create filename: subN_XXXX format
        if sub_str.startswith('sub'):
            # If sub already starts with 'sub', use it directly
            filename_base = f"{sub_str}_{sub_id_str}"
        else:
            # Otherwise, add 'sub' prefix
            filename_base = f"sub{sub_str}_{sub_id_str}"
        
        # Filter by BATCH_ITEM_ID if set
        if batch_item_id and filename_base != batch_item_id:
            skipped_count += 1
            continue
        
        # Get recall text
        recall_text = row['recall']
        
        # Skip if recall is empty or NaN
        if pd.isna(recall_text) or (isinstance(recall_text, str) and len(recall_text.strip()) == 0):
            print(f"Skipping row {idx}: No recall data")
            skipped_count += 1
            continue
        
        # Convert to string and clean up quotes if present
        recall_text = str(recall_text)
        # Remove surrounding quotes if present
        if recall_text.startswith('"') and recall_text.endswith('"'):
            recall_text = recall_text[1:-1]
        if recall_text.startswith("'") and recall_text.endswith("'"):
            recall_text = recall_text[1:-1]
        
        # Perform spell/grammar correction
        print(f"Processing {filename_base}...")
        corrected_text = correct_text(
            recall_text,
            remove_fillers=remove_fillers,
            method=method,
            prompt_file=prompt_file,
            ollama_model=ollama_model,
        )
        
        out_stem, header_line = spell_corrected_output_names(
            filename_base,
            method,
            ollama_model=ollama_model,
        )
        output_file = output_path / f"{out_stem}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{header_line}\n")
            f.write(corrected_text)
        
        processed_count += 1
        print(f"  Saved to {output_file}")
    
    print(f"\nProcessing complete!")
    print(f"  Processed: {processed_count} files")
    print(f"  Skipped: {skipped_count} rows")
    print(f"  Output directory: {output_path.absolute()}")


def process_recall_text_dir(
    input_dir,
    output_dir='output/recall_corrected',
    remove_fillers=True,
    method='rules',
    prompt_file=None,
    ollama_model=None,
):
    """
    Read .txt files from a directory (one file per subject), correct each, and
    write to output_dir. Subject ID is the file stem (e.g. subN_XXXX.txt -> subN_XXXX).
    
    Args:
        input_dir: Path to directory containing .txt recall files
        output_dir: Directory to save corrected text files
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists() or not input_path.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    txt_files = sorted(input_path.glob('*.txt'))
    # Exclude user-edit variants and prior spell-method outputs as inputs
    txt_files = [f for f in txt_files if not re.search(r'_\w+-edit\.', f.name)]
    txt_files = [f for f in txt_files if '_spell-' not in f.name]

    batch_item_id = os.environ.get('BATCH_ITEM_ID', None)
    if batch_item_id:
        txt_files = [f for f in txt_files if f.stem == batch_item_id]
        print(f"Filtering by BATCH_ITEM_ID: {batch_item_id} -> {len(txt_files)} file(s)")

    explicit_variant = os.environ.get('BATCH_INPUT_VARIANT')
    if explicit_variant is not None and batch_item_id:
        before = len(txt_files)
        target_stem = f"{batch_item_id}{explicit_variant}"
        txt_files = [f for f in txt_files if f.stem == target_stem]
        print(
            f"Filtering by BATCH_INPUT_VARIANT={explicit_variant!r}: "
            f"{before} -> {len(txt_files)} file(s)"
        )

    print(f"Found {len(txt_files)} .txt file(s) in {input_path}")
    
    processed_count = 0
    for file_path in txt_files:
        subject_id = file_path.stem
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                recall_text = f.read()
        except Exception as e:
            print(f"Skipping {file_path.name}: {e}")
            continue
        
        if not recall_text.strip():
            print(f"Skipping {file_path.name}: empty file")
            continue
        
        print(f"Processing {subject_id}...")
        corrected_text = correct_text(
            recall_text,
            remove_fillers=remove_fillers,
            method=method,
            prompt_file=prompt_file,
            ollama_model=ollama_model,
        )
        
        out_stem, header_line = spell_corrected_output_names(
            subject_id,
            method,
            ollama_model=ollama_model,
        )
        output_file = output_path / f"{out_stem}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{header_line}\n")
            f.write(corrected_text)
        
        processed_count += 1
        print(f"  Saved to {output_file}")
    
    print(f"\nProcessing complete!")
    print(f"  Processed: {processed_count} files")
    print(f"  Output directory: {output_path.absolute()}")


def process_recall_text_file(
    input_file,
    output_dir='output/recall_corrected',
    remove_fillers=True,
    method='rules',
    prompt_file=None,
    ollama_model=None,
):
    """Correct a single recall .txt file and write output/recall_corrected/{stem}.txt."""
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    subject_id = input_path.stem
    recall_text = input_path.read_text(encoding='utf-8')

    if not recall_text.strip():
        print(f"Skipping {input_path.name}: empty file")
        return

    print(f"Processing {subject_id} ({method})...")
    corrected_text = correct_text(
        recall_text,
        remove_fillers=remove_fillers,
        method=method,
        prompt_file=prompt_file,
        ollama_model=ollama_model,
    )

    out_stem, header_line = spell_corrected_output_names(
        subject_id,
        method,
        ollama_model=ollama_model,
    )
    output_file = output_path / f"{out_stem}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"{header_line}\n")
        f.write(corrected_text)

    print(f"  Saved to {output_file}")
    print(f"\nProcessing complete!")
    print(f"  Output directory: {output_path.absolute()}")


if __name__ == "__main__":
    _sm = (os.environ.get("SPELL_GRAM_METHOD") or "rules").strip().lower()
    if _sm in ("gemma", "gemma-hf"):
        os.environ["SPELL_GRAM_METHOD"] = "gemma-ollama"

    parser = argparse.ArgumentParser(
        description="Spell/grammar correction for narrative recall texts (rule-based or Gemma-4 via Ollama)."
    )
    parser.add_argument(
        "--method",
        choices=["rules", "gemma-ollama"],
        default=os.environ.get("SPELL_GRAM_METHOD", "rules"),
        help="rules: built-in (default). gemma-ollama: Ollama gemma4:e4b (local).",
    )
    parser.add_argument(
        "--prompt-file",
        default=os.environ.get("SPELL_GRAM_PROMPT_FILE", "prompt/spell_gram.txt"),
        help="Instructions file for --method gemma-ollama (default: prompt/spell_gram.txt relative to scripts/).",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.environ.get("SPELL_GRAM_OLLAMA_MODEL", "gemma4:e4b"),
        help="Ollama model tag for --method gemma-ollama (default: gemma4:e4b).",
    )
    parser.add_argument(
        "--input-file",
        "-i",
        default=None,
        help="Process one recall .txt file (e.g. data/5_recall_texts/the_siren_sub-02.txt).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="Output directory (default: BATCH_OUTPUT_DIR or output/recall_corrected).",
    )
    args = parser.parse_args()

    if args.method == "gemma-ollama":
        try:
            from helpers.ollama_gemma_e4b import check_ollama_e4b_environment

            rep = check_ollama_e4b_environment(model_tag=args.ollama_model)
            for w in rep.get("warnings") or []:
                print(f"  Spell/grammar Ollama — warning: {w}")
            if not rep.get("ok"):
                print(
                    "Spell/grammar Ollama environment not ready: "
                    + "; ".join(rep.get("errors") or [])
                )
                sys.exit(1)
            d = rep.get("details") or {}
            print(
                f"  Spell/grammar Ollama OK (base={d.get('base', '?')}, model_tag={d.get('model_tag', '?')})"
            )
        except Exception as e:
            print(f"Ollama preflight failed: {e}")
            sys.exit(1)

    batch_input_dir = os.environ.get("BATCH_INPUT_DIR", None)
    batch_output_dir = os.environ.get("BATCH_OUTPUT_DIR", None)

    remove_fillers = os.environ.get("REMOVE_FILLERS", "1") != "0"

    default_input = "data/5_recall_texts"
    output_dir = args.output_dir or batch_output_dir or "output/recall_corrected"

    corr_kwargs = {
        "method": args.method,
        "prompt_file": args.prompt_file,
        "ollama_model": args.ollama_model,
    }

    if args.input_file:
        try:
            process_recall_text_file(
                args.input_file,
                output_dir=output_dir,
                remove_fillers=remove_fillers,
                **corr_kwargs,
            )
        except Exception as e:
            print(f"Error processing data: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
        exit(0)

    input_path = Path(batch_input_dir) if batch_input_dir else Path(default_input)

    use_text_dir = False
    excel_file = None

    if input_path.is_file():
        if input_path.suffix.lower() in (".xlsx", ".xls"):
            excel_file = str(input_path)
        elif input_path.suffix.lower() == ".txt":
            try:
                process_recall_text_file(
                    str(input_path),
                    output_dir=output_dir,
                    remove_fillers=remove_fillers,
                    **corr_kwargs,
                )
            except Exception as e:
                print(f"Error processing data: {e}")
                import traceback
                traceback.print_exc()
                exit(1)
            exit(0)
        else:
            print(f"Error: Unsupported input file: {input_path}")
            exit(1)
    elif input_path.is_dir():
        txt_files = list(input_path.glob("*.txt"))
        txt_files = [f for f in txt_files if not re.search(r"_\w+-edit\.", f.name)]
        xlsx_files = list(input_path.glob("*.xlsx"))
        if txt_files:
            use_text_dir = True
        elif xlsx_files:
            excel_file = str(xlsx_files[0])
        else:
            print(f"Error: No .txt or .xlsx files found in {input_path}")
            exit(1)
    else:
        input_path = Path(default_input)
        if input_path.is_dir() and list(input_path.glob("*.txt")):
            use_text_dir = True
        else:
            excel_files = sorted(Path("data").glob("summary_*.xlsx"))
            excel_file = str(excel_files[0]) if excel_files else "data/summary.xlsx"

    try:
        if use_text_dir:
            process_recall_text_dir(
                str(input_path),
                output_dir=output_dir,
                remove_fillers=remove_fillers,
                **corr_kwargs,
            )
        else:
            if not os.path.exists(excel_file):
                print(f"Error: File not found: {excel_file}")
                exit(1)
            sheet = "Sheet1"
            try:
                df_test = pd.read_excel(excel_file, sheet_name=sheet)
                if "recall" not in df_test.columns:
                    print("Note: 'recall' column not found in Sheet1, trying 'all' sheet...")
                    sheet = "all"
            except Exception as e:
                print(f"Note: Could not read Sheet1 ({e}), trying 'all' sheet...")
                sheet = "all"
            process_recall_data(
                excel_file,
                sheet_name=sheet,
                output_dir=output_dir,
                remove_fillers=remove_fillers,
                **corr_kwargs,
            )
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

