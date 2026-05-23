"""Resolve the software package root (folder containing ``data/``, ``scripts/``, etc.)."""
from __future__ import annotations

import os
from pathlib import Path


def looks_like_narraters_workspace(path: Path) -> bool:
    """True when ``path`` looks like a narRaters data workspace (not the pip package alone)."""
    try:
        p = path.resolve()
    except OSError:
        return False
    data = p / "data"
    out = p / "output"
    if data.is_dir() and out.is_dir():
        return True
    if (p / "pyproject.toml").is_file() and data.is_dir():
        return True
    # Recognisable narRaters data layout without requiring both trees.
    for sub in (
        "data/3_story_events",
        "data/5_recall_texts",
        "data/2_story_transcript",
        "output/recall_parsed",
    ):
        if (p / sub).is_dir():
            return True
    return False


def resolve_runtime_project_root(*, script_dir: Path | None = None) -> Path:
    """Pick the directory that ``data/…`` and ``output/…`` paths should resolve against.

    Priority:
    1. ``NARRATERS_PROJECT_ROOT`` env var
    2. Current working directory (or a parent) that contains ``data/`` or ``output/``
       — typical when users ``pip install narraters`` then ``cd`` into their project
    3. Editable clone / repo checkout (directory with ``pyproject.toml``)
    4. Installed package root (``…/site-packages/narraters`` with bundled scripts/)
    """
    env_root = (os.environ.get("NARRATERS_PROJECT_ROOT") or "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    script_dir = script_dir or Path(__file__).resolve().parent
    package_root = script_dir.parent if script_dir.name == "server" else script_dir
    if (package_root / "scripts").is_dir() and (package_root / "server").is_dir():
        installed_root = package_root
    else:
        installed_root = script_dir.parent

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if looks_like_narraters_workspace(candidate):
            return candidate
        if (candidate / "pyproject.toml").is_file() and (candidate / "data").is_dir():
            return candidate

    for candidate in (installed_root.parent.parent, installed_root.parent, installed_root):
        if (candidate / "pyproject.toml").exists():
            return candidate.resolve()

    return installed_root.resolve()


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
