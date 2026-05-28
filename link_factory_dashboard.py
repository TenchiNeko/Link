"""Compatibility shim for moved Business Link module.

Canonical module:
    link_modes.business.link_factory_dashboard
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_modes" / "business" / "link_factory_dashboard.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_modes.business.link_factory_dashboard import *  # noqa: F401,F403

# Compatibility healthcheck markers:
# from link_upgrade_status import render_upgrade_badges
# /upgrade-status
# render_upgrade_badges()
