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

from link_modes.growth.growth_schema_helpers import normalize_implementation_branch_refs

GROWTH_DIRECT_EVAL_CACHE_PLAN_VERSION = "link-growth-direct-eval-cache-plan-v1"
GROWTH_DIRECT_UPGRADE_EVAL_VERSION = "link-growth-direct-upgrade-eval-v1"


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


def growth_direct_eval_issue(
    issue_id: str,
    severity: str,
    category: str,
    title: str,
    observed: str,
    expected: str,
    evidence: str,
    fix: str,
    *,
    implement_now: bool = False,
    blocked_reason: str = "",
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "severity": severity,
        "category": category,
        "title": _source_text(title, max_chars=140),
        "observed_behavior": _source_text(observed, max_chars=240),
        "expected_behavior": _source_text(expected, max_chars=220),
        "evidence_summary": _source_text(evidence, max_chars=240),
        "recommended_fix": _source_text(fix, max_chars=220),
        "implement_now_candidate": bool(implement_now),
        "blocked_reason": _source_text(blocked_reason, max_chars=180),
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


def growth_direct_eval_per_target_summary(
    source_path: str,
    queue: dict[str, Any],
    status: dict[str, Any],
    queue_e2e: dict[str, Any],
    *,
    collect_summary: Callable[..., dict[str, Any]],
    collect_score: Callable[..., dict[str, Any]],
    get_or_collect_cache: Callable[..., tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    source_entry = next((item for item in queue["selected_sources"] if item["source_path"] == source_path), {})
    source_status = next((item for item in status["source_statuses"] if item["source_path"] == source_path), {})
    queue_summary = summarize_queue_e2e_source_for_direct_eval(source_path, queue_e2e)
    e2e_item = dict(queue_summary.get("summary", {}))
    recomputed_fields: list[str] = []
    reuse_warnings: list[str] = []
    archive_touch_required = False
    archive_touch_reason = ""
    cache: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    if queue_summary["reuse_status"] == "missing_from_queue_e2e":
        archive_touch_required = True
        archive_touch_reason = "queue E2E summary did not include this selected source"
        summary = collect_summary(source_path=source_path)
        score = collect_score(source_path=source_path, summary=summary)
        best_title = summary["best_growth_opportunity"]["title"]
        e2e_item = {
            "best_growth_opportunity_title": best_title,
            "calibrated_best_opportunity": best_title,
            "primary_repo_role": "unknown",
            "primary_repo_role_confidence": "low",
            "calibrated_top_concepts": [],
            "calibrated_direct_usefulness_score": score["calibrated_direct_usefulness_score"],
            "role_alignment_score": score["role_alignment_score"],
            "evidence_support_score": score["evidence_support_score"],
            "safety_risk_score": score["safety_risk_score"],
            "operator_confidence_score": score["operator_confidence_score"],
            "recommended_next_action": score["recommended_next_action"],
            "cache_status": source_status.get("cache_status", "miss"),
        }
        recomputed_fields.extend(["e2e_summary", "opportunity_score"])
    elif queue_summary["reuse_status"] == "incomplete_queue_e2e_summary":
        reuse_warnings.append("queue E2E summary was reused with missing optional direct-eval fields")
    if archive_touch_required:
        cache, artifacts = get_or_collect_cache(source_path)
    profile = artifacts.get("compression_profile", {})
    task = artifacts.get("operator_task_draft", {})
    best_title = str(e2e_item.get("best_growth_opportunity_title") or e2e_item.get("calibrated_best_opportunity") or "unavailable")
    task_title = str(task.get("calibrated_best_growth_opportunity") or task.get("objective") or best_title)
    dashboard_title = best_title
    e2e_title = best_title
    divergence = []
    if archive_touch_required and task_title and task_title != e2e_title and e2e_title not in task_title:
        divergence.append(f"task draft title differs from E2E best: {task_title}")
    if archive_touch_required:
        task_alignment_source = str(task.get("task_alignment_source") or ("calibrated_task_candidate" if not divergence else "diverged"))
    elif queue_e2e.get("queue_e2e_cache_used"):
        task_alignment_source = "queue_e2e_compact_cache"
    else:
        task_alignment_source = "queue_e2e_source_summary"
    task_alignment_warnings = normalize_implementation_branch_refs(list(task.get("task_alignment_warnings", [])) + divergence)
    reused_fields = list(queue_summary.get("reused_fields", []))
    if archive_touch_required:
        reused_fields.extend(["source_archive_intake_request_cache", "compression_profile", "operator_task_draft"])
    else:
        reused_fields.extend(["source_queue_status", "queue_e2e_per_target_summary"])
    missing_fields = list(queue_summary.get("missing_fields", []))
    if queue_e2e.get("queue_e2e_cache_used") and not archive_touch_required:
        summary_reuse_source = "queue_e2e_compact_cache"
    elif not archive_touch_required:
        summary_reuse_source = "queue_e2e_computed"
    else:
        summary_reuse_source = "mixed"
    if queue_summary["reuse_status"] == "incomplete_queue_e2e_summary":
        summary_reuse_source = "mixed" if archive_touch_required else summary_reuse_source
    if queue_summary["reuse_status"] == "missing_from_queue_e2e":
        summary_reuse_source = "recomputed"
    primary_role = e2e_item.get("primary_repo_role", "unknown")
    if profile:
        compression_decision = profile.get("compression_profile_decision", "insufficient_evidence")
    elif primary_role == "compression_context":
        compression_decision = "compression_repo"
    elif primary_role == "unknown":
        compression_decision = "insufficient_evidence"
    else:
        compression_decision = "not_compression_repo"
    source_inventory_cache_hit = bool(source_status.get("cache_hit", False))
    source_inventory_cache_used = source_inventory_cache_hit and not archive_touch_required
    archive_recompute_avoided = not archive_touch_required and queue_summary["reuse_status"] in {"reused_from_queue_e2e", "incomplete_queue_e2e_summary"}
    return {
        "source_path": source_path,
        "source_name": source_entry.get("source_name", source_path.rsplit("/", 1)[-1]),
        "suitability_status": source_entry.get("suitability_status", "suitable"),
        "quarantine_status": source_entry.get("quarantine_status", "not_quarantined"),
        "cache_status": source_status.get("cache_status", e2e_item.get("cache_status", "miss")),
        "primary_repo_role": primary_role,
        "primary_repo_role_confidence": e2e_item.get("primary_repo_role_confidence", "low"),
        "calibrated_top_concepts": e2e_item.get("calibrated_top_concepts", [])[:5],
        "compression_profile_decision": compression_decision,
        "best_growth_opportunity_title": best_title,
        "calibrated_direct_usefulness_score": e2e_item.get("calibrated_direct_usefulness_score", 0),
        "role_alignment_score": e2e_item.get("role_alignment_score", 0),
        "evidence_support_score": e2e_item.get("evidence_support_score", 0),
        "safety_risk_score": e2e_item.get("safety_risk_score", 10),
        "operator_confidence_score": e2e_item.get("operator_confidence_score", 0),
        "task_draft_title": task_title,
        "task_alignment_source": task_alignment_source,
        "task_alignment_warnings": task_alignment_warnings,
        "dashboard_best_opportunity_title": dashboard_title,
        "e2e_best_opportunity_title": e2e_title,
        "divergence_warnings": normalize_implementation_branch_refs(divergence),
        "source_archive_intake_cache_id": cache.get("source_archive_intake_cache_id", ""),
        "source_inventory_cache_hit": source_inventory_cache_hit,
        "source_inventory_cache_used": source_inventory_cache_used,
        "source_inventory_cache_record_id": source_status.get("cache_observability_card_id", ""),
        "archive_touch_required": archive_touch_required,
        "archive_touch_reason": archive_touch_reason,
        "per_target_archive_recompute_avoided": archive_recompute_avoided,
        "recommended_next_action": e2e_item.get("recommended_next_action", "Review queue E2E opportunity before implementation."),
        "summary_reuse_source": summary_reuse_source,
        "recomputed_fields": recomputed_fields,
        "reused_fields": normalize_implementation_branch_refs(reused_fields),
        "missing_fields": normalize_implementation_branch_refs(missing_fields),
        "reuse_warnings": normalize_implementation_branch_refs(reuse_warnings),
    }


def build_growth_direct_eval_candidates(
    per_target: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    *,
    eval_version: str = GROWTH_DIRECT_UPGRADE_EVAL_VERSION,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in per_target:
        blocked = bool(item["divergence_warnings"]) or item["suitability_status"] not in {"suitable", "suitable_with_warnings"}
        safety_score = max(0, 10 - int(item["safety_risk_score"]))
        candidate_type = "source_growth_upgrade"
        if "source" in item["best_growth_opportunity_title"].lower() or "planning" in item["best_growth_opportunity_title"].lower():
            candidate_type = "queue_cache_observability"
        if "compression" in item["best_growth_opportunity_title"].lower():
            candidate_type = "repo_role_calibration"
        candidates.append(growth_direct_eval_candidate(
            candidate_id="growth-direct-upgrade-candidate-" + _hash_text({"source": item["source_path"], "title": item["best_growth_opportunity_title"], "version": eval_version})[:12],
            source_path=item["source_path"],
            title=item["best_growth_opportunity_title"],
            candidate_type=candidate_type,
            direct_value=item["calibrated_direct_usefulness_score"],
            friction=8 if candidate_type in {"queue_cache_observability", "repo_role_calibration"} else 6,
            test_speed=2,
            source_specificity=9 if item["primary_repo_role"] != "unknown" else 4,
            confidence=item["operator_confidence_score"],
            safety=safety_score,
            verification=8 if item["task_alignment_source"] else 6,
            maintenance=3 if item["role_alignment_score"] >= 7 else 5,
            evidence=f"{item['primary_repo_role']} / {item['primary_repo_role_confidence']}; task alignment {item['task_alignment_source']}",
            next_slice=item["recommended_next_action"],
            blocked=blocked,
            rejection_reason="task/dashboard/E2E divergence must be resolved first" if blocked else "",
            candidate_source_artifact="queue_e2e_source_summary" if item["summary_reuse_source"] in {"queue_e2e", "mixed", "queue_e2e_compact_cache", "queue_e2e_computed"} else "recomputed_opportunity_score",
            reused_queue_score=item["summary_reuse_source"] in {"queue_e2e", "mixed", "queue_e2e_compact_cache", "queue_e2e_computed"} and "opportunity_score" not in item["recomputed_fields"],
            recompute_reason="; ".join(item["recomputed_fields"]),
        ))
    if any(issue["issue_id"] == "planning-deterministic-hotspot" for issue in issues):
        candidates.append(growth_direct_eval_candidate(
            candidate_id="growth-direct-upgrade-candidate-planning-speed",
            source_path="",
            title="Split or optimize planning-deterministic hotspot checks",
            candidate_type="planning_test_speed",
            direct_value=5,
            friction=7,
            test_speed=10,
            source_specificity=5,
            confidence=7,
            safety=10,
            verification=8,
            maintenance=3,
            evidence="Prior measured planning-deterministic runtime remains about 69-70s.",
            next_slice="Add per-check timings and move expensive console data coverage behind an explicit deeper planning suite.",
            candidate_source_artifact="direct_eval_issue",
        ))
    if any(issue["issue_id"] == "activepieces-quarantined" for issue in issues):
        candidates.append(growth_direct_eval_candidate(
            candidate_id="growth-direct-upgrade-candidate-source-ref-normalization",
            source_path="research/activepieces-main.zip",
            title="Normalize unsupported activepieces source refs",
            candidate_type="source_ref_normalization",
            direct_value=5,
            friction=4,
            test_speed=1,
            source_specificity=8,
            confidence=4,
            safety=7,
            verification=4,
            maintenance=6,
            evidence="activepieces remains quarantined by deterministic source-ref generation checks.",
            next_slice="Inspect source-ref path normalization failure and add a fail-closed adapter only if the archive shape is clearly supported.",
            candidate_source_artifact="direct_eval_issue",
        ))
    candidates.append(growth_direct_eval_candidate(
        candidate_id="growth-direct-upgrade-candidate-model-status",
        source_path="",
        title="Improve local model timeout status reporting",
        candidate_type="model_status_clarity",
        direct_value=3,
        friction=4,
        test_speed=1,
        source_specificity=2,
        confidence=7,
        safety=8,
        verification=7,
        maintenance=2,
        evidence="Prior operator run observed local model timeout; this deterministic evaluator did not call models.",
        next_slice="Keep model work out of Growth deterministic path; only improve status text if needed.",
        blocked=True,
        rejection_reason="model path is out of scope for deterministic Growth evaluator",
        candidate_source_artifact="prior_observed_issue",
    ))
    return rank_growth_direct_eval_candidates(candidates)


def build_growth_direct_eval_issues(
    status: dict[str, Any],
    warmup: dict[str, Any],
    queue_e2e: dict[str, Any],
    calibration: dict[str, Any],
    per_target: list[dict[str, Any]],
    queue: dict[str, Any],
) -> list[dict[str, Any]]:
    issues = [
        growth_direct_eval_issue(
            "manual-operator-chain-recomputation",
            "high",
            "UX",
            "Manual Growth operator loop is command-heavy",
            "Previous operator runs required queue, E2E, calibration, per-target dashboard, task-draft, and target-command invocations.",
            "One deterministic command should emit the compact direct-upgrade report.",
            "Current direct evaluator composes queue/status/warm/E2E/calibration/per-target summaries in one process.",
            "Use growth direct-upgrade-eval as the operator starting point and keep adding reuse metrics.",
            implement_now=True,
        ),
        growth_direct_eval_issue(
            "planning-deterministic-hotspot",
            "high",
            "test_coverage",
            "planning-deterministic remains slow",
            "Prior measured planning-deterministic runtime is about 69-70s.",
            "Broad deterministic planning checks should have a faster checkpoint tier or per-check timings.",
            "Prior-observed; not remeasured by this evaluator command.",
            "Split check_growth_console_data or add planning-deep so frequent checkpoints stay fast.",
        ),
    ]
    if int(queue_e2e.get("performance_summary", {}).get("total_runtime_ms", 0)) > 30000:
        issues.append(growth_direct_eval_issue(
            "queue-e2e-runtime",
            "high",
            "performance",
            "Queue E2E remains expensive even with caches",
            f"Queue E2E runtime was {queue_e2e['performance_summary']['total_runtime_ms']}ms.",
            "Warmed queue E2E should reuse compact artifacts and make hotspot sources obvious.",
            f"Slowest sources: {queue_e2e['performance_summary'].get('slowest_sources', [])[:3]}",
            "Use direct evaluator performance summary to target repeated downstream recomputation.",
        ))
    if status["cache_miss_count"] or warmup["estimated_work_count"]:
        issues.append(growth_direct_eval_issue(
            "cache-not-warm",
            "medium",
            "cache",
            "Source queue cache needs warming",
            f"Cache status has {status['cache_hit_count']} hits and {status['cache_miss_count']} misses; warmup work count {warmup['estimated_work_count']}.",
            "Operator should see whether --write-cache is needed before E2E.",
            "Direct evaluator reports cache_summary and write_cache_requested/write_cache_performed.",
            "Run growth direct-upgrade-eval --write-cache before repeated repo snowball evaluation.",
        ))
    for quarantine in queue.get("quarantine_records", []):
        if quarantine.get("quarantine_status") != "not_quarantined":
            issues.append(growth_direct_eval_issue(
                "activepieces-quarantined" if quarantine["source_path"].endswith("activepieces-main.zip") else "source-quarantined-" + _hash_text(quarantine["source_path"])[:8],
                "medium",
                "queue",
                f"{quarantine['source_path']} is quarantined",
                quarantine.get("quarantine_reason", "source skipped by queue quarantine"),
                "Problematic optional archives should not break the default queue.",
                quarantine.get("failure_category", "unknown"),
                quarantine.get("recommended_fix", "Keep skipped until deterministic suitability is fixed."),
            ))
    if int(calibration.get("calibration_quality_score", 100)) < 70:
        issues.append(growth_direct_eval_issue(
            "calibration-quality-low",
            "medium",
            "idea_quality",
            "Concept calibration quality is still weak",
            f"Calibration quality score is {calibration.get('calibration_quality_score')}.",
            "Source roles and opportunity templates should be confident only when evidence supports them.",
            f"Needs profile work: {[item.get('source_path') for item in calibration.get('needs_profile_work', [])[:4]]}",
            "Add source-specific profile fixtures/templates for weak business/workflow sources.",
        ))
    scores = [item["calibrated_direct_usefulness_score"] for item in per_target]
    if scores and max(scores) - min(scores) < 2:
        issues.append(growth_direct_eval_issue(
            "score-spread-too-tight",
            "medium",
            "idea_quality",
            "Direct usefulness scores are tightly clustered",
            f"Per-target usefulness score range is {min(scores)}..{max(scores)}.",
            "Ranking should expose meaningful confidence differences.",
            "Current evidence comes from direct evaluator per-target summaries.",
            "Add a small score-spread guard using role alignment, evidence strength, and maintenance burden.",
        ))
    for item in per_target:
        if item["divergence_warnings"]:
            issues.append(growth_direct_eval_issue(
                "task-draft-divergence-" + _hash_text(item["source_path"])[:8],
                "high",
                "operator_handoff",
                f"Task draft diverges for {item['source_name']}",
                "; ".join(item["divergence_warnings"]),
                "Task draft, dashboard, and E2E should point to the same calibrated opportunity.",
                f"task={item['task_draft_title']} e2e={item['e2e_best_opportunity_title']}",
                "Align source-aware task draft selection with calibrated E2E opportunity.",
                implement_now=True,
            ))
    issues.append(growth_direct_eval_issue(
        "local-model-timeout-prior-observed",
        "low",
        "model",
        "Local model timeout path remains outside deterministic Growth",
        "Prior operator run observed local model timeout; this command intentionally did not call local models.",
        "Deterministic Growth should remain useful without model availability.",
        "Prior-observed; no model smoke was run in this batch.",
        "Only improve read-only status reporting in a separate model-status slice.",
        blocked_reason="model calls are out of scope for this deterministic evaluator",
    ))
    return issues


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
