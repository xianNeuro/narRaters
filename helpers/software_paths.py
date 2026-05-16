"""Resolve the software package root (folder containing ``data/``, ``scripts/``, etc.)."""
from __future__ import annotations

from pathlib import Path


def pipeline_scripts_dir(software_root: Path) -> Path:
    """Directory containing the numbered pipeline CLI scripts (``1_*.py`` … ``6_*.py``)."""
    return software_root / "scripts"


def pipeline_prompt_dir(software_root: Path) -> Path:
    """Directory containing LLM prompt ``.txt`` files (next to the pipeline scripts)."""
    return pipeline_scripts_dir(software_root) / "prompt"


def software_package_root(this_file: str) -> Path:
    """
    Directory that holds pipeline assets (``data/``, ``output/``, etc.).

    Prompt templates live under ``scripts/prompt/``. This returns the parent of
    ``scripts/`` (the package root). If a file still sits at the package root,
    returns that directory.
    """
    d = Path(this_file).resolve().parent
    return d.parent if d.name == "scripts" else d
