#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any


APPROVAL_GATED_PATCH_DRAFT_QUEUE_VERSION = "LU107-approval-gated-patch-draft-queue-v1"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def run(cmd: list[str], root: Path, timeout: int = 20) -> tuple[int, str]:
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


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "patch-draft"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def queue_root(root: Path) -> Path:
    return root / ".link" / "agent_queue"


def patch_draft_root(root: Path) -> Path:
    return root / ".link" / "patch_drafts"


def first_pending_task(root: Path) -> tuple[Path | None, dict[str, Any]]:
    pending = queue_root(root) / "pending"
    if not pending.exists():
        return None, {}
    for path in sorted(pending.glob("*.json")):
        data = load_json(path)
        if data:
            return path, data
    return None, {}


def safe_planning_command(task: dict[str, Any]) -> str:
    task_id = str(task.get("task_id") or task.get("id") or "TASK").strip()
    title = str(task.get("title") or "queued task").strip()
    goal = f"Plan {task_id} {title}".strip()
    return f"python3 link_task_receipt.py --goal {shlex.quote(goal)} --format markdown"


def git_summary(root: Path) -> dict[str, Any]:
    status_code, status = run(["git", "status", "--short"], root)
    branch_code, branch = run(["git", "branch", "--show-current"], root)
    head_code, head = run(["git", "log", "--oneline", "-1"], root)
    return {
        "status_exit": status_code,
        "branch_exit": branch_code,
        "head_exit": head_code,
        "branch": branch,
        "head": head,
        "working_tree_clean": status.strip() == "",
        "status": status,
    }


def build_patch_draft(
    goal: str = "Draft next approval-gated Link patch",
    root: Path | None = None,
) -> dict[str, Any]:
    repo = (root or Path.cwd()).resolve()
    task_path, task = first_pending_task(repo)

    task_id = str(task.get("task_id") or task.get("id") or "manual").strip()
    title = str(task.get("title") or goal).strip()
    risk = str(task.get("risk") or "medium").strip()
    priority = task.get("priority")
    command = str(task.get("command") or "").strip() or safe_planning_command(task)

    draft = {
        "draft_version": APPROVAL_GATED_PATCH_DRAFT_QUEUE_VERSION,
        "generated": now(),
        "goal": goal,
        "repo": str(repo),
        "git": git_summary(repo),
        "ok": True,
        "non_destructive": True,
        "approval_required": True,
        "source_edits_written": False,
        "commits_created": False,
        "pushes_created": False,
        "destructive_commands_run": False,
        "source_task_path": str(task_path) if task_path else None,
        "task": {
            "task_id": task_id,
            "title": title,
            "risk": risk,
            "priority": priority,
            "command": command,
        },
        "allowed_without_approval": [
            "inspect queue state",
            "read repository files",
            "generate local .link patch draft receipts",
            "run read-only git status/diff/log",
            "run safe planning receipts",
        ],
        "blocked_until_approval": [
            "source file edits",
            "git add",
            "git commit",
            "git push",
            "destructive shell commands",
            "force push",
            "reset hard",
            "clean -fdx",
        ],
        "proposed_patch_flow": [
            "Read the next pending queue task.",
            "Create an approval-gated draft under .link/patch_drafts/pending.",
            "Show the exact intended files, tests, and safety gates.",
            "Wait for Brandon approval before any source edit.",
            "After approval, perform the smallest useful patch.",
            "Run compile, smoke, healthcheck, and marker checks.",
            "Commit and push only after verification passes.",
        ],
        "recommended_checks": [
            "python3 -m py_compile link_healthcheck.py link_upgrade_registry.py",
            "python3 -m py_compile link_task_patch_runner.py",
            "python3 link_task_receipt.py --goal 'smoke test' --format json",
            "python3 link_healthcheck.py",
        ],
        "approval_prompt": (
            f"Approve drafting/patching for {task_id} — {title}? "
            "Without approval, Link should only write local .link draft receipts."
        ),
        "written_paths": [],
    }
    draft["validation_problems"] = validate_patch_draft(draft)
    draft["ok"] = not draft["validation_problems"]
    return draft


