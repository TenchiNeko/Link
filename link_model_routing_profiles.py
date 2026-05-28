"""Compatibility shim for moved routing/profile module.

Canonical module:
    link_core.routing.link_model_routing_profiles
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "routing" / "link_model_routing_profiles.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.routing.link_model_routing_profiles import *  # noqa: F401,F403
