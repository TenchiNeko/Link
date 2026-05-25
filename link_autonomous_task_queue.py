#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path
from typing import Any


AUTONOMOUS_TASK_QUEUE_VERSION = "LU104-autonomous-task-queue-seed-v1"

QUEUE_STATES = ["pending", "running", "done", "blocked", "receipts"]


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def queue_root(root: Path) -> Path:
    return root / ".link" / "agent_queue"


def ensure_queue_dirs(root: Path) -> dict[str, str]:
    base = queue_root(root)
    paths: dict[str, str] = {}
    for state in QUEUE_STATES:
        path = base / state
        path.mkdir(parents=True, exist_ok=True)
        paths[state] = str(path)
    return paths


def slugify(text: str, limit: int = 80) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").lower()).strip("-")
    value = re.sub(r"-+", "-", value)
    return (value[:limit].strip("-") or "task")


def latest_growth_receipt(root: Path) -> dict[str, Any] | None:
    receipts = sorted((root / ".link" / "growth_receipts").glob("*-autonomous-growth-receipt.json"))
    for path in reversed(receipts):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def default_growth_tasks() -> list[dict[str, Any]]:
    return [
        {
            "id": "LU105",
            "title": "Autonomous research reflection",
            "priority": 94,
            "risk": "medium",
            "why": "Inspect research zips and turn useful concepts into safe Link implementation tasks.",
            "suggested_paths": ["research/", ".link/research_reflections/"],
        },
        {
            "id": "LU106",
            "title": "Autonomous tick runner",
            "priority": 90,
            "risk": "medium",
            "why": "Run safe read-only queue work on demand or by timer while keeping writes approval-gated.",
            "suggested_paths": ["link_autonomous_tick.py", ".link/agent_queue/receipts/"],
        },
        {
            "id": "LU107",
            "title": "Approval-gated patch draft queue",
            "priority": 88,
            "risk": "high",
            "why": "Let agents draft patch plans and patch files while requiring approval before source edits, commits, and pushes.",
            "suggested_paths": [".link/patch_drafts/", "link_task_patch_runner.py"],
        },
    ]


def growth_tasks(root: Path) -> tuple[str, list[dict[str, Any]]]:
    receipt = latest_growth_receipt(root)
    if receipt:
        tasks = receipt.get("recommended_growth_tasks") or []
        if tasks:
            return "latest-growth-receipt", tasks

    try:
        from link_autonomous_growth_receipt import build_autonomous_growth_receipt

        generated = build_autonomous_growth_receipt(root, "Seed autonomous task queue")
        tasks = generated.get("recommended_growth_tasks") or []
        if tasks:
            return "live-growth-receipt", tasks
    except Exception:
        pass

    return "default-growth-tasks", default_growth_tasks()


def existing_task_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    base = queue_root(root)
    for state in QUEUE_STATES:
        for path in (base / state).glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                task_id = str(data.get("task_id") or data.get("id") or "").strip()
                if task_id:
                    ids.add(task_id)
            except Exception:
                continue
    return ids


def task_payload(task: dict[str, Any], source: str, rank: int) -> dict[str, Any]:
    task_id = str(task.get("id") or f"TASK-{rank:03d}").strip()
    title = str(task.get("title") or task_id).strip()
    return {
        "queue_receipt_version": AUTONOMOUS_TASK_QUEUE_VERSION,
        "task_id": task_id,
        "title": title,
        "status": "pending",
        "rank": rank,
        "priority": task.get("priority", 50),
        "risk": task.get("risk", "medium"),
        "source": source,
        "created": now(),
        "why": task.get("why", ""),
        "suggested_paths": task.get("suggested_paths", []),
        "approval_policy": {
            "may_do_without_approval": [
                "read files",
                "inspect repo state",
                "write local queue receipts under .link/",
                "produce plans",
            ],
            "requires_approval": [
                "edit source files",
                "commit changes",
                "push changes",
                "run destructive cleanup",
            ],
        },
        "recommended_next_command": (
            f'python3 link_task_receipt.py --goal "Plan {task_id} {title}" --format markdown'
        ),
    }


def queue_counts(root: Path) -> dict[str, int]:
    base = queue_root(root)
    counts: dict[str, int] = {}
    for state in QUEUE_STATES:
        counts[state] = len(list((base / state).glob("*.json"))) if (base / state).exists() else 0
    return counts


