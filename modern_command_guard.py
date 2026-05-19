"""
Conservative command guard for local autonomous coding agents.

This does not replace human judgment, but it catches common foot-guns before
an agent runs shell commands: destructive file operations, network exfiltration,
privilege changes, shell substitutions, and broad chmod/chown.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
from typing import Iterable
from pathlib import Path


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    level: str
    reasons: tuple[str, ...] = ()


SUBSTITUTION_PATTERNS = [
    (re.compile(r"\$\("), "command substitution $()"),
    (re.compile(r"`"), "backtick command substitution"),
    (re.compile(r"<\("), "process substitution <()"),
    (re.compile(r">\("), "process substitution >()"),
    (re.compile(r"\$\{"), "parameter expansion ${}"),
]

DESTRUCTIVE = {
    "rm", "rmdir", "shred", "mkfs", "dd", "truncate", "wipefs",
    "chmod", "chown", "chgrp", "sudo", "su", "mount", "umount",
    "iptables", "nft", "systemctl", "service", "pkill", "killall",
}

NETWORK = {"curl", "wget", "nc", "ncat", "ssh", "scp", "rsync", "ftp", "sftp"}
READ_ONLY = {
    "ls", "pwd", "cat", "sed", "awk", "grep", "rg", "find", "git", "python", "python3",
    "pytest", "ruff", "mypy", "head", "tail", "wc", "tree", "du", "df", "stat",
}

SAFE_WRITE = {
    "echo", "printf", "touch", "mkdir", "cp", "mv",
}


def _commands(command: str) -> list[str]:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return []
    cmds: list[str] = []
    separators = {"&&", "||", ";", "|"}
    expect_cmd = True
    for part in parts:
        if part in separators:
            expect_cmd = True
            continue
        if expect_cmd:
            cmds.append(part.split("/")[-1])
            expect_cmd = False
    return cmds


def check_command(command: str, *, allow_network: bool = False, allow_destructive: bool = False) -> GuardResult:
    reasons: list[str] = []

    for pattern, label in SUBSTITUTION_PATTERNS:
        if pattern.search(command):
            reasons.append(label)

    cmds = _commands(command)
    if not cmds:
        reasons.append("could not parse command safely")

    for cmd in cmds:
        if cmd in NETWORK and not allow_network:
            reasons.append(f"network command blocked: {cmd}")
        if cmd in DESTRUCTIVE and not allow_destructive:
            reasons.append(f"destructive/admin command blocked: {cmd}")

    # Extra rm -rf style protection even if rm is later allowed manually.
    if re.search(r"\brm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)", command):
        reasons.append("recursive force delete pattern")

    if re.search(r"\bgit\s+clean\b", command):
        reasons.append("git clean blocked")

    if re.search(r"\bgit\s+rm\b", command):
        reasons.append("git rm blocked")

    if reasons:
        return GuardResult(False, "blocked", tuple(dict.fromkeys(reasons)))

    if cmds and all(c in READ_ONLY for c in cmds):
        level = "readonly"
    elif cmds and all(c in READ_ONLY or c in SAFE_WRITE for c in cmds):
        level = "safe-write"
    else:
        level = "write"

    return GuardResult(True, level, ())

# Backward-compatible alias
validate_command = check_command


def require_clean_worktree(repo: Path) -> GuardResult:
    """Require git worktree to be clean before risky agent edits."""
    import subprocess

    if not (repo / ".git").exists():
        return GuardResult(False, "blocked", ("not a git repository",))

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return GuardResult(False, "blocked", ("git status failed",))

    if result.stdout.strip():
        return GuardResult(False, "blocked", ("working tree has uncommitted changes",))

    return GuardResult(True, "readonly", ())


def create_checkpoint(repo: Path, message: str = "agent checkpoint") -> GuardResult:
    """Create a git checkpoint commit when there are staged/unstaged changes."""
    import subprocess
    from modern_test_gate import run_gate

    if not (repo / ".git").exists():
        return GuardResult(False, "blocked", ("not a git repository",))

    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, text=True, timeout=20)

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if status.returncode != 0:
        return GuardResult(False, "blocked", ("git status failed",))

    if not status.stdout.strip():
        return GuardResult(True, "readonly", ("nothing to checkpoint",))

    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if commit.returncode != 0:
        return GuardResult(False, "blocked", ("git commit failed", commit.stderr.strip()))

    return GuardResult(True, "safe-write", ("checkpoint created",))
