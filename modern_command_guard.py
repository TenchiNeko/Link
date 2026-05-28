"""Compatibility shim for moved safety/guard module.

Canonical module:
    link_core.safety.modern_command_guard
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "safety" / "modern_command_guard.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.safety.modern_command_guard import *  # noqa: F401,F403
