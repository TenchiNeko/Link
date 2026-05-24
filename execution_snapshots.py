#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from capability_gate import classify_git_command

ROOT = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT_DIR = ROOT / ".agents" / "execution_snapshots"


def _safe_slug(value: str, limit: int = 48) -> str:
    cleaned = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in {"-", "_", ".", "/"}:
            cleaned.append("-")
        elif ch.isspace():
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug or "execution")[:limit]


def _snapshot_root() -> Path:
    override = os.environ.get("LINK_EXECUTION_SNAPSHOT_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_SNAPSHOT_DIR


def _run_git(args: list[str]) -> tuple[int, str]:
    command = ["git", *args]
    decision = classify_git_command(command)
    if decision.denied:
        raise PermissionError(f"snapshot git command blocked: {decision.reason}")

    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode, proc.stdout


def create_execution_snapshot(
    *,
    action: str,
    target: Any,
    gate_decision: str,
    gate_reason: str,
    actor: str = "link",
    details: dict[str, Any] | None = None,
) -> Path:
    """
    Create a deterministic, read-only rollback/audit snapshot before execution.

    This never mutates repo state. It records:
    - HEAD
    - git status
    - unstaged diff
    - staged diff
    - untracked file list
    - metadata
    """
    now = time.strftime("%Y%m%d-%H%M%S")
    target_text = json.dumps(target, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{action}\n{target_text}\n{now}".encode("utf-8")).hexdigest()[:10]
    name = f"{now}-{_safe_slug(action)}-{digest}"

    root = _snapshot_root()
    snap = root / name
    snap.mkdir(parents=True, exist_ok=False)

    commands = {
        "HEAD.txt": ["rev-parse", "--verify", "HEAD"],
        "git_status.txt": ["status", "--short"],
        "git_diff.patch": ["diff", "--no-ext-diff", "--"],
        "git_diff_cached.patch": ["diff", "--cached", "--no-ext-diff", "--"],
        "untracked_files.txt": ["ls-files", "--others", "--exclude-standard"],
    }

    git_results: dict[str, dict[str, Any]] = {}
    for filename, args in commands.items():
        code, out = _run_git(args)
        (snap / filename).write_text(out, encoding="utf-8", errors="replace")
        git_results[filename] = {"returncode": code, "command": ["git", *args]}

    metadata = {
        "snapshot_version": 1,
        "created_at": now,
        "actor": actor,
        "action": action,
        "target": target,
        "gate_decision": gate_decision,
        "gate_reason": gate_reason,
        "details": details or {},
        "git_results": git_results,
        "restore_note": (
            "This is an audit/rollback snapshot. Review git_diff.patch, "
            "git_diff_cached.patch, git_status.txt, and untracked_files.txt before restoring."
        ),
    }
    (snap / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    return snap


if __name__ == "__main__":
    path = create_execution_snapshot(
        action="manual_snapshot",
        target=[],
        gate_decision="allow",
        gate_reason="manual",
        actor="manual",
    )
    print(path)
