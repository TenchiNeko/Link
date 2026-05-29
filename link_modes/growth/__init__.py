"""Growth mode entrypoint.

Import path: ``link_modes.growth``

Growth mode is Link's upgrade research team. It mines external research into
Link-native upgrade candidates and proposals for human review. The concrete
research/mining/proposal tools live in this ``link_modes.growth`` package's
submodules and in the control plane; this package's ``__init__`` is the thin
canonical entrypoint that describes the mode and points at its configuration.

This facade performs no execution and makes no network calls on import.
"""

from __future__ import annotations

from typing import Any

MODE_NAME = "growth"
TEAM_CONFIG = "configs/teams/link_growth.yaml"


def describe() -> dict[str, Any]:
    """Return a read-only description of growth mode.

    Pulls the canonical definition from ``link_core.modes`` when available so
    there is a single source of truth, with a safe local fallback.
    """
    try:
        from link_core.modes import get_mode

        return get_mode(MODE_NAME).to_dict()
    except Exception:
        return {
            "name": MODE_NAME,
            "title": "Growth Mode",
            "description": "Upgrade research team: mine research into Link-native proposals.",
            "entrypoint_module": "link_modes.growth",
            "team_config": TEAM_CONFIG,
            "notes": ["Research-to-upgrade conversion lane.", "Never auto-merges."],
        }


def control_plane_stages() -> tuple[str, ...]:
    """Return the control-plane stages growth proposals flow through."""
    try:
        from link_core.control_plane import get_control_plane_stages

        return get_control_plane_stages()
    except Exception:
        return ()


def propose(
    candidates: list[dict[str, Any]],
    *,
    validate: bool = True,
) -> list[dict[str, Any]]:
    """Convert mined upgrade candidates into validated control-plane proposals.

    Composes the existing ``candidate_to_proposal`` bridge and the control-plane
    ``validate_proposal`` function. This is the canonical runtime entry point
    for the Growth pipeline::

        receipt = run_miner(...)
        proposals = propose(receipt["candidates"])

    Args:
        candidates: A list of miner candidate dicts (from ``run_miner`` /
            ``build_candidates`` in ``link_research_upgrade_miner``).
        validate: When ``True`` (default), each proposal is validated via
            ``link_core.control_plane.validate_proposal`` and an unvalidated
            proposal will raise. When ``False``, validation is skipped but
            the returned dicts still contain all required fields.

    Returns:
        A list of control-plane proposal dicts convertible to proposal
        artifacts via ``write_proposal``.

    Raises:
        TypeError:  ``candidates`` is not iterable.
        ValueError: A candidate is missing required identity fields or
            contains invalid values, propagated from ``candidate_to_proposal``
            or ``validate_proposal``.

    No file I/O. No network. No subprocess. Pure data transform.
    """
    from link_modes.growth.link_candidate_proposal_bridge import (
        candidate_to_proposal,
    )

    proposals: list[dict[str, Any]] = []
    for candidate in candidates:
        proposal = candidate_to_proposal(candidate)
        if validate:
            from link_core.control_plane import validate_proposal
            validate_proposal(proposal)
        proposals.append(proposal)
    return proposals


__all__ = [
    "MODE_NAME",
    "TEAM_CONFIG",
    "describe",
    "control_plane_stages",
    "propose",
]
