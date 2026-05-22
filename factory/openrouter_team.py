"""OpenRouter client for Factory Mode.

This only calls LLM APIs. It does not post, publish, send messages, or touch external social accounts.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api").rstrip("/")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LINK_OPENROUTER_API_KEY")
SITE_URL = os.environ.get("OPENROUTER_SITE_URL") or os.environ.get("LINK_FACTORY_SITE_URL", "http://localhost")
APP_TITLE = os.environ.get("OPENROUTER_APP_TITLE", "Link Factory")


@dataclass
class ModelReply:
    model: str
    content: str
    raw: dict[str, Any]
    usage: dict[str, Any]



def _apply_reasoning_to_payload(payload: dict, role) -> dict:
    """Attach OpenRouter reasoning controls only for roles that need them."""
    try:
        from factory.team_registry import reasoning_for_role
    except Exception:
        return payload

    if isinstance(role, str):
        role_id = role
    else:
        role_id = getattr(role, "role_id", "")
    cfg = reasoning_for_role(role_id)
    mode = cfg.get("mode", "none")

    if mode == "effort":
        effort = cfg.get("effort")
        if effort:
            payload["reasoning"] = {"effort": effort}
    elif mode == "max_tokens":
        max_tokens = int(cfg.get("max_tokens") or 0)
        if max_tokens > 0:
            payload["reasoning"] = {"max_tokens": max_tokens}

    return payload


def _inject_project_context_payload(payload: dict) -> dict:
    """Add project/platform context to every factory model call."""
    project = os.environ.get("LINK_FACTORY_ACTIVE_PROJECT", "")
    if not project:
        return payload

    try:
        from factory.project_context import load_project_context
    except Exception:
        return payload

    context = load_project_context(project)
    if not context:
        return payload

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload

    context_text = (
        "FACTORY PROJECT CONTEXT AND GOVERNANCE\n"
        "Use this as high-priority operating context. Do not ignore the real platforms/tools.\n\n"
        + context
    )

    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = str(messages[0].get("content", "")) + "\n\n" + context_text
    else:
        messages.insert(0, {"role": "system", "content": context_text})

    payload["messages"] = messages
    return payload


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": APP_TITLE,
    }
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
    return headers


def require_key() -> None:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY or LINK_OPENROUTER_API_KEY is not set")


def fetch_model_catalog(timeout: int = 60) -> list[dict[str, Any]]:
    """Pull current OpenRouter model catalog."""
    req = urllib.request.Request(f"{OPENROUTER_BASE_URL}/v1/models", headers=_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("data", data.get("models", []))


def validate_model_ids(model_ids: list[str]) -> dict[str, Any]:
    catalog = fetch_model_catalog()
    available = {m.get("id") or m.get("name") for m in catalog}
    missing = [m for m in model_ids if m not in available]
    present = [m for m in model_ids if m in available]
    return {
        "present": present,
        "missing": missing,
        "available_count": len(available),
    }


def chat(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.25,
    max_tokens: int = 1600,
    timeout: int = 180,
) -> ModelReply:
    require_key()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    payload = _apply_reasoning_to_payload(
        payload,
        locals().get("role") or locals().get("role_spec") or locals().get("spec") or locals().get("role_id") or "",
    )

    payload = _inject_project_context_payload(payload)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/v1/chat/completions",
        data=body,
        headers=_headers(),
        method="POST",
    )

    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {e.code} for {model}: {detail[:800]}") from e

    choices = raw.get("choices") or []
    content = ""
    if choices:
        content = (choices[0].get("message") or {}).get("content") or choices[0].get("text") or ""

    usage = raw.get("usage") or {}
    usage["elapsed_seconds"] = round(time.time() - started, 3)

    return ModelReply(model=model, content=content.strip(), raw=raw, usage=usage)
