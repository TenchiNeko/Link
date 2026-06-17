#!/usr/bin/env python3
"""Task draft/source alignment helpers for Growth.

Extracted from link_growth_console.py. This module owns deterministic task
alignment helpers only; CLI dispatch and broad direct-eval orchestration stay
in link_growth_console.py.
"""

from __future__ import annotations

from typing import Any


def select_source_aware_operator_task_candidate(
    decision: dict[str, Any],
    source_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], str, list[str]]:
    """Select the candidate that aligns a task draft with calibrated source data."""
    ranked_top = next(
        item
        for item in decision["candidate_set"]["candidates"]
        if item["decision_candidate_id"] == decision["ranking"]["top_candidate_id"]
    )
    if source_context is None:
        return ranked_top, "decision_ranking", []
    calibrated_task = source_context.get("research_target_operator_task_draft")
    if not isinstance(calibrated_task, dict):
        return ranked_top, "decision_ranking", []
    selected_id = calibrated_task.get("selected_upgrade_candidate_id")
    if not isinstance(selected_id, str) or not selected_id:
        return ranked_top, "decision_ranking", []
    aligned = next(
        (
            item
            for item in decision["candidate_set"]["candidates"]
            if item.get("selected_upgrade_candidate_id") == selected_id
        ),
        None,
    )
    if not isinstance(aligned, dict):
        return ranked_top, "decision_ranking", [
            "calibrated task candidate was not present in the decision candidate set",
        ]
    if aligned["decision_candidate_id"] == ranked_top["decision_candidate_id"]:
        return aligned, "decision_ranking", []
    return aligned, "calibrated_task_candidate", [
        f"task draft aligned to calibrated candidate {selected_id} instead of raw decision ranking {ranked_top.get('selected_upgrade_candidate_id', '')}",
    ]
