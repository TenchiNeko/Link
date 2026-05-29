#!/usr/bin/env python3
"""Deterministic file/path safety helpers for Link.

This module is intentionally small and dependency-free. It does not perform
file edits by itself; it classifies whether a future read/write/edit operation
is safe for Link tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class FileRiskLevel(str, Enum):
    ALLOW = "allow"
    CAUTION = "caution"
    DENY = "deny"


@dataclass(frozen=True)
class FileSafetyAssessment:
    level: FileRiskLevel
    reason: str
    resolved_path: str


DENY_PARTS = {
    ".git",
    ".agents",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

CAUTION_PARTS = {
    "research",
}

READ_ONLY_SAFE_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
}


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def classify_file_operation(path: str | Path, operation: str = "read", root: str | Path | None = None) -> FileSafetyAssessment:
    """Classify a file operation as allow/caution/deny.

    operation should be one of: read, write, edit, delete, move, copy.
    """

    repo_root = Path(root or Path.cwd()).resolve()
    target = Path(path)

    if not target.is_absolute():
        target = repo_root / target

    resolved = target.resolve(strict=False)
    op = (operation or "read").lower().strip()

    if not _inside(resolved, repo_root):
        return FileSafetyAssessment(
            FileRiskLevel.DENY,
            "path is outside the Link repo root",
            str(resolved),
        )

    rel = resolved.relative_to(repo_root)
    parts = set(rel.parts)

    if parts & DENY_PARTS:
        return FileSafetyAssessment(
            FileRiskLevel.DENY,
            "path is inside protected generated/internal state",
            str(resolved),
        )

    if op in {"delete", "remove", "rm"}:
        return FileSafetyAssessment(
            FileRiskLevel.DENY,
            "delete operations require a separate manual cleanup flow",
            str(resolved),
        )

    if parts & CAUTION_PARTS:
        return FileSafetyAssessment(
            FileRiskLevel.CAUTION,
            "path is in research/reference material; do not merge directly",
            str(resolved),
        )

    if op in {"write", "edit", "move", "copy"}:
        return FileSafetyAssessment(
            FileRiskLevel.CAUTION,
            f"{op} may modify repo state",
            str(resolved),
        )

    if op == "read":
        if resolved.suffix in READ_ONLY_SAFE_SUFFIXES or resolved.suffix == "":
            return FileSafetyAssessment(
                FileRiskLevel.ALLOW,
                "read-only inspection inside Link repo",
                str(resolved),
            )
        return FileSafetyAssessment(
            FileRiskLevel.CAUTION,
            "read target has a less common file type",
            str(resolved),
        )

    return FileSafetyAssessment(
        FileRiskLevel.CAUTION,
        "unknown file operation",
        str(resolved),
    )


__all__ = [
    "FileRiskLevel",
    "FileSafetyAssessment",
    "classify_file_operation",
]
