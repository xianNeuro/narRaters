#!/usr/bin/env python3
"""
Script to parse narrative recall text into event-sized units.

Reads corrected recall files from output/recall_corrected/ (or another input dir), parses them into
segments, and outputs Excel/CSV to output/recall_parsed/.

**Methods**
- **rules** (default): Deterministic independent-clause heuristics in ``parse_text()``.
- **ollama** (Gemma 4 E4B): Set ``RECALL_PARSE_METHOD=ollama`` or pass ``--ollama``; uses
  ``scripts/prompt/recall_parse_clause.txt`` and local Ollama (``OLLAMA_GEMMA_TAG``, default ``gemma4:e4b``).
"""

import os
import sys
from pathlib import Path
import re
import pandas as pd


def _software_package_root() -> Path:
    d = Path(__file__).resolve().parent
    return d.parent if d.name == "scripts" else d


_pr = _software_package_root()
if str(_pr) not in sys.path:
    sys.path.insert(0, str(_pr))


_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# Import clause-validation helpers from the segmentation module.
# These are used in the proof-check pass to ensure every segment contains
# at least one independent clause.
try:
    _seg_mod_name = '2_story-event-segment'
    import importlib
    _seg_mod = importlib.import_module(_seg_mod_name)
    _has_independent_clause = _seg_mod._has_independent_clause
    _merge_non_independent_clauses = _seg_mod._merge_non_independent_clauses
    _try_load_spacy = _seg_mod._try_load_spacy
except Exception:
    _has_independent_clause = None
    _merge_non_independent_clauses = None
    _try_load_spacy = None


def parse_text(text):
    """
    Parse text into independent clause units.
    
    An independent clause contains a subject and a predicate and can stand
    alone as a sentence.  Each segment represents one independent clause or
    one speech act.  Dialogue turns from different speakers are always
    separate segments.
    
    Segmentation Rules:
    1. SPLIT at sentence boundaries (periods, question marks, exclamation marks)
    2. SPLIT at semicolons (always separate independent clauses)
    3. SPLIT at non-restrictive relative clauses: ", who/which/whom"
    4. SPLIT at speech attribution + direct speech boundaries (said/asked/... , dialogue)
    5. SPLIT at commas between independent clauses (subject + verb on both sides)
    6. SPLIT at coordinating conjunctions (and/but/so/yet) between independent clauses
    7. DO NOT split: time + action, subordinate + main, lists, participial phrases
    
    Principles:
    - Use only exact substrings from the original text - NO MODIFICATIONS
    - Preserve original spacing, capitalization, punctuation exactly
    """
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return []
    
    original_text = text
    
    # --- Sentence boundary detection ---
    sentence_boundaries = []
    
    for match in re.finditer(r'([.!?])\s+([A-Z])', original_text):
        pos = match.start()
        before_period = original_text[max(0, pos-3):pos]
        if re.search(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|Inc|Ltd|etc|vs|i\.e|e\.g)\s*$', before_period, re.IGNORECASE):
            continue
        if re.search(r'\b[A-Z]\.\s*$', before_period):
            continue
        sentence_boundaries.append(match.start() + 1)
    
    # [.!?] followed by closing double-quote + whitespace  (end of quoted sentence)
    for match in re.finditer(r'([.!?])\s*(["\u201d])\s+', original_text):
        pos = match.start()
        end_pos = match.end()
        if end_pos not in sentence_boundaries:
            before_period = original_text[max(0, pos-3):pos]
            if not re.search(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|Inc|Ltd|etc|vs)\s*$', before_period, re.IGNORECASE):
                sentence_boundaries.append(end_pos)
    
    # [.!?] + whitespace + opening double-quote  (new quoted sentence starts)
    for match in re.finditer(r'([.!?])\s+(["\u201c])', original_text):
        pos = match.start()
        boundary = pos + 1
        if boundary not in sentence_boundaries:
            before_period = original_text[max(0, pos-3):pos]
            if not re.search(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|Inc|Ltd|etc|vs)\s*$', before_period, re.IGNORECASE):
                sentence_boundaries.append(boundary)
    
    sentence_boundaries.append(len(original_text))
    sentence_boundaries = sorted(set(sentence_boundaries))
    
    sentences = []
    prev_boundary = 0
    for boundary in sentence_boundaries:
        sentence = original_text[prev_boundary:boundary]
        if sentence and len(sentence.split()) > 0:
            sentences.append((prev_boundary, boundary, sentence))
        prev_boundary = boundary
    
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
    for start_pos, end_pos, sentence in sentences:
        if not sentence or len(sentence.split()) == 0:
            continue
        
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
            pos_after_comma = match.start() + len(match.group())
            before = sentence[:match.start()]
            after = sentence[pos_after_comma:]
            
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
                boundary_positions.add(pos_after_comma)
        
        # RULE 5: Coordinating conjunctions between independent clauses
        # "and" requires subject change; "but"/"so"/"yet" do not
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
    
    final_parsed = [p for p in parsed_units if p and len(p.split()) > 0]
    if not final_parsed:
        final_parsed = [original_text] if original_text.strip() else []
    
    final_parsed = _proof_check_segments(final_parsed)

    if _merge_non_independent_clauses is not None:
        nlp = _try_load_spacy() if _try_load_spacy else None
        final_parsed = _merge_non_independent_clauses(final_parsed, nlp)

    return final_parsed


