#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from link_profile_gate import _tool_map, classify_profile_tool


def classify(profile: str, tool: str, approved: bool = False):
    kwargs = {}
    signature = inspect.signature(classify_profile_tool)

    for name in (
        "approved",
        "approval_confirmed",
        "explicit_approval",
        "has_approval",
        "approved_by_human",
    ):
        if name in signature.parameters:
            kwargs[name] = approved
            break

    return classify_profile_tool(profile, tool, **kwargs)


def expect(profile: str, tool: str, expected: str, approved: bool = False):
    decision = classify(profile, tool, approved=approved)
    actual = decision.decision

    print(f"{profile} {tool} approved={approved} => {actual} - {decision.reason}")

    if actual != expected:
        raise AssertionError(
            f"{profile} {tool} expected {expected}, got {actual}: {decision.reason}"
        )

    if not decision.reason:
        raise AssertionError(f"{profile} {tool} returned an empty reason")

    return decision


def main() -> None:
    tools = _tool_map()

    if not isinstance(tools, dict):
        raise AssertionError("_tool_map must return a dictionary")

    for required in ("file_read", "file_write", "git_status", "capability_gate"):
        if required not in tools:
            raise AssertionError(f"_tool_map missing required tool: {required}")

    expect("read_only_auditor", "file_read", "allow")
    expect("read_only_auditor", "file_write", "deny")
    expect("research_only", "research_archive_miner", "allow")
    expect("research_only", "factory_execute", "deny")
    expect("patch_worker", "file_write", "caution")
    expect("patch_worker", "git_commit", "caution")
    expect("patch_worker", "file_write", "allow", approved=True)
    expect("self_update_preflight", "self_update_preflight", "allow")
    expect("self_update_preflight", "file_write", "deny")
    expect("missing_profile", "file_read", "deny")
    expect("read_only_auditor", "unknown_tool", "deny")

    print("profile gate regression checks passed")


if __name__ == "__main__":
    main()
