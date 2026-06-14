#!/usr/bin/env python3
"""Link canonical CLI entrypoint.

This is the single front-door CLI for Link. It is intentionally a thin
delegating layer: each subcommand forwards to an existing, working module
without changing its behavior. No patches, commits, pushes, or destructive
actions happen here.

The goal of this module is architectural clarity, not new behavior. As Link
migrates toward the clean ``link_core`` / ``link_modes`` structure, this file
stays the stable command surface while the modules underneath are reorganized.

Usage:
    python3 link.py <command> [args...]
    python3 link.py --help
    python3 link.py <command> --help
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent


# Commands that delegate to an external module's main() with adjusted argv.
_DELEGATED_COMMANDS: dict[str, tuple[str, str, str]] = {
    "status": ("link_status", "main", "Check Link runtime/model/web endpoints."),
    "doctor": (
        "link_core.diagnostics.link_doctor",
        "main",
        "Full Link diagnostics dashboard.",
    ),
    "agents": ("link_agents", "main", "List Link agent/model configuration sources."),
    "engine": ("link_engine", "main", "Supervised Link run engine."),
    "route": (
        "link_core.routing.link_route_intelligence",
        "main",
        "Deterministic pre-run route intelligence.",
    ),
    "grade": (
        "link_core.ops.link_grade",
        "main",
        "Generate branch/internal/market grade report.",
    ),
}


def _delegate(module_path: str, attr: str, argv: list[str]) -> int:
    """Call a delegated module's main() with a temporarily adjusted argv."""
    module = importlib.import_module(module_path)
    func: Callable[..., int] = getattr(module, attr)

    saved_argv = sys.argv
    sys.argv = [module_path, *argv]
    try:
        result = func()
    finally:
        sys.argv = saved_argv

    return int(result or 0)


def _run_healthcheck(argv: list[str]) -> int:
    """Run the canonical healthcheck as a subprocess (never imported here)."""
    cmd = [sys.executable, str(ROOT / "link_healthcheck.py"), *argv]
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return proc.returncode


# ---------------------------------------------------------------------------
# Local commands implemented inline using canonical facade imports.
# ---------------------------------------------------------------------------


def _cmd_modes(argv: list[str]) -> int:
    """Print available Link operating modes."""
    import json as _json

    from link_core.modes import list_modes as _list_modes

    modes = _list_modes()
    if "--json" in argv:
        print(_json.dumps(modes, indent=2))
        return 0

    for mode in modes:
        name = mode["name"]
        title = mode["title"]
        desc = mode["description"][:90]
        print(f"{name.ljust(12)}{title} -- {desc}")
    return 0


def _cmd_roles(argv: list[str]) -> int:
    """Print worker profiles and business/factory roles."""
    import json as _json

    from link_core.roles import list_business_roles as _business_roles
    from link_core.roles import list_worker_profile_names as _worker_names

    worker_names = _worker_names()
    business = _business_roles()

    if "--json" in argv:
        print(_json.dumps({
            "worker_profiles": worker_names,
            "business_roles": [
                {
                    "role_id": role.get("role_id", ""),
                    "title": role.get("title", ""),
                    "department": role.get("department", ""),
                }
                for role in business
            ],
        }, indent=2))
        return 0

    print("Worker profiles:")
    for name in worker_names:
        print(f"  - {name}")

    if business:
        print("")
        print("Business roles:")
        for role in business:
            role_id = role.get("role_id", "")
            title = role.get("title", "")
            dept = role.get("department", "")
            print(f"  - {role_id.ljust(22)}{title.ljust(24)}({dept})")
    return 0



