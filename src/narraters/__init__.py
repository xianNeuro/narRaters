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

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("narRaters")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"

from narraters.paths import project_root, repo_root  # noqa: F401

__all__ = [
    "__version__",
    "project_root",
    "repo_root",
]
