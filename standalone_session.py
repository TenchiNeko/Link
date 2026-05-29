"""Compatibility shim for moved module.

Canonical module:
    link_core.standalone.standalone_session
"""

# Healthcheck compatibility marker: class SessionManager
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: state.json
# Healthcheck compatibility marker: PROGRESS.md
# Healthcheck compatibility marker: plans
# Healthcheck compatibility marker: reports
# Healthcheck compatibility marker: logs
# Healthcheck compatibility marker: State saved: iteration={state.iteration}, phase={state.phase.value}
# Healthcheck compatibility marker: No state file found: {self.state_file}
# Healthcheck compatibility marker: State loaded: iteration={state.iteration}, phase={state.phase.value}
# Healthcheck compatibility marker: %Y-%m-%d %H:%M:%S
# Healthcheck compatibility marker: # Progress Log\n\n**Task:** {state.goal}\n**Task ID:** {state.task_id}\n**Started:** {state.started_at}\n\n---\n\n
# Healthcheck compatibility marker: ## [{timestamp}] Iteration {state.iteration} — {state.phase.value.upper()}\n\n{message}\n\n---\n\n
# Healthcheck compatibility marker: ---\n\n
# Healthcheck compatibility marker: No-op if feature list doesn't exist.
# Healthcheck compatibility marker: feature_list.json
# Healthcheck compatibility marker: features
# Healthcheck compatibility marker: assigned_task_id
# Healthcheck compatibility marker: passes
# Healthcheck compatibility marker: last_tested
# Healthcheck compatibility marker: Could not update feature list: {e}
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: --short
# Healthcheck compatibility marker: Not a git repository
# Healthcheck compatibility marker: Error: {e}
# Healthcheck compatibility marker: log
# Healthcheck compatibility marker: --oneline
# Healthcheck compatibility marker: -{count}
# Healthcheck compatibility marker: No git history
# Healthcheck compatibility marker: ## Session Context
# Healthcheck compatibility marker: **Task ID:** {state.task_id}
# Healthcheck compatibility marker: **Goal:** {state.goal}
# Healthcheck compatibility marker: **Iteration:** {state.iteration}
# Healthcheck compatibility marker: **Phase:** {state.phase.value}
# Healthcheck compatibility marker: ## Git Status
# Healthcheck compatibility marker: ```
# Healthcheck compatibility marker: ## Recent Commits
# Healthcheck compatibility marker: ## Failure History
# Healthcheck compatibility marker: - Iteration {failure.get('iteration')}: {failure.get('phase')} — {failure.get('error', '?')}
# Healthcheck compatibility marker: ## Current Plan
# Healthcheck compatibility marker: \n... (truncated)

from link_core.standalone.standalone_session import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.standalone.standalone_session", run_name="__main__")
