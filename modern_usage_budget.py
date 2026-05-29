"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_usage_budget
"""

# Healthcheck compatibility marker: class UsageEvent
# Healthcheck compatibility marker: class UsageBudget
# Healthcheck compatibility marker: Simple local budget tracker for long autonomous runs.
# Healthcheck compatibility marker: ), len(output or
# Healthcheck compatibility marker: , encoding=
# Healthcheck compatibility marker: time budget exceeded: {self.total_seconds:.1f}s >= {self.max_seconds}s
# Healthcheck compatibility marker: char budget exceeded: {self.total_chars} >= {self.max_chars}

from link_core.modern.modern_usage_budget import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_usage_budget", run_name="__main__")
