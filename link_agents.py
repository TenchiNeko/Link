#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any

from link_common import ROOT, json_print, load_text, redact_obj

AGENT_FILES = [
    "standalone_agents.py",
    "standalone_models.py",
    "standalone_config.py",
    "link_config.json",
    ".agents/config.json",
]


def extract_names(src: str) -> list[str]:
    names: set[str] = set()
    for match in re.finditer(r"class\s+([A-Za-z_][A-Za-z0-9_]*(?:Agent|Model|Config))\b", src):
        names.add(match.group(1))
    for match in re.finditer(r'["\']([A-Za-z0-9_.:-]*(?:agent|model)[A-Za-z0-9_.:-]*)["\']', src, re.I):
        names.add(match.group(1))
    return sorted(names)


def collect() -> dict[str, Any]:
    files = []
    names: set[str] = set()
    for rel in AGENT_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        src = load_text(path)
        found = extract_names(src)
        names.update(found)
        files.append({"path": rel, "found": found, "line_count": len(src.splitlines())})

    env = {
        k: os.environ.get(k)
        for k in sorted(os.environ)
        if k.startswith("LINK_") or "MODEL" in k or "AGENT" in k
    }

    return redact_obj({
        "files": files,
        "resolved_names": sorted(names),
        "environment_overrides": env,
        "notes": [
            "This is a static listing. It shows probable active/shadowed agent/model names from Link config/source files.",
            "Use link_doctor.py --json for combined repo, engine, web, and endpoint state.",
        ],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="List Link agent/model configuration sources.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = collect()
    if args.json:
        json_print(data)
    else:
        print("Agent/model sources:")
        for item in data["files"]:
            print(f"- {item['path']}: {len(item['found'])} names")
            for name in item["found"][:20]:
                print(f"  - {name}")
        if data["environment_overrides"]:
            print("Environment overrides detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
