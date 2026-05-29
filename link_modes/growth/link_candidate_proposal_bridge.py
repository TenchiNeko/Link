#!/usr/bin/env python3
"""Thin bridge converting a miner candidate dict into a control-plane proposal dict.

Import path: ``link_modes.growth.link_candidate_proposal_bridge``

This module maps the schema from the research upgrade miner's candidate output
to the control-plane proposal schema required by ``validate_proposal``. It is
a pure data transform: no file I/O, no network, no subprocess, no mutation.

When a miner produces a structured candidate from research, this bridge
converts it so it can flow through the control-plane pipeline:

research input -> mined candidate -> bridge -> valid proposal -> approval gate
-> patch plan -> implementation handoff -> verifier -> finalizer
"""

from __future__ import annotations

import datetime as dt
from typing import Any

BRIDGE_VERSION = "growth-candidate-proposal-bridge-v1"


def candidate_to_proposal(
    candidate: dict[str, Any],
    source_path: str | None = None,
    recommendation: str = "accept",
) -> dict[str, Any]:
    """Convert a miner candidate dict into a control-plane proposal dict.

    The returned dict passes ``link_core.control_plane.validate_proposal``
    with safe deterministic defaults for fields not derivable from the
    candidate.

    Args:
        candidate: Miner candidate dict (from ``build_candidates`` /
            ``run_miner`` in ``link_research_upgrade_miner``).
        source_path: Research source path. If not given, derives from the
            first evidence entry's ``source_path``, or defaults to
            ``"research/unknown"``.
        recommendation: One of ``"accept"``, ``"defer"``, ``"reject"``.
            Defaults to ``"accept"``.

    Returns:
        A dict with all 15 fields required by ``validate_proposal``.

    Raises:
        TypeError:  ``candidate`` is not a dict.
        ValueError: ``candidate`` has no non-empty ``title``, or
            ``recommendation`` is invalid.
    """
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dict")

    title = str(candidate.get("title") or "")
    if not title:
        raise ValueError("candidate must have a non-empty title")

    if recommendation not in ("accept", "defer", "reject"):
        raise ValueError(
            f"recommendation must be accept/defer/reject, got {recommendation!r}"
        )

    _resolved_source_path = _resolve_source_path(candidate, source_path)

    from link_core.control_plane import make_proposal_id

    proposal_id = make_proposal_id(title, _resolved_source_path)

    return {
        "proposal_id": proposal_id,
        "title": title,
        "source_path": _resolved_source_path,
        "source_summary": str(candidate.get("why") or title),
        "extracted_capabilities": list(candidate.get("plan") or []),
        "link_takeaways": list(candidate.get("plan") or []),
        "affected_files": list(
            candidate.get("files_affected")
            or candidate.get("files")
            or []
        ),
        "risk_level": str(candidate.get("risk") or "medium"),
        "expected_behavior_change": str(candidate.get("why") or title),
        "implementation_plan": list(candidate.get("plan") or []),
        "verification_commands": list(
            candidate.get("tests") or candidate.get("checks") or []
        ),
        "rollback_plan": (
            "Revert patch branch; healthcheck must pass before merge."
        ),
        "recommendation": recommendation,
        "status": "pending",
        "created_at": str(
            candidate.get("created_at")
            or dt.datetime.now().replace(microsecond=0).isoformat()
        ),
    }


def _resolve_source_path(
    candidate: dict[str, Any],
    explicit: str | None,
) -> str:
    if explicit:
        return explicit
    evidence = candidate.get("evidence")
    if isinstance(evidence, list) and evidence:
        first = evidence[0]
        if isinstance(first, dict) and first.get("source_path"):
            return str(first["source_path"])
    return "research/unknown"


def smoke() -> None:
    """Deterministic self-test (no file I/O, no network, no subprocess).

    Builds a synthetic miner candidate, converts it via
    ``candidate_to_proposal``, and verifies the result passes
    ``validate_proposal``. Also tests input validation guards.
    """
    from link_core.control_plane import validate_proposal

    synthetic = {
        "candidate_id": "abc123def456",
        "source": "research_upgrade_miner",
        "source_version": "LU190-research-upgrade-miner-foundation-v1",
        "title": "research evidence index for upgrade proposals",
        "risk": "medium",
        "why": "Link needs source-grounded upgrade proposals so agents can cite "
               "research files instead of inventing vague maintenance work.",
        "plan": [
            "Index configured research folders and archives.",
            "Record source path and snippet for each hit.",
            "Attach evidence references to generated candidates.",
        ],
        "proposed_plan": [
            "Index configured research folders and archives.",
            "Record source path and snippet for each hit.",
            "Attach evidence references to generated candidates.",
        ],
        "files": ["link_research_upgrade_miner.py"],
        "files_affected": ["link_research_upgrade_miner.py"],
        "areas_affected": ["link_research_upgrade_miner.py"],
        "tests": ["python3 -m py_compile link_research_upgrade_miner.py"],
        "checks": ["python3 -m py_compile link_research_upgrade_miner.py"],
        "receipts": [".link/approval_candidates.jsonl"],
        "evidence": [
            {
                "source_path": "research/upgrade_ideas.md",
                "line": 1,
                "snippet": "evidence citation research",
            }
        ],
        "created_at": "2026-05-29T00:00:00",
    }

    proposal = candidate_to_proposal(synthetic)
    try:
        validate_proposal(proposal)
    except Exception as exc:
        raise AssertionError(
            f"validate_proposal rejected bridged proposal: {exc}"
        )

    if proposal["risk_level"] != "medium":
        raise AssertionError(
            f"risk_level expected 'medium', got {proposal['risk_level']!r}"
        )
    if proposal["status"] != "pending":
        raise AssertionError(
            f"status expected 'pending', got {proposal['status']!r}"
        )
    if proposal["recommendation"] != "accept":
        raise AssertionError(
            f"recommendation expected 'accept', got {proposal['recommendation']!r}"
        )
    if not isinstance(proposal["implementation_plan"], list):
        raise AssertionError("implementation_plan must be a list")
    if len(proposal["implementation_plan"]) == 0:
        raise AssertionError("implementation_plan must be non-empty")

    # Input validation guards
    try:
        candidate_to_proposal(None)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("candidate_to_proposal(None) must raise TypeError")

    try:
        candidate_to_proposal({})
    except ValueError:
        pass
    else:
        raise AssertionError("candidate_to_proposal({}) must raise ValueError")

    print("candidate proposal bridge smoke OK")


__all__ = [
    "BRIDGE_VERSION",
    "candidate_to_proposal",
    "smoke",
]