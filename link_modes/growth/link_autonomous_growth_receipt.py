#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
from pathlib import Path
from typing import Any


AUTONOMOUS_GROWTH_RECEIPT_VERSION = "LU103-autonomous-growth-receipt-v1"


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


def _compact(text: Any, limit: int = 180) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def find_research_archives(root: Path) -> list[dict[str, Any]]:
    research = root / "research"
    if not research.exists():
        return []
    archives: list[dict[str, Any]] = []
    for path in sorted(research.rglob("*.zip"))[:25]:
        try:
            stat = path.stat()
            archives.append(
                {
                    "path": _rel(path, root),
                    "size_bytes": stat.st_size,
                    "modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
        except OSError:
            continue
    return archives


def file_signals(root: Path) -> dict[str, bool]:
    names = [
        "link_task_receipt.py",
        "link_task_patch_runner.py",
        "link_worker_profiles.py",
        "link_profile_gate.py",
        "link_model_routing_profiles.py",
        "link_worker_dashboard_card.py",
        "link_worker_dashboard_web_admin.py",
        "link_healthcheck.py",
    ]
    return {name: (root / name).exists() for name in names}


def marker_signals(root: Path) -> dict[str, bool]:
    healthcheck = root / "link_healthcheck.py"
    text = healthcheck.read_text(encoding="utf-8", errors="ignore") if healthcheck.exists() else ""
    markers = [
        "guarded task-to-patch executor OK",
        "concise task receipt format OK",
        "model routing profiles OK",
        "worker dashboard card OK",
        "worker dashboard web admin route OK",
        "worker dashboard evidence index execution receipt web admin route OK",
    ]
    return {marker: marker in text for marker in markers}


def recommended_growth_tasks(root: Path, archives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = [
        {
            "id": "LU104",
            "title": "Autonomous task queue seed",
            "priority": 100,
            "risk": "medium",
            "why": "Gives Link a persistent queue so it can create, rank, and track work without Brandon manually prompting every step.",
            "suggested_paths": [
                ".link/agent_queue/pending",
                ".link/agent_queue/running",
                ".link/agent_queue/done",
                ".link/agent_queue/blocked",
                ".link/agent_queue/receipts",
            ],
        },
        {
            "id": "LU105",
            "title": "Autonomous research reflection",
            "priority": 94,
            "risk": "medium",
            "why": "Lets Link inspect research files and turn them into safe implementation tasks instead of leaving research as passive reference material.",
            "suggested_paths": ["research/", ".link/research_reflections/"],
        },
        {
            "id": "LU106",
            "title": "Autonomous tick runner",
            "priority": 90,
            "risk": "medium",
            "why": "Runs safe read-only queue work on demand or timer while still requiring approval for writes, commits, and pushes.",
            "suggested_paths": ["link_autonomous_tick.py", ".link/agent_queue/receipts/"],
        },
        {
            "id": "LU107",
            "title": "Approval-gated patch draft queue",
            "priority": 88,
            "risk": "high",
            "why": "Allows agents to draft patches while keeping file writes, commits, and pushes behind explicit approval gates.",
            "suggested_paths": [".link/patch_drafts/", "link_task_patch_runner.py"],
        },
    ]
    if archives:
        tasks.insert(
            1,
            {
                "id": "LU104R",
                "title": "Research archive comparison task",
                "priority": 97,
                "risk": "low",
                "why": "There are research zip archives available; Link should compare them to its own architecture before copying ideas.",
                "suggested_paths": [item["path"] for item in archives[:5]],
            },
        )
    return tasks


def build_autonomous_growth_receipt(root: Path, goal: str) -> dict[str, Any]:
    root = root.resolve()
    generated = dt.datetime.now().isoformat(timespec="seconds")

    branch_code, branch = run(["git", "branch", "--show-current"], root)
    head_code, head = run(["git", "log", "--oneline", "-1"], root)
    status_code, status = run(["git", "status", "--short"], root)
    upstream_code, upstream = run(["git", "status", "-sb"], root)

    archives = find_research_archives(root)
    files = file_signals(root)
    markers = marker_signals(root)

    blockers: list[str] = []
    if branch_code != 0:
        blockers.append("could not resolve git branch")
    if head_code != 0:
        blockers.append("could not resolve git HEAD")
    if not files.get("link_healthcheck.py"):
        blockers.append("missing link_healthcheck.py")
    if not files.get("link_task_patch_runner.py"):
        blockers.append("missing task-to-patch runner")

    recommended = recommended_growth_tasks(root, archives)

    return {
        "receipt_version": AUTONOMOUS_GROWTH_RECEIPT_VERSION,
        "generated": generated,
        "repo": str(root),
        "goal": goal,
        "branch": branch,
        "head": head,
        "working_tree_clean": not bool(status.strip()),
        "git_status": status,
        "upstream_state": upstream,
        "file_signals": files,
        "marker_signals": markers,
        "research_archives": archives,
        "recommended_growth_tasks": recommended,
        "next_recommended_task": recommended[0] if recommended else None,
        "blockers": blockers,
        "autonomy_policy": {
            "safe_now": [
                "inspect repository state",
                "read research/reference files",
                "create receipts",
                "seed queued read-only tasks",
                "draft patch plans",
            ],
            "requires_approval": [
                "write source files",
                "modify git history",
                "commit changes",
                "push changes",
                "run destructive cleanup",
            ],
            "denied": [
                "force push",
                "reset --hard without explicit recovery plan",
                "clean -fdx without explicit approval",
                "modify .git metadata directly",
            ],
        },
    }


def validate_autonomous_growth_receipt(receipt: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if receipt.get("receipt_version") != AUTONOMOUS_GROWTH_RECEIPT_VERSION:
        problems.append("wrong receipt version")
    if not receipt.get("goal"):
        problems.append("missing goal")
    if not isinstance(receipt.get("recommended_growth_tasks"), list):
        problems.append("recommended_growth_tasks must be a list")
    if not receipt.get("next_recommended_task"):
        problems.append("missing next recommended task")
    if not isinstance(receipt.get("autonomy_policy"), dict):
        problems.append("missing autonomy policy")
    return problems


def write_growth_receipt(receipt: dict[str, Any], root: Path, out_dir: Path | None = None) -> Path:
    target_dir = out_dir or (root / ".link" / "growth_receipts")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"{stamp}-autonomous-growth-receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_autonomous_growth_markdown(receipt: dict[str, Any]) -> str:
    next_task = receipt.get("next_recommended_task") or {}
    archives = receipt.get("research_archives") or []
    blockers = receipt.get("blockers") or []
    tasks = receipt.get("recommended_growth_tasks") or []

    lines = [
        "# Link Autonomous Growth Receipt",
        "",
        f"Version: `{receipt.get('receipt_version')}`",
        f"Generated: {receipt.get('generated')}",
        f"Goal: {receipt.get('goal')}",
        f"Branch: `{receipt.get('branch')}`",
        f"HEAD: `{_compact(receipt.get('head'))}`",
        f"Working tree clean: **{'yes' if receipt.get('working_tree_clean') else 'no'}**",
        "",
        "## Next Recommended Task",
        "",
        f"- ID: `{next_task.get('id', '')}`",
        f"- Title: **{next_task.get('title', '')}**",
        f"- Priority: **{next_task.get('priority', '')}**",
        f"- Risk: **{next_task.get('risk', '')}**",
        f"- Why: {next_task.get('why', '')}",
        "",
        "## Research Archives",
        "",
    ]

    if archives:
        for item in archives[:10]:
            lines.append(f"- `{item.get('path')}` ({item.get('size_bytes')} bytes)")
    else:
        lines.append("- none found")

    lines.extend(["", "## Growth Queue Candidates", ""])
    for task in tasks:
        lines.append(
            f"- `{task.get('id')}` — **{task.get('title')}** — priority {task.get('priority')} — risk `{task.get('risk')}`"
        )

    lines.extend(["", "## Blockers", ""])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Autonomy Boundary",
            "",
            "- Link may inspect, summarize, rank, and draft plans without approval.",
            "- Link must wait for approval before source edits, commits, pushes, or destructive commands.",
        ]
    )
    if receipt.get("written_path"):
        lines.extend(["", f"Written: `{receipt.get('written_path')}`"])
    return "\n".join(lines) + "\n"


def render_autonomous_growth_html(receipt: dict[str, Any]) -> str:
    return (
        f'<section class="link-autonomous-growth-receipt" '
        f'data-version="{html.escape(str(receipt.get("receipt_version", "")))}">'
        f"<h2>Link Autonomous Growth Receipt</h2>"
        f"<pre>{html.escape(render_autonomous_growth_markdown(receipt))}</pre>"
        f"</section>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Link autonomous growth receipt.")
    parser.add_argument("--goal", default="Find next autonomous Link growth work")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    parser.add_argument("--write", action="store_true", help="write receipt under .link/growth_receipts")
    parser.add_argument("--out-dir", default="", help="optional output directory for --write")
    args = parser.parse_args()

    root = Path.cwd()
    receipt = build_autonomous_growth_receipt(root, args.goal)
    problems = validate_autonomous_growth_receipt(receipt)
    receipt["validation_problems"] = problems
    receipt["ok"] = not problems

    if args.write:
        out_dir = Path(args.out_dir) if args.out_dir else None
        path = write_growth_receipt(receipt, root, out_dir=out_dir)
        receipt["written_path"] = str(path)

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_autonomous_growth_html(receipt))
    else:
        print(render_autonomous_growth_markdown(receipt), end="")


if __name__ == "__main__":
    main()
