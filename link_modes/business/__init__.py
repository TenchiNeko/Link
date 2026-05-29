"""Business mode entrypoint.

Import path: ``link_modes.business``

Business mode is Link's business operations team (the factory). It turns goals
into draft work orders, research, and deliverables under QA gates. The concrete
team/pipeline definitions live in the ``factory`` package and this
``link_modes.business`` package's submodules; this package's ``__init__`` is
the thin canonical entrypoint that describes the mode and points at its
configuration.

This facade performs no execution and makes no network calls on import.
Nothing is posted, published, or sent without human approval.
"""

from __future__ import annotations

from typing import Any

MODE_NAME = "business"
TEAM_CONFIG = "configs/teams/business_ops.yaml"


def describe() -> dict[str, Any]:
    """Return a read-only description of business mode.

    Pulls the canonical definition from ``link_core.modes`` when available so
    there is a single source of truth, with a safe local fallback.
    """
    try:
        from link_core.modes import get_mode

        return get_mode(MODE_NAME).to_dict()
    except Exception:
        return {
            "name": MODE_NAME,
            "title": "Business Mode",
            "description": "Business operations / factory team producing draft deliverables.",
            "entrypoint_module": "link_modes.business",
            "team_config": TEAM_CONFIG,
            "notes": ["Draft-only outputs.", "No external action without approval."],
        }


def team_roles() -> list[dict[str, Any]]:
    """Return the business/factory team roles when available."""
    try:
        from link_core.roles import list_business_roles

        return list_business_roles()
    except Exception:
        return []


def tier_names() -> list[str]:
    """Return available factory execution tiers when available."""
    try:
        from link_core.roles import business_tier_names

        if business_tier_names is None:
            return []
        return business_tier_names()
    except Exception:
        return []


__all__ = [
    "MODE_NAME",
    "TEAM_CONFIG",
    "describe",
    "team_roles",
    "tier_names",
]
