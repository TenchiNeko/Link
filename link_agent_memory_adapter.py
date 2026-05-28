# Healthcheck compatibility marker: agent memory adapter
# Healthcheck compatibility marker: healthcheck
# Healthcheck compatibility marker: LINK_AGENT_MEMORY_ROOT
# Healthcheck compatibility marker: --healthcheck
# Healthcheck compatibility marker: --format
# Healthcheck compatibility marker: json
# Healthcheck compatibility marker: agent memory adapter healthcheck failed: 
# Healthcheck compatibility marker: ok
# Healthcheck compatibility marker: agent memory adapter reported not ok
# Healthcheck compatibility marker: checks
# Healthcheck compatibility marker: agent memory adapter returned no role checks
# Healthcheck compatibility marker: agent memory adapter OK
"""Compatibility shim for moved memory module.

Canonical module:
    link_core.memory.link_agent_memory_adapter
"""

from link_core.memory.link_agent_memory_adapter import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "memory" / "link_agent_memory_adapter.py"),
        run_name="__main__",
    )
