#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


REFILL_VERSION = "LU112-dashboard-proposal-refill-v1"

CORE_FILES = [
    "link_self_learning_dashboard.py",
    "link_self_learning_dashboard_web_admin.py",
    "link_dashboard_approval_contract.py",
    "link_approval_patch_draft_queue.py",
    "link_autonomous_growth_receipt.py",
    "link_autonomous_task_queue.py",
    "link_autonomous_tick_runner.py",
    "link_healthcheck.py",
]

CORE_TESTS = [
    "python3 -m py_compile link_self_learning_dashboard.py link_self_learning_dashboard_web_admin.py link_dashboard_approval_contract.py link_approval_patch_draft_queue.py link_autonomous_growth_receipt.py link_autonomous_task_queue.py link_autonomous_tick_runner.py link_healthcheck.py",
    "python3 link_self_learning_dashboard.py render --format markdown",
    "python3 link_self_learning_dashboard.py render --format html --write",
    "python3 link_approval_patch_draft_queue.py status --format markdown",
    "python3 link_dashboard_proposal_refill.py --write --format markdown",
    "python3 link_healthcheck.py",
    "git diff --check",
]

DEFAULT_PLAN = [
    "Check whether a pending approval draft exists before rendering the dashboard.",
    "If no pending draft exists, create the next safe approval proposal automatically.",
    "If an agent queue task exists, convert that task into a synced approval proposal.",
    "If no agent task exists, create a growth/refill proposal so the loop does not appear stuck.",
    "Require explicit affected files, tests, receipts, and a stable proposal hash before YES is enabled.",
    "Keep YES, NO, and TRY AGAIN tied to the exact visible draft ID.",
    "Write receipts for every automatic refill attempt.",
]


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def slugify(text: str, limit: int = 80) -> str:
    out: list[str] = []
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", ".", "/"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug or "approval-proposal")[:limit].strip("-")


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def list_json(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"))


def done_task_ids(root: Path) -> set[str]:
    done = root / ".link" / "agent_queue" / "done"
    ids: set[str] = set()
    for path in list_json(done):
        data = load_json(path)
        for key in ("id", "task_id"):
            value = data.get(key)
            if value:
                ids.add(str(value))
    return ids


def first_pending_agent_task(root: Path) -> dict[str, Any] | None:
    pending = root / ".link" / "agent_queue" / "pending"
    files = list_json(pending)
    if not files:
        return None
    data = load_json(files[0])
    data["_source_path"] = str(files[0])
    return data


def latest_growth_candidate(root: Path) -> dict[str, Any] | None:
    files = list_json(root / ".link" / "growth_receipts")
    if not files:
        return None

    done = done_task_ids(root)
    for path in reversed(files):
        data = load_json(path)
        candidates = (
            data.get("growth_queue_candidates")
            or data.get("queue_candidates")
            or data.get("candidates")
            or []
        )
        if isinstance(candidates, dict):
            candidates = list(candidates.values())
        if not isinstance(candidates, list):
            continue
        for item in candidates:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("id") or item.get("task_id") or "").strip()
            title = str(item.get("title") or item.get("name") or "").strip()
            if not task_id and not title:
                continue
            if task_id and task_id in done:
                continue
            item["_source_path"] = str(path)
            return item
    return None


def build_proposal(root: Path, source: str) -> dict[str, Any]:
    agent_task = first_pending_agent_task(root)
    growth = None if agent_task else latest_growth_candidate(root)

    if agent_task:
        task_id = str(agent_task.get("id") or agent_task.get("task_id") or "queue-task")
        title = str(agent_task.get("title") or agent_task.get("name") or f"{task_id} queued task")
        risk = str(agent_task.get("risk") or "medium")
        why = str(agent_task.get("why") or "A pending agent queue task is ready to become an approval-gated proposal.")
        goal = str(agent_task.get("goal") or f"Create an approval-gated patch plan for {task_id} {title}.")
        proposal_source = agent_task.get("_source_path")
    elif growth:
        task_id = str(growth.get("id") or growth.get("task_id") or "growth")
        title = str(growth.get("title") or growth.get("name") or f"{task_id} growth task")
        risk = str(growth.get("risk") or "medium")
        why = str(growth.get("why") or "Latest growth receipt identified this as the next useful Link improvement.")
        goal = str(growth.get("goal") or f"Create an approval-gated patch plan for {task_id} {title}.")
        proposal_source = growth.get("_source_path")
    else:
        task_id = "LU113"
        title = "LU113 next autonomous growth proposal"
        risk = "medium"
        why = (
            "No pending agent task or unused growth candidate was available, so Link is creating "
            "a safe refill proposal to keep the dashboard from going idle."
        )
        goal = "Create the next approval-gated Link improvement proposal from current queue, receipts, and healthcheck state."
        proposal_source = "fallback-refill"

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    draft_id = f"{stamp}-manual-{slugify(task_id + ' ' + title)}"

    pending = root / ".link" / "patch_drafts" / "pending"
    receipts_dir = root / ".link" / "patch_drafts" / "receipts"
    json_path = pending / f"{draft_id}.json"
    md_path = pending / f"{draft_id}.md"

    return {
        "draft_version": REFILL_VERSION,
        "id": draft_id,
        "draft_id": draft_id,
        "created": now(),
        "generated": now(),
        "status": "waiting_approval",
        "approval_required": True,
        "source": source,
        "proposal_source": proposal_source,
        "task_id": task_id,
        "title": title,
        "risk": risk,
        "goal": goal,
        "why": why,
        "proposed_plan": DEFAULT_PLAN,
        "plan": DEFAULT_PLAN,
        "files_affected": CORE_FILES,
        "affected_files": CORE_FILES,
        "tests": CORE_TESTS,
        "checks": CORE_TESTS,
        "receipt_paths": [
            str(json_path),
            str(md_path),
            ".link/patch_drafts/receipts/",
            ".link/growth_receipts/",
            ".link/agent_queue/receipts/",
        ],
        "receipts": [
            str(json_path),
            str(md_path),
            ".link/patch_drafts/receipts/",
            ".link/growth_receipts/",
            ".link/agent_queue/receipts/",
        ],
        "allowed_without_approval": [
            "inspect repo state",
            "read local queue files",
            "write .link runtime receipts",
            "generate approval proposals",
        ],
        "requires_approval": [
            "source edits",
            "commits",
            "pushes",
            "destructive shell commands",
            "unknown external code",
        ],
        "_json_path": str(json_path),
        "_md_path": str(md_path),
        "_receipt_path": str(receipts_dir / f"{draft_id}-created.json"),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Link Dashboard Proposal Refill",
        "",
        f"Version: `{REFILL_VERSION}`",
        f"Status: **{result.get('status')}**",
        f"Action: `{result.get('action')}`",
    ]
    if result.get("draft_id"):
        lines += [
            f"Draft: `{result.get('draft_id')}`",
            f"Task: `{result.get('task_id')}` — **{result.get('title')}**",
            f"Risk: **{result.get('risk')}**",
            f"Path: `{result.get('draft_path')}`",
        ]
    if result.get("reason"):
        lines += ["", f"Reason: {result.get('reason')}"]
    return "\n".join(lines) + "\n"


