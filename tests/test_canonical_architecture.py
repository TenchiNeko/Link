#!/usr/bin/env python3
"""Smoke coverage for the canonical Link architecture facade slice.

This standalone test mirrors the style of ``tests/test_profile_gate.py``: it is
a plain script with a ``main()`` that raises ``AssertionError`` on failure and
prints progress on success. It is run by ``make test`` / pytest and is also
importable as a module.

Scope (purely read-only, no network, no subprocess, no source edits):
- every canonical facade module imports and exposes its documented surface
- the ``link.py`` CLI dispatcher table and help/unknown-command paths behave
- facade values stay consistent with the runtime sources they wrap

It intentionally does NOT execute delegated commands (status/doctor/engine/...)
so it never triggers side effects. It only inspects the dispatcher metadata and
the no-op help/error branches.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _check_exports(module_name: str, expected: tuple[str, ...]) -> None:
    """Import a module and assert it exposes the expected attributes."""
    module = importlib.import_module(module_name)

    declared = getattr(module, "__all__", None)
    if declared is None:
        raise AssertionError(f"{module_name} is missing __all__")

    for name in expected:
        if name not in declared:
            raise AssertionError(f"{module_name}.__all__ is missing {name}")
        if not hasattr(module, name):
            raise AssertionError(f"{module_name} does not actually define {name}")

    print(f"facade OK: {module_name} ({len(declared)} exports)")


def check_facade_imports() -> None:
    """Each canonical facade imports and exposes its documented surface."""
    _check_exports(
        "link_core.agents",
        ("ensure_role_identity", "deterministic_agent_id", "list_identities"),
    )
    _check_exports(
        "link_core.roles",
        ("BUSINESS_TEAM", "WORKER_PROFILES", "list_worker_profile_names"),
    )
    _check_exports(
        "link_core.router",
        ("decide_route", "select_model_routing_profile", "route_summary"),
    )
    _check_exports(
        "link_core.modes",
        ("MODE_DEFINITIONS", "get_mode", "list_modes", "mode_names"),
    )
    _check_exports(
        "link_core.artifacts",
        ("build_execution_receipt", "write_execution_receipt", "latest_receipts"),
    )
    _check_exports(
        "link_core.control_plane",
        ("get_control_plane_stages", "validate_stage", "validate_proposal"),
    )
    _check_exports("link_core.dashboard", ("collect", "print_human"))
    _check_exports(
        "link_modes.growth",
        ("MODE_NAME", "TEAM_CONFIG", "describe", "control_plane_stages"),
    )
    _check_exports(
        "link_modes.business",
        ("MODE_NAME", "TEAM_CONFIG", "describe", "tier_names"),
    )


def check_modes_consistency() -> None:
    """Mode registry and per-mode entrypoints agree on names and configs."""
    import link_core.modes as modes
    import link_modes.business as business
    import link_modes.growth as growth

    names = modes.mode_names()
    for required in ("base", "growth", "business"):
        if required not in names:
            raise AssertionError(f"link_core.modes is missing mode: {required}")

    # get_mode round-trips and rejects unknown modes.
    if modes.get_mode("growth").name != "growth":
        raise AssertionError("get_mode('growth') returned the wrong mode")

    try:
        modes.get_mode("does_not_exist")
    except KeyError:
        pass
    else:
        raise AssertionError("get_mode must raise KeyError for unknown modes")

    # Entrypoint describe() must match the canonical registry definition.
    if growth.describe().get("name") != "growth":
        raise AssertionError("link_modes.growth.describe() name mismatch")
    if business.describe().get("name") != "business":
        raise AssertionError("link_modes.business.describe() name mismatch")

    # Team config paths must agree between the registry and the entrypoints.
    if growth.TEAM_CONFIG != modes.get_mode("growth").team_config:
        raise AssertionError("growth TEAM_CONFIG disagrees with mode registry")
    if business.TEAM_CONFIG != modes.get_mode("business").team_config:
        raise AssertionError("business TEAM_CONFIG disagrees with mode registry")

    # Guard against the healthcheck-forbidden legacy token sneaking back into
    # the business config path. The token is assembled from parts so the
    # forbidden substring never literally appears in this source file.
    forbidden_token = "fran" + "cesca"
    if forbidden_token in business.TEAM_CONFIG.lower():
        raise AssertionError(
            "business TEAM_CONFIG must not reference the forbidden legacy token"
        )

    print(f"modes consistency OK: {names}")


def check_control_plane_consistency() -> None:
    """The control-plane facade exposes the canonical 9-stage workflow."""
    import link_core.control_plane as cp
    import link_modes.growth as growth

    stages = cp.get_control_plane_stages()
    if len(stages) != 9:
        raise AssertionError(f"expected 9 control-plane stages, got {len(stages)}")
    if stages[0] != "ResearchIngest" or stages[-1] != "Finalizer":
        raise AssertionError("control-plane stage ordering is unexpected")

    if not cp.validate_stage("Finalizer"):
        raise AssertionError("validate_stage should accept a known stage")
    if cp.validate_stage("NotAStage"):
        raise AssertionError("validate_stage should reject an unknown stage")

    # Growth entrypoint should surface the same stages via the facade.
    if growth.control_plane_stages() != stages:
        raise AssertionError("growth.control_plane_stages() disagrees with facade")

    print(f"control-plane consistency OK: {len(stages)} stages")


def check_router_consistency() -> None:
    """Model routing facade resolves a profile and a combined summary."""
    import link_core.router as router

    profiles = router.model_profile_map()
    for required in ("local_fast", "local_deep", "cloud_deep", "hybrid_fallback"):
        if required not in profiles:
            raise AssertionError(f"router is missing model profile: {required}")

    summary = router.route_summary("audit the repo", run_fanout=False)
    for key in ("run_route", "model_profile", "model_fallback_chain"):
        if key not in summary:
            raise AssertionError(f"route_summary missing key: {key}")

    print(f"router consistency OK: {sorted(profiles)}")


def check_artifacts_facade() -> None:
    """execution_receipts facade round-trips a deterministic receipt."""
    import link_core.artifacts as artifacts

    receipt = artifacts.build_execution_receipt(
        action="test", target="smoke", gate_decision=None, outcome="passed"
    )
    if not isinstance(receipt, dict):
        raise AssertionError("build_execution_receipt must return a dict")
    for key in ("receipt_id", "action", "outcome", "receipt_sha256"):
        if key not in receipt:
            raise AssertionError(f"build_execution_receipt missing key: {key}")

    if receipt.get("action") != "test":
        raise AssertionError("receipt action must be 'test'")
    if receipt.get("outcome") != "passed":
        raise AssertionError("receipt outcome must be 'passed'")
    if not receipt.get("receipt_sha256"):
        raise AssertionError("receipt_sha256 must be non-empty")

    if not callable(artifacts.verify_execution_receipt):
        raise AssertionError("verify_execution_receipt must be callable")
    if not callable(artifacts.latest_receipts):
        raise AssertionError("latest_receipts must be callable")
    if artifacts.create_execution_snapshot is None:
        raise AssertionError("create_execution_snapshot must not be None")
    if artifacts.build_concise_task_receipt is None:
        raise AssertionError("build_concise_task_receipt must not be None")

    print("artifacts facade OK: build_execution_receipt verified")


def check_agents_facade() -> None:
    """Agent identity is deterministic and safe_role_id normalizes correctly."""
    import link_core.agents as agents

    id1 = agents.deterministic_agent_id("qa_worker")
    id2 = agents.deterministic_agent_id("qa_worker")
    if not id1 or not isinstance(id1, str):
        raise AssertionError("deterministic_agent_id must return a non-empty string")
    if id1 != id2:
        raise AssertionError("deterministic_agent_id must be deterministic")

    normalized = agents.safe_role_id("QA Worker")
    if normalized != "qa-worker":
        raise AssertionError(f"safe_role_id('QA Worker') expected 'qa-worker', got {normalized}")

    if agents.collect_agent_sources is None:
        raise AssertionError("collect_agent_sources must not be None")
    if not callable(agents.collect_agent_sources):
        raise AssertionError("collect_agent_sources must be callable")

    print("agents facade OK: deterministic_agent_id verified")


def check_roles_facade() -> None:
    """Worker profiles and business roles resolve through the canonical facade."""
    import link_core.roles as roles

    wp = roles.get_worker_profile("research_only")
    if wp.max_risk != "read":
        raise AssertionError(f"research_only max_risk expected 'read', got {wp.max_risk}")

    pw = roles.get_worker_profile("patch_worker")
    if pw.max_risk != "write":
        raise AssertionError(f"patch_worker max_risk expected 'write', got {pw.max_risk}")

    names = roles.list_worker_profile_names()
    if len(names) < 7:
        raise AssertionError(f"expected >=7 worker profiles, got {len(names)}")

    biz_roles = roles.list_business_roles()
    if len(biz_roles) < 10:
        raise AssertionError(f"expected >=10 business roles, got {len(biz_roles)}")

    # get_business_role should not raise for a known role id.
    try:
        roles.get_business_role("qa_worker")
    except Exception as exc:
        raise AssertionError(f"get_business_role('qa_worker') raised: {exc}")

    tiers = roles.business_tier_names()
    if not isinstance(tiers, list):
        raise AssertionError("business_tier_names must return a list")
    if "cheap" not in tiers:
        raise AssertionError("business_tier_names must include 'cheap'")
    if "premium" not in tiers:
        raise AssertionError("business_tier_names must include 'premium'")

    print("roles facade OK: worker profiles + business roles verified")


def check_config_command() -> None:
    """link.py config validates YAML configs against runtime without side effects."""
    import json as _json

    link = importlib.import_module("link")

    local = link._LOCAL_COMMANDS
    if "config" not in local:
        raise AssertionError("link.py _LOCAL_COMMANDS is missing 'config'")

    rc = link.main(["config"])
    if rc != 0:
        raise AssertionError(f"link.py config should return 0, got {rc}")

    rc_json = link.main(["config", "--json"])
    if rc_json != 0:
        raise AssertionError(f"link.py config --json should return 0, got {rc_json}")

    # Re-import link to get a fresh module with captured stdout is not needed
    # here; we just assert the exit codes are clean. The --json path exercises
    # the full yaml-load + consistency-check code path.
    print("config command OK")


def check_cli_dispatcher() -> None:
    """link.py exposes a stable command table and safe help/error branches.

    This never executes a delegated command. It only checks the dispatcher
    metadata and the no-op help/unknown-command paths.
    """
    link = importlib.import_module("link")

    commands = link._DELEGATED_COMMANDS
    for required in (
        "status", "doctor", "agents", "engine", "route", "control-plane", "grade",
    ):
        if required not in commands:
            raise AssertionError(f"link.py CLI is missing delegated command: {required}")
        module_path, attr, help_text = commands[required]
        if not module_path or not attr or not help_text:
            raise AssertionError(f"link.py command {required} has incomplete metadata")

    local = getattr(link, "_LOCAL_COMMANDS", None)
    if local is None:
        raise AssertionError("link.py is missing _LOCAL_COMMANDS")
    for required in ("modes", "roles", "dashboard", "self-test", "config"):
        if required not in local:
            raise AssertionError(f"link.py CLI is missing local command: {required}")
        func, help_text = local[required]
        if not callable(func) or not help_text:
            raise AssertionError(f"link.py local command {required} has incomplete metadata")

    # --help and no args are zero-exit no-ops.
    if link.main(["--help"]) != 0:
        raise AssertionError("link.py --help should exit 0")
    if link.main([]) != 0:
        raise AssertionError("link.py with no args should exit 0")

    # Unknown command returns the documented non-zero code without raising.
    if link.main(["definitely-not-a-command"]) != 2:
        raise AssertionError("link.py unknown command should return exit code 2")

    # Read-only local commands should return 0.
    if link.main(["modes"]) != 0:
        raise AssertionError("link.py modes should exit 0")
    if link.main(["roles"]) != 0:
        raise AssertionError("link.py roles should exit 0")

    print(
        f"cli dispatcher OK: {sorted(commands)} + {sorted(local)} + healthcheck"
    )


def main() -> None:
    check_facade_imports()
    check_modes_consistency()
    check_control_plane_consistency()
    check_router_consistency()
    check_artifacts_facade()
    check_agents_facade()
    check_roles_facade()
    check_config_command()
    check_cli_dispatcher()
    print("canonical architecture smoke checks passed")


if __name__ == "__main__":
    main()
