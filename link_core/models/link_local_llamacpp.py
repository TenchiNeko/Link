#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

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
    parser.add_argument("--model", default=os.environ.get("LINK_LLAMACPP_MODEL", "local"))
    args = parser.parse_args()

    base_url = os.environ.get("LINK_LLAMACPP_BASE_URL", "http://127.0.0.1:8084").rstrip("/")
    prompt = read_prompt(args)

    if not prompt:
        print("ERROR: empty prompt", file=sys.stderr)
        return 2

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a read-only local code review delegate. "
                    "Do not execute commands. Do not claim to modify files. "
                    "Return concise audit/review text only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 1200,
    }

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: llama.cpp delegate request failed: {e}", file=sys.stderr)
        return 1

    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        print(json.dumps(data, indent=2), file=sys.stderr)
        return 1

    text = text.strip()
    if text.startswith("</think>"):
        text = text[len("</think>"):].strip()
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
