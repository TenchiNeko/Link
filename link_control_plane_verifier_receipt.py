"""Verifier receipts for Link control-plane worker handoffs.

This module records verification outcomes for PatchWorker handoffs. It does not
execute verification commands or mutate source files.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from link_control_plane_worker_handoff import load_worker_handoff, validate_worker_handoff


REQUIRED_VERIFIER_RECEIPT_FIELDS: Final[tuple[str, ...]] = (
    "verification_id",
    "handoff_id",
    "plan_id",
    "proposal_id",
    "title",
    "stage",
    "status",
    "verification_commands",
    "evidence_paths",
    "findings",
    "created_at",
)

ALLOWED_VERIFIER_STATUSES: Final[set[str]] = {"pending", "passed", "failed", "blocked"}
ALLOWED_VERIFIER_STAGES: Final[set[str]] = {"Verifier"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "verification"


def make_verification_id(handoff_id: str) -> str:
    digest = hashlib.sha256(handoff_id.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(handoff_id)}-verify-{digest}"


def validate_verifier_receipt(receipt: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_VERIFIER_RECEIPT_FIELDS if field not in receipt]
    if missing:
        raise ValueError(f"verifier receipt missing required fields: {missing}")

    if receipt["stage"] not in ALLOWED_VERIFIER_STAGES:
        raise ValueError(f"invalid verifier stage: {receipt['stage']}")

    if receipt["status"] not in ALLOWED_VERIFIER_STATUSES:
        raise ValueError(f"invalid verifier status: {receipt['status']}")

    for field in ("verification_commands", "evidence_paths", "findings"):
        if not isinstance(receipt[field], list):
            raise TypeError(f"{field} must be a list")
        if not all(isinstance(item, str) and item.strip() for item in receipt[field]):
            raise TypeError(f"{field} must contain non-empty strings")

    for field in (
        "verification_id",
        "handoff_id",
        "plan_id",
        "proposal_id",
        "title",
        "stage",
        "status",
        "created_at",
    ):
        if not isinstance(receipt[field], str) or not receipt[field].strip():
            raise TypeError(f"{field} must be a non-empty string")


def build_verifier_receipt_from_handoff(
    handoff: dict[str, Any],
    *,
    status: str = "pending",
    evidence_paths: list[str] | None = None,
    findings: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_worker_handoff(handoff)

    receipt = {
        "verification_id": make_verification_id(handoff["handoff_id"]),
        "handoff_id": handoff["handoff_id"],
        "plan_id": handoff["plan_id"],
        "proposal_id": handoff["proposal_id"],
        "title": handoff["title"],
        "stage": "Verifier",
        "status": status,
        "verification_commands": list(handoff["verification_commands"]),
        "evidence_paths": list(evidence_paths or []),
        "findings": list(findings or ["verification receipt created"]),
        "created_at": created_at or utc_now(),
    }
    validate_verifier_receipt(receipt)
    return receipt


def verifier_receipt_to_json(receipt: dict[str, Any]) -> str:
    validate_verifier_receipt(receipt)
    return json.dumps(receipt, indent=2, sort_keys=True) + "\n"


def verifier_receipt_from_json(text: str) -> dict[str, Any]:
    receipt = json.loads(text)
    validate_verifier_receipt(receipt)
    return receipt


def write_verifier_receipt(receipt: dict[str, Any], root: str | Path) -> Path:
    validate_verifier_receipt(receipt)
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    path = root_path / f"{receipt['verification_id']}.json"
    path.write_text(verifier_receipt_to_json(receipt), encoding="utf-8")
    return path


def load_verifier_receipt(path: str | Path) -> dict[str, Any]:
    return verifier_receipt_from_json(Path(path).read_text(encoding="utf-8"))


def list_verifier_receipts(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(root_path.glob("*.json"))


def derive_verifier_receipt_for_handoff(
    handoff_path: str | Path,
    receipt_root: str | Path,
    *,
    status: str = "pending",
    evidence_paths: list[str] | None = None,
    findings: list[str] | None = None,
    created_at: str | None = None,
) -> Path:
    handoff = load_worker_handoff(handoff_path)
    receipt = build_verifier_receipt_from_handoff(
        handoff,
        status=status,
        evidence_paths=evidence_paths,
        findings=findings,
        created_at=created_at,
    )
    return write_verifier_receipt(receipt, receipt_root)
