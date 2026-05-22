#!/usr/bin/env python3
"""Link Factory Dashboard.

Standalone stdlib web UI for:
- prompting a factory team run
- viewing role outputs by position
- seeing model + reasoning policy per role
- recording human approval: yes / no / try_again

No posting, publishing, sending, buying, or external platform actions happen here.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = Path(__file__).resolve().parent
PROJECT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
STEP_RE = re.compile(r"^(\d+)-(.+)\.md$")

try:
    from factory.team_registry import TEAM, tier_names, reasoning_label_for_role
except Exception:
    TEAM = {}
    tier_names = lambda: ["cheap", "balanced", "premium", "board-review"]  # noqa: E731
    reasoning_label_for_role = lambda role_id: "unknown"  # noqa: E731


def safe_project(value: str) -> str:
    value = (value or "growth_lab").strip()
    if not PROJECT_RE.match(value):
        raise ValueError("Project names may only contain letters, numbers, dot, dash, and underscore.")
    return value


def project_root(project: str) -> Path:
    return ROOT / "factory" / "projects" / project


def latest_run(project: str) -> Path | None:
    runs = project_root(project) / "runs"
    if not runs.exists():
        return None
    dirs = sorted([p for p in runs.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs[0] if dirs else None


def run_dirs(project: str) -> list[Path]:
    runs = project_root(project) / "runs"
    if not runs.exists():
        return []
    return sorted([p for p in runs.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)


def read_text(path: Path, limit: int = 60000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n\n[truncated]"
    return text


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def approval_file(project: str, run_name: str, step_file: str) -> Path:
    base = project_root(project) / "approvals" / run_name
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{step_file}.approval.json"


def read_approval(project: str, run_name: str, step_file: str) -> dict:
    return read_json(approval_file(project, run_name, step_file))


def write_approval(project: str, run_name: str, step_file: str, decision: str, note: str = "") -> None:
    if decision not in {"yes", "no", "try_again"}:
        raise ValueError("Invalid approval decision.")
    payload = {
        "project": project,
        "run": run_name,
        "step_file": step_file,
        "decision": decision,
        "note": note,
        "updated_at": int(time.time()),
    }
    approval_file(project, run_name, step_file).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def role_meta(role_id: str) -> tuple[str, str, str]:
    role = TEAM.get(role_id) if isinstance(TEAM, dict) else None
    title = getattr(role, "title", role_id.replace("_", " ").title())
    model = getattr(role, "model", "unknown")
    reasoning = reasoning_label_for_role(role_id)
    return title, model, reasoning


def output_steps(run_dir: Path) -> list[tuple[int, str, str, Path]]:
    items = []
    for p in sorted(run_dir.glob("*.md")):
        if p.name == "SUMMARY.md":
            continue
        m = STEP_RE.match(p.name)
        if not m:
            continue
        items.append((int(m.group(1)), m.group(2), p.name, p))
    return sorted(items)


def run_factory(project: str, goal: str, tier: str, execute: bool, max_tokens: int) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(ROOT / "link_factory_team.py"),
        "run",
        "--project",
        project,
        "--goal",
        goal,
        "--tier",
        tier,
        "--max-tokens",
        str(max_tokens),
    ]
    args.append("--execute-models" if execute else "--dry-run")
    return subprocess.run(
        args,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        env=os.environ.copy(),
    )


def page(project: str, message: str = "") -> str:
    run = latest_run(project)
    tiers = tier_names()
    run_options = run_dirs(project)

    parts = []
    parts.append("""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Link Factory Dashboard</title>
