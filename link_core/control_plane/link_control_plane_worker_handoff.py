"""Worker handoff packets for Link control-plane patch plans.

This module packages a patch-plan draft for a PatchWorker without executing
patches or mutating source files.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from link_control_plane_patch_plan import load_patch_plan, validate_patch_plan


REQUIRED_WORKER_HANDOFF_FIELDS: Final[tuple[str, ...]] = (
    "handoff_id",
    "plan_id",
    "proposal_id",
    "title",
    "stage",
    "allowed_files",
    "implementation_steps",
    "verification_commands",
    "rollback_plan",
    "risk_level",
    "status",
    "created_at",
)

ALLOWED_WORKER_HANDOFF_STATUSES: Final[set[str]] = {
    "queued",
    "dispatched",
    "completed",
    "failed",
}

ALLOWED_HANDOFF_STAGES: Final[set[str]] = {"PatchWorker"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "worker-handoff"


def make_worker_handoff_id(plan_id: str) -> str:
    digest = hashlib.sha256(plan_id.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(plan_id)}-handoff-{digest}"


def validate_worker_handoff(handoff: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_WORKER_HANDOFF_FIELDS if field not in handoff]
    if missing:
        raise ValueError(f"worker handoff missing required fields: {missing}")

    if handoff["stage"] not in ALLOWED_HANDOFF_STAGES:
        raise ValueError(f"invalid handoff stage: {handoff['stage']}")

    if handoff["status"] not in ALLOWED_WORKER_HANDOFF_STATUSES:
        raise ValueError(f"invalid handoff status: {handoff['status']}")

    for field in ("allowed_files", "implementation_steps", "verification_commands"):
        if not isinstance(handoff[field], list):
            raise TypeError(f"{field} must be a list")

    for field in (
        "handoff_id",
        "plan_id",
        "proposal_id",
        "title",
        "stage",
        "rollback_plan",
        "risk_level",
        "status",
        "created_at",
    ):
        if not isinstance(handoff[field], str) or not handoff[field].strip():
            raise TypeError(f"{field} must be a non-empty string")


def build_worker_handoff_from_plan(
    plan: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_patch_plan(plan)

    if plan.get("status") == "blocked":
        raise ValueError("blocked patch plans cannot be handed to workers")

    handoff = {
        "handoff_id": make_worker_handoff_id(plan["plan_id"]),
        "plan_id": plan["plan_id"],
        "proposal_id": plan["proposal_id"],
        "title": plan["title"],
        "stage": "PatchWorker",
        "allowed_files": list(plan["affected_files"]),
        "implementation_steps": list(plan["implementation_steps"]),
        "verification_commands": list(plan["verification_commands"]),
        "rollback_plan": plan["rollback_plan"],
        "risk_level": plan["risk_level"],
        "status": "queued",
        "created_at": created_at or utc_now(),
    }
    validate_worker_handoff(handoff)
    return handoff


def worker_handoff_to_json(handoff: dict[str, Any]) -> str:
    validate_worker_handoff(handoff)
    return json.dumps(handoff, indent=2, sort_keys=True) + "\n"


def worker_handoff_from_json(text: str) -> dict[str, Any]:
    handoff = json.loads(text)
    validate_worker_handoff(handoff)
    return handoff


def write_worker_handoff(handoff: dict[str, Any], root: str | Path) -> Path:
    validate_worker_handoff(handoff)
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    path = root_path / f"{handoff['handoff_id']}.json"
    path.write_text(worker_handoff_to_json(handoff), encoding="utf-8")
    return path


def load_worker_handoff(path: str | Path) -> dict[str, Any]:
    return worker_handoff_from_json(Path(path).read_text(encoding="utf-8"))


def list_worker_handoffs(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(root_path.glob("*.json"))


def derive_worker_handoff_for_patch_plan(
    plan_path: str | Path,
    handoff_root: str | Path,
    *,
    created_at: str | None = None,
) -> Path:
    plan = load_patch_plan(plan_path)
    handoff = build_worker_handoff_from_plan(plan, created_at=created_at)
    return write_worker_handoff(handoff, handoff_root)
