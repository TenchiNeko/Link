#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from link_tool_registry import HARD_BLOCKED_TOOLS, all_tools, resolve_toolsets, toolsets


RISK_ORDER = {
    "read": 0,
    "write": 1,
    "external": 2,
}


@dataclass(frozen=True)
class WorkerProfile:
    name: str
    purpose: str
    enabled_selectors: tuple[str, ...] = ()
    disabled_selectors: tuple[str, ...] = ()
    max_risk: str = "read"
    include_default_tools: bool = True
    include_approval_required_tools: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILES: tuple[WorkerProfile, ...] = (
    WorkerProfile(
        name="research_only",
        purpose="Mine docs, archives, and project context for Link-native upgrade ideas.",
        enabled_selectors=("research",),
        disabled_selectors=("file_write", "git_commit", "factory_execute", "workflow_step_executor"),
        max_risk="read",
        include_approval_required_tools=False,
        notes=(
            "Cannot write files.",
            "Cannot commit.",
            "Cannot execute external factory actions.",
        ),
    ),
    WorkerProfile(
        name="patch_worker",
        purpose="Apply small local patches after planning and safety checks.",
        enabled_selectors=("filesystem", "git", "safety", "self_update"),
        disabled_selectors=("factory_execute", "research_archive_miner"),
        max_risk="write",
        include_approval_required_tools=True,
        notes=(
            "May see write tools, but approval-required tools still need human approval.",
            "Must use snapshots, tests, and receipts.",
        ),
    ),
    WorkerProfile(
        name="qa_worker",
        purpose="Inspect diffs, run read-only checks, and review upgrade evidence.",
        enabled_selectors=("git", "filesystem", "workflow", "safety"),
        disabled_selectors=("file_write", "git_commit", "factory_execute", "workflow_step_executor"),
        max_risk="read",
        include_approval_required_tools=False,
        notes=(
            "Read-only by default.",
            "Should report findings instead of patching.",
        ),
    ),
    WorkerProfile(
        name="factory_planner",
        purpose="Create draft multi-agent plans without external execution.",
        enabled_selectors=("factory", "research", "safety"),
        disabled_selectors=("factory_execute", "file_write", "git_commit", "workflow_step_executor"),
        max_risk="write",
        include_approval_required_tools=False,
        notes=(
            "Planning only.",
            "No external action.",
        ),
    ),
    WorkerProfile(
        name="factory_executor",
        purpose="Execute approved factory work with strict approval and evidence requirements.",
        enabled_selectors=("factory", "workflow", "safety"),
        disabled_selectors=(),
        max_risk="external",
        include_approval_required_tools=True,
        notes=(
            "High-risk profile.",
            "Must have human approval before use.",
            "Must produce receipts.",
        ),
    ),
    WorkerProfile(
        name="self_update_preflight",
        purpose="Inspect whether Link is ready for a self-update and write a preflight receipt.",
        enabled_selectors=("self_update", "git", "safety"),
        disabled_selectors=("file_write", "git_commit", "factory_execute", "workflow_step_executor"),
        max_risk="write",
        include_approval_required_tools=False,
        notes=(
            "Preflight only.",
            "Does not apply patches.",
        ),
    ),
    WorkerProfile(
        name="read_only_auditor",
        purpose="Inspect repository state, files, diffs, and safety metadata without changing anything.",
        enabled_selectors=("git", "filesystem", "safety"),
        disabled_selectors=("file_write", "git_commit", "factory_execute", "workflow_step_executor"),
        max_risk="read",
        include_approval_required_tools=False,
        notes=(
            "Strictly read-only.",
            "Good default profile for first-pass audits.",
        ),
    ),
)


def _risk_value(risk: str) -> int:
    return RISK_ORDER.get(str(risk or "read").strip().lower(), 99)


def profile_map() -> dict[str, WorkerProfile]:
    return {profile.name: profile for profile in PROFILES}


def list_profiles() -> list[dict[str, Any]]:
    return [profile.to_dict() for profile in PROFILES]


def get_profile(name: str) -> WorkerProfile:
    profiles = profile_map()
    key = str(name or "").strip()
    if key not in profiles:
        available = ", ".join(sorted(profiles))
        raise KeyError(f"unknown worker profile: {key}. Available profiles: {available}")
    return profiles[key]


def resolve_profile_tools(name: str) -> list[dict[str, Any]]:
    profile = get_profile(name)
    tools = resolve_toolsets(
        profile.enabled_selectors,
        profile.disabled_selectors,
        include_default=profile.include_default_tools,
    )

    allowed = []
    max_risk = _risk_value(profile.max_risk)

    for tool in tools:
        if tool.name in HARD_BLOCKED_TOOLS:
            continue
        if _risk_value(tool.risk) > max_risk:
            continue
        if tool.requires_approval and not profile.include_approval_required_tools:
            continue
        allowed.append(tool)

    return [tool.to_dict() for tool in allowed]


def profile_summary(name: str) -> dict[str, Any]:
    profile = get_profile(name)
    tools = resolve_profile_tools(name)
    return {
        "profile": profile.to_dict(),
        "enabled_tools": tools,
        "enabled_tool_names": [tool["name"] for tool in tools],
    }


def all_profile_summaries() -> dict[str, Any]:
    return {
        "profiles": [profile_summary(profile.name) for profile in PROFILES],
        "available_toolsets": toolsets(),
        "hard_blocked_tools": sorted(HARD_BLOCKED_TOOLS),
    }


def validate_profiles() -> dict[str, Any]:
    known_tools = set(all_tools())
    known_toolsets = set(toolsets())
    profile_names = [profile.name for profile in PROFILES]

    duplicate_profiles = sorted({name for name in profile_names if profile_names.count(name) > 1})
    unknown_selectors: list[dict[str, str]] = []
    empty_profiles: list[str] = []
    approval_leaks: list[str] = []
    invalid_risks: list[str] = []

    for profile in PROFILES:
        if profile.max_risk not in RISK_ORDER:
            invalid_risks.append(profile.name)

        for selector in profile.enabled_selectors + profile.disabled_selectors:
            if selector not in known_tools and selector not in known_toolsets:
                unknown_selectors.append({"profile": profile.name, "selector": selector})

        resolved = resolve_profile_tools(profile.name)
        if not resolved:
            empty_profiles.append(profile.name)

        if not profile.include_approval_required_tools:
            for tool in resolved:
                if tool.get("requires_approval"):
                    approval_leaks.append(f"{profile.name}:{tool.get('name')}")

    return {
        "ok": not duplicate_profiles
        and not unknown_selectors
        and not empty_profiles
        and not approval_leaks
        and not invalid_risks,
        "profile_count": len(PROFILES),
        "duplicate_profiles": duplicate_profiles,
        "unknown_selectors": unknown_selectors,
        "empty_profiles": empty_profiles,
        "approval_leaks": approval_leaks,
        "invalid_risks": invalid_risks,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Inspect Link worker profiles.")
    parser.add_argument("--profile", default="", help="Show one profile instead of all profiles.")
    parser.add_argument("--validate", action="store_true", help="Validate profile definitions.")
    args = parser.parse_args()

    if args.validate:
        payload = validate_profiles()
    elif args.profile:
        payload = profile_summary(args.profile)
    else:
        payload = all_profile_summaries()

    print(json.dumps(payload, indent=2, sort_keys=True))
