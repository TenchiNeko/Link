"""Growth source queue subsystem.

Extracted from ``link_growth_console.py`` with explicit callback boundaries.
This module owns source-queue payload, cache-status, and warmup-plan helpers.
CLI dispatch remains in the monolith. Broad integrations are supplied through
callbacks so this module does not import ``link_growth_console.py``.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Mapping

from link_modes.growth.growth_source_suitability import (
    GROWTH_SOURCE_QUEUE_OPTIONAL,
    GROWTH_SOURCE_QUEUE_REQUIRED,
)

GROWTH_SOURCE_QUEUE_VERSION = "link-growth-source-queue-v1"
GROWTH_SOURCE_QUEUE_CACHE_STATUS_VERSION = "link-growth-source-queue-cache-status-v1"
GROWTH_SOURCE_QUEUE_WARMUP_PLAN_VERSION = "link-growth-source-queue-warmup-plan-v1"


def _stable_json(value: Any, indent: int | None = None) -> str:
    kwargs: dict[str, Any] = {"sort_keys": True, "default": str}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return json.dumps(value, **kwargs)


def _hash_text(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def collect_growth_source_queue(
    *,
    sources: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    collect_policy: Callable[..., dict[str, Any]],
    queue_source_entry: Callable[..., dict[str, Any]],
    collect_suitability: Callable[..., dict[str, Any]],
    collect_quarantine: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    explicit = [str(item).strip() for item in (sources or []) if str(item).strip()]
    requested = explicit if explicit else list(GROWTH_SOURCE_QUEUE_REQUIRED) + list(GROWTH_SOURCE_QUEUE_OPTIONAL)
    policy = collect_policy()
    selected: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    quarantine_records: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    explicit_include_sources: list[dict[str, Any]] = []
    required_failures: list[str] = []
    seen: set[str] = set()
    for index, source_path in enumerate(requested, 1):
        if source_path in seen:
            skipped.append({"source_path": source_path, "reason": "duplicate source"})
            continue
        seen.add(source_path)
        entry = queue_source_entry(source_path, priority=index, reason_selected="explicit source" if explicit else "default queue candidate")
        assessment = collect_suitability(source_path=source_path)
        quarantine = collect_quarantine(source_path=source_path, assessment=assessment)
        assessments.append(assessment)
        quarantine_records.append(quarantine)
        is_required = source_path in policy["required_sources"]
        is_optional = source_path in policy["optional_sources"]
        source_note = {
            "source_path": source_path,
            "suitability_status": assessment["suitability_status"],
            "queue_eligible": assessment["queue_eligible"],
            "quarantine_status": quarantine["quarantine_status"],
            "failure_category": assessment["failure_category"],
            "skip_reason": quarantine["quarantine_reason"],
            "explicit_include_warning": quarantine["explicit_include_warning"],
        }
        if explicit:
            explicit_include_sources.append(source_note)
        if entry["source_exists"] and source_path.startswith("research/") and assessment["queue_eligible"]:
            entry.update(source_note)
            selected.append(entry)
        elif is_required:
            missing.append(entry)
            required_failures.append(source_path)
            skipped.append({"source_path": source_path, "reason": quarantine["quarantine_reason"] or "required source is not queue eligible"})
        elif explicit and not entry["source_exists"]:
            missing.append(entry)
            skipped.append({"source_path": source_path, "reason": quarantine["quarantine_reason"] or "explicit source is missing"})
        elif explicit:
            skipped.append({"source_path": source_path, "reason": quarantine["quarantine_reason"] or "explicit source is not queue eligible"})
            excluded.append(source_note)
        elif is_optional and assessment["source_exists"]:
            skipped.append({"source_path": source_path, "reason": quarantine["quarantine_reason"] or "optional source is not queue eligible"})
            excluded.append(source_note)
        elif explicit:
            missing.append(entry)
        else:
            skipped.append({"source_path": source_path, "reason": "optional source not present"})
    discovered = [item for item in selected]
    quarantined_count = sum(1 for item in quarantine_records if item["quarantine_status"] != "not_quarantined")
    unsuitable_count = sum(1 for item in assessments if item["suitability_status"] in {"unsuitable", "unsupported", "failed"})
    queue_ready = bool(selected) and not required_failures
    payload = {
        "growth_source_queue_version": GROWTH_SOURCE_QUEUE_VERSION,
        "growth_source_queue_id": "growth-source-queue-" + _hash_text({"sources": [item["source_path"] for item in selected], "missing": [item["source_path"] for item in missing], "excluded": [item["source_path"] for item in excluded], "version": GROWTH_SOURCE_QUEUE_VERSION})[:12],
        "queue_name": "growth-source-cache-warmup",
        "queue_version": "v1",
        "source_queue_policy_id": policy["growth_source_queue_policy_id"],
        "requested_sources": requested,
        "discovered_sources": discovered,
        "selected_sources": selected,
        "missing_sources": missing,
        "skipped_sources": skipped,
        "source_count": len(selected),
        "queue_policy": {
            "default_required_sources": policy["required_sources"],
            "default_optional_sources": policy["optional_sources"],
            "archive_extraction_allowed": False,
            "model_allowed": False,
            "external_network_allowed": False,
            "source_mutation_allowed": False,
            "optional_source_failure_policy": policy["optional_source_failure_policy"],
            "required_source_failure_policy": policy["required_source_failure_policy"],
        },
        "suitability_assessments": assessments,
        "quarantine_records": quarantine_records,
        "suitable_source_count": sum(1 for item in assessments if item["queue_eligible"]),
        "quarantined_source_count": quarantined_count,
        "skipped_source_count": len(skipped),
        "unsuitable_source_count": unsuitable_count,
        "default_queue_excluded_sources": excluded,
        "explicit_include_sources": explicit_include_sources,
        "queue_ready_for_warmup": queue_ready,
        "queue_ready_for_e2e": queue_ready,
        "recommended_next_action": "Run growth source-queue-status, then source-queue-warm --write-cache before queue E2E." if queue_ready else "Review skipped/quarantined sources before warmup; required source failures fail closed.",
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
    validate_growth_source_queue(payload)
    return payload


def validate_growth_source_queue(payload: Mapping[str, Any]) -> None:
    required = ("growth_source_queue_version", "growth_source_queue_id", "queue_name", "queue_version", "source_queue_policy_id", "requested_sources", "discovered_sources", "selected_sources", "missing_sources", "skipped_sources", "source_count", "queue_policy", "suitability_assessments", "quarantine_records", "suitable_source_count", "quarantined_source_count", "skipped_source_count", "unsuitable_source_count", "default_queue_excluded_sources", "explicit_include_sources", "queue_ready_for_warmup", "queue_ready_for_e2e", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"growth source queue missing field: {key}")
    if payload["growth_source_queue_version"] != GROWTH_SOURCE_QUEUE_VERSION:
        raise ValueError("invalid growth source queue version")
    if payload["source_count"] != len(payload["selected_sources"]):
        raise ValueError("growth source queue source_count mismatch")
    for entry in payload["selected_sources"]:
        for key in ("source_path", "source_exists", "source_name", "source_type", "source_size_bytes", "source_mtime_ns", "guessed_concept_family", "priority", "reason_selected", "warnings", "suitability_status", "queue_eligible", "quarantine_status", "failure_category", "skip_reason", "explicit_include_warning"):
            if key not in entry:
                raise ValueError(f"growth source queue selected entry missing {key}")
        if not entry["source_exists"] or not entry["source_path"].startswith("research/"):
            raise ValueError("growth source queue selected sources must be existing research sources")
        if entry["queue_eligible"] is not True or entry["quarantine_status"] != "not_quarantined":
            raise ValueError("growth source queue selected sources must be eligible and not quarantined")
    if payload["suitable_source_count"] != sum(1 for item in payload["suitability_assessments"] if item.get("queue_eligible")):
        raise ValueError("growth source queue suitable count mismatch")
    if payload["quarantined_source_count"] != sum(1 for item in payload["quarantine_records"] if item.get("quarantine_status") != "not_quarantined"):
        raise ValueError("growth source queue quarantine count mismatch")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth source queue must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("growth source queue must remain read-only")


def stable_growth_source_queue_json(payload: dict[str, Any]) -> str:
    validate_growth_source_queue(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_source_queue_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_source_queue(payload)
    return payload


def collect_growth_source_queue_cache_status(
    *,
    sources: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    collect_queue: Callable[..., dict[str, Any]],
    collect_cache_policy: Callable[..., dict[str, Any]],
    collect_observability_card: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    queue = collect_queue(sources=sources)
    policy = collect_cache_policy()
    source_statuses: list[dict[str, Any]] = []
    ages: list[int] = []
    total_cached = 0
    for entry in queue["selected_sources"]:
        card = collect_observability_card(source_path=entry["source_path"])
        if isinstance(card["cache_age_seconds"], int):
            ages.append(card["cache_age_seconds"])
        total_cached += int(card["cached_size_bytes"])
        status = card["cache_status"]
        source_statuses.append({
            "source_path": card["source_path"],
            "cache_observability_card_id": card["source_cache_observability_card_id"],
            "cache_status": status,
            "cache_hit": card["cache_hit"],
            "cache_valid": card["cache_valid"],
            "cache_age_seconds": card["cache_age_seconds"],
            "cached_size_bytes": card["cached_size_bytes"],
            "invalidation_reasons": card["invalidation_reasons"],
            "recommended_action": card["recommended_next_action"],
            "suitability_status": entry["suitability_status"],
            "queue_eligible": entry["queue_eligible"],
            "quarantine_status": entry["quarantine_status"],
            "failure_category": entry["failure_category"],
            "skip_reason": entry["skip_reason"],
            "explicit_include_warning": entry["explicit_include_warning"],
        })
    hit_count = sum(1 for item in source_statuses if item["cache_status"] == "hit")
    miss_count = sum(1 for item in source_statuses if item["cache_status"] == "miss")
    stale_count = sum(1 for item in source_statuses if item["cache_status"] == "stale")
    invalid_count = sum(1 for item in source_statuses if item["cache_status"] == "invalid")
    missing_count = len(queue["missing_sources"])
    ready = bool(source_statuses) and hit_count == len(source_statuses) and missing_count == 0
    payload = {
        "growth_source_queue_cache_status_version": GROWTH_SOURCE_QUEUE_CACHE_STATUS_VERSION,
        "growth_source_queue_cache_status_id": "growth-source-queue-cache-status-" + _hash_text({"queue_id": queue["growth_source_queue_id"], "statuses": source_statuses, "version": GROWTH_SOURCE_QUEUE_CACHE_STATUS_VERSION})[:12],
        "source_queue_id": queue["growth_source_queue_id"],
        "source_queue_policy_id": queue["source_queue_policy_id"],
        "cache_policy_id": policy["persistent_source_inventory_cache_policy_id"],
        "cache_root": policy["cache_root"],
        "source_statuses": source_statuses,
        "source_count": len(source_statuses),
        "cache_hit_count": hit_count,
        "cache_miss_count": miss_count,
        "stale_count": stale_count,
        "invalid_count": invalid_count,
        "missing_count": missing_count,
        "total_cached_size_bytes": total_cached,
        "oldest_cache_age_seconds": max(ages) if ages else None,
        "newest_cache_age_seconds": min(ages) if ages else None,
        "suitability_assessments": queue["suitability_assessments"],
        "quarantine_records": queue["quarantine_records"],
        "suitable_source_count": queue["suitable_source_count"],
        "quarantined_source_count": queue["quarantined_source_count"],
        "skipped_source_count": queue["skipped_source_count"],
        "unsuitable_source_count": queue["unsuitable_source_count"],
        "default_queue_excluded_sources": queue["default_queue_excluded_sources"],
        "explicit_include_sources": queue["explicit_include_sources"],
        "queue_ready_for_warmup": queue["queue_ready_for_warmup"],
        "queue_ready_for_e2e": ready and queue["queue_ready_for_e2e"],
        "recommended_next_action": "Queue caches are warm; run growth source-queue-e2e." if ready else "Run growth source-queue-warm --write-cache to warm missing/stale/invalid source caches.",
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
    validate_growth_source_queue_cache_status(payload)
    return payload


def validate_growth_source_queue_cache_status(payload: Mapping[str, Any]) -> None:
    required = ("growth_source_queue_cache_status_version", "growth_source_queue_cache_status_id", "source_queue_id", "source_queue_policy_id", "cache_policy_id", "cache_root", "source_statuses", "source_count", "cache_hit_count", "cache_miss_count", "stale_count", "invalid_count", "missing_count", "total_cached_size_bytes", "oldest_cache_age_seconds", "newest_cache_age_seconds", "suitability_assessments", "quarantine_records", "suitable_source_count", "quarantined_source_count", "skipped_source_count", "unsuitable_source_count", "default_queue_excluded_sources", "explicit_include_sources", "queue_ready_for_warmup", "queue_ready_for_e2e", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"growth source queue cache status missing field: {key}")
    if payload["growth_source_queue_cache_status_version"] != GROWTH_SOURCE_QUEUE_CACHE_STATUS_VERSION:
        raise ValueError("invalid growth source queue cache status version")
    if payload["source_count"] != len(payload["source_statuses"]):
        raise ValueError("growth source queue cache status count mismatch")
    for item in payload["source_statuses"]:
        if item.get("cache_status") not in {"hit", "miss", "stale", "invalid"}:
            raise ValueError("invalid queue source cache status")
        for key in ("suitability_status", "queue_eligible", "quarantine_status", "failure_category", "skip_reason", "explicit_include_warning"):
            if key not in item:
                raise ValueError(f"queue source cache status missing {key}")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth source queue cache status must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("growth source queue cache status must remain read-only")


def stable_growth_source_queue_cache_status_json(payload: dict[str, Any]) -> str:
    validate_growth_source_queue_cache_status(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_source_queue_cache_status_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_source_queue_cache_status(payload)
    return payload


def collect_growth_source_queue_warmup_plan(
    *,
    sources: list[str] | None = None,
    write_cache: bool = False,
    metadata: dict[str, Any] | None = None,
    collect_queue: Callable[..., dict[str, Any]],
    collect_status: Callable[..., dict[str, Any]],
    collect_manifest: Callable[..., dict[str, Any]],
    collect_cache_record: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    started = time.perf_counter()
    queue = collect_queue(sources=sources)
    status = collect_status(sources=sources)
    sources_to_warm: list[dict[str, Any]] = []
    already_warm: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in status["source_statuses"]:
        if item["cache_status"] == "hit":
            already_warm.append({"source_path": item["source_path"], "reason": "valid persistent cache already exists", "current_status": item["cache_status"]})
        else:
            try:
                manifest = collect_manifest(source_path=item["source_path"])
                manifest_id = manifest["persistent_source_inventory_cache_manifest_id"]
            except Exception:
                manifest_id = ""
            sources_to_warm.append({
                "source_path": item["source_path"],
                "reason": item["cache_status"],
                "manifest_id": manifest_id,
                "current_status": item["cache_status"],
                "planned_write_command": f"python3 link.py growth source-cache-persistent --source {item['source_path']} --write-cache --json",
            })
    for missing in queue["missing_sources"]:
        skipped.append({"source_path": missing["source_path"], "reason": "source missing or invalid"})
    for quarantine in queue["quarantine_records"]:
        if quarantine["quarantine_status"] != "not_quarantined":
            skipped.append({"source_path": quarantine["source_path"], "reason": quarantine["quarantine_reason"]})
    warmed_sources: list[dict[str, Any]] = []
    failed_sources: list[dict[str, Any]] = []
    write_performed = False
    if write_cache:
        for item in sources_to_warm:
            t0 = time.perf_counter()
            try:
                record = collect_cache_record(source_path=item["source_path"], write_cache=True)
                runtime_ms = int((time.perf_counter() - t0) * 1000)
                write_performed = write_performed or bool(record["cache_write_performed"])
                warmed_sources.append({
                    "source_path": record["source_path"],
                    "cache_record_id": record["persistent_source_inventory_cache_record_id"],
                    "cache_file_path": record["cache_file_path"],
                    "cache_write_performed": record["cache_write_performed"],
                    "runtime_ms": runtime_ms,
                    "cached_size_bytes": record["cached_size_bytes"],
                })
            except Exception as exc:
                failed_sources.append({
                    "source_path": item["source_path"],
                    "error": _source_text(str(exc), max_chars=220),
                    "runtime_ms": int((time.perf_counter() - t0) * 1000),
                })
    runtime_ms = int((time.perf_counter() - started) * 1000)
    slowest = sorted(warmed_sources + failed_sources, key=lambda item: item.get("runtime_ms", 0), reverse=True)[:5]
    writes = [item["cache_file_path"] for item in warmed_sources if item.get("cache_write_performed")]
    payload = {
        "growth_source_queue_warmup_plan_version": GROWTH_SOURCE_QUEUE_WARMUP_PLAN_VERSION,
        "growth_source_queue_warmup_plan_id": "growth-source-queue-warmup-plan-" + _hash_text({"status_id": status["growth_source_queue_cache_status_id"], "write": write_cache, "warmed": warmed_sources, "version": GROWTH_SOURCE_QUEUE_WARMUP_PLAN_VERSION})[:12],
        "source_queue_cache_status_id": status["growth_source_queue_cache_status_id"],
        "cache_policy_id": status["cache_policy_id"],
        "source_queue_policy_id": queue["source_queue_policy_id"],
        "warmup_requested": True,
        "write_cache_requested": bool(write_cache),
        "sources_to_warm": sources_to_warm,
        "sources_already_warm": already_warm,
        "sources_skipped": skipped,
        "estimated_work_count": len(sources_to_warm),
        "planned_commands": [item["planned_write_command"] for item in sources_to_warm],
        "write_cache_performed": write_performed,
        "warmed_sources": warmed_sources,
        "failed_sources": failed_sources,
        "skipped_sources": skipped + already_warm,
        "warmed_count": len(warmed_sources),
        "failed_count": len(failed_sources),
        "skipped_count": len(skipped) + len(already_warm),
        "total_runtime_ms": runtime_ms,
        "slowest_sources": slowest,
        "suitability_assessments": queue["suitability_assessments"],
        "quarantine_records": queue["quarantine_records"],
        "suitable_source_count": queue["suitable_source_count"],
        "quarantined_source_count": queue["quarantined_source_count"],
        "skipped_source_count": queue["skipped_source_count"],
        "unsuitable_source_count": queue["unsuitable_source_count"],
        "default_queue_excluded_sources": queue["default_queue_excluded_sources"],
        "explicit_include_sources": queue["explicit_include_sources"],
        "queue_ready_for_warmup": queue["queue_ready_for_warmup"],
        "queue_ready_for_e2e": status["queue_ready_for_e2e"],
        "recommended_next_action": "Run growth source-queue-status, then growth source-queue-e2e." if write_cache and not failed_sources else "Review this plan, then rerun with --write-cache to warm the queue.",
        "fallback_allowed": False,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": bool(write_cache),
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": writes,
    }
    validate_growth_source_queue_warmup_plan(payload)
    return payload


def validate_growth_source_queue_warmup_plan(payload: Mapping[str, Any]) -> None:
    required = ("growth_source_queue_warmup_plan_version", "growth_source_queue_warmup_plan_id", "source_queue_cache_status_id", "cache_policy_id", "source_queue_policy_id", "warmup_requested", "write_cache_requested", "sources_to_warm", "sources_already_warm", "sources_skipped", "estimated_work_count", "planned_commands", "write_cache_performed", "warmed_sources", "failed_sources", "skipped_sources", "warmed_count", "failed_count", "skipped_count", "total_runtime_ms", "slowest_sources", "suitability_assessments", "quarantine_records", "suitable_source_count", "quarantined_source_count", "skipped_source_count", "unsuitable_source_count", "default_queue_excluded_sources", "explicit_include_sources", "queue_ready_for_warmup", "queue_ready_for_e2e", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"growth source queue warmup plan missing field: {key}")
    if payload["growth_source_queue_warmup_plan_version"] != GROWTH_SOURCE_QUEUE_WARMUP_PLAN_VERSION:
        raise ValueError("invalid growth source queue warmup plan version")
    if payload["estimated_work_count"] != len(payload["sources_to_warm"]):
        raise ValueError("growth source queue warmup estimated work mismatch")
    if payload["write_cache_requested"] is False and payload["writes"]:
        raise ValueError("growth source queue warmup preview must not write")
    if payload["warmed_count"] != len(payload["warmed_sources"]) or payload["failed_count"] != len(payload["failed_sources"]):
        raise ValueError("growth source queue warmup count mismatch")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth source queue warmup must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["automation_allowed"] is not False:
        raise ValueError("growth source queue warmup must remain deterministic")
    if payload["write_allowed"] != payload["write_cache_requested"]:
        raise ValueError("growth source queue warmup write flag mismatch")


def stable_growth_source_queue_warmup_plan_json(payload: dict[str, Any]) -> str:
    validate_growth_source_queue_warmup_plan(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_source_queue_warmup_plan_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_source_queue_warmup_plan(payload)
    return payload
