"""Compatibility shim for moved routing/profile module.

Canonical module:
    link_core.routing.test_profile_gate
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "routing" / "test_profile_gate.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.routing.test_profile_gate import *  # noqa: F401,F403
