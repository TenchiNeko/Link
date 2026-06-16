#!/usr/bin/env python3
"""Pure Growth human output renderers.

This module is part of the safe extraction from
``link_modes.growth.link_growth_console``. Keep it limited to deterministic
formatting of already-built payloads.

No business logic, cache logic, model logic, archive reads, CLI dispatch, or
source mutation should live here.
"""

from __future__ import annotations

from typing import Any


def render_growth_operator_cache_dashboard_text(payload: dict[str, Any]) -> str:
    """Render a compact operator cache dashboard summary."""
    source = payload["source_inventory_cache_summary"]
    queue = payload["queue_e2e_cache_summary"]
    readiness = payload["operator_readiness"]
    lines = [
        "Growth Operator Cache Dashboard",
        "  source inventory:",
    ]
    source_status = "hot" if source["ready_for_hot_path"] else ("cold" if source["hit_count"] == 0 else "partial")
    lines.append(f"    status: {source_status}")
    lines.append(f"    hits/misses/stale: {source['hit_count']}/{source['miss_count']}/{source['stale_count']}")
    lines.append(f"    next: {source['recommended_next_action']}")
    lines.append("  queue E2E compact:")
    lines.append(f"    status: {queue['summary_source']}")
    lines.append(f"    best cached opportunity: {queue['best_cached_opportunity_title'] or 'none'}")
    lines.append(f"    next: {queue['recommended_next_action']}")
    lines.append("  hot paths:")
    lines.append(f"    direct-upgrade-eval: {'ready' if payload['direct_upgrade_eval_hot_path']['ready'] else 'not ready'}")
    lines.append(f"    concept-calibration-report fast: {'ready' if payload['concept_calibration_hot_path']['ready'] else 'not ready'}")
    lines.append("  skipped/quarantined:")
    for item in payload["quarantined_sources"][:6] or [{"source_path": "none", "quarantine_reason": ""}]:
        reason = item.get("quarantine_reason") or item.get("failure_category") or "none"
        lines.append(f"    - {item['source_path']}: {reason}")
    lines.append("  issues:")
    for item in payload["broken_unoptimized_items"][:5]:
        lines.append(f"    - {item['severity']}/{item['category']}: {item['title']}")
    lines.append("  next command:")
    lines.append(f"    {readiness['next_command']}")
    lines.append("Safety:")
    lines.append("  model used: no")
    lines.append("  OpenRouter: no")
    lines.append(f"  network: {'yes' if payload['external_network_used'] else 'no'}")
    lines.append("  read-only: yes")
    return "\n".join(lines) + "\n"


def print_growth_operator_cache_dashboard(payload: dict[str, Any]) -> None:
    """Print the operator cache dashboard human summary."""
    print(render_growth_operator_cache_dashboard_text(payload), end="")


