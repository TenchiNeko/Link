#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse
import urllib.request
from typing import Any

from link_common import ROOT, json_print, run_cmd, tcp_check, redact_obj


def http_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read(512_000).decode("utf-8", "replace")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw[:500]}
            return {"ok": True, "url": url, "status": getattr(response, "status", None), "data": redact_obj(data)}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def _ollama_tcp_target(raw_endpoint: str) -> tuple[str, int]:
    """Return the host and port represented by an Ollama base URL."""
    endpoint = raw_endpoint if "://" in raw_endpoint else f"http://{raw_endpoint}"
    parsed = urlparse(endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def collect_endpoints() -> dict[str, Any]:
    endpoints: dict[str, Any] = {}

    raw_ollama_host = (
        os.environ.get("OLLAMA_HOST")
        or os.environ.get("OLLAMA_BASE_URL")
        or "http://127.0.0.1:11434"
    )
    ollama_host = raw_ollama_host.rstrip("/")
    endpoints["ollama_tcp"] = tcp_check(*_ollama_tcp_target(ollama_host))
    endpoints["ollama_tags"] = http_json(f"{ollama_host}/api/tags")

    configured = []
    raw = os.environ.get("LINK_MODEL_ENDPOINTS", "")
    for item in raw.split(","):
        item = item.strip()
        if item:
            configured.append(item)
    endpoints["configured_model_endpoints"] = [http_json(e.rstrip("/") + "/health") for e in configured]

    endpoints["link_engine_self_test"] = run_cmd(["python3", "link_engine.py", "self-test"], timeout=30)
    endpoints["healthcheck"] = run_cmd(["python3", "link_healthcheck.py"], timeout=60)

    pgrep = run_cmd(["pgrep", "-af", "link_web.py"], timeout=5)
    endpoints["web_processes"] = pgrep

    return redact_obj({
        "root": str(ROOT),
        "endpoints": endpoints,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Link runtime/model/web endpoints.")
    parser.add_argument("command", nargs="?", default="endpoints", choices=["endpoints"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = collect_endpoints()
    if args.json:
        json_print(data)
    else:
        for name, result in data["endpoints"].items():
            if isinstance(result, dict):
                ok = result.get("ok", result.get("reachable", False))
                print(f"{name}: {'OK' if ok else 'FAIL'}")
                if not ok and result.get("error"):
                    print(f"  {result['error']}")
            else:
                print(f"{name}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
