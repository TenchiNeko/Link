#!/usr/bin/env python3
"""Deterministic operator QA payload helpers for Growth.

Extracted from link_growth_console.py. This module owns bounded QA check,
issue, and ROI helper logic only; collectors and CLI dispatch stay in the
Growth monolith.
"""

from __future__ import annotations

from typing import Any


def operator_qa_check_item(
    check_id: str,
    check_name: str,
    status: str,
    severity: str,
    observed: str,
    expected: str,
    evidence_summary: str,
    recommended_fix: str,
    command_hint: str = "",
    **extra: Any,
) -> dict[str, Any]:
    item = {
        "check_id": check_id,
        "check_name": check_name,
        "status": status,
        "severity": severity,
        "observed": observed,
        "expected": expected,
        "evidence_summary": evidence_summary,
        "recommended_fix": recommended_fix,
        "command_hint": command_hint,
    }
    item.update(extra)
    return item


def operator_qa_issue(
    issue_id: str,
    severity: str,
    category: str,
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
        "observed_behavior": observed,
        "expected_behavior": expected,
        "evidence_summary": evidence,
        "recommended_fix": fix,
        "implement_now_candidate": bool(implement_now),
        "blocked_reason": blocked_reason,
    }


def operator_qa_candidate(
    candidate_id: str,
    title: str,
    decision: str,
    direct_value: int,
    friction: int,
    confidence: int,
    testability: int,
    safety: int,
    runtime: int,
    schema: int,
    burden: int,
    rationale: str,
    slice_text: str,
) -> dict[str, Any]:
    total = direct_value + friction + confidence + testability + safety + runtime + schema - burden
    return {
        "candidate_id": candidate_id,
        "title": title,
        "decision": decision,
        "direct_growth_functionality_value": direct_value,
        "operator_friction_reduction": friction,
        "implementation_confidence": confidence,
        "testability": testability,
        "safety": safety,
        "expected_runtime_improvement": runtime,
        "schema_output_value": schema,
        "maintenance_burden": burden,
        "total_roi_score": total,
        "rationale": rationale,
        "recommended_implementation_slice": slice_text,
    }


def operator_qa_check_status(checks: list[dict[str, Any]], issues: list[dict[str, Any]]) -> str:
    if any(item.get("status") == "fail" for item in checks):
        return "fail"
    if any(item.get("severity") == "critical" for item in issues):
        return "fail"
    if any(item.get("status") in {"warn", "skipped"} for item in checks):
        return "warn"
    if any(item.get("severity") in {"high", "medium"} for item in issues):
        return "warn"
    return "pass"


def operator_qa_candidate_scores(
    dashboard: dict[str, Any],
    direct_eval: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    readiness = dashboard["operator_readiness"]
    cache_ready = readiness["status"] == "ready"
    direct_issues = direct_eval.get("broken_unoptimized_items", []) if direct_eval else []
    has_score_spread_issue = any(item.get("issue_id") == "score-spread-too-tight" for item in direct_issues)
    has_activepieces = any(
        item.get("source_path", "").endswith("activepieces-main.zip")
        for item in dashboard.get("quarantined_sources", [])
    )
    candidates = [
        operator_qa_candidate(
            "add_or_improve_operator_qa_check",
            "Keep improving deterministic Growth operator QA checks",
            "report_only",
            4,
            5,
            8,
            8,
            10,
            1,
            8,
            5,
            "The command now exists; future work should add checks only when a concrete operator gap is observed.",
            "Extend growth operator-qa-check with one focused new check after evidence from an operator run.",
        ),
        operator_qa_candidate(
            "optimize_source_core",
            "Monitor or optimize the source-core default checkpoint",
            "needs_more_evidence",
            5,
            5,
            8,
            9,
            10,
            5,
            3,
            4,
            "source-fast has been split from the default path; optimize source-core only if it becomes the largest remaining normal checkpoint component.",
            "Measure default no-args after the source-core/source-extended split, then optimize repeated source-core setup only if needed.",
        ),
        operator_qa_candidate(
            "superset_cache_reuse_for_explicit_sources",
            "Reuse superset compact queue cache for explicit-source subsets",
            "needs_more_evidence",
            7,
            7,
            5,
            6,
            8,
            8,
            7,
            6,
            "Could reduce explicit-source operator friction, but this run did not prove the miss pattern enough for an immediate patch.",
            "Measure explicit-source subset cache behavior, then add deterministic cache-key subset reuse only if valid.",
        ),
        operator_qa_candidate(
            "clarify_activepieces_quarantine",
            "Clarify activepieces quarantine output",
            "report_only" if has_activepieces else "needs_more_evidence",
            5,
            4,
            7,
            7,
            9,
            2,
            6,
            4,
            "Activepieces is safely skipped, but source-ref failure language is still technical.",
            "Add a plain-language quarantine summary for deterministic source-ref generation failures.",
        ),
        operator_qa_candidate(
            "improve_score_spread",
            "Improve direct-eval score spread and candidate ranking clarity",
            "needs_more_evidence",
            7,
            5,
            4,
            6,
            7,
            1,
            7,
            6,
            "Ranking quality matters, but score-spread changes are judgment logic and need a dedicated calibration slice.",
            "Add deterministic score-spread guardrails only after fixture-backed calibration examples.",
        ),
        operator_qa_candidate(
            "improve_operator_dashboard_next_actions",
            "Improve Growth operator dashboard next actions",
            "report_only" if not cache_ready else "reject",
            5,
            6,
            8,
            8,
            10,
            1,
            6,
            3,
            "Dashboard next commands are currently clear; only refine if QA finds a stale or missing command hint.",
            "Patch the dashboard hint text only for a concrete observed mismatch.",
        ),
        operator_qa_candidate(
            "optimize_hidden_cold_path",
            "Optimize remaining hidden cold path",
            "needs_more_evidence",
            7,
            6,
            5,
            6,
            8,
            8 if not cache_ready else 4,
            5,
            6,
            "Cold warm remains expensive, but the dashboard now makes that cost explicit and the hot path is fast.",
            "Profile slow source inventory and queue E2E cache writes in a focused performance batch.",
        ),
    ]
    if has_score_spread_issue:
        for item in candidates:
            if item["candidate_id"] == "improve_score_spread":
                item["rationale"] += " Current direct-eval issues still flag tight score spread."
    return sorted(candidates, key=lambda item: item["total_roi_score"], reverse=True)
