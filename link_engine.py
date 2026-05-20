#!/usr/bin/env python3
"""Professional supervised run engine for Link.

Dependency-free engine layer above the existing orchestrator.

Responsibilities:
- clean repo preflight
- baseline/safe-tag tracking
- human-readable event stream
- noisy log filtering
- stuck-loop detection
- postflight healthcheck
- protected-file / huge-diff detection
- quarantine bad HEADs
- optional restore to baseline
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / ".agents" / "engine_runs"

RunStatus = Literal[
    "created",
    "preflight",
    "running",
    "verifying",
    "completed",
    "failed",
    "escalated",
    "blocked",
    "restored",
]
EventLevel = Literal["debug", "info", "success", "warning", "error"]

NOISE_PATTERNS = (
    re.compile(r"HTTP Request: POST .* /v1/chat/completions"),
    re.compile(r"^\s*$"),
)

PHASE_PATTERNS = (
    ("INITIALIZER", "Initializer"),
    ("PHASE 1: EXPLORE", "Explore"),
    ("PHASE 2: PLAN", "Plan"),
    ("PHASE 3: BUILD", "Build"),
    ("PHASE 4: TEST", "Verify"),
    ("DECISION", "Decision"),
)

PROTECTED_PATH_PREFIXES = (
    ".git/",
    ".agents/worktrees/",
    ".agents/reports/",
    ".agents/backups/",
    "research/",
    "venv/",
    ".venv/",
)

DEFAULT_PROTECTED_FILES = {
    "link_healthcheck.py",
    "modern_command_guard.py",
    "modern_file_safety.py",
    "modern_git_safety.py",
}


@dataclass
class EngineEvent:
    ts: float
    level: EventLevel
    title: str
    detail: str = ""
    phase: str = ""
    raw: str = ""


@dataclass
class EngineConfig:
    prompt: str
    max_iterations: int = 1
    worktree: bool = False
    timeout_seconds: int = 1800
    max_changed_files: int = 8
    min_changed_files: int = 0
    max_diff_lines: int = 1200
    auto_restore_on_failure: bool = False
    allow_protected_changes: bool = False
    protected_files: set[str] = field(default_factory=lambda: set(DEFAULT_PROTECTED_FILES))
    expected_changed_files: set[str] = field(default_factory=set)


@dataclass
class EngineState:
    run_id: str
    status: RunStatus = "created"
    phase: str = "created"
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    baseline_commit: str = ""
    baseline_safe_latest: str = ""
    final_commit: str = ""
    exit_code: int | None = None
    changed_files: list[str] = field(default_factory=list)
    diff_lines: int = 0
    events: list[EngineEvent] = field(default_factory=list)
    report_path: str = ""


class EngineError(RuntimeError):
    pass


class LinkEngine:

    def _write_live_report(self, state) -> None:
        """Best-effort live engine_report.json snapshot for web status polling."""
        try:
            run_id = getattr(state, "run_id", None) or getattr(state, "id", None) or "unknown"
            report_path = getattr(state, "report_path", None)
            if not report_path:
                run_dir = getattr(state, "run_dir", None)
                if run_dir:
                    report_path = Path(run_dir) / "engine_report.json"
                else:
                    report_path = self.root / ".agents" / "engine_runs" / str(run_id) / "engine_report.json"

            events = []
            for event in list(getattr(state, "events", [])):
                if isinstance(event, dict):
                    events.append(event)
                    continue
                events.append({
                    "ts": getattr(event, "ts", None),
                    "level": getattr(event, "level", ""),
                    "title": getattr(event, "title", ""),
                    "detail": getattr(event, "detail", ""),
                    "phase": getattr(event, "phase", ""),
                    "raw": getattr(event, "raw", ""),
                })

            payload = {
                "run_id": run_id,
                "status": getattr(state, "status", None),
                "phase": getattr(state, "phase", None),
                "started_at": getattr(state, "started_at", None),
                "ended_at": getattr(state, "ended_at", None),
                "baseline_commit": getattr(state, "baseline_commit", None),
                "baseline_safe_latest": getattr(state, "baseline_safe_latest", None),
                "final_commit": getattr(state, "final_commit", None),
                "exit_code": getattr(state, "exit_code", None),
                "changed_files": list(getattr(state, "changed_files", []) or []),
                "diff_lines": getattr(state, "diff_lines", None),
                "events": events,
                "report_path": str(report_path),
                "live_snapshot": True,
                "live_snapshot_at": time.time(),
            }

            report_path = Path(report_path)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            # Never let diagnostics break the supervised engine.
            return


    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        RUNS_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, config: EngineConfig) -> EngineState:
        state = EngineState(run_id=uuid.uuid4().hex[:8])
        report_dir = RUNS_DIR / state.run_id
        report_dir.mkdir(parents=True, exist_ok=True)
        state.report_path = str(report_dir / "engine_report.json")

        self._event(state, "info", "Run created", f"Run {state.run_id}")

        try:
            self._preflight(state)
            self._execute_orchestrator(state, config)
            self._postflight(state, config)
        except EngineError as exc:
            state.status = "blocked" if state.status in {"created", "preflight"} else "failed"
            self._event(state, "error", "Engine stopped", str(exc))
        except KeyboardInterrupt:
            state.status = "failed"
            self._event(state, "warning", "Interrupted", "User interrupted the run")
        finally:
            state.ended_at = time.time()
            self._write_report(state)

        return state

    def _preflight(self, state: EngineState) -> None:
        state.status = "preflight"
        state.phase = "preflight"
        self._event(state, "info", "Preflight started", "Checking clean repo and baseline")

        state.baseline_commit = self._git(["rev-parse", "--short", "HEAD"])
        state.baseline_safe_latest = self._git(["rev-parse", "--short", "safe-link-latest"], check=False) or "missing"

        dirty = self._git(["status", "--porcelain", "--untracked-files=all"])
        if dirty.strip():
            raise EngineError("Repo is dirty before run. Stop and inspect git status first.")

        health = self._cmd([sys.executable, "link_healthcheck.py"], timeout=120)
        if health.returncode != 0:
            raise EngineError("Preflight healthcheck failed. Do not run agents.")

        self._event(
            state,
            "success",
            "Preflight passed",
            f"HEAD {state.baseline_commit}; safe-link-latest {state.baseline_safe_latest}",
        )

    def _execute_orchestrator(self, state: EngineState, config: EngineConfig) -> None:
        state.status = "running"
        state.phase = "running"

        cmd = [
            sys.executable,
            str(self.root / "standalone_main.py"),
            config.prompt,
            "--max-iterations",
            str(config.max_iterations),
        ]
        if config.worktree:
            cmd.append("--worktree")

        self._event(state, "info", "Orchestrator started", " ".join(self._redact_cmd(cmd)))

        proc = subprocess.Popen(
            cmd,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )

        start = time.time()
        repeated: dict[str, int] = {}

        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                if time.time() - start > config.timeout_seconds:
                    self._terminate(proc)
                    raise EngineError(f"Run exceeded timeout of {config.timeout_seconds}s")

                clean = strip_ansi(line).rstrip()
                self._classify_line(state, clean, repeated)

                if repeated.get(clean, 0) >= 8 and clean:
                    self._terminate(proc)
                    raise EngineError("Repeated output detected; killed likely stuck run")

            proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                self._terminate(proc)

        state.exit_code = proc.returncode

        if proc.returncode == 0:
            self._event(state, "success", "Process exited cleanly", "Exit code 0")
        else:
            self._event(state, "warning", "Process exited with failure", f"Exit code {proc.returncode}")

    def _postflight(self, state: EngineState, config: EngineConfig) -> None:
        state.status = "verifying"
        state.phase = "verifying"
        self._event(state, "info", "Postflight started", "Inspecting changed files and healthcheck")

        state.final_commit = self._git(["rev-parse", "--short", "HEAD"], check=False) or "unknown"

        uncommitted_changed = parse_name_status(
            self._git(["diff", "--name-only", "HEAD"], check=False)
        )
        committed_changed = parse_name_status(
            self._git(["diff", "--name-only", f"{state.baseline_commit}..HEAD"], check=False)
        )

        all_changed = sorted(set(uncommitted_changed) | set(committed_changed))
        state.changed_files = all_changed

        committed_stat = self._git(["diff", "--stat", f"{state.baseline_commit}..HEAD"], check=False)
        uncommitted_stat = self._git(["diff", "--stat", "HEAD"], check=False)
        state.diff_lines = count_diff_lines(committed_stat) + count_diff_lines(uncommitted_stat)

        violations = []

        if len(all_changed) > config.max_changed_files:
            violations.append(f"changed too many files: {len(all_changed)} > {config.max_changed_files}")

        if len(all_changed) < config.min_changed_files:
            violations.append(f"changed too few files: {len(all_changed)} < {config.min_changed_files}")

        if config.expected_changed_files:
            changed_set = set(all_changed)
            missing_expected = sorted(config.expected_changed_files - changed_set)
            unexpected = sorted(changed_set - config.expected_changed_files)
            if missing_expected:
                violations.append("expected files not changed: " + ", ".join(missing_expected[:12]))
            if unexpected:
                violations.append("unexpected files changed: " + ", ".join(unexpected[:12]))

        if state.diff_lines > config.max_diff_lines:
            violations.append(f"diff too large: {state.diff_lines} > {config.max_diff_lines}")

        if not config.allow_protected_changes:
            protected = [p for p in all_changed if is_protected_path(p, config.protected_files)]
            if protected:
                violations.append("protected files changed: " + ", ".join(protected[:12]))

        health = self._cmd([sys.executable, "link_healthcheck.py"], timeout=120)
        if health.returncode != 0:
            violations.append("healthcheck failed after run")

        if state.exit_code != 0:
            violations.append(f"orchestrator exit code was {state.exit_code}")

        if violations:
            self._event(state, "error", "Postflight failed", "; ".join(violations))
            self._quarantine_if_needed(state)
            self._restore_safe_latest_tag(state)

            if config.auto_restore_on_failure:
                self._restore_baseline(state)

            state.status = "failed" if state.status != "restored" else "restored"
            return

        if state.final_commit and state.final_commit != "unknown":
            self._cmd(["git", "tag", "-f", "safe-link-latest", "HEAD"], timeout=30)

        self._event(state, "success", "Postflight passed", f"Approved HEAD {state.final_commit}")
        state.status = "completed"

    def _quarantine_if_needed(self, state: EngineState) -> None:
        head = self._git(["rev-parse", "--short", "HEAD"], check=False) or ""
        if not head or head == state.baseline_commit:
            return

        tag = f"quarantine-engine-{state.run_id}-{head}"
        self._cmd(["git", "tag", "-f", tag, "HEAD"], timeout=30)
        self._event(state, "warning", "Quarantined unapproved HEAD", tag)

    def _restore_safe_latest_tag(self, state: EngineState) -> None:
        if not state.baseline_safe_latest or state.baseline_safe_latest == "missing":
            return

        self._cmd(["git", "tag", "-f", "safe-link-latest", state.baseline_safe_latest], timeout=30)
        self._event(state, "warning", "Restored safe-link-latest tag", state.baseline_safe_latest)

    def _restore_baseline(self, state: EngineState) -> None:
        if not state.baseline_commit:
            return

        self._cmd(["git", "reset", "--hard", state.baseline_commit], timeout=60)
        state.status = "restored"
        self._event(state, "warning", "Restored baseline", state.baseline_commit)

    def _classify_line(self, state: EngineState, line: str, repeated: dict[str, int]) -> None:
        if not line:
            return

        repeated[line] = repeated.get(line, 0) + 1

        if any(p.search(line) for p in NOISE_PATTERNS):
            return

        for marker, phase in PHASE_PATTERNS:
            if marker in line:
                state.phase = phase.lower()
                self._event(state, "info", f"Phase: {phase}", raw=line)
                return

        upper = line.upper()

        if "TASK COMPLETED SUCCESSFULLY" in upper or "ALL DOD CRITERIA PASSED" in upper:
            self._event(state, "success", "Agent reported success", raw=line)
        elif "TASK ESCALATED" in upper or "STUCK LOOP" in upper:
            state.status = "escalated"
            self._event(state, "error", "Agent escalated", raw=line)
        elif "ERROR" in upper or "FATAL" in upper:
            self._event(state, "error", "Error", raw=line)
        elif "WARNING" in upper or "FAILED" in upper:
            self._event(state, "warning", "Warning", raw=line)
        elif "ORCHESTRATOR STARTING" in upper:
            self._event(state, "info", "Orchestrator booting", raw=line)
        elif "BUILD SEQUENCE" in upper:
            self._event(state, "info", "Build sequence selected", raw=line)
        elif "MICRO-BUILD" in upper:
            self._event(state, "info", "Micro-build progress", raw=line)

    def _event(
        self,
        state: EngineState,
        level: EventLevel,
        title: str,
        detail: str = "",
        phase: str = "",
        raw: str = "",
    ) -> None:
        event = EngineEvent(
            ts=time.time(),
            level=level,
            title=title,
            detail=detail,
            phase=phase or state.phase,
            raw=raw,
        )
        state.events.append(event)
        self._write_live_report(state)

        icon = {
            "debug": "·",
            "info": "•",
            "success": "✓",
            "warning": "!",
            "error": "✗",
        }[level]

        msg = f"{icon} {title}"
        if detail:
            msg += f" — {detail}"
        elif raw:
            msg += f" — {raw}"

        print(msg, flush=True)

    def _write_report(self, state: EngineState) -> None:
        payload = asdict(state)
        Path(state.report_path).write_text(json.dumps(payload, indent=2, default=str) + "\n")

    def _cmd(self, cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    def _git(self, args: list[str], check: bool = True) -> str:
        proc = self._cmd(["git", *args], timeout=60)

        if check and proc.returncode != 0:
            raise EngineError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")

        if proc.returncode != 0:
            return ""

        return proc.stdout.strip()

    def _terminate(self, proc: subprocess.Popen[str]) -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass

    def _redact_cmd(self, cmd: Iterable[str]) -> list[str]:
        out = []
        for part in cmd:
            if len(part) > 120:
                out.append("<prompt>")
            else:
                out.append(part)
        return out


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def parse_name_status(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def count_diff_lines(diff_stat: str) -> int:
    last = diff_stat.splitlines()[-1] if diff_stat.splitlines() else ""
    nums = [int(n) for n in re.findall(r"(\d+)\s+(?:insertion|deletion)", last)]
    return sum(nums)


def is_protected_path(path: str, protected_files: set[str]) -> bool:
    clean = path.strip().lstrip("./")
    if clean in protected_files:
        return True
    return any(clean.startswith(prefix) for prefix in PROTECTED_PATH_PREFIXES)


def self_test() -> int:
    engine = LinkEngine(ROOT)
    state = EngineState(run_id="selftest")

    engine._event(state, "info", "Self-test event")

    assert strip_ansi("\x1b[31mERROR\x1b[0m") == "ERROR"
    assert is_protected_path("link_healthcheck.py", set(DEFAULT_PROTECTED_FILES))
    assert is_protected_path("research/x.md", set())
    assert not is_protected_path("link_web.py", set(DEFAULT_PROTECTED_FILES))
    assert count_diff_lines(" 1 file changed, 3 insertions(+), 2 deletions(-)") == 5

    print("LINK ENGINE SELF-TEST PASSED")
    return 0


def read_prompt(args: argparse.Namespace) -> str:
    if getattr(args, "prompt_file", None):
        return Path(args.prompt_file).read_text()
    return args.prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supervised Link run engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--prompt", default="")
    run_p.add_argument("--prompt-file")
    run_p.add_argument("--max-iterations", type=int, default=1)
    run_p.add_argument("--worktree", action="store_true")
    run_p.add_argument("--timeout-seconds", type=int, default=1800)
    run_p.add_argument("--max-changed-files", type=int, default=8)
    run_p.add_argument("--max-diff-lines", type=int, default=1200)
    run_p.add_argument("--auto-restore-on-failure", action="store_true")
    run_p.add_argument("--min-changed-files", type=int, default=0)
    run_p.add_argument("--expect-changed-file", action="append", default=[])
    run_p.add_argument("--allow-protected-changes", action="store_true")

    sub.add_parser("self-test")

    args = parser.parse_args(argv)

    if args.cmd == "self-test":
        return self_test()

    prompt = read_prompt(args)
    if not prompt.strip():
        print("ERROR: provide --prompt or --prompt-file", file=sys.stderr)
        return 2

    config = EngineConfig(
        prompt=prompt,
        max_iterations=args.max_iterations,
        worktree=args.worktree,
        timeout_seconds=args.timeout_seconds,
        max_changed_files=args.max_changed_files,
        min_changed_files=args.min_changed_files,
        max_diff_lines=args.max_diff_lines,
        auto_restore_on_failure=args.auto_restore_on_failure,
        allow_protected_changes=args.allow_protected_changes,
        expected_changed_files=set(args.expect_changed_file or []),
    )

    state = LinkEngine(ROOT).run(config)
    print(f"Report: {state.report_path}")

    return 0 if state.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
