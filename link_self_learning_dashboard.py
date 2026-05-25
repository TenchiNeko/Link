#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from link_dashboard_proposal_refill import ensure_pending_approval_draft

from link_dashboard_approval_contract import build_approval_contract, render_html as render_contract_html, render_markdown as render_contract_markdown


SELF_LEARNING_DASHBOARD_VERSION = "LU110-self-learning-dashboard-approval-sync-v1"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def run(cmd: list[str], root: Path, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
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


def count_json(path: Path) -> int:
    return len(list(path.glob("*.json"))) if path.exists() else 0


def latest_json(path: Path) -> str | None:
    if not path.exists():
        return None
    files = sorted(path.glob("*.json"))
    return str(files[-1]) if files else None


def _build_dashboard_impl(root: Path, run_healthcheck: bool = False, include_healthcheck: bool | None = None) -> dict[str, Any]:
    # dashboard-refill:auto
    root = Path(root)
    try:
        ensure_pending_approval_draft(root=root, source="dashboard-render", write=True)
    except Exception:
        pass
    branch_exit, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    head_exit, head = run(["git", "log", "-1", "--oneline"], root)
    status_exit, status = run(["git", "status", "--short"], root)

    health_exit = None
    health_tail = ""
    if run_healthcheck:
        health_exit, health_tail = run(["python3", "link_healthcheck.py"], root, timeout=120)

    agent_root = root / ".link" / "agent_queue"
    draft_root = root / ".link" / "patch_drafts"
    contract = build_approval_contract(root)

    queue_counts = {
        "agent_pending": count_json(agent_root / "pending"),
        "agent_running": count_json(agent_root / "running"),
        "agent_done": count_json(agent_root / "done"),
        "agent_blocked": count_json(agent_root / "blocked"),
        "agent_receipts": count_json(agent_root / "receipts"),
        "draft_pending": count_json(draft_root / "pending"),
        "draft_approved": count_json(draft_root / "approved"),
        "draft_rejected": count_json(draft_root / "rejected"),
        "draft_retry": count_json(draft_root / "retry"),
        "draft_receipts": count_json(draft_root / "receipts"),
    }

    if contract.get("present") and contract.get("can_approve"):
        mode = "waiting_approval_synced"
        next_action = "Read Approval Target, then choose YES / NO / TRY AGAIN."
    elif contract.get("present"):
        mode = "waiting_approval_blocked"
        next_action = contract.get("disable_reason")
    elif queue_counts["agent_pending"] > 0:
        mode = "ready_for_tick"
        next_action = "Run one tick."
    else:
        mode = "idle"
        next_action = "No pending work; find growth work or seed new queue."

    return {
        "version": SELF_LEARNING_DASHBOARD_VERSION,
        "generated": now(),
        "mode": mode,
        "next_action": next_action,
        "git": {
            "branch": branch if branch_exit == 0 else "unknown",
            "head": head if head_exit == 0 else "unknown",
            "working_tree_clean": status_exit == 0 and not bool(status.strip()),
            "status": status,
        },
        "health": {
            "ran": run_healthcheck,
            "exit": health_exit,
            "passed": health_exit == 0 if health_exit is not None else None,
            "tail": "\n".join(health_tail.splitlines()[-30:]) if health_tail else "",
        },
        "counts": queue_counts,
        "receipts": {
            "latest_agent_pending": latest_json(agent_root / "pending"),
            "latest_agent_receipt": latest_json(agent_root / "receipts"),
            "latest_draft_pending": latest_json(draft_root / "pending"),
            "latest_draft_approved": latest_json(draft_root / "approved"),
            "latest_draft_receipt": latest_json(draft_root / "receipts"),
        },
        "approval_contract": contract,
    }


def add_dashboard_compat_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Expose old healthcheck keys while keeping the newer dashboard schema."""
    counts = data.get("counts") or data.get("queue_counts") or {}

    if "agent_queue_counts" not in data:
        data["agent_queue_counts"] = {
            "pending": counts.get("agent_pending", 0),
            "running": counts.get("agent_running", 0),
            "done": counts.get("agent_done", 0),
            "blocked": counts.get("agent_blocked", 0),
            "receipts": counts.get("agent_receipts", 0),
        }

    if "patch_draft_counts" not in data:
        data["patch_draft_counts"] = {
            "pending": counts.get("draft_pending", 0),
            "approved": counts.get("draft_approved", 0),
            "rejected": counts.get("draft_rejected", 0),
            "retry": counts.get("draft_retry", 0),
            "receipts": counts.get("draft_receipts", 0),
        }

    return add_dashboard_compat_keys(data)
def render_markdown(dashboard: dict[str, Any]) -> str:
    c = dashboard["counts"]
    lines = [
        "# Link Self-Learning Dashboard",
        "",
        f"Version: `{dashboard['version']}`",
        f"Generated: `{dashboard['generated']}`",
        f"Mode: **{dashboard['mode']}**",
        f"Next action: {dashboard['next_action']}",
        "",
        "## Git / Health",
        f"- Branch: `{dashboard['git']['branch']}`",
        f"- HEAD: `{dashboard['git']['head']}`",
        f"- Working tree clean: **{dashboard['git']['working_tree_clean']}**",
        f"- Healthcheck passed: **{dashboard['health']['passed']}**",
        "",
        "## Queue Counts",
    ]
    for key, value in c.items():
        lines.append(f"- `{key}`: **{value}**")
    lines += [
        "",
        render_contract_markdown(dashboard["approval_contract"]),
        "",
        "## Receipts",
    ]
    for key, value in dashboard["receipts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines += [
        "",
        "## Safety Boundary",
        "- Buttons may inspect queues, write local .link receipts, approve/reject drafts, and run safe tick/growth commands.",
        "- Source edits, commits, pushes, destructive commands, and unknown external code remain approval-gated.",
        "- YES is disabled whenever the visible proposal cannot be synced to an exact draft/hash.",
    ]
    return "\n".join(lines)


def build_copy_box_text(data: dict[str, Any]) -> str:
    """Build a compact, safe copy box from the current dashboard contract.

    The big visual Approval Target can still render below. This box is only for
    copy/paste and must never become a stale or malformed source of truth.
    """
    contract = data.get("approval_contract") or {}
    draft_id = contract.get("draft_id") or ""
    draft_file = contract.get("draft_file") or ""
    proposal_hash = contract.get("proposal_hash") or ""
    task_id = contract.get("task_id") or ""
    title = contract.get("title") or ""
    status = contract.get("status") or "not ready"
    yes_enabled = contract.get("yes_enabled", False)

    if not draft_id:
        return (
            "## Approval Target\\n\\n"
            "Status: not ready\\n"
            "Reason: No pending approval draft is available.\\n"
        )

    lines = [
        "## Approval Target",
        "",
        f"Draft ID: {draft_id}",
        f"Draft file: {draft_file}",
        f"Proposal hash: {proposal_hash}",
        f"Status: {status}",
        f"Task: {task_id} — {title}",
        f"YES enabled: {yes_enabled}",
        "",
        "Commands:",
        f"YES: python3 link_approval_patch_draft_queue.py decide --action yes --draft-id '{draft_id}' --feedback 'Approved from dashboard.' --format markdown",
        f"NO: python3 link_approval_patch_draft_queue.py decide --action no --draft-id '{draft_id}' --feedback 'Rejected from dashboard.' --format markdown",
        f"TRY AGAIN: python3 link_approval_patch_draft_queue.py decide --action try_again --draft-id '{draft_id}' --feedback 'Try again with Brandon feedback.' --format markdown",
    ]
    return "\\n".join(lines) + "\\n"

def render_html(dashboard: dict[str, Any]) -> str:
    style = """
body { margin: 24px; background: #111827; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; }
h1, h2, h3 { color: #f9fafb; }
.card, .approval-target-card { border: 1px solid #334155; border-radius: 14px; padding: 18px; margin: 14px 0; background: #172033; }
.badge { display: inline-block; border: 1px solid #475569; border-radius: 999px; padding: 5px 9px; margin: 3px; background: #263247; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #020617; border: 1px solid #334155; border-radius: 10px; padding: 12px; color: #e5e7eb; }
textarea { width: 100%; min-height: 72px; background: #020617; color: #e5e7eb; border: 1px solid #334155; border-radius: 8px; padding: 10px; }
button { border: 0; border-radius: 9px; padding: 10px 13px; margin: 5px 4px 0 0; font-weight: 800; }
button:disabled { opacity: .35; filter: grayscale(1); }
.yes { background: #62d26f; color: #052e16; }
.no { background: #ef6262; color: #450a0a; }
.retry { background: #f2c14e; color: #422006; }
.tick { background: #60a5fa; color: #082f49; }
.growth { background: #34d399; color: #022c22; }
.reconcile { background: #f9fafb; color: #111827; }
.danger { color: #fecaca; font-weight: 800; }
.sync-row span { display: inline-block; margin-right: 12px; margin-bottom: 6px; }

.copy { background: #a78bfa; color: #1e1b4b; }
.copy-box { width: 100%; min-height: 190px; margin-top: 10px; background: #020617; color: #e5e7eb; border: 1px solid #334155; border-radius: 8px; padding: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
.copy-status { margin-left: 10px; color: #bbf7d0; font-weight: 700; }
.copy-proposal-panel { margin: 10px 0 14px 0; }

a { color: #93c5fd; }
"""
    counts = " ".join(f"<span class='badge'>{html.escape(k)}: {v}</span>" for k, v in dashboard["counts"].items())
    contract = dashboard["approval_contract"]
    draft_id = html.escape(str(contract.get("draft_id") or ""))
    yes_disabled = "disabled" if not contract.get("can_approve") else ""
    md = html.escape(render_markdown(dashboard))
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Link Self-Learning Dashboard</title>
<style>{style}</style>
</head>
<body>
<h1>Link Self-Learning Dashboard</h1>
<p>Version: <code>{html.escape(dashboard['version'])}</code> · Generated: {html.escape(dashboard['generated'])}</p>
<div class="card">
  <span class="badge">Mode: {html.escape(dashboard['mode'])}</span>
  <span class="badge">Next: {html.escape(str(dashboard['next_action']))}</span>
  <span class="badge">Draft pending: {dashboard['counts']['draft_pending']}</span>
  <span class="badge">Agent pending: {dashboard['counts']['agent_pending']}</span>
  <span class="badge">Receipts: {dashboard['counts']['agent_receipts'] + dashboard['counts']['draft_receipts']}</span>
</div>

{render_contract_html(contract)}

<div class="card">
<h2>Approval Controls</h2>
<p><strong>Dashboard Controls</strong></p>
<form method="post" action="/action">
  <input type="hidden" name="draft_id" value="{draft_id}">
  <textarea name="feedback" placeholder="Feedback for YES / NO / TRY AGAIN. Example: Try again but make the plan smaller and list exact files."></textarea>
  <br>
  <button class="yes" name="action" value="yes" {yes_disabled}>YES</button>
  <button class="no" name="action" value="no">NO</button>
  <button class="retry" name="action" value="try_again">TRY AGAIN</button>
  <button class="tick" name="action" value="run_tick">RUN ONE TICK</button>
  <button class="growth" name="action" value="find_growth">FIND GROWTH WORK</button>
  <button class="reconcile" name="action" value="reconcile">RECONCILE STALE DRAFTS</button>
  <button class="reconcile" name="action" value="refresh">REFRESH</button>
</form>
<p><strong>YES is only enabled when the Approval Target above is complete and synced to the exact draft/hash.</strong></p>
</div>

<div class="card">
<h2>Queue Counts</h2>
{counts}
</div>

<div class="card">
<h2>Full Dashboard Receipt</h2>
<pre>{md}</pre>
</div>
</body>
</html>
"""


def write_dashboard(root: Path, dashboard: dict[str, Any]) -> Path:
    out = root / ".link" / "dashboard" / "self_learning_dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(dashboard), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])

    # Backward compatibility for old broken web-admin call:
    # python3 link_self_learning_dashboard.py markdown
    if argv and argv[0] in {"markdown", "html", "json"}:
        argv = ["render", "--format", argv[0]] + argv[1:]

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    r = sub.add_parser("render")
    r.add_argument("--format", choices=["markdown", "html", "json"], default="markdown")
    r.add_argument("--write", action="store_true")
    r.add_argument("--run-healthcheck", action="store_true")
    r.add_argument("--root", default=".")

    args = parser.parse_args(argv)
    if not args.cmd:
        args.cmd = "render"
        args.format = "markdown"
        args.write = False
        args.run_healthcheck = False
        args.root = "."

    root = Path(args.root).resolve()
    dashboard = build_dashboard(root, run_healthcheck=args.run_healthcheck)

    if args.write:
        written = write_dashboard(root, dashboard)
    else:
        written = None

    if args.format == "json":
        if written:
            dashboard["written_dashboard"] = str(written)
        print(json.dumps(dashboard, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(dashboard))
        if written:
            print(f"\n<!-- Written dashboard: {written} -->")
    else:
        print(render_markdown(dashboard))
        if written:
            print(f"\nWritten dashboard: `{written}`")
    return 0



# BEGIN LINK DASHBOARD COMPAT WRAPPER
def add_dashboard_compat_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Expose old healthcheck keys while keeping the newer dashboard schema."""
    counts = data.get("counts") or data.get("queue_counts") or {}

    data["agent_queue_counts"] = data.get("agent_queue_counts") or {
        "pending": counts.get("agent_pending", 0),
        "running": counts.get("agent_running", 0),
        "done": counts.get("agent_done", 0),
        "blocked": counts.get("agent_blocked", 0),
        "receipts": counts.get("agent_receipts", 0),
    }

    data["patch_draft_counts"] = data.get("patch_draft_counts") or {
        "pending": counts.get("draft_pending", 0),
        "approved": counts.get("draft_approved", 0),
        "rejected": counts.get("draft_rejected", 0),
        "retry": counts.get("draft_retry", 0),
        "receipts": counts.get("draft_receipts", 0),
    }

    return data


def build_dashboard(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility wrapper used by dashboard renderers and older healthcheck code."""
    kwargs.pop("include_healthcheck", None)
    data = _build_dashboard_impl(*args, **kwargs)
    return add_dashboard_compat_keys(data)
# END LINK DASHBOARD COMPAT WRAPPER

if __name__ == "__main__":
    raise SystemExit(main())
