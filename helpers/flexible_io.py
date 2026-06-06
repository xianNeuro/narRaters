"""Flexible file loading for pipeline steps.

Accepts common tabular and document formats (.txt, .csv, .tsv, .xlsx, .xls)
and normalizes story-event and parsed-recall column layouts, including cases
where recall text and event ratings appear in swapped columns.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd

TRANSCRIPT_EXTENSIONS = frozenset({".txt", ".md", ".csv", ".tsv", ".xlsx", ".xls"})
TABULAR_EXTENSIONS = frozenset({".csv", ".tsv", ".xlsx", ".xls"})
STORY_EVENTS_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv", ".tsv"})
PARSED_RECALL_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv", ".tsv"})

_EVENT_COL_NAMES = (
    "event",
    "event_number",
    "event_num",
    "event_id",
    "event_no",
    "event #",
    "number",
    "num",
    "idx",
    "index",
    "#",
)
_TEXT_COL_NAMES = (
    "story_texts",
    "story_text",
    "text",
    "segment",
    "content",
    "story",
    "event_text",
    "sentence",
    "clause",
)
_RECALL_TEXT_COL_NAMES = (
    "recall_in_temporal_order",
    "recall_text",
    "recall",
    "text",
    "parsed",
    "temporal_order",
    "segment",
)
_RATING_COL_NAMES = (
    "recalled_events",
    # The matched-events column in some exports / the alternative CSV convention is
    # named after the *story* side, e.g. ``story_segments`` in a recall-matched.csv.
    "story_segments",
    "story-segments",
    "matched_story_segments",
    "story_events",
    "matched",
    "matches",
    "events",
    "event",
    "rating",
    "matched_events",
    "event_match",
    "event_matches",
    "matched_event",
)

# Columns that must NEVER be mistaken for the matched-events column even though they
# look numeric / empty: the recall-segment INDEX (0,1,2…), the per-segment further
# ratings, and the free-text comment.
_NON_RATING_COL_NAMES = frozenset({
    "recall_segment", "recall segment", "recall_segment_number", "segment_number",
    "segment_num", "segment_index", "seg", "seg_num", "index", "idx", "#", "row", "n", "no",
    "comment", "comments", "note", "notes",
    "summary", "error", "confabulation", "inference", "opinion", "meta",
})


def _norm_name(name: object) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _column_map(df: pd.DataFrame) -> dict[str, str]:
    return {_norm_name(c): c for c in df.columns}


def read_tabular(path: Path | str) -> pd.DataFrame:
    """Read a tabular file into a DataFrame."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(p)
    if ext == ".tsv":
        return pd.read_csv(p, sep="\t")
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(p)
    if ext == ".txt":
        # Tab-delimited or comma-delimited text tables.
        try:
            return pd.read_csv(p, sep="\t")
        except Exception:
            return pd.read_csv(p)
    raise ValueError(f"Unsupported tabular extension: {ext}")


