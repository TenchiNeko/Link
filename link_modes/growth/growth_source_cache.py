#!/usr/bin/env python3
"""Growth source inventory cache subsystem.

Extracted from ``link_modes.growth.link_growth_console`` as a bounded first
non-renderer modularization slice.

This module owns source-cache-specific path, key, policy, manifest, status,
clear, and performance helpers. It must not import the Growth monolith, call
model providers, use external network, mutate research archives, or perform
CLI dispatch. File writes are allowed only through explicit helpers and only
inside configured cache roots.
"""

from __future__ import annotations

from typing import Any, Callable

SOURCE_ARCHIVE_INTAKE_CACHE_KEY_VERSION = "link-source-archive-intake-cache-key-v1"
SOURCE_ARCHIVE_INTAKE_CACHE_VERSION = "link-source-archive-intake-cache-v1"
PERSISTENT_SOURCE_INVENTORY_CACHE_POLICY_VERSION = "link-persistent-source-inventory-cache-policy-v1"
PERSISTENT_SOURCE_INVENTORY_CACHE_MANIFEST_VERSION = "link-persistent-source-inventory-cache-manifest-v1"
PERSISTENT_SOURCE_INVENTORY_CACHE_RECORD_VERSION = "link-persistent-source-inventory-cache-record-v1"
PERSISTENT_SOURCE_CACHE_STATUS_VERSION = "link-persistent-source-cache-status-v1"
PERSISTENT_SOURCE_CACHE_CLEAR_VERSION = "link-persistent-source-cache-clear-v1"
PERSISTENT_SOURCE_CACHE_PERFORMANCE_REPORT_VERSION = "link-persistent-source-cache-performance-report-v1"
PERSISTENT_SOURCE_INVENTORY_COLLECTOR_VERSION = "link-source-inventory-collector-v1"
PERSISTENT_SOURCE_INVENTORY_PROVENANCE_SCHEMA_VERSION = "link-source-provenance-schema-v1"
PERSISTENT_SOURCE_INVENTORY_CACHE_SCHEMA_VERSION = "link-source-inventory-cache-schema-v1"
PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES = 1500000
PERSISTENT_SOURCE_INVENTORY_MAX_SNIPPET_CHARS = 1200


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


def persistent_source_cache_root() -> tuple[str, str]:
    import os as _os
    from pathlib import Path as _Path

    override = str(_os.environ.get("LINK_SOURCE_CACHE_ROOT", "")).strip()
    if override:
        root = _Path(override).expanduser()
        source = "LINK_SOURCE_CACHE_ROOT"
    else:
        root = _Path.home() / ".cache" / "link" / "source_inventory"
        source = "default"
    return str(root), source


def persistent_source_cache_path_is_safe(path_text: str) -> bool:
    from pathlib import Path as _Path

    try:
        path = _Path(path_text).expanduser().resolve()
        repo = _Path.cwd().resolve()
    except Exception:
        return False
    denied = {repo / ".git", repo / ".link"}
    if path == repo or repo in path.parents:
        return False
    for item in denied:
        if path == item or item in path.parents:
            return False
    return True


def persistent_source_cache_file_path(cache_root: str, cache_key: str) -> str:
    from pathlib import Path as _Path
    import re as _re

    safe = _re.sub(r"[^A-Za-z0-9_.-]+", "-", cache_key).strip("-")[:180]
    return str(_Path(cache_root).expanduser() / f"{safe}.json")


