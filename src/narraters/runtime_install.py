"""Best-effort auto-install of optional runtime dependencies (pip + Ollama pull).

Triggered when the user selects a backend that needs extra Python packages or a
local Ollama model that is not yet pulled. Disable entirely with:

    export NARRATERS_AUTO_INSTALL_DEPS=0

Ollama itself (the desktop app / daemon) cannot be installed via pip; we only run
``ollama pull <tag>`` when the ``ollama`` CLI is on PATH and the model is missing.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from typing import Any, Sequence

# Keep in sync with ``[project.optional-dependencies]`` in pyproject.toml.
_PIP_API = ("anthropic>=0.34.0", "openai>=1.0.0")
_PIP_AUDIO = ("openai-whisper>=20231117", "whisperx>=3.3.0")
_PIP_NLP = ("spacy>=3.5.0", "benepar>=0.2.0")
_PIP_MATCH = ("rmatch>=0.3.2",)

# Must match ``server/web-interface.py`` keys for story segmentation via Ollama.
_EVENT_SEGMENT_OLLAMA_MODEL_KEYS = frozenset({"gemma4-e4b-ollama", "llama5.3-ollama", "llama3.3-ollama"})
_EVENT_SEGMENT_OLLAMA_DEFAULT_TAGS = {
    "gemma4-e4b-ollama": "gemma4:e4b",
    "llama5.3-ollama": "llama5.3",
    "llama3.3-ollama": "llama3.3",
}


def auto_install_enabled() -> bool:
    v = (os.environ.get("NARRATERS_AUTO_INSTALL_DEPS") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _pip_install(*specs: str) -> None:
    if not specs or not auto_install_enabled():
        return
    cmd = [sys.executable, "-m", "pip", "install", *specs]
    print(f"narraters: installing Python packages: {' '.join(specs)}", file=sys.stderr)
    subprocess.check_call(cmd)


def _have_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _ensure_modules(modules: Sequence[str], pip_specs: Sequence[str]) -> None:
    if not auto_install_enabled():
        return
    if all(_have_module(m) for m in modules):
        return
    _pip_install(*pip_specs)


def _ollama_tag_for_segment_api(api_model: str | None, step_options: dict[str, Any] | None) -> str | None:
    m = (api_model or "").strip()
    if m not in _EVENT_SEGMENT_OLLAMA_MODEL_KEYS:
        return None
    opts = step_options or {}
    default = _EVENT_SEGMENT_OLLAMA_DEFAULT_TAGS.get(m, "gemma4:e4b")
    tag = (
        str(opts.get("ollama_model") or opts.get("event_segment_ollama_model") or "").strip()
        or None
    ) or os.environ.get("EVENT_SEGMENT_OLLAMA_MODEL") or default
    return tag.strip() or default


def ensure_ollama_model(model_tag: str | None) -> None:
    """If Ollama is reachable and the model is missing, run ``ollama pull``."""
    if not auto_install_enabled():
        return
    tag = (model_tag or "").strip() or "gemma4:e4b"
    if not shutil.which("ollama"):
        return

    from narraters.paths import ensure_repo_on_path

    ensure_repo_on_path()
    from helpers.ollama_gemma_e4b import check_ollama_e4b_environment

    rep = check_ollama_e4b_environment(model_tag=tag)
    if rep.get("ok"):
        return
    errs = [str(e) for e in (rep.get("errors") or [])]
    if any("Cannot reach Ollama" in e for e in errs):
        return
    if not any("not found" in e.lower() or "ollama pull" in e.lower() for e in errs):
        return

    print(f"narraters: pulling Ollama model {tag!r} (this may take a while)…", file=sys.stderr)
    subprocess.check_call(["ollama", "pull", tag])

    rep2 = check_ollama_e4b_environment(model_tag=tag)
    if not rep2.get("ok"):
        msg = "; ".join(str(e) for e in (rep2.get("errors") or []) if e)
        raise RuntimeError(f"Ollama model {tag!r} still not available after pull: {msg}")


def ensure_api_clients() -> None:
    _ensure_modules(("anthropic", "openai"), _PIP_API)


def ensure_audio_stack() -> None:
    _ensure_modules(("whisper", "torch"), _PIP_AUDIO)


def ensure_nlp_stack() -> None:
    _ensure_modules(("spacy", "benepar"), _PIP_NLP)


def ensure_rmatch_stack() -> None:
    _ensure_modules(("rmatch",), _PIP_MATCH)


def _argv_flag_value(parts: Sequence[str], flag: str) -> str | None:
    for i, p in enumerate(parts):
        if p == flag and i + 1 < len(parts):
            return parts[i + 1]
        if p.startswith(flag + "="):
            return p.split("=", 1)[1]
    return None


def resolved_method(args: Any, extra: list[str] | None, *, default: str | None = None) -> str | None:
    m = getattr(args, "method", None)
    if m:
        return str(m).strip().lower()
    if extra:
        v = _argv_flag_value(extra, "--method")
        if v:
            return v.strip().lower()
    return (default or "").strip().lower() or None


def resolved_model(args: Any, extra: list[str] | None) -> str | None:
    m = getattr(args, "model", None)
    if m:
        return str(m).strip()
    if extra:
        v = _argv_flag_value(extra, "--model")
        if v:
            return v.strip()
    return None


def resolved_ollama_model(args: Any, extra: list[str] | None, *, env_names: tuple[str, ...], default: str) -> str:
    om = getattr(args, "ollama_model", None)
    if om and str(om).strip():
        return str(om).strip()
    if extra:
        v = _argv_flag_value(extra, "--ollama-model")
        if v:
            return v.strip()
    for k in env_names:
        ev = (os.environ.get(k) or "").strip()
        if ev:
            return ev
    return default


# --- CLI entry helpers (called from narraters.cli before legacy subprocess) ---


def prepare_cli_transcribe(args: Any, extra: list[str]) -> None:
    ensure_audio_stack()


def prepare_cli_segment(args: Any, extra: list[str]) -> None:
    method = resolved_method(args, extra, default="fine") or "fine"
    model = resolved_model(args, extra)
    if method in ("fine", "coarse"):
        ensure_nlp_stack()
    elif method == "api" and model:
        tag = _ollama_tag_for_segment_api(model, None)
        if tag:
            ensure_ollama_model(tag)
        else:
            ensure_api_clients()
    elif method == "api":
        ensure_api_clients()


def prepare_cli_correct(args: Any, extra: list[str]) -> None:
    method = resolved_method(args, extra, default="rules") or "rules"
    if method == "gemma-ollama":
        tag = resolved_ollama_model(args, extra, env_names=("SPELL_GRAM_OLLAMA_MODEL",), default="gemma4:e4b")
        ensure_ollama_model(tag)
    elif method == "rules":
        _ensure_modules(("spellchecker",), ("pyspellchecker>=0.7.0",))


def prepare_cli_parse(args: Any, extra: list[str]) -> None:
    method = resolved_method(args, extra, default="rules") or "rules"
    if method == "ollama":
        tag = resolved_model(args, extra) or os.environ.get("RECALL_PARSE_OLLAMA_MODEL") or "gemma4:e4b"
        ensure_ollama_model(tag)
    elif method == "rules":
        pass


def prepare_cli_match(args: Any, extra: list[str]) -> None:
    test_mode = bool(getattr(args, "test_mode", False))
    raw_m = getattr(args, "method", None) or _argv_flag_value(extra, "--method")
    if raw_m and str(raw_m).strip().lower() == "test":
        test_mode = True
    if test_mode:
        return
    method = (str(raw_m).strip().lower() if raw_m else "") or ""
    if not method:
        return
    if method in ("gemma-ollama", "ollama", "gemma"):
        tag = resolved_model(args, extra) or os.environ.get("RECALL_RATING_OLLAMA_MODEL") or "gemma4:e4b"
        ensure_ollama_model(tag)
        return
    if method == "rmatch":
        ensure_rmatch_stack()
        return
    if method in ("api", "claude", "anthropic", "openai"):
        ensure_api_clients()
        return


def prepare_cli_rate(args: Any, extra: list[str]) -> None:
    method = resolved_method(args, extra, default="linguistic") or "linguistic"
    if method == "api":
        ensure_api_clients()


# --- Web UI (Flask) ---


def prepare_web_step(
    *,
    step_type: str,
    method: str | None,
    request_data: dict[str, Any] | None,
    step_options: dict[str, Any] | None,
) -> str | None:
    """Return an error string to surface to the client, or None if OK."""
    try:
        from narraters.paths import ensure_repo_on_path

        ensure_repo_on_path()
        rd = request_data or {}
        opts = step_options or {}
        m = (method or "").strip().lower() if method else None

        if step_type in ("story-audio-transcribe", "recall-audio-transcribe"):
            ensure_audio_stack()
        elif step_type == "story-event-segment":
            seg_method = m or "fine"
            if seg_method in ("fine", "coarse"):
                ensure_nlp_stack()
            elif seg_method == "api":
                api_model = str(rd.get("model") or opts.get("model") or "").strip()
                tag = _ollama_tag_for_segment_api(api_model, opts)
                if tag:
                    ensure_ollama_model(tag)
                elif api_model in ("gpt-4o", "gpt-4o-mini"):
                    ensure_api_clients()
                elif api_model:
                    ensure_api_clients()
                else:
                    ensure_api_clients()
        elif step_type == "spell-grammar-correct":
            if m == "gemma-ollama":
                tag = (
                    str(opts.get("ollama_model") or opts.get("spell_gram_ollama_model") or "").strip()
                    or os.environ.get("SPELL_GRAM_OLLAMA_MODEL")
                    or "gemma4:e4b"
                )
                ensure_ollama_model(tag)
            elif m == "rules" or not m:
                _ensure_modules(("spellchecker",), ("pyspellchecker>=0.7.0",))
        elif step_type == "recall-parse":
            if m == "gemma-ollama":
                env_method = "ollama"
            else:
                env_method = m
            if env_method == "ollama" or m == "gemma-ollama":
                tag = (
                    str(opts.get("recall_parse_ollama_model") or opts.get("ollama_model") or "").strip()
                    or os.environ.get("RECALL_PARSE_OLLAMA_MODEL")
                    or "gemma4:e4b"
                )
                ensure_ollama_model(tag)
        elif step_type == "recall-match-events":
            if m in (None, "", "test-mode", "test"):
                return None
            if m == "gemma-ollama":
                tag = (
                    str(
                        opts.get("recall_rating_ollama_model")
                        or opts.get("recall_ollama_model")
                        or opts.get("ollama_model")
                        or ""
                    ).strip()
                    or os.environ.get("RECALL_RATING_OLLAMA_MODEL")
                    or "gemma4:e4b"
                )
                ensure_ollama_model(tag)
            elif m == "rmatch":
                ensure_rmatch_stack()
            elif m == "api":
                ensure_api_clients()
        elif step_type == "causal-rate-events":
            if m == "api":
                ensure_api_clients()
        return None
    except subprocess.CalledProcessError as e:
        return f"Automatic dependency install failed (exit {e.returncode}). See server logs."
    except Exception as e:
        return f"Automatic dependency install failed: {e}"