def read_document_text(path: Path | str) -> str:
    """Extract plain narrative text from txt/csv/tsv/xlsx transcript files."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".txt", ".md"):
        text = p.read_text(encoding="utf-8").strip()
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].strip().endswith((".txt", ".csv", ".tsv", ".xlsx")):
            text = "\n".join(lines[1:]).strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]
        return text.strip()

    df = read_tabular(p)
    if df.empty:
        return ""

    cols = _column_map(df)
    for key in ("transcript", "text", "story_text", "story_texts", "content", "body"):
        if key in cols:
            parts = df[cols[key]].dropna().astype(str).tolist()
            return " ".join(parts).strip()

    # Single-column file or unnamed text column.
    if len(df.columns) == 1:
        parts = df.iloc[:, 0].dropna().astype(str).tolist()
        return " ".join(parts).strip()

    # Pick the longest average-length object column.
    best_col = None
    best_score = 0.0
    for col in df.columns:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        score = series.str.len().mean()
        if score > best_score:
            best_score = score
            best_col = col
    if best_col is not None:
        return " ".join(df[best_col].dropna().astype(str).tolist()).strip()
    return ""


def _pick_named_column(cols: dict[str, str], candidates: Sequence[str]) -> Optional[str]:
    for name in candidates:
        if name in cols:
            return cols[name]
    return None


def _series_looks_like_event_numbers(series: pd.Series) -> bool:
    sample = series.dropna().head(30)
    if sample.empty:
        return False
    ok = 0
    for val in sample:
        try:
            float(val)
            ok += 1
        except (TypeError, ValueError):
            pass
    return ok / len(sample) >= 0.7


def _series_looks_like_recall_text(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(30)
    if sample.empty:
        return False
    return sample.str.len().mean() >= 18


def _series_looks_like_event_ratings(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(30)
    if sample.empty:
        return True
    if sample.str.len().mean() > 24:
        return False
    return sample.str.match(r"^[\d,\s\-]*$").mean() >= 0.5


def detect_story_events_columns(df: pd.DataFrame) -> Optional[tuple[str, str]]:
    if df is None or df.empty:
        return None
    cols = _column_map(df)
    event_col = _pick_named_column(cols, _EVENT_COL_NAMES)
    text_col = _pick_named_column(cols, _TEXT_COL_NAMES)

    numeric_cols = [c for c in df.columns if _series_looks_like_event_numbers(df[c])]
    texty_cols = [c for c in df.columns if _series_looks_like_recall_text(df[c])]

    if not event_col and numeric_cols:
        event_col = numeric_cols[0]
    if not text_col:
        for c in texty_cols:
            if c != event_col:
                text_col = c
                break
    if not text_col and len(df.columns) >= 2:
        c0, c1 = df.columns[0], df.columns[1]
        if event_col == c0:
            text_col = c1
        elif event_col == c1:
            text_col = c0
        elif _series_looks_like_event_numbers(df[c0]):
            event_col, text_col = c0, c1
        else:
            event_col, text_col = c0, c1
    if event_col and text_col:
        return event_col, text_col
    return None


def normalize_story_events_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with canonical columns ``event`` and ``story_texts``."""
    detected = detect_story_events_columns(df)
    if not detected:
        raise ValueError("Could not detect story event columns (event number + text)")
    event_col, text_col = detected
    out = pd.DataFrame(
        {
            "event": df[event_col],
            "story_texts": df[text_col].fillna("").astype(str),
        }
    )
    cleaned = []
    for _, row in out.iterrows():
        ev = row["event"]
        if pd.isna(ev) or str(ev).strip() == "":
            continue
        try:
            evn = int(float(ev))
        except (TypeError, ValueError):
            continue
        cleaned.append({"event": evn, "story_texts": str(row["story_texts"]).strip()})
    return pd.DataFrame(cleaned)


def detect_parsed_recall_columns(df: pd.DataFrame) -> Optional[tuple[str, str]]:
    """Return (rating_col, recall_text_col)."""
    if df is None or df.empty:
        return None
    cols = _column_map(df)
    rating_col = _pick_named_column(cols, _RATING_COL_NAMES)
    recall_col = _pick_named_column(cols, _RECALL_TEXT_COL_NAMES)

    if len(df.columns) == 1:
        only = df.columns[0]
        if _series_looks_like_recall_text(df[only]):
            return only, only  # same column used as placeholder; ratings filled empty below
        return None

    if len(df.columns) >= 2:
        c0, c1 = df.columns[0], df.columns[1]
        if not rating_col and not recall_col:
            s0, s1 = df[c0], df[c1]
            if _series_looks_like_recall_text(s0) and _series_looks_like_event_ratings(s1):
                return c1, c0
            if _series_looks_like_recall_text(s1) and _series_looks_like_event_ratings(s0):
                return c0, c1
            if _series_looks_like_recall_text(s1):
                recall_col = c1
                rating_col = c0
            elif _series_looks_like_recall_text(s0):
                recall_col = c0
                rating_col = c1
        elif rating_col and not recall_col:
            for c in df.columns:
                if c != rating_col and _series_looks_like_recall_text(df[c]):
                    recall_col = c
                    break
        elif recall_col and not rating_col:
            for c in df.columns:
                if (c != recall_col and _norm_name(c) not in _NON_RATING_COL_NAMES
                        and _series_looks_like_event_ratings(df[c])):
                    rating_col = c
                    break

    if recall_col:
        if not rating_col:
            # Only adopt a column that genuinely looks like matched events and isn't a
            # segment index / further-rating / comment column. Otherwise treat the file
            # as "no matches yet" (ratings left empty), rather than loading the recall
            # segment number as the matched event.
            rating_col = next(
                (c for c in df.columns
                 if c != recall_col and _norm_name(c) not in _NON_RATING_COL_NAMES
                 and _series_looks_like_event_ratings(df[c])),
                None,
            )
        if rating_col:
            return rating_col, recall_col
        return recall_col, recall_col  # recall text only; matched-events filled empty
    return None


