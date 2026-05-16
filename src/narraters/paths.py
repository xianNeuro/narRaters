"""Path resolution for narRaters.

In Phase 1, the package lives in src/narraters/ and the legacy scripts/, server/,
helpers/, templates/, and static/ directories remain at the repo root. We need to
find that repo root from inside the installed package so we can delegate to
existing entry points without moving every file at once.

Two operating modes are supported:

1. **Editable install from source clone**  (the Phase 1 common case)
   `pip install -e .` from the project root. `src/narraters/__file__` resolves
   to `<repo>/src/narraters/paths.py`, so `repo_root()` walks up two levels.

2. **Installed wheel** (future, once Phase 3 bundles everything)
   The legacy directories will move *into* the package, so `repo_root()` will
   equal `package_root()`. Until then, a wheel-only install will not have a
   working `narraters serve` — Phase 3 fixes that.
"""

from __future__ import annotations

import os
from pathlib import Path


def package_root() -> Path:
    """Directory containing the narraters package (i.e. the dir of this file)."""
    return Path(__file__).resolve().parent


def repo_root() -> Path:
    """The repository root, containing legacy scripts/, server/, templates/, etc.

    Walks up from src/narraters/ to the dir containing pyproject.toml. If not
    found (e.g. installed wheel without bundled legacy dirs), falls back to
    package_root() and lets the caller surface a clearer error.
    """
    here = package_root()
    # Editable install: src/narraters/ → src/ → <repo>
    for candidate in [here.parent.parent, here.parent, here]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    # Last resort
    return here.parent.parent


def project_root() -> Path:
    """Alias for repo_root() — matches the variable name used in server/web-interface.py."""
    return repo_root()


def scripts_dir() -> Path:
    """Directory containing the legacy scripts/N_*.py pipeline scripts."""
    return repo_root() / "scripts"


def server_dir() -> Path:
    """Directory containing the legacy Flask app (server/web-interface.py)."""
    return repo_root() / "server"


def templates_dir() -> Path:
    return repo_root() / "templates"


def static_dir() -> Path:
    return repo_root() / "static"


def ensure_repo_on_path() -> None:
    """Insert repo_root() at sys.path[0] so legacy `import helpers`, `import server` work.

    The legacy scripts and the Flask app both rely on being able to import
    sibling top-level packages (helpers, etc.) from the repo root. This shim
    makes that work when the CLI is launched from anywhere.
    """
    import sys

    root = str(repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
