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

TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION: Final[str] = "link-transcript-snapshot-receipt-v1"

REQUIRED_TRANSCRIPT_SNAPSHOT_FIELDS: Final[tuple[str, ...]] = (
    "receipt_version",
    "snapshot_id",
    "parent_session_id",
    "source_session_id",
    "copied_at",
    "fork_depth",
    "message_count",
    "transcript_entries",
    "metadata",
)

CONTENT_REPLACEMENT_VERSION: Final[str] = "link-content-replacement-v1"

REQUIRED_CONTENT_REPLACEMENT_FIELDS: Final[tuple[str, ...]] = (
    "replacement_id",
    "session_id",
    "previous_content_hash",
    "replacement_content_hash",
    "created_at",
)


def utc_now() -> str:
    """Return a UTC timestamp suitable for deterministic receipt fields."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "session"


def make_unique_title(
    requested_title: str | None,
    existing_titles: set[str] | None = None,
    *,
    max_attempts: int = 100,
) -> str:
    """Return a unique title not already in ``existing_titles``.

    If ``requested_title`` is ``None`` or empty, a stable timestamp-based
    fallback is generated.  When the requested title collides with an
    existing title the function appends a numeric suffix (``" 2"``,
    ``" 3"``, …) until a free slot is found — up to ``max_attempts``.
    If all attempts are exhausted, a short collision-resistant hash
    suffix is appended instead.

    Titles are compared whitespace-normalised and case-insensitively.
    The returned title preserves the original casing of the request.
    """
    if existing_titles is None:
        existing_titles = set()

    if not requested_title or not str(requested_title).strip():
        import datetime as _dt
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"untitled-upgrade-{ts}"

    requested = str(requested_title).strip()
    key = _normalise_title_key(requested)

    seen = {_normalise_title_key(t) for t in existing_titles}

    if key not in seen:
        return requested

    for attempt in range(2, max_attempts + 1):
        candidate = f"{requested} {attempt}"
        if _normalise_title_key(candidate) not in seen:
            return candidate

    digest = hashlib.sha256(requested.encode("utf-8")).hexdigest()[:8]
    return f"{requested} {digest}"


def _normalise_title_key(title: str) -> str:
    """Produce a whitespace-normalised, lowercase comparison key."""
    return " ".join(title.split()).lower()


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
    content_replacements: list[dict[str, Any]] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a fork lineage receipt without writing runtime state.

    When ``content_replacements`` is provided each entry is validated
    as a ``ContentReplacementEntry`` before inclusion.  Only content
    hashes are stored — raw replacement content is never embedded.
    """
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
    if content_replacements is not None:
        validated: list[dict[str, Any]] = []
        for cr in content_replacements:
            validate_content_replacement_entry(cr)
            validated.append(dict(cr))
        receipt["content_replacements"] = validated
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

    content_replacements = receipt.get("content_replacements")
    if content_replacements is not None:
        if not isinstance(content_replacements, list):
            raise TypeError("content_replacements must be a list")
        for index, cr in enumerate(content_replacements):
            if not isinstance(cr, dict):
                raise TypeError(
                    f"content_replacements entry {index} must be a dict"
                )
            validate_content_replacement_entry(cr)

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


def make_transcript_snapshot_id(
    source_session_id: str,
    transcript_entries: list[dict[str, Any]],
    *,
    parent_session_id: str | None = None,
    fork_depth: int | None = None,
) -> str:
    """Build a stable snapshot id from the source session and normalized messages."""
    source_slug = _slugify(source_session_id)[:48]
    digest_source = _stable_json(
        {
            "fork_depth": 0 if fork_depth is None else fork_depth,
            "parent_session_id": parent_session_id,
            "receipt_version": TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION,
            "source_session_id": source_session_id,
            "transcript_entries": transcript_entries,
        }
    )
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    return f"transcript-snapshot-{source_slug}-{digest}"


