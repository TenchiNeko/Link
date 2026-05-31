"""Receipt helpers for Link artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Final


FORK_LINEAGE_RECEIPT_VERSION: Final[str] = "link-fork-lineage-receipt-v1"

REQUIRED_FORK_LINEAGE_FIELDS: Final[tuple[str, ...]] = (
    "receipt_version",
    "receipt_id",
    "parent_session_id",
    "child_session_id",
    "fork_point",
    "fork_depth",
    "diverged",
    "divergence_status",
    "created_at",
    "source_metadata",
    "parent_trace",
    "child_trace",
)

ALLOWED_DIVERGENCE_STATUSES: Final[set[str]] = {
    "unknown",
    "not_diverged",
    "diverged",
}


def utc_now() -> str:
    """Return a UTC timestamp suitable for deterministic receipt fields."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "session"


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def make_fork_lineage_receipt_id(
    parent_session_id: str,
    child_session_id: str,
    fork_point: dict[str, Any] | None = None,
) -> str:
    """Build a stable receipt id for a parent/child fork relationship."""
    parent_slug = _slugify(parent_session_id)[:40]
    child_slug = _slugify(child_session_id)[:40]
    digest_source = _stable_json(
        {
            "child_session_id": child_session_id,
            "fork_point": fork_point or {},
            "parent_session_id": parent_session_id,
            "receipt_version": FORK_LINEAGE_RECEIPT_VERSION,
        }
    )
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    return f"fork-lineage-{parent_slug}-to-{child_slug}-{digest}"


def build_fork_lineage_receipt(
    *,
    parent_session_id: str,
    child_session_id: str,
    fork_point: dict[str, Any] | None = None,
    fork_depth: int | None = None,
    diverged: bool | None = None,
    divergence_status: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a fork lineage receipt without writing runtime state."""
    normalized_fork_point = dict(fork_point or {})
    normalized_depth = 1 if fork_depth is None else fork_depth
    normalized_diverged = False if diverged is None else diverged
    normalized_status = (
        divergence_status
        if divergence_status is not None
        else ("diverged" if normalized_diverged else "unknown")
    )
    receipt = {
        "receipt_version": FORK_LINEAGE_RECEIPT_VERSION,
        "receipt_id": make_fork_lineage_receipt_id(
            parent_session_id,
            child_session_id,
            normalized_fork_point,
        ),
        "parent_session_id": parent_session_id,
        "child_session_id": child_session_id,
        "fork_point": normalized_fork_point,
        "fork_depth": normalized_depth,
        "diverged": normalized_diverged,
        "divergence_status": normalized_status,
        "created_at": created_at or utc_now(),
        "source_metadata": dict(source_metadata or {}),
        "parent_trace": {
            "session_id": parent_session_id,
            "relation": "parent",
            "child_session_id": child_session_id,
        },
        "child_trace": {
            "session_id": child_session_id,
            "relation": "child",
            "parent_session_id": parent_session_id,
        },
    }
    validate_fork_lineage_receipt(receipt)
    return receipt


def validate_fork_lineage_receipt(receipt: dict[str, Any]) -> None:
    """Validate the stable shape of a fork lineage receipt."""
    missing = [field for field in REQUIRED_FORK_LINEAGE_FIELDS if field not in receipt]
    if missing:
        raise ValueError(f"fork lineage receipt missing fields: {', '.join(missing)}")
    if receipt["receipt_version"] != FORK_LINEAGE_RECEIPT_VERSION:
        raise ValueError("unsupported fork lineage receipt version")
    for field in ("receipt_id", "parent_session_id", "child_session_id", "created_at"):
        if not isinstance(receipt[field], str) or not receipt[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if receipt["parent_session_id"] == receipt["child_session_id"]:
        raise ValueError("parent_session_id and child_session_id must differ")
    if not isinstance(receipt["fork_point"], dict):
        raise TypeError("fork_point must be a dict")
    if not isinstance(receipt["fork_depth"], int) or receipt["fork_depth"] < 0:
        raise ValueError("fork_depth must be a non-negative integer")
    if not isinstance(receipt["diverged"], bool):
        raise TypeError("diverged must be a bool")
    if receipt["divergence_status"] not in ALLOWED_DIVERGENCE_STATUSES:
        raise ValueError("divergence_status must be unknown, not_diverged, or diverged")
    if not isinstance(receipt["source_metadata"], dict):
        raise TypeError("source_metadata must be a dict")

    parent_trace = receipt["parent_trace"]
    child_trace = receipt["child_trace"]
    if not isinstance(parent_trace, dict) or not isinstance(child_trace, dict):
        raise TypeError("parent_trace and child_trace must be dicts")
    if parent_trace.get("session_id") != receipt["parent_session_id"]:
        raise ValueError("parent_trace session_id must match parent_session_id")
    if parent_trace.get("child_session_id") != receipt["child_session_id"]:
        raise ValueError("parent_trace child_session_id must match child_session_id")
    if child_trace.get("session_id") != receipt["child_session_id"]:
        raise ValueError("child_trace session_id must match child_session_id")
    if child_trace.get("parent_session_id") != receipt["parent_session_id"]:
        raise ValueError("child_trace parent_session_id must match parent_session_id")


def fork_lineage_receipt_to_json(receipt: dict[str, Any]) -> str:
    """Serialize a validated fork lineage receipt to stable JSON."""
    validate_fork_lineage_receipt(receipt)
    return json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"


def fork_lineage_receipt_from_json(text: str) -> dict[str, Any]:
    """Deserialize and validate a fork lineage receipt."""
    receipt = json.loads(text)
    validate_fork_lineage_receipt(receipt)
    return receipt


__all__ = [
    "FORK_LINEAGE_RECEIPT_VERSION",
    "build_fork_lineage_receipt",
    "fork_lineage_receipt_from_json",
    "fork_lineage_receipt_to_json",
    "make_fork_lineage_receipt_id",
    "validate_fork_lineage_receipt",
]
