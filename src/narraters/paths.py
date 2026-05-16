"""Path resolution for narRaters.

In Phase 1, the package lives in src/narraters/ and the legacy scripts/, server/,
helpers/, templates/, and static/ directories remain at the repo root. We need to
find that repo root from inside the installed package so we can delegate to
existing entry points without moving every file at once.

Two operating modes are supported:

1. **Editable install from source clone** (typical development)
   `pip install -e .` from the project root. `src/narraters/__file__` resolves
   to `<repo>/src/narraters/paths.py`, so `repo_root()` walks up to the
   directory that contains `pyproject.toml`.

2. **Installed wheel from PyPI or ``pip install *.whl``**
   The wheel bundles ``scripts/``, ``server/``, ``templates/``, ``static/``,
   and ``helpers/`` under the ``narraters`` package directory. In that layout
   ``repo_root()`` equals ``package_root()`` (the installed ``narraters/``
   folder next to ``paths.py``).
"""

from __future__ import annotations

import os
from pathlib import Path


def package_root() -> Path:
    """Directory containing the narraters package (i.e. the dir of this file)."""
    return Path(__file__).resolve().parent


def repo_root() -> Path:
    """The repository root, containing legacy scripts/, server/, templates/, etc.

    - **Wheel / sdist layout:** bundled assets live next to this module
      (``…/site-packages/narraters/{scripts,server,...}``).
    - **Editable clone:** walk up from ``src/narraters/`` to the directory
      that contains ``pyproject.toml``.
    """
    here = package_root()
    if (here / "scripts").is_dir() and (here / "server").is_dir():
        return here
    for candidate in (here.parent.parent, here.parent, here):
        if (candidate / "pyproject.toml").exists():
            return candidate
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