def collect_persistent_source_inventory_cache_policy(*, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    cache_root, root_source = persistent_source_cache_root()
    payload = {
        "persistent_source_inventory_cache_policy_version": PERSISTENT_SOURCE_INVENTORY_CACHE_POLICY_VERSION,
        "persistent_source_inventory_cache_policy_id": "persistent-source-inventory-cache-policy-" + _hash_text({"cache_root": cache_root, "version": PERSISTENT_SOURCE_INVENTORY_CACHE_POLICY_VERSION})[:12],
        "cache_enabled_by_default": True,
        "cache_root": cache_root,
        "cache_root_source": root_source,
        "cache_namespace": "source_inventory",
        "cache_version": SOURCE_ARCHIVE_INTAKE_CACHE_VERSION,
        "collector_version": PERSISTENT_SOURCE_INVENTORY_COLLECTOR_VERSION,
        "provenance_schema_version": PERSISTENT_SOURCE_INVENTORY_PROVENANCE_SCHEMA_VERSION,
        "cache_schema_version": PERSISTENT_SOURCE_INVENTORY_CACHE_SCHEMA_VERSION,
        "allowed_payload_types": ["source_inventory_summary", "source_refs", "evidence_refs", "provenance_metadata", "artifact_ids", "bounded_snippets", "concept_summaries"],
        "prohibited_payload_types": ["full_raw_archive_content", "secrets", "credentials", "unbounded_file_blobs", "external_model_responses", "execution_outputs"],
        "max_cached_entry_bytes": PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES,
        "max_cached_snippet_chars": PERSISTENT_SOURCE_INVENTORY_MAX_SNIPPET_CHARS,
        "cache_full_raw_archive_content": False,
        "cache_secrets": False,
        "external_network_allowed": False,
        "model_allowed": False,
        "openrouter_allowed": False,
        "mcp_proxy_allowed": False,
        "invalidation_fields": ["source_path", "source_size_bytes", "source_mtime_ns", "collector_version", "provenance_schema_version", "cache_schema_version", "cache_namespace", "cache_version"],
        "recommended_next_action": "Use --write-cache only after reviewing the manifest; stale or corrupt caches fail closed to request cache.",
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_persistent_source_inventory_cache_policy(payload)
    return payload


def validate_persistent_source_inventory_cache_policy(payload: dict[str, Any]) -> None:
    required = ("persistent_source_inventory_cache_policy_version", "persistent_source_inventory_cache_policy_id", "cache_enabled_by_default", "cache_root", "cache_root_source", "cache_namespace", "cache_version", "collector_version", "provenance_schema_version", "cache_schema_version", "allowed_payload_types", "prohibited_payload_types", "max_cached_entry_bytes", "max_cached_snippet_chars", "cache_full_raw_archive_content", "cache_secrets", "external_network_allowed", "model_allowed", "openrouter_allowed", "mcp_proxy_allowed", "invalidation_fields", "recommended_next_action", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"persistent source cache policy missing field: {key}")
    if payload["persistent_source_inventory_cache_policy_version"] != PERSISTENT_SOURCE_INVENTORY_CACHE_POLICY_VERSION:
        raise ValueError("invalid persistent source cache policy version")
    if not payload["persistent_source_inventory_cache_policy_id"].startswith("persistent-source-inventory-cache-policy-"):
        raise ValueError("invalid persistent source cache policy id")
    if payload["cache_enabled_by_default"] is not True:
        raise ValueError("persistent source cache policy must be enabled by default")
    if payload["cache_root_source"] == "default" and not persistent_source_cache_path_is_safe(payload["cache_root"]):
        raise ValueError("default persistent cache root must be outside repo source")
    for field in ("source_path", "source_size_bytes", "source_mtime_ns", "collector_version", "provenance_schema_version", "cache_schema_version"):
        if field not in payload["invalidation_fields"]:
            raise ValueError(f"persistent source cache policy missing invalidation field {field}")
    if "full_raw_archive_content" not in payload["prohibited_payload_types"] or "secrets" not in payload["prohibited_payload_types"]:
        raise ValueError("persistent source cache policy must prohibit raw archive content and secrets")
    if payload["cache_full_raw_archive_content"] is not False or payload["cache_secrets"] is not False:
        raise ValueError("persistent source cache policy must not cache raw archive content or secrets")
    if payload["external_network_allowed"] is not False or payload["model_allowed"] is not False or payload["openrouter_allowed"] is not False or payload["mcp_proxy_allowed"] is not False:
        raise ValueError("persistent source cache policy must disallow model/network/MCP/proxy")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("persistent source cache policy must remain read-only")


def stable_persistent_source_inventory_cache_policy_json(payload: dict[str, Any]) -> str:
    validate_persistent_source_inventory_cache_policy(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_persistent_source_inventory_cache_policy_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_persistent_source_inventory_cache_policy(payload)
    return payload


def collect_source_archive_intake_cache_key(*, source_path: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    from pathlib import Path as _Path

    source_text = str(source_path or "").strip()
    if not source_text.startswith("research/"):
        raise ValueError("source archive cache key requires --source under research/")
    path = _Path(source_text)
    exists = path.exists()
    if not exists:
        raise ValueError(f"source archive cache key source does not exist: {source_text}")
    size = path.stat().st_size
    mtime_ns = path.stat().st_mtime_ns
    if path.is_dir():
        source_type = "folder"
    elif path.suffix.lower() == ".zip":
        source_type = "zip_archive"
    else:
        source_type = "file"
    source_name = path.name
    fingerprint = _hash_text({
        "source_path": source_text,
        "source_name": source_name,
        "source_type": source_type,
        "source_size_bytes": size,
        "source_mtime_ns": mtime_ns,
        "version": SOURCE_ARCHIVE_INTAKE_CACHE_KEY_VERSION,
    })[:16]
    cache_key = f"source-archive-intake:{SOURCE_ARCHIVE_INTAKE_CACHE_VERSION}:{fingerprint}"
    payload = {
        "source_archive_intake_cache_key_version": SOURCE_ARCHIVE_INTAKE_CACHE_KEY_VERSION,
        "source_archive_intake_cache_key_id": "source-archive-intake-cache-key-" + fingerprint[:12],
        "source_path": source_text,
        "source_name": source_name,
        "source_type": source_type,
        "source_exists": True,
        "source_size_bytes": int(size),
        "source_mtime_ns": int(mtime_ns),
        "source_fingerprint": fingerprint,
        "cache_namespace": "source_archive_intake",
        "cache_version": SOURCE_ARCHIVE_INTAKE_CACHE_VERSION,
        "cache_key": cache_key,
        "cache_scope": "request",
        "persistent_cache_allowed": False,
        "invalidation_reasons": _normalize_refs(["source path", "source size", "source mtime", "collector version"]),
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
    validate_source_archive_intake_cache_key(payload)
    return payload


def validate_source_archive_intake_cache_key(payload: dict[str, Any]) -> None:
    required = (
        "source_archive_intake_cache_key_version", "source_archive_intake_cache_key_id", "source_path",
        "source_name", "source_type", "source_exists", "source_size_bytes", "source_mtime_ns",
        "source_fingerprint", "cache_namespace", "cache_version", "cache_key", "cache_scope",
        "persistent_cache_allowed", "invalidation_reasons", "fallback_allowed", "model_used",
        "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes",
    )
    for key in required:
        if key not in payload:
            raise ValueError(f"source archive cache key missing field: {key}")
    if payload["source_archive_intake_cache_key_version"] != SOURCE_ARCHIVE_INTAKE_CACHE_KEY_VERSION:
        raise ValueError("invalid source archive cache key version")
    if not payload["source_archive_intake_cache_key_id"].startswith("source-archive-intake-cache-key-"):
        raise ValueError("invalid source archive cache key id")
    if not payload["source_path"].startswith("research/") or payload["source_exists"] is not True:
        raise ValueError("source archive cache key requires an existing research source")
    if payload["cache_scope"] != "request" or payload["persistent_cache_allowed"] is not False:
        raise ValueError("source archive cache key must be request-scoped only")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("source archive cache key must be deterministic with no fallback/model/network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("source archive cache key must remain read-only")


def stable_source_archive_intake_cache_key_json(payload: dict[str, Any]) -> str:
    validate_source_archive_intake_cache_key(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_source_archive_intake_cache_key_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_source_archive_intake_cache_key(payload)
    return payload


def read_persistent_source_inventory_cache(
    cache_file_path: str,
    *,
    validate_payload: Callable[[dict[str, Any]], None] | None = None,
    error_formatter: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    import json as _json
    from pathlib import Path as _Path

    try:
        path = _Path(cache_file_path)
        if not path.exists():
            return {"ok": False, "error": "cache file missing"}
        payload = _json.loads(path.read_text())
        if validate_payload is not None:
            validate_payload(payload)
        else:
            validate_persistent_source_inventory_cache_payload(payload)
        return {"ok": True, "payload": payload}
    except Exception as exc:
        text = str(exc)
        return {"ok": False, "error": error_formatter(text) if error_formatter else _short_text(text, max_chars=220)}


def validate_persistent_source_inventory_cache_payload(payload: dict[str, Any]) -> None:
    required = ("persistent_source_inventory_cache_payload_version", "cache_key", "source_path", "collector_version", "provenance_schema_version", "cache_schema_version", "created_at", "source_cache", "artifacts")
    for key in required:
        if key not in payload:
            raise ValueError(f"persistent source cache payload missing field: {key}")
    if payload["persistent_source_inventory_cache_payload_version"] != PERSISTENT_SOURCE_INVENTORY_CACHE_RECORD_VERSION:
        raise ValueError("invalid persistent source cache payload version")
    if not str(payload["source_path"]).startswith("research/"):
        raise ValueError("persistent source cache payload must be source-bound")
    if payload["collector_version"] != PERSISTENT_SOURCE_INVENTORY_COLLECTOR_VERSION or payload["cache_schema_version"] != PERSISTENT_SOURCE_INVENTORY_CACHE_SCHEMA_VERSION:
        raise ValueError("persistent source cache payload version mismatch")
    text = _stable_json(payload)
    if len(text.encode("utf-8")) > PERSISTENT_SOURCE_INVENTORY_MAX_ENTRY_BYTES:
        raise ValueError("persistent source cache payload exceeds max cached entry bytes")
    forbidden = ("BEGIN PRIVATE KEY", "AWS_SECRET", "OPENROUTER_API_KEY", "password=", "token=")
    if any(item.lower() in text.lower() for item in forbidden):
        raise ValueError("persistent source cache payload appears to contain secret-like content")


def collect_persistent_source_inventory_cache_manifest(
    *,
    source_path: str,
    metadata: dict[str, Any] | None = None,
    collect_policy: Callable[..., dict[str, Any]] = collect_persistent_source_inventory_cache_policy,
    collect_key: Callable[..., dict[str, Any]] = collect_source_archive_intake_cache_key,
    read_cache: Callable[[str], dict[str, Any]] = read_persistent_source_inventory_cache,
) -> dict[str, Any]:
    from pathlib import Path as _Path

    policy = collect_policy()
    key_payload = collect_key(source_path=source_path)
    source_fingerprint = _hash_text({
        "source_path": key_payload["source_path"],
        "source_size_bytes": key_payload["source_size_bytes"],
        "source_mtime_ns": key_payload["source_mtime_ns"],
        "collector_version": policy["collector_version"],
        "provenance_schema_version": policy["provenance_schema_version"],
        "cache_schema_version": policy["cache_schema_version"],
        "cache_namespace": policy["cache_namespace"],
        "cache_version": policy["cache_version"],
    })[:16]
    cache_key = f"{policy['cache_namespace']}:{policy['cache_version']}:{source_fingerprint}"
    cache_file_path = persistent_source_cache_file_path(policy["cache_root"], cache_key)
    cache_file_exists = _Path(cache_file_path).exists()
    invalidation: list[str] = []
    cache_valid = False
    cache_status = "missing"
    if cache_file_exists:
        record = read_cache(cache_file_path)
        if record.get("ok"):
            raw = record["payload"]
            if raw.get("cache_key") == cache_key and raw.get("collector_version") == policy["collector_version"] and raw.get("cache_schema_version") == policy["cache_schema_version"]:
                cache_valid = True
                cache_status = "valid"
            else:
                cache_status = "stale"
                invalidation.append("cache metadata does not match current manifest")
        else:
            cache_status = "corrupt"
            invalidation.append(record.get("error", "cache could not be read"))
    payload = {
        "persistent_source_inventory_cache_manifest_version": PERSISTENT_SOURCE_INVENTORY_CACHE_MANIFEST_VERSION,
        "persistent_source_inventory_cache_manifest_id": "persistent-source-inventory-cache-manifest-" + source_fingerprint[:12],
        "policy_id": policy["persistent_source_inventory_cache_policy_id"],
        "source_path": key_payload["source_path"],
        "source_name": key_payload["source_name"],
        "source_type": key_payload["source_type"],
        "source_exists": key_payload["source_exists"],
        "source_size_bytes": key_payload["source_size_bytes"],
        "source_mtime_ns": key_payload["source_mtime_ns"],
        "source_fingerprint": source_fingerprint,
        "cache_key": cache_key,
        "cache_file_path": cache_file_path,
        "cache_file_exists": cache_file_exists,
        "cache_status": cache_status,
        "invalidation_reasons": _normalize_refs(invalidation),
        "cache_valid": cache_valid,
        "collector_version": policy["collector_version"],
        "provenance_schema_version": policy["provenance_schema_version"],
        "cache_schema_version": policy["cache_schema_version"],
        "cache_namespace": policy["cache_namespace"],
        "recommended_next_action": "Persistent cache is valid." if cache_valid else "Run source-cache-persistent --write-cache to create or refresh the source inventory cache.",
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
    validate_persistent_source_inventory_cache_manifest(payload)
    return payload


def validate_persistent_source_inventory_cache_manifest(payload: dict[str, Any]) -> None:
    required = ("persistent_source_inventory_cache_manifest_version", "persistent_source_inventory_cache_manifest_id", "policy_id", "source_path", "source_name", "source_type", "source_exists", "source_size_bytes", "source_mtime_ns", "source_fingerprint", "cache_key", "cache_file_path", "cache_file_exists", "cache_status", "invalidation_reasons", "cache_valid", "collector_version", "provenance_schema_version", "cache_schema_version", "cache_namespace", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"persistent source cache manifest missing field: {key}")
    if payload["persistent_source_inventory_cache_manifest_version"] != PERSISTENT_SOURCE_INVENTORY_CACHE_MANIFEST_VERSION:
        raise ValueError("invalid persistent source cache manifest version")
    if payload["cache_status"] not in {"missing", "valid", "stale", "corrupt"}:
        raise ValueError("invalid persistent source cache status")
    if not payload["source_path"].startswith("research/") or payload["source_exists"] is not True:
        raise ValueError("persistent source cache manifest requires existing research source")
    if payload["cache_file_path"].endswith(".json") is not True:
        raise ValueError("persistent source cache file must be JSON")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("persistent source cache manifest must not use fallback/model/network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("persistent source cache manifest must remain read-only")


def stable_persistent_source_inventory_cache_manifest_json(payload: dict[str, Any]) -> str:
    validate_persistent_source_inventory_cache_manifest(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_persistent_source_inventory_cache_manifest_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_persistent_source_inventory_cache_manifest(payload)
    return payload


def collect_source_cache_status(
    *,
    source_path: str,
    metadata: dict[str, Any] | None = None,
    collect_manifest: Callable[..., dict[str, Any]] = collect_persistent_source_inventory_cache_manifest,
    read_cache: Callable[[str], dict[str, Any]] = read_persistent_source_inventory_cache,
) -> dict[str, Any]:
    from pathlib import Path as _Path

    manifest = collect_manifest(source_path=source_path)
    size = _Path(manifest["cache_file_path"]).stat().st_size if _Path(manifest["cache_file_path"]).exists() else 0
    created = ""
    read_result = read_cache(manifest["cache_file_path"])
    if read_result.get("ok"):
        created = read_result["payload"].get("created_at", "")
    payload = {
        "source_cache_status_version": PERSISTENT_SOURCE_CACHE_STATUS_VERSION,
        "source_cache_status_id": "source-cache-status-" + _hash_text({"manifest_id": manifest["persistent_source_inventory_cache_manifest_id"], "status": manifest["cache_status"], "version": PERSISTENT_SOURCE_CACHE_STATUS_VERSION})[:12],
        "source_path": manifest["source_path"],
        "manifest_id": manifest["persistent_source_inventory_cache_manifest_id"],
        "cache_file_exists": manifest["cache_file_exists"],
        "cache_valid": manifest["cache_valid"],
        "cache_hit": manifest["cache_valid"],
        "cached_size_bytes": size,
        "created_at": created,
        "invalidation_reasons": manifest["invalidation_reasons"],
        "recommended_next_action": manifest["recommended_next_action"],
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_source_cache_status(payload)
    return payload


def validate_source_cache_status(payload: dict[str, Any]) -> None:
    required = ("source_cache_status_version", "source_cache_status_id", "source_path", "manifest_id", "cache_file_exists", "cache_valid", "cache_hit", "cached_size_bytes", "created_at", "invalidation_reasons", "recommended_next_action", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"source cache status missing field: {key}")
    if payload["source_cache_status_version"] != PERSISTENT_SOURCE_CACHE_STATUS_VERSION:
        raise ValueError("invalid source cache status version")
    if not payload["source_cache_status_id"].startswith("source-cache-status-"):
        raise ValueError("invalid source cache status id")
    if not payload["source_path"].startswith("research/"):
        raise ValueError("source cache status must be source-bound")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("source cache status must be read-only")


def stable_source_cache_status_json(payload: dict[str, Any]) -> str:
    validate_source_cache_status(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_source_cache_status_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_source_cache_status(payload)
    return payload


def collect_source_cache_clear(
    *,
    source_path: str | None = None,
    clear_all: bool = False,
    metadata: dict[str, Any] | None = None,
    collect_policy: Callable[..., dict[str, Any]] = collect_persistent_source_inventory_cache_policy,
    collect_manifest: Callable[..., dict[str, Any]] = collect_persistent_source_inventory_cache_manifest,
) -> dict[str, Any]:
    from pathlib import Path as _Path

    policy = collect_policy()
    root = _Path(policy["cache_root"]).expanduser().resolve()
    if not str(root).startswith("/tmp/") and not persistent_source_cache_path_is_safe(str(root)):
        raise ValueError("refusing unsafe persistent cache root")
    files: list[str] = []
    scope = "all" if clear_all else "source"
    if clear_all:
        if root.exists():
            for item in sorted(root.glob("*.json")):
                if item.is_file() and item.parent == root:
                    item.unlink()
                    files.append(str(item))
    else:
        if not source_path:
            raise ValueError("source-cache-clear requires --source or --all")
        manifest = collect_manifest(source_path=source_path)
        path = _Path(manifest["cache_file_path"]).expanduser().resolve()
        if path.exists() and path.parent == root:
            path.unlink()
            files.append(str(path))
    payload = {
        "source_cache_clear_version": PERSISTENT_SOURCE_CACHE_CLEAR_VERSION,
        "source_cache_clear_id": "source-cache-clear-" + _hash_text({"scope": scope, "files": files, "version": PERSISTENT_SOURCE_CACHE_CLEAR_VERSION})[:12],
        "clear_scope": scope,
        "source_path": source_path or "",
        "cache_root": str(root),
        "files_removed": files,
        "removed_count": len(files),
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": True,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": files,
    }
    validate_source_cache_clear(payload)
    return payload


def validate_source_cache_clear(payload: dict[str, Any]) -> None:
    required = ("source_cache_clear_version", "source_cache_clear_id", "clear_scope", "source_path", "cache_root", "files_removed", "removed_count", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"source cache clear missing field: {key}")
    if payload["source_cache_clear_version"] != PERSISTENT_SOURCE_CACHE_CLEAR_VERSION:
        raise ValueError("invalid source cache clear version")
    if payload["clear_scope"] not in {"source", "all"}:
        raise ValueError("invalid source cache clear scope")
    if payload["removed_count"] != len(payload["files_removed"]):
        raise ValueError("source cache clear removed count mismatch")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not True or payload["automation_allowed"] is not False:
        raise ValueError("source cache clear must remain bounded and explicit")


def stable_source_cache_clear_json(payload: dict[str, Any]) -> str:
    validate_source_cache_clear(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_source_cache_clear_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_source_cache_clear(payload)
    return payload


def collect_persistent_source_cache_performance_report(
    *,
    source_path: str,
    metadata: dict[str, Any] | None = None,
    collect_status: Callable[..., dict[str, Any]] = collect_source_cache_status,
) -> dict[str, Any]:
    status = collect_status(source_path=source_path)
    payload = {
        "persistent_source_cache_performance_report_version": PERSISTENT_SOURCE_CACHE_PERFORMANCE_REPORT_VERSION,
        "persistent_source_cache_performance_report_id": "persistent-source-cache-performance-report-" + _hash_text({"status_id": status["source_cache_status_id"], "version": PERSISTENT_SOURCE_CACHE_PERFORMANCE_REPORT_VERSION})[:12],
        "source_path": status["source_path"],
        "persistent_cache_status_id": status["source_cache_status_id"],
        "cache_hit": status["cache_hit"],
        "expected_rebuilds_avoided": _normalize_refs(["target_intake archive walk", "target_evidence rebuild", "archive_concepts rebuild", "target_upgrades rebuild", "operator dashboard source context rebuild"] if status["cache_hit"] else []),
        "remaining_rebuild_hotspots": _normalize_refs(["first cache write still computes target_intake", "separate commands still parse final compact JSON", "persistent invalidation depends on source size and mtime"]),
        "slowest_artifacts": [],
        "recommendation": "Persistent cache hit; use e2e-summary/dashboard/target-command normally." if status["cache_hit"] else "Run source-cache-persistent --write-cache to populate the cache before repeated CLI runs.",
        "fallback_allowed": False,
        "model_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_persistent_source_cache_performance_report(payload)
    return payload


def validate_persistent_source_cache_performance_report(payload: dict[str, Any]) -> None:
    required = ("persistent_source_cache_performance_report_version", "persistent_source_cache_performance_report_id", "source_path", "persistent_cache_status_id", "cache_hit", "expected_rebuilds_avoided", "remaining_rebuild_hotspots", "slowest_artifacts", "recommendation", "fallback_allowed", "model_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"persistent source cache performance report missing field: {key}")
    if payload["persistent_source_cache_performance_report_version"] != PERSISTENT_SOURCE_CACHE_PERFORMANCE_REPORT_VERSION:
        raise ValueError("invalid persistent cache performance report version")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False:
        raise ValueError("persistent cache performance report must be no-model/no-fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("persistent cache performance report must remain read-only")


def stable_persistent_source_cache_performance_report_json(payload: dict[str, Any]) -> str:
    validate_persistent_source_cache_performance_report(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_persistent_source_cache_performance_report_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_persistent_source_cache_performance_report(payload)
    return payload
