#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path
from typing import Any


REFILL_VERSION = "LU115-dashboard-draft-recovery-refill-v1"

GENERIC_PATTERNS = [
    "next autonomous growth proposal",
    "safe refill proposal",
    "generic refill",
    "keep the dashboard from going idle",
    "so the loop does not appear stuck",
    "no pending agent task or unused growth candidate",
    "no pending agent task",
    "unused growth candidate",
    "growth/refill proposal",
]

CONCRETE_PROPOSALS: list[dict[str, Any]] = [
    {
        "task_id": "LU115",
        "title": "approval queue stale draft auditor",
        "risk": "medium",
        "why": "The dashboard needs a concrete auditor that detects stale, duplicate, generic, or already-decided pending drafts before they can keep the UI stuck on a bad approval target.",
        "proposed_plan": [
            "Add a stale draft auditor for the approval queue.",
            "Detect pending drafts that are generic, missing required fields, already decided, duplicated, or unsafe to approve.",
            "Move bugged drafts to a blocked folder with a receipt instead of leaving them visible.",
            "Expose the auditor result in the dashboard so Brandon can see why a draft was cleared.",
            "Add healthcheck coverage for generic/self-loop draft blocking.",
        ],
        "files_affected": [
            "link_dashboard_proposal_refill.py",
            "link_dashboard_approval_contract.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    },
    {
        "task_id": "LU116",
        "title": "dashboard action result banner",
        "risk": "medium",
        "why": "Dashboard button clicks need visible results so Brandon can tell whether YES, NO, TRY AGAIN, CLEAR BUGGED DRAFT, or GENERATE NEW DRAFT actually changed state.",
        "proposed_plan": [
            "Add an action result banner to the web dashboard.",
            "Show command output, exit code, and the refreshed current draft ID after every button click.",
            "Make failed actions visually obvious without leaving stale HTML on screen.",
            "Preserve no-cache headers so mobile browsers do not show an old approval target.",
            "Add smoke coverage for the result banner path.",
        ],
        "files_affected": [
            "link_self_learning_dashboard_web_admin.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    },
    {
        "task_id": "LU117",
        "title": "concrete growth candidate loader",
        "risk": "medium",
        "why": "When no pending approval draft exists, Link should pull from concrete known upgrade candidates instead of creating vague refill/self-loop proposals.",
        "proposed_plan": [
            "Create a concrete growth candidate loader.",
            "Read candidate tasks from receipts, healthcheck gaps, upgrade registry, or a local candidate seed file.",
            "Require every candidate to name a behavior change and affected files before it can become an approval draft.",
            "Block candidates that only say refill, growth, or keep-alive without a real change.",
            "Add healthcheck coverage for candidate quality gates.",
        ],
        "files_affected": [
            "link_dashboard_proposal_refill.py",
            "link_autonomous_growth_receipt.py",
            "link_autonomous_task_queue.py",
            "link_healthcheck.py",
        ],
    },
    {
        "task_id": "LU118",
        "title": "proposal uniqueness receipt index",
        "risk": "medium",
        "why": "Repeated proposal IDs and repeated task ideas make the dashboard look alive while cycling the same stale work.",
        "proposed_plan": [
            "Add a proposal uniqueness index across pending, approved, rejected, retry, blocked, and receipt folders.",
            "Prevent a task ID/title from being generated again after it was approved, rejected, retried, or blocked.",
            "Write a uniqueness receipt whenever a duplicate proposal is skipped.",
            "Show skipped duplicate count in the dashboard.",
            "Add tests for repeated LU113-style proposal blocking.",
        ],
        "files_affected": [
            "link_dashboard_proposal_refill.py",
            "link_dashboard_approval_contract.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    },
]


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def queue_root(root: Path) -> Path:
    return root / ".link" / "patch_drafts"


def pending_dir(root: Path) -> Path:
    return queue_root(root) / "pending"


def receipts_dir(root: Path) -> Path:
    return queue_root(root) / "receipts"


def blocked_dir(root: Path) -> Path:
    return queue_root(root) / "blocked"


def pending_jsons(root: Path) -> list[Path]:
    d = pending_dir(root)
    if not d.exists():
        return []
    return sorted(d.glob("*.json"))


def text_blob(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, default=str).lower()


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def draft_task_id(data: dict[str, Any]) -> str:
    task = data.get("task")
    if isinstance(task, dict):
        return str(task.get("id") or task.get("task_id") or data.get("task_id") or "").strip()
    return str(data.get("task_id") or data.get("task") or "").strip()


def draft_title(data: dict[str, Any]) -> str:
    task = data.get("task")
    if isinstance(task, dict):
        return str(task.get("title") or data.get("title") or "").strip()
    return str(data.get("title") or data.get("name") or "").strip()


def files_from(data: dict[str, Any]) -> list[Any]:
    return (
        as_list(data.get("files_affected"))
        or as_list(data.get("affected_files"))
        or as_list(data.get("files"))
        or as_list(data.get("file_paths"))
    )


def tests_from(data: dict[str, Any]) -> list[Any]:
    return (
        as_list(data.get("tests_checks"))
        or as_list(data.get("tests"))
        or as_list(data.get("checks"))
        or as_list(data.get("recommended_tests"))
    )


def is_generic_or_bugged(data: dict[str, Any]) -> bool:
    blob = text_blob(data)
    task_id = draft_task_id(data).lower()
    title = draft_title(data).lower()
    files = files_from(data)
    tests = tests_from(data)

    if task_id == "lu113":
        return True
    if any(pattern in blob for pattern in GENERIC_PATTERNS):
        return True
    if "not explicitly listed" in blob:
        return True
    if not task_id or not title:
        return True
    if not files or not tests:
        return True

    return False


def move_to_blocked(root: Path, path: Path, reason: str) -> dict[str, Any]:
    blocked = blocked_dir(root)
    receipts = receipts_dir(root)
    blocked.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)

    target = blocked / f"{path.stem}-blocked-{stamp()}.json"
    shutil.move(str(path), str(target))

    md = path.with_suffix(".md")
    md_target = None
    if md.exists():
        md_target = blocked / f"{md.stem}-blocked-{stamp()}.md"
        shutil.move(str(md), str(md_target))

    receipt = {
        "receipt_version": REFILL_VERSION,
        "generated": now(),
        "action": "blocked_bugged_draft",
        "reason": reason,
        "source": str(path.resolve()),
        "target": str(target.resolve()),
        "markdown_target": str(md_target.resolve()) if md_target else None,
    }
    rpath = receipts / f"{path.stem}-blocked-{stamp()}.json"
    rpath.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(rpath.resolve())
    return receipt


def clear_bugged_pending(root: Path) -> list[dict[str, Any]]:
    moved: list[dict[str, Any]] = []
    for path in pending_jsons(root):
        data = load_json(path)
        if is_generic_or_bugged(data):
            moved.append(move_to_blocked(root, path, "Generic, incomplete, stale, or self-loop pending draft."))
    return moved


def dedupe_pending(root: Path) -> list[dict[str, Any]]:
    pending = pending_jsons(root)
    if len(pending) <= 1:
        return []

    keep = pending[-1]
    moved: list[dict[str, Any]] = []
    for path in pending[:-1]:
        moved.append(move_to_blocked(root, path, f"Duplicate pending draft; kept latest pending draft {keep.name}."))
    return moved


def all_existing_task_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    qroot = queue_root(root)
    for folder_name in ["pending", "approved", "rejected", "retry", "blocked", "receipts"]:
        folder = qroot / folder_name
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            data = load_json(path)
            tid = draft_task_id(data) or str(data.get("task_id") or "")
            if tid:
                ids.add(tid.upper())
            title = draft_title(data)
            match = re.search(r"\bLU\d+\b", title.upper())
            if match:
                ids.add(match.group(0))
    return ids


def choose_next_concrete_proposal(root: Path) -> dict[str, Any] | None:
    used = all_existing_task_ids(root)
    for proposal in CONCRETE_PROPOSALS:
        if proposal["task_id"].upper() not in used:
            return proposal
    return None


def default_tests() -> list[str]:
    return [
        "python3 -m py_compile link_dashboard_proposal_refill.py link_self_learning_dashboard.py link_self_learning_dashboard_web_admin.py link_dashboard_approval_contract.py link_healthcheck.py",
        "python3 link_dashboard_proposal_refill.py --clear-bugged --force-new --write --format markdown",
        "python3 link_self_learning_dashboard.py render --format markdown",
        "python3 link_self_learning_dashboard.py render --format html --write",
        "python3 link_self_learning_dashboard_web_admin.py --smoke",
        "python3 link_healthcheck.py",
        "git diff --check",
    ]


def write_draft(root: Path, proposal: dict[str, Any], write: bool) -> dict[str, Any]:
    pending = pending_dir(root)
    receipts = receipts_dir(root)
    pending.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)

    draft_id = f"{stamp()}-manual-{proposal['task_id'].lower()}-{slug(proposal['title'])}"
    json_path = pending / f"{draft_id}.json"
    md_path = pending / f"{draft_id}.md"

    receipt_paths = [
        str(json_path.resolve()),
        str(md_path.resolve()),
        ".link/patch_drafts/receipts/",
        ".link/growth_receipts/",
        ".link/agent_queue/receipts/",
    ]

    data = {
        "receipt_version": "LU107-compatible-approval-draft-v1",
        "generated": now(),
        "draft_id": draft_id,
        "status": "waiting_approval",
        "approval_required": True,
        "task_id": proposal["task_id"],
        "task": {"id": proposal["task_id"], "title": proposal["title"]},
        "title": proposal["title"],
        "risk": proposal.get("risk", "medium"),
        "why": proposal["why"],
        "proposed_plan": proposal["proposed_plan"],
        "files_affected": proposal["files_affected"],
        "affected_files": proposal["files_affected"],
        "tests_checks": default_tests(),
        "tests": default_tests(),
        "receipts": receipt_paths,
        "button_meaning": {
            "YES": "Approve this exact visible draft/hash only.",
            "NO": "Reject this exact visible draft and store feedback.",
            "TRY_AGAIN": "Move this exact visible draft to retry with feedback.",
        },
    }

    md = draft_markdown(data, json_path)

    if write:
        json_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(md, encoding="utf-8")
        receipt = {
            "receipt_version": REFILL_VERSION,
            "generated": now(),
            "action": "created_concrete_proposal",
            "draft_id": draft_id,
            "task_id": proposal["task_id"],
            "title": proposal["title"],
            "draft_path": str(json_path.resolve()),
            "markdown_path": str(md_path.resolve()),
        }
        (receipts / f"{draft_id}-created.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "receipt_version": REFILL_VERSION,
        "generated": now(),
        "status": "ok",
        "action": "created",
        "draft_id": draft_id,
        "task_id": proposal["task_id"],
        "title": proposal["title"],
        "risk": proposal.get("risk", "medium"),
        "path": str(json_path.resolve()),
        "markdown_path": str(md_path.resolve()),
        "reason": "Created next concrete approval proposal.",
    }


def write_no_useful_receipt(root: Path, write: bool, moved: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    receipts = receipts_dir(root)
    receipts.mkdir(parents=True, exist_ok=True)

    receipt_path = receipts / f"{stamp()}-no-useful-proposal-found.json"
    rec = {
        "receipt_version": REFILL_VERSION,
        "generated": now(),
        "status": "blocked",
        "action": "no_useful_proposal_found",
        "reason": "No pending draft and no unused concrete proposal candidate exists. Generic refill/self-loop proposals are blocked.",
        "moved_bugged_drafts": moved or [],
        "receipt_path": str(receipt_path.resolve()),
    }

    if write:
        receipt_path.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    return rec


def slug(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return out or "proposal"


def draft_markdown(data: dict[str, Any], path: Path) -> str:
    lines = [
        "## Approval Target",
        "",
        f"- Draft ID: `{data['draft_id']}`",
        f"- Draft file: `{path.resolve()}`",
        "- Status: **waiting_approval**",
        f"- Task: `{data['task_id']}` — **{data['title']}**",
        f"- Risk: **{data['risk']}**",
        "- YES enabled: **True**",
        "",
        "### Why",
        "",
        data["why"],
        "",
        "### Proposed Plan",
    ]
    lines += [f"- {item}" for item in data["proposed_plan"]]
    lines += ["", "### Files / Areas Affected"]
    lines += [f"- `{item}`" for item in data["files_affected"]]
    lines += ["", "### Tests / Checks"]
    lines += [f"- `{item}`" for item in data["tests_checks"]]
    lines += ["", "### Receipts"]
    lines += [f"- `{item}`" for item in data["receipts"]]
    return "\n".join(lines) + "\n"


def ensure_pending_approval_draft(
    root: Path | str = ".",
    write: bool = True,
    force_new: bool = False,
    clear_bugged: bool = True,
    **_: Any,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    pending_dir(root_path).mkdir(parents=True, exist_ok=True)
    receipts_dir(root_path).mkdir(parents=True, exist_ok=True)

    moved: list[dict[str, Any]] = []
    if clear_bugged:
        moved.extend(clear_bugged_pending(root_path))
    moved.extend(dedupe_pending(root_path))

    pending = pending_jsons(root_path)
    if pending and not force_new:
        latest = pending[-1]
        data = load_json(latest)
        return {
            "receipt_version": REFILL_VERSION,
            "generated": now(),
            "status": "ok",
            "action": "already_pending",
            "draft_id": latest.stem,
            "task_id": draft_task_id(data),
            "title": draft_title(data),
            "risk": data.get("risk", ""),
            "path": str(latest.resolve()),
            "moved_bugged_drafts": moved,
            "reason": "Pending approval draft already exists.",
        }

    if pending and force_new:
        latest = pending[-1]
        data = load_json(latest)
        if not is_generic_or_bugged(data):
            return {
                "receipt_version": REFILL_VERSION,
                "generated": now(),
                "status": "ok",
                "action": "already_pending_valid",
                "draft_id": latest.stem,
                "task_id": draft_task_id(data),
                "title": draft_title(data),
                "risk": data.get("risk", ""),
                "path": str(latest.resolve()),
                "moved_bugged_drafts": moved,
                "reason": "A valid pending draft already exists; not replacing it.",
            }

    proposal = choose_next_concrete_proposal(root_path)
    if not proposal:
        return write_no_useful_receipt(root_path, write=write, moved=moved)

    result = write_draft(root_path, proposal, write=write)
    result["moved_bugged_drafts"] = moved
    return result


def format_markdown(rec: dict[str, Any]) -> str:
    lines = [
        "# Link Dashboard Proposal Refill",
        "",
        f"Version: `{rec.get('receipt_version', REFILL_VERSION)}`",
        f"Status: **{rec.get('status')}**",
        f"Action: `{rec.get('action')}`",
    ]
    if rec.get("draft_id"):
        lines.append(f"Draft: `{rec.get('draft_id')}`")
    if rec.get("task_id") or rec.get("title"):
        lines.append(f"Task: `{rec.get('task_id')}` — **{rec.get('title')}**")
    if rec.get("path"):
        lines.append(f"Path: `{rec.get('path')}`")
    if rec.get("receipt_path"):
        lines.append(f"Receipt: `{rec.get('receipt_path')}`")
    lines += ["", f"Reason: {rec.get('reason', '')}", ""]
    moved = rec.get("moved_bugged_drafts") or []
    if moved:
        lines.append("## Moved Bugged Drafts")
        for item in moved:
            lines.append(f"- `{item.get('source')}` -> `{item.get('target')}`")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--force-new", action="store_true")
    parser.add_argument("--clear-bugged", action="store_true")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    rec = ensure_pending_approval_draft(
        root=args.root,
        write=args.write,
        force_new=args.force_new,
        clear_bugged=True if args.clear_bugged or args.force_new else True,
    )

    if args.format == "json":
        print(json.dumps(rec, indent=2, sort_keys=True, default=str))
    else:
        print(format_markdown(rec))


if __name__ == "__main__":
    main()
