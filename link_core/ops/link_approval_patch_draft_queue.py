#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import shlex
from pathlib import Path
from typing import Any


APPROVAL_PATCH_DRAFT_QUEUE_VERSION = "LU107-approval-gated-patch-draft-queue-v1"

DRAFT_STATES = ["pending", "approved", "rejected", "retry", "receipts"]


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def slugify(text: str, limit: int = 80) -> str:
    out = []
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", ".", "/"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug or "draft")[:limit].strip("-") or "draft"


def patch_queue_root(root: Path) -> Path:
    return root / ".link" / "patch_drafts"


def agent_queue_root(root: Path) -> Path:
    return root / ".link" / "agent_queue"


def ensure_patch_dirs(root: Path) -> dict[str, str]:
    base = patch_queue_root(root)
    paths: dict[str, str] = {}
    for state in DRAFT_STATES:
        path = base / state
        path.mkdir(parents=True, exist_ok=True)
        paths[state] = str(path)
    return paths


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def queue_counts(root: Path) -> dict[str, int]:
    base = patch_queue_root(root)
    counts: dict[str, int] = {}
    for state in DRAFT_STATES:
        folder = base / state
        counts[state] = len(list(folder.glob("*.json"))) if folder.exists() else 0
    return counts


def latest_pending_agent_task(root: Path) -> tuple[Path | None, dict[str, Any]]:
    pending = agent_queue_root(root) / "pending"
    if not pending.exists():
        return None, {}
    files = sorted(pending.glob("*.json"))
    if not files:
        return None, {}
    path = files[0]
    return path, load_json(path)


def normalize_task(goal: str, task_path: Path | None, task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("task_id") or task.get("id") or "manual").strip() or "manual"
    title = str(task.get("title") or goal or "Manual approval-gated patch draft").strip()
    risk = str(task.get("risk") or "medium").strip()
    priority = task.get("priority", 50)
    command = task.get("command")
    if not command:
        command = f"python3 link_task_receipt.py --goal {shlex.quote('Plan ' + task_id + ' ' + title)} --format markdown"
    return {
        "task_id": task_id,
        "title": title,
        "risk": risk,
        "priority": priority,
        "command": command,
        "source_path": str(task_path) if task_path else None,
    }


def build_approval_patch_draft(
    goal: str = "",
    root: Path | None = None,
    write: bool = False,
    feedback: str = "",
    use_agent_task: bool = True,
) -> dict[str, Any]:
    root = Path(root or Path.cwd())
    paths = ensure_patch_dirs(root) if write else {state: str(patch_queue_root(root) / state) for state in DRAFT_STATES}

    task_path: Path | None = None
    task: dict[str, Any] = {}
    if use_agent_task:
        task_path, task = latest_pending_agent_task(root)

    normalized = normalize_task(goal, task_path, task)
    generated = now()
    draft_id = f"{generated.replace(':', '').replace('-', '').replace('T', '-')}-{slugify(normalized['task_id'] + '-' + normalized['title'])}"

    draft: dict[str, Any] = {
        "version": APPROVAL_PATCH_DRAFT_QUEUE_VERSION,
        "draft_id": draft_id,
        "generated": generated,
        "status": "waiting_approval",
        "approval_required": True,
        "allowed_decisions": ["yes", "no", "try_again"],
        "goal": goal or normalized["title"],
        "task": normalized,
        "risk": normalized["risk"],
        "why": "This draft creates a human approval checkpoint before Link can turn autonomous research/planning into source edits.",
        "proposed_next_step": "Review this draft. Press yes to approve, no to reject, or try_again with feedback.",
        "safe_without_approval": [
            "inspect repo state",
            "read local queue files",
            "write .link runtime receipts",
            "generate draft plans",
        ],
        "requires_approval": [
            "source edits",
            "commits",
            "pushes",
            "destructive shell commands",
            "running unknown external code",
        ],
        "suggested_command": normalized["command"],
        "feedback": feedback,
        "queue_counts": queue_counts(root),
        "paths": paths,
        "written": False,
        "written_path": None,
    }

    if write:
        out = patch_queue_root(root) / "pending" / f"{draft_id}.json"
        write_json(out, draft | {"written": True, "written_path": str(out)})
        receipt = {
            "receipt_version": "approval-patch-draft-created-v1",
            "created": generated,
            "draft_id": draft_id,
            "draft_path": str(out),
            "status": "waiting_approval",
            "task": normalized,
        }
        receipt_path = patch_queue_root(root) / "receipts" / f"{draft_id}-created.json"
        write_json(receipt_path, receipt)
        draft["written"] = True
        draft["written_path"] = str(out)
        draft["receipt_path"] = str(receipt_path)

    return draft


