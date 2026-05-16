"""Disk-space preflight for local model installs (Ollama / Hugging Face).

Downloading a local model writes multi-GB weight files into a cache directory.
On a nearly-full disk that download can wedge or crash the user's machine
(macOS in particular becomes unstable when the boot volume fills). These
helpers estimate how much free space a model needs and return the same
``{ok, errors, warnings, details}`` report shape used by the other
environment-check helpers, so callers can block the install *before* the
first byte is written.

Nothing here downloads or installs anything; it only inspects free space.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

# Working headroom to keep free *after* the model lands, so the OS, temp files
# and the model's own runtime scratch space don't hit a full disk.
SAFETY_HEADROOM_GB = 5.0

# Approximate on-disk size of the default local models, in GB. These are
# deliberately conservative (rounded up); a too-high estimate only makes us
# warn earlier, which is the safe direction.
_KNOWN_OLLAMA_GB = {
    "gemma4:e4b": 7.0,    # Gemma 4 E4B (Q4) ~ a few GB; rounded up
    "gemma4:e2b": 4.0,
    "llama3.3": 43.0,     # 70B — referenced by the segment step preset
}
_DEFAULT_OLLAMA_GB = 8.0


def _estimate_hf_gb_from_id(model_id: str) -> float:
    """Guess full-precision (fp16/bf16) on-disk size from a HF model id.

    ~2 bytes/param for 16-bit weights => GB ≈ 2 * (params in billions).
    Falls back to a conservative default when the id has no param hint.
    """
    m = re.search(r"(\d+(?:\.\d+)?)\s*B\b", model_id, re.IGNORECASE)
    if m:
        params_b = float(m.group(1))
        return round(params_b * 2.0 + 2.0, 1)  # +2 GB for tokenizer/config/extras
    return 20.0


def _free_gb(path: Path) -> float:
    """Free space (GB) on the volume containing ``path`` or its nearest parent."""
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    usage = shutil.disk_usage(p)
    return usage.free / (1024 ** 3)


def ollama_models_dir() -> Path:
    env = os.environ.get("OLLAMA_MODELS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".ollama" / "models"


def hf_cache_dir() -> Path:
    for var in ("HF_HUB_CACHE", "HF_HOME", "TRANSFORMERS_CACHE"):
        val = os.environ.get(var)
        if val:
            base = Path(val).expanduser()
            return base / "hub" if var == "HF_HOME" else base
    return Path.home() / ".cache" / "huggingface" / "hub"


def _report(
    *,
    needed_gb: float,
    free_gb: float,
    target: Path,
    label: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = round(needed_gb + SAFETY_HEADROOM_GB, 1)
    details: dict[str, Any] = {
        "target_dir": str(target),
        "free_gb": round(free_gb, 1),
        "estimated_model_gb": round(needed_gb, 1),
        "required_gb": required,
    }
    if free_gb < required:
        errors.append(
            f"Not enough disk space for {label}: ~{needed_gb:.0f} GB model + "
            f"{SAFETY_HEADROOM_GB:.0f} GB working headroom needed "
            f"(~{required:.0f} GB), but only {free_gb:.0f} GB free at "
            f"{target}. Free up space or set the cache dir "
            f"(OLLAMA_MODELS / HF_HOME) to a larger volume before installing."
        )
    elif free_gb < required + SAFETY_HEADROOM_GB:
        warnings.append(
            f"Low disk space for {label}: {free_gb:.0f} GB free, ~{required:.0f} "
            f"GB needed at {target}. The install may succeed but will leave the "
            f"disk nearly full."
        )
    return {"ok": not errors, "errors": errors, "warnings": warnings, "details": details}


def check_disk_for_ollama_model(model_tag: str) -> dict[str, Any]:
    """Preflight free space for an ``ollama pull <model_tag>``."""
    tag = (model_tag or "").strip().lower()
    needed = _KNOWN_OLLAMA_GB.get(tag)
    if needed is None:
        repo = tag.split(":", 1)[0]
        needed = next(
            (gb for k, gb in _KNOWN_OLLAMA_GB.items() if k.split(":", 1)[0] == repo),
            _DEFAULT_OLLAMA_GB,
        )
    target = ollama_models_dir()
    return _report(
        needed_gb=needed,
        free_gb=_free_gb(target),
        target=target,
        label=f"Ollama model {model_tag!r}",
    )


def check_disk_for_hf_model(model_id: str) -> dict[str, Any]:
    """Preflight free space for a Hugging Face weights download (from_pretrained)."""
    needed = _estimate_hf_gb_from_id(model_id or "")
    target = hf_cache_dir()
    return _report(
        needed_gb=needed,
        free_gb=_free_gb(target),
        target=target,
        label=f"Hugging Face model {model_id!r}",
    )
