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


__all__ = [
    "MODE_NAME",
    "TEAM_CONFIG",
    "describe",
    "control_plane_stages",
]