def build_transcript_snapshot_receipt(
    *,
    source_session_id: str,
    transcript_entries: list[dict[str, Any]],
    parent_session_id: str | None = None,
    fork_depth: int | None = None,
    metadata: dict[str, Any] | None = None,
    copied_at: str | None = None,
) -> dict[str, Any]:
    """Create a normalized transcript snapshot receipt without writing state."""
    if not isinstance(transcript_entries, list):
        raise TypeError("transcript_entries must be a list")
    normalized_entries = []
    for index, entry in enumerate(transcript_entries):
        if not isinstance(entry, dict):
            raise TypeError(f"transcript entry {index} must be a dict")
        normalized_entries.append(dict(entry))
    normalized_depth = 0 if fork_depth is None else fork_depth
    receipt = {
        "receipt_version": TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION,
        "snapshot_id": make_transcript_snapshot_id(
            source_session_id,
            normalized_entries,
            parent_session_id=parent_session_id,
            fork_depth=normalized_depth,
        ),
        "parent_session_id": parent_session_id,
        "source_session_id": source_session_id,
        "copied_at": copied_at or utc_now(),
        "fork_depth": normalized_depth,
        "message_count": len(normalized_entries),
        "transcript_entries": normalized_entries,
        "metadata": dict(metadata or {}),
    }
    validate_transcript_snapshot_receipt(receipt)
    return receipt


