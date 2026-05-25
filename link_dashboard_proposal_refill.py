#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path
from typing import Any


REFILL_VERSION = "LU116-dashboard-recovery-refill-v2"

GENERIC_PATTERNS = [
    "next autonomous growth proposal",
    "safe refill proposal",
    "generic refill",
    "keep the dashboard from going idle",
    "so the loop does not appear stuck",
    "no pending agent task or unused growth candidate",
    "growth/refill proposal",
]

CANDIDATES: list[dict[str, Any]] = [
    {
        "task_id": "LU116",
        "title": "dashboard visible action result banner",
        "risk": "medium",
        "why": "Dashboard button clicks need a visible result banner showing what happened, whether a new draft was generated, and whether the visible approval target changed.",
        "plan": [
            "Show action output at the top of the dashboard after every POST.",
            "Show the refreshed pending draft ID after YES, NO, TRY AGAIN, CLEAR BUGGED, or GENERATE NEW.",
            "Add no-cache headers to every response.",
            "Keep source edits approval-gated.",
        ],
        "files": ["link_self_learning_dashboard_web_admin.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "task_id": "LU117",
        "title": "approval queue stale draft auditor",
        "risk": "medium",
        "why": "Bugged, duplicate, stale, or generic drafts should be moved out of pending before they can keep the web UI stuck.",
        "plan": [
            "Audit pending approval drafts before render.",
            "Move generic or incomplete drafts into a blocked folder.",
            "Write receipts for every moved draft.",
            "Fail healthcheck if a generic LU113-style proposal can remain YES-enabled.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_dashboard_approval_contract.py", "link_healthcheck.py"],
    },
    {
        "task_id": "LU118",
        "title": "concrete growth candidate loader",
        "risk": "medium",
        "why": "When no pending draft exists, Link needs concrete candidate work instead of refill/self-loop proposals.",
        "plan": [
            "Load candidate work from a concrete local catalog.",
            "Require affected files, behavior change, tests, and receipts.",
            "Skip candidates already approved, retried, rejected, blocked, or pending.",
            "Block vague keep-alive proposals.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_autonomous_growth_receipt.py", "link_autonomous_task_queue.py", "link_healthcheck.py"],
    },
    {
        "task_id": "LU119",
        "title": "proposal uniqueness receipt index",
        "risk": "medium",
        "why": "The approval queue should not regenerate the same task idea after it has already been approved, rejected, retried, or blocked.",
        "plan": [
            "Index task IDs and titles across approval folders.",
            "Skip duplicate proposals.",
            "Write a skipped-duplicate receipt.",
            "Show skipped duplicate count in the dashboard.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_dashboard_approval_contract.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "task_id": "LU120",
        "title": "dashboard recovery controls healthcheck",
        "risk": "medium",
        "why": "The dashboard needs healthcheck coverage for CLEAR BUGGED DRAFT and GENERATE NEW DRAFT so these controls do not silently disappear again.",
        "plan": [
            "Add smoke coverage for recovery buttons.",
            "Check that web admin --smoke renders recovery controls.",
            "Check that a no-pending state can generate a concrete draft.",
            "Check that LU113-style drafts are blocked.",
        ],
        "files": ["link_self_learning_dashboard_web_admin.py", "link_dashboard_proposal_refill.py", "link_healthcheck.py"],
    },
]


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def qroot(root: Path) -> Path:
    return root / ".link" / "patch_drafts"


def ensure_dirs(root: Path) -> None:
    for name in ["pending", "approved", "rejected", "retry", "blocked", "receipts"]:
        (qroot(root) / name).mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pending_files(root: Path) -> list[Path]:
    return sorted((qroot(root) / "pending").glob("*.json"))


def get_task_id(data: dict[str, Any]) -> str:
    task = data.get("task")
    if isinstance(task, dict):
        return str(task.get("id") or task.get("task_id") or data.get("task_id") or "").strip()
    return str(data.get("task_id") or data.get("task") or "").strip()


def get_title(data: dict[str, Any]) -> str:
    task = data.get("task")
    if isinstance(task, dict):
        return str(task.get("title") or data.get("title") or "").strip()
    return str(data.get("title") or data.get("name") or "").strip()


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def files_from(data: dict[str, Any]) -> list[Any]:
    return as_list(data.get("files_affected")) or as_list(data.get("affected_files")) or as_list(data.get("files"))


def tests_from(data: dict[str, Any]) -> list[Any]:
    return as_list(data.get("tests_checks")) or as_list(data.get("tests")) or as_list(data.get("checks"))


def is_bugged(data: dict[str, Any]) -> bool:
    blob = json.dumps(data, sort_keys=True, default=str).lower()
    tid = get_task_id(data).upper()
    if tid == "LU113":
        return True
    if any(pattern in blob for pattern in GENERIC_PATTERNS):
        return True
    if "not explicitly listed" in blob:
        return True
    if not get_task_id(data) or not get_title(data):
        return True
    if not files_from(data) or not tests_from(data):
        return True
    return False


def move_to_blocked(root: Path, path: Path, reason: str) -> dict[str, Any]:
    ensure_dirs(root)
    target = qroot(root) / "blocked" / f"{path.stem}-blocked-{stamp()}.json"
    shutil.move(str(path), str(target))

    md = path.with_suffix(".md")
    md_target = None
    if md.exists():
        md_target = qroot(root) / "blocked" / f"{md.stem}-blocked-{stamp()}.md"
        shutil.move(str(md), str(md_target))

    receipt = {
        "receipt_version": REFILL_VERSION,
        "generated": now(),
        "action": "blocked_bugged_pending_draft",
        "reason": reason,
        "source": str(path.resolve()),
        "target": str(target.resolve()),
        "markdown_target": str(md_target.resolve()) if md_target else None,
    }
    rpath = qroot(root) / "receipts" / f"{path.stem}-blocked-{stamp()}.json"
    rpath.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["receipt_path"] = str(rpath.resolve())
    return receipt


def clear_bugged_pending(root: Path) -> list[dict[str, Any]]:
    moved = []
    for path in pending_files(root):
        data = load_json(path)
        if is_bugged(data):
            moved.append(move_to_blocked(root, path, "Generic, incomplete, stale, or self-loop draft."))
    return moved


def used_task_ids(root: Path) -> set[str]:
    used: set[str] = set()
    for folder in ["pending", "approved", "rejected", "retry", "blocked", "receipts"]:
        d = qroot(root) / folder
        if not d.exists():
            continue
        for path in d.glob("*.json"):
            data = load_json(path)
            tid = get_task_id(data)
            if tid:
                used.add(tid.upper())
            for match in re.findall(r"\bLU\d+\b", path.name.upper()):
                used.add(match)
    return used


def tests() -> list[str]:
    return [
        "python3 -m py_compile link_dashboard_proposal_refill.py link_self_learning_dashboard.py link_self_learning_dashboard_web_admin.py link_dashboard_approval_contract.py link_healthcheck.py",
        "python3 link_dashboard_proposal_refill.py --clear-bugged --write --format markdown",
        "python3 link_self_learning_dashboard.py render --format markdown",
        "python3 link_self_learning_dashboard.py render --format html --write",
        "python3 link_self_learning_dashboard_web_admin.py --smoke",
        "python3 link_healthcheck.py",
        "git diff --check",
    ]


def slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-") or "proposal"


def write_candidate(root: Path, c: dict[str, Any], write: bool) -> dict[str, Any]:
    ensure_dirs(root)
    draft_id = f"{stamp()}-manual-{c['task_id'].lower()}-{slug(c['title'])}"
    json_path = qroot(root) / "pending" / f"{draft_id}.json"
    md_path = qroot(root) / "pending" / f"{draft_id}.md"

    data = {
        "receipt_version": "LU107-compatible-approval-draft-v1",
        "generated": now(),
        "draft_id": draft_id,
        "status": "waiting_approval",
        "approval_required": True,
        "task_id": c["task_id"],
        "task": {"id": c["task_id"], "title": c["title"]},
        "title": c["title"],
        "risk": c["risk"],
        "why": c["why"],
        "proposed_plan": c["plan"],
        "files_affected": c["files"],
        "affected_files": c["files"],
        "tests_checks": tests(),
        "tests": tests(),
        "receipts": [
            str(json_path.resolve()),
            str(md_path.resolve()),
            ".link/patch_drafts/receipts/",
            ".link/growth_receipts/",
            ".link/agent_queue/receipts/",
        ],
    }

    md = ["## Approval Target", "", f"- Draft ID: `{draft_id}`", f"- Draft file: `{json_path.resolve()}`", "- Status: **waiting_approval**", f"- Task: `{c['task_id']}` — **{c['title']}**", f"- Risk: **{c['risk']}**", "- YES enabled: **True**", "", "### Why", "", c["why"], "", "### Proposed Plan"]
    md += [f"- {x}" for x in c["plan"]]
    md += ["", "### Files / Areas Affected"]
    md += [f"- `{x}`" for x in c["files"]]
    md += ["", "### Tests / Checks"]
    md += [f"- `{x}`" for x in tests()]
    md += ["", "### Receipts"]
    md += [f"- `{x}`" for x in data["receipts"]]

    if write:
        json_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
        receipt = {
            "receipt_version": REFILL_VERSION,
            "generated": now(),
            "action": "created_concrete_recovery_proposal",
            "draft_id": draft_id,
            "task_id": c["task_id"],
            "title": c["title"],
            "draft_path": str(json_path.resolve()),
        }
        (qroot(root) / "receipts" / f"{draft_id}-created.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "receipt_version": REFILL_VERSION,
        "generated": now(),
        "status": "ok",
        "action": "created",
        "draft_id": draft_id,
        "task_id": c["task_id"],
        "title": c["title"],
        "path": str(json_path.resolve()),
        "reason": "Created concrete recovery proposal.",
    }


def used_lu_numbers(root: Path) -> set[int]:
    numbers: set[int] = set()
    for base in [
        root / ".link/patch_drafts/pending",
        root / ".link/patch_drafts/approved",
        root / ".link/patch_drafts/rejected",
        root / ".link/patch_drafts/retry",
        root / ".link/patch_drafts/blocked",
        root / ".link/patch_drafts/receipts",
        root / ".link/growth_receipts",
        root / ".link/agent_queue/receipts",
    ]:
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in re.finditer(r"\bLU(\d+)\b", text, re.I):
                try:
                    numbers.add(int(m.group(1)))
                except ValueError:
                    pass
    return numbers


def next_unused_lu_id(root: Path, used: set[str]) -> str:
    nums = used_lu_numbers(root)
    n = max(nums or {120}) + 1
    while f"LU{n}".upper() in used:
        n += 1
    return f"LU{n}"


def build_dynamic_concrete_candidate(root: Path, used: set[str]) -> dict[str, Any]:
    task_id = next_unused_lu_id(root, used)
    return {
        "task_id": task_id,
        "title": f"{task_id} dynamic approval proposal source fallback",
        "risk": "medium",
        "why": (
            "The approval refill system exhausted its hardcoded proposal list and started "
            "writing no_useful_proposal_found receipts. It needs a dynamic fallback so the "
            "dashboard can keep producing concrete, non-generic approval drafts without "
            "reusing old task IDs or titles."
        ),
        "proposed_plan": [
            "Add a dynamic proposal source after static recovery candidates are exhausted.",
            "Derive the next LU task ID from existing approval folders and receipts.",
            "Generate a concrete proposal instead of ending permanently at no_useful_proposal_found.",
            "Keep LU113-style generic refill/self-loop proposals blocked.",
            "Write a receipt explaining which dynamic source created the draft.",
            "Add smoke coverage for the exhausted-candidate path.",
        ],
        "files_affected": [
            "link_dashboard_proposal_refill.py",
            "link_self_learning_dashboard.py",
            "link_self_learning_dashboard_web_admin.py",
            "link_healthcheck.py",
        ],
        "tests": [
            "python3 -m py_compile link_dashboard_proposal_refill.py link_self_learning_dashboard.py link_self_learning_dashboard_web_admin.py link_dashboard_approval_contract.py link_healthcheck.py",
            "python3 link_dashboard_proposal_refill.py --clear-bugged --force-new --write --format markdown",
            "python3 link_self_learning_dashboard.py render --format markdown",
            "python3 link_self_learning_dashboard.py render --format html --write",
            "python3 link_self_learning_dashboard_web_admin.py --smoke",
            "python3 link_healthcheck.py",
            "git diff --check",
        ],
        "receipts": [
            ".link/patch_drafts/pending/",
            ".link/patch_drafts/receipts/",
            ".link/growth_receipts/",
            ".link/agent_queue/receipts/",
        ],
    }

def _safe_slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:90] or "proposal"


def _stable_hash(data: dict[str, Any]) -> str:
    import copy
    import hashlib

    payload = copy.deepcopy(data)
    for key in ["proposal_hash", "hash", "generated", "created", "created_at", "updated", "updated_at", "written"]:
        payload.pop(key, None)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _approval_markdown(data: dict[str, Any], draft_path: Path, markdown_path: Path) -> str:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    task_id = data.get("task_id") or task.get("id") or ""
    title = data.get("title") or task.get("title") or ""

    def lines(items: Any) -> list[str]:
        if isinstance(items, list):
            return [str(x) for x in items]
        if items:
            return [str(items)]
        return []

    plan = lines(data.get("proposed_plan"))
    files = lines(data.get("files_affected"))
    tests = lines(data.get("tests") or data.get("checks"))
    receipts = lines(data.get("receipts"))

    out: list[str] = []
    out.append("## Approval Target")
    out.append("")
    out.append("Contract version: `LU110-dashboard-approval-contract-v1`")
    out.append("")
    out.append(f"- Draft ID: `{data.get('draft_id', '')}`")
    out.append(f"- Draft file: `{draft_path}`")
    out.append(f"- Markdown file: `{markdown_path}`")
    out.append(f"- Proposal hash: `{data.get('proposal_hash', '')}`")
    out.append(f"- Status: **{data.get('status', 'waiting_approval')}**")
    out.append(f"- Task: `{task_id}` — **{title}**")
    out.append(f"- Risk: **{data.get('risk', 'medium')}**")
    out.append("- YES enabled: **True**")
    out.append("")
    out.append("### Why")
    out.append("")
    out.append(str(data.get("why") or "Concrete dashboard proposal generated by the recovery refill fallback."))
    out.append("")
    out.append("### Proposed Plan")
    for item in plan:
        out.append(f"- {item}")
    out.append("")
    out.append("### Files / Areas Affected")
    for item in files:
        out.append(f"- `{item}`")
    out.append("")
    out.append("### Tests / Checks")
    for item in tests:
        out.append(f"- `{item}`")
    out.append("")
    out.append("### Receipts")
    for item in receipts:
        out.append(f"- `{item}`")
    out.append("")
    out.append("### Button Meaning")
    out.append("- **YES** approves this exact visible draft/hash only.")
    out.append("- **NO** rejects this exact visible draft and stores feedback.")
    out.append("- **TRY AGAIN** moves this exact visible draft to retry with feedback.")
    out.append("")
    out.append("### Exact Commands")
    out.append(f"- YES: `python3 link_approval_patch_draft_queue.py decide --action yes --draft-id '{data.get('draft_id', '')}' --feedback 'Approved from dashboard.' --format markdown`")
    out.append(f"- NO: `python3 link_approval_patch_draft_queue.py decide --action no --draft-id '{data.get('draft_id', '')}' --feedback 'Rejected from dashboard.' --format markdown`")
    out.append(f"- TRY AGAIN: `python3 link_approval_patch_draft_queue.py decide --action try_again --draft-id '{data.get('draft_id', '')}' --feedback 'Try again with Brandon feedback.' --format markdown`")
    out.append("")
    return "\n".join(out)


def create_concrete(root: Path, c: dict[str, Any], write: bool, moved: list[dict[str, Any]]) -> dict[str, Any]:
    pending_dir = root / ".link/patch_drafts/pending"
    receipts_dir = root / ".link/patch_drafts/receipts"

    task_id = str(c.get("task_id") or "").strip()
    title = str(c.get("title") or "").strip()
    if not task_id or not title:
        return no_useful(root, write, moved)

    generated = now()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    draft_id = f"{stamp}-manual-{task_id.lower()}-{_safe_slug(title)}"
    draft_path = pending_dir / f"{draft_id}.json"
    markdown_path = pending_dir / f"{draft_id}.md"

    data: dict[str, Any] = {
        "receipt_version": REFILL_VERSION,
        "draft_id": draft_id,
        "status": "waiting_approval",
        "generated": generated,
        "task_id": task_id,
        "task": {"id": task_id, "title": title},
        "title": title,
        "risk": c.get("risk", "medium"),
        "why": c.get("why", ""),
        "proposed_plan": c.get("proposed_plan", []),
        "files_affected": c.get("files_affected", []),
        "tests": c.get("tests", []),
        "receipts": c.get("receipts", []),
        "moved_bugged_drafts": moved,
        "proposal_hash": "",
    }
    data["proposal_hash"] = _stable_hash(data)

    markdown = _approval_markdown(data, draft_path.resolve(), markdown_path.resolve())

    rec: dict[str, Any] = {
        "receipt_version": REFILL_VERSION,
        "status": "ok",
        "action": "created_dynamic_concrete_recovery_proposal",
        "generated": generated,
        "draft_id": draft_id,
        "task_id": task_id,
        "title": title,
        "proposal_hash": data["proposal_hash"],
        "draft_path": str(draft_path.resolve()),
        "markdown_path": str(markdown_path.resolve()),
        "moved_bugged_drafts": moved,
    }

    if write:
        pending_dir.mkdir(parents=True, exist_ok=True)
        receipts_dir.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        receipt_path = receipts_dir / f"{draft_id}-created.json"
        rec["receipt_path"] = str(receipt_path.resolve())
        receipt_path.write_text(json.dumps(rec, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    return rec


def no_useful(root: Path, write: bool, moved: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_dirs(root)
    rec = {
        "receipt_version": REFILL_VERSION,
        "generated": now(),
        "status": "blocked",
        "action": "no_useful_proposal_found",
        "reason": "No unused concrete proposal candidate remains. Generic refill/self-loop proposals are blocked.",
        "moved_bugged_drafts": moved,
    }
    path = qroot(root) / "receipts" / f"{stamp()}-no-useful-proposal-found.json"
    rec["receipt_path"] = str(path.resolve())
    if write:
        path.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    return rec


def ensure_pending_approval_draft(root: Path | str = ".", write: bool = True, force_new: bool = False, clear_bugged: bool = True, **_: Any) -> dict[str, Any]:
    root = Path(root).resolve()
    ensure_dirs(root)
    moved = clear_bugged_pending(root) if clear_bugged else []

    pending = pending_files(root)
    if pending and not force_new:
        latest = pending[-1]
        data = load_json(latest)
        return {
            "receipt_version": REFILL_VERSION,
            "generated": now(),
            "status": "ok",
            "action": "already_pending",
            "draft_id": latest.stem,
            "task_id": get_task_id(data),
            "title": get_title(data),
            "path": str(latest.resolve()),
            "moved_bugged_drafts": moved,
            "reason": "Valid pending approval draft already exists.",
        }

    if pending and force_new:
        latest = pending[-1]
        data = load_json(latest)
        if not is_bugged(data):
            return {
                "receipt_version": REFILL_VERSION,
                "generated": now(),
                "status": "ok",
                "action": "already_pending_valid",
                "draft_id": latest.stem,
                "task_id": get_task_id(data),
                "title": get_title(data),
                "path": str(latest.resolve()),
                "moved_bugged_drafts": moved,
                "reason": "Valid pending draft exists; not replacing it.",
            }

    used = used_task_ids(root)
    for c in CANDIDATES:
        if c["task_id"].upper() not in used:
            result = write_candidate(root, c, write)
            result["moved_bugged_drafts"] = moved
            return result

    dynamic_used = used if "used" in locals() else set()

    dynamic_candidate = build_dynamic_concrete_candidate(root, dynamic_used)

    if dynamic_candidate["task_id"].upper() not in dynamic_used:

        return create_concrete(root, dynamic_candidate, write, moved)


    return no_useful(root, write, moved)
def format_markdown(rec: dict[str, Any]) -> str:
    lines = [
        "# Link Dashboard Proposal Refill",
        "",
        f"Version: `{rec.get('receipt_version')}`",
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
    lines += ["", f"Reason: {rec.get('reason', '')}"]
    moved = rec.get("moved_bugged_drafts") or []
    if moved:
        lines += ["", "## Moved Bugged Drafts"]
        lines += [f"- `{m.get('source')}` -> `{m.get('target')}`" for m in moved]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--force-new", action="store_true")
    parser.add_argument("--clear-bugged", action="store_true")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    rec = ensure_pending_approval_draft(args.root, write=args.write, force_new=args.force_new, clear_bugged=True)
    if args.format == "json":
        print(json.dumps(rec, indent=2, sort_keys=True, default=str))
    else:
        print(format_markdown(rec))



# BEGIN LINK NONSELF DYNAMIC FALLBACK
NONSELF_DYNAMIC_IDEAS = [
    {
        "title": "approval queue orphan markdown cleanup",
        "why": "The pending folder can contain orphan .md files with no matching JSON, which makes troubleshooting look like there are pending drafts when the queue is actually empty.",
        "plan": [
            "Scan pending approval markdown files for missing matching JSON files.",
            "Move orphan markdown files to an archived orphan folder with a receipt.",
            "Show orphan cleanup counts in dashboard receipts.",
            "Keep real pending JSON drafts untouched.",
        ],
        "files": [
            "link_dashboard_proposal_refill.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    },
    {
        "title": "approval target single source renderer",
        "why": "The dashboard previously showed different approval text in different boxes. The approval target should be rendered from one canonical source.",
        "plan": [
            "Create one canonical approval markdown builder.",
            "Use the same builder for the copy box, visible approval block, and full dashboard receipt.",
            "Fail healthcheck if visible approval target blocks disagree.",
            "Keep YES disabled if identity fields cannot be synced.",
        ],
        "files": [
            "link_self_learning_dashboard.py",
            "link_self_learning_dashboard_web_admin.py",
            "link_dashboard_approval_contract.py",
            "link_healthcheck.py",
        ],
    },
    {
        "title": "dashboard action result receipt panel",
        "why": "Button actions are hard to verify unless the result is shown directly in the dashboard after each click.",
        "plan": [
            "Persist the latest dashboard action result as a small receipt.",
            "Render the latest action, exit code, and output tail above the approval target.",
            "Add coverage for YES, NO, TRY AGAIN, clear bugged, and generate new draft actions.",
            "Avoid relying only on server logs for button confirmation.",
        ],
        "files": [
            "link_self_learning_dashboard_web_admin.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    },
    {
        "title": "approval decision idempotency guard",
        "why": "Double-clicking or refreshing after a decision should not create confusing duplicate receipts or stale dashboard state.",
        "plan": [
            "Detect already-decided drafts before running a second decision.",
            "Return a clear already-decided receipt instead of failing silently.",
            "Re-render the dashboard from current disk state after every decision.",
            "Add healthcheck coverage for repeat decision behavior.",
        ],
        "files": [
            "link_approval_patch_draft_queue.py",
            "link_self_learning_dashboard_web_admin.py",
            "link_healthcheck.py",
        ],
    },
    {
        "title": "approval proposal hash persistence guard",
        "why": "Proposal hashes should be stable on disk so the dashboard does not need to repair missing or mismatched hash values after render.",
        "plan": [
            "Persist proposal_hash into newly created draft JSON files.",
            "Backfill missing proposal_hash only when a draft is otherwise valid.",
            "Fail healthcheck if YES is enabled with a blank hash.",
            "Keep all visible approval blocks synced to the persisted hash.",
        ],
        "files": [
            "link_dashboard_proposal_refill.py",
            "link_dashboard_approval_contract.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    },
    {
        "title": "approval queue duplicate title blocker",
        "why": "The queue should not keep generating the same proposal with a new LU number after the old one was approved, rejected, retried, or blocked.",
        "plan": [
            "Normalize proposal titles before comparing them across approval folders.",
            "Treat LU-prefixed and non-LU-prefixed versions of the same title as duplicates.",
            "Write skipped-duplicate receipts for transparency.",
            "Add healthcheck coverage using a duplicate dynamic proposal fixture.",
        ],
        "files": [
            "link_dashboard_proposal_refill.py",
            "link_healthcheck.py",
        ],
    },
    {
        "title": "dashboard no-pending recovery explainer",
        "why": "When no pending draft exists, the dashboard should explain whether generation is blocked, exhausted, or waiting for real input.",
        "plan": [
            "Render the latest no-useful-proposal receipt when no draft exists.",
            "Show why generation was blocked or exhausted.",
            "Keep generate-new controls visible.",
            "Add a direct command hint for the next recovery action.",
        ],
        "files": [
            "link_self_learning_dashboard.py",
            "link_self_learning_dashboard_web_admin.py",
            "link_dashboard_proposal_refill.py",
        ],
    },
    {
        "title": "approval refill external candidate loader",
        "why": "Hardcoded proposal lists eventually run out. The refill system should be able to load concrete candidates from a small local candidate file.",
        "plan": [
            "Add an optional .link/approval_candidates.jsonl source.",
            "Validate candidate fields before creating a draft.",
            "Skip candidates already seen in approval history.",
            "Fall back to built-in maintenance ideas only when the candidate file is empty.",
        ],
        "files": [
            "link_dashboard_proposal_refill.py",
            "link_healthcheck.py",
        ],
    },
]


def _nf_norm(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\blu\d+\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _nf_text_from_json(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _nf_used_state(root: Path) -> tuple[set[int], set[str]]:
    numbers: set[int] = set()
    titles: set[str] = set()

    bases = [
        root / ".link/patch_drafts/pending",
        root / ".link/patch_drafts/approved",
        root / ".link/patch_drafts/rejected",
        root / ".link/patch_drafts/retry",
        root / ".link/patch_drafts/blocked",
        root / ".link/patch_drafts/receipts",
        root / ".link/growth_receipts",
        root / ".link/agent_queue/receipts",
    ]

    for base in bases:
        if not base.exists():
            continue
        for path in list(base.glob("*.json")) + list(base.glob("*.md")):
            text = _nf_text_from_json(path)
            for m in re.finditer(r"\bLU(\d+)\b", text, re.I):
                try:
                    numbers.add(int(m.group(1)))
                except ValueError:
                    pass

            try:
                data = json.loads(text)
            except Exception:
                data = {}

            candidates = [
                data.get("title"),
                data.get("task_title"),
                data.get("reason"),
            ]

            task = data.get("task")
            if isinstance(task, dict):
                candidates.append(task.get("title"))
            elif isinstance(task, str):
                candidates.append(task)

            for item in candidates:
                n = _nf_norm(item)
                if n:
                    titles.add(n)

            # Also catch markdown-style task lines.
            for m in re.finditer(r"Task:\s*`?LU\d+`?\s*[—-]\s*\*\*([^*\n]+)\*\*", text):
                n = _nf_norm(m.group(1))
                if n:
                    titles.add(n)

    return numbers, titles


def _nf_next_lu(root: Path) -> str:
    numbers, _ = _nf_used_state(root)
    return f"LU{(max(numbers) if numbers else 120) + 1}"


def _nf_choose_idea(root: Path, task_id: str) -> dict[str, Any]:
    _, used_titles = _nf_used_state(root)

    forbidden = {
        _nf_norm("dynamic approval proposal source fallback"),
        _nf_norm("LU dynamic approval proposal source fallback"),
        _nf_norm("next autonomous growth proposal"),
    }

    for idea in NONSELF_DYNAMIC_IDEAS:
        n = _nf_norm(idea["title"])
        if n in forbidden:
            continue
        if n not in used_titles:
            return dict(idea)

    # Last-resort concrete task, still non-self and unique by LU number.
    return {
        "title": f"approval queue maintenance audit {task_id.lower()}",
        "why": "All built-in dynamic fallback ideas have already been used, so Link needs a concrete maintenance audit proposal instead of looping on the fallback system itself.",
        "plan": [
            "Audit approval queue folders for stale, duplicate, orphan, or malformed records.",
            "Write a receipt summarizing queue health and cleanup recommendations.",
            "Keep generic LU113-style refill proposals blocked.",
            "Add a healthcheck marker for the specific maintenance audit path.",
        ],
        "files": [
            "link_dashboard_proposal_refill.py",
            "link_self_learning_dashboard.py",
            "link_healthcheck.py",
        ],
    }


def _nf_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "dynamic-approval-proposal"


def _nf_stable_hash(data: dict[str, Any]) -> str:
    import hashlib
    payload = dict(data)
    payload.pop("proposal_hash", None)
    payload.pop("hash", None)
    payload.pop("generated", None)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _nf_render_markdown(root: Path, proposal: dict[str, Any]) -> str:
    draft_id = proposal["draft_id"]
    draft_file = root / ".link/patch_drafts/pending" / f"{draft_id}.json"
    md_file = root / ".link/patch_drafts/pending" / f"{draft_id}.md"
    task_id = proposal["task_id"]
    title = proposal["title"]

    lines = [
        "## Approval Target",
        "",
        "Contract version: `LU110-dashboard-approval-contract-v1`",
        "",
        f"- Draft ID: `{draft_id}`",
        f"- Draft file: `{draft_file}`",
        f"- Markdown file: `{md_file}`",
        f"- Proposal hash: `{proposal['proposal_hash']}`",
        "- Status: **waiting_approval**",
        f"- Task: `{task_id}` — **{title}**",
        "- Risk: **medium**",
        "- YES enabled: **True**",
        "",
        "### Why",
        "",
        proposal["why"],
        "",
        "### Proposed Plan",
    ]

    for item in proposal["plan"]:
        lines.append(f"- {item}")

    lines += ["", "### Files / Areas Affected"]
    for item in proposal["files"]:
        lines.append(f"- `{item}`")

    tests = proposal["tests"]
    lines += ["", "### Tests / Checks"]
    for item in tests:
        lines.append(f"- `{item}`")

    lines += [
        "",
        "### Receipts",
        "- `.link/patch_drafts/pending/`",
        "- `.link/patch_drafts/receipts/`",
        "- `.link/growth_receipts/`",
        "- `.link/agent_queue/receipts/`",
        "",
        "### Button Meaning",
        "- **YES** approves this exact visible draft/hash only.",
        "- **NO** rejects this exact visible draft and stores feedback.",
        "- **TRY AGAIN** moves this exact visible draft to retry with feedback.",
        "",
        "### Exact Commands",
        f"- YES: `python3 link_approval_patch_draft_queue.py decide --action yes --draft-id '{draft_id}' --feedback 'Approved from dashboard.' --format markdown`",
        f"- NO: `python3 link_approval_patch_draft_queue.py decide --action no --draft-id '{draft_id}' --feedback 'Rejected from dashboard.' --format markdown`",
        f"- TRY AGAIN: `python3 link_approval_patch_draft_queue.py decide --action try_again --draft-id '{draft_id}' --feedback 'Try again with Brandon feedback.' --format markdown`",
    ]
    return "\n".join(lines) + "\n"


def _nf_move_pending_json(root: Path, reason: str) -> list[dict[str, Any]]:
    pending = root / ".link/patch_drafts/pending"
    retry = root / ".link/patch_drafts/retry"
    retry.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, Any]] = []

    for src in sorted(pending.glob("*.json")) if pending.exists() else []:
        dst = retry / src.name
        shutil.move(str(src), str(dst))
        md = src.with_suffix(".md")
        if md.exists():
            shutil.move(str(md), str(retry / md.name))
        moved.append({"source": str(src), "target": str(dst), "reason": reason})

    return moved


def _nf_archive_orphan_pending_markdown(root: Path) -> int:
    pending = root / ".link/patch_drafts/pending"
    archive = root / ".link/patch_drafts/orphan_markdown"
    archive.mkdir(parents=True, exist_ok=True)
    count = 0

    for md in sorted(pending.glob("*.md")) if pending.exists() else []:
        if not md.with_suffix(".json").exists():
            shutil.move(str(md), str(archive / md.name))
            count += 1
    return count


def _nf_create_dynamic_concrete(root: Path, write: bool, moved: list[dict[str, Any]]) -> dict[str, Any]:
    task_id = _nf_next_lu(root)
    idea = _nf_choose_idea(root, task_id)
    title = idea["title"]

    ts = now().replace("-", "").replace(":", "").replace("T", "-")[:15]
    draft_id = f"{ts}-manual-{task_id.lower()}-{_nf_slug(title)}"

    tests = [
        "python3 -m py_compile link_dashboard_proposal_refill.py link_self_learning_dashboard.py link_self_learning_dashboard_web_admin.py link_dashboard_approval_contract.py link_healthcheck.py",
        "python3 link_dashboard_proposal_refill.py --clear-bugged --force-new --write --format markdown",
        "python3 link_self_learning_dashboard.py render --format markdown",
        "python3 link_self_learning_dashboard.py render --format html --write",
        "python3 link_self_learning_dashboard_web_admin.py --smoke",
        "python3 link_healthcheck.py",
        "git diff --check",
    ]

    proposal: dict[str, Any] = {
        "contract_version": "LU110-dashboard-approval-contract-v1",
        "receipt_version": REFILL_VERSION,
        "draft_id": draft_id,
        "status": "waiting_approval",
        "task_id": task_id,
        "task": {"id": task_id, "title": title},
        "title": title,
        "risk": "medium",
        "why": idea["why"],
        "plan": idea["plan"],
        "proposed_plan": idea["plan"],
        "files": idea["files"],
        "files_affected": idea["files"],
        "tests": tests,
        "checks": tests,
        "yes_enabled": True,
        "generated": now(),
        "source": "nonself_dynamic_fallback",
        "moved_pending_before_create": moved,
    }
    proposal["proposal_hash"] = _nf_stable_hash(proposal)

    draft_dir = root / ".link/patch_drafts/pending"
    receipt_dir = root / ".link/patch_drafts/receipts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    draft_path = draft_dir / f"{draft_id}.json"
    md_path = draft_dir / f"{draft_id}.md"
    receipt_path = receipt_dir / f"{draft_id}-created.json"

    if write:
        draft_path.write_text(json.dumps(proposal, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        md_path.write_text(_nf_render_markdown(root, proposal), encoding="utf-8")
        receipt_path.write_text(json.dumps({
            "receipt_version": REFILL_VERSION,
            "action": "created_nonself_dynamic_proposal",
            "status": "ok",
            "draft_id": draft_id,
            "task_id": task_id,
            "title": title,
            "draft_path": str(draft_path),
            "markdown_path": str(md_path),
            "proposal_hash": proposal["proposal_hash"],
            "moved_pending_before_create": moved,
            "generated": now(),
        }, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    return {
        "receipt_version": REFILL_VERSION,
        "status": "ok",
        "action": "created_nonself_dynamic_proposal",
        "draft_id": draft_id,
        "task_id": task_id,
        "title": title,
        "draft_path": str(draft_path),
        "markdown_path": str(md_path),
        "proposal_hash": proposal["proposal_hash"],
        "reason": "Created a concrete non-self dynamic proposal after static candidates were exhausted.",
        "moved_pending_before_create": moved,
    }


def ensure_pending_approval_draft(
    root: Path | str = ".",
    write: bool = True,
    force_new: bool = False,
    clear_bugged: bool = True,
    **_: Any,
) -> dict[str, Any]:
    root = Path(root).resolve()
    pending = root / ".link/patch_drafts/pending"
    pending.mkdir(parents=True, exist_ok=True)

    _nf_archive_orphan_pending_markdown(root)

    json_pending = sorted(pending.glob("*.json"))

    if json_pending and not force_new:
        latest = json_pending[-1]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return {
            "receipt_version": REFILL_VERSION,
            "status": "ok",
            "action": "already_pending",
            "draft_id": data.get("draft_id") or latest.stem,
            "task_id": get_task_id(data) if "get_task_id" in globals() else data.get("task_id"),
            "title": get_title(data) if "get_title" in globals() else data.get("title"),
            "draft_path": str(latest),
            "proposal_hash": data.get("proposal_hash") or data.get("hash") or "",
            "reason": "Valid pending approval draft already exists.",
        }

    moved: list[dict[str, Any]] = []
    if json_pending and force_new:
        moved = _nf_move_pending_json(root, "force_new requested before creating nonself dynamic proposal")

    return _nf_create_dynamic_concrete(root, write=write, moved=moved)
# END LINK NONSELF DYNAMIC FALLBACK



# BEGIN LINK TITLE DEDUPE HARD FIX

def _link_norm_title(value) -> str:
    """Canonical title used for approval duplicate checks.

    Important: strips LU IDs anywhere in the title, so these all match:
    - LU146 approval queue maintenance audit
    - approval queue maintenance audit lu146
    - approval queue maintenance audit
    """
    text = str(value or "").lower()
    text = re.sub(r"\b\d{8}-\d{6}\b", " ", text)
    text = re.sub(r"\blu\s*[-_ ]*\d+\b", " ", text)
    text = re.sub(r"\blu\d+\b", " ", text)
    text = re.sub(r"\bmanual\b", " ", text)
    text = re.sub(r"\b(created|approved|rejected|retry|blocked|pending)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _link_extract_titles(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in {"title", "task_title", "proposal_title", "name"} and isinstance(value, str):
                yield value
            yield from _link_extract_titles(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _link_extract_titles(item)


def _link_seen_titles(root: Path, include_pending: bool = True) -> set[str]:
    folders = [
        ".link/patch_drafts/approved",
        ".link/patch_drafts/rejected",
        ".link/patch_drafts/retry",
        ".link/patch_drafts/blocked",
        ".link/patch_drafts/receipts",
        ".link/growth_receipts",
        ".link/agent_queue/receipts",
    ]
    if include_pending:
        folders.insert(0, ".link/patch_drafts/pending")

    seen: set[str] = set()
    for rel in folders:
        base = root / rel
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue

            for title in _link_extract_titles(data):
                norm = _link_norm_title(title)
                if norm:
                    seen.add(norm)

            # Filename fallback for older/nonstandard receipts.
            stem = path.stem
            stem = re.sub(r"^\d{8}-\d{6}-", "", stem)
            stem = re.sub(r"-(created|approved|rejected|retry|blocked)$", "", stem)
            norm = _link_norm_title(stem.replace("-", " "))
            if norm:
                seen.add(norm)

    return seen


def _link_used_lu_numbers(root: Path) -> set[int]:
    used: set[int] = set()
    for rel in [
        ".link/patch_drafts/pending",
        ".link/patch_drafts/approved",
        ".link/patch_drafts/rejected",
        ".link/patch_drafts/retry",
        ".link/patch_drafts/blocked",
        ".link/patch_drafts/receipts",
        ".link/growth_receipts",
        ".link/agent_queue/receipts",
    ]:
        base = root / rel
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in re.finditer(r"\bLU(\d+)\b", text, re.I):
                try:
                    used.add(int(m.group(1)))
                except ValueError:
                    pass
    return used


def _link_next_lu(root: Path) -> str:
    used = _link_used_lu_numbers(root)
    return f"LU{(max(used) + 1) if used else 1}"


_LINK_NONSELF_IDEAS = [
    {
        "title": "approval queue orphan markdown cleanup",
        "why": "The pending folder can contain orphan .md files with no matching JSON, which makes troubleshooting look like pending drafts still exist.",
        "plan": [
            "Scan pending approval markdown files for missing matching JSON files.",
            "Move orphan markdown files to an archived orphan folder with a receipt.",
            "Show orphan cleanup counts in dashboard receipts.",
            "Keep real pending JSON drafts untouched.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "title": "approval target single source renderer",
        "why": "The dashboard should never show different approval text in the copy box, visible block, and full receipt.",
        "plan": [
            "Create one canonical approval markdown builder.",
            "Use that builder for every approval target display.",
            "Fail healthcheck if visible approval blocks disagree.",
            "Keep YES disabled if identity fields cannot be synced.",
        ],
        "files": ["link_self_learning_dashboard.py", "link_self_learning_dashboard_web_admin.py", "link_dashboard_approval_contract.py", "link_healthcheck.py"],
    },
    {
        "title": "dashboard action result receipt panel",
        "why": "Button actions are hard to verify unless the result is shown directly in the dashboard after each click.",
        "plan": [
            "Persist the latest dashboard action result as a small receipt.",
            "Render latest action, exit code, and output tail above the approval target.",
            "Cover YES, NO, TRY AGAIN, clear bugged, and generate new actions.",
            "Avoid relying only on server logs for button confirmation.",
        ],
        "files": ["link_self_learning_dashboard_web_admin.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "title": "approval decision idempotency guard",
        "why": "Double-clicking or refreshing after a decision should not create duplicate receipts or stale dashboard state.",
        "plan": [
            "Detect already-decided drafts before running a second decision.",
            "Return a clear already-decided receipt.",
            "Re-render the dashboard from disk after every decision.",
            "Add healthcheck coverage for repeat decision behavior.",
        ],
        "files": ["link_approval_patch_draft_queue.py", "link_self_learning_dashboard_web_admin.py", "link_healthcheck.py"],
    },
    {
        "title": "approval proposal hash persistence guard",
        "why": "Proposal hashes should be stable on disk so the dashboard does not need to repair missing or mismatched hash values after render.",
        "plan": [
            "Persist proposal_hash into newly created draft JSON files.",
            "Backfill missing proposal_hash only when a draft is otherwise valid.",
            "Fail healthcheck if YES is enabled with a blank hash.",
            "Keep all visible approval blocks synced to the persisted hash.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_dashboard_approval_contract.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "title": "approval queue duplicate title blocker",
        "why": "The queue should not keep generating the same proposal with a new LU number after the old one was approved, rejected, retried, or blocked.",
        "plan": [
            "Normalize proposal titles before comparing them across approval folders.",
            "Treat LU-prefixed and LU-suffixed versions of the same title as duplicates.",
            "Write skipped-duplicate receipts for transparency.",
            "Add healthcheck coverage using a duplicate dynamic proposal fixture.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_healthcheck.py"],
    },
    {
        "title": "dashboard no pending recovery explainer",
        "why": "When no pending draft exists, the dashboard should explain whether generation is blocked, exhausted, or waiting for real input.",
        "plan": [
            "Render the latest no-useful-proposal receipt when no draft exists.",
            "Show why generation was blocked or exhausted.",
            "Keep generate-new controls visible.",
            "Add a direct command hint for the next recovery action.",
        ],
        "files": ["link_self_learning_dashboard.py", "link_self_learning_dashboard_web_admin.py", "link_dashboard_proposal_refill.py"],
    },
    {
        "title": "approval refill external candidate loader",
        "why": "Hardcoded proposal lists eventually run out. The refill system should be able to load concrete candidates from a small local candidate file.",
        "plan": [
            "Add an optional .link/approval_candidates.jsonl source.",
            "Validate candidate fields before creating a draft.",
            "Skip candidates already seen in approval history.",
            "Fall back to built-in maintenance ideas only when the candidate file is empty.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_healthcheck.py"],
    },
    {
        "title": "approval queue malformed json quarantine",
        "why": "Malformed pending JSON can make the dashboard look empty or broken even when files are present.",
        "plan": [
            "Detect unreadable JSON drafts in pending.",
            "Move malformed files to blocked with an error receipt.",
            "Keep markdown companions with their JSON record.",
            "Add healthcheck coverage for a malformed pending fixture.",
        ],
        "files": ["link_dashboard_proposal_refill.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "title": "approval queue receipt compactor",
        "why": "Repeated action and no-useful receipts make queue diagnosis noisy and hide the useful recent state.",
        "plan": [
            "Summarize repeated no-useful-proposal receipts into one compact dashboard line.",
            "Keep raw receipts on disk.",
            "Show latest unique action per draft ID.",
            "Add coverage for noisy receipt folders.",
        ],
        "files": ["link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "title": "dashboard approval cache buster",
        "why": "The browser can show stale dashboard HTML after approval actions unless every action returns a fresh identity.",
        "plan": [
            "Add a generated timestamp and cache-control headers to web admin responses.",
            "Ensure action redirects or responses include a fresh query token.",
            "Expose current draft/hash in the action result banner.",
            "Add smoke coverage for stale-cache prevention.",
        ],
        "files": ["link_self_learning_dashboard_web_admin.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
]


def _link_pick_nonself_candidate(root: Path) -> dict | None:
    seen = _link_seen_titles(root, include_pending=True)
    task_id = _link_next_lu(root)

    for idea in _LINK_NONSELF_IDEAS:
        norm = _link_norm_title(idea["title"])
        if not norm or norm in seen:
            continue

        title = idea["title"]  # Do NOT append LU number to title.
        return {
            "task_id": task_id,
            "task": {"id": task_id, "title": title},
            "title": title,
            "risk": "medium",
            "why": idea["why"],
            "plan": idea["plan"],
            "files": idea["files"],
            "tests": [
                "python3 -m py_compile link_dashboard_proposal_refill.py link_self_learning_dashboard.py link_self_learning_dashboard_web_admin.py link_dashboard_approval_contract.py link_healthcheck.py",
                "python3 link_dashboard_proposal_refill.py --clear-bugged --force-new --write --format markdown",
                "python3 link_self_learning_dashboard.py render --format markdown",
                "python3 link_self_learning_dashboard.py render --format html --write",
                "python3 link_self_learning_dashboard_web_admin.py --smoke",
                "python3 link_healthcheck.py",
                "git diff --check",
            ],
            "source": "title_dedupe_hard_fix_nonself_candidate",
        }

    return None


def _link_is_duplicate_or_self_loop_draft(root: Path, draft_path: Path, seen_before: set[str]) -> bool:
    try:
        data = json.loads(draft_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return True

    title = str(data.get("title") or (data.get("task") or {}).get("title") or draft_path.stem)
    norm = _link_norm_title(title)

    if not norm:
        return True

    if norm in seen_before:
        return True

    # Explicitly kill the two bad fallback loops we saw.
    if re.search(r"\bdynamic approval proposal source fallback\b", title, re.I):
        return True

    if re.search(r"\bapproval queue maintenance audit\s+lu\d+\b", title, re.I):
        return True

    return False


def _link_block_pending_draft(root: Path, draft_path: Path, reason: str) -> None:
    blocked = root / ".link/patch_drafts/blocked"
    receipts = root / ".link/patch_drafts/receipts"
    blocked.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)

    target = blocked / draft_path.name
    try:
        shutil.move(str(draft_path), str(target))
    except Exception:
        return

    md = draft_path.with_suffix(".md")
    if md.exists():
        try:
            shutil.move(str(md), str(blocked / md.name))
        except Exception:
            pass

    rec = {
        "receipt_version": "LINK-title-dedupe-hard-fix-v1",
        "action": "blocked_duplicate_or_self_loop_dynamic_draft",
        "status": "blocked",
        "draft_id": draft_path.stem,
        "source_path": str(draft_path),
        "target_path": str(target),
        "reason": reason,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    receipt_path = receipts / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{draft_path.stem}-blocked-duplicate-title.json"
    receipt_path.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")


def _link_create_nonself_candidate(root: Path, write: bool, moved: list[dict] | None = None) -> dict:
    moved = moved or []
    candidate = _link_pick_nonself_candidate(root)
    if not candidate:
        return no_useful(root, write, moved)

    creator = globals().get("create_concrete")
    if callable(creator):
        return creator(root, candidate, write, moved)

    # Fallback only if create_concrete is missing.
    return no_useful(root, write, moved)


_link_original_ensure_pending_approval_draft = ensure_pending_approval_draft


def ensure_pending_approval_draft(root: Path | str = ".", write: bool = True, force_new: bool = False, clear_bugged: bool = True, **kwargs) -> dict:
    root = Path(root)
    seen_before = _link_seen_titles(root, include_pending=False)

    rec = _link_original_ensure_pending_approval_draft(
        root,
        write=write,
        force_new=force_new,
        clear_bugged=clear_bugged,
        **kwargs,
    )

    pending_dir = root / ".link/patch_drafts/pending"
    pending_json = sorted(pending_dir.glob("*.json")) if pending_dir.exists() else []

    # If the old generator produced a duplicate with only the LU number changed,
    # quarantine it and immediately create the next non-self concrete candidate.
    if pending_json:
        latest = pending_json[-1]
        if _link_is_duplicate_or_self_loop_draft(root, latest, seen_before):
            _link_block_pending_draft(
                root,
                latest,
                "Generated draft was duplicate/self-loop after title normalization.",
            )
            return _link_create_nonself_candidate(root, write=write, moved=rec.get("moved_bugged_drafts", []))

    # If the old generator says exhausted/no useful, try the non-self candidate pool.
    if str(rec.get("action", "")).lower() == "no_useful_proposal_found":
        return _link_create_nonself_candidate(root, write=write, moved=rec.get("moved_bugged_drafts", []))

    return rec

# END LINK TITLE DEDUPE HARD FIX


if __name__ == "__main__":
    main()
