#!/usr/bin/env python3
"""Deterministic direct-upgrade-eval helpers for Growth.

Extracted from link_growth_console.py. This module owns bounded direct-eval
helper and cache-plan logic only. Full direct-upgrade-eval orchestration and
CLI dispatch remain in link_growth_console.py.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

GROWTH_DIRECT_EVAL_CACHE_PLAN_VERSION = "link-growth-direct-eval-cache-plan-v1"


def _stable_json(value: Any, indent: int | None = None) -> str:
    kwargs: dict[str, Any] = {"sort_keys": True, "default": str}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return json.dumps(value, **kwargs)


def _hash_text(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _source_text(value: Any, *, fallback: str = "not available", max_chars: int = 180) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def _read_only_safety_metadata() -> dict[str, Any]:
    return {
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "writes": [],
    }


def growth_direct_eval_candidate(
    *,
    candidate_id: str,
    source_path: str,
    title: str,
    candidate_type: str,
    direct_value: int,
    friction: int,
    test_speed: int,
    source_specificity: int,
    confidence: int,
    safety: int,
    verification: int,
    maintenance: int,
    evidence: str,
    next_slice: str,
    blocked: bool = False,
    rejection_reason: str = "",
    candidate_source_artifact: str = "direct_eval_summary",
    reused_queue_score: bool = False,
    recompute_reason: str = "",
) -> dict[str, Any]:
    scores = [direct_value, friction, test_speed, source_specificity, confidence, safety, verification]
    direct_value, friction, test_speed, source_specificity, confidence, safety, verification = [
        max(0, min(10, int(item))) for item in scores
    ]
    maintenance = max(0, min(10, int(maintenance)))
    total = max(
        0,
        direct_value * 3
        + friction * 2
        + test_speed
        + source_specificity * 2
        + confidence * 2
        + safety
        + verification * 2
        - maintenance,
    )
    return {
        "candidate_id": candidate_id,
        "source_path": source_path,
        "title": _source_text(title, max_chars=160),
        "candidate_type": candidate_type,
        "direct_growth_functionality_value": direct_value,
        "operator_friction_reduction": friction,
        "test_checkpoint_speed_value": test_speed,
        "source_specificity": source_specificity,
        "implementation_confidence": confidence,
        "safety_score": safety,
        "verification_clarity": verification,
        "expected_maintenance_burden": maintenance,
        "total_roi_score": total,
        "decision": "blocked" if blocked else "needs_more_evidence",
        "rejection_reason": _source_text(rejection_reason, max_chars=180),
        "evidence_summary": _source_text(evidence, max_chars=260),
        "recommended_implementation_slice": _source_text(next_slice, max_chars=240),
        "candidate_source_artifact": candidate_source_artifact,
        "reused_queue_score": bool(reused_queue_score),
        "recompute_reason": _source_text(recompute_reason, max_chars=180),
    }


def rank_growth_direct_eval_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            item["total_roi_score"],
            item["direct_growth_functionality_value"],
            item["source_specificity"],
            item["implementation_confidence"],
            item["title"],
        ),
        reverse=True,
    )
    for index, candidate in enumerate(ranked):
        if candidate["decision"] == "blocked":
            continue
        if index == 0 and candidate["total_roi_score"] >= 60:
            candidate["decision"] = "accept"
            candidate["rejection_reason"] = ""
        elif index <= 3:
            candidate["decision"] = "runner_up"
            candidate["rejection_reason"] = "lower deterministic ROI than the best candidate"
        else:
            candidate["decision"] = "reject"
            candidate["rejection_reason"] = "lower deterministic ROI for this implementation cycle"
    return ranked


def growth_direct_eval_normalized_source_path(source_path: str) -> str:
    return str(source_path or "").strip()


def build_queue_e2e_source_summary_index(queue_e2e: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in queue_e2e.get("source_summaries", []):
        source_path = growth_direct_eval_normalized_source_path(str(item.get("source_path", "")))
        if source_path:
            index[source_path] = item
    return index


def get_queue_e2e_source_summary_for_source(index: dict[str, dict[str, Any]], source_path: str) -> dict[str, Any]:
    return dict(index.get(growth_direct_eval_normalized_source_path(source_path), {}))


def summarize_queue_e2e_source_for_direct_eval(source_path: str, queue_e2e: dict[str, Any]) -> dict[str, Any]:
    index = build_queue_e2e_source_summary_index(queue_e2e)
    item = get_queue_e2e_source_summary_for_source(index, source_path)
    if not item:
        return {
            "reuse_status": "missing_from_queue_e2e",
            "source_path": source_path,
            "reused_fields": [],
            "missing_fields": ["best_growth_opportunity_title", "primary_repo_role", "calibrated_direct_usefulness_score"],
            "summary": {},
        }
    required_fields = (
        "best_growth_opportunity_title",
        "primary_repo_role",
        "primary_repo_role_confidence",
        "calibrated_top_concepts",
        "calibrated_direct_usefulness_score",
        "role_alignment_score",
        "evidence_support_score",
        "safety_risk_score",
        "operator_confidence_score",
    )
    missing = [field for field in required_fields if field not in item]
    reuse_status = "reused_from_queue_e2e" if not missing else "incomplete_queue_e2e_summary"
    return {
        "reuse_status": reuse_status,
        "source_path": source_path,
        "reused_fields": [field for field in required_fields if field in item],
        "missing_fields": missing,
        "summary": item,
    }


def source_inventory_cache_status_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "growth_source_queue_cache_status_id": status.get("growth_source_queue_cache_status_id", ""),
        "cache_root": status.get("cache_root", ""),
        "cache_hit_count": int(status.get("cache_hit_count", 0) or 0),
        "cache_miss_count": int(status.get("cache_miss_count", 0) or 0),
        "stale_count": int(status.get("stale_count", 0) or 0),
        "invalid_count": int(status.get("invalid_count", 0) or 0),
        "queue_ready_for_e2e": bool(status.get("queue_ready_for_e2e", False)),
    }


def collect_growth_direct_eval_cache_plan(
    *,
    sources: list[str] | None = None,
    write_cache_requested: bool = False,
    metadata: dict[str, Any] | None = None,
    collect_queue: Callable[..., dict[str, Any]],
    collect_source_status: Callable[..., dict[str, Any]],
    collect_queue_cache: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    explicit_sources = [str(item).strip() for item in (sources or []) if str(item).strip()]
    queue = collect_queue(sources=explicit_sources or None)
    source_status = collect_source_status(sources=explicit_sources or None)
    queue_cache = collect_queue_cache(sources=explicit_sources or None)
    planned_actions: list[dict[str, Any]] = []
    planned_actions.append({
        "action_type": "observe_source_inventory_cache",
        "source_path": "",
        "reason": "direct-upgrade-eval checks persistent source inventory cache before per-target summaries",
        "command_hint": "python3 link.py growth source-queue-status --json",
    })
    for skipped in queue.get("skipped_sources", []):
        planned_actions.append({
            "action_type": "skip_quarantined_source",
            "source_path": skipped.get("source_path", ""),
            "reason": skipped.get("skip_reason") or skipped.get("quarantine_status") or "source skipped by queue policy",
            "command_hint": "python3 link.py growth source-quarantine --source <source> --json",
        })
    for item in source_status.get("source_statuses", []):
        if item.get("source_path") and not item.get("cache_hit"):
            planned_actions.append({
                "action_type": "warm_source_inventory_cache",
                "source_path": item["source_path"],
                "reason": item.get("recommended_action") or item.get("cache_status") or "source inventory cache is not hot",
                "command_hint": "python3 link.py growth direct-upgrade-eval --write-cache --json",
            })
    planned_actions.append({
        "action_type": "observe_queue_e2e_cache",
        "source_path": "",
        "reason": "direct-upgrade-eval checks the compact queue E2E cache before full queue E2E compute",
        "command_hint": "python3 link.py growth source-queue-e2e-cache-status --json",
    })
    if write_cache_requested or not queue_cache.get("cache_valid"):
        planned_actions.append({
            "action_type": "write_queue_e2e_cache",
            "source_path": "",
            "reason": "compact queue E2E cache is missing or write-cache was requested",
            "command_hint": "python3 link.py growth source-queue-e2e-cache --write-cache --json",
        })
    payload = {
        "growth_direct_eval_cache_plan_version": GROWTH_DIRECT_EVAL_CACHE_PLAN_VERSION,
        "growth_direct_eval_cache_plan_id": "growth-direct-eval-cache-plan-" + _hash_text({
            "queue": queue["growth_source_queue_id"],
            "status": source_status["growth_source_queue_cache_status_id"],
            "queue_cache": queue_cache["growth_source_queue_e2e_cache_record_id"],
            "write": bool(write_cache_requested),
            "version": GROWTH_DIRECT_EVAL_CACHE_PLAN_VERSION,
        })[:12],
        "source_queue_id": queue["growth_source_queue_id"],
        "source_inventory_cache_status_id": source_status["growth_source_queue_cache_status_id"],
        "queue_e2e_cache_status_id": queue_cache["growth_source_queue_e2e_cache_record_id"],
        "write_cache_requested": bool(write_cache_requested),
        "source_inventory_cache_hit_count": source_status["cache_hit_count"],
        "source_inventory_cache_miss_count": source_status["cache_miss_count"],
        "source_inventory_cache_stale_count": source_status["stale_count"],
        "queue_e2e_cache_hit": bool(queue_cache.get("cache_hit", False)),
        "queue_e2e_cache_valid": bool(queue_cache.get("cache_valid", False)),
        "source_inventory_warm_required": bool(source_status["cache_miss_count"] or source_status["stale_count"] or source_status["invalid_count"]),
        "queue_e2e_compact_cache_write_required": bool(write_cache_requested or not queue_cache.get("cache_valid")),
        "planned_cache_actions": planned_actions,
        "skipped_sources": queue["skipped_sources"],
        "recommended_next_action": "Run growth direct-upgrade-eval --write-cache --json to prepare both cache layers." if write_cache_requested or source_status["cache_miss_count"] or not queue_cache.get("cache_valid") else "Both cache layers appear ready for a hot direct-upgrade-eval run.",
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
    validate_growth_direct_eval_cache_plan(payload)
    return payload


def validate_growth_direct_eval_cache_plan(payload: dict[str, Any]) -> None:
    required = (
        "growth_direct_eval_cache_plan_version", "growth_direct_eval_cache_plan_id",
        "source_queue_id", "source_inventory_cache_status_id", "queue_e2e_cache_status_id",
        "write_cache_requested", "source_inventory_cache_hit_count",
        "source_inventory_cache_miss_count", "source_inventory_cache_stale_count",
        "queue_e2e_cache_hit", "queue_e2e_cache_valid", "source_inventory_warm_required",
        "queue_e2e_compact_cache_write_required", "planned_cache_actions", "skipped_sources",
        "recommended_next_action", "fallback_allowed", "model_used", "external_network_used",
        "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes",
    )
    for key in required:
        if key not in payload:
            raise ValueError(f"growth direct eval cache plan missing {key}")
    if payload["growth_direct_eval_cache_plan_version"] != GROWTH_DIRECT_EVAL_CACHE_PLAN_VERSION:
        raise ValueError("invalid growth direct eval cache plan version")
    if not payload["growth_direct_eval_cache_plan_id"].startswith("growth-direct-eval-cache-plan-"):
        raise ValueError("invalid growth direct eval cache plan id")
    for action in payload["planned_cache_actions"]:
        for key in ("action_type", "source_path", "reason", "command_hint"):
            if key not in action:
                raise ValueError(f"growth direct eval cache action missing {key}")
        if action["action_type"] not in {
            "observe_source_inventory_cache",
            "warm_source_inventory_cache",
            "observe_queue_e2e_cache",
            "write_queue_e2e_cache",
            "skip_quarantined_source",
        }:
            raise ValueError("invalid growth direct eval cache action type")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth direct eval cache plan must avoid model/network/fallback")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False:
        raise ValueError("growth direct eval cache plan must remain read-only")
    if payload["writes"] != []:
        raise ValueError("growth direct eval cache plan must not report writes")


def stable_growth_direct_eval_cache_plan_json(payload: dict[str, Any]) -> str:
    validate_growth_direct_eval_cache_plan(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_direct_eval_cache_plan_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_direct_eval_cache_plan(payload)
    return payload
