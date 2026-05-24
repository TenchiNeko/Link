#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from link_tool_registry import HARD_BLOCKED_TOOLS, all_tools
from link_worker_profiles import profile_summary


@dataclass(frozen=True)
class ProfileToolDecision:
    profile: str
    tool: str
    decision: str
    reason: str
    source: str = "link_profile_gate"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def denied(self) -> bool:
        return self.decision == "deny"

    @property
    def caution(self) -> bool:
        return self.decision == "caution"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tool_map() -> dict[str, Any]:
    return {tool.name: tool for tool in all_tools()}


def classify_profile_tool(
    profile: str,
    tool_name: str,
    *,
    approval_confirmed: bool = False,
) -> ProfileToolDecision:
    profile_name = str(profile or "").strip()
    tool = str(tool_name or "").strip()

    if not profile_name:
        return ProfileToolDecision(profile_name, tool, "deny", "missing worker profile")

    if not tool:
        return ProfileToolDecision(profile_name, tool, "deny", "missing tool name")

    if tool in HARD_BLOCKED_TOOLS:
        return ProfileToolDecision(
            profile_name,
            tool,
            "deny",
            "tool is hard-blocked by the Link tool registry",
            metadata={"hard_blocked": sorted(HARD_BLOCKED_TOOLS)},
        )

    tools = _tool_map()
    spec = tools.get(tool)
    if spec is None:
        return ProfileToolDecision(
            profile_name,
            tool,
            "deny",
            "tool is not registered in the Link tool registry",
        )

    try:
        summary = profile_summary(profile_name)
    except Exception as exc:
        return ProfileToolDecision(
            profile_name,
            tool,
            "deny",
            f"worker profile could not be resolved: {exc}",
        )

    enabled = set(summary.get("enabled_tool_names", []))
    if tool not in enabled:
        return ProfileToolDecision(
            profile_name,
            tool,
            "deny",
            "tool is not enabled for this worker profile",
            metadata={
                "enabled_tool_names": sorted(enabled),
                "toolset": spec.toolset,
                "risk": spec.risk,
                "requires_approval": spec.requires_approval,
            },
        )

    if spec.requires_approval and not approval_confirmed:
        return ProfileToolDecision(
            profile_name,
            tool,
            "caution",
            "tool is enabled for this profile but still requires explicit approval",
            metadata={
                "enabled_tool_names": sorted(enabled),
                "toolset": spec.toolset,
                "risk": spec.risk,
                "requires_approval": spec.requires_approval,
            },
        )

    return ProfileToolDecision(
        profile_name,
        tool,
        "allow",
        "tool is enabled for this worker profile",
        metadata={
            "enabled_tool_names": sorted(enabled),
            "toolset": spec.toolset,
            "risk": spec.risk,
            "requires_approval": spec.requires_approval,
            "approval_confirmed": approval_confirmed,
        },
    )


def require_profile_tool(
    profile: str,
    tool_name: str,
    *,
    approval_confirmed: bool = False,
) -> ProfileToolDecision:
    decision = classify_profile_tool(
        profile,
        tool_name,
        approval_confirmed=approval_confirmed,
    )
    if not decision.allowed:
        raise PermissionError(
            f"profile tool blocked: {decision.profile} cannot use {decision.tool}: "
            f"{decision.decision}: {decision.reason}"
        )
    return decision


__all__ = [
    "ProfileToolDecision",
    "classify_profile_tool",
    "require_profile_tool",
]
