#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
from pathlib import Path
from typing import Any


SELF_LEARNING_DASHBOARD_VERSION = "LU108-self-learning-dashboard-v1"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def run(cmd: list[str], root: Path, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, (p.stdout or "").strip()
    except Exception as exc:
        return 99, str(exc)


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def list_json(folder: Path, limit: int = 20) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"))[-limit:]


def count_json(folder: Path) -> int:
    return len(list(folder.glob("*.json"))) if folder.exists() else 0


def latest_file(folder: Path) -> Path | None:
    files = list_json(folder, limit=999)
    return files[-1] if files else None


def queue_counts(root: Path) -> dict[str, int]:
    base = root / ".link" / "agent_queue"
    return {
        "pending": count_json(base / "pending"),
        "running": count_json(base / "running"),
        "done": count_json(base / "done"),
        "blocked": count_json(base / "blocked"),
        "receipts": count_json(base / "receipts"),
    }


def draft_counts(root: Path) -> dict[str, int]:
    base = root / ".link" / "patch_drafts"
    return {
        "pending": count_json(base / "pending"),
        "approved": count_json(base / "approved"),
        "rejected": count_json(base / "rejected"),
        "retry": count_json(base / "retry"),
        "receipts": count_json(base / "receipts"),
    }


def git_state(root: Path) -> dict[str, Any]:
    branch_code, branch = run(["git", "branch", "--show-current"], root)
    head_code, head = run(["git", "log", "--oneline", "-1"], root)
    status_code, status = run(["git", "status", "--short"], root)
    return {
        "branch": branch if branch_code == 0 else "",
        "head": head if head_code == 0 else "",
        "working_tree_clean": status.strip() == "",
        "status": status,
    }


def latest_records(root: Path) -> dict[str, Any]:
    agent_base = root / ".link" / "agent_queue"
    draft_base = root / ".link" / "patch_drafts"

    paths = {
        "latest_pending_task": latest_file(agent_base / "pending"),
        "latest_done_task": latest_file(agent_base / "done"),
        "latest_tick_receipt": latest_file(agent_base / "receipts"),
        "latest_pending_draft": latest_file(draft_base / "pending"),
        "latest_approved_draft": latest_file(draft_base / "approved"),
        "latest_retry_draft": latest_file(draft_base / "retry"),
        "latest_rejected_draft": latest_file(draft_base / "rejected"),
    }

    out: dict[str, Any] = {}
    for name, path in paths.items():
        out[f"{name}_path"] = str(path) if path else None
        out[name] = load_json(path)
    return out


def health_tail(root: Path) -> dict[str, Any]:
    code, out = run(["python3", "link_healthcheck.py"], root, timeout=90)
    lines = out.splitlines()
    return {
        "exit_code": code,
        "passed": code == 0 and any("LINK HEALTHCHECK PASSED" in line for line in lines),
        "tail": "\n".join(lines[-35:]),
    }


def build_dashboard(root: Path | None = None, include_healthcheck: bool = False) -> dict[str, Any]:
    root = Path(root or Path.cwd()).resolve()
    records = latest_records(root)
    git = git_state(root)
    health = health_tail(root) if include_healthcheck else {
        "exit_code": None,
        "passed": None,
        "tail": "healthcheck not run for this render",
    }

    pending_draft = records.get("latest_pending_draft") or {}
    pending_task = records.get("latest_pending_task") or {}
    approved_draft = records.get("latest_approved_draft") or {}
    retry_draft = records.get("latest_retry_draft") or {}

    if pending_draft:
        mode = "waiting_approval"
        next_action = "Brandon approval needed: yes, no, or try_again."
    elif retry_draft:
        mode = "needs_retry"
        next_action = "A draft needs retry feedback before patching."
    elif pending_task:
        mode = "work_available"
        next_action = "Run one autonomous tick or generate an approval draft."
    elif approved_draft:
        mode = "approved_work_available"
        next_action = "Approved draft exists; next step is safe patch execution."
    else:
        mode = "idle"
        next_action = "No queued work. Generate a growth receipt to find the next useful upgrade."

    return {
        "version": SELF_LEARNING_DASHBOARD_VERSION,
        "generated": now(),
        "mode": mode,
        "next_action": next_action,
        "git": git,
        "healthcheck": health,
        "agent_queue_counts": queue_counts(root),
        "patch_draft_counts": draft_counts(root),
        "records": records,
        "summary": {
            "pending_task_id": pending_task.get("task_id") or pending_task.get("id"),
            "pending_task_title": pending_task.get("title"),
            "pending_draft_id": pending_draft.get("draft_id"),
            "pending_draft_goal": pending_draft.get("goal"),
            "approved_draft_id": approved_draft.get("draft_id"),
            "approved_draft_goal": approved_draft.get("goal"),
        },
        "commands": {
            "refresh": "python3 link_self_learning_dashboard.py render --format html --write",
            "tick": "python3 link_autonomous_tick_runner.py --write --format markdown",
            "growth": "python3 link_autonomous_growth_receipt.py --goal 'Find next autonomous Link growth work' --format markdown --write",
            "yes": "python3 link_approval_patch_draft_queue.py decide --action yes --draft-id latest --feedback 'Approved from dashboard.' --format markdown",
            "no": "python3 link_approval_patch_draft_queue.py decide --action no --draft-id latest --feedback 'Rejected from dashboard.' --format markdown",
            "try_again": "python3 link_approval_patch_draft_queue.py decide --action try_again --draft-id latest --feedback 'Try again with Brandon feedback.' --format markdown",
        },
        "boundary": [
            "May inspect repo state, read queue files, write local .link receipts, and draft plans.",
            "Must wait for approval before source edits, commits, pushes, destructive commands, or unknown external code.",
            "Dashboard buttons copy commands for now; the next upgrade can wire them to a local POST route.",
        ],
    }


def render_markdown(data: dict[str, Any]) -> str:
    git = data.get("git") or {}
    health = data.get("healthcheck") or {}
    summary = data.get("summary") or {}
    records = data.get("records") or {}
    commands = data.get("commands") or {}

    lines = [
        "# Link Self-Learning Dashboard",
        "",
        f"Version: `{data.get('version')}`",
        f"Generated: {data.get('generated')}",
        f"Mode: **{data.get('mode')}**",
        f"Next action: {data.get('next_action')}",
        "",
        "## Git / Health",
        f"- Branch: `{git.get('branch')}`",
        f"- HEAD: `{git.get('head')}`",
        f"- Working tree clean: **{git.get('working_tree_clean')}**",
        f"- Healthcheck passed: **{health.get('passed')}**",
        "",
        "## Queue Counts",
    ]

    for key, value in (data.get("agent_queue_counts") or {}).items():
        lines.append(f"- Agent `{key}`: **{value}**")
    for key, value in (data.get("patch_draft_counts") or {}).items():
        lines.append(f"- Draft `{key}`: **{value}**")

    lines += [
        "",
        "## Current Work",
        f"- Pending task: `{summary.get('pending_task_id')}` — **{summary.get('pending_task_title')}**",
        f"- Pending draft: `{summary.get('pending_draft_id')}` — **{summary.get('pending_draft_goal')}**",
        f"- Approved draft: `{summary.get('approved_draft_id')}` — **{summary.get('approved_draft_goal')}**",
        "",
        "## Receipts",
        f"- Latest pending task: `{records.get('latest_pending_task_path')}`",
        f"- Latest pending draft: `{records.get('latest_pending_draft_path')}`",
        f"- Latest approved draft: `{records.get('latest_approved_draft_path')}`",
        f"- Latest tick receipt: `{records.get('latest_tick_receipt_path')}`",
        "",
        "## Controls",
        f"- YES: `{commands.get('yes')}`",
        f"- NO: `{commands.get('no')}`",
        f"- TRY AGAIN: `{commands.get('try_again')}`",
        f"- RUN ONE TICK: `{commands.get('tick')}`",
        f"- FIND GROWTH WORK: `{commands.get('growth')}`",
        "",
        "## Boundary",
    ]

    for item in data.get("boundary") or []:
        lines.append(f"- {item}")

    return "\n".join(lines).rstrip() + "\n"


def render_html(data: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""), quote=True)

    def card(label: str, value: Any) -> str:
        return f'<div class="card"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div></div>'

    git = data.get("git") or {}
    health = data.get("healthcheck") or {}
    summary = data.get("summary") or {}
    commands = data.get("commands") or {}

    cards = [
        card("Mode", data.get("mode")),
        card("Branch", git.get("branch")),
        card("Clean", git.get("working_tree_clean")),
        card("Health", health.get("passed")),
    ]

    for key, value in (data.get("agent_queue_counts") or {}).items():
        cards.append(card(f"Agent {key}", value))
    for key, value in (data.get("patch_draft_counts") or {}).items():
        cards.append(card(f"Draft {key}", value))

    markdown = esc(render_markdown(data))

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Link Self-Learning Dashboard</title>
<style>
body {{
  font-family: system-ui, -apple-system, Segoe UI, sans-serif;
  margin: 24px;
  background: #101216;
  color: #f3f4f6;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin: 16px 0;
}}
.card, .panel {{
  background: #1b1f2a;
  border: 1px solid #30384a;
  border-radius: 14px;
  padding: 14px;
  margin: 14px 0;
}}
.label {{
  color: #9ca3af;
  font-size: 13px;
}}
.value {{
  font-size: 22px;
  font-weight: 800;
  margin-top: 4px;
  overflow-wrap: anywhere;
}}
button {{
  border: 0;
  border-radius: 12px;
  padding: 14px 18px;
  font-weight: 800;
  cursor: pointer;
  margin: 6px;
}}
.yes {{ background: #16a34a; color: white; }}
.no {{ background: #dc2626; color: white; }}
.retry {{ background: #f59e0b; color: #111827; }}
.neutral {{ background: #334155; color: white; }}
pre {{
  white-space: pre-wrap;
  background: #0b0d12;
  border-radius: 12px;
  padding: 16px;
  overflow: auto;
}}
small {{ color: #9ca3af; }}
</style>
<script>
function copyCommand(cmd) {{
  navigator.clipboard.writeText(cmd);
  alert("Copied command:\\n" + cmd);
}}
</script>
</head>
<body>
<h1>Link Self-Learning Dashboard</h1>
<small>{esc(data.get("version"))} · {esc(data.get("generated"))}</small>

<div class="panel">
  <h2>Status</h2>
  <p>{esc(data.get("next_action"))}</p>
  <div class="grid">
    {"".join(cards)}
  </div>
</div>

<div class="panel">
  <h2>Current Work</h2>
  <p><b>Pending task:</b> {esc(summary.get("pending_task_id"))} — {esc(summary.get("pending_task_title"))}</p>
  <p><b>Pending draft:</b> {esc(summary.get("pending_draft_id"))} — {esc(summary.get("pending_draft_goal"))}</p>
  <p><b>Approved draft:</b> {esc(summary.get("approved_draft_id"))} — {esc(summary.get("approved_draft_goal"))}</p>
</div>

<div class="panel">
  <h2>Approval Controls</h2>
  <button class="yes" onclick="copyCommand('{esc(commands.get("yes"))}')">YES</button>
  <button class="no" onclick="copyCommand('{esc(commands.get("no"))}')">NO</button>
  <button class="retry" onclick="copyCommand('{esc(commands.get("try_again"))}')">TRY AGAIN</button>
  <button class="neutral" onclick="copyCommand('{esc(commands.get("tick"))}')">RUN ONE TICK</button>
  <button class="neutral" onclick="copyCommand('{esc(commands.get("growth"))}')">FIND GROWTH WORK</button>
  <p><small>Buttons copy terminal commands for now. Next upgrade can turn these into real local web actions.</small></p>
</div>

<div class="panel">
  <h2>Copy/Paste Receipt</h2>
  <pre>{markdown}</pre>
</div>
</body>
</html>
"""


def write_dashboard(data: dict[str, Any], root: Path) -> Path:
    out_dir = root / ".link" / "dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "self_learning_dashboard.html"
    out.write_text(render_html(data), encoding="utf-8")
    receipt = out_dir / f"{now().replace(':', '').replace('-', '').replace('T', '-')}-dashboard.json"
    receipt.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Link self-learning dashboard.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render")
    render.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    render.add_argument("--write", action="store_true")
    render.add_argument("--healthcheck", action="store_true")
    render.add_argument("--root", default=".")

    args = parser.parse_args()
    root = Path(args.root).resolve()
    data = build_dashboard(root=root, include_healthcheck=args.healthcheck)

    written = None
    if args.write:
        written = write_dashboard(data, root)

    if args.format == "json":
        data = dict(data)
        data["written_dashboard_path"] = str(written) if written else None
        print(json.dumps(data, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(data))
    else:
        print(render_markdown(data), end="")
        if written:
            print(f"\nWritten dashboard: `{written}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