def write_proposal(root: Path, proposal: dict[str, Any]) -> None:
    json_path = Path(proposal["_json_path"])
    md_path = Path(proposal["_md_path"])
    receipt_path = Path(proposal["_receipt_path"])

    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    json_payload = {k: v for k, v in proposal.items() if not k.startswith("_")}
    json_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md = "# Link Approval-Gated Patch Draft Queue\n\n"
    md += f"Draft: `{proposal['draft_id']}`\n"
    md += "Status: **waiting_approval**\n\n"
    md += "## Proposal\n\n"
    md += f"- Task: `{proposal['task_id']}` — **{proposal['title']}**\n"
    md += f"- Risk: **{proposal['risk']}**\n\n"
    md += "## Why\n\n"
    md += f"{proposal['why']}\n\n"
    md += "## Proposed Plan\n"
    md += "\n".join(f"- {item}" for item in proposal["proposed_plan"]) + "\n\n"
    md += "## Files / Areas Affected\n"
    md += "\n".join(f"- `{item}`" for item in proposal["files_affected"]) + "\n\n"
    md += "## Tests / Checks\n"
    md += "\n".join(f"- `{item}`" for item in proposal["tests"]) + "\n\n"
    md += "## Button Meaning\n\n"
    md += "- **YES** approves this exact visible draft/hash only.\n"
    md += "- **NO** rejects this exact visible draft and stores feedback.\n"
    md += "- **TRY AGAIN** moves this exact visible draft to retry with feedback.\n"
    md_path.write_text(md, encoding="utf-8")

    receipt = {
        "receipt_version": "dashboard-proposal-refill-created-v1",
        "version": REFILL_VERSION,
        "created": now(),
        "draft_id": proposal["draft_id"],
        "task_id": proposal["task_id"],
        "json": str(json_path),
        "md": str(md_path),
        "source": proposal.get("source"),
        "proposal_source": proposal.get("proposal_source"),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_pending_approval_draft(
    root: Path | str | None = None,
    source: str = "dashboard",
    write: bool = True,
) -> dict[str, Any]:
    root_path = Path(root or ".").resolve()
    pending = root_path / ".link" / "patch_drafts" / "pending"
    pending.mkdir(parents=True, exist_ok=True)

    existing = list_json(pending)
    if existing:
        data = load_json(existing[-1])
        return {
            "version": REFILL_VERSION,
            "status": "ok",
            "action": "already_pending",
            "draft_id": data.get("draft_id") or data.get("id") or existing[-1].stem,
            "task_id": data.get("task_id"),
            "title": data.get("title"),
            "risk": data.get("risk"),
            "draft_path": str(existing[-1]),
            "reason": "Pending approval draft already exists.",
        }

    proposal = build_proposal(root_path, source=source)
    if write:
        write_proposal(root_path, proposal)

    return {
        "version": REFILL_VERSION,
        "status": "ok",
        "action": "created_pending",
        "draft_id": proposal["draft_id"],
        "task_id": proposal["task_id"],
        "title": proposal["title"],
        "risk": proposal["risk"],
        "draft_path": proposal["_json_path"],
        "reason": "No pending draft existed, so a new approval proposal was created.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure the Link dashboard always has a pending approval proposal.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    result = ensure_pending_approval_draft(root=Path(args.root), source=args.source, write=args.write)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_markdown(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
