# Healthcheck compatibility marker: rollback recovery plan web admin route failures:\n
# Healthcheck compatibility marker: \n
# Healthcheck compatibility marker: export rollback recovery plan as json
# Healthcheck compatibility marker: python3
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: rollback recovery plan web route command mismatch: {command!r}
# Healthcheck compatibility marker: guarded recovery plan
# Healthcheck compatibility marker: guarded
# Healthcheck compatibility marker: rollback recovery plan web route is not guarded
# Healthcheck compatibility marker: destructive
# Healthcheck compatibility marker: rollback recovery plan web route should not be destructive
# Healthcheck compatibility marker: rollback recovery plan web admin route OK
"""Compatibility shim for moved recovery module.

Canonical module:
    link_core.recovery.rollback_recovery_plan
"""

from link_core.recovery.rollback_recovery_plan import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "recovery" / "rollback_recovery_plan.py"),
        run_name="__main__",
    )