def build_autonomous_task_queue_seed(
    root: Path,
    goal: str = "Seed autonomous task queue",
    limit: int = 10,
    write: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    source, tasks = growth_tasks(root)
    existing = existing_task_ids(root)
    dirs = ensure_queue_dirs(root) if write else {state: str(queue_root(root) / state) for state in QUEUE_STATES}

    queued: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    written_paths: list[str] = []

    for rank, task in enumerate(tasks[:limit], start=1):
        payload = task_payload(task, source=source, rank=rank)
        task_id = payload["task_id"]

        if task_id in existing:
            skipped.append({"task_id": task_id, "reason": "already exists in queue"})
            continue

        if write:
            pending = Path(dirs["pending"])
            filename = f"{rank:03d}-{slugify(task_id + '-' + payload['title'])}.json"
            path = pending / filename
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written_paths.append(str(path))
            existing.add(task_id)

        queued.append(payload)

    return {
        "receipt_version": AUTONOMOUS_TASK_QUEUE_VERSION,
        "generated": now(),
        "repo": str(root),
        "goal": goal,
        "queue_root": str(queue_root(root)),
        "queue_dirs": dirs,
        "source": source,
        "write_requested": write,
        "queued_count": len(queued),
        "skipped_count": len(skipped),
        "written_paths": written_paths,
        "queued_tasks": queued,
        "skipped_tasks": skipped,
        "queue_counts": queue_counts(root),
        "next_task": queued[0] if queued else None,
        "non_destructive_boundary": "Queue seeding writes only local .link queue files; source edits, commits, and pushes still require approval.",
    }


def validate_autonomous_task_queue_seed(receipt: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if receipt.get("receipt_version") != AUTONOMOUS_TASK_QUEUE_VERSION:
        problems.append("wrong receipt version")
    if not receipt.get("queue_root"):
        problems.append("missing queue root")
    if not isinstance(receipt.get("queue_dirs"), dict):
        problems.append("missing queue dirs")
    for state in QUEUE_STATES:
        if state not in receipt.get("queue_dirs", {}):
            problems.append(f"missing queue state: {state}")
    if not isinstance(receipt.get("queued_tasks"), list):
        problems.append("queued_tasks must be a list")
    return problems


def render_autonomous_task_queue_markdown(receipt: dict[str, Any]) -> str:
    next_task = receipt.get("next_task") or {}
    lines = [
        "# Link Autonomous Task Queue Seed",
        "",
        f"Version: `{receipt.get('receipt_version')}`",
        f"Generated: {receipt.get('generated')}",
        f"Goal: {receipt.get('goal')}",
        f"Source: `{receipt.get('source')}`",
        f"Queue root: `{receipt.get('queue_root')}`",
        f"Write requested: **{'yes' if receipt.get('write_requested') else 'no'}**",
        f"Queued: **{receipt.get('queued_count')}**",
        f"Skipped: **{receipt.get('skipped_count')}**",
        "",
        "## Next Task",
        "",
    ]

    if next_task:
        lines.extend(
            [
                f"- ID: `{next_task.get('task_id')}`",
                f"- Title: **{next_task.get('title')}**",
                f"- Priority: **{next_task.get('priority')}**",
                f"- Risk: **{next_task.get('risk')}**",
                f"- Command: `{next_task.get('recommended_next_command')}`",
            ]
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Queue Counts", ""])
    for state, count in (receipt.get("queue_counts") or {}).items():
        lines.append(f"- `{state}`: **{count}**")

    lines.extend(["", "## Queued Tasks", ""])
    queued = receipt.get("queued_tasks") or []
    if queued:
        for task in queued:
            lines.append(
                f"- `{task.get('task_id')}` — **{task.get('title')}** — priority {task.get('priority')} — risk `{task.get('risk')}`"
            )
    else:
        lines.append("- none")

    if receipt.get("written_paths"):
        lines.extend(["", "## Written Paths", ""])
        for path in receipt["written_paths"]:
            lines.append(f"- `{path}`")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- {receipt.get('non_destructive_boundary')}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_autonomous_task_queue_html(receipt: dict[str, Any]) -> str:
    return (
        f'<section class="link-autonomous-task-queue-seed" '
        f'data-version="{html.escape(str(receipt.get("receipt_version", "")))}">'
        f"<h2>Link Autonomous Task Queue Seed</h2>"
        f"<pre>{html.escape(render_autonomous_task_queue_markdown(receipt))}</pre>"
        f"</section>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Link autonomous task queue.")
    parser.add_argument("--goal", default="Seed autonomous task queue")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--seed", action="store_true", help="write pending queue tasks under .link/agent_queue")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    args = parser.parse_args()

    receipt = build_autonomous_task_queue_seed(Path.cwd(), args.goal, limit=args.limit, write=args.seed)
    problems = validate_autonomous_task_queue_seed(receipt)
    receipt["validation_problems"] = problems
    receipt["ok"] = not problems

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_autonomous_task_queue_html(receipt))
    else:
        print(render_autonomous_task_queue_markdown(receipt), end="")


if __name__ == "__main__":
    main()
