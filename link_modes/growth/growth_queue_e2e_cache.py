#!/usr/bin/env python3
"""Compact Growth source queue E2E cache subsystem.

This module owns compact queue E2E cache key, read/write, and status helpers.
It intentionally does not import ``link_growth_console`` or perform CLI
dispatch. Callers provide queue, manifest, and summary callbacks so full queue
construction and E2E collection stay outside this cache module.
"""

from __future__ import annotations

from typing import Any, Callable

GROWTH_SOURCE_QUEUE_POLICY_VERSION = "link-growth-source-queue-policy-v1"
GROWTH_SOURCE_QUEUE_VERSION = "link-growth-source-queue-v1"
GROWTH_SOURCE_QUEUE_E2E_SUMMARY_VERSION = "link-growth-source-queue-e2e-summary-v1"
GROWTH_SOURCE_QUEUE_E2E_CACHE_KEY_VERSION = "link-growth-source-queue-e2e-cache-key-v1"
GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION = "link-growth-source-queue-e2e-cache-record-v1"
REPO_ROLE_CALIBRATION_POLICY_VERSION = "link-repo-role-calibration-policy-v1"
CONCEPT_CONFIDENCE_CALIBRATION_VERSION = "link-concept-confidence-calibration-v1"
GROWTH_OPPORTUNITY_DECISION_SCORE_VERSION = "link-growth-opportunity-decision-score-v1"
PERSISTENT_SOURCE_INVENTORY_CACHE_SCHEMA_VERSION = "link-source-inventory-cache-schema-v1"
PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES = 1500000


def _stable_json(value: Any, indent: int | None = None) -> str:
    import json as _json

    kwargs: dict[str, Any] = {"sort_keys": True, "default": str}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return _json.dumps(value, **kwargs)


def _hash_text(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read_only_safety_metadata() -> dict[str, Any]:
    return {
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "writes": [],
    }


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


def _short_text(text: str, *, max_chars: int = 220) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)].rstrip() + "..."


def _cache_age_seconds(created_at: str) -> int | None:
    if not created_at:
        return None
    import datetime as _dt

    try:
        created = _dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at.endswith("Z") else _dt.datetime.fromisoformat(created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=_dt.timezone.utc)
        now = _dt.datetime.now(_dt.timezone.utc)
        return max(0, int((now - created).total_seconds()))
    except Exception:
        return None


def growth_source_queue_e2e_cache_file_path(cache_root: str, cache_key: str) -> str:
    from pathlib import Path as _Path

    digest = _hash_text(cache_key)[:24]
    return str(_Path(cache_root).expanduser() / f"growth-source-queue-e2e-summary-{digest}.json")


