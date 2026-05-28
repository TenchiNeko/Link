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

# ---------------------------------------------------------------------------
# Link command risk classification
# Added as a small, dependency-free safety layer for shell/tool execution.
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _link_dataclass
from enum import Enum as _LinkEnum
import re as _link_re
import shlex as _link_shlex


class CommandRiskLevel(str, _LinkEnum):
    ALLOW = "allow"
    CAUTION = "caution"
    DENY = "deny"


@_link_dataclass(frozen=True)
class CommandRiskAssessment:
    level: CommandRiskLevel
    reason: str


_DANGEROUS_PATTERNS = [
    # rm -rf against root/home/user paths. Conservative on purpose.
    (r"\brm\s+-[^\n\s]*(?:r[^\n\s]*f|f[^\n\s]*r)[^\n]*\s+(?:/|~(?:/|$)|\$home(?:/|$))", "destructive recursive delete against root/home"),
    (r"\bsudo\s+rm\b", "sudo rm is destructive"),

    # Permission disasters.
    (r"\bchmod\s+-r\s+777\b", "recursive world-writable chmod"),
    (r"\b(chown|chmod)\s+-r\s+.*(?:/|~(?:/|$)|\$home(?:/|$))", "recursive permission change against root/home"),

    # Download-and-execute.
    (r"\b(curl|wget)\b.*\|\s*(bash|sh)\b", "downloaded script piped into shell"),

    # Secret reads/exfiltration.
    (r"\b(cat|grep|sed|awk)\b.*(\.env|id_rsa|id_ed25519|credentials|token|secret|api_key)", "possible secret access/exfiltration"),

    # Disk destruction.
    (r">\s*/dev/(sd[a-z]|nvme\d+n\d+)", "direct block-device write"),
    (r"\bdd\s+.*of=/dev/", "direct disk overwrite"),
    (r"\bmkfs\b", "filesystem formatting command"),
]


_CAUTION_COMMANDS = {
    "git add", "git commit", "git reset", "git checkout", "git switch",
    "mv", "cp", "mkdir", "touch", "python", "python3", "pip", "pip3",
    "npm", "pnpm", "yarn", "make", "chmod", "chown",
}


_SAFE_READ_ONLY_COMMANDS = {
    "ls", "pwd", "cat", "head", "tail", "grep", "rg", "find",
    "sed", "awk", "wc", "du", "df", "tree", "git", "sha256sum",
}


_SAFE_GIT_SUBCOMMANDS = {
    "status", "diff", "log", "show", "branch", "rev-parse", "ls-files",
}


def classify_command_risk(command: str) -> CommandRiskAssessment:
    """Classify a shell command as allow/caution/deny.

    This is intentionally conservative. It does not execute anything.
    """

    raw = (command or "").strip()
    if not raw:
        return CommandRiskAssessment(CommandRiskLevel.DENY, "empty command")

    lowered = raw.lower()

    for pattern, reason in _DANGEROUS_PATTERNS:
        if _link_re.search(pattern, lowered):
            return CommandRiskAssessment(CommandRiskLevel.DENY, reason)

    try:
        parts = _link_shlex.split(raw)
    except ValueError:
        return CommandRiskAssessment(CommandRiskLevel.CAUTION, "could not parse command safely")

    if not parts:
        return CommandRiskAssessment(CommandRiskLevel.DENY, "empty command")

    cmd = parts[0]
    first_two = " ".join(parts[:2]) if len(parts) >= 2 else cmd

    if cmd == "git":
        sub = parts[1] if len(parts) > 1 else ""
        if sub in _SAFE_GIT_SUBCOMMANDS:
            return CommandRiskAssessment(CommandRiskLevel.ALLOW, f"read-only git {sub}")
        return CommandRiskAssessment(CommandRiskLevel.CAUTION, f"git {sub or 'command'} may modify repo state")

    if first_two in _CAUTION_COMMANDS or cmd in _CAUTION_COMMANDS:
        return CommandRiskAssessment(CommandRiskLevel.CAUTION, f"{cmd} may modify files or environment")

    if cmd in _SAFE_READ_ONLY_COMMANDS:
        return CommandRiskAssessment(CommandRiskLevel.ALLOW, f"{cmd} is normally read-only inspection")

    if "|" in raw or ">" in raw or "&&" in raw or ";" in raw:
        return CommandRiskAssessment(CommandRiskLevel.CAUTION, "compound shell command needs review")

    return CommandRiskAssessment(CommandRiskLevel.CAUTION, "unknown command; review before execution")


def command_risk_level(command: str) -> str:
    """Compatibility helper returning only allow/caution/deny."""
    return classify_command_risk(command).level.value


def command_is_denied(command: str) -> bool:
    return classify_command_risk(command).level == CommandRiskLevel.DENY
