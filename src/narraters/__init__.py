"""narRaters — AI-assisted narrative processing with human-screening.

A 6-step pipeline (transcription → segmentation → spell/grammar correction →
parsing → event matching → causal rating) with a Flask web UI for interactive
review and editing at each step.

Quick start
-----------
    # Install editable from a clone of the repo:
    pip install -e .

    # Launch the web interface:
    narraters serve

    # Run individual pipeline steps:
    narraters segment --method fine --input data/2_story_transcript/foo.txt
    narraters match --method api --model <anthropic-model-id>

Library use
-----------
    from narraters import run_serve
    run_serve(port=5000)
"""

import re
from importlib.metadata import version
from pathlib import Path

from narraters.paths import project_root, repo_root  # noqa: F401

# Single source of truth is ``version`` in pyproject.toml. In a source checkout
# read it directly (editable-install metadata goes stale until reinstall);
# a wheel / git install has no pyproject.toml, so use the package metadata.
_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
if Path(__file__).resolve().parents[1].name == "src" and _PYPROJECT.is_file():
    __version__ = re.search(r'^version = "([^"]+)"', _PYPROJECT.read_text(), re.MULTILINE).group(1)
else:
    __version__ = version("narraters")

__all__ = [
    "__version__",
    "project_root",
    "repo_root",
]
