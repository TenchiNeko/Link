#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RUN_ROOT = ROOT / ".agents" / "engine_runs"

ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".csv"}
DENY_PARTS = {".git", ".agents", "__pycache__", "node_modules", ".venv", "venv", "research"}

FILE_RE = re.compile(r"`([^`]+\.(?:md|txt|json|csv))`|(?<![\w./-])([A-Za-z0-9_./-]+\.(?:md|txt|json|csv))")
CONTENT_PATTERNS = [
    re.compile(r"""single line\s+(?:saying|containing)\s+["'“”]([^"'“”]+)["'“”]""", re.I),
    re.compile(r"""(?:to|that should)\s+say\s+["'“”]([^"'“”]+)["'“”]""", re.I),
    re.compile(r"""with\s+(?:the\s+)?(?:text|content|line)\s+["'“”]([^"'“”]+)["'“”]""", re.I),
    re.compile(r"""containing\s+["'“”]([^"'“”]+)["'“”]""", re.I),
]


def run(cmd: list[str], *, check: bool = False, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed with {cp.returncode}\n{cp.stdout}")
    return cp


def git_status() -> str:
    return run(["git", "status", "--porcelain", "--untracked-files=all"]).stdout.strip()


def git_head() -> str:
    return run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()


def safe_latest() -> str:
    cp = run(["git", "rev-parse", "--short", "safe-link-latest"])
    return cp.stdout.strip() if cp.returncode == 0 else ""


def parse_target(prompt: str) -> str:
    candidates: list[str] = []
    for match in FILE_RE.finditer(prompt):
        value = match.group(1) or match.group(2)
        if not value:
            continue
        value = value.strip()
        if value.startswith("/") or ".." in Path(value).parts:
            continue
        suffix = Path(value).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            continue
        if any(part in DENY_PARTS for part in Path(value).parts):
            continue
        candidates.append(value)

    unique = []
    for item in candidates:
        if item not in unique:
            unique.append(item)

    if len(unique) != 1:
        raise ValueError(f"Expected exactly one safe target file, found: {unique}")
    return unique[0]


def parse_content(prompt: str) -> str:
    for pattern in CONTENT_PATTERNS:
        match = pattern.search(prompt)
        if match:
            line = match.group(1).strip()
            line = line.replace("\\n", " ").replace("\r", " ").replace("\n", " ").strip()
            if line:
                return line + "\n"
    raise ValueError("Could not find the requested single-line content. Use: single line saying \"...\"")


def safe_path(rel: str) -> Path:
    path = (ROOT / rel).resolve()
    root = ROOT.resolve()
    if path == root or not str(path).startswith(str(root) + os.sep):
        raise ValueError(f"Target escapes repo root: {rel}")
    if any(part in DENY_PARTS for part in path.relative_to(root).parts):
        raise ValueError(f"Target is protected: {rel}")
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(f"Micro patch only allows {sorted(ALLOWED_SUFFIXES)} files")
    return path


class Reporter:
    def __init__(self, run_id: str, prompt: str) -> None:
        self.run_id = run_id
        self.prompt = prompt
        self.started_at = time.time()
        self.events: list[dict[str, Any]] = []
        self.run_dir = RUN_ROOT / run_id
        self.report_path = self.run_dir / "engine_report.json"
        self.status = "created"
        self.phase = "created"
        self.exit_code: int | None = None
        self.changed_files: list[str] = []
        self.diff_lines = 0
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def event(self, level: str, title: str, detail: str = "", *, phase: str | None = None, raw: str = "") -> None:
        if phase:
            self.phase = phase
        item = {
            "ts": time.time(),
            "level": level,
            "title": title,
            "detail": detail,
            "phase": self.phase,
            "raw": raw,
        }
        self.events.append(item)
        prefix = {"info": "•", "success": "✓", "warning": "!", "error": "✗"}.get(level, "•")
        print(f"{prefix} {title}" + (f" — {detail}" if detail else ""), flush=True)
        self.write()

    def write(self) -> None:
        payload = {
            "run_id": self.run_id,
            "status": self.status,
            "phase": self.phase,
            "started_at": self.started_at,
            "ended_at": time.time() if self.status in {"completed", "failed"} else None,
            "baseline_commit": None,
            "baseline_safe_latest": None,
            "final_commit": None,
            "exit_code": self.exit_code,
            "changed_files": self.changed_files,
            "diff_lines": self.diff_lines,
            "events": self.events,
            "report_path": str(self.report_path),
        }
        self.report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def changed_files() -> list[str]:
    out = git_status()
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip())
    return files


