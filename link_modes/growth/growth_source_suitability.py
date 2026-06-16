"""Growth source suitability and quarantine helpers.

Extracted from ``link_growth_console.py`` as a focused source subsystem.
This module owns source suitability, quarantine, and source queue policy
payloads. It must not import the Growth monolith, call model providers, use
network access, mutate research archives, or perform CLI dispatch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

SOURCE_ARCHIVE_SUITABILITY_ASSESSMENT_VERSION = "link-source-archive-suitability-assessment-v1"
SOURCE_QUEUE_QUARANTINE_RECORD_VERSION = "link-source-queue-quarantine-record-v1"
GROWTH_SOURCE_QUEUE_POLICY_VERSION = "link-growth-source-queue-policy-v1"
PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES = 1500000

GROWTH_SOURCE_QUEUE_REQUIRED = (
    "research/headroom-main.zip",
    "research/gpt-crawler-main.zip",
    "research/Agent-Reach-main.zip",
)
GROWTH_SOURCE_QUEUE_OPTIONAL = (
    "research/activepieces-main.zip",
    "research/Flowise-main.zip",
    "research/agentmemory-main.zip",
    "research/AiToEarn-main.zip",
)


def _stable_json(value: Any, indent: int | None = None) -> str:
    kwargs: dict[str, Any] = {"sort_keys": True, "default": str}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return json.dumps(value, **kwargs)


def _hash_text(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _normalize_refs(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list):
        raw_values = values
    else:
        raise TypeError("implementation branch refs must be a string or list")
    normalized: list[str] = []
    for raw in raw_values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError("implementation branch refs cannot contain empty strings")
        if "\x00" in value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid implementation branch ref: {value}")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)


def _read_only_safety_metadata() -> dict[str, Any]:
    return {
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "writes": [],
    }


def _source_text(value: Any, *, fallback: str = "not available", max_chars: int = 180) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def source_type(path_text: str) -> str:
    path = Path(path_text)
    if path.is_dir():
        return "folder"
    if path.suffix.lower() == ".zip":
        return "zip_archive"
    return "file"


def guess_concept_family(source_path: str) -> str:
    name = source_path.lower()
    if "headroom" in name:
        return "compression"
    if "crawler" in name or "scrap" in name:
        return "source_collection"
    if "reach" in name:
        return "outreach"
    if "flowise" in name or "activepieces" in name:
        return "workflow_automation"
    if "memory" in name:
        return "agent_memory"
    return "unknown"


def queue_source_entry(source_path: str, *, priority: int, reason_selected: str) -> dict[str, Any]:
    path = Path(source_path)
    exists = path.exists()
    warnings: list[str] = []
    if not source_path.startswith("research/"):
        warnings.append("source is outside research/")
    if not exists:
        warnings.append("source is missing")
    return {
        "source_path": source_path,
        "source_exists": exists,
        "source_name": path.name,
        "source_type": source_type(source_path) if exists else "missing",
        "source_size_bytes": int(path.stat().st_size) if exists else 0,
        "source_mtime_ns": int(path.stat().st_mtime_ns) if exists else 0,
        "guessed_concept_family": guess_concept_family(source_path),
        "priority": int(priority),
        "reason_selected": reason_selected,
        "warnings": _normalize_refs(warnings),
    }


def classify_source_archive_failure(
    *,
    source_path: str,
    error_text: str = "",
    source_exists: bool | None = None,
    source_size_bytes: int | None = None,
) -> dict[str, Any]:
    text = str(error_text or "").lower()
    path_text = str(source_path or "")
    category = "unknown"
    likely_cause = "The source failed a deterministic suitability check."
    recommended_fix = "Inspect the source-specific deterministic intake failure before retrying queue warmup."
    safe_to_retry: bool | str = "unknown"
    include_default = False
    if source_exists is False:
        category = "source_missing"
        likely_cause = "The requested source path does not exist under the local research directory."
        recommended_fix = "Verify the source path or remove it from the queue."
        safe_to_retry = False
    elif source_size_bytes is not None and int(source_size_bytes) > PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES * 100:
        category = "oversized_archive"
        likely_cause = "The archive is large enough to be expensive for source inventory warmup."
        recommended_fix = "Add a focused inventory adapter or smaller fixture before enabling it in the default queue."
        safe_to_retry = False
    elif "forbidden path segment" in text or "activepieces-main.zip" in path_text:
        category = "source_ref_generation_error"
        likely_cause = "Deterministic source-ref generation currently emits or encounters a forbidden path segment for this archive shape."
        recommended_fix = "Add a source-ref sanitizer or archive-shape adapter, then rerun suitability before default queue inclusion."
        safe_to_retry = False
    elif "provenance" in text and ("schema" in text or "ref" in text):
        category = "provenance_ref_schema_error"
        likely_cause = "Source provenance refs did not satisfy Link's deterministic provenance schema."
        recommended_fix = "Normalize provenance refs before persistent cache payload validation."
        safe_to_retry = False
    elif "timeout" in text:
        category = "archive_inventory_timeout"
        likely_cause = "Archive inventory exceeded the bounded deterministic runtime expectation."
        recommended_fix = "Add a cheaper manifest-only adapter or exclude the source from default queue warming."
        safe_to_retry = "unknown"
    elif "payload" in text and "validation" in text:
        category = "cache_payload_validation_failed"
        likely_cause = "The compact persistent cache payload failed validation."
        recommended_fix = "Inspect the validation failure and normalize the compact payload before retrying."
        safe_to_retry = False
    elif "nested" in text or "vendor" in text:
        category = "nested_archive_or_vendor_tree"
        likely_cause = "The archive appears to contain nested or vendor-heavy content unsuitable for default warmup."
        recommended_fix = "Add targeted source selection rules before queue inclusion."
        safe_to_retry = False
    operator_summary = {
        "source_missing": "source path is missing",
        "oversized_archive": "archive is too large for default queue warmup",
        "source_ref_generation_error": "source-ref generation fails deterministic safety checks",
        "provenance_ref_schema_error": "provenance refs fail deterministic schema checks",
        "archive_inventory_timeout": "archive inventory appears too slow for default queue warmup",
        "cache_payload_validation_failed": "persistent cache payload validation failed",
        "nested_archive_or_vendor_tree": "archive shape needs a targeted adapter",
        "unknown": "deterministic source failure is not classified yet",
    }[category]
    return {
        "category": category,
        "operator_summary": operator_summary,
        "likely_cause": likely_cause,
        "recommended_fix": recommended_fix,
        "safe_to_retry": safe_to_retry,
        "include_in_default_queue": include_default if category != "unknown" else False,
    }


def summarize_source_archive_failure_for_operator(classification: Mapping[str, Any]) -> str:
    return _source_text(
        f"{classification.get('operator_summary', 'source failure')}: {classification.get('likely_cause', '')}",
        max_chars=220,
    )


def collect_growth_source_queue_policy(*, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "growth_source_queue_policy_version": GROWTH_SOURCE_QUEUE_POLICY_VERSION,
        "growth_source_queue_policy_id": "growth-source-queue-policy-" + _hash_text({"required": GROWTH_SOURCE_QUEUE_REQUIRED, "optional": GROWTH_SOURCE_QUEUE_OPTIONAL, "version": GROWTH_SOURCE_QUEUE_POLICY_VERSION})[:12],
        "required_sources": list(GROWTH_SOURCE_QUEUE_REQUIRED),
        "optional_sources": list(GROWTH_SOURCE_QUEUE_OPTIONAL),
        "default_queue_requires_suitability": True,
        "optional_source_failure_policy": "skip_with_reason",
        "required_source_failure_policy": "fail_closed_with_reason",
        "persistent_cache_required_for_queue_ready": False,
        "quarantine_enabled": True,
        "explicit_include_allowed": True,
        "explicit_include_warning_required": True,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_growth_source_queue_policy(payload)
    return payload


def validate_growth_source_queue_policy(payload: Mapping[str, Any]) -> None:
    required = ("growth_source_queue_policy_version", "growth_source_queue_policy_id", "required_sources", "optional_sources", "default_queue_requires_suitability", "optional_source_failure_policy", "required_source_failure_policy", "persistent_cache_required_for_queue_ready", "quarantine_enabled", "explicit_include_allowed", "explicit_include_warning_required", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"growth source queue policy missing field: {key}")
    if payload["growth_source_queue_policy_version"] != GROWTH_SOURCE_QUEUE_POLICY_VERSION:
        raise ValueError("invalid growth source queue policy version")
    if payload["optional_source_failure_policy"] != "skip_with_reason":
        raise ValueError("optional source failure policy must be skip_with_reason")
    if payload["required_source_failure_policy"] != "fail_closed_with_reason":
        raise ValueError("required source failure policy must be fail_closed_with_reason")
    if "research/activepieces-main.zip" not in payload["optional_sources"]:
        raise ValueError("activepieces must be optional by default")
    if payload["default_queue_requires_suitability"] is not True or payload["quarantine_enabled"] is not True:
        raise ValueError("growth source queue policy must require suitability and quarantine")
    if payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth source queue policy must avoid model/network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("growth source queue policy must remain read-only")


def stable_growth_source_queue_policy_json(payload: dict[str, Any]) -> str:
    validate_growth_source_queue_policy(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_source_queue_policy_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_source_queue_policy(payload)
    return payload


def collect_source_archive_suitability_assessment(
    *,
    source_path: str,
    metadata: dict[str, Any] | None = None,
    collect_cache_key: Callable[..., dict[str, Any]],
    collect_manifest: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    entry = queue_source_entry(str(source_path or ""), priority=1, reason_selected="suitability assessment")
    cache_key_id = ""
    manifest_id = ""
    status = "failed"
    queue_eligible = False
    persistent_eligible = False
    e2e_eligible = False
    default_eligible = False
    failure_category = ""
    failure_summary = ""
    blocked: list[str] = []
    warnings: list[str] = []
    safe_to_retry: bool | str = True
    retry_cost = "low"
    if not entry["source_exists"]:
        classification = classify_source_archive_failure(source_path=entry["source_path"], source_exists=False)
        failure_category = classification["category"]
        failure_summary = summarize_source_archive_failure_for_operator(classification)
        blocked.append(failure_summary)
        safe_to_retry = classification["safe_to_retry"]
        retry_cost = "unknown"
    else:
        known_failure = classify_source_archive_failure(
            source_path=entry["source_path"],
            source_exists=True,
            source_size_bytes=entry["source_size_bytes"],
        )
        try:
            key_payload = collect_cache_key(source_path=entry["source_path"])
            manifest = collect_manifest(source_path=entry["source_path"])
            cache_key_id = key_payload["source_archive_intake_cache_key_id"]
            manifest_id = manifest["persistent_source_inventory_cache_manifest_id"]
            if known_failure["category"] != "unknown":
                status = "unsupported"
                failure_category = known_failure["category"]
                failure_summary = summarize_source_archive_failure_for_operator(known_failure)
                blocked.append(failure_summary)
                safe_to_retry = known_failure["safe_to_retry"]
                retry_cost = "high"
            else:
                status = "suitable"
                queue_eligible = True
                persistent_eligible = True
                e2e_eligible = True
                default_eligible = True
                warnings = list(entry["warnings"])
        except Exception as exc:
            classification = classify_source_archive_failure(
                source_path=entry["source_path"],
                error_text=str(exc),
                source_exists=entry["source_exists"],
                source_size_bytes=entry["source_size_bytes"],
            )
            status = "failed"
            failure_category = classification["category"]
            failure_summary = summarize_source_archive_failure_for_operator(classification)
            blocked.append(failure_summary)
            safe_to_retry = classification["safe_to_retry"]
            retry_cost = "unknown"
    payload = {
        "source_archive_suitability_assessment_version": SOURCE_ARCHIVE_SUITABILITY_ASSESSMENT_VERSION,
        "source_archive_suitability_assessment_id": "source-archive-suitability-assessment-" + _hash_text({"source_path": entry["source_path"], "status": status, "failure_category": failure_category, "version": SOURCE_ARCHIVE_SUITABILITY_ASSESSMENT_VERSION})[:12],
        "source_path": entry["source_path"],
        "source_name": entry["source_name"],
        "source_type": entry["source_type"],
        "source_exists": entry["source_exists"],
        "source_size_bytes": entry["source_size_bytes"],
        "source_mtime_ns": entry["source_mtime_ns"],
        "cache_key_id": cache_key_id,
        "manifest_id": manifest_id,
        "suitability_status": status,
        "queue_eligible": queue_eligible,
        "persistent_cache_eligible": persistent_eligible,
        "growth_e2e_eligible": e2e_eligible,
        "default_queue_eligible": default_eligible,
        "failure_category": failure_category,
        "failure_summary": failure_summary,
        "blocked_reasons": _normalize_refs(blocked),
        "warnings": _normalize_refs(warnings),
        "recommended_next_action": "Source is suitable for queue warmup and Growth E2E." if queue_eligible else "Skip or quarantine this source until the deterministic source suitability issue is fixed.",
        "safe_to_retry": safe_to_retry,
        "retry_cost": retry_cost,
        "fallback_allowed": False,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_source_archive_suitability_assessment(payload)
    return payload


def validate_source_archive_suitability_assessment(payload: Mapping[str, Any]) -> None:
    required = ("source_archive_suitability_assessment_version", "source_archive_suitability_assessment_id", "source_path", "source_name", "source_type", "source_exists", "source_size_bytes", "source_mtime_ns", "cache_key_id", "manifest_id", "suitability_status", "queue_eligible", "persistent_cache_eligible", "growth_e2e_eligible", "default_queue_eligible", "failure_category", "failure_summary", "blocked_reasons", "warnings", "recommended_next_action", "safe_to_retry", "retry_cost", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"source archive suitability assessment missing field: {key}")
    if payload["source_archive_suitability_assessment_version"] != SOURCE_ARCHIVE_SUITABILITY_ASSESSMENT_VERSION:
        raise ValueError("invalid source archive suitability assessment version")
    if payload["suitability_status"] not in {"suitable", "suitable_with_warnings", "unsuitable", "unsupported", "failed"}:
        raise ValueError("invalid source suitability status")
    if payload["retry_cost"] not in {"low", "medium", "high", "unknown"}:
        raise ValueError("invalid source suitability retry cost")
    if payload["queue_eligible"] and payload["blocked_reasons"]:
        raise ValueError("queue eligible source must not have blockers")
    if not payload["queue_eligible"] and not payload["failure_category"]:
        raise ValueError("ineligible source must include failure category")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("source suitability must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("source suitability must remain read-only")


def stable_source_archive_suitability_assessment_json(payload: dict[str, Any]) -> str:
    validate_source_archive_suitability_assessment(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_source_archive_suitability_assessment_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_source_archive_suitability_assessment(payload)
    return payload


def collect_source_queue_quarantine_record(
    *,
    source_path: str,
    assessment: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    collect_suitability: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    assess = assessment or collect_suitability(source_path=source_path)
    validate_source_archive_suitability_assessment(assess)
    suitable = bool(assess["queue_eligible"])
    status = "not_quarantined" if suitable else "quarantined"
    reason = "" if suitable else assess["failure_summary"]
    safe_explicit = bool(suitable)
    payload = {
        "source_queue_quarantine_record_version": SOURCE_QUEUE_QUARANTINE_RECORD_VERSION,
        "source_queue_quarantine_record_id": "source-queue-quarantine-record-" + _hash_text({"assessment_id": assess["source_archive_suitability_assessment_id"], "status": status, "version": SOURCE_QUEUE_QUARANTINE_RECORD_VERSION})[:12],
        "source_path": assess["source_path"],
        "suitability_assessment_id": assess["source_archive_suitability_assessment_id"],
        "quarantine_status": status,
        "quarantine_reason": reason,
        "failure_category": assess["failure_category"],
        "excluded_from_default_queue": not suitable,
        "excluded_from_warmup": not suitable,
        "excluded_from_e2e": not suitable,
        "safe_to_include_explicitly": safe_explicit,
        "explicit_include_warning": "" if suitable else "Explicit source was not included because deterministic suitability failed closed.",
        "recommended_fix": "No quarantine fix required." if suitable else classify_source_archive_failure(source_path=assess["source_path"], error_text=assess["failure_summary"], source_exists=assess["source_exists"], source_size_bytes=assess["source_size_bytes"])["recommended_fix"],
        "recommended_next_action": "Use this source in queue warmup." if suitable else "Keep this source skipped/quarantined until the recommended fix is implemented.",
        "fallback_allowed": False,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_source_queue_quarantine_record(payload)
    return payload


def validate_source_queue_quarantine_record(payload: Mapping[str, Any]) -> None:
    required = ("source_queue_quarantine_record_version", "source_queue_quarantine_record_id", "source_path", "suitability_assessment_id", "quarantine_status", "quarantine_reason", "failure_category", "excluded_from_default_queue", "excluded_from_warmup", "excluded_from_e2e", "safe_to_include_explicitly", "explicit_include_warning", "recommended_fix", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"source queue quarantine record missing field: {key}")
    if payload["source_queue_quarantine_record_version"] != SOURCE_QUEUE_QUARANTINE_RECORD_VERSION:
        raise ValueError("invalid source queue quarantine record version")
    if payload["quarantine_status"] not in {"not_quarantined", "quarantined", "skipped", "needs_review"}:
        raise ValueError("invalid source queue quarantine status")
    if payload["quarantine_status"] != "not_quarantined" and not payload["quarantine_reason"]:
        raise ValueError("quarantined source must include reason")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("source queue quarantine must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("source queue quarantine must remain read-only")


def stable_source_queue_quarantine_record_json(payload: dict[str, Any]) -> str:
    validate_source_queue_quarantine_record(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_source_queue_quarantine_record_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_source_queue_quarantine_record(payload)
    return payload