def render_growth_operator_qa_check_text(payload: dict[str, Any]) -> str:
    """Render a compact operator QA check summary."""
    highest = payload["highest_roi_next_fix"]
    cache = {item["check_id"]: item for item in payload["cache_readiness_checks"]}
    hot = {item["check_id"]: item for item in payload["hot_path_checks"]}
    lines = [
        "Growth Operator QA Check",
        f"  status: {payload['operator_qa_status']}",
        f"  mode: {payload['mode']}",
        "  readiness:",
        f"    Growth: {payload['operator_readiness_status']}",
        f"    direct-upgrade-eval: {hot.get('direct_upgrade_eval_hot_path_ready_or_warm_command', {}).get('observed', 'unknown')}",
        f"    concept-calibration fast: {hot.get('concept_calibration_fast_ready_or_warm_command', {}).get('observed', 'unknown')}",
        "  cache:",
        f"    source inventory: {cache.get('source_inventory_cache_status_known', {}).get('observed', 'unknown')}",
        f"    queue E2E compact: {cache.get('queue_e2e_compact_cache_status_known', {}).get('observed', 'unknown')}",
        "  alignment:",
    ]
    alignment_statuses = [item["status"] for item in payload["alignment_checks"]]
    lines.append(f"    task draft: {'checked' if any(item['check_id'] == 'task_draft_alignment_source_present' for item in payload['alignment_checks']) else 'skipped'}")
    lines.append(f"    best opportunity: {'checked' if any(item['check_id'] == 'direct_eval_best_direct_upgrade_present' for item in payload['alignment_checks']) else 'skipped'}")
    if payload["skipped_checks"] or "skipped" in alignment_statuses:
        lines.append("  skipped:")
        skipped = payload["skipped_checks"][:4] or [item for item in payload["alignment_checks"] if item["status"] == "skipped"][:4]
        for item in skipped:
            lines.append(f"    - {item['check_id']}: {item.get('reason') or item.get('observed')}")
    lines.append("  issues:")
    for item in payload["issue_inventory"][:6] or [{"severity": "low", "category": "none", "issue_id": "none", "observed_behavior": "none"}]:
        lines.append(f"    - {item['severity']}/{item['category']}: {item['issue_id']}")
    lines.extend([
        "  highest ROI next fix:",
        f"    title: {highest['title']}",
        f"    why: {highest['rationale']}",
        f"    slice: {highest['recommended_implementation_slice']}",
        f"  next command: {payload['recommended_next_action']}",
        "  safety:",
        f"    model used: {'yes' if payload['model_used'] else 'no'}",
        "    OpenRouter: no",
        f"    network: {'yes' if payload['external_network_used'] else 'no'}",
        "    read-only: yes",
    ])
    return "\n".join(lines) + "\n"


def print_growth_operator_qa_check(payload: dict[str, Any]) -> None:
    """Print the operator QA check human summary."""
    print(render_growth_operator_qa_check_text(payload), end="")


def render_growth_direct_upgrade_eval_text(payload: dict[str, Any]) -> str:
    """Render a compact direct-upgrade-eval operator summary."""
    best = payload.get("best_direct_upgrade") or {}
    cache = payload.get("cache_summary") or {}
    queue = payload.get("queue_summary") or {}
    reuse = payload.get("request_reuse_summary") or {}
    lines = [
        "Growth Direct Upgrade Eval",
        "  queue:",
        f"    selected: {queue.get('selected_count', 0)}",
        f"    skipped: {queue.get('skipped_count', 0)}  quarantined: {queue.get('quarantined_count', 0)}",
        f"    cache: hits {cache.get('after_hit_count', 0)} / misses {cache.get('after_miss_count', 0)} / stale {cache.get('stale_count', 0)}",
        f"    cache writes: {'yes' if payload.get('write_cache_performed') else 'no'}",
        "  cache:",
        (
            f"    source inventory: {reuse.get('source_inventory_cache_after_hit_count', 0)} hit / "
            f"{reuse.get('source_inventory_cache_after_miss_count', 0)} miss"
        ),
    ]
    if payload.get("write_cache_requested"):
        lines.append(
            f"    source inventory warm: warmed {payload.get('source_inventory_cache_warmed_count', 0)} / "
            f"failed {payload.get('source_inventory_cache_failed_count', 0)} / skipped {payload.get('source_inventory_cache_skipped_count', 0)}"
        )
    lines.extend([
        f"    hot path: {'ready' if reuse.get('cache_layers_ready') else 'not ready'}",
        "  queue E2E cache:",
        (
            f"    hit: {payload.get('queue_e2e_cache_hit', False)}  "
            f"used: {payload.get('queue_e2e_cache_used', False)}  "
            f"written: {payload.get('queue_e2e_cache_write_performed', False)}"
        ),
        "  best:",
    ])
    if best:
        lines.extend([
            f"    title: {best['title']}",
            f"    source: {best['source_path'] or 'operator'}",
            f"    ROI: {best['total_roi_score']}",
            f"    why: {best['evidence_summary']}",
            f"    next: {best['recommended_implementation_slice']}",
        ])
    else:
        lines.extend([
            "    title: none",
            "    next: no high-quality deterministic implementation candidate",
        ])
    lines.append("  runners-up:")
    for item in payload.get("runner_up_upgrades", [])[:3] or [{"title": "none", "total_roi_score": 0}]:
        lines.append(f"    - {item['title']} (ROI {item['total_roi_score']})")
    lines.append("  issues:")
    for item in payload.get("broken_unoptimized_items", [])[:5]:
        lines.append(f"    - {item['severity']}/{item['category']}: {item['title']}")
    safety = "no" if not payload.get("model_used") else "yes"
    lines.extend([
        "  safety:",
        f"    model used: {safety}",
        "    OpenRouter: no",
        f"    network: {'yes' if payload.get('external_network_used') else 'no'}",
        "  reuse:",
        (
            "    queue E2E reused for "
            f"{reuse.get('source_queue_e2e_reused_for_targets_count', 0)} targets; "
            f"opportunity recomputes {reuse.get('opportunity_score_recompute_count', 0)}; "
            f"avoided {reuse.get('avoided_per_target_recompute_count', 0)} per-target recomputes"
        ),
        (
            f"    per-target archive touches avoided: {reuse.get('per_target_archive_touch_avoided_count', 0)}; "
            f"required: {reuse.get('per_target_archive_touch_required_count', 0)}; "
            f"full queue E2E avoided: {'yes' if reuse.get('full_queue_e2e_compute_avoided') else 'no'}"
        ),
        f"  next: {payload.get('recommended_next_action', '')}",
    ])
    return "\n".join(lines) + "\n"


