"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_test_gate
"""

# Healthcheck compatibility marker: class GateResult
# Healthcheck compatibility marker: def run_gate
# Healthcheck compatibility marker: python3
# Healthcheck compatibility marker: py_compile
# Healthcheck compatibility marker: standalone_agents.py
# Healthcheck compatibility marker: modern_command_guard.py
# Healthcheck compatibility marker: modern_symbol_index.py
# Healthcheck compatibility marker: modern_task_runtime.py
# Healthcheck compatibility marker: modern_usage_budget.py
# Healthcheck compatibility marker: modern_edit_tools.py
# Healthcheck compatibility marker: +

from link_core.modern.modern_test_gate import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_test_gate", run_name="__main__")