def validate_patch_draft(draft: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if draft.get("approval_required") is not True:
        problems.append("approval_required must be true")
    if draft.get("non_destructive") is not True:
        problems.append("non_destructive must be true")
    if draft.get("source_edits_written") is not False:
        problems.append("source_edits_written must be false")
    if draft.get("commits_created") is not False:
        problems.append("commits_created must be false")
    if draft.get("pushes_created") is not False:
        problems.append("pushes_created must be false")
    blocked = set(draft.get("blocked_until_approval") or [])
    for expected in ["source file edits", "git commit", "git push"]:
        if expected not in blocked:
            problems.append(f"missing blocked action: {expected}")
    return problems


def render_markdown(draft: dict[str, Any]) -> str:
    task = draft.get("task") or {}
    git = draft.get("git") or {}
    lines = [
        "# Link Approval-Gated Patch Draft Queue",
        "",
        f"Version: `{draft.get('draft_version')}`",
        f"Generated: {draft.get('generated')}",
        f"Goal: {draft.get('goal')}",
        f"Status: **{'ready' if draft.get('ok') else 'blocked'}**",
        f"Approval required: **{draft.get('approval_required')}**",
        f"Non-destructive: **{draft.get('non_destructive')}**",
        f"Branch: `{git.get('branch')}`",
        f"HEAD: `{git.get('head')}`",
        f"Working tree clean: **{git.get('working_tree_clean')}**",
        "",
        "## Draft Task",
        "",
        f"- ID: `{task.get('task_id')}`",
        f"- Title: **{task.get('title')}**",
        f"- Priority: **{task.get('priority')}**",
        f"- Risk: **{task.get('risk')}**",
        f"- Source: `{draft.get('source_task_path')}`",
        f"- Safe planning command: `{task.get('command')}`",
        "",
        "## Allowed Without Approval",
    ]
    for item in draft.get("allowed_without_approval") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Blocked Until Approval"])
    for item in draft.get("blocked_until_approval") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Proposed Patch Flow"])
    for item in draft.get("proposed_patch_flow") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Checks"])
    for item in draft.get("recommended_checks") or []:
        lines.append(f"- `{item}`")
    if draft.get("validation_problems"):
        lines.extend(["", "## Validation Problems"])
        for item in draft.get("validation_problems") or []:
            lines.append(f"- {item}")
    if draft.get("written_paths"):
        lines.extend(["", "## Written Paths"])
        for item in draft.get("written_paths") or []:
            lines.append(f"- `{item}`")
    lines.extend([
        "",
        "## Approval Prompt",
        "",
        draft.get("approval_prompt") or "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def render_html(draft: dict[str, Any]) -> str:
    body = html.escape(render_markdown(draft))
    return (
        f'<section class="link-approval-gated-patch-draft-queue" '
        f'data-version="{html.escape(APPROVAL_GATED_PATCH_DRAFT_QUEUE_VERSION)}">'
        f"<h2>Link Approval-Gated Patch Draft Queue</h2><pre>{body}</pre></section>"
    )


def write_outputs(root: Path, draft: dict[str, Any]) -> list[str]:
    out = patch_draft_root(root) / "pending"
    out.mkdir(parents=True, exist_ok=True)
    task = draft.get("task") or {}
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = slugify(f"{task.get('task_id', 'task')}-{task.get('title', 'patch-draft')}")
    json_path = out / f"{stamp}-{slug}.json"
    md_path = out / f"{stamp}-{slug}.md"
    draft["written_paths"] = [str(json_path), str(md_path)]
    json_path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(draft), encoding="utf-8")
    return draft["written_paths"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default="Draft next approval-gated Link patch")
    ap.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    root = Path.cwd()
    draft = build_patch_draft(args.goal, root=root)

    if args.write and draft.get("ok"):
        write_outputs(root, draft)

    if args.format == "json":
        print(json.dumps(draft, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(draft))
    else:
        print(render_markdown(draft), end="")
        if args.write and draft.get("written_paths"):
            print(f"\nWritten: `{draft['written_paths'][0]}`")
    return 0 if draft.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
