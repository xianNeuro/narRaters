"""
Runtime checks for local Gemma-4 (Hugging Face) workflows: rMatch HuggingFace
matcher and spell/grammar --method gemma.

Gemma is not a separate OS package: weights live under the Hugging Face cache
after first download. This module verifies Python deps and device support
before loading multi-GB weights.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_GEMMA4_MODEL_ID = "google/gemma-4-E4B-it"


def _omp_workarounds() -> None:
    """Avoid common macOS OpenMP duplicate-runtime abort when importing torch."""
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def resolved_gemma_model_id(model_name: str | None) -> str:
    m = (model_name or "").strip()
    return m if m else DEFAULT_GEMMA4_MODEL_ID


def model_name_implies_gemma4(model_name: str | None) -> bool:
    """True if the HF model id is empty (HF matcher default) or mentions gemma-4."""
    if model_name is None or not str(model_name).strip():
        return True
    return "gemma-4" in str(model_name).lower()


def step_uses_local_gemma4(
    *,
    matcher_name: str | None = None,
    model_name: str | None = None,
    spell_method: str | None = None,
) -> bool:
    """Whether the configured step runs local Gemma-4 via Transformers."""
    sm = (spell_method or "").strip().lower()
    if sm == "gemma":
        return True
    m = (matcher_name or "").strip().lower()
    if m != "huggingface":
        return False
    return model_name_implies_gemma4(model_name)


def step_uses_ollama_gemma_e4b(
    *,
    matcher_name: str | None = None,
    spell_method: str | None = None,
    story_segment_model: str | None = None,
) -> bool:
    """Whether the configured step uses Gemma 4 E4B through Ollama (local HTTP)."""
    if (spell_method or "").strip().lower() == "gemma-ollama":
        return True
    if (matcher_name or "").strip().lower() == "ollama":
        return True
    mid = (story_segment_model or "").strip().lower()
    return mid == "gemma4-e4b-ollama"


def check_ollama_gemma_e4b_environment(model_tag: str | None = None) -> dict[str, Any]:
    """Delegate to :mod:`helpers.ollama_gemma_e4b` (Ollama /api/tags probe)."""
    from helpers.ollama_gemma_e4b import check_ollama_e4b_environment

    return check_ollama_e4b_environment(model_tag=model_tag)


def check_gemma4_environment(
    *,
    model_name: str | None = None,
    quantization: str | None = None,
) -> dict[str, Any]:
    """
    Inspect the current interpreter for Gemma-4 readiness (no model download).

    Returns a dict:
      ok (bool): True if there are no blocking errors
      errors / warnings: lists of human-readable strings
      details: versions and device flags
    """
    _omp_workarounds()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    q = (quantization or os.getenv("RMATCH_QUANTIZATION") or os.getenv("SPELL_GRAM_QUANTIZATION") or "").strip().lower()
    if q not in ("", "4bit", "8bit"):
        q = ""

    try:
        import torch

        details["torch"] = torch.__version__
        cuda_ok = torch.cuda.is_available()
        details["cuda_available"] = cuda_ok
        mps_ok = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        details["mps_available"] = mps_ok
        if not cuda_ok and not mps_ok:
            warnings.append(
                "No CUDA or Apple MPS: Gemma-4 will run on CPU (very slow and may run out of RAM)."
            )
        if q in ("4bit", "8bit") and not cuda_ok:
            errors.append(
                f"Quantization {q!r} requires CUDA; this machine has no CUDA. "
                "Unset RMATCH_QUANTIZATION / SPELL_GRAM_QUANTIZATION or use a GPU."
            )
    except Exception as e:
        errors.append(f"PyTorch import or probe failed ({type(e).__name__}: {e}). Install torch for local Gemma.")

    try:
        import transformers

        details["transformers"] = transformers.__version__
    except Exception as e:
        errors.append(f"transformers import failed ({type(e).__name__}: {e}). Install transformers>=4.44.")

    try:
        import accelerate

        details["accelerate"] = accelerate.__version__
    except Exception:
        warnings.append("accelerate not installed (recommended for efficient model load).")

    if q in ("4bit", "8bit"):
        try:
            import bitsandbytes  # noqa: F401

            details["bitsandbytes"] = getattr(bitsandbytes, "__version__", "installed")
        except Exception:
            errors.append("bitsandbytes not importable; 4bit/8bit quantization needs bitsandbytes + CUDA.")

    mid = resolved_gemma_model_id(model_name)
    details["model_id"] = mid

    # Weights are pulled into the HF cache on first from_pretrained(). Preflight
    # free disk space so a multi-GB download can't wedge or crash the machine.
    try:
        from helpers.disk_space import check_disk_for_hf_model

        disk = check_disk_for_hf_model(mid)
        details["disk"] = disk.get("details")
        warnings.extend(disk.get("warnings") or [])
        if not disk.get("ok"):
            errors.extend(disk.get("errors") or [])
    except Exception:
        pass

    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        details["hf_token"] = "set"
    else:
        warnings.append(
            "No HF_TOKEN / HUGGING_FACE_HUB_TOKEN: public models still work; gated models may fail until you log in."
        )

    try:
        from huggingface_hub import model_info

        model_info(mid, token=False)
        details["hub_model_reachable"] = True
    except Exception as e:
        details["hub_model_reachable"] = False
        warnings.append(
            f"Could not verify model metadata for {mid!r} ({type(e).__name__}: {e}). "
            "Offline or network issues may still allow a run if weights are already cached."
        )

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings, "details": details}


def ensure_gemma4_environment_or_raise(
    *,
    model_name: str | None = None,
    quantization: str | None = None,
    label: str = "Gemma-4",
) -> dict[str, Any]:
    """Raise RuntimeError if blocking checks fail; otherwise print warnings and return report."""
    report = check_gemma4_environment(model_name=model_name, quantization=quantization)
    for w in report.get("warnings") or []:
        print(f"  {label} check — warning: {w}")
    if not report.get("ok"):
        msg = "; ".join(report.get("errors") or ["unknown error"])
        raise RuntimeError(f"{label} environment not ready: {msg}")
    d = report.get("details") or {}
    print(
        f"  {label} environment: torch={d.get('torch', '?')}, "
        f"transformers={d.get('transformers', '?')}, "
        f"model_id={d.get('model_id', '?')}"
    )
    return report
