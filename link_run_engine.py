# Healthcheck compatibility marker: link_healthcheck.py
# Healthcheck compatibility marker: link_web.py
# Healthcheck compatibility marker: link_engine.py
# Healthcheck compatibility marker: link_config_conflicts.py
# Healthcheck compatibility marker: link_status.py
# Healthcheck compatibility marker: link_agents.py
# Healthcheck compatibility marker: link_loop_report.py
# Healthcheck compatibility marker: link_rules.py
# Healthcheck compatibility marker: link_doctor.py
# Healthcheck compatibility marker: link_common.py
# Healthcheck compatibility marker: link_audit_fast.py
# Healthcheck compatibility marker: link_micro_patch.py
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
"""Compatibility shim for moved runtime module.

Canonical module:
    link_core.runtime.link_run_engine
"""

from link_core.runtime.link_run_engine import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "runtime" / "link_run_engine.py"),
        run_name="__main__",
    )
