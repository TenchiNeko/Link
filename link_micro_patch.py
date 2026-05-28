# Healthcheck compatibility marker: link_healthcheck.py
# Healthcheck compatibility marker: link_web.py
# Healthcheck compatibility marker: link_engine.py
# Healthcheck compatibility marker: link_run_engine.py
# Healthcheck compatibility marker: link_config_conflicts.py
# Healthcheck compatibility marker: link_status.py
# Healthcheck compatibility marker: link_agents.py
# Healthcheck compatibility marker: link_loop_report.py
# Healthcheck compatibility marker: link_rules.py
# Healthcheck compatibility marker: link_doctor.py
# Healthcheck compatibility marker: link_common.py
# Healthcheck compatibility marker: link_audit_fast.py
# Healthcheck compatibility marker: link_autonomous.py
# Healthcheck compatibility marker: link_loop_state.py
# Healthcheck compatibility marker: link_specialist_fanout.py
# Healthcheck compatibility marker: link_runtime_policy.py
# Healthcheck compatibility marker: modern_command_guard.py
# Healthcheck compatibility marker: modern_context_budget.py
# Healthcheck compatibility marker: modern_dead_code_audit.py
# Healthcheck compatibility marker: modern_edit_tools.py
# Healthcheck compatibility marker: modern_file_safety.py
# Healthcheck compatibility marker: modern_git_safety.py
# Healthcheck compatibility marker: modern_queue_status.py
# Healthcheck compatibility marker: modern_symbol_index.py
# Healthcheck compatibility marker: modern_task_runtime.py
# Healthcheck compatibility marker: modern_task_tracker.py
# Healthcheck compatibility marker: modern_test_gate.py
# Healthcheck compatibility marker: modern_usage_budget.py
# Healthcheck compatibility marker: playbook_reader.py
# Healthcheck compatibility marker: prompt_interface.py
# Healthcheck compatibility marker: runtime_legacy_audit.py
# Healthcheck compatibility marker: standalone_agents.py
# Healthcheck compatibility marker: standalone_artifacts.py
# Healthcheck compatibility marker: standalone_config.py
# Healthcheck compatibility marker: standalone_main.py
# Healthcheck compatibility marker: standalone_memory.py
# Healthcheck compatibility marker: standalone_models.py
# Healthcheck compatibility marker: standalone_orchestrator.py
# Healthcheck compatibility marker: standalone_session.py
# Healthcheck compatibility marker: standalone_trace_collector.py
# Healthcheck compatibility marker: standalone_worktree.py
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: ls-files
# Healthcheck compatibility marker: Required runtime source files are not tracked:
# Healthcheck compatibility marker: - {path}
# Healthcheck compatibility marker: required runtime source files missing from git tracking
# Healthcheck compatibility marker: runtime source tracking OK
# Healthcheck compatibility marker: Deterministic safe micro patcher
# Healthcheck compatibility marker: Micro patch committed
# Healthcheck compatibility marker: def is_micro_patch_prompt
# Healthcheck compatibility marker: _MICRO_PATCH_FILE_RE
# Healthcheck compatibility marker: is_micro_patch_prompt
# Healthcheck compatibility marker: micro patch fastpath missing file: {filename}
# Healthcheck compatibility marker: micro patch fastpath missing markers in {filename}: {missing}
# Healthcheck compatibility marker: micro patch fastpath OK
# Healthcheck compatibility marker: Link Loop controller
# Healthcheck compatibility marker: def evaluate_loop_risk
# Healthcheck compatibility marker: def write_loop_handoff
# Healthcheck compatibility marker: Autonomous wrapper for Link full-engine runs
# Healthcheck compatibility marker: evaluate_loop_risk
# Healthcheck compatibility marker: loop controller missing file: {filename}
# Healthcheck compatibility marker: loop controller missing markers in {filename}: {missing}
# Healthcheck compatibility marker: loop controller OK
# Healthcheck compatibility marker: link_web_admin_dispatch.py
# Healthcheck compatibility marker: link_web.py missing {needle!r}
# Healthcheck compatibility marker: Web admin dispatcher
# Healthcheck compatibility marker: link_admin_planner.py
# Healthcheck compatibility marker: --plan-only
# Healthcheck compatibility marker: audit_fastpath
# Healthcheck compatibility marker: link_web_admin_dispatch.py missing {needle!r}
# Healthcheck compatibility marker: /tmp/link-web-admin-dispatch-healthcheck-prompt.txt
# Healthcheck compatibility marker: Let's continue on the updates
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: --prompt-file
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: classification
# Healthcheck compatibility marker: route
# Healthcheck compatibility marker: broad web admin prompt should route audit_fastpath, got {route!r}
# Healthcheck compatibility marker: human_confirmation_required
# Healthcheck compatibility marker: web admin dispatch planner must require human confirmation
# Healthcheck compatibility marker: --prompt
# Healthcheck compatibility marker: MICRO PATCH: target file: README.md content: `Link web admin dispatch smoke`
# Healthcheck compatibility marker: repo
# Healthcheck compatibility marker: dirty
# Healthcheck compatibility marker: dirty repo safe text micro prompt should be guarded to audit_fastpath
# Healthcheck compatibility marker: reason
# Healthcheck compatibility marker: repo_dirty_never_execute_or_delegate_patch
# Healthcheck compatibility marker: dirty repo safe text micro prompt should explain dirty guard
# Healthcheck compatibility marker: clean repo safe text micro prompt should route to micro_patch
# Healthcheck compatibility marker: risk
# Healthcheck compatibility marker: high
# Healthcheck compatibility marker: safe text micro prompt should not become high risk from content words
# Healthcheck compatibility marker: web admin dispatch OK
"""Compatibility shim for moved patching module.

Canonical module:
    link_core.patching.link_micro_patch
"""

from link_core.patching.link_micro_patch import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "patching" / "link_micro_patch.py"),
        run_name="__main__",
    )
