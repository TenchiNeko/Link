#!/usr/bin/env python3
"""
Local Link web console.

A tiny no-dependency browser UI:
- prompt box at bottom
- live agent journal above
- Run / Stop buttons
- audit-only and worktree toggles
"""


from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
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
    <label><input id="worktree" type="checkbox" checked /> Use worktree</label>
    <label>Max iterations <input id="maxIterations" type="number" min="1" max="20" value="1" /></label>
    <span class="small">Tip: Ctrl/Cmd + Enter runs.</span>
  </div>
</section>

<script>
let currentRunId = null;
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
    worktree: document.getElementById("worktree").checked,
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

<!-- Link human-friendly journal view -->
<style>
#link-human-journal {
  border-top: 1px solid #263244;
  border-bottom: 1px solid #263244;
  background: #07111f;
  color: #e5e7eb;
  padding: 12px;
  margin: 10px 0;
  font-family: system-ui, sans-serif;
}
#link-human-journal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
#link-human-journal-title {
  font-weight: 700;
}
#link-human-journal-toggle {
  border: 1px solid #475569;
  background: #111827;
  color: #e5e7eb;
  border-radius: 8px;
  padding: 5px 9px;
  cursor: pointer;
}
#link-human-journal-text {
  white-space: pre-wrap;
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  line-height: 1.45;
  max-height: 45vh;
  overflow: auto;
}
</style>
<script>
(function () {
  const ansiPattern = /\x1b\[[0-9;]*m/g;

  function stripNoisePrefix(line) {
    return line
      .replace(ansiPattern, "")
      .replace(/^\d{2}:\d{2}:\d{2}\s+│\s*(INFO|WARNING|ERROR)\s+│\s*[^│]+│\s*/i, "")
      .replace(/^\d{2}:\d{2}:\d{2}\s+│\s*/i, "")
      .trim();
  }

  function humanize(line) {
    const l = stripNoisePrefix(line);
    if (!l) return "";

    const lower = l.toLowerCase();

    if (lower.includes("http request: post")) return "";
    if (lower.includes("knowledge base:")) return "";
    if (lower.includes("working directory:")) return "";
    if (lower.includes("max iterations:")) return "";
    if (/^[=\-]{10,}$/.test(l)) return "";
    if (lower.includes("standalone_agents") && lower.includes("progress:")) return "";

    if (l.includes("ORCHESTRATOR STARTING")) return "▶️ Run started";
    if (l.includes("ITERATION ")) return "🔁 " + l;
    if (l.includes("PHASE 1: EXPLORE")) return "🔎 Exploring repo";
    if (l.includes("PHASE 2: PLAN")) return "🧭 Planning changes";
    if (l.includes("PHASE 3: BUILD")) return "🛠️ Applying patch";
    if (l.includes("PHASE 4: TEST")) return "✅ Verifying";
    if (l.includes("TASK COMPLETED SUCCESSFULLY")) return "🎉 Task completed successfully";
    if (l.includes("TASK ESCALATED TO HUMAN")) return "🚨 Needs human help";
    if (l.includes("LINK HEALTHCHECK PASSED")) return "✅ Link healthcheck passed";
    if (l.includes("DoD FAILED")) return "⚠️ " + l;
    if (l.includes("Stuck loop detected")) return "⚠️ Agent got stuck repeating itself";
    if (l.includes("Build sequence:")) return "📋 " + l;
    if (l.includes("Micro-build")) return "🧱 " + l;
    if (l.includes("verified OK")) return "✅ " + l;
    if (l.includes("content changed")) return "📝 " + l;
    if (l.includes("Wrote artifact manifest")) return "📦 Artifact manifest written";
    if (l.includes("Git commit") || l.includes("commit")) return "🔖 " + l;
    if (l.includes("Fatal error") || l.includes("Traceback")) return "❌ " + l;

    if (lower.includes("running initializer")) return "Preparing run...";
    if (lower.includes("running explore")) return "";
    if (lower.includes("running plan")) return "";
    if (lower.includes("running build")) return "";
    if (lower.includes("running test")) return "";

    if (l.length > 220) return "";
    return l;
  }

  function findRawJournal() {
    const candidates = Array.from(document.querySelectorAll("pre, textarea, div"))
      .filter(el => {
        if (!el || !el.textContent) return false;
        if ((el.id || "").startsWith("link-")) return false;
        const txt = el.textContent;
        return txt.includes("ORCHESTRATOR") ||
               txt.includes("PHASE ") ||
               txt.includes("HTTP Request") ||
               txt.includes("Run finished") ||
               txt.includes("standalone_orchestrator");
      });

    candidates.sort((a, b) => b.textContent.length - a.textContent.length);
    return candidates[0] || null;
  }

  function ensurePanel() {
    let panel = document.getElementById("link-human-journal");
    if (panel) return panel;

    panel = document.createElement("div");
    panel.id = "link-human-journal";
    panel.innerHTML = `
      <div id="link-human-journal-head">
        <div id="link-human-journal-title">Agent Journal</div>
        <button id="link-human-journal-toggle" type="button">Show raw logs</button>
      </div>
      <pre id="link-human-journal-text">Waiting for a run...</pre>
    `;

    const promptBox = document.querySelector("textarea");
    const anchor = promptBox ? (promptBox.closest("form") || promptBox.parentElement) : null;
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(panel, anchor);
    } else {
      document.body.appendChild(panel);
    }

    document.getElementById("link-human-journal-toggle").onclick = function () {
      const raw = findRawJournal();
      if (!raw) return;
      const hidden = raw.style.display === "none";
      raw.style.display = hidden ? "" : "none";
      this.textContent = hidden ? "Hide raw logs" : "Show raw logs";
    };

    return panel;
  }

  function refreshHumanJournal() {
    const panel = ensurePanel();
    const output = panel.querySelector("#link-human-journal-text");
    const raw = findRawJournal();

    if (!raw) return;

    raw.style.display = "none";

    const seen = new Set();
    const clean = raw.textContent
      .split(/\n/)
      .map(humanize)
      .filter(Boolean)
      .filter(line => {
        const key = line.replace(/\d+\/\d+/g, "N/N");
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(-120);

    output.textContent = clean.length ? clean.join("\n") : "Run is active. Waiting for meaningful agent events...";
    output.scrollTop = output.scrollHeight;
  }

  setInterval(refreshHumanJournal, 1000);
  window.addEventListener("load", refreshHumanJournal);
})();
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
        state.status = "done" if state.exit_code == 0 else "failed"
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
            worktree = bool(data.get("worktree", True))

            if audit_only:
                audit_prefix = (
                    "Audit only. Do not modify files. Do not patch. Do not write files. "
                    "After the report, stop.\n\n"
                )
                lowered = prompt.lower()
                if "audit only" not in lowered and "read-only" not in lowered and "read only" not in lowered:
                    prompt = audit_prefix + prompt

            command = [
                sys.executable,
                str(ROOT / "standalone_main.py"),
                prompt,
                "--max-iterations",
                str(max_iterations),
            ]
            if worktree:
                # standalone_main.py does not currently accept --worktree.
                # Keep the UI checkbox harmless until native CLI worktree support exists.
                pass
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






# --- Link repo status helper (stdlib HTTP server) ----------------------------
def _link_status_run(cmd, timeout=8):
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def _link_repo_status_payload():
    branch_code, branch, _ = _link_status_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=3)
    hash_code, short_hash, _ = _link_status_run(["git", "rev-parse", "--short", "HEAD"], timeout=3)
    latest_code, latest_hash, _ = _link_status_run(["git", "rev-parse", "--short", "safe-link-latest"], timeout=3)
    status_code, dirty_text, _ = _link_status_run(["git", "status", "--porcelain", "--untracked-files=all"], timeout=3)
    health_code, health_out, health_err = _link_status_run([sys.executable, "link_healthcheck.py"], timeout=30)

    return {
        "branch": branch if branch_code == 0 else "unknown",
        "commit": short_hash if hash_code == 0 else "unknown",
        "safe_link_latest": latest_hash if latest_code == 0 else "missing",
        "git_clean": status_code == 0 and dirty_text == "",
        "healthcheck_passed": health_code == 0,
        "healthcheck_tail": ((health_out or health_err).splitlines()[-1:] or [""])[0],
    }


def _link_send_json(handler, payload):
    body = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _link_repo_status_box_html():
    return """
<div id="link-repo-status-box" style="position:fixed;right:16px;top:16px;z-index:9999;max-width:360px;padding:12px 14px;border:1px solid #334155;border-radius:10px;background:#0f172a;color:#e5e7eb;font-family:system-ui, sans-serif;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.25)">
  <div style="font-weight:700;margin-bottom:6px">Repo Safety Status</div>
  <pre id="link-repo-status-text" style="white-space:pre-wrap;margin:0;font-family:ui-monospace, SFMono-Regular, Menlo, monospace">Loading...</pre>
</div>
<script>
async function refreshLinkRepoStatus() {
  const el = document.getElementById("link-repo-status-text");
  if (!el) return;
  try {
    const res = await fetch("/repo-status", {cache: "no-store"});
    const s = await res.json();
    el.textContent =
      "Branch: " + s.branch + "\\n" +
      "Commit: " + s.commit + "\\n" +
      "Clean: " + (s.git_clean ? "yes" : "NO") + "\\n" +
      "Healthcheck: " + (s.healthcheck_passed ? "PASS" : "FAIL") + "\\n" +
      "safe-link-latest: " + s.safe_link_latest;
  } catch (e) {
    el.textContent = "Status unavailable: " + e;
  }
}
refreshLinkRepoStatus();
setInterval(refreshLinkRepoStatus, 60000);
</script>
"""


def _link_install_repo_status_box():
    global HTML
    if "link-repo-status-box" in HTML:
        return
    box = _link_repo_status_box_html()
    if "</body>" in HTML:
        HTML = HTML.replace("</body>", box + "\n</body>", 1)
    else:
        HTML += box


def _link_install_repo_status_route():
    for obj in list(globals().values()):
        if not isinstance(obj, type):
            continue
        try:
            is_handler = issubclass(obj, BaseHTTPRequestHandler) and obj is not BaseHTTPRequestHandler
        except TypeError:
            continue
        if not is_handler:
            continue

        original_do_get = getattr(obj, "do_GET", None)
        if original_do_get is None or getattr(original_do_get, "_link_repo_status_wrapped", False):
            continue

        def patched_do_GET(self, _original_do_get=original_do_get):
            if urlparse(self.path).path == "/repo-status":
                _link_send_json(self, _link_repo_status_payload())
                return
            return _original_do_get(self)

        patched_do_GET._link_repo_status_wrapped = True
        obj.do_GET = patched_do_GET
        return obj.__name__

    return ""


_link_install_repo_status_box()
_LINK_REPO_STATUS_HANDLER = _link_install_repo_status_route()
# --- end Link repo status helper --------------------------------------------

if __name__ == "__main__":
    raise SystemExit(main())
