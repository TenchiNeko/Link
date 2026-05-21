#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def read_prompt(args) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read().strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "LINK_OPENROUTER_DEEPSEEK_MODEL",
            "deepseek/deepseek-chat",
        ),
    )
    parser.add_argument("--debug-auth", action="store_true")
    args = parser.parse_args()

    api_key = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("LINK_OPENROUTER_API_KEY")
        or ""
    ).strip()

    if not api_key or api_key in {"your_key_here", "your_real_openrouter_key_here"}:
        print("ERROR: Set a real OPENROUTER_API_KEY or LINK_OPENROUTER_API_KEY.", file=sys.stderr)
        return 2

    prompt = read_prompt(args)
    if not prompt:
        print("ERROR: empty prompt", file=sys.stderr)
        return 2

    if args.debug_auth:
        print(f"auth_loaded=true key_prefix={api_key[:7]}... key_len={len(api_key)}", file=sys.stderr)

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful code review delegate. "
                    "Do not claim to execute commands. "
                    "Return concise audit findings and patch suggestions only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost/link",
            "X-Title": "Link Delegate Runner",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"ERROR: OpenRouter HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    try:
        print(data["choices"][0]["message"]["content"].strip())
    except Exception:
        print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
