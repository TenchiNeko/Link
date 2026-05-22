#!/usr/bin/env python3
"""Link Factory Dashboard."""

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

from factory.output_quality import assess_output_quality
from factory.team_registry import TEAM, reasoning_label_for_role, tier_names


def h(value) -> str:
    return html.escape(str(value or ""), quote=True)


def safe_project(project: str) -> str:
    project = (project or os.environ.get("LINK_FACTORY_DEFAULT_PROJECT", "[private-name]_growth")).strip()
    if not PROJECT_RE.match(project):
        raise ValueError("Invalid project name")
    return project


def project_root(project: str) -> Path:
    return ROOT / "factory" / "projects" / safe_project(project)


def runs_root(project: str) -> Path:
    return project_root(project) / "runs"


def latest_run(project: str) -> Path | None:
    root = runs_root(project)
    if not root.exists():
        return None
    runs = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0] if runs else None


def get_run(project: str, run_id: str | None) -> Path | None:
    if run_id:
        candidate = runs_root(project) / run_id
        if candidate.exists() and candidate.is_dir():
            return candidate
    return latest_run(project)


def role_id_from_file(path: Path) -> str:
    m = STEP_RE.match(path.name)
    return m.group(2) if m else path.stem


def role_meta(role_id: str) -> tuple[str, str, str]:
    spec = TEAM.get(role_id)
    if not spec:
        return role_id.replace("_", " ").title(), "unknown", "none"
    return spec.title, spec.model, reasoning_label_for_role(role_id)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def approvals_path(run: Path) -> Path:
    return run / "approvals.json"


def load_approvals(run: Path) -> dict:
    return load_json(approvals_path(run), {"qa_gate": {}, "files": {}})


def read_text(path: Path, limit: int = 60000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"[could not read file: {exc}]"
    if len(text) > limit:
        return text[:limit] + "\n\n[dashboard display truncated]"
    return text


def markdown_files(run: Path) -> list[Path]:
    return sorted([p for p in run.glob("*.md") if p.name != "SUMMARY.md"], key=lambda p: p.name)


def run_factory(project: str, goal: str, tier: str, execute: bool, max_tokens: int) -> tuple[int, str]:
    cmd = [
        sys.executable,
        str(ROOT / "link_factory_team.py"),
        "run",
        "--project", project,
        "--goal", goal,
        "--tier", tier,
        "--max-tokens", str(max_tokens),
    ]
    cmd.append("--execute-models" if execute else "--dry-run")

    env = os.environ.copy()
    env["LINK_FACTORY_ACTIVE_PROJECT"] = project

    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=1800)
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, out
    except Exception as exc:
        return 1, f"Dashboard failed to start factory run: {exc}"


def build_repair_goal(project: str, run: Path, note: str) -> str:
    chunks = [
        f"REPAIR PASS for project `{project}`.",
        "Use the prior run outputs, QA findings, quality warnings, and human note below.",
        "Do not restart with a generic plan.",
        "Complete missing or truncated sections only.",
        "Preserve useful prior work.",
        "Use the real Project platform context: TikTok, X/Twitter, Instagram, [private-project], Projectchat.com, and Platform Automation.",
        "No posting, publishing, DMing, sending, buying, scheduling, or external action.",
        "",
        f"Previous run: {run.name}",
    ]

    if note.strip():
        chunks += ["", "Human note:", note.strip()]

    for file in markdown_files(run):
        text = read_text(file, limit=10000)
        issues = assess_output_quality(text)
        if issues or "qa" in file.name or "chief_of_staff" in file.name:
            chunks.append(f"\n\n---\nFile: {file.name}\n")
            if issues:
                chunks.append("Quality warnings:\n" + json.dumps(issues, indent=2))
            chunks.append(text)

    return "\n".join(chunks)


def form_value(params: dict, key: str, default: str = "") -> str:
    values = params.get(key)
    return values[0] if values else default


def redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.end_headers()


def send_html(handler: BaseHTTPRequestHandler, body: str, status: int = 200) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(data)


def decision_buttons(project: str, run: Path, target: str, current: dict) -> str:
    decision = current.get("decision", "pending")
    return f'''
    <form class="buttons" method="post" action="/approve">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="run" value="{h(run.name)}">
      <input type="hidden" name="target" value="{h(target)}">
      <span class="decision decision-{h(decision)}">{h(decision)}</span>
      <button name="decision" value="approved" class="yes">Approve</button>
      <button name="decision" value="rejected" class="no">Reject</button>
      <button name="decision" value="revise" class="try">Revise / Try Again</button>
    </form>
    '''


