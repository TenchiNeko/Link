#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import shlex
from pathlib import Path
from typing import Any


AUTONOMOUS_TICK_RUNNER_VERSION = "LU106-autonomous-tick-runner-v1"

QUEUE_STATES = ["pending", "running", "done", "blocked", "receipts"]


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def queue_root(root: Path) -> Path:
    return root / ".link" / "agent_queue"


def ensure_queue_dirs(root: Path) -> None:
    base = queue_root(root)
    for state in QUEUE_STATES:
        (base / state).mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"path": str(path), "error": str(exc), "status": "blocked"}


def queue_counts(root: Path) -> dict[str, int]:
    base = queue_root(root)
    counts: dict[str, int] = {}
    for state in QUEUE_STATES:
        folder = base / state
        counts[state] = len(list(folder.glob("*.json"))) if folder.exists() else 0
    return counts


def pending_task_files(root: Path) -> list[Path]:
    pending = queue_root(root) / "pending"
    if not pending.exists():
        return []
    return sorted(pending.glob("*.json"))


def normalize_task(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    task_id = str(data.get("task_id") or data.get("id") or path.stem).strip()
    title = str(data.get("title") or task_id).strip()
    risk = str(data.get("risk") or "unknown").strip()
    try:
        priority = int(data.get("priority", 0))
    except Exception:
        priority = 0

    command = data.get("command") or data.get("suggested_command")
    if not command and str(data.get("status") or "") == "pending_guarded_implementation":
        task_id = str(data.get("task_id") or "").strip()
        title = str(data.get("title") or "").strip()
        goal = f"Implement {task_id} {title}".strip()
        command = (
            "python3 link_task_patch_runner.py "
            f"--goal {shlex.quote(goal)} "
            "--approved --execute --format markdown"
        )
        data["needs_queue_consumer"] = True
        data["implementation_note"] = (
            "This guarded implementation job now dispatches to patch runner, "
            "but the current patch runner only executes safe checks. "
            "A real implementation consumer must edit the target files or create a concrete patch receipt "
            "before this job should move from pending to done."
        )
    if not command:
        command = derive_command(task_id, title)

    return {
        "task_id": task_id,
        "title": title,
        "priority": priority,
        "risk": risk,
        "status": data.get("status") or "pending",
        "source_path": str(path),
        "command": command,
        "raw": data,
    }


def derive_command(task_id: str, title: str) -> str:
    goal = f"Plan {task_id} {title}".strip()
    return "python3 link_task_receipt.py --goal " + shlex.quote(goal) + " --format markdown"


def select_next_task(root: Path) -> dict[str, Any] | None:
    tasks = [normalize_task(path, read_json(path)) for path in pending_task_files(root)]
    if not tasks:
        return None
    tasks.sort(key=lambda item: (-int(item.get("priority", 0)), str(item.get("source_path", ""))))
    return tasks[0]


def build_autonomous_tick(
    goal: str = "Run one autonomous Link tick",
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    repo = root or Path.cwd()
    if write:
        ensure_queue_dirs(repo)

    next_task = select_next_task(repo)
    counts = queue_counts(repo)

    receipt: dict[str, Any] = {
        "receipt_version": AUTONOMOUS_TICK_RUNNER_VERSION,
        "generated": now(),
        "goal": goal,
        "repo": str(repo),
        "queue_root": str(queue_root(repo)),
        "write_requested": bool(write),
        "non_destructive": True,
        "queue_counts": counts,
        "next_task": next_task,
        "suggested_command": next_task.get("command") if next_task else None,
        "status": "ready" if next_task else "idle",
        "action": "plan_next_task" if next_task else "wait_for_work",
        "boundary": [
            "Tick runner may inspect .link queue files and write local receipts.",
            "It must not edit source, commit, push, or run destructive commands without approval.",
            "Missing task commands are converted into safe planning commands only.",
        ],
    }

    if write:
        receipts = queue_root(repo) / "receipts"
        receipts.mkdir(parents=True, exist_ok=True)
        task_id = "idle"
        if next_task:
            task_id = str(next_task.get("task_id") or "task").lower().replace("/", "-")
        path = receipts / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-tick-{task_id}.json"
        receipt["written_path"] = str(path)
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return receipt


def validate_autonomous_tick(receipt: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if receipt.get("receipt_version") != AUTONOMOUS_TICK_RUNNER_VERSION:
        problems.append("receipt version mismatch")
    if receipt.get("non_destructive") is not True:
        problems.append("tick runner must be non-destructive")
    if not isinstance(receipt.get("queue_counts"), dict):
        problems.append("queue counts missing")
    if receipt.get("status") not in {"ready", "idle"}:
        problems.append("unexpected tick status")
    task = receipt.get("next_task")
    if task:
        if not task.get("task_id"):
            problems.append("next task missing task_id")
        if not task.get("title"):
            problems.append("next task missing title")
        if not receipt.get("suggested_command"):
            problems.append("next task missing suggested command")
    if receipt.get("write_requested") and not receipt.get("written_path"):
        problems.append("write requested but written_path missing")
    return problems


def render_autonomous_tick_markdown(receipt: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Link Autonomous Tick Runner",
        "",
        f"Version: `{receipt.get('receipt_version')}`",
        f"Generated: {receipt.get('generated')}",
        f"Goal: {receipt.get('goal')}",
        f"Status: **{receipt.get('status')}**",
        f"Action: `{receipt.get('action')}`",
        f"Queue root: `{receipt.get('queue_root')}`",
        f"Write requested: **{'yes' if receipt.get('write_requested') else 'no'}**",
        "",
        "## Queue Counts",
        "",
    ]

    for state, count in receipt.get("queue_counts", {}).items():
        lines.append(f"- `{state}`: **{count}**")

    task = receipt.get("next_task")
    lines.extend(["", "## Next Task", ""])

    if task:
        lines.extend([
            f"- ID: `{task.get('task_id')}`",
            f"- Title: **{task.get('title')}**",
            f"- Priority: **{task.get('priority')}**",
            f"- Risk: **{task.get('risk')}**",
            f"- Source: `{task.get('source_path')}`",
            f"- Suggested command: `{receipt.get('suggested_command')}`",
        ])
    else:
        lines.append("- No pending task found.")

    lines.extend(["", "## Boundary", ""])
    for item in receipt.get("boundary", []):
        lines.append(f"- {item}")

    if receipt.get("written_path"):
        lines.extend(["", f"Written: `{receipt.get('written_path')}`"])

    return "\n".join(lines)


def render_autonomous_tick_html(receipt: dict[str, Any]) -> str:
    body = html.escape(render_autonomous_tick_markdown(receipt))
    version = html.escape(str(receipt.get("receipt_version", "")))
    return (
        f'<section class="link-autonomous-tick-runner" data-version="{version}">'
        "<h2>Link Autonomous Tick Runner</h2>"
        f"<pre>{body}</pre>"
        "</section>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one safe autonomous Link queue tick.")
    parser.add_argument("--goal", default="Run one autonomous Link tick")
    parser.add_argument("--format", choices=["json", "markdown", "md", "html"], default="markdown")
    parser.add_argument("--write", action="store_true", help="Write a local .link receipt.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    receipt = build_autonomous_tick(
        goal=args.goal,
        root=Path(args.root).resolve(),
        write=args.write,
    )
    problems = validate_autonomous_tick(receipt)
    if problems:
        print("autonomous tick runner validation failures:")
        for problem in problems:
            print("-", problem)
        return 1

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_autonomous_tick_html(receipt))
    else:
        print(render_autonomous_tick_markdown(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
