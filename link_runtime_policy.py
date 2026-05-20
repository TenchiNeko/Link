#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

MAX_INLINE_TEXT_CHARS = 50_000
MAX_EVENT_PREVIEW_CHARS = 4_000
TOOL_RESULTS_DIR = Path(".agents") / "tool_results"

BINARY_EXTENSIONS = {
    ".7z", ".a", ".avi", ".bin", ".bmp", ".bundle", ".class", ".db", ".dll",
    ".dmg", ".doc", ".docx", ".exe", ".gif", ".gz", ".heic", ".ico", ".iso",
    ".jar", ".jpeg", ".jpg", ".lockb", ".mov", ".mp3", ".mp4", ".o", ".obj",
    ".pdf", ".png", ".pyc", ".pyd", ".rar", ".so", ".sqlite", ".sqlite3",
    ".tar", ".tgz", ".tiff", ".webp", ".woff", ".woff2", ".xls", ".xlsx",
    ".zip", ".zst",
}

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".agents/reports",
    ".agents/worktrees",
    ".agents/tool_results",
}

SECRET_RE = re.compile(
    r"(?i)\b(token|secret|api[_-]?key|authorization|cookie|password|webhook|bearer)\b"
    r"\s*([:=])\s*([^\s,'\"]+)"
)

POLICY_MARKER = "LINK_ENGINE_POLICY_V2"


def redact_text(text: str) -> str:
    return SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)


def is_binary_path(path: str | Path) -> bool:
    p = Path(path)
    return p.suffix.lower() in BINARY_EXTENSIONS


def should_skip_repo_path(path: str | Path) -> bool:
    p = Path(path)
    normalized = str(p).replace("\\", "/")
    if is_binary_path(p):
        return True
    return any(
        normalized == item or normalized.startswith(item.rstrip("/") + "/")
        for item in SKIP_DIRS
    )


def looks_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    if b"\0" in data[:4096]:
        return True
    sample = data[:4096]
    textish = sum(1 for b in sample if b in b"\n\r\t" or 32 <= b <= 126)
    return (textish / max(1, len(sample))) < 0.70


def spooled_output_path(root: Path, run_id: str, label: str, text: str) -> Path:
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "output"
    return root / TOOL_RESULTS_DIR / str(run_id) / f"{safe_label}-{digest}.txt"


def spool_large_text(
    root: Path,
    run_id: str,
    label: str,
    value: Any,
    *,
    max_inline: int = MAX_INLINE_TEXT_CHARS,
    preview_chars: int = MAX_EVENT_PREVIEW_CHARS,
) -> Any:
    if value is None:
        return value
    if not isinstance(value, str):
        return value

    text = redact_text(value)
    if len(text) <= max_inline:
        return text

    out = spooled_output_path(root, run_id, label, text)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", errors="replace")

    preview = text[:preview_chars]
    return (
        f"[large output spooled: {len(text)} chars -> {out}]\n"
        f"[preview first {len(preview)} chars]\n"
        f"{preview}"
    )


def compact_event(root: Path, run_id: str, event: Any, index: int = 0) -> Any:
    if not isinstance(event, dict):
        return event

    compacted = dict(event)
    for key in ("raw", "detail", "message", "stdout", "stderr", "output"):
        if key in compacted:
            compacted[key] = spool_large_text(
                root,
                run_id,
                f"event-{index}-{key}",
                compacted[key],
            )
    return compacted


def compact_engine_report_payload(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or "unknown")
    out = dict(payload)

    events = out.get("events")
    if isinstance(events, list):
        out["events"] = [compact_event(root, run_id, event, i) for i, event in enumerate(events)]

    return out


def compact_status_event(root: Path, run_id: str, event: Any) -> Any:
    return compact_event(root, run_id, event, 0)


def requires_nontrivial_verification(changed_files: list[str] | tuple[str, ...], diff_lines: int | None = None) -> bool:
    files = [str(f) for f in changed_files if str(f).strip()]
    if len(files) >= 3:
        return True

    critical_names = {
        "link_engine.py",
        "link_web.py",
        "link_healthcheck.py",
        "standalone_main.py",
        "standalone_orchestrator.py",
        "standalone_agents.py",
        "modern_command_guard.py",
        "modern_file_safety.py",
        "modern_git_safety.py",
    }

    if any(Path(f).name in critical_names for f in files):
        return True

    if any(f.startswith(("api/", "server/", "javascript/", "scripts/")) for f in files):
        return True

    if diff_lines is not None and diff_lines > 1200:
        return True

    return False


def build_policy_prompt(prompt: str, *, audit_only: bool = False) -> str:
    if POLICY_MARKER in prompt:
        return prompt

    audit_text = ""
    if audit_only:
        audit_text = """
AUDIT-ONLY FAST-PATH RULE:
- Do not modify files.
- Do not run build/commit/artifact phases.
- Prefer deterministic diagnostics: git status, link_doctor.py, link_healthcheck.py, and a short summary.
"""

    policy = f"""
[{POLICY_MARKER}]

ANTI-LOOP RULES:
- Do not retry the identical command/tool sequence blindly.
- After any failed command, diagnose the exact failure before trying a different tactic.
- If the same action fails twice, stop, summarize known state, name the missing info, and write/return a handoff instead of looping.
- Prefer direct file search/read/targeted patch before broad autonomous exploration.

OUTPUT LIMIT RULES:
- Do not inline very large command output.
- If output is too large, save it to .agents/tool_results/<run_id>/ and include only a preview/path.

FILE-SAFETY RULES:
- Skip binary/archive/generated files during audits unless explicitly requested.
- Do not inspect or merge from .agents/reports, .agents/worktrees, .git, node_modules, __pycache__, zip/db/sqlite/image/pdf/compiled files.

NON-TRIVIAL CHANGE RULE:
- 3+ file edits, backend/API/infra edits, or critical engine/web/healthcheck changes require an extra deterministic verification pass before safe tag update.
{audit_text}
[/LINK_ENGINE_POLICY_V2]
""".strip()

    return policy + "\n\n" + prompt