def collect_growth_source_queue_e2e_cache_key(
    *,
    sources: list[str] | None = None,
    mode: str = "fast",
    metadata: dict[str, Any] | None = None,
    collect_queue: Callable[..., dict[str, Any]],
    collect_policy: Callable[..., dict[str, Any]],
    collect_manifest: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    queue = collect_queue(sources=sources)
    policy = collect_policy()
    source_manifest_ids: list[str] = []
    source_inputs: list[dict[str, Any]] = []
    for item in queue["selected_sources"]:
        manifest = collect_manifest(source_path=item["source_path"])
        source_manifest_ids.append(manifest["persistent_source_inventory_cache_manifest_id"])
        source_inputs.append({
            "source_path": manifest["source_path"],
            "manifest_id": manifest["persistent_source_inventory_cache_manifest_id"],
            "source_size_bytes": manifest["source_size_bytes"],
            "source_mtime_ns": manifest["source_mtime_ns"],
            "source_cache_key": manifest["cache_key"],
        })
    skipped_inputs = [
        {
            "source_path": item["source_path"],
            "quarantine_status": item.get("quarantine_status", ""),
            "failure_category": item.get("failure_category", ""),
            "skip_reason": item.get("skip_reason", ""),
        }
        for item in queue.get("default_queue_excluded_sources", []) + queue.get("skipped_sources", [])
    ]
    schema_versions = {
        "queue_policy": GROWTH_SOURCE_QUEUE_POLICY_VERSION,
        "queue": GROWTH_SOURCE_QUEUE_VERSION,
        "queue_e2e": GROWTH_SOURCE_QUEUE_E2E_SUMMARY_VERSION,
        "queue_e2e_cache_key": GROWTH_SOURCE_QUEUE_E2E_CACHE_KEY_VERSION,
        "queue_e2e_cache_record": GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION,
        "repo_role_policy": REPO_ROLE_CALIBRATION_POLICY_VERSION,
        "concept_confidence": CONCEPT_CONFIDENCE_CALIBRATION_VERSION,
        "opportunity_score": GROWTH_OPPORTUNITY_DECISION_SCORE_VERSION,
        "source_inventory_cache": PERSISTENT_SOURCE_INVENTORY_CACHE_SCHEMA_VERSION,
    }
    invalidation_inputs = {
        "selected_sources": source_inputs,
        "skipped_sources": skipped_inputs,
        "source_queue_id": queue["growth_source_queue_id"],
        "source_queue_policy_id": queue["source_queue_policy_id"],
        "suitability_assessment_ids": [item["source_archive_suitability_assessment_id"] for item in queue.get("suitability_assessments", [])],
        "quarantine_record_ids": [item["source_queue_quarantine_record_id"] for item in queue.get("quarantine_records", [])],
        "schema_versions": schema_versions,
        "mode": mode,
    }
    cache_fingerprint = _hash_text(invalidation_inputs)[:24]
    cache_key = f"growth-source-queue-e2e-summary:{GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION}:{cache_fingerprint}"
    payload = {
        "growth_source_queue_e2e_cache_key_version": GROWTH_SOURCE_QUEUE_E2E_CACHE_KEY_VERSION,
        "growth_source_queue_e2e_cache_key_id": "growth-source-queue-e2e-cache-key-" + cache_fingerprint[:12],
        "cache_key": cache_key,
        "selected_sources": [item["source_path"] for item in queue["selected_sources"]],
        "skipped_sources": skipped_inputs,
        "source_manifest_ids": source_manifest_ids,
        "policy_ids": [queue["source_queue_policy_id"], policy["persistent_source_inventory_cache_policy_id"]],
        "schema_versions": schema_versions,
        "invalidation_inputs": invalidation_inputs,
        "cache_root": policy["cache_root"],
        "cache_file_path": growth_source_queue_e2e_cache_file_path(policy["cache_root"], cache_key),
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
    validate_growth_source_queue_e2e_cache_key(payload)
    return payload


def validate_growth_source_queue_e2e_cache_key(payload: dict[str, Any]) -> None:
    required = ("growth_source_queue_e2e_cache_key_version", "growth_source_queue_e2e_cache_key_id", "cache_key", "selected_sources", "skipped_sources", "source_manifest_ids", "policy_ids", "schema_versions", "invalidation_inputs", "cache_root", "cache_file_path", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"growth source queue e2e cache key missing field: {key}")
    if payload["growth_source_queue_e2e_cache_key_version"] != GROWTH_SOURCE_QUEUE_E2E_CACHE_KEY_VERSION:
        raise ValueError("invalid growth source queue e2e cache key version")
    if not payload["growth_source_queue_e2e_cache_key_id"].startswith("growth-source-queue-e2e-cache-key-"):
        raise ValueError("invalid growth source queue e2e cache key id")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth source queue e2e cache key must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("growth source queue e2e cache key must remain read-only")


def stable_growth_source_queue_e2e_cache_key_json(payload: dict[str, Any]) -> str:
    validate_growth_source_queue_e2e_cache_key(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_source_queue_e2e_cache_key_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_growth_source_queue_e2e_cache_key(payload)
    return payload


def growth_source_queue_e2e_cache_payload(
    cache_key: dict[str, Any],
    summary: dict[str, Any],
    *,
    validate_summary: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    import datetime as _dt

    compact = dict(summary)
    compact["writes"] = []
    compact["write_allowed"] = False
    compact["queue_e2e_cache_write_performed"] = False
    payload = {
        "growth_source_queue_e2e_cache_payload_version": GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION,
        "cache_key": cache_key["cache_key"],
        "cache_key_id": cache_key["growth_source_queue_e2e_cache_key_id"],
        "created_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "compact_queue_e2e_summary": compact,
    }
    validate_growth_source_queue_e2e_cache_payload(payload, validate_summary=validate_summary)
    return payload


def validate_growth_source_queue_e2e_cache_payload(
    payload: dict[str, Any],
    *,
    validate_summary: Callable[[dict[str, Any]], None],
) -> None:
    for key in ("growth_source_queue_e2e_cache_payload_version", "cache_key", "cache_key_id", "created_at", "compact_queue_e2e_summary"):
        if key not in payload:
            raise ValueError(f"growth source queue e2e cache payload missing {key}")
    if payload["growth_source_queue_e2e_cache_payload_version"] != GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION:
        raise ValueError("invalid growth source queue e2e cache payload version")
    validate_summary(payload["compact_queue_e2e_summary"])
    text = _stable_json(payload)
    if len(text.encode("utf-8")) > PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES:
        raise ValueError("growth source queue e2e compact cache payload exceeds max size")


def read_growth_source_queue_e2e_cache(
    cache_file_path: str,
    *,
    validate_payload: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    import json as _json
    from pathlib import Path as _Path

    try:
        path = _Path(cache_file_path)
        if not path.exists():
            return {"ok": False, "error": "cache file missing"}
        payload = _json.loads(path.read_text())
        validate_payload(payload)
        return {"ok": True, "payload": payload}
    except Exception as exc:
        return {"ok": False, "error": _short_text(str(exc), max_chars=220)}


def write_growth_source_queue_e2e_cache(
    cache_file_path: str,
    payload: dict[str, Any],
    *,
    validate_payload: Callable[[dict[str, Any]], None],
    path_is_safe: Callable[[str], bool],
) -> int:
    from pathlib import Path as _Path
    import os as _os
    import tempfile as _tempfile

    validate_payload(payload)
    path = _Path(cache_file_path).expanduser()
    root = path.parent
    if not str(root).startswith("/tmp/") and not path_is_safe(str(root)):
        raise ValueError("growth source queue e2e cache root is not safe to write")
    root.mkdir(parents=True, exist_ok=True)
    text = _stable_json(payload, indent=2) + "\n"
    fd, tmp = _tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(root))
    try:
        with _os.fdopen(fd, "w") as handle:
            handle.write(text)
        _os.replace(tmp, path)
    finally:
        try:
            if _Path(tmp).exists():
                _Path(tmp).unlink()
        except Exception:
            pass
    return len(text.encode("utf-8"))


def queue_e2e_summary_from_cache_record(
    record: dict[str, Any],
    *,
    validate_summary: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    summary = dict(record["compact_queue_e2e_summary"])
    summary["queue_e2e_cache_key_id"] = record["cache_key_id"]
    summary["queue_e2e_cache_record_id"] = record["growth_source_queue_e2e_cache_record_id"]
    summary["queue_e2e_cache_hit"] = True
    summary["queue_e2e_cache_used"] = True
    summary["queue_e2e_cache_write_performed"] = False
    summary["queue_e2e_summary_reuse_source"] = "compact_cache"
    summary["queue_e2e_summary_source"] = "compact_cache"
    summary["report_mode"] = "fast"
    summary["request_reuse_summary"] = dict(summary.get("request_reuse_summary", {}))
    summary["request_reuse_summary"].update({
        "queue_e2e_compact_cache_used": True,
        "queue_e2e_compact_cache_hit": True,
        "full_queue_e2e_compute_avoided": True,
        "compact_cache_write_performed": False,
    })
    perf = dict(summary.get("performance_summary", {}))
    perf["total_runtime_ms"] = 0
    perf["reuse_optimization_enabled"] = True
    perf["hotspot_notes"] = _normalize_refs(list(perf.get("hotspot_notes", [])) + ["compact queue E2E summary cache hit avoided full queue E2E compute"])
    summary["performance_summary"] = perf
    summary["writes"] = []
    summary["write_allowed"] = False
    validate_summary(summary)
    return summary


def collect_growth_source_queue_e2e_summary_cache_record(
    *,
    sources: list[str] | None = None,
    write_cache: bool = False,
    clear: bool = False,
    summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    collect_cache_key: Callable[..., dict[str, Any]],
    read_cache: Callable[[str], dict[str, Any]],
    build_payload: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    write_cache_file: Callable[[str, dict[str, Any]], int],
    collect_deep_summary: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    from pathlib import Path as _Path

    cache_key = collect_cache_key(sources=sources)
    path = _Path(cache_key["cache_file_path"])
    if clear and path.exists():
        if path.parent != _Path(cache_key["cache_root"]).expanduser().resolve() and not str(path).startswith("/tmp/"):
            raise ValueError("refusing to clear queue E2E cache outside cache root")
        path.unlink()
    read_result = read_cache(cache_key["cache_file_path"])
    cache_hit = bool(read_result.get("ok")) and read_result.get("payload", {}).get("cache_key") == cache_key["cache_key"]
    invalidation: list[str] = []
    stale: list[str] = []
    compact_summary: dict[str, Any] = {}
    created_at = ""
    cached_size = path.stat().st_size if path.exists() else 0
    write_performed = False
    if cache_hit:
        cached_payload = read_result["payload"]
        compact_summary = cached_payload["compact_queue_e2e_summary"]
        created_at = cached_payload.get("created_at", "")
    elif read_result.get("ok"):
        stale.append("cache key mismatch")
    elif path.exists():
        invalidation.append(read_result.get("error", "cache read failed"))
    if write_cache and not cache_hit:
        if summary is None:
            summary = collect_deep_summary(sources=sources, mode="deep", use_cache=False)
        payload = build_payload(cache_key, summary)
        cached_size = write_cache_file(cache_key["cache_file_path"], payload)
        write_performed = True
        cache_hit = True
        compact_summary = payload["compact_queue_e2e_summary"]
        created_at = payload["created_at"]
    age = _cache_age_seconds(created_at)
    record = {
        "growth_source_queue_e2e_cache_record_version": GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION,
        "growth_source_queue_e2e_cache_record_id": "growth-source-queue-e2e-cache-record-" + _hash_text({"key": cache_key["cache_key"], "hit": cache_hit, "write": write_performed, "version": GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION})[:12],
        "cache_key_id": cache_key["growth_source_queue_e2e_cache_key_id"],
        "cache_key": cache_key["cache_key"],
        "cache_root": cache_key["cache_root"],
        "cache_file_path": cache_key["cache_file_path"],
        "cache_file_exists": path.exists(),
        "cache_valid": cache_hit,
        "cache_hit": cache_hit,
        "cache_write_requested": bool(write_cache),
        "cache_write_performed": write_performed,
        "cache_age_seconds": age,
        "created_at": created_at,
        "source_count": len(cache_key["selected_sources"]),
        "selected_sources": cache_key["selected_sources"],
        "skipped_sources": cache_key["skipped_sources"],
        "compact_queue_e2e_summary": compact_summary,
        "cached_size_bytes": cached_size,
        "invalidation_reasons": _normalize_refs(invalidation),
        "stale_reasons": _normalize_refs(stale),
        "clear_command": "python3 link.py growth source-queue-e2e-cache --clear --json",
        "refresh_command": "python3 link.py growth source-queue-e2e-cache --write-cache --json",
        "recommended_next_action": "Compact queue E2E cache hit; operator reports can reuse it." if cache_hit else "Run growth source-queue-e2e-cache --write-cache --json to populate compact queue E2E cache.",
        "fallback_allowed": False,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": bool(write_cache or clear),
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [cache_key["cache_file_path"]] if write_performed or clear else [],
    }
    validate_growth_source_queue_e2e_summary_cache_record(record)
    return record


def validate_growth_source_queue_e2e_summary_cache_record(payload: dict[str, Any]) -> None:
    required = ("growth_source_queue_e2e_cache_record_version", "growth_source_queue_e2e_cache_record_id", "cache_key_id", "cache_key", "cache_root", "cache_file_path", "cache_file_exists", "cache_valid", "cache_hit", "cache_write_requested", "cache_write_performed", "cache_age_seconds", "created_at", "source_count", "selected_sources", "skipped_sources", "compact_queue_e2e_summary", "cached_size_bytes", "invalidation_reasons", "stale_reasons", "clear_command", "refresh_command", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"growth source queue e2e cache record missing {key}")
    if payload["growth_source_queue_e2e_cache_record_version"] != GROWTH_SOURCE_QUEUE_E2E_CACHE_RECORD_VERSION:
        raise ValueError("invalid growth source queue e2e cache record version")
    if payload["cache_hit"] and not payload["compact_queue_e2e_summary"]:
        raise ValueError("queue E2E cache hit requires compact summary")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth source queue e2e cache record must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["automation_allowed"] is not False:
        raise ValueError("growth source queue e2e cache record must remain deterministic")
    if not payload["write_allowed"] and payload["writes"] != []:
        raise ValueError("queue E2E cache record cannot report writes in read-only mode")


def stable_growth_source_queue_e2e_summary_cache_record_json(payload: dict[str, Any]) -> str:
    validate_growth_source_queue_e2e_summary_cache_record(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_source_queue_e2e_summary_cache_record_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_growth_source_queue_e2e_summary_cache_record(payload)
    return payload
