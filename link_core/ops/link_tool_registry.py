#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    toolset: str
    description: str
    risk: str = "read"
    requires_approval: bool = False
    enabled_by_default: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="git_status",
        toolset="git",
        description="Inspect current git branch and working tree status.",
        risk="read",
        enabled_by_default=True,
    ),
    ToolSpec(
        name="git_diff",
        toolset="git",
        description="Inspect unstaged or staged git diffs.",
        risk="read",
        enabled_by_default=True,
    ),
    ToolSpec(
        name="git_commit",
        toolset="git",
        description="Create a git commit after tests and evidence are available.",
        risk="write",
        requires_approval=True,
    ),
    ToolSpec(
        name="file_read",
        toolset="filesystem",
        description="Read project files inside the approved repository boundary.",
        risk="read",
        enabled_by_default=True,
    ),
    ToolSpec(
        name="file_write",
        toolset="filesystem",
        description="Write or edit project files inside the approved repository boundary.",
        risk="write",
        requires_approval=True,
    ),
    ToolSpec(
        name="execution_snapshot",
        toolset="safety",
        description="Create rollback and audit snapshots before risky execution.",
        risk="write",
        enabled_by_default=True,
    ),
    ToolSpec(
        name="capability_gate",
        toolset="safety",
        description="Classify file, git, shell, and capability requests before action.",
        risk="read",
        enabled_by_default=True,
    ),
    ToolSpec(
        name="self_update_preflight",
        toolset="self_update",
        description="Inspect self-update readiness and write a preflight receipt.",
        risk="write",
        enabled_by_default=True,
    ),
    ToolSpec(
        name="research_archive_miner",
        toolset="research",
        description="Mine external archives for Link-native upgrade ideas.",
        risk="read",
    ),
    ToolSpec(
        name="workflow_preflight",
        toolset="workflow",
        description="Validate workflow specifications before execution.",
        risk="read",
    ),
    ToolSpec(
        name="workflow_step_executor",
        toolset="workflow",
        description="Execute approved workflow steps with receipts.",
        risk="write",
        requires_approval=True,
    ),
    ToolSpec(
        name="factory_plan",
        toolset="factory",
        description="Create draft plans for multi-agent factory work.",
        risk="write",
    ),
    ToolSpec(
        name="factory_execute",
        toolset="factory",
        description="Run model-backed factory execution after approval.",
        risk="external",
        requires_approval=True,
    ),
)


HARD_BLOCKED_TOOLS: frozenset[str] = frozenset(
    {
        "destructive_shell",
        "git_reset_hard",
        "git_clean_force",
        "force_push",
        "external_publish",
    }
)


def all_tools() -> dict[str, ToolSpec]:
    return {tool.name: tool for tool in TOOLS}


def toolsets() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for tool in TOOLS:
        grouped.setdefault(tool.toolset, []).append(tool.name)
    return {name: sorted(values) for name, values in sorted(grouped.items())}


def _expand_selectors(selectors: list[str] | tuple[str, ...] | None) -> set[str]:
    if not selectors:
        return set()

    known_tools = all_tools()
    known_toolsets = toolsets()
    selected: set[str] = set()

    for raw in selectors:
        item = str(raw or "").strip()
        if not item:
            continue
        if item in known_toolsets:
            selected.update(known_toolsets[item])
        elif item in known_tools:
            selected.add(item)
        else:
            selected.add(item)

    return selected


def resolve_toolsets(
    enabled_toolsets: list[str] | tuple[str, ...] | None = None,
    disabled_toolsets: list[str] | tuple[str, ...] | None = None,
    *,
    include_default: bool = True,
) -> list[ToolSpec]:
    known = all_tools()

    enabled_names: set[str] = set()
    if include_default:
        enabled_names.update(tool.name for tool in TOOLS if tool.enabled_by_default)

    enabled_names.update(_expand_selectors(enabled_toolsets))
    disabled_names = _expand_selectors(disabled_toolsets)

    final_names = sorted(
        name
        for name in enabled_names
        if name in known and name not in disabled_names and name not in HARD_BLOCKED_TOOLS
    )
    return [known[name] for name in final_names]


def toolset_summary(
    enabled_toolsets: list[str] | tuple[str, ...] | None = None,
    disabled_toolsets: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    resolved = resolve_toolsets(enabled_toolsets, disabled_toolsets)
    return {
        "available_toolsets": toolsets(),
        "enabled_tools": [tool.to_dict() for tool in resolved],
        "hard_blocked_tools": sorted(HARD_BLOCKED_TOOLS),
    }


def validate_registry() -> dict[str, Any]:
    names = [tool.name for tool in TOOLS]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    empty_fields = [
        tool.name
        for tool in TOOLS
        if not tool.name.strip() or not tool.toolset.strip() or not tool.description.strip()
    ]

    return {
        "ok": not duplicate_names and not empty_fields,
        "tool_count": len(TOOLS),
        "toolset_count": len(toolsets()),
        "duplicate_names": duplicate_names,
        "empty_fields": empty_fields,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(toolset_summary(), indent=2, sort_keys=True))
