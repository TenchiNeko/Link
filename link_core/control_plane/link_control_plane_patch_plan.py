"""Patch-plan draft builder for Link control-plane proposals.

This module converts accepted proposal artifacts into deterministic patch-plan
drafts. It does not execute patches or mutate source files outside the plan
artifact written by the caller.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from link_control_plane_proposals import load_proposal, validate_proposal


REQUIRED_PATCH_PLAN_FIELDS: Final[tuple[str, ...]] = (
    "plan_id",
    "proposal_id",
    "title",
    "affected_files",
    "implementation_steps",
    "verification_commands",
    "rollback_plan",
    "risk_level",
    "status",
    "created_at",
)

ALLOWED_PATCH_PLAN_STATUSES: Final[set[str]] = {"draft", "ready_for_worker", "blocked"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "patch-plan"


def make_patch_plan_id(proposal_id: str) -> str:
    digest = hashlib.sha256(proposal_id.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(proposal_id)}-plan-{digest}"


def validate_patch_plan(plan: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_PATCH_PLAN_FIELDS if field not in plan]
    if missing:
        raise ValueError(f"patch plan missing required fields: {missing}")

    if plan["status"] not in ALLOWED_PATCH_PLAN_STATUSES:
        raise ValueError(f"invalid patch plan status: {plan['status']}")

    for field in ("affected_files", "implementation_steps", "verification_commands"):
        if not isinstance(plan[field], list):
            raise TypeError(f"{field} must be a list")

    for field in ("plan_id", "proposal_id", "title", "rollback_plan", "risk_level", "created_at"):
        if not isinstance(plan[field], str) or not plan[field].strip():
            raise TypeError(f"{field} must be a non-empty string")


def build_patch_plan_from_proposal(
    proposal: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_proposal(proposal)

    if proposal.get("status") != "accepted":
        raise ValueError("patch plans can only be built from accepted proposals")

    plan = {
        "plan_id": make_patch_plan_id(proposal["proposal_id"]),
        "proposal_id": proposal["proposal_id"],
        "title": proposal["title"],
        "affected_files": list(proposal["affected_files"]),
        "implementation_steps": list(proposal["implementation_plan"]),
        "verification_commands": list(proposal["verification_commands"]),
        "rollback_plan": proposal["rollback_plan"],
        "risk_level": proposal["risk_level"],
        "status": "draft",
        "created_at": created_at or utc_now(),
    }
    validate_patch_plan(plan)
    return plan


def patch_plan_to_json(plan: dict[str, Any]) -> str:
    validate_patch_plan(plan)
    return json.dumps(plan, indent=2, sort_keys=True) + "\n"


def patch_plan_from_json(text: str) -> dict[str, Any]:
    plan = json.loads(text)
    validate_patch_plan(plan)
    return plan


def write_patch_plan(plan: dict[str, Any], root: str | Path) -> Path:
    validate_patch_plan(plan)
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    path = root_path / f"{plan['plan_id']}.json"
    path.write_text(patch_plan_to_json(plan), encoding="utf-8")
    return path


def load_patch_plan(path: str | Path) -> dict[str, Any]:
    return patch_plan_from_json(Path(path).read_text(encoding="utf-8"))


def list_patch_plans(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(root_path.glob("*.json"))


def derive_patch_plan_for_proposal(
    proposal_path: str | Path,
    plan_root: str | Path,
    *,
    created_at: str | None = None,
) -> Path:
    proposal = load_proposal(proposal_path)
    plan = build_patch_plan_from_proposal(proposal, created_at=created_at)
    return write_patch_plan(plan, plan_root)
