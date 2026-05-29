"""
Stable task artifact paths for orchestrator runs.

Artifacts live outside transient worktrees:
.agents/artifacts/<task_id>/
"""

from __future__ import annotations

import shutil
from pathlib import Path


def get_task_artifact_dir(repo: Path, task_id: str) -> Path:
    artifact_dir = repo / ".agents" / "artifacts" / task_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def copy_file_to_artifacts(repo: Path, task_id: str, src: Path, subdir: str = "") -> Path:
    artifact_dir = get_task_artifact_dir(repo, task_id)
    if subdir:
        artifact_dir = artifact_dir / subdir
        artifact_dir.mkdir(parents=True, exist_ok=True)

    dst = artifact_dir / src.name
    shutil.copy2(src, dst)
    return dst
