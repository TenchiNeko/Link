"""Compatibility shim for moved recovery/dashboard module.

Canonical module:
    link_core.dashboard.rollback_advisor_dashboard
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "dashboard" / "rollback_advisor_dashboard.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.dashboard.rollback_advisor_dashboard import *  # noqa: F401,F403
