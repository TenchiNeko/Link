"""Finalizer receipts for Link control-plane verifier outcomes.

This module records final control-plane outcomes after verification. It does not
execute patches, run verification, or mutate source files.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from link_control_plane_verifier_receipt import load_verifier_receipt, validate_verifier_receipt


REQUIRED_FINALIZER_RECEIPT_FIELDS: Final[tuple[str, ...]] = (
    "finalization_id",
    "verification_id",
    "handoff_id",
    "plan_id",
    "proposal_id",
    "title",
    "stage",
    "status",
    "final_summary",
    "evidence_paths",
    "findings",
    "next_recommendation",
    "created_at",
)

ALLOWED_FINALIZER_STATUSES: Final[set[str]] = {"finalized", "failed", "blocked"}
ALLOWED_FINALIZER_STAGES: Final[set[str]] = {"Finalizer"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "finalizer"


def make_finalization_id(verification_id: str) -> str:
    digest = hashlib.sha256(verification_id.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(verification_id)}-final-{digest}"


def validate_finalizer_receipt(receipt: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FINALIZER_RECEIPT_FIELDS if field not in receipt]
    if missing:
        raise ValueError(f"finalizer receipt missing required fields: {missing}")

    if receipt["stage"] not in ALLOWED_FINALIZER_STAGES:
        raise ValueError(f"invalid finalizer stage: {receipt['stage']}")

    if receipt["status"] not in ALLOWED_FINALIZER_STATUSES:
        raise ValueError(f"invalid finalizer status: {receipt['status']}")

    for field in ("evidence_paths", "findings"):
        if not isinstance(receipt[field], list):
            raise TypeError(f"{field} must be a list")
        if not all(isinstance(item, str) and item.strip() for item in receipt[field]):
            raise TypeError(f"{field} must contain non-empty strings")

    for field in (
        "finalization_id",
        "verification_id",
        "handoff_id",
        "plan_id",
        "proposal_id",
        "title",
        "stage",
        "status",
        "final_summary",
        "next_recommendation",
        "created_at",
    ):
        if not isinstance(receipt[field], str) or not receipt[field].strip():
            raise TypeError(f"{field} must be a non-empty string")


def build_finalizer_receipt_from_verifier(
    verifier_receipt: dict[str, Any],
    *,
    status: str = "finalized",
    final_summary: str = "verification completed and finalizer receipt recorded",
    next_recommendation: str = "archive_and_report",
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_verifier_receipt(verifier_receipt)

    receipt = {
        "finalization_id": make_finalization_id(verifier_receipt["verification_id"]),
        "verification_id": verifier_receipt["verification_id"],
        "handoff_id": verifier_receipt["handoff_id"],
        "plan_id": verifier_receipt["plan_id"],
        "proposal_id": verifier_receipt["proposal_id"],
        "title": verifier_receipt["title"],
        "stage": "Finalizer",
        "status": status,
        "final_summary": final_summary,
        "evidence_paths": list(verifier_receipt["evidence_paths"]),
        "findings": list(verifier_receipt["findings"]),
        "next_recommendation": next_recommendation,
        "created_at": created_at or utc_now(),
    }
    validate_finalizer_receipt(receipt)
    return receipt


def finalizer_receipt_to_json(receipt: dict[str, Any]) -> str:
    validate_finalizer_receipt(receipt)
    return json.dumps(receipt, indent=2, sort_keys=True) + "\n"


def finalizer_receipt_from_json(text: str) -> dict[str, Any]:
    receipt = json.loads(text)
    validate_finalizer_receipt(receipt)
    return receipt


def write_finalizer_receipt(receipt: dict[str, Any], root: str | Path) -> Path:
    validate_finalizer_receipt(receipt)
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    path = root_path / f"{receipt['finalization_id']}.json"
    path.write_text(finalizer_receipt_to_json(receipt), encoding="utf-8")
    return path


def load_finalizer_receipt(path: str | Path) -> dict[str, Any]:
    return finalizer_receipt_from_json(Path(path).read_text(encoding="utf-8"))


def list_finalizer_receipts(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(root_path.glob("*.json"))


def derive_finalizer_receipt_for_verifier(
    verifier_receipt_path: str | Path,
    finalizer_root: str | Path,
    *,
    status: str = "finalized",
    final_summary: str = "verification completed and finalizer receipt recorded",
    next_recommendation: str = "archive_and_report",
    created_at: str | None = None,
) -> Path:
    verifier_receipt = load_verifier_receipt(verifier_receipt_path)
    finalizer_receipt = build_finalizer_receipt_from_verifier(
        verifier_receipt,
        status=status,
        final_summary=final_summary,
        next_recommendation=next_recommendation,
        created_at=created_at,
    )
    return write_finalizer_receipt(finalizer_receipt, finalizer_root)