def render_page(project: str, run_id: str | None = None) -> str:
    project = safe_project(project)
    run = get_run(project, run_id)
    tiers = tier_names()
    selected_tier = "balanced" if "balanced" in tiers else (tiers[0] if tiers else "cheap")
    tier_options = "".join(f'<option value="{h(t)}" {"selected" if t == selected_tier else ""}>{h(t)}</option>' for t in tiers)

    parts = ["""<!doctype html>
<html><head><meta charset="utf-8"><title>Link Factory Dashboard</title>
<style>
body{font-family:Arial,sans-serif;margin:0;background:#0b0d12;color:#eef1f7}
header{padding:18px 24px;background:#151925;border-bottom:1px solid #2a3144;position:sticky;top:0;z-index:2}
h1{margin:0;font-size:24px}.wrap{padding:20px;max-width:1500px;margin:auto}
.panel,.card{background:#151925;border:1px solid #2a3144;border-radius:14px;padding:16px;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px}
.card h2{font-size:18px;margin:0 0 8px}.meta{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px}
.tag{background:#222a3c;border:1px solid #33405b;border-radius:999px;padding:4px 8px;font-size:12px;color:#c8d2e8}
pre{white-space:pre-wrap;background:#080a0f;border:1px solid #222a3c;border-radius:10px;padding:12px;max-height:560px;overflow:auto;color:#dce5f8}
textarea,input,select{width:100%;box-sizing:border-box;background:#090c13;color:#eef1f7;border:1px solid #33405b;border-radius:10px;padding:10px}
textarea{min-height:110px}button{border:0;border-radius:10px;padding:9px 12px;margin:4px;cursor:pointer;font-weight:700}
.yes{background:#1f8f4d;color:white}.no{background:#9b2c2c;color:white}.try{background:#b7791f;color:white}.run{background:#4263eb;color:white}
.buttons{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.decision{padding:5px 8px;border-radius:999px;background:#2a3144;font-size:12px}
.decision-approved{background:#1f8f4d}.decision-rejected{background:#9b2c2c}.decision-revise{background:#b7791f}
.issue{border-left:4px solid #b7791f;padding:7px 10px;background:#1c1520;margin:6px 0;border-radius:8px}
.issue-critical{border-left-color:#e03131;background:#251218}.small{color:#aebad3;font-size:13px}
.row{display:grid;grid-template-columns:1fr 180px 140px 120px;gap:10px;align-items:end}@media(max-width:800px){.row{grid-template-columns:1fr}}
</style></head><body><header><h1>🏭 Link Factory Dashboard</h1></header><div class="wrap">
"""]

    parts.append(f"""
<div class="panel">
  <form method="post" action="/run">
    <div class="row">
      <label>Project<input name="project" value="{h(project)}"></label>
      <label>Tier<select name="tier">{tier_options}</select></label>
      <label>Max tokens<input name="max_tokens" value="5500"></label>
      <label class="small"><input type="checkbox" name="execute" value="1" style="width:auto"> execute</label>
    </div>
    <p class="small">Prompt the team. External posting/sending/buying remains forbidden unless separately approved.</p>
    <textarea name="goal" placeholder="Give the factory a job..."></textarea>
    <button class="run" type="submit">Run Team</button>
  </form>
</div>
""")

    last_error = project_root(project) / "dashboard_last_error.log"
    if last_error.exists():
        parts.append(f'<div class="panel"><h2>Last dashboard run log</h2><pre>{h(read_text(last_error, 12000))}</pre></div>')

    if not run:
        parts.append(f'<div class="panel">No runs found for <b>{h(project)}</b>.</div></div></body></html>')
        return "\n".join(parts)

    approvals = load_approvals(run)
    qa_gate = approvals.get("qa_gate", {})

    parts.append(f"""
<div class="panel">
  <h2>Latest Run: {h(run.name)}</h2>
  <div class="meta">
    <span class="tag">project: {h(project)}</span>
    <span class="tag">run: {h(run.name)}</span>
    <span class="tag">approval gate: QA → Router → Human</span>
  </div>
  <p class="small">Recommended flow: review QA/QA Advisor and final Chief of Staff, then use the run-level gate.</p>
  {decision_buttons(project, run, "__qa_gate__", qa_gate)}
  <form method="post" action="/repair" class="panel" style="margin-top:12px">
    <input type="hidden" name="project" value="{h(project)}">
    <input type="hidden" name="run" value="{h(run.name)}">
    <p class="small">Repair pass sends QA findings, quality warnings, and your note back to the Router/repair tier.</p>
    <textarea name="note" placeholder="Optional repair instruction..."></textarea>
    <button class="try" type="submit">Run Repair Pass</button>
  </form>
</div>
""")

    summary = run / "SUMMARY.md"
    if summary.exists():
        parts.append(f'<div class="panel"><h2>Summary</h2><pre>{h(read_text(summary, 12000))}</pre></div>')

    parts.append('<div class="grid">')
    for file in markdown_files(run):
        role_id = role_id_from_file(file)
        title, model, reasoning = role_meta(role_id)
        text = read_text(file)
        issues = assess_output_quality(text)
        current = approvals.get("files", {}).get(file.name, {})
        issue_html = ""
        if issues:
            issue_html = "<h3>Quality / completeness warnings</h3>" + "\n".join(
                f'<div class="issue issue-{h(i.get("severity"))}"><b>{h(i.get("code"))}</b>: {h(i.get("message"))}</div>'
                for i in issues
            )

        parts.append(f"""
<div class="card">
  <h2>{h(file.name)} — {h(title)}</h2>
  <div class="meta">
    <span class="tag">role: {h(role_id)}</span>
    <span class="tag">model: {h(model)}</span>
    <span class="tag">reasoning: {h(reasoning)}</span>
  </div>
  {decision_buttons(project, run, file.name, current)}
  {issue_html}
  <pre>{h(text)}</pre>
</div>
""")

    parts.append("</div></div></body></html>")
    return "\n".join(parts)


