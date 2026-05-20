#!/usr/bin/env python3
"""
Local Link web console.

A tiny no-dependency browser UI:
- prompt box at bottom
- live agent journal above
- Run / Stop buttons
- audit-only toggle and engine safety wrapper
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from link_runtime_policy import build_policy_prompt, compact_status_event, is_micro_patch_prompt


ROOT = Path(__file__).resolve().parent
# healthcheck marker: str(ROOT / "link_engine.py") via link_autonomous.py
RUNS: dict[str, "RunState"] = {}
RUNS_LOCK = threading.Lock()
MAX_STORED_LINES = 5000


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Link Console</title>
<style>
:root {
  color-scheme: dark;
  --bg: #0d1117;
  --panel: #111827;
  --muted: #9ca3af;
  --text: #e5e7eb;
  --border: #263244;
  --accent: #60a5fa;
  --danger: #f87171;
  --ok: #34d399;
  --warn: #fbbf24;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: rgba(13, 17, 23, 0.96);
}
h1 { margin: 0; font-size: 17px; font-weight: 700; }
.small { color: var(--muted); font-size: 12px; }
.status {
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--muted);
}
.status.running { color: var(--warn); border-color: var(--warn); }
.status.done { color: var(--ok); border-color: var(--ok); }
.status.failed { color: var(--danger); border-color: var(--danger); }
main { padding: 14px 14px 210px; }
#journal {
  min-height: calc(100vh - 260px);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  line-height: 1.45;
}
.line {
  padding: 2px 0;
  border-bottom: 1px solid rgba(38, 50, 68, 0.25);
}
.line.system { color: var(--accent); }
.line.warn { color: var(--warn); }
.line.error { color: var(--danger); }
.composer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 3;
  border-top: 1px solid var(--border);
  background: rgba(17, 24, 39, 0.98);
  padding: 12px;
}
textarea {
  width: 100%;
  min-height: 92px;
  resize: vertical;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  background: #070b12;
  color: var(--text);
  outline: none;
  font: inherit;
  line-height: 1.35;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: 10px;
}
button {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 9px 13px;
  background: #1f2937;
  color: var(--text);
  cursor: pointer;
  font-weight: 650;
}
button.primary { background: #1d4ed8; border-color: #2563eb; }
button.danger { background: #7f1d1d; border-color: #991b1b; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
label {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 13px;
}
input[type="number"] {
  width: 70px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 7px;
  background: #070b12;
  color: var(--text);
}
kbd {
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 5px;
  padding: 1px 5px;
  color: var(--muted);
}
</style>
</head>
<body>
<header>
  <div>
    <h1>Link Console</h1>
    <div class="small">Prompt at the bottom. Agent journal streams above.</div>
  </div>
  <div id="status" class="status">idle</div>
</header>

<main>
  <div id="journal"></div>
</main>

<section class="composer">
  <textarea id="prompt" placeholder="Enter a task prompt for Link..."></textarea>
  <div class="controls">
    <button id="run" class="primary">Run</button>
    <button id="stop" class="danger" disabled>Stop</button>
    <label><input id="auditOnly" type="checkbox" checked /> Audit/read-only mode</label>
    <span title="Runs are supervised by link_engine.py with postflight checks and auto-restore.">Engine safety mode: on</span>
    <label>Max iterations <input id="maxIterations" type="number" min="1" max="20" value="1" /></label>
    <span class="small">Tip: Ctrl/Cmd + Enter runs.</span>
  </div>
</section>

<script>
let currentRunId = null;
let statusPollTimer = null;
let seenStatusEventKeys = new Set();
let eventSource = null;

const journal = document.getElementById("journal");
const statusEl = document.getElementById("status");
const promptEl = document.getElementById("prompt");
const runBtn = document.getElementById("run");
const stopBtn = document.getElementById("stop");

function setStatus(text, cls) {
  statusEl.className = "status" + (cls ? " " + cls : "");
  statusEl.textContent = text;
}

function appendLine(text, kind = "") {
  const div = document.createElement("div");
  div.className = "line" + (kind ? " " + kind : "");
  div.textContent = text;
  journal.appendChild(div);
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function closeStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function clearStatusPoller() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

function statusEventKey(event, index) {
  return [
    event.ts || "",
    event.kind || "",
    event.message || "",
    event.detail || "",
    event.raw || "",
    index
  ].join("|");
}

function appendStatusEvent(event) {
  const kind = event.kind || "system";
  const message = event.raw || [event.message, event.detail].filter(Boolean).join(" — ");
  if (message) {
    appendLine(message, kind);
  }
}

async function pollRunStatus() {
  if (!currentRunId) return;

  try {
    const res = await fetch("/api/run/" + currentRunId);
    if (!res.ok) return;

    const data = await res.json();
    const events = Array.isArray(data.events) ? data.events : [];

    events.forEach((event, index) => {
      const key = statusEventKey(event, index);
      if (seenStatusEventKeys.has(key)) return;
      seenStatusEventKeys.add(key);
      appendStatusEvent(event);
    });

    if (["completed", "failed", "stopped"].includes(data.status)) {
      clearStatusPoller();
    }
  } catch (err) {
    // SSE remains primary; polling is a fallback.
  }
}

function startStatusPoller() {
  clearStatusPoller();
  seenStatusEventKeys = new Set();
  statusPollTimer = setInterval(pollRunStatus, 1500);
  pollRunStatus();
}

async function runTask() {
  const prompt = promptEl.value.trim();
  if (!prompt) {
    appendLine("Enter a prompt first.", "warn");
    return;
  }

  closeStream();
  journal.innerHTML = "";
  setStatus("starting", "running");
  runBtn.disabled = true;
  stopBtn.disabled = false;

  const payload = {
    prompt,
    audit_only: document.getElementById("auditOnly").checked,
    max_iterations: Number(document.getElementById("maxIterations").value || "1")
  };

  const res = await fetch("/api/run", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const text = await res.text();
    appendLine("Failed to start: " + text, "error");
    setStatus("failed", "failed");
    runBtn.disabled = false;
    stopBtn.disabled = true;
    return;
  }

  const data = await res.json();
  currentRunId = data.run_id;
  appendLine("Started run " + currentRunId, "system");
  startStatusPoller();

  eventSource = new EventSource("/events/" + currentRunId);
  eventSource.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "line") {
      appendLine(msg.text, msg.kind || "");
    } else if (msg.type === "status") {
      setStatus(msg.status, msg.status === "running" ? "running" : msg.status === "done" ? "done" : "failed");
    } else if (msg.type === "done") {
      setStatus(msg.exit_code === 0 ? "done" : "failed", msg.exit_code === 0 ? "done" : "failed");
      runBtn.disabled = false;
      stopBtn.disabled = true;
      closeStream();
    }
  };
  eventSource.onerror = () => {
    appendLine("Log stream disconnected.", "warn");
    runBtn.disabled = false;
    stopBtn.disabled = true;
    closeStream();
  };
}

async function stopTask() {
  if (!currentRunId) return;
  await fetch("/api/stop/" + currentRunId, { method: "POST" });
  appendLine("Stop requested.", "warn");
}

runBtn.addEventListener("click", runTask);
stopBtn.addEventListener("click", stopTask);
promptEl.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    runTask();
  }
});
</script>
</body>
</html>
"""