def diff_line_count() -> int:
    cp = run(["git", "diff", "--numstat"])
    total = 0
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            for value in parts[:2]:
                if value.isdigit():
                    total += int(value)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic safe micro patcher for simple one-file text updates.")
    parser.add_argument("--prompt-file", required=True)
    args = parser.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8", errors="replace")
    run_id = "micro-" + uuid.uuid4().hex[:12]
    reporter = Reporter(run_id, prompt)

    original_path: Path | None = None
    original_text: str | None = None
    existed = False

    try:
        reporter.status = "running"
        reporter.event("info", "Micro patch started", run_id, phase="micro")

        dirty = git_status()
        if dirty:
            raise RuntimeError("Repo must be clean before micro patch:\n" + dirty)

        rel = parse_target(prompt)
        content = parse_content(prompt)
        target = safe_path(rel)

        original_path = target
        existed = target.exists()
        original_text = target.read_text(encoding="utf-8", errors="replace") if existed else None

        reporter.event("info", "Target selected", rel, phase="micro")
        target.parent.mkdir(parents=True, exist_ok=True)

        if existed and original_text == content:
            reporter.status = "completed"
            reporter.exit_code = 0
            reporter.changed_files = []
            reporter.event("success", "No change needed", rel, phase="micro")
            reporter.write()
            return 0

        target.write_text(content, encoding="utf-8")
        reporter.changed_files = changed_files()
        reporter.diff_lines = diff_line_count()
        reporter.event("info", "File written", f"{rel}; changed={reporter.changed_files}", phase="micro")

        bad = [name for name in reporter.changed_files if name != rel]
        if bad:
            raise RuntimeError(f"Unexpected changed files: {bad}")

        health = run([sys.executable, str(ROOT / "link_healthcheck.py")], timeout=180)
        if health.returncode != 0:
            raise RuntimeError("healthcheck failed:\n" + health.stdout)
        reporter.event("success", "Healthcheck passed", "pre-commit", phase="verifying", raw=health.stdout)

        run(["git", "add", "--", rel], check=True)
        commit_msg = f"micro: update {rel}"
        commit = run(["git", "commit", "-m", commit_msg], timeout=120)
        if commit.returncode != 0:
            raise RuntimeError("git commit failed:\n" + commit.stdout)

        run(["git", "tag", "-f", "safe-link-latest", "HEAD"], check=True)
        reporter.status = "completed"
        reporter.exit_code = 0
        reporter.changed_files = []
        reporter.diff_lines = 0
        reporter.event("success", "Micro patch committed", git_head(), phase="completed", raw=commit.stdout)
        reporter.write()
        return 0

    except Exception as exc:
        reporter.status = "failed"
        reporter.exit_code = 1
        reporter.event("error", "Micro patch failed", str(exc), phase="failed")

        if original_path is not None:
            try:
                if existed:
                    original_path.write_text(original_text or "", encoding="utf-8")
                elif original_path.exists():
                    original_path.unlink()
                run(["git", "restore", "--staged", "--", str(original_path.relative_to(ROOT))])
            except Exception:
                pass

        reporter.changed_files = changed_files()
        reporter.diff_lines = diff_line_count()
        reporter.write()
        print(f"Micro patch report: {reporter.report_path}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