<style>
body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 24px; background: #0f1115; color: #eef0f5; }
h1, h2, h3 { margin-bottom: 8px; }
a { color: #9ecbff; }
.panel { background: #171a21; border: 1px solid #2a2f3a; border-radius: 14px; padding: 16px; margin-bottom: 18px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(390px, 1fr)); gap: 16px; }
.card { background: #171a21; border: 1px solid #2a2f3a; border-radius: 14px; padding: 16px; }
.meta { color: #aab3c5; font-size: 13px; line-height: 1.5; }
pre { white-space: pre-wrap; background: #0b0d11; border: 1px solid #2a2f3a; padding: 12px; border-radius: 10px; max-height: 520px; overflow: auto; }
textarea, input, select { width: 100%; box-sizing: border-box; background: #0b0d11; color: #eef0f5; border: 1px solid #2a2f3a; border-radius: 8px; padding: 10px; }
button { border: 0; border-radius: 8px; padding: 9px 12px; margin: 4px 4px 0 0; cursor: pointer; font-weight: 650; }
.yes { background: #238636; color: white; }
.no { background: #da3633; color: white; }
.try { background: #d29922; color: #111; }
.run { background: #2f81f7; color: white; }
.badge { display: inline-block; background: #222938; border: 1px solid #3b4457; border-radius: 999px; padding: 3px 8px; margin: 2px; font-size: 12px; }
.msg { background: #13233a; border: 1px solid #2f81f7; border-radius: 10px; padding: 10px; margin-bottom: 16px; }
</style>
</head>
<body>
<h1>Link Factory Dashboard</h1>
""")

    if message:
        parts.append(f'<div class="msg">{html.escape(message)}</div>')

    parts.append(f"""
<div class="panel">
<h2>Run the team</h2>
<form method="POST" action="/run">
<label>Project</label>
<input name="project" value="{html.escape(project)}">
<br><br>
<label>Tier</label>
<select name="tier">
""")
    for t in tiers:
        selected = "selected" if t == "balanced" else ""
        parts.append(f'<option value="{html.escape(t)}" {selected}>{html.escape(t)}</option>')
    parts.append("""
</select>
<br><br>
<label>Goal / Job Prompt</label>
<textarea name="goal" rows="5">Create a short internal project plan. Do not post, publish, send, buy, DM, or take external actions. Only produce internal planning output.</textarea>
<br><br>
<label>Max tokens per role</label>
<input name="max_tokens" value="1800">
<br><br>
<label><input type="checkbox" name="execute" value="1"> Execute models through OpenRouter</label>
<br><br>
<button class="run" type="submit">Run Factory Team</button>
</form>
</div>
""")

    parts.append('<div class="panel"><h2>Latest run</h2>')
    if run is None:
        parts.append("<p>No run found yet.</p></div></body></html>")
        return "".join(parts)

    manifest = read_json(run / "manifest.json")
    summary = read_text(run / "SUMMARY.md")
    parts.append(f'<div class="meta">Project: <b>{html.escape(project)}</b><br>Run: <b>{html.escape(run.name)}</b><br>')
    parts.append(f'Tier: <b>{html.escape(str(manifest.get("tier", "")))}</b><br>')
    parts.append(f'Execute models: <b>{html.escape(str(manifest.get("execute_models", "")))}</b></div>')
    if run_options:
        parts.append('<p class="meta">Recent runs: ')
        for r in run_options[:8]:
            parts.append(f'<span class="badge">{html.escape(r.name)}</span>')
        parts.append('</p>')
    parts.append(f"<pre>{html.escape(summary)}</pre></div>")

    parts.append('<div class="grid">')
    for step_num, role_id, step_file, path in output_steps(run):
        title, model, reasoning = role_meta(role_id)
        body = read_text(path)
        approval = read_approval(project, run.name, step_file)
        decision = approval.get("decision", "pending")
        note = approval.get("note", "")

        parts.append('<div class="card">')
        parts.append(f"<h3>{step_num:02d}. {html.escape(title)}</h3>")
        parts.append('<div class="meta">')
        parts.append(f'role: <b>{html.escape(role_id)}</b><br>')
        parts.append(f'model: <b>{html.escape(model)}</b><br>')
        parts.append(f'reasoning: <b>{html.escape(reasoning)}</b><br>')
        parts.append(f'approval: <b>{html.escape(decision)}</b>')
        if note:
            parts.append(f'<br>note: {html.escape(note)}')
        parts.append('</div>')

        parts.append(f"<pre>{html.escape(body)}</pre>")

        parts.append(f"""
<form method="POST" action="/approve">
<input type="hidden" name="project" value="{html.escape(project)}">
<input type="hidden" name="run" value="{html.escape(run.name)}">
<input type="hidden" name="step_file" value="{html.escape(step_file)}">
<textarea name="note" rows="2" placeholder="Optional note for this decision"></textarea>
<button class="yes" name="decision" value="yes">Yes</button>
<button class="no" name="decision" value="no">No</button>
<button class="try" name="decision" value="try_again">Try Again</button>
</form>
""")
        parts.append("</div>")
    parts.append("</div></body></html>")
    return "".join(parts)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("factory-dashboard: " + (fmt % args) + "\n")

    def send_html(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, project: str, message: str = ""):
        q = {"project": project}
        if message:
            q["message"] = message
        self.send_response(303)
        self.send_header("Location", "/?" + urlencode(q))
        self.end_headers()

    def read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        parsed = parse_qs(raw)
        return {k: v[-1] if v else "" for k, v in parsed.items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        project = safe_project((q.get("project") or ["growth_lab"])[0])
        message = (q.get("message") or [""])[0]
        if parsed.path not in {"/", "/dashboard"}:
            self.send_html("<h1>Not found</h1>", 404)
            return
        self.send_html(page(project, message))

    def do_POST(self):
        try:
            form = self.read_form()
            if self.path == "/approve":
                project = safe_project(form.get("project", "growth_lab"))
                run_name = form.get("run", "")
                step_file = form.get("step_file", "")
                decision = form.get("decision", "")
                note = form.get("note", "")
                if not run_name or not step_file:
                    raise ValueError("Missing run or step file.")
                write_approval(project, run_name, step_file, decision, note)
                self.redirect(project, f"Saved approval: {decision} for {step_file}")
                return

            if self.path == "/run":
                project = safe_project(form.get("project", "growth_lab"))
                goal = form.get("goal", "").strip()
                tier = form.get("tier", "cheap").strip()
                execute = form.get("execute") == "1"
                max_tokens = int(form.get("max_tokens", "1800") or "1800")
                if not goal:
                    raise ValueError("Goal cannot be blank.")

                result = run_factory(project, goal, tier, execute, max_tokens)
                msg = f"Factory run exit={result.returncode}. " + result.stdout[-600:].replace("\n", " | ")
                self.redirect(project, msg)
                return

            self.send_html("<h1>Not found</h1>", 404)
        except Exception as e:
            self.send_html(f"<h1>Error</h1><pre>{html.escape(str(e))}</pre>", 500)


def main() -> int:
    parser = argparse.ArgumentParser(description="Link Factory Dashboard")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Factory dashboard listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
