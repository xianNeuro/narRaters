"""Heavy-method resource preflight.

Some pipeline methods load multi-GB local models (Gemma-4 via Ollama, the
rMatch embedding matcher, local Transformers/Whisper). On a small machine
these can swap the box to a standstill or get OOM-killed. Rather than let the
UI launch them blindly, this module assesses — *before* anything is spawned —
whether the chosen method is likely too heavy for this device, and what
lighter method to use instead.

It composes the existing checks (``helpers.disk_space`` for free disk,
``helpers.gemma_environment`` for Ollama/model availability) and adds a RAM
probe. Nothing here downloads, installs, or runs a model.

Returned shape (consumed by the web UI to drive a warning popup):

    {
      "heavy":      bool,            # is this a heavy method at all?
      "severity":   "ok"|"warn"|"block",
      "title":      str,
      "message":    str,             # human text shown in the popup
      "reasons":    [str, ...],
      "suggestion": {"method": str|None, "label": str},
      "details":    {...},           # ram/disk/availability sub-reports
    }

``severity``:
  ok    — safe to run, no popup.
  warn  — risky (tight RAM / low disk headroom); popup, user may proceed.
  block — will almost certainly fail or wedge the machine (model missing,
          not enough disk, not enough total RAM); popup, switching strongly
          advised.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

# Approx RAM (GB) needed to actually *run* each heavy backend without thrashing.
# min_gb  = below this it will OOM / swap to a halt (=> block)
# rec_gb  = below this it runs but painfully (=> warn)
_RAM_PROFILE = {
    "ollama-gemma4-e4b": {"min_gb": 6.0, "rec_gb": 10.0, "label": "Gemma-4 E4B (Ollama)"},
    "rmatch": {"min_gb": 6.0, "rec_gb": 12.0, "label": "rMatch embedding matcher"},
    "gemma-hf": {"min_gb": 12.0, "rec_gb": 20.0, "label": "Gemma-4 (local Transformers)"},
    "whisper": {"min_gb": 4.0, "rec_gb": 8.0, "label": "Whisper transcription"},
}

# Lighter, dependency-free fallback per step type.
_LIGHTER_METHOD = {
    "sentenceCorrect": ("rules", "Rule-based spell/grammar (no model, instant)"),
    "textParsing": ("rules", "Rule-based parsing (regex, no model)"),
    "textMatching": ("test-mode", "Keyword matching (Test Mode, no model)"),
    "eventSegment": ("clause", "Clause heuristic segmentation (no model)"),
    "causalRating": ("linguistic", "Linguistic heuristics (no model)"),
    "audioTranscribe:recall": (None, "a smaller Whisper model, or pre-transcribed text"),
    "audioTranscribe:story": (None, "a smaller Whisper model, or pre-transcribed text"),
}


def _total_ram_gb() -> float | None:
    """Best-effort total physical RAM in GB. None if undeterminable."""
    try:
        import psutil  # optional

        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        pass
    try:
        n = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return n / (1024 ** 3)
    except (ValueError, OSError, AttributeError):
        pass
    try:  # macOS
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
        )
        return int(out.stdout.strip()) / (1024 ** 3)
    except Exception:
        return None


def _available_ram_gb() -> float | None:
    """Best-effort *currently free* RAM in GB. None if undeterminable."""
    try:
        import psutil

        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception:
        pass
    # macOS: parse `vm_stat` (free + inactive + speculative pages).
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        page = 4096
        m = re.search(r"page size of (\d+) bytes", out)
        if m:
            page = int(m.group(1))
        free_pages = 0
        for key in ("Pages free", "Pages inactive", "Pages speculative"):
            mm = re.search(rf"{key}:\s+(\d+)", out)
            if mm:
                free_pages += int(mm.group(1))
        if free_pages:
            return free_pages * page / (1024 ** 3)
    except Exception:
        pass
    # Linux: /proc/meminfo MemAvailable
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return None


def _classify(step_type: str, method: str | None, opts: dict) -> tuple[str | None, str | None]:
    """Return (ram_profile_key, model_tag) for the heavy backend, or (None, None)."""
    m = (method or "").strip().lower()
    if step_type in ("audioTranscribe:story", "audioTranscribe:recall"):
        return "whisper", None
    if step_type == "textMatching":
        if m == "rmatch":
            return "rmatch", None
        if m in ("gemma-ollama", "gemma"):
            tag = str(opts.get("recall_rating_ollama_model") or opts.get("ollama_model") or "").strip() or "gemma4:e4b"
            return "ollama-gemma4-e4b", tag
    if step_type in ("sentenceCorrect", "textParsing"):
        if m in ("gemma-ollama", "gemma", "ollama"):
            tag = str(opts.get("ollama_model") or "").strip() or "gemma4:e4b"
            return "ollama-gemma4-e4b", tag
        if m in ("gemma-hf",):
            return "gemma-hf", None
    if step_type == "eventSegment" and m == "api":
        model = str(opts.get("model") or opts.get("event_segment_model") or "").strip().lower()
        if "ollama" in model or "gemma" in model or "llama" in model:
            return "ollama-gemma4-e4b", "gemma4:e4b"
    return None, None


def assess_method(
    step_type: str,
    method: str | None,
    options: dict | None = None,
) -> dict[str, Any]:
    """Assess whether (step_type, method) is too heavy for this device."""
    opts = options if isinstance(options, dict) else {}
    profile_key, model_tag = _classify(step_type, method, opts)

    if profile_key is None:
        return {
            "heavy": False,
            "severity": "ok",
            "title": "",
            "message": "",
            "reasons": [],
            "suggestion": {"method": None, "label": ""},
            "details": {},
        }

    profile = _RAM_PROFILE[profile_key]
    lighter_method, lighter_label = _LIGHTER_METHOD.get(
        step_type, (None, "a lighter method")
    )

    reasons: list[str] = []
    severity = "ok"
    details: dict[str, Any] = {"profile": profile_key, "ram_profile": profile}

    # --- RAM ---------------------------------------------------------------
    total = _total_ram_gb()
    avail = _available_ram_gb()
    details["ram"] = {
        "total_gb": round(total, 1) if total else None,
        "available_gb": round(avail, 1) if avail else None,
        "min_gb": profile["min_gb"],
        "recommended_gb": profile["rec_gb"],
    }
    if total is not None and total < profile["min_gb"]:
        severity = "block"
        reasons.append(
            f"This device has ~{total:.0f} GB RAM total; {profile['label']} needs "
            f"at least ~{profile['min_gb']:.0f} GB and will likely run out of memory."
        )
    elif avail is not None and avail < profile["min_gb"]:
        severity = "block"
        reasons.append(
            f"Only ~{avail:.0f} GB RAM is free right now; {profile['label']} needs "
            f"~{profile['min_gb']:.0f} GB free and would freeze the machine."
        )
    elif avail is not None and avail < profile["rec_gb"]:
        severity = "warn"
        reasons.append(
            f"Only ~{avail:.0f} GB RAM free; {profile['label']} runs best with "
            f"~{profile['rec_gb']:.0f} GB and may be very slow / swap heavily."
        )
    elif total is None and avail is None:
        severity = "warn"
        reasons.append("Could not determine this device's RAM; proceed with caution.")

    # --- Disk + model availability ----------------------------------------
    try:
        if profile_key == "ollama-gemma4-e4b":
            from helpers.disk_space import check_disk_for_ollama_model
            from helpers.gemma_environment import check_ollama_gemma_e4b_environment

            disk = check_disk_for_ollama_model(model_tag or "gemma4:e4b")
            env = check_ollama_gemma_e4b_environment(model_tag=model_tag or "gemma4:e4b")
            details["disk"] = disk.get("details")
            details["availability"] = {
                "ok": env.get("ok"),
                "errors": env.get("errors"),
            }
            if not disk.get("ok"):
                severity = "block"
                reasons.extend(disk.get("errors") or [])
            elif disk.get("warnings"):
                severity = "warn" if severity != "block" else "block"
                reasons.extend(disk.get("warnings") or [])
            if not env.get("ok"):
                severity = "block"
                reasons.extend(env.get("errors") or [])
        elif profile_key == "rmatch":
            from helpers.disk_space import check_disk_for_hf_model

            rmatch_model = str(opts.get("rmatch_model") or opts.get("model") or "").strip()
            disk = check_disk_for_hf_model(rmatch_model or "sentence-transformers-all-MiniLM-1B")
            details["disk"] = disk.get("details")
            if not disk.get("ok"):
                severity = "block"
                reasons.extend(disk.get("errors") or [])
            elif disk.get("warnings"):
                severity = "warn" if severity != "block" else "block"
                reasons.extend(disk.get("warnings") or [])
            try:
                import importlib.util

                missing = [
                    p for p in ("torch", "rmatch", "sentence_transformers")
                    if importlib.util.find_spec(p) is None
                ]
                details["availability"] = {"missing_packages": missing}
                if missing:
                    severity = "block"
                    reasons.append(
                        "rMatch needs "
                        + ", ".join(missing)
                        + " (multi-GB ML stack) which are not installed."
                    )
            except Exception:
                pass
        elif profile_key == "gemma-hf":
            from helpers.disk_space import check_disk_for_hf_model

            disk = check_disk_for_hf_model("google/gemma-4-E4B-it")
            details["disk"] = disk.get("details")
            if not disk.get("ok"):
                severity = "block"
                reasons.extend(disk.get("errors") or [])
    except Exception as e:  # never let the preflight itself break the run
        details["preflight_error"] = f"{type(e).__name__}: {e}"

    heavy = True
    if severity == "ok":
        return {
            "heavy": True,
            "severity": "ok",
            "title": "",
            "message": "",
            "reasons": [],
            "suggestion": {"method": lighter_method, "label": lighter_label},
            "details": details,
        }

    if severity == "block":
        title = f"⚠️ {profile['label']} is too heavy for this device"
        lead = (
            "Running this method here will likely fail or freeze your computer. "
            "We strongly recommend switching to a lighter method:"
        )
    else:
        title = f"⚠️ {profile['label']} may be too heavy for this device"
        lead = (
            "This method can run here but may be very slow or make the machine "
            "unresponsive. Consider a lighter method instead:"
        )

    message = lead
    if lighter_method:
        message += f"\n\n→ Suggested: “{lighter_label}” (method: {lighter_method})."
    else:
        message += f"\n\n→ Suggested: {lighter_label}."

    return {
        "heavy": heavy,
        "severity": severity,
        "title": title,
        "message": message,
        "reasons": reasons,
        "suggestion": {"method": lighter_method, "label": lighter_label},
        "details": details,
    }
