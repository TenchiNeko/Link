#!/usr/bin/env python3
"""Deterministic operator cache dashboard helpers for Growth.

Extracted from link_growth_console.py. This module owns bounded dashboard
payload/status helper logic only; collectors and CLI dispatch stay in the
Growth monolith.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash_text(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def normalize_implementation_branch_refs(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = [values]
    elif isinstance(values, (list, tuple, set)):
        raw = list(values)
    else:
        raw = [values]
    normalized: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def operator_cache_dashboard_source_inventory_summary(status: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    total_size = 0
    ages: list[int] = []
    for item in status.get("source_statuses", []):
        age = item.get("cache_age_seconds")
        if isinstance(age, int):
            ages.append(age)
        total_size += int(item.get("cached_size_bytes", 0) or 0)
        action_required = "none" if item.get("cache_hit") else "warm_source_inventory_cache"
        sources.append({
            "source_path": item.get("source_path", ""),
            "source_name": str(item.get("source_path", "")).rsplit("/", 1)[-1],
            "suitability_status": item.get("suitability_status", "unknown"),
            "quarantine_status": item.get("quarantine_status", "unknown"),
            "cache_status": item.get("cache_status", "unknown"),
            "cache_hit": bool(item.get("cache_hit", False)),
            "cache_valid": bool(item.get("cache_valid", False)),
            "cache_age_seconds": age,
            "cached_size_bytes": int(item.get("cached_size_bytes", 0) or 0),
            "invalidation_reasons": normalize_implementation_branch_refs(list(item.get("invalidation_reasons", []))),
            "stale_reasons": normalize_implementation_branch_refs(list(item.get("stale_reasons", []))),
            "action_required": action_required,
            "refresh_command": f"python3 link.py growth source-cache-persistent --source {item.get('source_path', '')} --write-cache --json",
            "clear_command": f"python3 link.py growth source-cache-clear --source {item.get('source_path', '')} --json",
        })
    skipped_count = int(queue.get("skipped_source_count", 0) or 0)
    ready_count = sum(1 for item in sources if item["cache_hit"] and item["cache_valid"])
    source_count = len(sources)
    ready = source_count > 0 and ready_count == source_count
    return {
        "cache_root": status.get("cache_root", ""),
        "source_count": source_count,
        "hit_count": int(status.get("cache_hit_count", 0) or 0),
        "miss_count": int(status.get("cache_miss_count", 0) or 0),
        "stale_count": int(status.get("stale_count", 0) or 0),
        "invalid_count": int(status.get("invalid_count", 0) or 0),
        "skipped_count": skipped_count,
        "ready_count": ready_count,
        "ready_for_hot_path": ready,
        "total_cached_size_bytes": total_size,
        "oldest_cache_age_seconds": max(ages) if ages else None,
        "newest_cache_age_seconds": min(ages) if ages else None,
        "sources": sources,
        "refresh_command": "python3 link.py growth source-queue-warm --write-cache --json",
        "clear_command": "python3 link.py growth source-cache-clear --all --json",
        "recommended_next_action": "Source inventory cache is hot for all selected sources." if ready else "Run growth source-queue-warm --write-cache --json to warm selected source inventory caches.",
    }


def operator_cache_dashboard_queue_e2e_summary(record: dict[str, Any]) -> dict[str, Any]:
    compact = record.get("compact_queue_e2e_summary", {}) if record.get("cache_hit") else {}
    best = compact.get("best_overall_opportunity", {}) if isinstance(compact, dict) else {}
    quality = compact.get("calibration_quality_score") if isinstance(compact, dict) else None
    if quality is None and isinstance(compact, dict):
        quality = compact.get("operator_decision_summary", {}).get("calibration_quality_score")
    if record.get("cache_hit"):
        source = "compact_cache"
    elif record.get("cache_file_exists") and record.get("invalidation_reasons"):
        source = "invalid"
    elif record.get("cache_file_exists"):
        source = "stale"
    else:
        source = "missing"
    return {
        "cache_key_id": record.get("cache_key_id", ""),
        "cache_record_id": record.get("growth_source_queue_e2e_cache_record_id", ""),
        "cache_root": record.get("cache_root", ""),
        "cache_file_path": record.get("cache_file_path", ""),
        "cache_file_exists": bool(record.get("cache_file_exists", False)),
        "cache_hit": bool(record.get("cache_hit", False)),
        "cache_valid": bool(record.get("cache_valid", False)),
        "cache_age_seconds": record.get("cache_age_seconds"),
        "cached_size_bytes": int(record.get("cached_size_bytes", 0) or 0),
        "selected_source_count": int(record.get("source_count", 0) or 0),
        "skipped_source_count": len(record.get("skipped_sources", [])),
        "summary_source": source,
        "best_cached_opportunity_title": str(best.get("title") or ""),
        "calibration_quality_score": quality,
        "invalidation_reasons": normalize_implementation_branch_refs(list(record.get("invalidation_reasons", []))),
        "stale_reasons": normalize_implementation_branch_refs(list(record.get("stale_reasons", []))),
        "ready_for_fast_queue_e2e": bool(record.get("cache_hit") and record.get("cache_valid")),
        "refresh_command": record.get("refresh_command", "python3 link.py growth source-queue-e2e-cache --write-cache --json"),
        "clear_command": record.get("clear_command", "python3 link.py growth source-queue-e2e-cache --clear --json"),
        "recommended_next_action": record.get("recommended_next_action", "Run growth source-queue-e2e-cache --write-cache --json to populate compact queue E2E cache."),
    }


def operator_cache_dashboard_command_hints() -> dict[str, str]:
    return {
        "inspect_dashboard": "python3 link.py growth operator-cache-dashboard --json",
        "warm_source_inventory": "python3 link.py growth source-queue-warm --write-cache --json",
        "write_queue_e2e_cache": "python3 link.py growth source-queue-e2e-cache --write-cache --json",
        "warm_full_hot_path": "python3 link.py growth direct-upgrade-eval --write-cache --json",
        "run_direct_upgrade_eval_hot": "python3 link.py growth direct-upgrade-eval --json",
        "run_concept_calibration_fast": "python3 link.py growth concept-calibration-report --mode fast --json",
        "run_queue_e2e_fast": "python3 link.py growth source-queue-e2e --mode fast --json",
        "clear_source_inventory_cache": "python3 link.py growth source-cache-clear --all --json",
        "clear_queue_e2e_cache": "python3 link.py growth source-queue-e2e-cache --clear --json",
        "run_deep_verification": "python3 tests/test_growth_pipeline.py --suite planning-deterministic",
    }


def operator_cache_dashboard_issues(
    source_summary: dict[str, Any],
    queue_summary: dict[str, Any],
    queue: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if source_summary["miss_count"] or source_summary["stale_count"] or source_summary["invalid_count"]:
        issues.append({
            "issue_id": "source_inventory_cache_missing",
            "severity": "high" if source_summary["hit_count"] == 0 else "medium",
            "category": "cache",
            "title": "Source inventory cache is not fully hot",
            "observed_behavior": f"{source_summary['hit_count']} hits, {source_summary['miss_count']} misses, {source_summary['stale_count']} stale, {source_summary['invalid_count']} invalid.",
            "expected_behavior": "All suitable selected sources should have valid source inventory cache entries before repeated operator reports.",
            "recommended_fix": source_summary["refresh_command"],
            "evidence_scope": "current_dashboard",
            "implement_now_candidate": False,
        })
    if not queue_summary["cache_hit"]:
        issues.append({
            "issue_id": "queue_e2e_compact_cache_missing",
            "severity": "high",
            "category": "cache",
            "title": "Compact queue E2E summary cache is not ready",
            "observed_behavior": f"Queue E2E compact cache status is {queue_summary['summary_source']}.",
            "expected_behavior": "A valid compact queue E2E cache should exist before hot direct-upgrade-eval and concept-calibration-report fast runs.",
            "recommended_fix": queue_summary["refresh_command"],
            "evidence_scope": "current_dashboard",
            "implement_now_candidate": False,
        })
    for item in queue.get("quarantine_records", []):
        if item.get("quarantine_status") != "not_quarantined":
            issues.append({
                "issue_id": "activepieces_quarantined" if item.get("source_path", "").endswith("activepieces-main.zip") else "source_quarantined_" + _hash_text(item.get("source_path", ""))[:8],
                "severity": "medium",
                "category": "queue",
                "title": f"{item.get('source_path', 'source')} is quarantined",
                "observed_behavior": item.get("quarantine_reason") or item.get("failure_category") or "source is excluded from default queue",
                "expected_behavior": "Unsuitable optional sources should be skipped without breaking the operator cache dashboard.",
                "recommended_fix": item.get("recommended_fix") or "Keep skipped until deterministic suitability is fixed.",
                "evidence_scope": "current_dashboard",
                "implement_now_candidate": False,
            })
    quality = queue_summary.get("calibration_quality_score")
    if isinstance(quality, int | float) and quality < 70:
        issues.append({
            "issue_id": "calibration_quality_weak",
            "severity": "medium",
            "category": "idea_quality",
            "title": "Cached calibration quality remains weak",
            "observed_behavior": f"Cached calibration quality score is {quality}.",
            "expected_behavior": "Role/concept calibration should expose weak sources and avoid overconfident ideas.",
            "recommended_fix": "Review concept-calibration-report --mode fast output and add source-specific fixtures in a separate batch.",
            "evidence_scope": "cached_summary",
            "implement_now_candidate": False,
        })
    issues.append({
        "issue_id": "planning_extended_checkpoint_current_observed",
        "severity": "low",
        "category": "test_coverage",
        "title": "planning-fast umbrella coverage is split from normal base",
        "observed_behavior": "Current normal base runs foundation-fast, planning-core, and execution-fast; broader planning-fast coverage remains explicit through planning-fast/planning-extended.",
        "expected_behavior": "Normal checkpoint tiers should remain small enough for frequent use while deep planning/execution coverage stays explicit.",
        "recommended_fix": "Use planning-core for normal checkpoints and run planning-fast or planning-extended when broader deterministic planning coverage is needed.",
        "evidence_scope": "prior_observed",
        "implement_now_candidate": False,
    })
    return issues