class Handler(BaseHTTPRequestHandler):
    server_version = "LinkFactoryDashboard/1.1"

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        project = form_value(qs, "project", "[private-name]_growth")
        run_id = form_value(qs, "run", "")
        try:
            send_html(self, render_page(project, run_id or None))
        except Exception as exc:
            send_html(self, f"<pre>{h(type(exc).__name__)}: {h(exc)}</pre>", 500)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        params = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/run":
                project = safe_project(form_value(params, "project", "[private-name]_growth"))
                goal = form_value(params, "goal", "").strip() or (
                    "Create an internal-only growth factory plan using the real Project platforms: "
                    "TikTok, X/Twitter, Instagram, [private-project], Projectchat.com, and Platform Automation. No external actions."
                )
                tier = form_value(params, "tier", "balanced")
                execute = form_value(params, "execute", "") == "1"
                max_tokens = int(form_value(params, "max_tokens", "5500") or "5500")
                code, out = run_factory(project, goal, tier, execute, max_tokens)
                log = project_root(project) / "dashboard_last_error.log"
                if code != 0:
                    log.parent.mkdir(parents=True, exist_ok=True)
                    log.write_text(out, encoding="utf-8")
                elif log.exists():
                    log.unlink()
                redirect(self, "/?" + urlencode({"project": project}))
                return

            if parsed.path == "/approve":
                project = safe_project(form_value(params, "project", "[private-name]_growth"))
                run = get_run(project, form_value(params, "run", ""))
                if not run:
                    raise ValueError("Run not found")
                target = form_value(params, "target", "")
                decision = form_value(params, "decision", "pending")
                approvals = load_approvals(run)
                record = {"decision": decision, "ts": int(time.time())}
                if target == "__qa_gate__":
                    approvals["qa_gate"] = record
                else:
                    approvals.setdefault("files", {})[target] = record
                save_json(approvals_path(run), approvals)
                redirect(self, "/?" + urlencode({"project": project, "run": run.name}))
                return

            if parsed.path == "/repair":
                project = safe_project(form_value(params, "project", "[private-name]_growth"))
                run = get_run(project, form_value(params, "run", ""))
                if not run:
                    raise ValueError("Run not found")
                goal = build_repair_goal(project, run, form_value(params, "note", ""))
                code, out = run_factory(project, goal, "repair", True, 6500)
                log = project_root(project) / "dashboard_last_error.log"
                if code != 0:
                    log.parent.mkdir(parents=True, exist_ok=True)
                    log.write_text(out, encoding="utf-8")
                elif log.exists():
                    log.unlink()
                redirect(self, "/?" + urlencode({"project": project}))
                return

            send_html(self, "Not found", 404)
        except Exception as exc:
            send_html(self, f"<pre>{h(type(exc).__name__)}: {h(exc)}</pre>", 500)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Link Factory Dashboard: http://{args.host}:{args.port}/?project=[private-name]_growth", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
