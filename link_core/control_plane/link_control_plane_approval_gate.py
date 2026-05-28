"""Approval gate for Link control-plane proposals.

This module records human approval decisions without executing patches.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from link_control_plane_proposals import (
    load_proposal,
    update_proposal_status,
    validate_proposal,
)


APPROVAL_DECISIONS: Final[tuple[str, ...]] = (
    "accept",
    "reject",
    "defer",
    "request_smaller_plan",
)

DECISION_TO_STATUS: Final[dict[str, str]] = {
    "accept": "accepted",
    "reject": "rejected",
    "defer": "deferred",
    "request_smaller_plan": "needs_smaller_plan",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_decision(decision: str) -> bool:
    return decision in APPROVAL_DECISIONS


def proposal_status_for_decision(decision: str) -> str:
    if decision not in DECISION_TO_STATUS:
        raise ValueError(f"unknown approval decision: {decision}")
    return DECISION_TO_STATUS[decision]


def build_approval_receipt(
    proposal_id: str,
    decision: str,
    reviewer: str = "Brandon",
    note: str = "",
) -> dict[str, Any]:
    if not validate_decision(decision):
        raise ValueError(f"unknown approval decision: {decision}")

    return {
        "schema": "link_control_plane_approval_receipt_v1",
        "proposal_id": proposal_id,
        "decision": decision,
        "status": proposal_status_for_decision(decision),
        "reviewer": reviewer,
        "note": note,
        "created_at": utc_now(),
    }


def approval_receipt_path(root: str | Path, proposal_id: str) -> Path:
    safe_id = proposal_id.replace("/", "_").replace("..", "_")
    return Path(root) / f"{safe_id}.approval.json"


def write_approval_receipt(receipt: dict[str, Any], root: str | Path) -> Path:
    required = {"schema", "proposal_id", "decision", "status", "reviewer", "created_at"}
    missing = required - set(receipt)
    if missing:
        raise ValueError(f"approval receipt missing fields: {sorted(missing)}")

    path = approval_receipt_path(root, str(receipt["proposal_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def apply_approval_decision(
    proposal_id: str,
    decision: str,
    proposal_root: str | Path,
    receipt_root: str | Path,
    reviewer: str = "Brandon",
    note: str = "",
) -> dict[str, Any]:
    proposal_path = Path(proposal_root) / f"{proposal_id}.json"
    if not proposal_path.exists():
        matches = sorted(Path(proposal_root).rglob(f"{proposal_id}.json"))
        if matches:
            proposal_path = matches[0]
    proposal = load_proposal(proposal_path)
    validate_proposal(proposal)

    new_status = proposal_status_for_decision(decision)
    updated = update_proposal_status(proposal_id, new_status, proposal_root)
    validate_proposal(updated)

    receipt = build_approval_receipt(
        proposal_id=proposal_id,
        decision=decision,
        reviewer=reviewer,
        note=note,
    )
    write_approval_receipt(receipt, receipt_root)

    return {
        "proposal": updated,
        "receipt": receipt,
    }
