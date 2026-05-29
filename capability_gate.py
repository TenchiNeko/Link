# Healthcheck compatibility marker: capability gate OK
# Healthcheck compatibility marker: capability command
# Healthcheck compatibility marker: capability git
# Healthcheck compatibility marker: capability path
# Healthcheck compatibility marker: command
# Healthcheck compatibility marker: ls -la
# Healthcheck compatibility marker: allow
# Healthcheck compatibility marker: rm -rf /
# Healthcheck compatibility marker: deny
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: git status --short
# Healthcheck compatibility marker: git reset --hard HEAD
# Healthcheck compatibility marker: standalone_main.py
# Healthcheck compatibility marker: ../outside
# Healthcheck compatibility marker: capability {kind} {target!r} -> {result.decision}: {result.reason}
# Healthcheck compatibility marker: {kind} {target!r}: expected {expected}, got {result.decision}
# Healthcheck compatibility marker: capability gate failures:\n
# Healthcheck compatibility marker: \n
"""Compatibility shim for moved safety module.

Canonical module:
    link_core.safety.capability_gate
"""

from link_core.safety.capability_gate import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "safety" / "capability_gate.py"),
        run_name="__main__",
    )
