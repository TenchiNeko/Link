"""Compatibility shim for moved Growth Link module.

Canonical module:
    link_modes.growth.link_self_learning_dashboard
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_modes" / "growth" / "link_self_learning_dashboard.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_modes.growth.link_self_learning_dashboard import *  # noqa: F401,F403
