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
