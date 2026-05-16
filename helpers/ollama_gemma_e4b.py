"""
Local Gemma 4 E4B via Ollama HTTP API (no cloud LLM billing).

Default model tag: ``gemma4:e4b`` (Ollama library). Override with ``OLLAMA_GEMMA_TAG``
or per-call ``model_tag``. Base URL: ``OLLAMA_HOST`` (default ``http://127.0.0.1:11434``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_OLLAMA_GEMMA_TAG = "gemma4:e4b"


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def resolved_ollama_gemma_tag(model_tag: str | None) -> str:
    t = (model_tag or os.environ.get("OLLAMA_GEMMA_TAG") or DEFAULT_OLLAMA_GEMMA_TAG).strip()
    return t if t else DEFAULT_OLLAMA_GEMMA_TAG


def ollama_chat(
    messages: list[dict[str, str]],
    *,
    model_tag: str | None = None,
    temperature: float = 0.0,
    num_ctx: int = 32768,
    num_predict: int | None = None,
    think: bool = False,
    timeout: int = 600,
    base_url: str | None = None,
    response_format: str | dict | None = None,
) -> str:
    """
    POST /api/chat and return assistant message text (non-streaming).

    When ``think`` is False, the ``think`` field is omitted from the JSON body for
    compatibility with older Ollama versions that reject unknown keys.

    ``response_format`` forwards Ollama's top-level ``format`` field — pass ``"json"``
    to force strict-JSON output (the model's grammar is constrained server-side) or a
    JSON Schema dict for structured output. Reasoning-style models like ``gemma4:e4b``
    otherwise tend to emit meta-commentary instead of the requested JSON.
    """
    base = (base_url or ollama_base_url()).rstrip("/")
    tag = resolved_ollama_gemma_tag(model_tag)
    opts: dict[str, Any] = {
        "temperature": float(temperature),
        "num_ctx": int(num_ctx),
    }
    if num_predict is not None:
        opts["num_predict"] = int(num_predict)

    body: dict[str, Any] = {
        "model": tag,
        "messages": messages,
        "stream": False,
        "options": opts,
    }
    if response_format is not None:
        body["format"] = response_format
    # Thinking-by-default models (gemma4:e4b, deepseek-r1, …) will spend the full
    # ``num_predict`` budget on internal reasoning and emit an empty ``content`` field
    # unless we explicitly disable thinking. Always forward the bool — older Ollama
    # builds (pre-thinking-model support) ignore the field rather than rejecting it.
    body["think"] = bool(think)
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    msg = data.get("message")
    if isinstance(msg, str):
        return msg.strip()
    if isinstance(msg, dict):
        content = (msg.get("content") or "").strip()
        if content:
            return content
        thinking = msg.get("thinking")
        if isinstance(thinking, str) and thinking.strip():
            return thinking.strip()
        return ""
    # Some responses expose plain text only
    alt = data.get("response")
    if isinstance(alt, str) and alt.strip():
        return alt.strip()
    return ""


def check_ollama_e4b_environment(
    *,
    model_tag: str | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """
    Probe Ollama (``/api/tags``) for availability of the requested model tag.

    Returns the same shape as ``check_gemma4_environment``:
    ok, errors, warnings, details.
    """
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {"base": ollama_base_url()}
    tag = resolved_ollama_gemma_tag(model_tag)
    details["model_tag"] = tag

    try:
        req = urllib.request.Request(f"{details['base']}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        errors.append(
            f"Cannot reach Ollama at {details['base']!r} ({e}). "
            "Start the Ollama app or daemon and ensure OLLAMA_HOST is correct."
        )
        return {"ok": False, "errors": errors, "warnings": warnings, "details": details}
    except Exception as e:
        errors.append(f"Ollama /api/tags failed ({type(e).__name__}: {e}).")
        return {"ok": False, "errors": errors, "warnings": warnings, "details": details}

    names: list[str] = []
    for m in raw.get("models") or []:
        n = m.get("name")
        if isinstance(n, str) and n.strip():
            names.append(n.strip())

    details["ollama_model_names"] = names[:40]

    # Exact match or same repo (e.g. gemma4:e4b vs digest suffix variants)
    found = tag in names
    if not found and ":" in tag:
        repo = tag.split(":", 1)[0]
        found = any(n == tag or n.startswith(repo + ":") for n in names)

    if not found:
        # The model still has to be pulled. Preflight free disk space first so
        # we never advise an `ollama pull` that would fill the user's disk.
        try:
            from helpers.disk_space import check_disk_for_ollama_model

            disk = check_disk_for_ollama_model(tag)
            details["disk"] = disk.get("details")
            warnings.extend(disk.get("warnings") or [])
            if not disk.get("ok"):
                errors.extend(disk.get("errors") or [])
            else:
                errors.append(
                    f"Ollama model {tag!r} not found in `ollama list`. "
                    f"Install with: ollama pull {tag}"
                )
        except Exception:
            errors.append(
                f"Ollama model {tag!r} not found in `ollama list`. "
                f"Install with: ollama pull {tag}"
            )
    else:
        details["model_present"] = True

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings, "details": details}