def print_growth_direct_upgrade_eval(payload: dict[str, Any]) -> None:
    """Print the direct-upgrade-eval human summary."""
    print(render_growth_direct_upgrade_eval_text(payload), end="")


def render_growth_concept_calibration_report_text(payload: dict[str, Any]) -> str:
    """Render a compact concept-calibration-report operator summary."""
    best = payload["best_calibrated_opportunities"][0] if payload["best_calibrated_opportunities"] else {}
    reuse = payload["request_reuse_summary"]
    perf = payload["performance_summary"]
    lines = [
        "Concept Calibration Report",
        f"  mode: {payload['report_mode']}",
        f"  sources: {len(payload['sources'])}",
        f"  calibration quality: {payload['calibration_quality_score']}",
        (
            "  queue E2E cache: "
            f"hit {payload.get('queue_e2e_cache_hit', False)} / "
            f"used {payload.get('queue_e2e_cache_used', False)} / "
            f"source {payload.get('queue_e2e_summary_source', 'computed')}"
        ),
        f"  best classified: {best.get('source_path', 'none')} {best.get('primary_role', '')}",
        "  weak classifications:",
    ]
    for item in payload["needs_profile_work"][:5] or [{"source_path": "none", "primary_role": ""}]:
        lines.append(f"    - {item['source_path']}: {item.get('primary_role', 'unknown')}")
    lines.extend([
        f"  false positives: {payload['false_positive_summary']['compression_false_positive_count']}",
        "  reuse:",
        (
            f"    queue E2E reused for {reuse['queue_e2e_sources_reused_count']} sources; "
            f"recomputed {reuse['source_entries_recomputed_count']} source summaries; "
            f"avoided {reuse['avoided_source_recompute_count']}"
        ),
        f"  performance: total {perf['total_runtime_ms']}ms; queue E2E {perf['queue_e2e_runtime_ms']}ms",
        f"  next: {payload['recommended_next_action']}",
    ])
    return "\n".join(lines) + "\n"


def print_growth_concept_calibration_report(payload: dict[str, Any]) -> None:
    """Print the concept-calibration-report human summary."""
    print(render_growth_concept_calibration_report_text(payload), end="")


def render_growth_source_queue_e2e_text(payload: dict[str, Any]) -> str:
    """Render a compact source-queue-e2e summary."""
    best = payload["best_overall_opportunity"]
    cache = payload["cache_summary"]
    lines = [
        "Queue E2E",
        f"  mode: {payload['report_mode']}",
        "  cache:",
        (
            f"    compact summary: hit {payload['queue_e2e_cache_hit']} / "
            f"used {payload['queue_e2e_cache_used']} / written {payload['queue_e2e_cache_write_performed']}"
        ),
        f"  best opportunity: {best['title']} ({best['source_path']})",
    ]
    if payload["runner_up_opportunities"]:
        runner = payload["runner_up_opportunities"][0]
        lines.append(f"  runner-up: {runner['title']} ({runner['source_path']})")
    else:
        lines.append("  runner-up: none")
    lines.extend([
        f"  cache: hits {cache['cache_hit_count']} / misses {cache['cache_miss_count']} / stale {cache['stale_count']}",
        f"  skipped/quarantined: {payload['skipped_source_count']}/{payload['quarantined_source_count']}",
        f"  runtime_ms: {payload['performance_summary']['total_runtime_ms']}",
        f"  next: {payload['recommended_next_action']}",
    ])
    return "\n".join(lines) + "\n"


