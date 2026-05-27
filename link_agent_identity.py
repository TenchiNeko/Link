#!/usr/bin/env python3
"""Stable per-role Link agent identity adapter.

Creates deterministic agent_id values and persistent identity.json files under:
.link/agent_memory/<role_id>/identity.json

This module is intentionally local/offline and does not perform network, git, or
source-writing actions beyond its own .link/agent_memory storage.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "LU292-agent-identity-v1"
DEFAULT_PROJECT = "link"
MEMORY_ROOT = Path(os.environ.get("LINK_AGENT_MEMORY_ROOT", ".link/agent_memory"))
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://local.link/agent-identity")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_role_id(role_id: str) -> str:
    raw = str(role_id or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "-", raw)
    raw = raw.strip("-._")
    if not raw:
        raise ValueError("role_id is required")
    return raw[:96]


def role_dir(role_id: str, root: Path | None = None) -> Path:
    return (root or MEMORY_ROOT) / safe_role_id(role_id)


def identity_path(role_id: str, root: Path | None = None) -> Path:
    return role_dir(role_id, root) / "identity.json"


def deterministic_agent_id(role_id: str, project: str = DEFAULT_PROJECT) -> str:
    key = f"{project}:{safe_role_id(role_id)}"
    return str(uuid.uuid5(NAMESPACE, key))


def ensure_role_identity(
    role_id: str,
    project: str = DEFAULT_PROJECT,
    root: Path | None = None,
) -> dict[str, Any]:
    rid = safe_role_id(role_id)
    root = root or MEMORY_ROOT
    path = identity_path(rid, root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        data = json.loads(path.read_text())
    else:
        now = utc_now()
        data = {
            "schema_version": SCHEMA_VERSION,
            "project": project,
            "role_id": rid,
            "agent_id": deterministic_agent_id(rid, project),
            "created_at": now,
            "updated_at": now,
        }

    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("project", project)
    data.setdefault("role_id", rid)
    data.setdefault("agent_id", deterministic_agent_id(rid, project))
    data["updated_at"] = utc_now()

    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    ensure_memory_tree(rid, project=project, root=root)
    return data


def ensure_memory_tree(
    role_id: str,
    project: str = DEFAULT_PROJECT,
    root: Path | None = None,
) -> dict[str, str]:
    rid = safe_role_id(role_id)
    base = role_dir(rid, root)
    base.mkdir(parents=True, exist_ok=True)
    for name in ("positive", "negative", "neutral", "receipts"):
        (base / name).mkdir(parents=True, exist_ok=True)
    (base / "events.jsonl").touch(exist_ok=True)
    return {
        "role_dir": str(base),
        "identity": str(identity_path(rid, root)),
        "events": str(base / "events.jsonl"),
        "positive": str(base / "positive"),
        "negative": str(base / "negative"),
        "neutral": str(base / "neutral"),
        "receipts": str(base / "receipts"),
    }


def list_identities(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or MEMORY_ROOT
    identities: list[dict[str, Any]] = []
    if not root.exists():
        return identities
    for path in sorted(root.glob("*/identity.json")):
        try:
            identities.append(json.loads(path.read_text()))
        except Exception:
            identities.append({"path": str(path), "error": "unreadable_identity"})
    return identities


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Link agent identity adapter")
    parser.add_argument("--role-id", default="qa_worker")
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_identities(), indent=2, sort_keys=True))
    else:
        print(json.dumps(ensure_role_identity(args.role_id, args.project), indent=2, sort_keys=True))
