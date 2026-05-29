#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path
from typing import Any

from link_common import ROOT, json_print, read_json, redact_obj

CONFIG_FILES = [
    "link_config.json",
    ".link/config.json",
    ".agents/config.json",
    "standalone_config.py",
    "standalone_models.py",
    "standalone_agents.py",
    "link_rules.local.json",
]


def parse_python_assignments(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return out

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for name in names:
                if name.isupper() or name.endswith("_CONFIG") or "model" in name.lower() or "agent" in name.lower():
                    try:
                        out[name] = ast.literal_eval(node.value)
                    except Exception:
                        out[name] = "<dynamic>"
    return out


def flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        out[prefix] = value


def collect() -> dict[str, Any]:
    scopes: dict[str, dict[str, Any]] = {}

    for rel in CONFIG_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        if path.suffix == ".json":
            data = read_json(path) or {}
        elif path.suffix == ".py":
            data = parse_python_assignments(path)
        else:
            data = {}
        flat: dict[str, Any] = {}
        flatten("", data, flat)
        scopes[rel] = redact_obj(flat)

    env_keys = [
        k for k in os.environ
        if k.startswith("LINK_") or k.startswith("OLLAMA_") or k in {"MODEL", "MODEL_NAME"}
    ]
    if env_keys:
        scopes["environment"] = redact_obj({k: os.environ.get(k) for k in sorted(env_keys)})

    seen: dict[str, list[str]] = {}
    for scope, values in scopes.items():
        for key in values:
            seen.setdefault(key.lower(), []).append(scope)

    conflicts = [
        {"key": key, "scopes": sorted(set(scope_list))}
        for key, scope_list in seen.items()
        if len(set(scope_list)) > 1
    ]

    return {
        "scopes": scopes,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Find Link config settings that appear in multiple scopes.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = collect()
    if args.json:
        json_print(data)
    else:
        print(f"Config scopes found: {len(data['scopes'])}")
        print(f"Conflicts found: {data['conflict_count']}")
        for item in data["conflicts"][:50]:
            print(f"- {item['key']}: {', '.join(item['scopes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