def normalize_parsed_recall_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with ``recalled_events`` then ``recall_in_temporal_order``."""
    detected = detect_parsed_recall_columns(df)
    if not detected:
        raise ValueError(
            "Could not detect parsed recall columns (recall text + optional event ratings)"
        )
    rating_col, recall_col = detected
    if rating_col == recall_col:
        ratings = pd.Series([''] * len(df), dtype=str)
    else:
        ratings = df[rating_col].fillna("").astype(str).replace("nan", "")
    out = pd.DataFrame(
        {
            "recalled_events": ratings,
            "recall_in_temporal_order": df[recall_col].fillna("").astype(str),
        }
    )
    return order_recall_rating_columns(out)


def order_recall_rating_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if "recalled_events" in cols and "recall_in_temporal_order" in cols:
        return df[["recalled_events", "recall_in_temporal_order"]]
    return df


def read_story_events_file(path: Path | str) -> pd.DataFrame:
    df = read_tabular(path)
    return normalize_story_events_df(df)


def read_parsed_recall_file(path: Path | str) -> pd.DataFrame:
    df = read_tabular(path)
    return normalize_parsed_recall_df(df)


def story_events_to_records(df: pd.DataFrame) -> list[dict]:
    norm = normalize_story_events_df(df)
    return [
        {
            "event": int(row["event"]),
            "story_texts": str(row["story_texts"]) if pd.notna(row["story_texts"]) else "",
        }
        for _, row in norm.iterrows()
        if pd.notna(row["event"])
    ]


def pick_story_events_file(events_dir: Path | str, base_id: str) -> Optional[Path]:
    """Resolve ``{base_id}_events`` file in one directory (xlsx/csv/tsv)."""
    root = Path(events_dir)
    if not root.is_dir():
        return None
    base = f"{base_id}_events"
    for ext in (".xlsx", ".csv", ".tsv", ".xls"):
        p0 = root / f"{base}{ext}"
        if p0.is_file():
            return p0
    paths: list[Path] = []
    for ext in STORY_EVENTS_EXTENSIONS:
        paths.extend(root.glob(f"{base}-*{ext}"))
        for suffix in ("_rule-based", "_api"):
            q = root / f"{base}{suffix}{ext}"
            if q.is_file():
                paths.append(q)
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def story_events_records_from_path(path: Path | str) -> list[dict]:
    """Load story events list-of-dicts from a tabular events file."""
    return story_events_to_records(read_story_events_file(path))


def glob_extensions(directory: Path | str, extensions: Iterable[str], pattern: str = "*") -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        return []
    exts = {e if e.startswith(".") else f".{e}" for e in extensions}
    out: list[Path] = []
    seen: set[str] = set()
    for ext in sorted(exts):
        for fp in sorted(root.glob(f"{pattern}{ext}")):
            if fp.is_file() and fp.name not in seen:
                seen.add(fp.name)
                out.append(fp)
    return out


def extensions_for_suffix(suffix: str) -> tuple[str, ...]:
    """Extensions used when scanning for files with a pipeline tail (e.g. _events, _parsed)."""
    if suffix in ("_events", "_parsed"):
        return tuple(sorted(STORY_EVENTS_EXTENSIONS if suffix == "_events" else PARSED_RECALL_EXTENSIONS))
    return tuple(sorted(TRANSCRIPT_EXTENSIONS))


def stem_has_tail(filename: str, base: str, tail: str) -> bool:
    stem = Path(filename).stem
    return stem == f"{base}{tail}" or stem.startswith(f"{base}{tail}")