# Ollama Gemma 4 E4B — clause-level recall parsing (see scripts/prompt/recall_parse_clause.txt)
RECALL_PARSE_OLLAMA_SYSTEM = (
    "You are a careful linguistic annotation assistant. "
    "You must not paraphrase or fix the recall text. "
    "Copy it only by splitting into exact contiguous substrings, one per line, as instructed."
)

DEFAULT_RECALL_PARSE_PROMPT = "recall_parse_clause.txt"


def get_recall_parse_prompt_path():
    return Path(__file__).resolve().parent / "prompt"


def load_recall_parse_prompt(prompt_filename=None):
    """Load recall-parse instructions from ``scripts/prompt/`` (default: recall_parse_clause.txt)."""
    name = (prompt_filename or os.environ.get("RECALL_PARSE_PROMPT") or DEFAULT_RECALL_PARSE_PROMPT).strip()
    p = get_recall_parse_prompt_path() / name
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError(f"Recall parse prompt not found: {p}")


def _strip_code_fence(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 1)[-1] if "```" in t[3:] else t[3:]
        t = t.strip()
        if t.lower().startswith("text") or t.lower().startswith("plaintext"):
            t = t.split("\n", 1)[-1] if "\n" in t else t
    return t.strip()


def parse_text_ollama_e4b(
    text,
    prompt_version=None,
    model_tag=None,
    *,
    num_predict: int = 12000,
) -> list:
    """
    Segment recall text using local Ollama (Gemma 4 E4B by default).

    Set ``model_tag`` or ``OLLAMA_GEMMA_TAG`` to override. Prompt file: ``RECALL_PARSE_PROMPT`` or
    default ``recall_parse_clause.txt``.
    """
    if not text or not str(text).strip():
        return []

    from helpers.ollama_gemma_e4b import ollama_chat, resolved_ollama_gemma_tag

    otag = resolved_ollama_gemma_tag((model_tag or os.environ.get("OLLAMA_GEMMA_TAG", "")).strip() or None)
    try:
        num_ctx = int(os.environ.get("RECALL_PARSE_OLLAMA_NUM_CTX", "32768"))
    except ValueError:
        num_ctx = 32768
    try:
        npred = int(os.environ.get("RECALL_PARSE_OLLAMA_NUM_PREDICT", str(num_predict)))
    except ValueError:
        npred = num_predict

    template = load_recall_parse_prompt(prompt_version)
    user_message = f"{template}\n\n---\n\nRecall text to segment (verbatim, one segment per line):\n\n{text}"

    output_text = ollama_chat(
        [
            {"role": "system", "content": RECALL_PARSE_OLLAMA_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        model_tag=otag,
        temperature=0.0,
        num_ctx=num_ctx,
        num_predict=npred,
        think=False,
    )
    output_text = _strip_code_fence(output_text)
    segments = [line.strip() for line in output_text.split("\n") if line.strip()]
    if not segments:
        return []
    # Reject accidental single-line echo of full text when model ignores format
    if len(segments) == 1 and len(segments[0]) > 0.95 * len(text) and text.strip() in segments[0]:
        return [text.strip()]

    return segments


def _proof_check_segments(segments):
    """
    Examine each segment in relation to previous and next. Merge if the split
    appears unjustified (fragment, or same proposition continued).
    
    Merge rules:
    - Time phrase alone ("At 3:59 p.m.,") -> merge with next
    - Bare subordinate without main -> merge with next
    - "and" fragment after comma when very short -> merge with prev
    
    Protection (never merge across):
    - Segments starting with quotation marks (dialogue turns)
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
        
        # Time phrase alone ("At 3:59 p.m.,")
        if curr_words <= 4 and re.match(r'^(At|On|In|By)\s+\d', curr, re.IGNORECASE) and nxt:
            merge_with_next = True
        
        # Bare subordinate without main clause
        if (curr_words <= 8 and re.match(r'^(When|While|Although|Because|If)\s+', curr, re.IGNORECASE) 
                and not re.search(r'[.!?]\s*$', curr_stripped) and nxt):
            merge_with_next = True
        
        # "and" fragment after comma — same thought continued
        if prev and re.match(r'^\s*and\s+', curr) and prev.rstrip().endswith(',') and curr_words <= 5:
            merge_with_prev = True
        
        # Prev ends with bare determiner (the/a/an) — cannot stand alone
        if prev and re.search(r'\s(the|a|an)\s*$', prev.rstrip()) and curr:
            merge_with_prev = True
        
        # Protection: never merge dialogue turns (segments with quotation marks)
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


def validate_segments(segments, text=None):
    """
    Proof-check: examine each segment in relation to neighbors. Return list of
    (segment_index, warning) for potentially unjustified splits.
    Optional: pass original text to verify segments reconstruct it correctly.
    """
    warnings = []
    for i, seg in enumerate(segments):
        prev = segments[i - 1] if i > 0 else None
        nxt = segments[i + 1] if i + 1 < len(segments) else None
        n = len(seg.split())
        if n < 3 and prev and nxt:
            if re.match(r'^\s*(and|or|but)\s+', seg):
                warnings.append((i, f"Short conjunction fragment ({n} words): {repr(seg[:50])}"))
        if n <= 4 and re.match(r'^(At|On|In|By)\s+\d', seg, re.IGNORECASE) and nxt:
            warnings.append((i, f"Time phrase alone may belong with next segment"))
    if text:
        reconstructed = ' '.join(s.strip() for s in segments)
        orig_compact = re.sub(r'\s+', ' ', text).strip()
        if reconstructed.replace(' ', '') != orig_compact.replace(' ', ''):
            warnings.append((-1, "Segments do not reconstruct original text"))
    return warnings


def process_recall_file(
    file_path,
    parse_method: str = "rules",
    ollama_model_tag: str | None = None,
    prompt_version: str | None = None,
):
    """
    Process a single recall file and return parsed units.
    
    Args:
        file_path: Path to the recall file
        parse_method: ``"rules"`` (default, deterministic clause heuristics) or ``"ollama"``
            (Gemma 4 E4B via Ollama + ``scripts/prompt/recall_parse_clause.txt``).
        ollama_model_tag: Ollama model tag when ``parse_method="ollama"`` (else ignored).
        prompt_version: Prompt filename in ``scripts/prompt/`` for Ollama method (else env or default).
        
    Returns:
        Tuple of (filename_base, list of parsed units)
    """
    from helpers.flexible_io import read_document_text

    ext = Path(file_path).suffix.lower()
    if ext in (".csv", ".tsv", ".xlsx", ".xls"):
        text = read_document_text(file_path)
        filename_base = Path(file_path).stem
        if not text.strip():
            return filename_base, []
        lines = None
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    if lines is not None:
        # First line is filename, rest is text
        if len(lines) < 2:
            return None, []
        filename_line = lines[0].strip()
        filename_base = filename_line.replace('.txt', '')
        text = '\n'.join(lines[1:]).strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]
    
    if (parse_method or "rules").lower() == "ollama":
        parsed_units = parse_text_ollama_e4b(
            text,
            prompt_version=prompt_version,
            model_tag=ollama_model_tag,
        )
    else:
        parsed_units = parse_text(text)
    
    return filename_base, parsed_units


def create_dataframe(parsed_units):
    """
    Create a pandas DataFrame with recalled_events (empty) and recall_in_temporal_order columns.
    
    Args:
        parsed_units: List of parsed text units
        
    Returns:
        pandas DataFrame with columns: recalled_events, recall_in_temporal_order
    """
    if not parsed_units:
        return pd.DataFrame(columns=['recalled_events', 'recall_in_temporal_order'])
    
    # Create DataFrame with empty strings (not NaN) for recalled_events
    df = pd.DataFrame({
        'recalled_events': [''] * len(parsed_units),
        'recall_in_temporal_order': parsed_units
    })
    
    # Ensure recalled_events column is string type to avoid NaN
    df['recalled_events'] = df['recalled_events'].astype(str)
    # Replace 'nan' string with empty string if any occur
    df['recalled_events'] = df['recalled_events'].replace('nan', '')
    
    return df


def _slug_tag(tag: str | None, max_len: int = 56) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (tag or "").strip()).strip("_")
    return (s or "default")[:max_len]


def _output_stem_parsed(filename_base, parse_method, ollama_model_tag=None):
    if (parse_method or "rules").lower() == "ollama":
        tag = (
            (ollama_model_tag or "").strip()
            or (os.environ.get("RECALL_PARSE_OLLAMA_MODEL") or "").strip()
            or (os.environ.get("OLLAMA_GEMMA_TAG") or "").strip()
            or "gemma4:e4b"
        )
        return f"{filename_base}_parsed-ollama_{_slug_tag(tag)}"
    return f"{filename_base}_parsed"


def process_all_recall_files(
    input_dir='output/recall_corrected',
    output_dir='output/recall_parsed',
    output_format='excel',
    filter_pattern=None,
    parse_method: str = "rules",
    ollama_model_tag: str | None = None,
    prompt_version: str | None = None,
):
    """
    Process all recall files and output parsed CSV or Excel files.
    
    Args:
        input_dir: Directory containing corrected recall files
        output_dir: Directory to save parsed output files
        output_format: 'excel' or 'csv' (default: 'excel')
        filter_pattern: Optional string pattern to filter files (e.g., 'subject_a' to process only files containing 'subject_a')
        parse_method: ``"rules"`` or ``"ollama"`` (Gemma 4 E4B)
        ollama_model_tag: Ollama tag for ``ollama`` method
        prompt_version: Prompt file in ``scripts/prompt/`` for ``ollama`` method
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        error_msg = f"Error: Input directory not found: {input_dir}"
        print(error_msg)
        raise FileNotFoundError(error_msg)
    
    if not input_path.is_dir():
        error_msg = f"Error: Input path is not a directory: {input_dir}"
        print(error_msg)
        raise NotADirectoryError(error_msg)
    
    from helpers.flexible_io import TRANSCRIPT_EXTENSIONS, glob_extensions

    input_files = glob_extensions(input_path, TRANSCRIPT_EXTENSIONS)
    input_files = [f for f in input_files if not re.search(r'_\w+-edit\.', f.name)]
    txt_files = list(input_files)

    # Filter by pattern if provided
    # Resolution order:
    #   1. If BATCH_INPUT_VARIANT is set, look for {filter_pattern}{variant}.txt exactly (no fallback).
    #   2. Exact stem match: {filter_pattern}.txt
    #   3. Any suffixed variant: {filter_pattern}_<anything>.txt (newest by mtime wins)
    #   4. Substring fallback: any file whose name contains filter_pattern
    if filter_pattern:
        original_count = len(txt_files)
        explicit_variant = os.environ.get("BATCH_INPUT_VARIANT")
        if explicit_variant is not None:
            target_stem = f"{filter_pattern}{explicit_variant}"
            txt_files = [f for f in input_files if f.stem == target_stem]
        else:
            exact = [f for f in input_files if f.stem == filter_pattern]
            if exact:
                txt_files = exact
            else:
                suffix_cands = [f for f in input_files
                                if f.stem.startswith(f"{filter_pattern}_")]
                if suffix_cands:
                    txt_files = [max(suffix_cands, key=lambda p: p.stat().st_mtime)]
                else:
                    txt_files = [f for f in input_files if filter_pattern in f.name]
        if not txt_files:
            error_msg = (
                f"No files found matching BATCH_ITEM_ID/pattern '{filter_pattern}' in {input_dir}. "
                f"Found {original_count} eligible file(s) total."
            )
            print(error_msg)
            raise FileNotFoundError(error_msg)
        print(f"Filtered to {len(txt_files)} file(s) for '{filter_pattern}'")
    
    if not txt_files:
        error_msg = f"No transcript files found in {input_dir} (supported: .txt, .csv, .tsv, .xlsx)"
        print(error_msg)
        raise FileNotFoundError(error_msg)
    
    print(f"Found {len(txt_files)} files to process")
    print(f"Output format: {output_format}")
    print(f"Parse method: {parse_method}")
    if (parse_method or "").lower() == "ollama":
        print("  (Ollama: set OLLAMA_GEMMA_TAG or pull gemma4:e4b; see helpers/ollama_gemma_e4b.py)")

    processed_count = 0
    
    for file_path in txt_files:
        print(f"Processing {file_path.name}...")
        
        try:
            filename_base, parsed_units = process_recall_file(
                file_path,
                parse_method=parse_method,
                ollama_model_tag=ollama_model_tag,
                prompt_version=prompt_version,
            )
        except Exception as e:
            error_msg = f"Error processing {file_path.name}: {e}"
            print(f"  {error_msg}")
            import traceback
            traceback.print_exc()
            # Continue with next file instead of failing completely
            continue
        
        if not parsed_units:
            print(f"  Warning: No parsed units extracted from {file_path.name}")
            continue
        
        if not filename_base:
            print(f"  Warning: Could not extract filename base from {file_path.name}")
            continue
        
        # Create DataFrame
        df = create_dataframe(parsed_units)
        
        # Ensure recalled_events is empty strings (not NaN) before saving
        df['recalled_events'] = df['recalled_events'].fillna('').astype(str)
        df['recalled_events'] = df['recalled_events'].replace('nan', '')
        
        # Save to output file
        try:
            out_stem = _output_stem_parsed(filename_base, parse_method, ollama_model_tag)
            if output_format.lower() == 'excel':
                output_file = output_path / f"{out_stem}.xlsx"
                # Use na_rep='' to ensure empty strings stay empty in Excel
                df.to_excel(output_file, index=False, engine='openpyxl', na_rep='')
            else:  # CSV
                output_file = output_path / f"{out_stem}.csv"
                df.to_csv(output_file, index=False, encoding='utf-8', na_rep='')
            
            print(f"  Extracted {len(parsed_units)} parsed units")
            print(f"  Saved to {output_file}")
            processed_count += 1
        except Exception as save_error:
            error_msg = f"Error saving {filename_base}: {save_error}"
            print(f"  {error_msg}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            # Re-raise to fail the script
            raise
    
    print(f"\nProcessing complete!")
    print(f"  Processed: {processed_count} files")
    print(f"  Output directory: {output_path.absolute()}")


if __name__ == "__main__":
    # Process all recall files (default: rule-based; use --ollama for Gemma 4 E4B via Ollama)
    # Or: RECALL_PARSE_METHOD=ollama BATCH_ITEM_ID=... (web interface)
    import sys

    def _recall_method_from_env():
        m = (os.environ.get("RECALL_PARSE_METHOD") or "rules").strip().lower()
        if m in ("e4b", "ollama", "api"):
            return "ollama"
        return m if m in ("rules", "ollama") else "rules"

    omt = (os.environ.get("RECALL_PARSE_OLLAMA_MODEL") or "").strip() or None
    pv = (os.environ.get("RECALL_PARSE_PROMPT") or "").strip() or None
    argv_work = list(sys.argv[1:])
    parse_method = _recall_method_from_env()
    pos = []
    i = 0
    while i < len(argv_work):
        a = argv_work[i]
        if a in ("--ollama", "--e4b"):
            parse_method = "ollama"
        elif a == "--model" and i + 1 < len(argv_work):
            omt = argv_work[i + 1]
            i += 1
        elif a == "--prompt" and i + 1 < len(argv_work):
            pv = argv_work[i + 1]
            i += 1
        else:
            pos.append(a)
        i += 1

    # Check for environment variables first (from web interface)
    batch_item_id = os.environ.get('BATCH_ITEM_ID', None)
    batch_input_dir = os.environ.get('BATCH_INPUT_DIR', None)
    batch_output_dir = os.environ.get('BATCH_OUTPUT_DIR', None)
    
    # Determine filter pattern
    filter_pattern = None
    if batch_item_id:
        filter_pattern = batch_item_id
        print(f"Processing single item from BATCH_ITEM_ID: {filter_pattern}")
    elif pos:
        filter_pattern = pos[0]
        print(f"Filtering files by pattern: {filter_pattern}")
    
    # Determine input and output directories
    input_dir = batch_input_dir if batch_input_dir else 'output/recall_corrected'
    output_dir = batch_output_dir if batch_output_dir else 'output/recall_parsed'
    
    try:
        process_all_recall_files(
            input_dir=input_dir,
            output_dir=output_dir,
            output_format='excel',
            filter_pattern=filter_pattern,
            parse_method=parse_method,
            ollama_model_tag=omt,
            prompt_version=pv,
        )
    except FileNotFoundError as e:
        error_msg = f"File not found error: {e}"
        print(error_msg, file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        error_msg = f"Error processing files: {e}"
        print(error_msg, file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