def validate_transcript_snapshot_receipt(receipt: dict[str, Any]) -> None:
    """Validate the stable shape of a transcript snapshot receipt."""
    missing = [field for field in REQUIRED_TRANSCRIPT_SNAPSHOT_FIELDS if field not in receipt]
    if missing:
        raise ValueError(f"transcript snapshot receipt missing fields: {', '.join(missing)}")
    if receipt["receipt_version"] != TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION:
        raise ValueError("unsupported transcript snapshot receipt version")
    for field in ("snapshot_id", "source_session_id", "copied_at"):
        if not isinstance(receipt[field], str) or not receipt[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    parent_session_id = receipt["parent_session_id"]
    if parent_session_id is not None and (
        not isinstance(parent_session_id, str) or not parent_session_id.strip()
    ):
        raise ValueError("parent_session_id must be null or a non-empty string")
    if not isinstance(receipt["fork_depth"], int) or receipt["fork_depth"] < 0:
        raise ValueError("fork_depth must be a non-negative integer")
    if not isinstance(receipt["transcript_entries"], list):
        raise TypeError("transcript_entries must be a list")
    if not isinstance(receipt["message_count"], int):
        raise TypeError("message_count must be an integer")
    if receipt["message_count"] != len(receipt["transcript_entries"]):
        raise ValueError("message_count must match transcript_entries length")
    if not isinstance(receipt["metadata"], dict):
        raise TypeError("metadata must be a dict")

    for index, entry in enumerate(receipt["transcript_entries"]):
        if not isinstance(entry, dict):
            raise TypeError(f"transcript entry {index} must be a dict")
        for field in ("role", "content"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"transcript entry {index} must include non-empty {field}")


def transcript_snapshot_receipt_to_json(receipt: dict[str, Any]) -> str:
    """Serialize a validated transcript snapshot receipt to stable JSON."""
    validate_transcript_snapshot_receipt(receipt)
    return json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"


def transcript_snapshot_receipt_from_json(text: str) -> dict[str, Any]:
    """Deserialize and validate a transcript snapshot receipt."""
    receipt = json.loads(text)
    validate_transcript_snapshot_receipt(receipt)
    return receipt


def make_content_replacement_id(
    session_id: str,
    previous_content_hash: str,
    replacement_content_hash: str,
    *,
    message_index: int | None = None,
) -> str:
    """Build a stable content replacement id.

    Derived from the session, the two content hashes, and an optional
    message index.  Uses SHA-256 for collision resistance with a
    human-readable slug prefix.
    """
    session_slug = _slugify(session_id)[:40]
    digest_source = _stable_json(
        {
            "message_index": message_index,
            "previous_content_hash": previous_content_hash,
            "receipt_version": CONTENT_REPLACEMENT_VERSION,
            "replacement_content_hash": replacement_content_hash,
            "session_id": session_id,
        }
    )
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    return f"content-replacement-{session_slug}-{digest}"


def build_content_replacement_entry(
    *,
    session_id: str,
    previous_content_hash: str,
    replacement_content_hash: str,
    created_at: str | None = None,
    message_index: int | None = None,
    fork_point: dict[str, Any] | None = None,
    reason: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a validated content replacement entry.

    Stores content hashes only — never raw transcript content.  The
    entry is designed to be embedded inside a fork lineage receipt or
    stored independently.
    """
    entry: dict[str, Any] = {
        "replacement_id": make_content_replacement_id(
            session_id,
            previous_content_hash,
            replacement_content_hash,
            message_index=message_index,
        ),
        "session_id": session_id,
        "previous_content_hash": previous_content_hash,
        "replacement_content_hash": replacement_content_hash,
        "created_at": created_at or utc_now(),
    }
    if message_index is not None:
        entry["message_index"] = message_index
    if fork_point is not None and fork_point:
        entry["fork_point"] = dict(fork_point)
    if reason is not None:
        entry["reason"] = reason
    if source is not None:
        entry["source"] = source
    if metadata is not None:
        entry["metadata"] = dict(metadata)
    validate_content_replacement_entry(entry)
    return entry


def validate_content_replacement_entry(entry: dict[str, Any]) -> None:
    """Validate the stable shape of a content replacement entry."""
    missing = [
        field for field in REQUIRED_CONTENT_REPLACEMENT_FIELDS
        if field not in entry
    ]
    if missing:
        raise ValueError(
            f"content replacement entry missing fields: {', '.join(missing)}"
        )

    for field in ("replacement_id", "session_id", "created_at"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ValueError(f"{field} must be a non-empty string")

    for hash_field in ("previous_content_hash", "replacement_content_hash"):
        val = entry[hash_field]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"{hash_field} must be a non-empty string")
        if len(val) != 64 or not _is_hex_string(val):
            raise ValueError(
                f"{hash_field} must be a 64-character hex string (sha-256 hash)"
            )

    if entry["previous_content_hash"] == entry["replacement_content_hash"]:
        raise ValueError(
            "previous_content_hash and replacement_content_hash must differ"
        )

    optional_checks: dict[str, type] = {
        "message_index": int,
        "fork_point": dict,
        "reason": str,
        "source": str,
        "metadata": dict,
    }
    for field, expected_type in optional_checks.items():
        if field in entry and entry[field] is not None:
            if not isinstance(entry[field], expected_type):
                raise TypeError(
                    f"{field} must be {expected_type.__name__} or None, "
                    f"got {type(entry[field]).__name__}"
                )
            if expected_type in (str, int) and isinstance(entry[field], str) and not entry[field].strip():
                raise ValueError(f"{field} must be a non-empty string")


def _is_hex_string(value: str) -> bool:
    """Return True if value consists solely of lowercase hex chars."""
    return all(c in "0123456789abcdef" for c in value)


def content_replacement_entry_to_json(entry: dict[str, Any]) -> str:
    """Serialize a validated content replacement entry to stable JSON."""
    validate_content_replacement_entry(entry)
    return json.dumps(entry, indent=2, sort_keys=True, default=str) + "\n"


def content_replacement_entry_from_json(text: str) -> dict[str, Any]:
    """Deserialize and validate a content replacement entry."""
    entry = json.loads(text)
    validate_content_replacement_entry(entry)
    return entry


__all__ = [
    "CONTENT_REPLACEMENT_VERSION",
    "FORK_LINEAGE_RECEIPT_VERSION",
    "TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION",
    "make_unique_title",
    "build_content_replacement_entry",
    "build_fork_lineage_receipt",
    "build_transcript_snapshot_receipt",
    "content_replacement_entry_from_json",
    "content_replacement_entry_to_json",
    "fork_lineage_receipt_from_json",
    "fork_lineage_receipt_to_json",
    "make_content_replacement_id",
    "make_fork_lineage_receipt_id",
    "make_transcript_snapshot_id",
    "transcript_snapshot_receipt_from_json",
    "transcript_snapshot_receipt_to_json",
    "validate_content_replacement_entry",
    "validate_fork_lineage_receipt",
    "validate_transcript_snapshot_receipt",
]
