#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


APPROVAL_CONTRACT_VERSION = "LU110-dashboard-approval-contract-v1"


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


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


def first_value(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
    return default


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        lines = [line.strip(" -\t") for line in value.splitlines()]
        return [line for line in lines if line]
    return [str(value).strip()] if str(value).strip() else []


def short_hash(path: Path, data: dict[str, Any]) -> str:
    try:
        raw = path.read_bytes()
    except Exception:
        raw = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def task_already_done(root: Path, task_id: str) -> bool:
    if not task_id:
        return False
    done = root / ".link" / "agent_queue" / "done"
    if not done.exists():
        return False
    needle = task_id.lower()
    for path in done.glob("*.json"):
        if needle in path.name.lower():
            return True
        data = load_json(path)
        if str(data.get("id") or data.get("task_id") or "").lower() == needle:
            return True
    return False


def latest_pending_draft(root: Path) -> Path | None:
    pending = root / ".link" / "patch_drafts" / "pending"
    files = list_json(pending)
    return files[-1] if files else None


def normalize_draft(root: Path, path: Path | None) -> dict[str, Any]:
    if not path:
        return {
            "present": False,
            "can_approve": False,
            "disable_reason": "No pending approval draft is available.",
        }

    data = load_json(path)
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    proposal = data.get("proposal") if isinstance(data.get("proposal"), dict) else {}
    draft_task = data.get("draft_task") if isinstance(data.get("draft_task"), dict) else {}

    draft_id = first_value(data.get("draft_id"), data.get("id"), path.stem, default=path.stem)
    task_id = first_value(
        data.get("task_id"),
        task.get("id"),
        draft_task.get("id"),
        proposal.get("task_id"),
        default="manual",
    )
    title = first_value(
        data.get("title"),
        data.get("task_title"),
        task.get("title"),
        draft_task.get("title"),
        proposal.get("title"),
        data.get("goal"),
        default="Unknown proposal",
    )
    risk = first_value(data.get("risk"), task.get("risk"), draft_task.get("risk"), proposal.get("risk"), default="unknown")
    why = first_value(data.get("why"), data.get("reason"), proposal.get("why"), data.get("goal"), default="")

    plan = (
        as_list(data.get("proposed_plan"))
        or as_list(data.get("proposed_patch_flow"))
        or as_list(data.get("plan"))
        or as_list(proposal.get("plan"))
        or [
            "Read the visible approval target.",
            "Apply only the smallest useful approved patch.",
            "Run compile, smoke, marker, and healthcheck gates.",
            "Commit and push only after verification passes.",
        ]
    )

    affected = (
        as_list(data.get("affected_files"))
        or as_list(data.get("files"))
        or as_list(data.get("files_to_modify"))
        or as_list(proposal.get("affected_files"))
        or ["Not explicitly listed in draft; treat as unsafe until clarified."]
    )

    checks = (
        as_list(data.get("recommended_checks"))
        or as_list(data.get("checks"))
        or [
            "python3 -m py_compile link_healthcheck.py",
            "python3 link_healthcheck.py",
            "git diff --check",
        ]
    )

    allowed = as_list(data.get("allowed_without_approval")) or [
        "inspect repo state",
        "read queue/draft files",
        "write local .link receipts",
        "generate draft plans",
    ]
    blocked = as_list(data.get("blocked_until_approval")) or [
        "source edits",
        "git add / commit / push",
        "destructive shell commands",
        "running unknown external code",
    ]

    already_done = task_already_done(root, task_id)
    complete = bool(title and title != "Unknown proposal" and why and plan and checks)
    disable_reason = ""
    if already_done:
        disable_reason = f"Draft task {task_id} is already marked done; reconcile stale drafts first."
    elif not complete:
        disable_reason = "Draft is missing title, why, plan, or checks; YES is disabled until it is rewritten."
    elif "unknown" in risk.lower() and "not explicitly listed" in " ".join(affected).lower():
        disable_reason = "Draft does not clearly list risk/files; YES is disabled until proposal is clearer."

    can_approve = not disable_reason

    contract = {
        "version": APPROVAL_CONTRACT_VERSION,
        "present": True,
        "draft_id": draft_id,
        "draft_path": str(path),
        "proposal_hash": short_hash(path, data),
        "status": first_value(data.get("status"), default="waiting_approval"),
        "task_id": task_id,
        "title": title,
        "risk": risk,
        "why": why,
        "plan": plan,
        "affected_files": affected,
        "checks": checks,
        "receipts": as_list(data.get("written_paths")) or as_list(data.get("receipts")),
        "allowed_without_approval": allowed,
        "requires_approval": blocked,
        "task_already_done": already_done,
        "complete": complete,
        "can_approve": can_approve,
        "disable_reason": disable_reason,
        "yes_command": f"python3 link_approval_patch_draft_queue.py decide --action yes --draft-id {draft_id!r} --feedback 'Approved from dashboard.' --format markdown",
        "no_command": f"python3 link_approval_patch_draft_queue.py decide --action no --draft-id {draft_id!r} --feedback 'Rejected from dashboard.' --format markdown",
        "try_again_command": f"python3 link_approval_patch_draft_queue.py decide --action try_again --draft-id {draft_id!r} --feedback 'Try again with Brandon feedback.' --format markdown",
    }
    return contract


def build_approval_contract(root: Path | None = None) -> dict[str, Any]:
    root = root or Path.cwd()
    return normalize_draft(root, latest_pending_draft(root))


def render_markdown(contract: dict[str, Any]) -> str:
    lines = [
        "## Approval Target",
        "",
        f"Contract version: `{APPROVAL_CONTRACT_VERSION}`",
    ]
    if not contract.get("present"):
        lines += ["", f"Status: **not ready**", f"Reason: {contract.get('disable_reason')}"]
        return "\n".join(lines)

    lines += [
        "",
        f"- Draft ID: `{contract.get('draft_id')}`",
        f"- Draft file: `{contract.get('draft_path')}`",
        f"- Proposal hash: `{contract.get('proposal_hash')}`",
        f"- Status: **{contract.get('status')}**",
        f"- Task: `{contract.get('task_id')}` — **{contract.get('title')}**",
        f"- Risk: **{contract.get('risk')}**",
        f"- YES enabled: **{bool(contract.get('can_approve'))}**",
    ]
    if contract.get("disable_reason"):
        lines.append(f"- Disable reason: {contract.get('disable_reason')}")

    lines += ["", "### Why", "", contract.get("why") or "No why provided.", "", "### Proposed Plan"]
    lines += [f"- {item}" for item in contract.get("plan", [])]
    lines += ["", "### Files / Areas Affected"]
    lines += [f"- `{item}`" for item in contract.get("affected_files", [])]
    lines += ["", "### Tests / Checks"]
    lines += [f"- `{item}`" for item in contract.get("checks", [])]
    lines += ["", "### Receipts"]
    receipts = contract.get("receipts") or ["No receipt paths listed in draft."]
    lines += [f"- `{item}`" for item in receipts]
    lines += ["", "### Button Meaning"]
    lines += [
        "- **YES** approves this exact visible draft/hash only.",
        "- **NO** rejects this exact visible draft and stores feedback.",
        "- **TRY AGAIN** moves this exact visible draft to retry with feedback.",
    ]
    lines += ["", "### Exact Commands"]
    lines += [
        f"- YES: `{contract.get('yes_command')}`",
        f"- NO: `{contract.get('no_command')}`",
        f"- TRY AGAIN: `{contract.get('try_again_command')}`",
    ]
    return "\n".join(lines)


def render_html(contract: dict[str, Any]) -> str:
    md = render_markdown(contract)
    button_disabled = "disabled" if not contract.get("can_approve") else ""
    draft_id = contract.get("draft_id") or ""
    reason = contract.get("disable_reason") or ""
    return f"""
<section class="approval-target-card" data-contract-version="{esc(APPROVAL_CONTRACT_VERSION)}" data-draft-id="{esc(draft_id)}" data-proposal-hash="{esc(contract.get('proposal_hash'))}">
  <h2>Approval Target</h2>
  <div class="sync-row">
    <span>Draft: <code>{esc(draft_id or "none")}</code></span>
    <span>Hash: <code>{esc(contract.get("proposal_hash") or "none")}</code></span>
    <span>YES enabled: <strong>{esc(bool(contract.get("can_approve")))}</strong></span>
  </div>
  {f'<p class="danger">YES disabled: {esc(reason)}</p>' if reason else ''}
  <div class="copy-proposal-panel">
    <button type="button" class="copy" onclick="copyApprovalProposal(this)">COPY APPROVAL PROPOSAL</button>
    <span id="copy-approval-status" class="copy-status"></span>
    <textarea id="approval-proposal-copy" class="copy-box" readonly>{esc(md)}</textarea>
  </div>
  <pre>{esc(md)}</pre>
  <script>
  async function copyApprovalProposal(btn) {{
    const box = document.getElementById('approval-proposal-copy');
    const status = document.getElementById('copy-approval-status');
    if (!box) {{ return; }}
    const text = box.value || box.textContent || "";
    let ok = false;
    try {{
      if (navigator.clipboard && window.isSecureContext) {{
        await navigator.clipboard.writeText(text);
        ok = true;
      }}
    }} catch (e) {{
      ok = false;
    }}
    if (!ok) {{
      try {{
        box.style.display = 'block';
        box.focus();
        box.select();
        box.setSelectionRange(0, text.length);
        ok = document.execCommand('copy');
      }} catch (e) {{
        ok = false;
      }}
    }}
    if (status) {{
      status.textContent = ok ? "Copied approval proposal." : "Could not auto-copy. The text box is selected; copy it manually.";
    }}
    if (btn) {{
      const oldText = btn.textContent;
      btn.textContent = ok ? "COPIED" : "SELECTED";
      setTimeout(() => {{ btn.textContent = oldText; if (status) status.textContent = ""; }}, 2500);
    }}
  }}
  </script>
  <form method="post" action="/action" class="button-row">
    <input type="hidden" name="draft_id" value="{esc(draft_id)}">
    <textarea name="feedback" placeholder="Optional feedback for YES / NO / TRY AGAIN"></textarea>
    <button class="yes" name="action" value="yes" {button_disabled}>YES — approve this exact draft</button>
    <button class="no" name="action" value="no">NO — reject this exact draft</button>
    <button class="retry" name="action" value="try_again">TRY AGAIN — rewrite with feedback</button>
  </form>
</section>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    args = parser.parse_args()
    contract = build_approval_contract(Path.cwd())
    if args.format == "json":
        print(json.dumps(contract, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(contract))
    else:
        print(render_markdown(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
