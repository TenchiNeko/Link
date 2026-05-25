#!/usr/bin/env python3
from __future__ import annotations

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


if __name__ == "__main__":
    main()