class RunState:
    def __init__(self, prompt: str, command: list[str]) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.prompt = prompt
        self.command = command
        self.status = "queued"
        self.started_at = time.time()
        self.ended_at: float | None = None
        self.exit_code: int | None = None
        self.lines: list[dict[str, str]] = []
        self.process: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()

    def log(self, text: str, kind: str = "") -> None:
        with self.lock:
            self.lines.append({"text": text.rstrip("\n"), "kind": kind})
            if len(self.lines) > MAX_STORED_LINES:
                self.lines = self.lines[-MAX_STORED_LINES:]

    def snapshot_lines(self, start_index: int) -> tuple[int, list[dict[str, str]]]:
        with self.lock:
            lines = self.lines[start_index:]
            return len(self.lines), list(lines)


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, text: str, content_type: str = "text/plain") -> None:
    body = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type + "; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def classify_line(line: str) -> str:
    lower = line.lower()
    if "error" in lower or "failed" in lower or "traceback" in lower:
        return "error"
    if "warning" in lower or "blocked" in lower or "caution" in lower:
        return "warn"
    if "===" in line or "phase" in lower or "started" in lower:
        return "system"
    return ""


def run_process(state: RunState) -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    state.status = "running"
    shown_command = state.command[:2] + ["<prompt>"] + state.command[3:]
    state.log("Command: " + " ".join(shown_command), "system")

    try:
        process = subprocess.Popen(
            state.command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        state.process = process

        assert process.stdout is not None
        for line in process.stdout:
            state.log(line, classify_line(line))

        state.exit_code = process.wait()
        state.status = "completed" if state.exit_code == 0 else "failed"
        state.log(f"Run finished with exit code {state.exit_code}.", "system" if state.exit_code == 0 else "error")
    except Exception as exc:
        state.exit_code = 1
        state.status = "failed"
        state.log(f"Launcher error: {exc}", "error")
    finally:
        state.ended_at = time.time()


class Handler(BaseHTTPRequestHandler):
    server_version = "LinkWeb/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            text_response(self, 200, HTML, "text/html")
            return

        if parsed.path.startswith("/api/run/"):
            run_id = parsed.path.rsplit("/", 1)[-1]
            self.run_status(run_id)
            return

        if parsed.path.startswith("/events/"):
            run_id = parsed.path.rsplit("/", 1)[-1]
            self.stream_events(run_id)
            return

        if parsed.path == "/api/runs":
            with RUNS_LOCK:
                payload = [
                    {
                        "run_id": r.id,
                        "status": r.status,
                        "started_at": r.started_at,
                        "ended_at": r.ended_at,
                        "exit_code": r.exit_code,
                    }
                    for r in RUNS.values()
                ]
            json_response(self, 200, payload)
            return

        text_response(self, 404, "not found")

    def find_engine_report_for_run(self, run) -> tuple[str | None, dict[str, object] | None]:
        report_root = ROOT / ".agents" / "engine_runs"
        if not report_root.exists():
            return None, None

        run_started = float(getattr(run, "started_at", 0) or 0)
        run_ended = float(getattr(run, "ended_at", 0) or time.time())

        candidates = sorted(
            report_root.glob("*/engine_report.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for report_path in candidates[:30]:
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            report_started = float(data.get("started_at") or 0)
            report_ended = float(data.get("ended_at") or report_started or 0)

            # Match reports created during this web run window, with small clock/process slack.
            if report_started and report_started < run_started - 10:
                continue
            if run_ended and report_ended and report_ended > run_ended + 10:
                continue

            return str(report_path), data

        return None, None

    def run_status(self, run_id: str) -> None:
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            json_response(self, 404, {"error": "run not found", "run_id": run_id})
            return

        events = []
        for event in list(getattr(run, "events", [])):
            events.append({
                "kind": getattr(event, "kind", ""),
                "message": getattr(event, "message", ""),
                "raw": getattr(event, "raw", ""),
                "visible": getattr(event, "visible", True),
                "ts": getattr(event, "ts", None),
            })

        engine_report_path, engine_report = self.find_engine_report_for_run(run)
        engine_events = []
        if engine_report:
            raw_engine_events = engine_report.get("events", [])
            if isinstance(raw_engine_events, list):
                engine_events = raw_engine_events

            # If the web RunState has no events, expose engine events as the main events list.
            if not events:
                events = [
                    {
                        "kind": str(item.get("level", "")),
                        "message": str(item.get("title", "")),
                        "raw": str(item.get("raw", "")),
                        "visible": True,
                        "ts": item.get("ts"),
                        "detail": item.get("detail", ""),
                        "phase": item.get("phase", ""),
                    }
                    for item in engine_events
                    if isinstance(item, dict)
                ]

        events = [compact_status_event(ROOT, run_id, item) for item in events]

        payload = {
            "run_id": getattr(run, "id", run_id),
            "status": getattr(run, "status", "unknown"),
            "started_at": getattr(run, "started_at", None),
            "ended_at": getattr(run, "ended_at", None),
            "exit_code": getattr(run, "exit_code", None),
            "prompt": getattr(run, "prompt", ""),
            "command": getattr(run, "command", []),
            "events": events,
            "engine_report_path": engine_report_path,
            "engine_status": engine_report.get("status") if engine_report else None,
            "engine_phase": engine_report.get("phase") if engine_report else None,
            "engine_exit_code": engine_report.get("exit_code") if engine_report else None,
        }
        json_response(self, 200, payload)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/run":
            self.start_run()
            return

        if parsed.path.startswith("/api/stop/"):
            run_id = parsed.path.rsplit("/", 1)[-1]
            self.stop_run(run_id)
            return

        text_response(self, 404, "not found")

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def start_run(self) -> None:
        try:
            data = self.read_json()
            prompt = str(data.get("prompt", "")).strip()
            if not prompt:
                text_response(self, 400, "prompt is required")
                return

            max_iterations = int(data.get("max_iterations", 1))
            max_iterations = max(1, min(max_iterations, 20))
            audit_only = bool(data.get("audit_only", True))

            raw_prompt = prompt
            use_micro_patch = (not audit_only) and is_micro_patch_prompt(raw_prompt)

            if audit_only:
                audit_prefix = (
                    "Audit only. Do not modify files. Do not patch. Do not write files. "
                    "After the report, stop.\n\n"
                )
                lowered = prompt.lower()
                if "audit only" not in lowered and "read-only" not in lowered and "read only" not in lowered:
                    prompt = audit_prefix + prompt
                prompt = build_policy_prompt(prompt, audit_only=True)
            elif use_micro_patch:
                prompt = raw_prompt
            else:
                prompt = build_policy_prompt(prompt, audit_only=False)

            prompt_file = Path(tempfile.gettempdir()) / f"link-web-prompt-{uuid.uuid4().hex}.txt"
            prompt_file.write_text(prompt, encoding="utf-8")

            if audit_only:
                command = [
                    sys.executable,
                    str(ROOT / "link_audit_fast.py"),
                    "--prompt-file",
                    str(prompt_file),
                ]
            elif use_micro_patch:
                command = [
                    sys.executable,
                    str(ROOT / "link_micro_patch.py"),
                    "--prompt-file",
                    str(prompt_file),
                ]
            else:
                command = [
                    sys.executable,
                    str(ROOT / "link_autonomous.py"),
                    "run",
                    "--prompt-file",
                    str(prompt_file),
                    "--max-iterations",
                    str(max_iterations),
                    "--max-changed-files",
                    "8",
                    "--max-diff-lines",
                    "1200",
                    "--auto-restore-on-failure",
                ]

            state = RunState(prompt=prompt, command=command)
            with RUNS_LOCK:
                RUNS[state.id] = state

            thread = threading.Thread(target=run_process, args=(state,), daemon=True)
            thread.start()

            json_response(self, 200, {"run_id": state.id})
        except Exception as exc:
            text_response(self, 400, str(exc))

    def stop_run(self, run_id: str) -> None:
        with RUNS_LOCK:
            state = RUNS.get(run_id)

        if state is None:
            text_response(self, 404, "run not found")
            return

        process = state.process
        if process and process.poll() is None:
            state.log("Stop requested by user.", "warn")
            process.terminate()
            json_response(self, 200, {"stopped": True})
            return

        json_response(self, 200, {"stopped": False})

    def stream_events(self, run_id: str) -> None:
        with RUNS_LOCK:
            state = RUNS.get(run_id)

        if state is None:
            text_response(self, 404, "run not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        index = 0
        last_status = None

        try:
            while True:
                if state.status != last_status:
                    self.write_sse({"type": "status", "status": state.status})
                    last_status = state.status

                index, lines = state.snapshot_lines(index)
                for item in lines:
                    self.write_sse({"type": "line", **item})

                if state.status in {"done", "failed"}:
                    self.write_sse({"type": "done", "exit_code": state.exit_code})
                    break

                time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError):
            return

    def write_sse(self, payload: object) -> None:
        data = json.dumps(payload)
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Link web console.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Use 0.0.0.0 for LAN access.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Link Console running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Link Console.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
