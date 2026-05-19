"""
Minimal git worktree isolation helpers for risky orchestrator edits.

This module intentionally starts small:
- create an isolated git worktree under .agents/worktrees/
- validate task slugs to prevent path traversal
- detect whether the worktree has changes
- remove the worktree when finished

The orchestrator can later wire this into risky build tasks.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class WorktreeInfo:
    slug: str
    path: Path
    branch: str


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def get_changed_files_against_head(repo: Path, base_ref: str = "master") -> list[str]:
    """Return files changed in this worktree compared with the main branch/base ref."""
    result = _run_git(repo, ["diff", "--name-only", f"{base_ref}...HEAD"])
    if result.returncode != 0:
        result = _run_git(repo, ["diff", "--name-only", "HEAD"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_repo_status(repo: Path) -> str:
    """Return git porcelain status for the given repo."""
    result = _run_git(repo, ["status", "--porcelain", "--untracked-files=all"])
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def restore_repo_paths(repo: Path, paths: list[str]) -> None:
    """Restore tracked paths in the main repo after isolated runs."""
    if not paths:
        return
    result = _run_git(repo, ["restore", "--", *paths])
    if result.returncode != 0:
        raise RuntimeError(f"git restore failed: {result.stderr.strip() or result.stdout.strip()}")


def validate_worktree_slug(slug: str) -> str:
    slug = slug.strip()

    if not slug:
        raise ValueError("worktree slug must not be empty")

    if len(slug) > 64:
        raise ValueError("worktree slug must be 64 characters or fewer")

    if slug in {".", ".."} or "/" in slug or "\\" in slug:
        raise ValueError("worktree slug must not contain path separators or dot segments")

    if not _SLUG_RE.match(slug):
        raise ValueError("worktree slug may only contain letters, digits, dots, underscores, and dashes")

    return slug


def create_worktree(repo: Path, slug: str) -> WorktreeInfo:
    slug = validate_worktree_slug(slug)
    root = repo / ".agents" / "worktrees"
    root.mkdir(parents=True, exist_ok=True)

    path = root / slug
    branch = f"agent/{slug}"

    if path.exists():
        raise FileExistsError(f"worktree already exists: {path}")

    result = _run_git(repo, ["worktree", "add", "-b", branch, str(path), "HEAD"])
    if result.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {result.stderr.strip() or result.stdout.strip()}")

    return WorktreeInfo(slug=slug, path=path, branch=branch)


def has_worktree_changes(worktree_path: Path) -> bool:
    result = _run_git(worktree_path, ["status", "--porcelain", "--untracked-files=all", "--ignored=matching"])
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip() or result.stdout.strip()}")
    return bool(result.stdout.strip())


def remove_worktree(repo: Path, info: WorktreeInfo, force: bool = False) -> None:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(info.path))

    result = _run_git(repo, args)
    if result.returncode != 0 and info.path.exists():
        if force:
            shutil.rmtree(info.path, ignore_errors=True)
        else:
            raise RuntimeError(f"git worktree remove failed: {result.stderr.strip() or result.stdout.strip()}")

    # Best-effort branch cleanup.
    _run_git(repo, ["branch", "-D", info.branch])