def latest_draft_path(root: Path) -> Path | None:
    pending = patch_queue_root(root) / "pending"
    if not pending.exists():
        return None
    files = sorted(pending.glob("*.json"))
    return files[-1] if files else None


def resolve_draft_path(root: Path, draft_id: str) -> Path | None:
    if draft_id == "latest":
        return latest_draft_path(root)
    pending = patch_queue_root(root) / "pending"
    direct = pending / f"{draft_id}.json"
    if direct.exists():
        return direct
    matches = sorted(pending.glob(f"*{draft_id}*.json"))
    return matches[-1] if matches else None


def decide_approval_patch_draft(
    action: str,
    draft_id: str = "latest",
    feedback: str = "",
    root: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    root = Path(root or Path.cwd())
    ensure_patch_dirs(root)
    action = action.strip().lower()
    if action not in {"yes", "no", "try_again"}:
        raise ValueError("action must be yes, no, or try_again")

    source = resolve_draft_path(root, draft_id)
    if not source:
        result = {
            "version": APPROVAL_PATCH_DRAFT_QUEUE_VERSION,
            "status": "blocked",
            "action": action,
            "ok": False,
            "reason": "No pending draft found.",
            "feedback": feedback,
            "written": False,
        }
        return result

    data = load_json(source)
    target_state = {"yes": "approved", "no": "rejected", "try_again": "retry"}[action]
    decision = {
        "version": APPROVAL_PATCH_DRAFT_QUEUE_VERSION,
        "decided": now(),
        "status": target_state,
        "action": action,
        "ok": True,
        "draft_id": data.get("draft_id") or source.stem,
        "source_path": str(source),
        "target_state": target_state,
        "feedback": feedback,
        "written": False,
        "target_path": None,
    }

    data["status"] = target_state
    data["decision"] = action
    data["decision_feedback"] = feedback
    data["decided"] = decision["decided"]

    if write:
        target = patch_queue_root(root) / target_state / source.name
        write_json(target, data)
        try:
            source.unlink()
        except FileNotFoundError:
            pass
        receipt_path = patch_queue_root(root) / "receipts" / f"{decision['draft_id']}-{target_state}.json"
        write_json(receipt_path, decision | {"written": True, "target_path": str(target), "receipt_path": str(receipt_path)})
        decision["written"] = True
        decision["target_path"] = str(target)
        decision["receipt_path"] = str(receipt_path)

    return decision


def build_status(root: Path | None = None) -> dict[str, Any]:
    root = Path(root or Path.cwd())
    ensure_patch_dirs(root)
    latest = latest_draft_path(root)
    return {
        "version": APPROVAL_PATCH_DRAFT_QUEUE_VERSION,
        "generated": now(),
        "status": "waiting_approval" if latest else "idle",
        "queue_root": str(patch_queue_root(root)),
        "queue_counts": queue_counts(root),
        "latest_pending_draft": str(latest) if latest else None,
        "latest_pending_draft_data": load_json(latest) if latest else {},
    }


def render_markdown(data: dict[str, Any]) -> str:
    if "latest_pending_draft" in data:
        latest = data.get("latest_pending_draft_data") or {}
        task = latest.get("task") or {}
        lines = [
            "# Link Approval-Gated Patch Draft Queue Status",
            "",
            f"Version: `{data.get('version')}`",
            f"Generated: {data.get('generated')}",
            f"Status: **{data.get('status')}**",
            f"Queue root: `{data.get('queue_root')}`",
            "",
            "## Queue Counts",
            "",
        ]
        for key, value in (data.get("queue_counts") or {}).items():
            lines.append(f"- `{key}`: **{value}**")
        lines += [
            "",
            "## Latest Pending Draft",
            "",
            f"- Path: `{data.get('latest_pending_draft')}`",
            f"- Task: `{task.get('task_id')}` — **{task.get('title')}**",
            f"- Risk: **{latest.get('risk')}**",
        ]
        return "\n".join(lines).rstrip() + "\n"

    if "action" in data and "target_state" in data:
        return "\n".join([
            "# Link Approval Decision Receipt",
            "",
            f"Version: `{data.get('version')}`",
            f"Decision: **{data.get('action')}**",
            f"Status: **{data.get('status')}**",
            f"Draft: `{data.get('draft_id')}`",
            f"Feedback: {data.get('feedback') or '(none)'}",
            f"Written: **{bool(data.get('written'))}**",
            f"Target: `{data.get('target_path')}`",
        ]).rstrip() + "\n"

    task = data.get("task") or {}
    lines = [
        "# Link Approval-Gated Patch Draft Queue",
        "",
        f"Version: `{data.get('version')}`",
        f"Draft: `{data.get('draft_id')}`",
        f"Generated: {data.get('generated')}",
        f"Status: **{data.get('status')}**",
        f"Approval required: **{data.get('approval_required')}**",
        "",
        "## Proposal",
        "",
        f"- Task: `{task.get('task_id')}` — **{task.get('title')}**",
        f"- Risk: **{data.get('risk')}**",
        f"- Why: {data.get('why')}",
        f"- Suggested command: `{data.get('suggested_command')}`",
        "",
        "## What Link May Do Without Approval",
        "",
    ]
    for item in data.get("safe_without_approval") or []:
        lines.append(f"- {item}")
    lines += ["", "## Requires Brandon Approval", ""]
    for item in data.get("requires_approval") or []:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Decision Buttons",
        "",
        "- **YES**: approve this exact draft.",
        "- **NO**: reject this draft and store feedback.",
        "- **TRY AGAIN**: rewrite with your feedback.",
        "",
        f"Written: **{bool(data.get('written'))}**",
    ]
    if data.get("written_path"):
        lines.append(f"Written path: `{data.get('written_path')}`")
    return "\n".join(lines).rstrip() + "\n"


