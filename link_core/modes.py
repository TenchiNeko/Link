"""Canonical Link mode definitions.

Import path: ``link_core.modes``

Link runs in distinct operating modes. This module defines the stable
vocabulary for those modes and points each one at its entrypoint package.
It is declarative and dependency-light: it does not execute modes, only
describes them.

Modes:
- ``base``     : core single-agent supervised engine work.
- ``growth``   : the upgrade research/mining team (``link_modes.growth``).
- ``business`` : the business operations / factory team (``link_modes.business``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModeDefinition:
    name: str
    title: str
    description: str
    entrypoint_module: str
    team_config: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "entrypoint_module": self.entrypoint_module,
            "team_config": self.team_config,
            "notes": list(self.notes),
        }


MODE_DEFINITIONS: dict[str, ModeDefinition] = {
    "base": ModeDefinition(
        name="base",
        title="Base Mode",
        description=(
            "Core supervised single-agent engine work: plan, patch, verify, "
            "and produce evidence under safety gates."
        ),
        entrypoint_module="link_engine",
        team_config="",
        notes=(
            "Default mode for direct repository work.",
            "Runs through the supervised Link engine and healthcheck gates.",
        ),
    ),
    "growth": ModeDefinition(
        name="growth",
        title="Growth Mode",
        description=(
            "Upgrade research team. Mines external research into Link-native "
            "upgrade candidates and proposals for human review."
        ),
        entrypoint_module="link_modes.growth",
        team_config="configs/teams/link_growth.yaml",
        notes=(
            "Research-to-upgrade conversion lane.",
            "Produces proposals/candidates, never auto-merges.",
        ),
    ),
    "business": ModeDefinition(
        name="business",
        title="Business Mode",
        description=(
            "Business operations team (factory). Turns goals into draft work "
            "orders, research, and deliverables with QA gates."
        ),
        entrypoint_module="link_modes.business",
        team_config="configs/teams/business_ops.yaml",
        notes=(
            "Draft-only outputs.",
            "Nothing is posted, published, or sent without human approval.",
        ),
    ),
}


def list_modes() -> list[dict[str, Any]]:
    """Return all mode definitions as plain dicts."""
    return [mode.to_dict() for mode in MODE_DEFINITIONS.values()]


def get_mode(name: str) -> ModeDefinition:
    """Return one mode definition by name."""
    key = str(name or "").strip().lower()
    if key not in MODE_DEFINITIONS:
        available = ", ".join(sorted(MODE_DEFINITIONS))
        raise KeyError(f"unknown mode: {name}. Available modes: {available}")
    return MODE_DEFINITIONS[key]


def mode_names() -> list[str]:
    """Return the ordered list of mode names."""
    return list(MODE_DEFINITIONS)


__all__ = [
    "ModeDefinition",
    "MODE_DEFINITIONS",
    "list_modes",
    "get_mode",
    "mode_names",
]
