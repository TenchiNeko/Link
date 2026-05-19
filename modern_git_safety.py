#!/usr/bin/env python3
"""Deterministic git/worktree safety helpers for Link.

Small, dependency-free guard layer for classifying git commands before future
agent/tool execution. This module does not run git commands by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import shlex


class GitRiskLevel(str, Enum):
    ALLOW = "allow"
    CAUTION = "caution"
    DENY = "deny"


@dataclass(frozen=True)
class GitSafetyAssessment:
    level: GitRiskLevel
    reason: str


_READ_ONLY_GIT_OPS = {
    "status",
    "diff",
    "log",
    "show",
    "rev-parse",
    "branch",
    "tag",
    "remote",
}

_MUTATING_GIT_OPS = {
    "add",
    "commit",
    "checkout",
    "switch",
    "merge",
    "rebase",
    "reset",
    "clean",
    "stash",
    "pull",
    "fetch",
    "push",
    "worktree",
    "restore",
    "rm",
    "mv",
}


_DANGEROUS_PATTERNS = [
    (r"\bgit\s+reset\b.*\s--hard\b", "git reset --hard can destroy local work"),
    (r"\bgit\s+clean\b.*-[a-zA-Z]*f[a-zA-Z]*d", "git clean -fd can delete untracked files"),
    (r"\bgit\s+clean\b.*-[a-zA-Z]*x", "git clean -x can delete ignored files"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "force push can rewrite remote history"),
    (r"\bgit\s+branch\s+-D\b", "force deleting branches is destructive"),
    (r"\bgit\s+worktree\s+remove\b.*(--force|-f)\b", "force removing worktrees can destroy work"),
    (r"\bgit\s+checkout\s+--\s+\.", "checkout -- . can discard local changes"),
    (r"\bgit\s+restore\s+\.", "restore . can discard local changes"),
]


def _has_shell_write_or_pipe(command: str) -> bool:
    return bool(re.search(r"(\||>>?|2>|&>)", command))


def classify_git_command(command: str) -> GitSafetyAssessment:
    raw = (command or "").strip()

    if not raw:
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "empty command")

    lowered = raw.lower()

    for pattern, reason in _DANGEROUS_PATTERNS:
        if re.search(pattern, lowered):
            return GitSafetyAssessment(GitRiskLevel.DENY, reason)

    try:
        tokens = shlex.split(raw)
    except ValueError:
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "could not parse command safely")

    if not tokens or tokens[0] != "git":
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "not a git command")

    if len(tokens) == 1:
        return GitSafetyAssessment(GitRiskLevel.ALLOW, "git with no subcommand only prints help")

    op = tokens[1]

    if op in {"-C", "--git-dir", "--work-tree"}:
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "git path override needs review")

    if _has_shell_write_or_pipe(raw):
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "git command includes shell pipe/redirection")

    if op == "branch":
        if any(t in {"-d", "-D", "--delete"} for t in tokens[2:]):
            return GitSafetyAssessment(GitRiskLevel.CAUTION, "branch deletion needs review")
        return GitSafetyAssessment(GitRiskLevel.ALLOW, "read-only git branch inspection")

    if op == "tag":
        mutating_tag_flags = {"-a", "-s", "-f", "--force", "-d", "--delete"}
        if any(t in mutating_tag_flags for t in tokens[2:]):
            return GitSafetyAssessment(GitRiskLevel.CAUTION, "git tag mutation needs review")
        return GitSafetyAssessment(GitRiskLevel.ALLOW, "read-only git tag inspection")

    if op in {"status", "diff", "log", "show", "rev-parse", "remote"}:
        return GitSafetyAssessment(GitRiskLevel.ALLOW, f"read-only git {op}")

    if op in _MUTATING_GIT_OPS:
        return GitSafetyAssessment(GitRiskLevel.CAUTION, f"git {op} may modify repo state")

    if op in _READ_ONLY_GIT_OPS:
        return GitSafetyAssessment(GitRiskLevel.ALLOW, f"read-only git {op}")

    return GitSafetyAssessment(GitRiskLevel.CAUTION, f"unknown git subcommand: {op}")


def classify_worktree_path(path: str | Path, repo_root: str | Path) -> GitSafetyAssessment:
    root = Path(repo_root).resolve()
    target = Path(path)

    if not target.is_absolute():
        target = root / target

    try:
        resolved = target.resolve()
        resolved.relative_to(root)
    except Exception:
        return GitSafetyAssessment(GitRiskLevel.DENY, "path is outside Link repo root")

    parts = set(resolved.relative_to(root).parts)

    if ".git" in parts:
        return GitSafetyAssessment(GitRiskLevel.DENY, "path is inside .git metadata")

    if ".agents" in parts:
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "path is inside Link agent generated state")

    if "research" in parts:
        return GitSafetyAssessment(GitRiskLevel.CAUTION, "path is research/reference material")

    return GitSafetyAssessment(GitRiskLevel.ALLOW, "path is inside Link repo")
