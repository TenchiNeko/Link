"""Compatibility shim for moved dashboard module.

Canonical module:
    link_core.dashboard.recovery_plan_dashboard_web_admin
"""

from link_core.dashboard.recovery_plan_dashboard_web_admin import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "dashboard" / "recovery_plan_dashboard_web_admin.py"),
        run_name="__main__",
    )
