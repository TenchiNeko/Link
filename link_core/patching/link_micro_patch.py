#!/usr/bin/env python3
from __future__ import annotations

"""
Deterministic safe micro patcher.

Purpose:
- Handle simple one-file text writes without invoking the full autonomous engine.
- Avoid loops for tiny "create/update a .md/.txt/.json/.csv with one line" tasks.
- Commit the deterministic change after healthcheck.
- Force-add ignored safe text targets only after path/suffix validation.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / ".agents" / "engine_runs"

ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".csv"}
DENY_PARTS = {
    ".git",
    ".agents",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "research",
}

FILE_RE = re.compile(
    r"`([^`]+\.(?:md|txt|json|csv))`|(?:\b(?:target\s+file|target|file|path)\s*(?::|=|-|is|should be)?\s*`?|(?<![\w./-]))([A-Za-z0-9_./-]+\.(?:md|txt|json|csv))`?",
    re.I,
)

CONTENT_PATTERNS = [
    re.compile(r'(?:single line\s+(?:saying|containing)|saying|containing)\s+["“](.*?)["”]', re.I | re.S),
    re.compile(r"(?:single line\s+(?:saying|containing)|saying|containing)\s+'(.*?)'", re.I | re.S),
    re.compile(r"(?:content|contents|text)\s*:\s*`([^`]+)`", re.I | re.S),
    re.compile(r'(?:content|contents|text)\s*:\s*["“](.*?)["”]', re.I | re.S),
]


def run(cmd: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def git(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], timeout=timeout)


def relpath_from_prompt(prompt: str) -> Path:
    candidates: list[str] = []
    for match in FILE_RE.finditer(prompt):
        value = match.group(1) or match.group(2)
        if value:
            candidates.append(value.strip())

    unique: list[str] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)

    if len(unique) != 1:
        raise ValueError(f"Expected exactly one safe target file, found {len(unique)}: {unique}")

    rel = Path(unique[0])
    validate_relpath(rel)
    return rel


def validate_relpath(rel: Path) -> None:
    if rel.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    parts = rel.parts
    if ".." in parts:
        raise ValueError("Parent traversal is not allowed")

    if any(part in DENY_PARTS for part in parts):
        raise ValueError(f"Target path contains denied path component: {rel}")

    if rel.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(f"Only {sorted(ALLOWED_SUFFIXES)} targets are allowed")

    resolved = (ROOT / rel).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Target resolves outside repo root") from exc


def content_from_prompt(prompt: str) -> str:
    for pattern in CONTENT_PATTERNS:
        match = pattern.search(prompt)
        if match:
            return normalize_one_line(match.group(1))

    raise ValueError(
        "Could not find target content. Use wording like: "
        'Create or update file.md with a single line saying "text here"'
    )


def normalize_one_line(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    if not value:
        raise ValueError("Content cannot be empty")
    return value + "\n"


class Reporter:
    def __init__(self, run_id: str, prompt: str) -> None:
        self.run_id = run_id
        self.prompt = prompt
        self.run_dir = RUN_ROOT / run_id
        self.report_path = self.run_dir / "engine_report.json"
        self.events: list[dict[str, Any]] = []
        self.started_at = time.time()
        self.status = "running"
        self.phase = "micro"
        self.exit_code: int | None = None
        self.changed_files: list[str] = []
        self.commit: str | None = None
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, level: str, title: str, detail: str = "", *, raw: str = "") -> None:
        event = {
            "ts": time.time(),
            "level": level,
            "title": title,
            "detail": detail,
            "phase": self.phase,
            "raw": raw,
        }
        self.events.append(event)
        prefix = {
            "success": "✓",
            "error": "✗",
            "warning": "!",
            "info": "•",
        }.get(level, "•")
        if detail:
            print(f"{prefix} {title} — {detail}", flush=True)
        else:
            print(f"{prefix} {title}", flush=True)
        self.write_report()

    def write_report(self) -> None:
        payload = {
            "run_id": self.run_id,
            "status": self.status,
            "phase": self.phase,
            "started_at": self.started_at,
            "ended_at": time.time() if self.status in {"completed", "failed"} else None,
            "exit_code": self.exit_code,
            "changed_files": self.changed_files,
            "final_commit": self.commit,
            "events": self.events,
            "report_path": str(self.report_path),
            "micro_patch": True,
        }
        self.report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def complete(self, changed_files: list[str], commit: str | None, detail: str) -> int:
        self.status = "completed"
        self.exit_code = 0
        self.changed_files = changed_files
        self.commit = commit
        self.emit("success", "Micro patch completed", detail)
        self.write_report()
        print(f"Micro patch report: {self.report_path}", flush=True)
        return 0

    def fail(self, detail: str, *, raw: str = "") -> int:
        self.status = "failed"
        self.exit_code = 1
        self.emit("error", "Micro patch failed", detail, raw=raw)
        self.write_report()
        print(f"Micro patch report: {self.report_path}", flush=True)
        return 1


def ensure_clean_repo() -> None:
    cp = git("status", "--porcelain", "--untracked-files=all")
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr or cp.stdout)
    if cp.stdout.strip():
        raise RuntimeError("Repo is dirty before micro patch:\n" + cp.stdout)


def is_ignored(rel: Path) -> bool:
    cp = git("check-ignore", "-q", "--", str(rel))
    return cp.returncode == 0


def staged_files_for(rel: Path) -> list[str]:
    cp = git("diff", "--cached", "--name-only", "--", str(rel))
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr or cp.stdout)
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def run_healthcheck() -> str:
    cp = run([sys.executable, str(ROOT / "link_healthcheck.py")], timeout=180)
    output = (cp.stdout + cp.stderr).strip()
    if cp.returncode != 0:
        raise RuntimeError(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    args = parser.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    run_id = "micro-" + uuid.uuid4().hex[:12]
    report = Reporter(run_id, prompt)

    try:
        report.emit("info", "Micro patch started", run_id)

        ensure_clean_repo()

        rel = relpath_from_prompt(prompt)
        content = content_from_prompt(prompt)
        target = ROOT / rel

        report.emit("info", "Target selected", str(rel))

        target.parent.mkdir(parents=True, exist_ok=True)
        before = target.read_text(encoding="utf-8") if target.exists() else None
        target.write_text(content, encoding="utf-8")

        ignored = is_ignored(rel)
        if ignored:
            report.emit("warning", "Target is gitignored", f"{rel}; using safe force-add for validated text file")

        changed_on_disk = before != content
        report.emit(
            "info",
            "File written",
            f"{rel}; changed_on_disk={changed_on_disk}",
        )

        health = run_healthcheck()
        report.emit("success", "Healthcheck passed", "pre-commit", raw=health[:4000])

        add_cp = git("add", "-f", "--", str(rel))
        if add_cp.returncode != 0:
            return report.fail(
                f"git add -f -- {rel} failed with {add_cp.returncode}",
                raw=(add_cp.stdout + add_cp.stderr).strip(),
            )

        staged = staged_files_for(rel)
        if not staged:
            return report.complete([], None, f"No staged change for {rel}; content already current")

        commit_cp = git("commit", "-m", f"LINK: micro patch {rel}")
        commit_output = (commit_cp.stdout + commit_cp.stderr).strip()
        if commit_cp.returncode != 0:
            if "nothing to commit" in commit_output.lower():
                return report.complete([], None, f"No commit needed for {rel}")
            return report.fail(
                f"git commit failed with {commit_cp.returncode}",
                raw=commit_output,
            )

        rev_cp = git("rev-parse", "--short", "HEAD")
        commit = rev_cp.stdout.strip() if rev_cp.returncode == 0 else None

        tag_cp = git("tag", "-f", "safe-link-latest", "HEAD")
        if tag_cp.returncode != 0:
            return report.fail(
                "failed to update safe-link-latest",
                raw=(tag_cp.stdout + tag_cp.stderr).strip(),
            )

        final_health = run_healthcheck()
        report.emit("success", "Healthcheck passed", "post-commit", raw=final_health[:4000])

        # Marker required by healthcheck: Micro patch committed
        return report.complete(staged, commit, f"Micro patch committed {commit or ''}".strip())

    except Exception as exc:
        return report.fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