def print_growth_source_queue_e2e(payload: dict[str, Any]) -> None:
    """Print the source-queue-e2e human summary."""
    print(render_growth_source_queue_e2e_text(payload), end="")


def render_growth_source_cache_status_text(payload: dict[str, Any]) -> str:
    """Render a persistent source cache status summary."""
    lines = [
        "Persistent Source Cache Status",
        f"source: {payload['source_path']}",
        f"manifest: {payload['manifest_id']}",
        f"exists: {payload['cache_file_exists']}  valid: {payload['cache_valid']}  hit: {payload['cache_hit']}",
        f"bytes: {payload['cached_size_bytes']}  created: {payload['created_at'] or 'not available'}",
    ]
    if payload["invalidation_reasons"]:
        lines.append("invalidation: " + "; ".join(payload["invalidation_reasons"][:3]))
    lines.append(f"next: {payload['recommended_next_action']}")
    return "\n".join(lines) + "\n"


def print_growth_source_cache_status(payload: dict[str, Any]) -> None:
    """Print the persistent source cache status human summary."""
    print(render_growth_source_cache_status_text(payload), end="")


def render_growth_source_suitability_text(payload: dict[str, Any]) -> str:
    """Render a source suitability summary."""
    lines = [
        "Source Suitability",
        f"  source: {payload['source_path']}",
        f"  status: {payload['suitability_status']}",
        f"  queue eligible: {payload['queue_eligible']}",
        f"  persistent cache eligible: {payload['persistent_cache_eligible']}",
        f"  failure: {payload['failure_category'] or 'none'}",
    ]
    if payload["failure_summary"]:
        lines.append(f"  summary: {payload['failure_summary']}")
    lines.append(f"  next: {payload['recommended_next_action']}")
    return "\n".join(lines) + "\n"


def print_growth_source_suitability(payload: dict[str, Any]) -> None:
    """Print the source suitability human summary."""
    print(render_growth_source_suitability_text(payload), end="")


def render_growth_source_quarantine_text(payload: dict[str, Any]) -> str:
    """Render a source quarantine summary."""
    lines = [
        "Source Quarantine",
        f"  source: {payload['source_path']}",
        f"  status: {payload['quarantine_status']}",
        f"  failure: {payload['failure_category'] or 'none'}",
        f"  default excluded: {payload['excluded_from_default_queue']}",
    ]
    if payload["quarantine_reason"]:
        lines.append(f"  reason: {payload['quarantine_reason']}")
    lines.append(f"  next: {payload['recommended_next_action']}")
    return "\n".join(lines) + "\n"


def print_growth_source_quarantine(payload: dict[str, Any]) -> None:
    """Print the source quarantine human summary."""
    print(render_growth_source_quarantine_text(payload), end="")


def render_growth_source_queue_policy_text(payload: dict[str, Any]) -> str:
    """Render a source queue policy summary."""
    lines = [
        "Source Queue Policy",
        f"  suitability required: {payload['default_queue_requires_suitability']}",
        f"  optional failure policy: {payload['optional_source_failure_policy']}",
        f"  required failure policy: {payload['required_source_failure_policy']}",
        "  required:",
    ]
    for item in payload["required_sources"]:
        lines.append(f"    - {item}")
    lines.append("  optional:")
    for item in payload["optional_sources"]:
        lines.append(f"    - {item}")
    return "\n".join(lines) + "\n"


def print_growth_source_queue_policy(payload: dict[str, Any]) -> None:
    """Print the source queue policy human summary."""
    print(render_growth_source_queue_policy_text(payload), end="")
