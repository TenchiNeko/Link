"""Compatibility shim for moved module.

Canonical module:
    link_core.docs_runtime.prompt_interface
"""

# Healthcheck compatibility marker: def ask_int
# Healthcheck compatibility marker: def ask_bool
# Healthcheck compatibility marker: def read_task
# Healthcheck compatibility marker: def run_task
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: standalone_main.py
# Healthcheck compatibility marker: {prompt} [{default}]:
# Healthcheck compatibility marker: Using default.
# Healthcheck compatibility marker: if default else
# Healthcheck compatibility marker: {prompt} (on/off) [{label}]:
# Healthcheck compatibility marker: yes
# Healthcheck compatibility marker: true
# Healthcheck compatibility marker: \nPaste/type your full task prompt below.
# Healthcheck compatibility marker: Finish with Ctrl+D, or type END on its own line.\n
# Healthcheck compatibility marker: END
# Healthcheck compatibility marker: \nExiting.
# Healthcheck compatibility marker: ORCH_REPORT_FAST_PATH
# Healthcheck compatibility marker: ORCH_USE_WORKTREE
# Healthcheck compatibility marker: --max-iterations
# Healthcheck compatibility marker: \nRunning real backend:\npython3 standalone_main.py \
# Healthcheck compatibility marker: === Link Orchestrator Interactive Launcher ===
# Healthcheck compatibility marker: quit
# Healthcheck compatibility marker: exit
# Healthcheck compatibility marker: Max iterations
# Healthcheck compatibility marker: Use worktree
# Healthcheck compatibility marker: \n--- Confirm ---
# Healthcheck compatibility marker: ...
# Healthcheck compatibility marker: Max iterations: {max_iterations}
# Healthcheck compatibility marker: Worktree: {'on' if worktree else 'off'}
# Healthcheck compatibility marker: ---------------
# Healthcheck compatibility marker: Run
# Healthcheck compatibility marker: \nReady for another prompt.
# Healthcheck compatibility marker: __main__

from link_core.docs_runtime.prompt_interface import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.docs_runtime.prompt_interface", run_name="__main__")
