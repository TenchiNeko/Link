"""Proposal artifact registry for Link control-plane upgrades."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final


REQUIRED_PROPOSAL_FIELDS: Final[tuple[str, ...]] = (
    "proposal_id",
    "title",
    "source_path",
    "source_summary",
    "extracted_capabilities",
    "link_takeaways",
    "affected_files",
    "risk_level",
    "expected_behavior_change",
    "implementation_plan",
    "verification_commands",
    "rollback_plan",
    "recommendation",
    "status",
    "created_at",
)

ALLOWED_RISK_LEVELS: Final[set[str]] = {"low", "medium", "high"}
ALLOWED_RECOMMENDATIONS: Final[set[str]] = {"accept", "review", "defer", "reject"}
ALLOWED_STATUSES: Final[set[str]] = {
    "pending",
    "accepted",
    "deferred",
    "rejected",
    "converted_to_patch",
    "needs_smaller_plan",
}

LIST_FIELDS: Final[set[str]] = {
    "extracted_capabilities",
    "link_takeaways",
    "affected_files",
    "implementation_plan",
    "verification_commands",
}


def make_proposal_id(title: str, source_path: str) -> str:
    """Create a stable readable proposal id."""
    raw_title = title or "proposal"
    raw_source = source_path or "unknown-source"
    slug = re.sub(r"[^a-z0-9]+", "-", raw_title.lower()).strip("-")[:48]
    if not slug:
        slug = "proposal"
    digest = hashlib.sha256(f"{raw_title}\0{raw_source}".encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def proposal_storage_dir(root: Path | str | None = None) -> Path:
    """Return the proposal registry directory for a repo/root."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    return base / ".agents" / "control_plane" / "proposals"


def validate_proposal(proposal: dict[str, Any]) -> None:
    """Validate a Link control-plane proposal artifact."""
    if not isinstance(proposal, dict):
        raise TypeError("proposal must be a dict")

    missing = [field for field in REQUIRED_PROPOSAL_FIELDS if field not in proposal]
    if missing:
        raise ValueError(f"proposal missing required fields: {', '.join(missing)}")

    for field in REQUIRED_PROPOSAL_FIELDS:
        value = proposal[field]
        if field in LIST_FIELDS:
            if not isinstance(value, list):
                raise TypeError(f"{field} must be a list")
        elif not isinstance(value, str):
            raise TypeError(f"{field} must be a string")

    if not proposal["proposal_id"].strip():
        raise ValueError("proposal_id must not be empty")
    if proposal["risk_level"] not in ALLOWED_RISK_LEVELS:
        raise ValueError(f"invalid risk_level: {proposal['risk_level']}")
    if proposal["recommendation"] not in ALLOWED_RECOMMENDATIONS:
        raise ValueError(f"invalid recommendation: {proposal['recommendation']}")
    if proposal["status"] not in ALLOWED_STATUSES:
        raise ValueError(f"invalid status: {proposal['status']}")


def proposal_to_json(proposal: dict[str, Any]) -> str:
    """Serialize a validated proposal artifact."""
    validate_proposal(proposal)
    return json.dumps(proposal, indent=2, sort_keys=True) + "\n"


def proposal_from_json(text: str) -> dict[str, Any]:
    """Deserialize and validate a proposal artifact."""
    proposal = json.loads(text)
    validate_proposal(proposal)
    return proposal


def write_proposal(proposal: dict[str, Any], root: Path | str | None = None) -> Path:
    """Write a proposal artifact and return its path."""
    validate_proposal(proposal)
    storage = proposal_storage_dir(root)
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / f"{proposal['proposal_id']}.json"
    path.write_text(proposal_to_json(proposal), encoding="utf-8")
    return path


def load_proposal(path: Path | str) -> dict[str, Any]:
    """Load a proposal artifact from disk."""
    return proposal_from_json(Path(path).read_text(encoding="utf-8"))


def list_proposals(root: Path | str | None = None) -> list[dict[str, Any]]:
    """List all proposal artifacts under the registry directory."""
    storage = proposal_storage_dir(root)
    if not storage.exists():
        return []
    return [load_proposal(path) for path in sorted(storage.glob("*.json"))]


def update_proposal_status(
    proposal_id: str,
    status: str,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Update one proposal's approval status."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid status: {status}")

    path = proposal_storage_dir(root) / f"{proposal_id}.json"
    proposal = load_proposal(path)
    proposal["status"] = status
    write_proposal(proposal, root)
    return proposal
