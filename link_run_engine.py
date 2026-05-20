#!/usr/bin/env python3
"""Structured run engine for Link.

This module wraps standalone_main.py and turns noisy process output into
small, human-friendly events for the web UI.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Deque, Optional


ROOT = Path(__file__).resolve().parent
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class LinkEvent:
    ts: float
    run_id: str
    kind: str
    message: str
    raw: str = ""
    visible: bool = True


class LinkRun:
    def __init__(self, run_id: str, prompt: str, max_iterations: int = 1) -> None:
        self.run_id = run_id
        self.prompt = prompt
        self.max_iterations = max_iterations
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self.returncode: Optional[int] = None
        self.status = "starting"
        self.process: Optional[subprocess.Popen[str]] = None
        self.thread: Optional[threading.Thread] = None
        self.events: Deque[LinkEvent] = deque(maxlen=1000)
        self.raw_lines: Deque[str] = deque(maxlen=3000)
        self.lock = threading.Lock()

    def add_event(self, kind: str, message: str, raw: str = "", visible: bool = True) -> None:
        event = LinkEvent(
            ts=time.time(),
            run_id=self.run_id,
            kind=kind,
            message=message,
            raw=raw,
            visible=visible,
        )
        with self.lock:
            self.events.append(event)
            if raw:
                self.raw_lines.append(raw)

    def snapshot(self, include_raw: bool = False) -> dict:
        with self.lock:
            data = {
                "run_id": self.run_id,
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "returncode": self.returncode,
                "events": [asdict(e) for e in self.events if e.visible],
            }
            if include_raw:
                data["raw_lines"] = list(self.raw_lines)
            return data


class LinkRunEngine:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.runs: dict[str, LinkRun] = {}
        self.active_run_id: Optional[str] = None
        self.lock = threading.Lock()

    def start(self, prompt: str, max_iterations: int = 1) -> dict:
        prompt = (prompt or "").strip()
        if not prompt:
            return {"ok": False, "error": "Prompt is empty"}

        with self.lock:
            if self.active_run_id:
                active = self.runs.get(self.active_run_id)
                if active and active.status in {"starting", "running"}:
                    return {"ok": False, "error": f"Run already active: {self.active_run_id}"}

            run_id = uuid.uuid4().hex[:8]
            run = LinkRun(run_id=run_id, prompt=prompt, max_iterations=max_iterations)
            self.runs[run_id] = run
            self.active_run_id = run_id

        thread = threading.Thread(target=self._worker, args=(run,), daemon=True)
        run.thread = thread
        thread.start()

        return {"ok": True, "run_id": run_id}

    def stop(self, run_id: Optional[str] = None) -> dict:
        run = self._get_run(run_id)
        if not run:
            return {"ok": False, "error": "No run found"}

        with run.lock:
            proc = run.process
            run.status = "stopping"

        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        run.add_event("warning", "Run stopped by user")
        with run.lock:
            run.status = "stopped"
            run.finished_at = time.time()
            run.returncode = proc.returncode if proc else None

        with self.lock:
            if self.active_run_id == run.run_id:
                self.active_run_id = None

        return {"ok": True, "run_id": run.run_id}

    def snapshot(self, run_id: Optional[str] = None, include_raw: bool = False) -> dict:
        run = self._get_run(run_id)
        if not run:
            return {"ok": False, "error": "No run found", "active_run_id": self.active_run_id}
        data = run.snapshot(include_raw=include_raw)
        data["ok"] = True
        return data

    def _get_run(self, run_id: Optional[str]) -> Optional[LinkRun]:
        with self.lock:
            rid = run_id or self.active_run_id
            return self.runs.get(rid) if rid else None

    def _worker(self, run: LinkRun) -> None:
        cmd = [
            sys.executable,
            str(self.root / "standalone_main.py"),
            run.prompt,
            "--max-iterations",
            str(run.max_iterations),
        ]

        run.status = "running"
        run.add_event("start", "Run started")
        run.add_event("command", "Starting Link orchestrator", raw=" ".join(cmd), visible=False)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=self.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            run.process = proc

            assert proc.stdout is not None
            for line in proc.stdout:
                clean = ANSI_RE.sub("", line.rstrip())
                if not clean:
                    continue
                self._handle_line(run, clean)

            proc.wait()
            with run.lock:
                run.returncode = proc.returncode
                run.finished_at = time.time()

            if proc.returncode == 0:
                run.status = "completed"
                run.add_event("success", "Run completed successfully")
            else:
                run.status = "failed"
                run.add_event("error", f"Run failed with exit code {proc.returncode}")

        except Exception as exc:
            run.status = "failed"
            run.finished_at = time.time()
            run.add_event("error", f"Engine error: {exc}")

        finally:
            with self.lock:
                if self.active_run_id == run.run_id:
                    self.active_run_id = None

    def _handle_line(self, run: LinkRun, line: str) -> None:
        lower = line.lower()

        # Hide low-value transport noise.
        if "http request:" in lower or "httpx" in lower:
            run.add_event("raw", "model/backend request", raw=line, visible=False)
            return

        # Human-friendly phase events.
        if "orchestrator starting" in lower:
            run.add_event("phase", "Orchestrator started", raw=line)
        elif "running initializer phase" in lower:
            run.add_event("phase", "Preparing task", raw=line)
        elif "phase 1: explore" in lower:
            run.add_event("phase", "Exploring files", raw=line)
        elif "phase 2: plan" in lower:
            run.add_event("phase", "Planning changes", raw=line)
        elif "phase 3: build" in lower:
            run.add_event("phase", "Applying changes", raw=line)
        elif "phase 4: test" in lower or "test (verify)" in lower:
            run.add_event("phase", "Verifying result", raw=line)
        elif "link healthcheck passed" in lower:
            run.add_event("success", "Healthcheck passed", raw=line)
        elif "task completed successfully" in lower:
            run.add_event("success", "Task completed", raw=line)
        elif "task escalated to human" in lower:
            run.add_event("error", "Needs human review", raw=line)
        elif "stuck loop detected" in lower:
            run.add_event("warning", "Agent got stuck in a loop", raw=line)
        elif "dod failed" in lower:
            run.add_event("warning", "Verification failed", raw=line)
        elif "fatal error" in lower or " error " in f" {lower} ":
            run.add_event("error", line, raw=line)
        elif "warning" in lower:
            run.add_event("warning", line, raw=line)
        elif "wrote artifact manifest" in lower:
            run.add_event("artifact", "Saved run artifact", raw=line)
        elif "commit" in lower and ("feat:" in lower or "fix:" in lower):
            run.add_event("commit", line, raw=line)
        else:
            # Keep raw line but do not spam the human journal.
            run.add_event("raw", line, raw=line, visible=False)


ENGINE = LinkRunEngine()


def main() -> int:
    print(json.dumps({"ok": True, "engine": "link_run_engine", "root": str(ROOT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