def _cmd_modules(argv: list[str]) -> int:
    """Print Link module boundary views."""
    subcommand = argv[0] if argv else ""
    if subcommand == "boundary-registry":
        from link_modes.growth.link_growth_console import module_boundary_registry_main as _module_boundary_registry_main

        return _module_boundary_registry_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Link modules commands:")
        print("  boundary-registry Preview Link module boundary registry")
        return 0
    print(f"modules: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py modules --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_research(argv: list[str]) -> int:
    """Read-only local research target intake and evidence views."""
    subcommand = argv[0] if argv else ""
    if subcommand == "advisor-review":
        from link_modes.growth.link_growth_console import research_advisor_review_main as _research_advisor_review_main

        return _research_advisor_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "advisor-comparison":
        from link_modes.growth.link_growth_console import research_advisor_comparison_main as _research_advisor_comparison_main

        return _research_advisor_comparison_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "advisor-two-stage":
        from link_modes.growth.link_growth_console import research_advisor_two_stage_main as _research_advisor_two_stage_main

        return _research_advisor_two_stage_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-binding":
        from link_modes.growth.link_growth_console import research_source_binding_main as _research_source_binding_main

        return _research_source_binding_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-operator-flow":
        from link_modes.growth.link_growth_console import source_aware_operator_flow_main as _source_aware_operator_flow_main

        return _source_aware_operator_flow_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-operator-report":
        from link_modes.growth.link_growth_console import research_target_operator_report_main as _research_target_operator_report_main

        return _research_target_operator_report_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-implementation-preview":
        from link_modes.growth.link_growth_console import research_target_implementation_preview_main as _research_target_implementation_preview_main

        return _research_target_implementation_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-sandbox-flow":
        from link_modes.growth.link_growth_console import research_target_sandbox_flow_main as _research_target_sandbox_flow_main

        return _research_target_sandbox_flow_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-provenance":
        from link_modes.growth.link_growth_console import research_target_provenance_main as _research_target_provenance_main

        return _research_target_provenance_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-patterns":
        from link_modes.growth.link_growth_console import research_target_patterns_main as _research_target_patterns_main

        return _research_target_patterns_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-concepts":
        from link_modes.growth.link_growth_console import research_archive_concepts_main as _research_archive_concepts_main

        return _research_archive_concepts_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "compression-profile":
        from link_modes.growth.link_growth_console import research_compression_profile_main as _research_compression_profile_main

        return _research_compression_profile_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "compression-upgrade-score":
        from link_modes.growth.link_growth_console import research_compression_upgrade_score_main as _research_compression_upgrade_score_main

        return _research_compression_upgrade_score_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "upgrade-genericity":
        from link_modes.growth.link_growth_console import research_upgrade_genericity_main as _research_upgrade_genericity_main

        return _research_upgrade_genericity_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-upgrade-rationale":
        from link_modes.growth.link_growth_console import research_target_upgrade_rationale_main as _research_target_upgrade_rationale_main

        return _research_target_upgrade_rationale_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-specificity":
        from link_modes.growth.link_growth_console import research_target_specificity_main as _research_target_specificity_main

        return _research_target_specificity_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-intake":
        from link_modes.growth.link_growth_console import research_target_intake_main as _research_target_intake_main

        return _research_target_intake_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-evidence":
        from link_modes.growth.link_growth_console import research_target_evidence_main as _research_target_evidence_main

        return _research_target_evidence_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-upgrades":
        from link_modes.growth.link_growth_console import research_target_upgrades_main as _research_target_upgrades_main

        return _research_target_upgrades_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-task-draft":
        from link_modes.growth.link_growth_console import research_target_task_draft_main as _research_target_task_draft_main

        return _research_target_task_draft_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-flow":
        from link_modes.growth.link_growth_console import research_target_flow_main as _research_target_flow_main

        return _research_target_flow_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Link research commands:")
        print("  advisor-review       Preview or run local-only research advisor review")
        print("  advisor-comparison   Compare deterministic output with advisor review")
        print("  advisor-two-stage    Gate richer local advisor review behind JSON check")
        print("  source-binding        Build a downstream source binding context")
        print("  source-operator-flow  Preview source-bound downstream operator flow")
        print("  target-operator-report Preview compact source-aware operator report")
        print("  target-implementation-preview Preview source-bound implementation scope")
        print("  target-sandbox-flow   Preview source target to sandbox boundary flow")
        print("  target-provenance     Preview compact source provenance table")
        print("  target-patterns       Preview source-specific pattern summary")
        print("  archive-concepts      Extract deterministic archive concepts")
        print("  compression-profile   Profile compression/context repos")
        print("  compression-upgrade-score Score compression-specific upgrades")
        print("  upgrade-genericity  Assess generic vs concept-supported upgrades")
        print("  target-upgrade-rationale Explain why the selected upgrade fits the target")
        print("  target-specificity    Score whether the recommendation is target-specific")
        print("  target-intake         Inspect a local research target without extraction")
        print("  target-evidence       Build evidence refs for a local research target")
        print("  target-upgrades       Preview Link upgrade candidates from a target")
        print("  target-task-draft     Preview a target-bound operator task draft")
        print("  target-flow           Preview target intake -> evidence -> task flow")
        return 0
    print(f"research: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py research --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_advisor(argv: list[str]) -> int:
    """Read-only local advisor configuration previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "providers":
        from link_modes.growth.link_growth_console import advisor_providers_main as _advisor_providers_main

        return _advisor_providers_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "provider-boundary":
        from link_modes.growth.link_growth_console import advisor_provider_boundary_main as _advisor_provider_boundary_main

        return _advisor_provider_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "openrouter-config":
        from link_modes.growth.link_growth_console import advisor_openrouter_config_main as _advisor_openrouter_config_main

        return _advisor_openrouter_config_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "local-status":
        from link_modes.growth.link_growth_console import advisor_local_status_main as _advisor_local_status_main

        return _advisor_local_status_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "openrouter-status":
        from link_modes.growth.link_growth_console import advisor_openrouter_status_main as _advisor_openrouter_status_main

        return _advisor_openrouter_status_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "status":
        from link_modes.growth.link_growth_console import advisor_status_main as _advisor_status_main

        return _advisor_status_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "guidance":
        from link_modes.growth.link_growth_console import advisor_guidance_main as _advisor_guidance_main

        return _advisor_guidance_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-command":
        from link_modes.growth.link_growth_console import advisor_target_command_main as _advisor_target_command_main

        return _advisor_target_command_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "ref-alias-map":
        from link_modes.growth.link_growth_console import advisor_ref_alias_map_main as _advisor_ref_alias_map_main

        return _advisor_ref_alias_map_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "headroom-descriptor":
        from link_modes.growth.link_growth_console import advisor_headroom_descriptor_main as _advisor_headroom_descriptor_main

        return _advisor_headroom_descriptor_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "headroom-policy":
        from link_modes.growth.link_growth_console import advisor_headroom_policy_main as _advisor_headroom_policy_main

        return _advisor_headroom_policy_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "headroom-preview":
        from link_modes.growth.link_growth_console import advisor_headroom_preview_main as _advisor_headroom_preview_main

        return _advisor_headroom_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "headroom-adapter":
        from link_modes.growth.link_growth_console import advisor_headroom_adapter_main as _advisor_headroom_adapter_main

        return _advisor_headroom_adapter_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "headroom-sample":
        from link_modes.growth.link_growth_console import advisor_headroom_sample_main as _advisor_headroom_sample_main

        return _advisor_headroom_sample_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "headroom-gate":
        from link_modes.growth.link_growth_console import advisor_headroom_gate_main as _advisor_headroom_gate_main

        return _advisor_headroom_gate_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "compression-policy":
        from link_modes.growth.link_growth_console import advisor_compression_policy_main as _advisor_compression_policy_main

        return _advisor_compression_policy_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "compression-preview":
        from link_modes.growth.link_growth_console import advisor_compression_preview_main as _advisor_compression_preview_main

        return _advisor_compression_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "micro-contract":
        from link_modes.growth.link_growth_console import advisor_micro_contract_main as _advisor_micro_contract_main

        return _advisor_micro_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "micro-check":
        from link_modes.growth.link_growth_console import advisor_micro_check_main as _advisor_micro_check_main

        return _advisor_micro_check_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "micro-diagnostic":
        from link_modes.growth.link_growth_console import advisor_micro_diagnostic_main as _advisor_micro_diagnostic_main

        return _advisor_micro_diagnostic_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "json-contract":
        from link_modes.growth.link_growth_console import advisor_json_contract_main as _advisor_json_contract_main

        return _advisor_json_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "json-check":
        from link_modes.growth.link_growth_console import advisor_json_check_main as _advisor_json_check_main

        return _advisor_json_check_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "local-json-diagnostic":
        from link_modes.growth.link_growth_console import advisor_local_json_diagnostic_main as _advisor_local_json_diagnostic_main

        return _advisor_local_json_diagnostic_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "prompt-budget":
        from link_modes.growth.link_growth_console import advisor_prompt_budget_main as _advisor_prompt_budget_main

        return _advisor_prompt_budget_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "compact-context":
        from link_modes.growth.link_growth_console import advisor_compact_context_main as _advisor_compact_context_main

        return _advisor_compact_context_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "smoke-receipt":
        from link_modes.growth.link_growth_console import advisor_smoke_receipt_main as _advisor_smoke_receipt_main

        return _advisor_smoke_receipt_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "smoke":
        from link_modes.growth.link_growth_console import advisor_smoke_main as _advisor_smoke_main

        return _advisor_smoke_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "local-smoke":
        from link_modes.growth.link_growth_console import advisor_local_smoke_main as _advisor_local_smoke_main

        return _advisor_local_smoke_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "local-config":
        from link_modes.growth.link_growth_console import advisor_local_config_main as _advisor_local_config_main

        return _advisor_local_config_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Advisor commands:")
        print("  providers         Preview advisor provider registry")
        print("  provider-boundary Preview canonical local llama.cpp provider boundary")
        print("  openrouter-config Preview redacted OpenRouter advisor config")
        print("  local-status      Preview local llama.cpp availability")
        print("  openrouter-status Preview redacted OpenRouter readiness")
        print("  status            Show compact advisor provider status")
        print("  guidance          Show advisor provider operator guidance")
        print("  target-command    Preview safe advisor commands for a selected source")
        print("  ref-alias-map     Preview deterministic S/E ref aliases")
        print("  headroom-descriptor Preview Headroom compression repo descriptor")
        print("  headroom-policy Preview Headroom advisor compression policy")
        print("  headroom-preview Preview selected-source Headroom compression readiness")
        print("  headroom-adapter Preview Headroom local adapter contract")
        print("  headroom-sample Preview/run tiny Headroom adapter fixture")
        print("  headroom-gate Preview Headroom adapter integration gate")
        print("  compression-policy Preview optional advisor context compression boundary")
        print("  compression-preview Preview selected-source compression readiness")
        print("  micro-contract    Preview staged tiny local JSON contract")
        print("  micro-check       Run one staged local JSON micro-check")
        print("  micro-diagnostic  Run staged local JSON diagnostics")
        print("  json-contract     Preview minimal source-bound local JSON contract")
        print("  json-check        Run minimal local JSON contract check")
        print("  local-json-diagnostic Diagnose local llama.cpp JSON behavior")
        print("  prompt-budget     Preview compact local advisor prompt budget")
        print("  compact-context   Preview compact source-aware advisor context")
        print("  smoke-receipt     Preview latest local advisor smoke receipt status")
        print("  smoke             Preview or run explicit provider smoke")
        print("  local-smoke       Preview or run bounded local llama.cpp smoke")
        print("  local-config      Preview safe local model advisor configuration")
        return 0
    print(f"advisor: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py advisor --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_business_development(argv: list[str]) -> int:
    """Business Development governance previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "intake-preview":
        from link_modes.growth.link_growth_console import business_development_intake_preview_main as _bd_intake_preview_main

        return _bd_intake_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence-contract":
        from link_modes.growth.link_growth_console import business_development_evidence_contract_main as _bd_evidence_contract_main

        return _bd_evidence_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "approval-checklist":
        from link_modes.growth.link_growth_console import business_development_approval_checklist_main as _bd_approval_checklist_main

        return _bd_approval_checklist_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import business_development_review_main as _bd_review_main

        return _bd_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-boundary":
        from link_modes.growth.link_growth_console import business_development_source_boundary_main as _bd_source_boundary_main

        return _bd_source_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-evidence-contract":
        from link_modes.growth.link_growth_console import business_development_source_evidence_contract_main as _bd_source_evidence_contract_main

        return _bd_source_evidence_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-review":
        from link_modes.growth.link_growth_console import business_development_source_review_main as _bd_source_review_main

        return _bd_source_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cards":
        from link_modes.growth.link_growth_console import business_development_source_cards_main as _bd_source_cards_main

        return _bd_source_cards_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "collection-plan-preview":
        from link_modes.growth.link_growth_console import business_development_collection_plan_preview_main as _bd_collection_plan_preview_main

        return _bd_collection_plan_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "collection-approval-checklist":
        from link_modes.growth.link_growth_console import business_development_collection_approval_checklist_main as _bd_collection_approval_checklist_main

        return _bd_collection_approval_checklist_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "collection-review":
        from link_modes.growth.link_growth_console import business_development_collection_review_main as _bd_collection_review_main

        return _bd_collection_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Business Development commands:")
        print("  intake-preview                  Preview Business Development intake")
        print("  evidence-contract               Preview Business Development evidence contract")
        print("  approval-checklist              Preview Business Development approval checklist")
        print("  review                          Preview Business Development review package")
        print("  source-boundary                 Preview Business Development source boundary")
        print("  source-evidence-contract        Preview Business Development source evidence contract")
        print("  source-review                   Preview Business Development source review package")
        print("  source-cards                    Preview Business Development source card registry")
        print("  collection-plan-preview         Preview Business Development collection plan")
        print("  collection-approval-checklist   Preview Business Development collection approvals")
        print("  collection-review               Preview Business Development collection review")
        return 0
    print(f"business-development: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py business-development --help' for subcommands.", file=sys.stderr)
    return 2

def _cmd_business_operations(argv: list[str]) -> int:
    """Business Operations governance previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "intake-preview":
        from link_modes.growth.link_growth_console import business_operations_intake_preview_main as _bo_intake_preview_main

        return _bo_intake_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence-contract":
        from link_modes.growth.link_growth_console import business_operations_evidence_contract_main as _bo_evidence_contract_main

        return _bo_evidence_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "approval-checklist":
        from link_modes.growth.link_growth_console import business_operations_approval_checklist_main as _bo_approval_checklist_main

        return _bo_approval_checklist_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import business_operations_review_main as _bo_review_main

        return _bo_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "operating-model-preview":
        from link_modes.growth.link_growth_console import business_operations_operating_model_preview_main as _bo_operating_model_main

        return _bo_operating_model_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "risk-boundary":
        from link_modes.growth.link_growth_console import operations_risk_boundary_main as _bo_risk_boundary_main

        return _bo_risk_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence-review":
        from link_modes.growth.link_growth_console import operations_evidence_review_main as _bo_evidence_review_main

        return _bo_evidence_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Business Operations commands:")
        print("  intake-preview           Preview Business Operations intake")
        print("  evidence-contract        Preview Business Operations evidence contract")
        print("  approval-checklist       Preview Business Operations approval checklist")
        print("  review                   Preview Business Operations review package")
        print("  operating-model-preview  Preview Business Operations operating model")
        print("  risk-boundary            Preview Operations risk boundary")
        print("  evidence-review          Preview Operations evidence review")
        return 0
    print(f"business-operations: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py business-operations --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_business(argv: list[str]) -> int:
    """Cross-lane business governance previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "readiness-review":
        from link_modes.growth.link_growth_console import business_readiness_review_main as _business_readiness_review_main

        return _business_readiness_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-boundary":
        from link_modes.growth.link_growth_console import business_execution_boundary_main as _business_execution_boundary_main

        return _business_execution_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-evidence-contract":
        from link_modes.growth.link_growth_console import business_execution_evidence_contract_main as _business_execution_evidence_contract_main

        return _business_execution_evidence_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-approval-checklist":
        from link_modes.growth.link_growth_console import business_execution_approval_checklist_main as _business_execution_approval_checklist_main

        return _business_execution_approval_checklist_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-review":
        from link_modes.growth.link_growth_console import business_execution_review_main as _business_execution_review_main

        return _business_execution_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Business commands:")
        print("  readiness-review              Preview cross-lane business readiness")
        print("  execution-boundary            Preview final business execution boundary")
        print("  execution-evidence-contract   Preview final business execution evidence contract")
        print("  execution-approval-checklist  Preview final business execution approval checklist")
        print("  execution-review              Preview final business execution review")
        return 0
    print(f"business: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py business --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_governance(argv: list[str]) -> int:
    """Unified Link governance dashboard previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "dashboard":
        from link_modes.growth.link_growth_console import governance_dashboard_main as _governance_dashboard_main

        return _governance_dashboard_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "risk":
        from link_modes.growth.link_growth_console import governance_risk_main as _governance_risk_main

        return _governance_risk_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "readiness":
        from link_modes.growth.link_growth_console import governance_readiness_main as _governance_readiness_main

        return _governance_readiness_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import governance_review_main as _governance_review_main

        return _governance_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Governance commands:")
        print("  dashboard  Preview unified governance dashboard summary")
        print("  risk       Preview cross-lane governance risk dashboard")
        print("  readiness  Preview cross-lane governance readiness dashboard")
        print("  review     Preview executive governance review package")
        return 0
    print(f"governance: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py governance --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_control_plane(argv: list[str]) -> int:
    """Link control-plane dashboard and health previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "dashboard":
        from link_modes.growth.link_growth_console import control_plane_dashboard_main as _control_plane_dashboard_main

        return _control_plane_dashboard_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "services":
        from link_modes.growth.link_growth_console import control_plane_services_main as _control_plane_services_main

        return _control_plane_services_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "health":
        from link_modes.growth.link_growth_console import control_plane_health_main as _control_plane_health_main

        return _control_plane_health_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import control_plane_review_main as _control_plane_review_main

        return _control_plane_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "status":
        from link_modes.growth.link_growth_console import control_plane_status_main as _control_plane_status_main

        return _control_plane_status_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-status":
        from link_modes.growth.link_growth_console import control_plane_target_status_main as _control_plane_target_status_main

        return _control_plane_target_status_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "operator-cards":
        from link_modes.growth.link_growth_console import control_plane_operator_cards_main as _control_plane_operator_cards_main

        return _control_plane_operator_cards_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "stale-artifacts":
        from link_modes.growth.link_growth_console import control_plane_stale_artifacts_main as _control_plane_stale_artifacts_main

        return _control_plane_stale_artifacts_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "operator-review":
        from link_modes.growth.link_growth_console import control_plane_operator_review_main as _control_plane_operator_review_main

        return _control_plane_operator_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Control-plane commands:")
        print("  dashboard        Preview Link control-plane dashboard")
        print("  services         Preview Link shared services dashboard")
        print("  health           Preview Link control-plane health package")
        print("  review           Preview Link control-plane review package")
        print("  status           Preview compact operator status summary")
        print("  target-status    Preview selected research target status")
        print("  operator-cards   Preview operator-facing lane cards")
        print("  stale-artifacts  Preview stale generated artifact report")
        print("  operator-review  Preview operator status review package")
        return 0
    print(f"control-plane: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py control-plane --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_simulation(argv: list[str]) -> int:
    """Dry-run business execution simulation previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "plan":
        from link_modes.growth.link_growth_console import business_execution_simulation_plan_main as _simulation_plan_main

        return _simulation_plan_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence":
        from link_modes.growth.link_growth_console import business_execution_simulation_evidence_main as _simulation_evidence_main

        return _simulation_evidence_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import business_execution_simulation_review_main as _simulation_review_main

        return _simulation_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "readiness":
        from link_modes.growth.link_growth_console import business_execution_simulation_readiness_main as _simulation_readiness_main

        return _simulation_readiness_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "dashboard":
        from link_modes.growth.link_growth_console import simulation_dashboard_main as _simulation_dashboard_main

        return _simulation_dashboard_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "gaps":
        from link_modes.growth.link_growth_console import execution_gap_analysis_main as _simulation_gaps_main

        return _simulation_gaps_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "score":
        from link_modes.growth.link_growth_console import execution_readiness_score_main as _simulation_score_main

        return _simulation_score_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "operator-review":
        from link_modes.growth.link_growth_console import operator_simulation_review_main as _simulation_operator_review_main

        return _simulation_operator_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "remediation-plan":
        from link_modes.growth.link_growth_console import simulation_remediation_plan_main as _simulation_remediation_plan_main

        return _simulation_remediation_plan_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "dependency-graph":
        from link_modes.growth.link_growth_console import remediation_dependency_graph_main as _simulation_dependency_graph_main

        return _simulation_dependency_graph_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "priority-queue":
        from link_modes.growth.link_growth_console import remediation_priority_queue_main as _simulation_priority_queue_main

        return _simulation_priority_queue_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "remediation-review":
        from link_modes.growth.link_growth_console import operator_remediation_review_main as _simulation_remediation_review_main

        return _simulation_remediation_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Simulation commands:")
        print("  plan                Preview dry-run business execution simulation plan")
        print("  evidence            Preview simulated execution evidence package")
        print("  review              Preview simulated execution review")
        print("  readiness           Preview simulated execution readiness check")
        print("  dashboard           Preview compact simulation dashboard")
        print("  gaps                Preview execution gap analysis")
        print("  score               Preview deterministic execution readiness score")
        print("  operator-review     Preview operator-facing simulation analysis package")
        print("  remediation-plan    Preview simulation remediation plan")
        print("  dependency-graph    Preview remediation dependency graph")
        print("  priority-queue      Preview remediation priority queue")
        print("  remediation-review  Preview operator remediation review")
        return 0
    print(f"simulation: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py simulation --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_sandbox(argv: list[str]) -> int:
    """Read-only execution readiness sandbox projections."""
    subcommand = argv[0] if argv else ""
    if subcommand == "readiness":
        from link_modes.growth.link_growth_console import sandbox_readiness_main as _sandbox_readiness_main

        return _sandbox_readiness_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence":
        from link_modes.growth.link_growth_console import sandbox_evidence_main as _sandbox_evidence_main

        return _sandbox_evidence_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "approvals":
        from link_modes.growth.link_growth_console import sandbox_approvals_main as _sandbox_approvals_main

        return _sandbox_approvals_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "outcome":
        from link_modes.growth.link_growth_console import sandbox_outcome_main as _sandbox_outcome_main

        return _sandbox_outcome_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import sandbox_review_main as _sandbox_review_main

        return _sandbox_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Sandbox commands:")
        print("  readiness  Preview projected readiness after remediation")
        print("  evidence   Preview projected evidence after remediation")
        print("  approvals  Preview projected approvals after remediation")
        print("  outcome    Preview projected execution outcome")
        print("  review     Preview operator sandbox review package")
        return 0
    print(f"sandbox: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py sandbox --help' for subcommands.", file=sys.stderr)
    return 2


def _cmd_decision(argv: list[str]) -> int:
    """Read-only operator decision support previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "candidates":
        from link_modes.growth.link_growth_console import decision_candidate_set_main as _decision_candidate_set_main

        return _decision_candidate_set_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "impact":
        from link_modes.growth.link_growth_console import decision_impact_analysis_main as _decision_impact_analysis_main

        return _decision_impact_analysis_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "ranking":
        from link_modes.growth.link_growth_console import decision_ranking_main as _decision_ranking_main

        return _decision_ranking_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import operator_decision_review_main as _operator_decision_review_main

        return _operator_decision_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "score-breakdown":
        from link_modes.growth.link_growth_console import decision_score_breakdown_main as _decision_score_breakdown_main

        return _decision_score_breakdown_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "rejected-alternatives":
        from link_modes.growth.link_growth_console import rejected_alternative_analysis_main as _rejected_alternative_analysis_main

        return _rejected_alternative_analysis_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "assumptions":
        from link_modes.growth.link_growth_console import decision_assumption_ledger_main as _decision_assumption_ledger_main

        return _decision_assumption_ledger_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "trace":
        from link_modes.growth.link_growth_console import operator_decision_trace_package_main as _operator_decision_trace_package_main

        return _operator_decision_trace_package_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-card":
        from link_modes.growth.link_growth_console import decision_target_card_main as _decision_target_card_main

        return _decision_target_card_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Decision commands:")
        print("  candidates              Preview remediation decision candidates")
        print("  impact                  Preview deterministic candidate impact analysis")
        print("  ranking                 Preview deterministic candidate ranking")
        print("  review                  Preview operator decision recommendation")
        print("  score-breakdown         Explain score components for each candidate")
        print("  rejected-alternatives   Explain why non-top candidates lost")
        print("  assumptions             Preview recommendation assumption ledger")
        print("  trace                   Preview operator decision trace package")
        print("  target-card             Preview selected research target decision card")
        return 0
    print(f"decision: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py decision --help' for subcommands.", file=sys.stderr)
    return 2



def _cmd_sandbox_executor(argv: list[str]) -> int:
    """Read-only sandbox executor boundary previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "boundary":
        from link_modes.growth.link_growth_console import sandbox_task_executor_boundary_main as _sandbox_executor_boundary_main

        return _sandbox_executor_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence":
        from link_modes.growth.link_growth_console import sandbox_execution_evidence_contract_main as _sandbox_executor_evidence_main

        return _sandbox_executor_evidence_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "approvals":
        from link_modes.growth.link_growth_console import sandbox_execution_approval_checklist_main as _sandbox_executor_approvals_main

        return _sandbox_executor_approvals_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "review":
        from link_modes.growth.link_growth_console import sandbox_execution_review_package_main as _sandbox_executor_review_main

        return _sandbox_executor_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Sandbox executor commands:")
        print("  boundary   Preview sandbox task executor boundary")
        print("  evidence   Preview sandbox execution evidence contract")
        print("  approvals  Preview sandbox execution approval checklist")
        print("  review     Preview sandbox execution review package")
        return 0
    print(f"sandbox-executor: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py sandbox-executor --help' for subcommands.", file=sys.stderr)
    return 2



def _cmd_operator(argv: list[str]) -> int:
    """Read-only operator action planning previews."""
    subcommand = argv[0] if argv else ""
    if subcommand == "action-plan":
        from link_modes.growth.link_growth_console import operator_action_plan_preview_main as _operator_action_plan_main

        return _operator_action_plan_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "action-evidence":
        from link_modes.growth.link_growth_console import operator_action_evidence_checklist_main as _operator_action_evidence_main

        return _operator_action_evidence_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "action-approvals":
        from link_modes.growth.link_growth_console import operator_action_approval_checklist_main as _operator_action_approvals_main

        return _operator_action_approvals_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "action-review":
        from link_modes.growth.link_growth_console import operator_action_review_package_main as _operator_action_review_main

        return _operator_action_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "task-draft":
        from link_modes.growth.link_growth_console import operator_task_draft_main as _operator_task_draft_main

        return _operator_task_draft_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "task-scope":
        from link_modes.growth.link_growth_console import operator_task_scope_review_main as _operator_task_scope_main

        return _operator_task_scope_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "task-tests":
        from link_modes.growth.link_growth_console import operator_task_test_plan_main as _operator_task_tests_main

        return _operator_task_tests_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "task-review":
        from link_modes.growth.link_growth_console import operator_task_review_package_main as _operator_task_review_main

        return _operator_task_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "target-review":
        from link_modes.growth.link_growth_console import operator_target_review_main as _operator_target_review_main

        return _operator_target_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-dashboard":
        from link_modes.growth.link_growth_console import operator_source_dashboard_main as _operator_source_dashboard_main

        return _operator_source_dashboard_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help", ""):
        print("Operator commands:")
        print("  action-plan       Preview the concrete next operator action plan")
        print("  action-evidence   Preview evidence required for the action plan")
        print("  action-approvals  Preview approvals required for the action plan")
        print("  action-review     Preview operator action review package")
        print("  task-draft        Preview the exact non-executable unit of work")
        print("  task-scope        Preview task scope and boundary review")
        print("  task-tests        Preview task verification plan")
        print("  task-review       Preview operator task review package")
        print("  target-review     Preview selected research target review")
        print("  source-dashboard  Preview selected research target dashboard")
        return 0
    print(f"operator: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py operator --help' for subcommands.", file=sys.stderr)
    return 2



def _cmd_dashboard(argv: list[str]) -> int:
    """Print a compact dashboard/status summary."""
    from link_core.dashboard import collect as _collect
    from link_core.dashboard import print_human as _print_human

    data = _collect()
    if data is None:
        print("dashboard: could not collect diagnostics data", file=sys.stderr)
        return 1

    if "--json" in argv:
        import json as _json
        print(_json.dumps(data, indent=2, default=str))
        return 0

    _print_human(data)
    return 0


def _cmd_self_test(argv: list[str]) -> int:
    """Run canonical architecture smoke checks (import + CLI)."""
    try:
        from tests.test_canonical_architecture import main as _run_smoke
    except ImportError as exc:
        print(f"link self-test: cannot import smoke test: {exc}", file=sys.stderr)
        return 1

    try:
        _run_smoke()
    except AssertionError as exc:
        print(f"link self-test FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"link self-test ERROR: {exc}", file=sys.stderr)
        return 1

    print("link self-test passed")
    return 0


def _cmd_config(argv: list[str]) -> int:
    """Read and validate Link YAML configuration files."""
    try:
        import yaml as _yaml
    except ImportError:
        print("config: PyYAML is not installed. Install with: pip install pyyaml", file=sys.stderr)
        return 1

    import json as _json

    config_root = ROOT / "configs"
    config_files = [
        ("configs/models.yaml", "Model routing", "models.yaml"),
        ("configs/teams/link_growth.yaml", "Growth team", "link_growth.yaml"),
        ("configs/teams/business_ops.yaml", "Business ops team", "business_ops.yaml"),
    ]

    file_results: list[dict] = []
    checks: list[dict] = []
    problems = 0

    for rel_path, label, basename in config_files:
        full_path = ROOT / rel_path
        entry: dict = {"label": label, "path": rel_path, "exists": False}
        if not full_path.is_file():
            entry["status"] = "missing"
            problems += 1
            file_results.append(entry)
            continue
        entry["exists"] = True
        try:
            data = _yaml.safe_load(full_path.read_text(encoding="utf-8"))
        except Exception as exc:
            entry["status"] = "parse_error"
            entry["error"] = str(exc)
            problems += 1
            file_results.append(entry)
            continue
        version = data.get("version", "unknown") if isinstance(data, dict) else "unknown"
        entry["status"] = "ok"
        entry["version"] = version
        entry["top_keys"] = list(data.keys()) if isinstance(data, dict) else []
        file_results.append(entry)

    # Model profiles consistency check.
    try:
        from link_core.router import model_profile_map as _runtime_profiles

        runtime_names = set(_runtime_profiles().keys())
        models_yaml = config_root / "models.yaml"
        if models_yaml.is_file():
            yaml_data = _yaml.safe_load(models_yaml.read_text(encoding="utf-8"))
            yaml_profiles = yaml_data.get("profiles", {}) if isinstance(yaml_data, dict) else {}
            yaml_names = set(yaml_profiles.keys())
            match = yaml_names == runtime_names
            checks.append({
                "label": "model profiles match runtime",
                "ok": match,
                "detail": f"{len(runtime_names)} runtime profiles, {len(yaml_names)} in yaml",
            })
            if not match:
                checks[-1]["yaml_only"] = sorted(yaml_names - runtime_names)
                checks[-1]["runtime_only"] = sorted(runtime_names - yaml_names)
                problems += 1
    except Exception as exc:
        checks.append({"label": "model profiles match runtime", "ok": False, "detail": str(exc)})
        problems += 1

    # Growth control-plane stages check.
    try:
        from link_core.control_plane import get_control_plane_stages as _runtime_stages

        growth_yaml = config_root / "teams" / "link_growth.yaml"
        if growth_yaml.is_file():
            yaml_data = _yaml.safe_load(growth_yaml.read_text(encoding="utf-8"))
            yaml_stages = yaml_data.get("control_plane_stages", []) if isinstance(yaml_data, dict) else []
            runtime_stages = list(_runtime_stages())
            match = yaml_stages == runtime_stages
            checks.append({
                "label": "growth control-plane stages match runtime",
                "ok": match,
                "detail": f"{len(runtime_stages)} runtime stages, {len(yaml_stages)} in yaml",
            })
            if not match:
                problems += 1
    except Exception as exc:
        checks.append({"label": "growth control-plane stages match runtime", "ok": False, "detail": str(exc)})
        problems += 1

    # Business tiers check.
    try:
        from link_core.roles import business_tier_names as _runtime_tiers

        biz_yaml = config_root / "teams" / "business_ops.yaml"
        if biz_yaml.is_file():
            yaml_data = _yaml.safe_load(biz_yaml.read_text(encoding="utf-8"))
            yaml_tiers = yaml_data.get("tiers", []) if isinstance(yaml_data, dict) else []
            runtime_tier_list = _runtime_tiers()
            runtime_tier_set = set(runtime_tier_list)
            missing = [t for t in yaml_tiers if t not in runtime_tier_set]
            ok = len(missing) == 0
            checks.append({
                "label": "business tiers in yaml present in runtime",
                "ok": ok,
                "detail": f"{len(yaml_tiers)} tiers in yaml, {len(runtime_tier_list)} in runtime",
            })
            if not ok:
                checks[-1]["missing"] = missing
                problems += 1
    except Exception as exc:
        checks.append({"label": "business tiers in yaml present in runtime", "ok": False, "detail": str(exc)})
        problems += 1

    result = {
        "config_files": file_results,
        "consistency_checks": checks,
        "all_ok": problems == 0,
    }

    if "--json" in argv:
        print(_json.dumps(result, indent=2))
        return 0 if result["all_ok"] else 1

    print("Link configuration")
    print("")
    print("Config files:")
    for entry in file_results:
        status = entry.get("status", "?")
        label = entry.get("label", entry.get("path", "?"))
        if status == "ok":
            print(f"  OK: {label} ({entry.get('version', '?')})")
        elif status == "missing":
            print(f"  MISSING: {entry['path']}")
        else:
            print(f"  ERROR: {label} - {entry.get('error', status)}")

    print("")
    print("Consistency:")
    for check in checks:
        indicator = "OK" if check["ok"] else "DRIFT"
        print(f"  {indicator}: {check['label']} ({check.get('detail', '')})")
        if not check["ok"]:
            for extra_key in ("yaml_only", "runtime_only", "missing"):
                if extra_key in check:
                    print(f"    {extra_key}: {check[extra_key]}")

    print("")
    if problems == 0:
        print("config OK")
    else:
        print(f"config FAILED ({problems} problem(s))")
    return 0 if problems == 0 else 1


def _cmd_growth(argv: list[str]) -> int:
    """Growth mode subcommand dispatcher.

    Usage: python3 link.py growth <subcommand> [args...]

    Subcommands:
      status     Render a read-only Growth mode status console.
      proposals  View control-plane proposal cards.
      propose    Mine research into proposals (dry-run by default).
      approve    Accept a pending proposal.
      reject     Reject a pending proposal.
      e2e-summary Build a compact deterministic source-aware Growth decision.
    """
    subcommand = argv[0] if argv else ""
    if subcommand in ("status", "--json", ""):
        from link_modes.growth.link_growth_console import main as _growth_main

        return _growth_main(argv if subcommand == "status" else [])
    if subcommand == "proposals":
        from link_modes.growth.link_growth_console import proposals_main as _growth_proposals_main

        return _growth_proposals_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "propose":
        from link_modes.growth.link_growth_console import propose_main as _growth_propose_main

        return _growth_propose_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "approve":
        from link_modes.growth.link_growth_console import approve_main as _growth_approve_main

        return _growth_approve_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "reject":
        from link_modes.growth.link_growth_console import reject_main as _growth_reject_main

        return _growth_reject_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "handoff":
        from link_modes.growth.link_growth_console import handoff_main as _growth_handoff_main

        return _growth_handoff_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "handoffs":
        from link_modes.growth.link_growth_console import handoffs_main as _growth_handoffs_main

        return _growth_handoffs_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execute":
        from link_modes.growth.link_growth_console import execute_main as _growth_execute_main

        return _growth_execute_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "receipts":
        from link_modes.growth.link_growth_console import receipts_main as _growth_receipts_main

        return _growth_receipts_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "finalize":
        from link_modes.growth.link_growth_console import finalize_main as _growth_finalize_main

        return _growth_finalize_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-policy":
        from link_modes.growth.link_growth_console import growth_source_cache_policy_main as _growth_source_cache_policy_main

        return _growth_source_cache_policy_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-key":
        from link_modes.growth.link_growth_console import growth_source_cache_key_main as _growth_source_cache_key_main

        return _growth_source_cache_key_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-manifest":
        from link_modes.growth.link_growth_console import growth_source_cache_manifest_main as _growth_source_cache_manifest_main

        return _growth_source_cache_manifest_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-persistent":
        from link_modes.growth.link_growth_console import growth_source_cache_persistent_main as _growth_source_cache_persistent_main

        return _growth_source_cache_persistent_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-status":
        from link_modes.growth.link_growth_console import growth_source_cache_status_main as _growth_source_cache_status_main

        return _growth_source_cache_status_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-clear":
        from link_modes.growth.link_growth_console import growth_source_cache_clear_main as _growth_source_cache_clear_main

        return _growth_source_cache_clear_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache":
        from link_modes.growth.link_growth_console import growth_source_cache_main as _growth_source_cache_main

        return _growth_source_cache_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "source-cache-performance":
        from link_modes.growth.link_growth_console import growth_source_cache_performance_main as _growth_source_cache_performance_main

        return _growth_source_cache_performance_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "persistent-cache-performance":
        from link_modes.growth.link_growth_console import growth_persistent_cache_performance_main as _growth_persistent_cache_performance_main

        return _growth_persistent_cache_performance_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "e2e-cache":
        from link_modes.growth.link_growth_console import growth_e2e_cache_main as _growth_e2e_cache_main

        return _growth_e2e_cache_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "e2e-summary":
        from link_modes.growth.link_growth_console import growth_e2e_summary_main as _growth_e2e_summary_main

        return _growth_e2e_summary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "opportunity-score":
        from link_modes.growth.link_growth_console import growth_opportunity_score_main as _growth_opportunity_score_main

        return _growth_opportunity_score_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "e2e-performance":
        from link_modes.growth.link_growth_console import growth_e2e_performance_main as _growth_e2e_performance_main

        return _growth_e2e_performance_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-inventory":
        from link_modes.growth.link_growth_console import archive_inventory_main as _growth_archive_inventory_main

        return _growth_archive_inventory_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-extract":
        from link_modes.growth.link_growth_console import archive_extract_main as _growth_archive_extract_main

        return _growth_archive_extract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-catalog":
        from link_modes.growth.link_growth_console import archive_catalog_main as _growth_archive_catalog_main

        return _growth_archive_catalog_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-queue":
        from link_modes.growth.link_growth_console import archive_queue_main as _growth_archive_queue_main

        return _growth_archive_queue_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-mine":
        from link_modes.growth.link_growth_console import archive_mine_main as _growth_archive_mine_main

        return _growth_archive_mine_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-batch-mine":
        from link_modes.growth.link_growth_console import archive_batch_mine_main as _growth_archive_batch_mine_main

        return _growth_archive_batch_mine_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-code-queue":
        from link_modes.growth.link_growth_console import archive_code_queue_main as _growth_archive_code_queue_main

        return _growth_archive_code_queue_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-code-brief":
        from link_modes.growth.link_growth_console import archive_code_brief_main as _growth_archive_code_brief_main

        return _growth_archive_code_brief_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "code-brief-propose":
        from link_modes.growth.link_growth_console import code_brief_propose_main as _growth_code_brief_propose_main

        return _growth_code_brief_propose_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "code-brief-propose-batch":
        from link_modes.growth.link_growth_console import code_brief_propose_batch_main as _growth_code_brief_propose_batch_main

        return _growth_code_brief_propose_batch_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "planning-chain":
        from link_modes.growth.link_growth_console import planning_chain_main as _growth_planning_chain_main

        return _growth_planning_chain_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-readiness":
        from link_modes.growth.link_growth_console import execution_readiness_main as _growth_execution_readiness_main

        return _growth_execution_readiness_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-gates":
        from link_modes.growth.link_growth_console import execution_gates_main as _growth_execution_gates_main

        return _growth_execution_gates_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-approval-checklist":
        from link_modes.growth.link_growth_console import execution_approval_checklist_main as _growth_execution_approval_checklist_main

        return _growth_execution_approval_checklist_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execution-review":
        from link_modes.growth.link_growth_console import execution_review_main as _growth_execution_review_main

        return _growth_execution_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "workspace-boundary":
        from link_modes.growth.link_growth_console import workspace_boundary_main as _growth_workspace_boundary_main

        return _growth_workspace_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "patch-boundary":
        from link_modes.growth.link_growth_console import patch_boundary_main as _growth_patch_boundary_main

        return _growth_patch_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "verification-boundary":
        from link_modes.growth.link_growth_console import verification_boundary_main as _growth_verification_boundary_main

        return _growth_verification_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "rollback-boundary":
        from link_modes.growth.link_growth_console import rollback_boundary_main as _growth_rollback_boundary_main

        return _growth_rollback_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "evidence-collect":
        from link_modes.growth.link_growth_console import evidence_collect_main as _growth_evidence_collect_main

        return _growth_evidence_collect_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "supervised-execution":
        from link_modes.growth.link_growth_console import supervised_execution_main as _growth_supervised_execution_main

        return _growth_supervised_execution_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "supervised-execution-boundary":
        from link_modes.growth.link_growth_console import supervised_execution_boundary_main as _growth_supervised_execution_boundary_main

        return _growth_supervised_execution_boundary_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "supervised-execution-review":
        from link_modes.growth.link_growth_console import supervised_execution_review_package_main as _growth_supervised_execution_review_package_main

        return _growth_supervised_execution_review_package_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "business-opportunities":
        from link_modes.growth.link_growth_console import business_opportunities_main as _growth_business_opportunities_main

        return _growth_business_opportunities_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "business-evidence-contract":
        from link_modes.growth.link_growth_console import business_evidence_contract_main as _growth_business_evidence_contract_main

        return _growth_business_evidence_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "opportunity-review":
        from link_modes.growth.link_growth_console import opportunity_review_main as _growth_opportunity_review_main

        return _growth_opportunity_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "campaign-plan-preview":
        from link_modes.growth.link_growth_console import campaign_plan_preview_main as _growth_campaign_plan_preview_main

        return _growth_campaign_plan_preview_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "campaign-evidence-contract":
        from link_modes.growth.link_growth_console import campaign_evidence_contract_main as _growth_campaign_evidence_contract_main

        return _growth_campaign_evidence_contract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "campaign-approval-checklist":
        from link_modes.growth.link_growth_console import campaign_approval_checklist_main as _growth_campaign_approval_checklist_main

        return _growth_campaign_approval_checklist_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "campaign-review":
        from link_modes.growth.link_growth_console import campaign_review_main as _growth_campaign_review_main

        return _growth_campaign_review_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "business-development-handoff":
        from link_modes.growth.link_growth_console import business_development_handoff_main as _growth_business_development_handoff_main

        return _growth_business_development_handoff_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "patch-apply":
        from link_modes.growth.link_growth_console import patch_apply_main as _growth_patch_apply_main

        return _growth_patch_apply_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "workspace-create":
        from link_modes.growth.link_growth_console import workspace_create_main as _growth_workspace_create_main

        return _growth_workspace_create_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "workspace-cleanup":
        from link_modes.growth.link_growth_console import workspace_cleanup_main as _growth_workspace_cleanup_main

        return _growth_workspace_cleanup_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "workspace-abandon":
        from link_modes.growth.link_growth_console import workspace_abandon_main as _growth_workspace_abandon_main

        return _growth_workspace_abandon_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "run":
        from link_modes.growth.link_growth_console import run_main as _growth_run_main

        return _growth_run_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help"):
        print("Growth mode commands:")
        print("  status             Render Growth mode status console")
        print("  proposals          View control-plane proposal cards")
        print("  propose            Mine research into proposals")
        print("  approve            Accept a pending proposal")
        print("  reject             Reject a pending proposal")
        print("  handoff            Create a worker handoff from an accepted proposal")
        print("  handoffs           View existing worker handoffs")
        print("  execute            Prepare handoff for verification")
        print("  receipts           View verifier receipts")
        print("  finalize           Create finalizer receipt from verifier receipt")
        print("  archive-inventory  Scan research archives without extraction")
        print("  archive-extract    Safely extract a research archive")
        print("  archive-catalog    Catalog extracted research contents")
        print("  archive-queue      Rank extracted sources for mining")
        print("  archive-mine       Mine a ranked archive source into proposals")
        print("  archive-batch-mine Batch-mine top ranked sources")
        print("  archive-code-queue Rank code files for research mining")
        print("  archive-code-brief Create markdown brief from code files")
        print("  code-brief-propose Convert code brief candidates to proposals")
        print("  code-brief-propose-batch Preview proposals for top code queue entries")
        print("  planning-chain     Preview gaps-to-verification planning chain")
        print("  execution-readiness Preview compact execution readiness dashboard")
        print("  execution-gates    Preview execution gate stack")
        print("  execution-approval-checklist Preview human approval checklist")
        print("  execution-review   Preview compact execution review")
        print("  workspace-boundary Preview workspace creator runtime boundary")
        print("  patch-boundary     Preview patch applier runtime boundary")
        print("  verification-boundary Preview verification runner runtime boundary")
        print("  rollback-boundary Preview rollback runtime boundary")
        print("  evidence-collect  Collect workspace-local execution evidence")
        print("  supervised-execution Preview supervised execution plan")
        print("  supervised-execution-boundary Preview supervised execution write boundary")
        print("  supervised-execution-review Preview supervised execution review package")
        print("  business-opportunities Preview Growth business opportunity scan")
        print("  business-evidence-contract Preview Growth business evidence contract")
        print("  opportunity-review Preview Growth opportunity review package")
        print("  campaign-plan-preview Preview Growth campaign plan preview")
        print("  campaign-evidence-contract Preview Growth campaign evidence contract")
        print("  campaign-approval-checklist Preview Growth campaign approval checklist")
        print("  campaign-review    Preview Growth campaign review package")
        print("  business-development-handoff Preview Business Development handoff boundary")
        print("  patch-apply        Apply guarded patch inside approved workspace")
        print("  workspace-create   Create guarded temporary workspace with approval")
        print("  workspace-cleanup  Cleanup guarded temporary workspace")
        print("  workspace-abandon  Abandon guarded temporary workspace")
        print("  run                Guided Growth workflow dashboard")
        return 0
    print(f"growth: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py growth --help' for subcommands.", file=sys.stderr)
    return 2


# Local commands: (function, help_text). Functions receive the remaining argv.
_LOCAL_COMMANDS: dict[str, tuple[Callable[[list[str]], int], str]] = {
    "modes": (_cmd_modes, "List Link operating modes (base/growth/business)."),
    "roles": (_cmd_roles, "List worker safety profiles and business roles."),
    "modules": (_cmd_modules, "Preview Link module boundary registry."),
    "advisor": (_cmd_advisor, "Preview optional local advisor configuration."),
    "research": (_cmd_research, "Read-only local research target intake."),
    "business-development": (_cmd_business_development, "Business Development governance previews."),
    "business-operations": (_cmd_business_operations, "Business Operations governance previews."),
    "business": (_cmd_business, "Cross-lane business readiness governance previews."),
    "governance": (_cmd_governance, "Unified Link governance dashboard previews."),
    "control-plane": (_cmd_control_plane, "Link control-plane dashboard and health previews."),
    "simulation": (_cmd_simulation, "Dry-run business execution simulation previews."),
    "sandbox": (_cmd_sandbox, "Read-only execution readiness sandbox projections."),
    "decision": (_cmd_decision, "Read-only operator decision support previews."),
    "operator": (_cmd_operator, "Read-only operator action planning previews."),
    "sandbox-executor": (_cmd_sandbox_executor, "Read-only sandbox executor boundary previews."),
    "dashboard": (_cmd_dashboard, "Compact diagnostics dashboard."),
    "self-test": (_cmd_self_test, "Run canonical architecture smoke checks."),
    "config": (_cmd_config, "Validate Link configuration files against runtime."),
    "growth": (_cmd_growth, "Growth mode terminal console."),
}


def _print_help() -> None:
    print("Link canonical CLI")
    print("")
    print("Usage:")
    print("  python3 link.py <command> [args...]")
    print("")
    print("Commands:")
    all_names = list(_DELEGATED_COMMANDS) + list(_LOCAL_COMMANDS) + ["healthcheck"]
    width = max(len(name) for name in all_names)
    for name, (_, _, help_text) in _DELEGATED_COMMANDS.items():
        print(f"  {name.ljust(width)}  {help_text}")
    for name, (_, help_text) in _LOCAL_COMMANDS.items():
        print(f"  {name.ljust(width)}  {help_text}")
    print(f"  {'healthcheck'.ljust(width)}  Run the Link healthcheck (preserves baseline).")
    print("")
    print("Run 'python3 link.py <command> --help' for command-specific help.")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in {"-h", "--help", "help"}:
        _print_help()
        return 0

    command, rest = args[0], args[1:]

    if command == "healthcheck":
        return _run_healthcheck(rest)

    if command in _DELEGATED_COMMANDS:
        module_path, attr, _ = _DELEGATED_COMMANDS[command]
        return _delegate(module_path, attr, rest)

    if command in _LOCAL_COMMANDS:
        func, _ = _LOCAL_COMMANDS[command]
        return func(rest)

    print(f"link: unknown command: {command}", file=sys.stderr)
    print("Run 'python3 link.py --help' for the command list.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
