# Healthcheck compatibility marker: Autonomous tick runner
"""Compatibility shim for moved autonomy module.

Canonical module:
    link_core.autonomy.link_autonomous_tick_runner
"""

from link_core.autonomy.link_autonomous_tick_runner import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "autonomy" / "link_autonomous_tick_runner.py"),
        run_name="__main__",
    )
