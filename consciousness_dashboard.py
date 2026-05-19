"""Clean Link consciousness dashboard compatibility module.

This module intentionally has no [private-project]/[private-name] dependencies.
It exists so older Link/KB code can import dashboard symbols safely.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DashboardState:
    status: str = "available"
    stats: dict[str, Any] = field(default_factory=dict)


def get_dashboard_state() -> DashboardState:
    return DashboardState()


def stats() -> dict[str, Any]:
    return {}


def render_dashboard() -> str:
    return "Link dashboard available."


def main() -> None:
    print(render_dashboard())


if __name__ == "__main__":
    main()
