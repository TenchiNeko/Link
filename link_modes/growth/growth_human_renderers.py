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