def render_html(data: dict[str, Any]) -> str:
    body = html.escape(render_markdown(data))
    return (
        f'<section class="link-approval-patch-draft-queue" '
        f'data-version="{APPROVAL_PATCH_DRAFT_QUEUE_VERSION}">'
        f"<h2>Link Approval-Gated Patch Draft Queue</h2><pre>{body}</pre></section>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and decide approval-gated Link patch drafts.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    create = sub.add_parser("create")
    create.add_argument("--goal", default="")
    create.add_argument("--feedback", default="")
    create.add_argument("--write", action="store_true")
    create.add_argument("--manual", action="store_true", help="Ignore agent queue and create a manual draft.")
    create.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    create.add_argument("--root", default=".")

    decide = sub.add_parser("decide")
    decide.add_argument("--action", choices=["yes", "no", "try_again"], required=True)
    decide.add_argument("--draft-id", default="latest")
    decide.add_argument("--feedback", default="")
    decide.add_argument("--no-write", action="store_true")
    decide.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    decide.add_argument("--root", default=".")

    status = sub.add_parser("status")
    status.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    status.add_argument("--root", default=".")

    args = parser.parse_args()
    # BEGIN LINK STALE APPROVAL GUARD
    if getattr(args, "action", None) in {"yes", "no", "try_again"} and getattr(args, "draft_id", None):
        import datetime as _link_stale_dt
        import json as _link_stale_json
        from pathlib import Path as _link_stale_Path

        _link_root = _link_stale_Path(getattr(args, "root", ".") or ".").resolve()
        _link_pending_dir = _link_root / ".link/patch_drafts/pending"
        _link_receipts_dir = _link_root / ".link/patch_drafts/receipts"
        _link_receipts_dir.mkdir(parents=True, exist_ok=True)

        _link_submitted_draft_id = str(getattr(args, "draft_id", "") or "").strip()
        _link_pending = []
        if _link_pending_dir.exists():
            _link_pending = sorted(
                _link_pending_dir.glob("*.json"),
                key=lambda x: (x.stat().st_mtime, x.name),
                reverse=True,
            )

        _link_current_path = _link_pending[0] if _link_pending else None
        _link_current_draft_id = ""
        _link_current_hash = ""

        if _link_current_path is not None:
            try:
                _link_current_data = _link_stale_json.loads(_link_current_path.read_text(encoding="utf-8"))
                _link_current_draft_id = str(_link_current_data.get("draft_id") or _link_current_path.stem)
                _link_current_hash = str(_link_current_data.get("proposal_hash") or _link_current_data.get("hash") or "")
            except Exception:
                _link_current_draft_id = _link_current_path.stem

        if (not _link_current_draft_id) or (_link_submitted_draft_id != _link_current_draft_id):
            _link_now = _link_stale_dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            _link_receipt = {
                "action": "stale_approval_rejected",
                "status": "stale_rejected",
                "reason": "Rejected stale approval action. Submitted draft_id does not match the current pending draft on disk.",
                "submitted_action": getattr(args, "action", None),
                "submitted_draft_id": _link_submitted_draft_id,
                "current_pending_draft_id": _link_current_draft_id or None,
                "current_pending_path": str(_link_current_path) if _link_current_path else None,
                "current_pending_proposal_hash": _link_current_hash or None,
                "written": True,
                "generated": _link_stale_dt.datetime.now().isoformat(timespec="seconds"),
            }
            _link_receipt_path = _link_receipts_dir / f"{_link_now}-stale-approval-rejected.json"
            _link_receipt["receipt_path"] = str(_link_receipt_path.resolve())
            _link_receipt_path.write_text(_link_stale_json.dumps(_link_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            if str(getattr(args, "format", "") or "").lower() == "markdown":
                print("# Link Approval Decision Receipt")
                print()
                print("Status: **stale_rejected**")
                print("Decision: **blocked**")
                print(f"Submitted action: `{getattr(args, 'action', None)}`")
                print(f"Submitted draft: `{_link_submitted_draft_id}`")
                print(f"Current pending draft: `{_link_current_draft_id or 'None'}`")
                if _link_current_hash:
                    print(f"Current proposal hash: `{_link_current_hash}`")
                print()
                print("Reason: Rejected stale approval action. Reload the dashboard and approve the current visible draft only.")
                print(f"Receipt: `{_link_receipt_path.resolve()}`")
            else:
                print(_link_stale_json.dumps(_link_receipt, indent=2, sort_keys=True))
            raise SystemExit(0)
    # END LINK STALE APPROVAL GUARD
    root = Path(args.root).resolve()

    if args.cmd == "create":
        data = build_approval_patch_draft(
            goal=args.goal,
            root=root,
            write=args.write,
            feedback=args.feedback,
            use_agent_task=not args.manual,
        )
    elif args.cmd == "decide":
        data = decide_approval_patch_draft(
            action=args.action,
            draft_id=args.draft_id,
            feedback=args.feedback,
            root=root,
            write=not args.no_write,
        )
    else:
        data = build_status(root=root)

    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(data))
    else:
        print(render_markdown(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
